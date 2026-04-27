from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    egr_full_name = fields.Char(string='Полное наименование')
    egr_full_name_be = fields.Char(string='Полное наименование (бел.)')
    egr_firm_name = fields.Char(string='Фирменное наименование')
    egr_status = fields.Selection(
        selection=[
            ('1', 'Действующая'),
            ('2', 'Исключена из ЕГР'),
            ('3', 'В процессе ликвидации'),
        ],
        string='Статус в ЕГР',
    )
    egr_reg_date = fields.Date(string='Дата регистрации')
    egr_excl_date = fields.Date(string='Дата исключения')
    egr_entity_type = fields.Char(string='Вид субъекта хозяйствования')
    egr_authority = fields.Char(string='Регистрирующий орган')
    egr_oked = fields.Char(string='ОКЭД')
    egr_sync_date = fields.Datetime(string='Последняя синхронизация с ЕГР')
