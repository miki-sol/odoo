from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nByNbrbSettings(models.Model):
    _name = 'l10n.by.nbrb.settings'
    _description = 'Настройки загрузки курсов НБ РБ'
    _rec_name = 'display_name'

    display_name = fields.Char(default='Настройки курсов НБ РБ')
    auto_update_enabled = fields.Boolean(
        string='Включить автозагрузку',
        default=True,
        help='Если выключено — курсы загружаются только вручную.',
    )
    update_hour = fields.Float(
        string='Время автозагрузки',
        default=9.0,
        help='Час суток (0–24) по часовому поясу компании. Используется для отображения; '
             'фактический запуск управляется записью ir.cron.',
    )
    tracked_currency_ids = fields.Many2many(
        'res.currency',
        relation='l10n_by_nbrb_settings_currency_rel',
        string='Отслеживаемые валюты',
        help='Только эти валюты загружаются и обновляются. Пусто — все из ответа API.',
    )
    error_recipient_user_id = fields.Many2one(
        'res.users',
        string='Получатель уведомлений (пользователь)',
        help='Пользователь Odoo, которому приходит письмо о сбоях.',
    )
    error_recipient_email = fields.Char(
        string='Получатель уведомлений (email)',
        help='Альтернатива: явный email-адрес.',
    )
    change_threshold_percent = fields.Float(
        string='Порог уведомления о резком изменении, %',
        default=2.0,
        help='Если курс за день изменился больше этого значения — отправляется уведомление.',
    )
    retry_count = fields.Integer(
        string='Количество попыток при ошибке',
        default=3,
    )
    retry_interval_minutes = fields.Integer(
        string='Интервал между попытками, мин',
        default=5,
    )
    request_timeout_seconds = fields.Integer(
        string='Таймаут запроса, сек',
        default=10,
    )
    last_success_at = fields.Datetime(string='Последняя успешная загрузка', readonly=True)
    next_scheduled_at = fields.Datetime(
        string='Следующее плановое обновление',
        compute='_compute_next_scheduled_at',
    )

    def _compute_next_scheduled_at(self):
        cron = self.env.ref('l10n_by_nbrb.ir_cron_l10n_by_nbrb_update',
                            raise_if_not_found=False)
        for rec in self:
            rec.next_scheduled_at = cron.nextcall if cron and cron.active else False

    @api.constrains('update_hour')
    def _check_hour(self):
        for rec in self:
            if rec.update_hour < 0 or rec.update_hour >= 24:
                raise ValidationError(_('Время автозагрузки должно быть в диапазоне 0–24.'))

    @api.constrains('change_threshold_percent', 'retry_count', 'retry_interval_minutes',
                    'request_timeout_seconds')
    def _check_positive(self):
        for rec in self:
            if rec.change_threshold_percent < 0:
                raise ValidationError(_('Порог изменения не может быть отрицательным.'))
            if rec.retry_count < 1 or rec.retry_count > 10:
                raise ValidationError(_('Количество попыток — от 1 до 10.'))
            if rec.retry_interval_minutes < 0:
                raise ValidationError(_('Интервал между попытками не может быть отрицательным.'))
            if rec.request_timeout_seconds < 1:
                raise ValidationError(_('Таймаут должен быть минимум 1 секунда.'))

    @api.model
    def get_settings(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.sudo().create({})
        return rec

    def action_test_connection(self):
        self.ensure_one()
        service = self.env['l10n.by.nbrb.service']
        result = service.test_connection()
        message = (_('Соединение с api.nbrb.by установлено. Получено валют в ответе: %s.', result)
                   if result is not None
                   else _('Не удалось подключиться к api.nbrb.by. См. журнал загрузок.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if result is not None else 'danger',
                'message': message,
                'sticky': False,
            },
        }

    def action_update_now(self):
        self.ensure_one()
        log = self.env['l10n.by.nbrb.service'].update_rates_for_today(run_type='manual')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.by.nbrb.log',
            'res_id': log.id if log else False,
            'view_mode': 'form',
            'target': 'current',
        }
