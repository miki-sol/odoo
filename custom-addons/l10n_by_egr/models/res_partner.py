from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    egr_full_name = fields.Char(
        string='Полное наименование',
        readonly=True,
    )
    egr_full_name_be = fields.Char(
        string='Полное наименование (бел.)',
        readonly=True,
    )
    egr_firm_name = fields.Char(
        string='Фирменное наименование',
        readonly=True,
    )
    egr_status = fields.Selection(
        selection=[
            ('1', 'Действующая'),
            ('2', 'Исключена из ЕГР'),
            ('3', 'В процессе ликвидации'),
        ],
        string='Статус в ЕГР',
        readonly=True,
    )
    egr_reg_date = fields.Date(
        string='Дата регистрации',
        readonly=True,
    )
    egr_excl_date = fields.Date(
        string='Дата исключения',
        readonly=True,
    )
    egr_entity_type = fields.Char(
        string='Вид субъекта хозяйствования',
        readonly=True,
    )
    egr_authority = fields.Char(
        string='Регистрирующий орган',
        readonly=True,
    )
    egr_oked = fields.Char(
        string='ОКЭД',
        readonly=True,
    )
    egr_sync_date = fields.Datetime(
        string='Последняя синхронизация с ЕГР',
        readonly=True,
    )
