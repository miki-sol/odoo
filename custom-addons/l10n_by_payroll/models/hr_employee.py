from odoo import api, fields, models


EMPLOYMENT_TYPES = [
    ('main', 'Основное место работы'),
    ('external', 'Совместительство (внешнее)'),
    ('internal', 'Внутренний совместитель'),
]

BENEFIT_CATEGORIES = [
    ('none', 'Нет'),
    ('single_parent', 'Одинокий родитель'),
    ('widow', 'Вдова / вдовец'),
    ('guardian', 'Опекун / попечитель'),
    ('disabled_1', 'Инвалид I группы'),
    ('disabled_2', 'Инвалид II группы'),
    ('chernobyl', 'Чернобылец и приравненные'),
]

RISK_CLASSES = [(str(i), str(i)) for i in range(1, 23)]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_by_salary_amount = fields.Float(
        string='Оклад, BYN/мес',
        groups='hr.group_hr_user',
        help='Базовая месячная сумма начисления при полностью отработанном месяце.',
    )
    l10n_by_employment_type = fields.Selection(
        EMPLOYMENT_TYPES,
        string='Тип занятости',
        default='main',
        groups='hr.group_hr_user',
        help='Совместителям стандартный налоговый вычет НЕ применяется.',
    )
    l10n_by_children_under_18 = fields.Integer(
        string='Детей до 18 лет',
        groups='hr.group_hr_user',
    )
    l10n_by_children_students = fields.Integer(
        string='Детей-студентов 18–24 (дневная форма)',
        groups='hr.group_hr_user',
    )
    l10n_by_dependents_total = fields.Integer(
        string='Иждивенцев всего',
        compute='_compute_dependents_total',
        store=True,
    )
    l10n_by_benefit_category = fields.Selection(
        BENEFIT_CATEGORIES,
        string='Льготная категория',
        default='none',
        groups='hr.group_hr_user',
    )
    l10n_by_risk_class = fields.Selection(
        RISK_CLASSES,
        string='Класс проф. риска (Белгосстрах)',
        default='1',
        groups='hr.group_hr_user',
    )
    l10n_by_risk_rate_override = fields.Float(
        string='Ставка Белгосстрах, %',
        groups='hr.group_hr_user',
        help='Если указано — переопределяет ставку из параметров расчёта.',
    )
    l10n_by_apply_income_tax = fields.Boolean(
        string='Применять подоходный налог',
        default=True,
        groups='hr.group_hr_user',
        help='Снимается для нерезидентов и особых случаев.',
    )
    l10n_by_iban = fields.Char(
        string='Платёжная карта (IBAN)',
        groups='hr.group_hr_user',
    )
    l10n_by_payslip_email = fields.Char(
        string='Email для расчётного листа',
        groups='hr.group_hr_user',
    )

    @api.depends('l10n_by_children_under_18', 'l10n_by_children_students')
    def _compute_dependents_total(self):
        for emp in self:
            emp.l10n_by_dependents_total = (
                emp.l10n_by_children_under_18 + emp.l10n_by_children_students
            )
