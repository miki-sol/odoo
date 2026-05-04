from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nByPayrollConfig(models.Model):
    _name = 'l10n.by.payroll.config'
    _description = 'Параметры расчёта зарплаты РБ'
    _order = 'date_from desc'
    _rec_name = 'display_name'

    date_from = fields.Date(
        string='Действует с',
        required=True,
        index=True,
        help='С какой даты применяются эти параметры. При расчёте система берёт '
             'запись с максимальной date_from <= последнего дня расчётного месяца.',
    )
    display_name = fields.Char(compute='_compute_display_name', store=True)
    active = fields.Boolean(default=True)

    income_tax_rate = fields.Float(string='Ставка подоходного, %', default=13.0)
    standard_deduction = fields.Float(string='Стандартный вычет, BYN', default=220.0)
    standard_deduction_threshold = fields.Float(
        string='Порог дохода для стандартного вычета, BYN',
        default=1333.0,
    )
    dependent_deduction_one = fields.Float(string='Вычет на 1 иждивенца, BYN', default=65.0)
    dependent_deduction_many = fields.Float(
        string='Вычет на иждивенца (2+), BYN',
        default=130.0,
        help='Применяется к каждому иждивенцу, если их 2 или более.',
    )
    single_parent_deduction = fields.Float(
        string='Вычет одинокому родителю / опекуну, BYN',
        default=130.0,
    )
    disabled_deduction = fields.Float(
        string='Вычет инвалидам I/II гр., чернобыльцам, BYN',
        default=311.0,
    )

    fszn_employee_rate = fields.Float(string='ФСЗН с работника, %', default=1.0)
    fszn_employer_rate = fields.Float(string='ФСЗН с нанимателя, %', default=34.0)
    belgosstrah_default_rate = fields.Float(
        string='Белгосстрах (по умолчанию), %',
        default=0.6,
        help='Применяется, если в карточке сотрудника не указан класс проф. риска со своей ставкой.',
    )

    note = fields.Text(string='Примечание')

    _sql_constraints = [
        ('date_from_unique', 'unique(date_from)',
         'Параметры с такой датой действия уже существуют.'),
    ]

    @api.depends('date_from')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                _('Параметры зарплаты РБ с %s', rec.date_from.strftime('%d.%m.%Y'))
                if rec.date_from else _('Параметры зарплаты РБ')
            )

    @api.constrains('income_tax_rate', 'fszn_employee_rate', 'fszn_employer_rate',
                    'belgosstrah_default_rate')
    def _check_rates(self):
        for rec in self:
            for field_name in ('income_tax_rate', 'fszn_employee_rate',
                               'fszn_employer_rate', 'belgosstrah_default_rate'):
                value = rec[field_name]
                if value < 0 or value > 100:
                    raise ValidationError(_('Ставка должна быть в диапазоне 0–100%.'))

    @api.model
    def get_for_date(self, target_date):
        """Возвращает запись параметров, действующую на указанную дату.

        Если на дату нет записи — возвращает пустой recordset (вызывающий
        код должен сообщить пользователю о необходимости настроить параметры).
        """
        return self.search([('date_from', '<=', target_date)], limit=1)
