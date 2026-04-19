from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    vat = fields.Char(string='УНП')
    company_registry = fields.Char(string='Регистрационный № в ЕГР')
    iban = fields.Char(string='IBAN')

    @api.constrains('vat')
    def _check_vat_unp(self):
        for company in self:
            if company.vat and not (company.vat.isdigit() and len(company.vat) == 9):
                raise ValidationError(_('УНП должен содержать ровно 9 цифр.'))

    @api.constrains('company_registry')
    def _check_company_registry_egr(self):
        for company in self:
            value = company.company_registry
            if value and not (value.isdigit() and len(value) == 9):
                raise ValidationError(_('Регистрационный № в ЕГР должен содержать ровно 9 цифр.'))
