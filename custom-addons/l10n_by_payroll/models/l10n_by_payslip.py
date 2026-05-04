import calendar

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nByPayslip(models.Model):
    _name = 'l10n.by.payslip'
    _description = 'Расчётный лист РБ'
    _inherit = ['mail.thread']
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
        string='Оклад (с учётом дней)',
        compute='_compute_salary_amount',
        store=True,
        readonly=False,
    )
    full_salary = fields.Float(string='Оклад полный', help='Берётся из карточки сотрудника.')
    worked_days = fields.Float(
        string='Отработано дней',
        help='Если меньше календарных дней месяца — оклад уменьшается пропорционально.',
    )
    total_days = fields.Float(
        string='Календарных дней',
        compute='_compute_total_days',
        store=True,
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
    move_id = fields.Many2one('account.move', string='Бухгалтерская проводка', readonly=True)

    _period_employee_unique = models.Constraint(
        'unique(period_id, employee_id)',
        'Для сотрудника уже существует расчётный лист в этом периоде.',
    )

    @api.depends('period_id.display_name', 'employee_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                '%(period)s — %(employee)s',
                period=rec.period_id.display_name or '',
                employee=rec.employee_id.name or '',
            )

    @api.depends('period_id.year', 'period_id.month')
    def _compute_total_days(self):
        for rec in self:
            if rec.period_id.year and rec.period_id.month:
                rec.total_days = calendar.monthrange(rec.period_id.year, int(rec.period_id.month))[1]
            else:
                rec.total_days = 0.0

    @api.depends('employee_id', 'full_salary', 'worked_days', 'total_days')
    def _compute_salary_amount(self):
        for rec in self:
            if rec.employee_id and not rec.full_salary:
                rec.full_salary = rec.employee_id.l10n_by_salary_amount
            if rec.total_days and rec.worked_days and rec.worked_days < rec.total_days:
                rec.salary_amount = rec.full_salary * rec.worked_days / rec.total_days
            else:
                rec.salary_amount = rec.full_salary

    @api.onchange('employee_id', 'period_id')
    def _onchange_defaults(self):
        for rec in self:
            if rec.employee_id and not rec.full_salary:
                rec.full_salary = rec.employee_id.l10n_by_salary_amount
            if rec.total_days and not rec.worked_days:
                rec.worked_days = rec.total_days

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

        if not self.worked_days:
            self.worked_days = self.total_days
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

    def _build_journal_entry_lines(self):
        """Возвращает список line_ids для одной проводки на этот payslip.

        Дебет ФОТ (расход) = валовая + ФСЗН наниматель + Белгосстрах.
        Кредит = к выплате (зарплата к расчёту), удержанный НДФЛ, ФСЗН
        работника + наниматель, Белгосстрах, прочие удержания.
        """
        self.ensure_one()
        config = self.period_id.config_id
        partner_id = self.employee_id.work_contact_id.id or False

        def line(account, debit=0.0, credit=0.0, label=None):
            return (0, 0, {
                'name': label or self.display_name,
                'account_id': account.id,
                'debit': debit,
                'credit': credit,
                'partner_id': partner_id,
            })

        lines = []
        # Расход компании
        if config.account_salary_expense_id and self.gross_amount:
            lines.append(line(config.account_salary_expense_id,
                              debit=self.gross_amount, label=_('Начисление ЗП')))
        if config.account_fszn_expense_id and self.fszn_employer:
            lines.append(line(config.account_fszn_expense_id,
                              debit=self.fszn_employer, label=_('ФСЗН наниматель')))
        if config.account_belgosstrah_expense_id and self.belgosstrah:
            lines.append(line(config.account_belgosstrah_expense_id,
                              debit=self.belgosstrah, label=_('Белгосстрах')))

        # Обязательства
        if config.account_salary_payable_id:
            lines.append(line(config.account_salary_payable_id,
                              credit=self.net_amount, label=_('К выплате')))
        if config.account_income_tax_payable_id and self.income_tax:
            lines.append(line(config.account_income_tax_payable_id,
                              credit=self.income_tax, label=_('Подоходный налог')))
        if config.account_fszn_payable_id:
            fszn_total = self.fszn_employee + self.fszn_employer
            if fszn_total:
                lines.append(line(config.account_fszn_payable_id,
                                  credit=fszn_total, label=_('ФСЗН')))
        if config.account_belgosstrah_payable_id and self.belgosstrah:
            lines.append(line(config.account_belgosstrah_payable_id,
                              credit=self.belgosstrah, label=_('Белгосстрах к уплате')))
        if self.other_deductions and config.account_other_deductions_id:
            lines.append(line(config.account_other_deductions_id,
                              credit=self.other_deductions,
                              label=_('Прочие удержания')))
        return lines

    def _create_journal_entry(self):
        """Создаёт account.move для одного payslip. Возвращает запись или False."""
        self.ensure_one()
        if self.move_id:
            return self.move_id
        period = self.period_id
        if not period.journal_id:
            return False
        lines = self._build_journal_entry_lines()
        if not lines:
            return False
        debit = sum(l[2]['debit'] for l in lines)
        credit = sum(l[2]['credit'] for l in lines)
        if abs(debit - credit) > 0.005:
            raise UserError(_(
                'Проводка по %s не сбалансирована: дебет %.2f, кредит %.2f. '
                'Проверьте настройки счетов в параметрах зарплаты.',
                self.display_name, debit, credit,
            ))
        move = self.env['account.move'].create({
            'journal_id': period.journal_id.id,
            'date': period.date_to,
            'ref': self.display_name,
            'line_ids': lines,
        })
        self.move_id = move
        return move

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }

    def action_send_payslip_email(self):
        """Отправляет PDF расчётного листа на email сотрудника.

        Использует l10n_by_payslip_email, при отсутствии — work_email.
        """
        template = self.env.ref('l10n_by_payroll.mail_template_payslip',
                                raise_if_not_found=False)
        if not template:
            raise UserError(_('Не найден шаблон письма для расчётного листа.'))
        sent = self.env['l10n.by.payslip']
        for rec in self:
            target = rec.employee_id.l10n_by_payslip_email or rec.employee_id.work_email
            if not target:
                continue
            template.with_context(
                payslip_email_to=target,
            ).send_mail(rec.id, force_send=True)
            sent |= rec
        return sent
