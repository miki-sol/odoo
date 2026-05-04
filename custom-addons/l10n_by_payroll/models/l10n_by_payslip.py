from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nByPayslip(models.Model):
    _name = 'l10n.by.payslip'
    _description = 'Расчётный лист РБ'
    _order = 'period_id desc, employee_id'
    _rec_name = 'display_name'

    period_id = fields.Many2one(
        'l10n.by.payroll.period',
        string='Расчётный период',
        required=True,
        ondelete='cascade',
        index=True,
    )
    period_state = fields.Selection(related='period_id.state', store=True)
    employee_id = fields.Many2one('hr.employee', string='Сотрудник', required=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    salary_amount = fields.Float(
        string='Оклад',
        compute='_compute_salary_amount',
        store=True,
        readonly=False,
    )
    bonus_amount = fields.Float(string='Премия')
    other_additions = fields.Float(string='Прочие начисления')
    other_deductions = fields.Float(
        string='Прочие удержания',
        help='Алименты, кредиты, исполнительные листы — без сложной логики приоритетов.',
    )

    gross_amount = fields.Float(string='Валовая зарплата', readonly=True)

    standard_deduction_applied = fields.Float(string='Стандартный вычет', readonly=True)
    dependent_deduction_applied = fields.Float(string='Вычет на иждивенцев', readonly=True)
    benefit_deduction_applied = fields.Float(string='Льготный вычет', readonly=True)
    total_deductions = fields.Float(string='Сумма вычетов', readonly=True)

    taxable_base = fields.Float(string='Облагаемая база', readonly=True)
    income_tax = fields.Float(string='Подоходный налог', readonly=True)
    fszn_employee = fields.Float(string='ФСЗН с работника', readonly=True)
    fszn_employer = fields.Float(string='ФСЗН с нанимателя', readonly=True)
    belgosstrah = fields.Float(string='Белгосстрах', readonly=True)

    net_amount = fields.Float(string='К выплате на руки', readonly=True)
    total_company_cost = fields.Float(string='Полная стоимость для компании', readonly=True)

    is_computed = fields.Boolean(readonly=True)

    _sql_constraints = [
        ('period_employee_unique', 'unique(period_id, employee_id)',
         'Для сотрудника уже существует расчётный лист в этом периоде.'),
    ]

    @api.depends('period_id.display_name', 'employee_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                '%(period)s — %(employee)s',
                period=rec.period_id.display_name or '',
                employee=rec.employee_id.name or '',
            )

    @api.depends('employee_id')
    def _compute_salary_amount(self):
        for rec in self:
            if rec.employee_id and not rec.salary_amount:
                rec.salary_amount = rec.employee_id.l10n_by_salary_amount

    def action_compute(self):
        for rec in self:
            rec._compute_payslip()

    def _compute_payslip(self):
        """Реализует алгоритм из раздела 5 ТЗ."""
        self.ensure_one()
        if self.period_state == 'approved':
            raise UserError(_('Утверждённый расчёт изменять нельзя.'))
        config = self.period_id.config_id
        if not config:
            raise UserError(_('Не заданы параметры расчёта для периода %s.',
                              self.period_id.display_name))
        emp = self.employee_id

        gross = self.salary_amount + self.bonus_amount + self.other_additions

        std_deduction = 0.0
        if emp.l10n_by_employment_type == 'main' and gross <= config.standard_deduction_threshold:
            std_deduction = config.standard_deduction

        dep_deduction = self._compute_dependent_deduction(config, emp)
        benefit_deduction = self._compute_benefit_deduction(config, emp)
        total_deductions = std_deduction + dep_deduction + benefit_deduction

        taxable_base = max(gross - total_deductions, 0.0)
        income_tax = (
            taxable_base * config.income_tax_rate / 100.0
            if emp.l10n_by_apply_income_tax else 0.0
        )

        fszn_employee = gross * config.fszn_employee_rate / 100.0
        fszn_employer = gross * config.fszn_employer_rate / 100.0
        belgosstrah_rate = (
            emp.l10n_by_risk_rate_override
            if emp.l10n_by_risk_rate_override
            else config.belgosstrah_default_rate
        )
        belgosstrah = gross * belgosstrah_rate / 100.0

        net = gross - income_tax - fszn_employee - self.other_deductions

        self.write({
            'gross_amount': gross,
            'standard_deduction_applied': std_deduction,
            'dependent_deduction_applied': dep_deduction,
            'benefit_deduction_applied': benefit_deduction,
            'total_deductions': total_deductions,
            'taxable_base': taxable_base,
            'income_tax': income_tax,
            'fszn_employee': fszn_employee,
            'fszn_employer': fszn_employer,
            'belgosstrah': belgosstrah,
            'net_amount': net,
            'total_company_cost': gross + fszn_employer + belgosstrah,
            'is_computed': True,
        })

    @staticmethod
    def _compute_dependent_deduction(config, emp):
        dependents = emp.l10n_by_dependents_total
        if dependents <= 0:
            return 0.0
        if dependents == 1:
            base = config.dependent_deduction_one
        else:
            base = config.dependent_deduction_many * dependents
        if emp.l10n_by_benefit_category in ('single_parent', 'widow', 'guardian'):
            return base + config.single_parent_deduction
        return base

    @staticmethod
    def _compute_benefit_deduction(config, emp):
        if emp.l10n_by_benefit_category in ('disabled_1', 'disabled_2', 'chernobyl'):
            return config.disabled_deduction
        return 0.0
