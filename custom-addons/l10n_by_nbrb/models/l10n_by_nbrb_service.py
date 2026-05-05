import logging
import time
import traceback
from datetime import date, datetime, timedelta

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


API_BASE = 'https://api.nbrb.by'
EMPTY_RATE_FALLBACK = 0.0001


class L10nByNbrbService(models.AbstractModel):
    """Сервис загрузки курсов из api.nbrb.by.

    Никогда не выбрасывает исключения наружу: при сбое API создаётся запись
    лога со статусом error/empty, существующие курсы остаются нетронутыми.
    Если ответ пустой или невалидный — для отслеживаемых валют пишется
    res.currency.rate с фолбэк-значением 0.0001 (constraint rate>0 не падает,
    в UI и расчётах это эффективный «ноль»).
    """
    _name = 'l10n.by.nbrb.service'
    _description = 'Сервис загрузки курсов НБ РБ'

    # ---------- HTTP ----------

    def _http_get(self, path, params=None, timeout=10):
        url = f'{API_BASE}{path}'
        return requests.get(url, params=params or {}, timeout=timeout)

    def _call_with_retry(self, path, params, settings):
        last_err = None
        for attempt in range(1, settings.retry_count + 1):
            try:
                resp = self._http_get(path, params=params,
                                      timeout=settings.request_timeout_seconds)
                if resp.status_code == 200:
                    try:
                        return resp.json(), None
                    except ValueError as e:
                        last_err = (
                            f'JSON parse error: {e}. Body: {resp.text[:500]}'
                        )
                else:
                    last_err = f'HTTP {resp.status_code}: {resp.text[:300]}'
            except requests.Timeout:
                last_err = f'Timeout (>{settings.request_timeout_seconds}s)'
            except requests.ConnectionError as e:
                last_err = f'ConnectionError: {e}'
            except Exception as e:
                last_err = f'{type(e).__name__}: {e}'
            if attempt < settings.retry_count and settings.retry_interval_minutes > 0:
                # В контексте cron нет смысла спать минутами — это блокирует worker.
                # Ставим маленькую паузу; полный retry-цикл по минутам делает сам cron
                # на следующей итерации, если установлена опция auto-update.
                time.sleep(min(settings.retry_interval_minutes, 2))
        return None, last_err

    # ---------- Public ----------

    def test_connection(self):
        """Возвращает количество валют в ответе /exrates/currencies или None."""
        settings = self.env['l10n.by.nbrb.settings'].get_settings()
        data, err = self._call_with_retry('/exrates/currencies', {}, settings)
        Log = self.env['l10n.by.nbrb.log']
        if data is None:
            Log.create({
                'run_type': 'test',
                'state': 'error',
                'message': err or 'Unknown error',
            })
            return None
        Log.create({
            'run_type': 'test',
            'state': 'success',
            'rates_loaded': 0,
            'message': _('Получено валют в справочнике: %s', len(data)),
        })
        return len(data)

    def update_rates_for_today(self, run_type='manual', currencies=None):
        return self.update_rates_for_date(date.today(), run_type=run_type,
                                          currencies=currencies)

    def update_rates_for_date(self, target_date, run_type='auto', currencies=None,
                              skip_holiday_check=False):
        """Загружает курсы на указанную дату. Никогда не выбрасывает наружу.

        :param skip_holiday_check: True для исторической загрузки, чтобы не
            пропускать прошедшие выходные.
        """
        Log = self.env['l10n.by.nbrb.log']
        settings = self.env['l10n.by.nbrb.settings'].get_settings()
        started = time.monotonic()

        if not skip_holiday_check and not self._is_working_day(target_date):
            return Log.create({
                'run_type': run_type,
                'state': 'skip',
                'target_date': target_date,
                'message': _('Нерабочий день — НБ РБ не устанавливает курсы.'),
                'duration_ms': int((time.monotonic() - started) * 1000),
            })

        try:
            data, err = self._call_with_retry(
                '/exrates/rates',
                {'periodicity': 0, 'ondate': target_date.strftime('%Y-%m-%d')},
                settings,
            )
        except Exception:
            data, err = None, traceback.format_exc()

        target_currencies = currencies if currencies else settings.tracked_currency_ids
        codes_for_fallback = (target_currencies.mapped('name')
                              if target_currencies else [])

        if data is None:
            # API недоступен — пишем фолбэк-курс 0.0001 для отслеживаемых валют,
            # чтобы математика в документах не падала на отсутствие записи курса
            # на эту дату. Фактические курсы остаются у предыдущих записей.
            applied = self._apply_fallback_rates(target_currencies, target_date)
            log = Log.create({
                'run_type': run_type,
                'state': 'error',
                'target_date': target_date,
                'rates_loaded': applied,
                'currency_codes': ', '.join(codes_for_fallback),
                'message': _('Ошибка обращения к api.nbrb.by: %s. Записан '
                             'фолбэк %s для %s валют.', err, EMPTY_RATE_FALLBACK,
                             applied),
                'error_traceback': err,
                'duration_ms': int((time.monotonic() - started) * 1000),
            })
            self._notify_error(log, settings)
            return log

        if not data:
            applied = self._apply_fallback_rates(target_currencies, target_date)
            return Log.create({
                'run_type': run_type,
                'state': 'empty',
                'target_date': target_date,
                'rates_loaded': applied,
                'currency_codes': ', '.join(codes_for_fallback),
                'message': _('API вернул пустой массив (нерабочий день / праздник). '
                             'Записан фолбэк %s для %s валют.',
                             EMPTY_RATE_FALLBACK, applied),
                'duration_ms': int((time.monotonic() - started) * 1000),
            })

        applied, breaches = self._apply_rates(data, target_date, target_currencies)
        log = Log.create({
            'run_type': run_type,
            'state': 'success' if applied > 0 else 'empty',
            'target_date': target_date,
            'rates_loaded': applied,
            'currency_codes': ', '.join(sorted({r.get('Cur_Abbreviation', '')
                                                for r in data})),
            'message': _('Загружено валют: %s.', applied),
            'duration_ms': int((time.monotonic() - started) * 1000),
        })
        if applied > 0:
            settings.last_success_at = fields.Datetime.now()
        for breach in breaches:
            self._notify_threshold_breach(breach, settings)
        return log

    # ---------- Helpers ----------

    @staticmethod
    def _is_working_day(d):
        # Понедельник=0 ... Воскресенье=6. НБ РБ устанавливает курсы только пн-пт.
        return d.weekday() < 5

    def _apply_rates(self, raw_data, target_date, target_currencies):
        """Создаёт/обновляет res.currency.rate из ответа API.

        Возвращает (count_applied, threshold_breaches).
        """
        Currency = self.env['res.currency']
        Rate = self.env['res.currency.rate']
        company = self.env.company
        applied = 0
        breaches = []
        tracked_codes = set(target_currencies.mapped('name')) if target_currencies else None

        for row in raw_data:
            code = row.get('Cur_Abbreviation')
            if not code:
                continue
            if tracked_codes is not None and code not in tracked_codes:
                continue
            currency = Currency.with_context(active_test=False).search(
                [('name', '=', code)], limit=1,
            )
            if not currency:
                continue
            scale = row.get('Cur_Scale') or currency.nbrb_scale or 1
            official = row.get('Cur_OfficialRate')
            # НБ РБ публикует Cur_OfficialRate = «сколько BYN за Cur_Scale единиц
            # валюты». Odoo хранит res.currency.rate.rate как «сколько единиц
            # этой валюты в 1 единице базовой валюты компании» (см.
            # _compute_current_rate в odoo/addons/base/models/res_currency.py:
            # currency.rate = stored_currency / stored_base). Если базовая = BYN,
            # то для корректной конвертации храним обратное значение:
            # stored_rate = Cur_Scale / Cur_OfficialRate.
            try:
                official_f = float(official) if official is not None else 0.0
                if official_f > 0:
                    rate_value = float(scale) / official_f
                else:
                    rate_value = EMPTY_RATE_FALLBACK
            except (TypeError, ValueError, ZeroDivisionError):
                rate_value = EMPTY_RATE_FALLBACK
            if rate_value <= 0:
                rate_value = EMPTY_RATE_FALLBACK

            cur_id = row.get('Cur_ID')
            update_vals = {}
            if cur_id and currency.nbrb_cur_id != cur_id:
                update_vals['nbrb_cur_id'] = cur_id
            if scale and currency.nbrb_scale != scale:
                update_vals['nbrb_scale'] = scale
            if not currency.active:
                update_vals['active'] = True
            cur_name = row.get('Cur_Name')
            if cur_name and not currency.full_name:
                update_vals['full_name'] = cur_name
            if update_vals:
                currency.write(update_vals)

            previous_rate = Rate.search([
                ('currency_id', '=', currency.id),
                ('company_id', '=', company.id),
                ('name', '<', target_date),
            ], order='name desc', limit=1)
            existing = Rate.search([
                ('currency_id', '=', currency.id),
                ('company_id', '=', company.id),
                ('name', '=', target_date),
            ], limit=1)
            if existing:
                existing.write({'rate': rate_value})
            else:
                Rate.create({
                    'currency_id': currency.id,
                    'company_id': company.id,
                    'name': target_date,
                    'rate': rate_value,
                })
            applied += 1

            if previous_rate and previous_rate.rate > 0 and rate_value > EMPTY_RATE_FALLBACK:
                delta_pct = abs(rate_value - previous_rate.rate) / previous_rate.rate * 100.0
                breaches.append({
                    'currency': currency,
                    'old_rate': previous_rate.rate,
                    'new_rate': rate_value,
                    'delta_pct': delta_pct,
                    'date': target_date,
                })
        return applied, breaches

    def _apply_fallback_rates(self, target_currencies, target_date):
        """Пишет фолбэк-курс 0.0001 для отслеживаемых валют, если на эту дату
        ещё нет записи. Существующие курсы НЕ перезаписываем.
        """
        if not target_currencies:
            return 0
        Rate = self.env['res.currency.rate']
        company = self.env.company
        applied = 0
        for currency in target_currencies:
            existing = Rate.search([
                ('currency_id', '=', currency.id),
                ('company_id', '=', company.id),
                ('name', '=', target_date),
            ], limit=1)
            if existing:
                continue
            Rate.create({
                'currency_id': currency.id,
                'company_id': company.id,
                'name': target_date,
                'rate': EMPTY_RATE_FALLBACK,
            })
            applied += 1
        return applied

    def _notify_error(self, log, settings):
        """Шлёт email о провале загрузки администратору. Не падает наружу."""
        recipients = []
        if settings.error_recipient_user_id and settings.error_recipient_user_id.email:
            recipients.append(settings.error_recipient_user_id.email)
        if settings.error_recipient_email:
            recipients.append(settings.error_recipient_email)
        if not recipients:
            return
        template = self.env.ref('l10n_by_nbrb.mail_template_nbrb_error',
                                raise_if_not_found=False)
        if not template:
            return
        try:
            template.with_context(
                error_email_to=','.join(recipients),
            ).send_mail(log.id, force_send=False)
        except Exception:
            _logger.exception('NBRB error notification failed')

    def _notify_threshold_breach(self, breach, settings):
        if breach['delta_pct'] < settings.change_threshold_percent:
            return
        recipients = []
        if settings.error_recipient_user_id and settings.error_recipient_user_id.email:
            recipients.append(settings.error_recipient_user_id.email)
        if settings.error_recipient_email:
            recipients.append(settings.error_recipient_email)
        if not recipients:
            return
        subject = _('НБ РБ: резкое изменение курса %s', breach['currency'].name)
        body = _(
            'Курс %(code)s на %(date)s изменился с %(old).4f на %(new).4f '
            '(%(delta).2f%%). Порог: %(threshold).2f%%.',
            code=breach['currency'].name,
            date=breach['date'],
            old=breach['old_rate'],
            new=breach['new_rate'],
            delta=breach['delta_pct'],
            threshold=settings.change_threshold_percent,
        )
        self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': f'<p>{body}</p>',
            'email_to': ','.join(recipients),
            'auto_delete': True,
        }).send()

    # ---------- Cron entrypoints ----------

    @api.model
    def cron_update_rates(self):
        """Точка входа из ir.cron — никогда не падает."""
        try:
            settings = self.env['l10n.by.nbrb.settings'].get_settings()
            if not settings.auto_update_enabled:
                self.env['l10n.by.nbrb.log'].create({
                    'run_type': 'auto',
                    'state': 'skip',
                    'message': _('Автозагрузка отключена в настройках.'),
                })
                return
            self.update_rates_for_today(run_type='auto')
        except Exception:
            _logger.exception('NBRB cron failed')
            self.env['l10n.by.nbrb.log'].sudo().create({
                'run_type': 'auto',
                'state': 'error',
                'message': _('Непредвиденная ошибка cron, см. лог сервера.'),
                'error_traceback': traceback.format_exc(),
            })

    def load_historical_range(self, date_from, date_to, currencies=None):
        """Загружает курсы за каждую рабочую дату диапазона.

        Возвращает (loaded_days, error_days, weekend_days).
        """
        loaded = errors = weekends = 0
        d = date_from
        while d <= date_to:
            if not self._is_working_day(d):
                weekends += 1
                self.env['l10n.by.nbrb.log'].create({
                    'run_type': 'historical',
                    'state': 'skip',
                    'target_date': d,
                    'message': _('Нерабочий день, пропуск.'),
                })
            else:
                log = self.update_rates_for_date(d, run_type='historical',
                                                 currencies=currencies,
                                                 skip_holiday_check=True)
                if log.state == 'success':
                    loaded += 1
                else:
                    errors += 1
                # Соблюдаем рекомендуемый лимит API: не чаще 1 запроса в секунду.
                time.sleep(1)
            d += timedelta(days=1)
        return loaded, errors, weekends
