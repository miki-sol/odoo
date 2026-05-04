from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nBySickLeaveWizard(models.TransientModel):
    _name = 'l10n.by.sickleave.wizard'
    _description = 'Расчёт больничных'

    employee_id = fields.Many2one('hr.employee', string='Сотрудник', required=True)
    days = fields.Integer(string='Дней больничного', required=True, default=5)
    reference_date = fields.Date(
        string='Дата начала больничного',
        required=True,
        default=fields.Date.today,
    )

    average_daily = fields.Float(string='Среднедневной заработок', readonly=True)
    days_partial = fields.Integer(string='Дней по 80%', readonly=True)
    days_full = fields.Integer(string='Дней по 100%', readonly=True)
    total_amount = fields.Float(string='Сумма больничного', readonly=True)
    note = fields.Text(readonly=True)

    @api.onchange('employee_id', 'reference_date', 'days')
    def _onchange_compute(self):
        if not (self.employee_id and self.reference_date and self.days):
            return
        self._do_compute()

    def _do_compute(self):
        """Первые N дней — частичная ставка, далее — 100%. Параметры из config."""
        Payslip = self.env['l10n.by.payslip']
        Config = self.env['l10n.by.payroll.config']
        config = Config.get_for_date(self.reference_date)
        if not config:
            raise UserError(_('Не найдены параметры расчёта на %s.', self.reference_date))

        end = self.reference_date - relativedelta(days=1)
        start = (end + relativedelta(days=1)) - relativedelta(months=12)
        slips = Payslip.search([
            ('employee_id', '=', self.employee_id.id),
            ('period_state', '=', 'approved'),
            ('period_id.date_to', '>=', start),
            ('period_id.date_to', '<=', end),
        ])
        total_pay = sum(slips.mapped('gross_amount'))
        total_days = sum(slips.mapped('worked_days'))
        if total_days:
            self.average_daily = total_pay / total_days
            self.note = _('Средний рассчитан по %s утверждённым месяцам.', len(slips))
        else:
            self.average_daily = self.employee_id.l10n_by_salary_amount / 21.0
            self.note = _(
                'Нет утверждённых расчётов за 12 месяцев. Использован приблизительный '
                'расчёт от текущего оклада.',
            )
        partial_limit = config.sick_leave_partial_days
        partial_rate = config.sick_leave_partial_rate / 100.0
        self.days_partial = min(self.days, partial_limit)
        self.days_full = max(self.days - partial_limit, 0)
        self.total_amount = (
            self.average_daily * self.days_partial * partial_rate
            + self.average_daily * self.days_full
        )

    def action_compute(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_('Укажите сотрудника.'))
        self._do_compute()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
