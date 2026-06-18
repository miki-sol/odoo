import base64
import io
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .contract_template import (
    CONTRACT_SIDE_SELECTION,
    CONTRACT_TYPE_SELECTION,
    DELIVERY_METHOD_SELECTION,
    PAYMENT_TERMS_SELECTION,
)

_logger = logging.getLogger(__name__)

NOTIFICATION_THRESHOLDS_DAYS = (60, 30, 14, 7, 0)

STATE_SELECTION = [
    ('draft', 'Черновик'),
    ('review', 'На согласовании'),
    ('signed_by_us', 'Подписан с нашей стороны'),
    ('active', 'Действует'),
    ('suspended', 'Приостановлен'),
    ('terminated', 'Расторгнут'),
    ('expired', 'Истёк'),
]

PAYMENT_TERMS_LABELS = dict(PAYMENT_TERMS_SELECTION)
DELIVERY_METHOD_LABELS = dict(DELIVERY_METHOD_SELECTION)
SIDE_LABELS = dict(CONTRACT_SIDE_SELECTION)


def _amount_to_ru_words(amount, currency_name):
    try:
        from num2words import num2words
    except ImportError:
        return ''
    integer = int(amount)
    cents = int(round((amount - integer) * 100))
    words = num2words(integer, lang='ru')
    return f"{words} {currency_name} {cents:02d} коп."


