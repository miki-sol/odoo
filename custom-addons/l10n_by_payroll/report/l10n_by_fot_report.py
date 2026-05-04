from odoo import fields, models, tools


class L10nByFotReport(models.Model):
    _name = 'l10n.by.fot.report'
    _description = 'Сводный отчёт ФОТ за период'
    _auto = False
    _order = 'date_to desc'

    period_id = fields.Many2one('l10n.by.payroll.period', string='Период', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Сотрудник', readonly=True)
    department_id = fields.Many2one('hr.department', string='Подразделение', readonly=True)
    date_from = fields.Date(readonly=True)
    date_to = fields.Date(readonly=True)
    year = fields.Integer(readonly=True)
    month = fields.Char(readonly=True)
    state = fields.Selection(
        [('draft', 'Черновик'), ('computed', 'Рассчитан'), ('approved', 'Утверждён')],
        readonly=True,
    )

    gross_amount = fields.Float(readonly=True, string='Начислено')
    income_tax = fields.Float(readonly=True, string='Подоходный налог')
    fszn_employee = fields.Float(readonly=True, string='ФСЗН работник')
    fszn_employer = fields.Float(readonly=True, string='ФСЗН наниматель')
    belgosstrah = fields.Float(readonly=True, string='Белгосстрах')
    net_amount = fields.Float(readonly=True, string='К выплате')
    total_company_cost = fields.Float(readonly=True, string='Полная стоимость')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ps.id              AS id,
                    ps.period_id       AS period_id,
                    ps.employee_id     AS employee_id,
                    e.department_id    AS department_id,
                    p.date_from        AS date_from,
                    p.date_to          AS date_to,
                    p.year             AS year,
                    p.month            AS month,
                    p.state            AS state,
                    ps.gross_amount    AS gross_amount,
                    ps.income_tax      AS income_tax,
                    ps.fszn_employee   AS fszn_employee,
                    ps.fszn_employer   AS fszn_employer,
                    ps.belgosstrah     AS belgosstrah,
                    ps.net_amount      AS net_amount,
                    ps.total_company_cost AS total_company_cost
                FROM l10n_by_payslip ps
                JOIN l10n_by_payroll_period p ON p.id = ps.period_id
                JOIN hr_employee e ON e.id = ps.employee_id
            )
        """)
