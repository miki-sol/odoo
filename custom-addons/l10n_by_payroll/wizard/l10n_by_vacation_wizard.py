from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nByVacationWizard(models.TransientModel):
    _name = 'l10n.by.vacation.wizard'
    _description = 'Расчёт отпускных'

    employee_id = fields.Many2one('hr.employee', string='Сотрудник', required=True)
    days = fields.Integer(string='Дней отпуска', required=True, default=14)
    reference_date = fields.Date(
        string='Дата начала отпуска',
        required=True,
        default=fields.Date.today,
    )

    average_daily = fields.Float(string='Среднедневной заработок', readonly=True)
    total_amount = fields.Float(string='Сумма отпускных', readonly=True)
    months_used = fields.Integer(string='Учтено месяцев', readonly=True)
    days_worked = fields.Float(string='Учтено дней', readonly=True)
    note = fields.Text(readonly=True)

    @api.onchange('employee_id', 'reference_date', 'days')
    def _onchange_compute(self):
        if not (self.employee_id and self.reference_date and self.days):
            return
        self._do_compute()

    def _do_compute(self):
        """Среднедневной = сумма выплат за 12 предшествующих месяцев / отработанные дни."""
        Payslip = self.env['l10n.by.payslip']
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
            self.total_amount = self.average_daily * self.days
            self.note = _('Средний рассчитан по %s утверждённым месяцам.', len(slips))
        else:
            # Если нет истории — берём оклад / календарные дни месяца как fallback.
            self.average_daily = self.employee_id.l10n_by_salary_amount / 21.0
            self.total_amount = self.average_daily * self.days
            self.note = _(
                'Нет утверждённых расчётов за 12 месяцев. Использован приблизительный '
                'расчёт от текущего оклада (%s / 21 раб. день).',
                self.employee_id.l10n_by_salary_amount,
            )
        self.months_used = len(slips)
        self.days_worked = total_days

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