class Contract(models.Model):
    _name = 'contract.contract'
    _description = 'Договор'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_signed desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Номер договора',
        required=True,
        copy=False,
        default=lambda self: _('Новый'),
        tracking=True,
    )
    side = fields.Selection(
        CONTRACT_SIDE_SELECTION, string='Сторона', required=True, default='sale', tracking=True,
    )
    contract_type = fields.Selection(
        CONTRACT_TYPE_SELECTION, string='Тип договора', default='supply', tracking=True,
    )
    template_id = fields.Many2one(
        'contract.template', string='Шаблон',
        domain="[('side','=',side),('active','=',True)]",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Контрагент', required=True,
        domain="[('is_company','=',True)]", tracking=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Компания', required=True,
        default=lambda self: self.env.company,
    )

    date_signed = fields.Date(string='Дата заключения', default=fields.Date.context_today, tracking=True)
    date_start = fields.Date(string='Дата начала действия', default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string='Дата окончания действия', tracking=True)

    amount = fields.Monetary(string='Сумма договора', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Валюта', required=True,
        default=lambda self: self.env.company.currency_id,
    )
    payment_terms = fields.Selection(PAYMENT_TERMS_SELECTION, string='Условия оплаты')
    delivery_method = fields.Selection(DELIVERY_METHOD_SELECTION, string='Способ доставки')
    penalty_rate = fields.Float(string='Штраф за просрочку (% в день)', default=0.1)
    jurisdiction = fields.Char(string='Подсудность', default='Экономический суд г. Минска')

    user_id = fields.Many2one(
        'res.users', string='Ответственный менеджер',
        default=lambda self: self.env.user, tracking=True,
    )
    state = fields.Selection(
        STATE_SELECTION, string='Статус', required=True, default='draft', tracking=True, copy=False,
    )

    notes = fields.Text(string='Заметки')

    auto_renew = fields.Boolean(string='Автопродление')
    auto_renew_period_months = fields.Integer(string='Период автопродления (мес.)', default=12)
    no_renewal_needed = fields.Boolean(string='Продление не требуется')

    last_notified_threshold = fields.Integer(
        string='Последний отправленный порог уведомления (дней)', copy=False,
    )

    generated_document = fields.Binary(string='Сформированный договор', attachment=True, copy=False)
    generated_document_name = fields.Char(string='Имя файла', copy=False)

    sale_order_ids = fields.One2many('sale.order', 'contract_id', string='Заказы продажи')
    purchase_order_ids = fields.One2many('purchase.order', 'contract_id', string='Заказы закупки')
    amendment_ids = fields.One2many('contract.amendment', 'contract_id', string='Допсоглашения')

    invoice_ids = fields.Many2many(
        'account.move', string='Счета', compute='_compute_invoices', store=False,
    )

    orders_count = fields.Integer(compute='_compute_totals')
    orders_amount = fields.Monetary(compute='_compute_totals', string='Заказов всего, сумма')
    orders_executed_amount = fields.Monetary(compute='_compute_totals', string='Исполнено')
    orders_in_progress_amount = fields.Monetary(compute='_compute_totals', string='В работе')
    balance_amount = fields.Monetary(compute='_compute_totals', string='Остаток лимита')
    balance_pct = fields.Float(compute='_compute_totals', string='Остаток лимита, %')

    amount_invoiced = fields.Monetary(compute='_compute_finance', string='Выставлено счетов')
    amount_paid = fields.Monetary(compute='_compute_finance', string='Оплачено')
    amount_debt = fields.Monetary(compute='_compute_finance', string='Дебиторская задолженность')

    days_to_expire = fields.Integer(compute='_compute_days_to_expire', store=False)
    expiry_color = fields.Integer(compute='_compute_days_to_expire', store=False)

    _name_company_uniq = models.Constraint(
        'unique(name, company_id)',
        'Номер договора должен быть уникален в рамках компании.',
    )

    # ---------- defaults / sequence ----------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Новый')) == _('Новый'):
                seq_code = (
                    'contract.contract.sale' if vals.get('side', 'sale') == 'sale'
                    else 'contract.contract.purchase'
                )
                vals['name'] = self.env['ir.sequence'].next_by_code(seq_code) or _('Новый')
        return super().create(vals_list)

    @api.onchange('side')
    def _onchange_side_clear_template(self):
        if self.template_id and self.template_id.side != self.side:
            self.template_id = False

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id and self.template_id.default_payment_terms and not self.payment_terms:
            self.payment_terms = self.template_id.default_payment_terms

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for c in self:
            if c.date_start and c.date_end and c.date_end < c.date_start:
                raise ValidationError(_('Дата окончания не может быть раньше даты начала.'))

    # ---------- computes ----------
    @api.depends('sale_order_ids.amount_total', 'sale_order_ids.state',
                 'purchase_order_ids.amount_total', 'purchase_order_ids.state',
                 'amount')
    def _compute_totals(self):
        for c in self:
            if c.side == 'sale':
                orders = c.sale_order_ids
                done_states = ('sale', 'done')
                executed = orders.filtered(lambda o: o.state in done_states and o.invoice_status == 'invoiced')
                in_progress = orders.filtered(lambda o: o.state in done_states and o.invoice_status != 'invoiced')
            else:
                orders = c.purchase_order_ids
                executed = orders.filtered(lambda o: o.state == 'done')
                in_progress = orders.filtered(lambda o: o.state == 'purchase')
            c.orders_count = len(orders)
            c.orders_amount = sum(orders.mapped('amount_total'))
            c.orders_executed_amount = sum(executed.mapped('amount_total'))
            c.orders_in_progress_amount = sum(in_progress.mapped('amount_total'))
            c.balance_amount = (c.amount or 0.0) - c.orders_amount
            c.balance_pct = (c.balance_amount / c.amount * 100.0) if c.amount else 0.0

    @api.depends('sale_order_ids.invoice_ids', 'purchase_order_ids.invoice_ids')
    def _compute_invoices(self):
        for c in self:
            if c.side == 'sale':
                c.invoice_ids = c.sale_order_ids.mapped('invoice_ids')
            else:
                c.invoice_ids = c.purchase_order_ids.mapped('invoice_ids')

    @api.depends('sale_order_ids.invoice_ids.amount_total',
                 'sale_order_ids.invoice_ids.amount_residual',
                 'purchase_order_ids.invoice_ids.amount_total',
                 'purchase_order_ids.invoice_ids.amount_residual')
    def _compute_finance(self):
        for c in self:
            invoices = c.invoice_ids.filtered(lambda m: m.state == 'posted')
            c.amount_invoiced = sum(invoices.mapped('amount_total'))
            c.amount_paid = c.amount_invoiced - sum(invoices.mapped('amount_residual'))
            c.amount_debt = c.amount_invoiced - c.amount_paid

    @api.depends('date_end', 'state')
    def _compute_days_to_expire(self):
        today = fields.Date.context_today(self)
        for c in self:
            if c.state != 'active' or not c.date_end:
                c.days_to_expire = 0
                c.expiry_color = 0
                continue
            delta = (c.date_end - today).days
            c.days_to_expire = delta
            if delta <= 7:
                c.expiry_color = 1  # red
            elif delta <= 14:
                c.expiry_color = 2  # orange
            elif delta <= 30:
                c.expiry_color = 3  # yellow
            else:
                c.expiry_color = 0

    # ---------- workflow ----------
    def action_send_for_review(self):
        for c in self:
            if c.state != 'draft':
                raise UserError(_('Отправить на согласование можно только из черновика.'))
            c.state = 'review'

    def action_back_to_draft(self):
        for c in self:
            if c.state not in ('review', 'signed_by_us'):
                raise UserError(_('Вернуть в черновик можно только со статусов «На согласовании»/«Подписан с нашей стороны».'))
            c.state = 'draft'

    def action_sign_by_us(self):
        for c in self:
            if c.state != 'review':
                raise UserError(_('Подписать можно только согласованный договор.'))
            c.state = 'signed_by_us'

    def action_activate(self):
        for c in self:
            if c.state not in ('signed_by_us', 'suspended'):
                raise UserError(_('Активировать можно только подписанный или приостановленный договор.'))
            c.state = 'active'

    def action_suspend(self):
        for c in self:
            if c.state != 'active':
                raise UserError(_('Приостановить можно только действующий договор.'))
            c.state = 'suspended'

    def action_terminate(self):
        for c in self:
            if c.state in ('terminated', 'expired'):
                raise UserError(_('Договор уже расторгнут или истёк.'))
            c.state = 'terminated'

    # ---------- document generation ----------
    def _check_partner_legal_data(self):
        self.ensure_one()
        p = self.partner_id
        missing = []
        if not p.vat:
            missing.append('УНП')
        if not p.iban:
            missing.append('расчётный счёт')
        if not p.partner_bank_name:
            missing.append('наименование банка')
        if not p.partner_bank_bic:
            missing.append('BIC банка')
        if missing:
            raise UserError(_(
                'Не заполнены реквизиты контрагента: %s. Заполните их в карточке контакта перед формированием договора.'
            ) % ', '.join(missing))

    def _get_template_context(self):
        self.ensure_one()
        company = self.company_id
        partner = self.partner_id
        currency_name = self.currency_id.name or 'BYN'
        return {
            # our company
            'our_company_name': company.partner_id.name or '',
            'our_company_short': company.name or '',
            'our_unp': company.vat or '',
            'our_address': company.partner_id._display_address(without_company=True) or '',
            'our_iban': company.iban or '',
            'our_bank': company.bank_name or '',
            'our_bank_bic': company.bank_bic or '',
            'our_director_position': company.director_position or 'Директор',
            'our_director_name': company.director_name or '',
            'our_director_basis': company.director_basis or 'Устава',
            # partner
            'partner_name': partner.name or '',
            'partner_short': partner.name or '',
            'partner_unp': partner.vat or '',
            'partner_address': partner._display_address(without_company=True) or '',
            'partner_iban': partner.iban or '',
            'partner_bank': partner.partner_bank_name or '',
            'partner_bank_bic': partner.partner_bank_bic or '',
            'partner_signatory': partner.signatory_name or '',
            'partner_signatory_position': partner.signatory_position or 'Директор',
            'partner_basis': partner.signatory_basis or 'Устава',
            # contract
            'contract_number': self.name,
            'contract_date': self.date_signed and self.date_signed.strftime('%d.%m.%Y') or '',
            'contract_city': company.city or 'Минск',
            'date_start': self.date_start and self.date_start.strftime('%d.%m.%Y') or '',
            'date_end': self.date_end and self.date_end.strftime('%d.%m.%Y') or 'не ограничен',
            'contract_amount': '%.2f' % (self.amount or 0.0),
            'contract_amount_words': _amount_to_ru_words(self.amount or 0.0, currency_name),
            'currency': currency_name,
            'payment_terms': PAYMENT_TERMS_LABELS.get(self.payment_terms, ''),
            'delivery_terms': DELIVERY_METHOD_LABELS.get(self.delivery_method, ''),
            'penalty_rate': '%.2f' % (self.penalty_rate or 0.0),
            'jurisdiction': self.jurisdiction or '',
        }

    def action_generate_document(self):
        self.ensure_one()
        if not self.template_id:
            raise UserError(_('Выберите шаблон договора.'))
        if not self.template_id.template_file:
            raise UserError(_('У выбранного шаблона не загружен DOCX-файл.'))
        self._check_partner_legal_data()

        try:
            from docxtpl import DocxTemplate
        except ImportError as exc:
            raise UserError(_(
                'Библиотека docxtpl не установлена. Добавьте её в requirements.txt и пересоберите контейнер.'
            )) from exc

        tpl_bytes = base64.b64decode(self.template_id.template_file)
        doc = DocxTemplate(io.BytesIO(tpl_bytes))
        try:
            doc.render(self._get_template_context())
        except Exception as exc:
            _logger.exception('Ошибка рендеринга шаблона договора %s', self.name)
            raise UserError(_('Не удалось обработать шаблон: %s') % exc) from exc

        out = io.BytesIO()
        doc.save(out)
        filename = f"{self.name.replace('/', '-')}.docx"
        self.write({
            'generated_document': base64.b64encode(out.getvalue()),
            'generated_document_name': filename,
        })
        self.message_post(body=_('Документ договора сформирован: %s') % filename)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=contract.contract&id={self.id}'
                   f'&field=generated_document&filename_field=generated_document_name&download=true',
            'target': 'self',
        }

    # ---------- validation when attaching orders ----------
    def _check_can_have_orders(self, raise_on_error=True):
        self.ensure_one()
        if self.state in ('draft', 'review'):
            if raise_on_error:
                raise UserError(_('Договор %s ещё не действует (статус: %s). Нельзя оформлять заказы.')
                                % (self.name, dict(STATE_SELECTION).get(self.state)))
            return False
        if self.state in ('suspended', 'terminated', 'expired'):
            if raise_on_error:
                raise UserError(_('Договор %s в статусе «%s» — новые заказы запрещены.')
                                % (self.name, dict(STATE_SELECTION).get(self.state)))
            return False
        return True

    def _check_amount_limit(self, new_order_amount, exclude_order=None):
        """Return remaining limit; raise UserError if would be exceeded for framework contracts."""
        self.ensure_one()
        if self.contract_type != 'framework' or not self.amount:
            return None
        existing = self.orders_amount
        if exclude_order is not None and exclude_order:
            existing -= exclude_order.amount_total
        remaining = self.amount - existing
        if new_order_amount > remaining:
            raise UserError(_(
                'Сумма заказа %(new).2f %(cur)s превышает остаток лимита договора %(name)s '
                '(остаток %(rem).2f %(cur)s).\n\nВарианты: уменьшить сумму заказа, оформить '
                'допсоглашение об увеличении лимита, либо оформить новый договор.'
            ) % {
                'new': new_order_amount,
                'cur': self.currency_id.name,
                'name': self.name,
                'rem': remaining,
            })
        return remaining

    # ---------- expiry cron ----------
    @api.model
    def _cron_check_expiry(self):
        today = fields.Date.context_today(self)
        active = self.search([('state', '=', 'active'), ('date_end', '!=', False)])
        for contract in active:
            days = (contract.date_end - today).days
            if days < 0:
                contract._handle_expired(today)
                continue
            if days == 0:
                contract._notify_expiry(0)
                if contract.auto_renew and not contract.no_renewal_needed:
                    contract._auto_renew_apply()
                else:
                    contract._handle_expired(today)
                continue
            for threshold in NOTIFICATION_THRESHOLDS_DAYS:
                if threshold == 0:
                    continue
                if days <= threshold and contract.last_notified_threshold != threshold \
                        and (contract.last_notified_threshold == 0 or threshold < contract.last_notified_threshold):
                    contract._notify_expiry(threshold)
                    contract.last_notified_threshold = threshold
                    break

    def _notify_expiry(self, threshold):
        self.ensure_one()
        if self.no_renewal_needed:
            return
        body = _('Договор %(name)s с %(partner)s истекает через %(days)s дн. (%(date)s). Запланируйте продление.') % {
            'name': self.name,
            'partner': self.partner_id.display_name,
            'days': threshold,
            'date': self.date_end and self.date_end.strftime('%d.%m.%Y') or '',
        }
        recipients = self._get_notification_recipients(threshold)
        partner_ids = [u.partner_id.id for u in recipients if u.partner_id]
        self.message_post(
            body=body,
            partner_ids=partner_ids,
            subtype_xmlid='mail.mt_comment',
        )
        if threshold <= 30:
            template = self.env.ref('l10n_by_contracts.mail_template_contract_expiry', raise_if_not_found=False)
            if template:
                emails = ','.join(filter(None, recipients.mapped('email')))
                if emails:
                    template.with_context(custom_emails=emails, threshold=threshold).send_mail(self.id, force_send=False)

    def _get_notification_recipients(self, threshold):
        users = self.env['res.users']
        if self.user_id:
            users |= self.user_id
        if threshold <= 14:
            director_group = self.env.ref('base.group_erp_manager', raise_if_not_found=False)
            if director_group:
                users |= director_group.user_ids
        if threshold <= 7:
            acc_group = self.env.ref('account.group_account_invoice', raise_if_not_found=False)
            if acc_group:
                users |= acc_group.user_ids
        return users

    def _auto_renew_apply(self):
        self.ensure_one()
        from dateutil.relativedelta import relativedelta
        old_end = self.date_end
        new_end = old_end + relativedelta(months=self.auto_renew_period_months or 12)
        self.env['contract.amendment'].create({
            'contract_id': self.id,
            'subject': _('О пролонгации'),
            'date_signed': fields.Date.context_today(self),
            'note': _('Автопродление с %(old)s по %(new)s.') % {
                'old': old_end.strftime('%d.%m.%Y'), 'new': new_end.strftime('%d.%m.%Y'),
            },
        })
        self.write({'date_end': new_end, 'last_notified_threshold': 0})
        self.message_post(body=_('Договор автоматически продлён до %s.') % new_end.strftime('%d.%m.%Y'))

    def _handle_expired(self, today):
        self.ensure_one()
        if self.state == 'active':
            self.state = 'expired'
            self.message_post(body=_('Договор переведён в статус «Истёк» (срок: %s).')
                              % (self.date_end and self.date_end.strftime('%d.%m.%Y') or ''))

    # ---------- smart actions ----------
    def action_open_orders(self):
        self.ensure_one()
        if self.side == 'sale':
            return {
                'type': 'ir.actions.act_window',
                'name': _('Заказы продажи'),
                'res_model': 'sale.order',
                'view_mode': 'list,form',
                'domain': [('contract_id', '=', self.id)],
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Заказы закупки'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
        }

    def action_open_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Счета по договору'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }
