from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bank_name = fields.Char(string='Банк (название)')
    bank_bic = fields.Char(string='BIC банка')
    director_position = fields.Char(string='Должность директора', default='Директор')
    director_name = fields.Char(string='ФИО директора')
    director_basis = fields.Char(string='Основание полномочий', default='Устава')
