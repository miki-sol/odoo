import calendar
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


MONTHS = [
    ('1', 'Январь'), ('2', 'Февраль'), ('3', 'Март'), ('4', 'Апрель'),
    ('5', 'Май'), ('6', 'Июнь'), ('7', 'Июль'), ('8', 'Август'),
    ('9', 'Сентябрь'), ('10', 'Октябрь'), ('11', 'Ноябрь'), ('12', 'Декабрь'),
]


class L10nByPayrollPeriod(models.Model):
    _name = 'l10n.by.payroll.period'
    _description = 'Расчётный период зарплаты РБ'
    _inherit = ['mail.thread']
    _order = 'year desc, month desc'
    _rec_name = 'display_name'

    year = fields.Integer(
        string='Год', required=True,
        default=lambda self: fields.Date.today().year,
        tracking=True,
    )
    month = fields.Selection(
        MONTHS,
        string='Месяц',
        required=True,
        default=lambda self: str(fields.Date.today().month),
        tracking=True,
    )
    display_name = fields.Char(compute='_compute_display_name', store=True)
    date_from = fields.Date(compute='_compute_dates', store=True)
    date_to = fields.Date(compute='_compute_dates', store=True)
    config_id = fields.Many2one(
        'l10n.by.payroll.config',
        string='Параметры расчёта',
        compute='_compute_config_id',
        store=True,
        readonly=False,
        help='Автоматически выбирается по дате окончания периода. Можно переопределить вручную.',
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Журнал проводок',
        domain=[('type', '=', 'general')],
        help='Журнал, в который записываются проводки начисления ЗП при утверждении.',
    )
    state = fields.Selection(
        [('draft', 'Черновик'), ('computed', 'Рассчитан'), ('approved', 'Утверждён')],
        default='draft',
        required=True,
        tracking=True,
    )
    payslip_ids = fields.One2many(
        'l10n.by.payslip',
        'period_id',
        string='Расчётные листы',
    )
    payslip_count = fields.Integer(compute='_compute_totals')
    move_count = fields.Integer(compute='_compute_move_count')
    total_gross = fields.Float(compute='_compute_totals', string='Итого начислено')
    total_net = fields.Float(compute='_compute_totals', string='Итого к выплате')
    total_company_cost = fields.Float(compute='_compute_totals', string='Итого с расходами компании')

    _year_month_unique = models.Constraint(
        'unique(year, month)',
        'Расчётный период за этот месяц уже существует.',
    )

    @api.depends('year', 'month')
    def _compute_display_name(self):
        month_label = dict(MONTHS)
        for rec in self:
            if rec.year and rec.month:
                rec.display_name = _('Зарплата %s %s', month_label.get(rec.month, ''), rec.year)
            else:
                rec.display_name = _('Расчётный период')

    @api.depends('year', 'month')
    def _compute_dates(self):
        for rec in self:
            if rec.year and rec.month:
                month = int(rec.month)
                rec.date_from = date(rec.year, month, 1)
                rec.date_to = date(rec.year, month, calendar.monthrange(rec.year, month)[1])
            else:
                rec.date_from = False
                rec.date_to = False

    @api.depends('date_to')
    def _compute_config_id(self):
        Config = self.env['l10n.by.payroll.config']
        for rec in self:
            rec.config_id = Config.get_for_date(rec.date_to) if rec.date_to else False

    @api.depends('payslip_ids.gross_amount', 'payslip_ids.net_amount',
                 'payslip_ids.total_company_cost')
    def _compute_totals(self):
        for rec in self:
            rec.payslip_count = len(rec.payslip_ids)
            rec.total_gross = sum(rec.payslip_ids.mapped('gross_amount'))
            rec.total_net = sum(rec.payslip_ids.mapped('net_amount'))
            rec.total_company_cost = sum(rec.payslip_ids.mapped('total_company_cost'))

    @api.depends('payslip_ids.move_id')
    def _compute_move_count(self):
        for rec in self:
            rec.move_count = len(rec.payslip_ids.mapped('move_id'))

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year < 2000 or rec.year > 2100:
                raise ValidationError(_('Год должен быть в диапазоне 2000–2100.'))

    def action_populate_employees(self):
        """Создаёт расчётные листы для всех сотрудников с заполненным окладом."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Добавлять сотрудников можно только в черновом периоде.'))
        existing_emp_ids = self.payslip_ids.mapped('employee_id').ids
        employees = self.env['hr.employee'].search([
            ('id', 'not in', existing_emp_ids),
            ('l10n_by_salary_amount', '>', 0),
        ])
        if not employees:
            raise UserError(_('Нет сотрудников с заполненным окладом, которые ещё не добавлены.'))
        total_days = calendar.monthrange(self.year, int(self.month))[1]
        self.env['l10n.by.payslip'].create([
            {
                'period_id': self.id,
                'employee_id': emp.id,
                'full_salary': emp.l10n_by_salary_amount,
                'worked_days': total_days,
            }
            for emp in employees
        ])

    def action_compute_all(self):
        self.ensure_one()
        if not self.config_id:
            raise UserError(_(
                'Не найдены параметры расчёта на дату %s. Создайте запись в '
                '«Параметры зарплаты РБ».',
                self.date_to,
            ))
        if not self.payslip_ids:
            self.action_populate_employees()
        self.payslip_ids.action_compute()
        self.state = 'computed'

    def action_approve(self):
        for rec in self:
            if rec.state != 'computed':
                raise UserError(_('Утвердить можно только рассчитанный период.'))
            if not rec.payslip_ids:
                raise UserError(_('Нет расчётных листов для утверждения.'))
            rec.state = 'approved'
            if rec.journal_id:
                for slip in rec.payslip_ids:
                    slip._create_journal_entry()
            rec.payslip_ids.action_send_payslip_email()

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_('Утверждённый период вернуть в черновик нельзя.'))
            rec.state = 'draft'

    def action_print_payslips(self):
        self.ensure_one()
        return self.env.ref('l10n_by_payroll.action_report_payslip').report_action(
            self.payslip_ids
        )

    def action_view_moves(self):
        self.ensure_one()
        moves = self.payslip_ids.mapped('move_id')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
            'name': _('Проводки %s', self.display_name),
        }

    def action_open_bank_export(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.by.bank.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_period_id': self.id},
        }

    def action_open_pu3_export(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.by.pu3.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_year': self.year,
                'default_quarter': str((int(self.month) - 1) // 3 + 1),
            },
        }
