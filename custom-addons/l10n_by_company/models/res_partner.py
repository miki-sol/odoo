from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    iban = fields.Char(string='IBAN')

    def _get_company_registry_labels(self):
        labels = super()._get_company_registry_labels()
        labels['BY'] = 'Регистрационный № в ЕГР'
        return labels

    @api.constrains('vat', 'is_company')
    def _check_vat_unp(self):
        for partner in self:
            if partner.is_company and partner.vat:
                if not (partner.vat.isdigit() and len(partner.vat) == 9):
                    raise ValidationError(_('УНП должен содержать ровно 9 цифр.'))

    @api.constrains('company_registry', 'is_company')
    def _check_company_registry_egr(self):
        for partner in self:
            if partner.is_company and partner.company_registry:
                value = partner.company_registry
                if not (value.isdigit() and len(value) == 9):
                    raise ValidationError(
                        _('Регистрационный № в ЕГР должен содержать ровно 9 цифр.')
                    )
