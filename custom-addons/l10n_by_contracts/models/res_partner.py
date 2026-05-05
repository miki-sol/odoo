from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    partner_bank_name = fields.Char(string='Банк контрагента')
    partner_bank_bic = fields.Char(string='BIC банка контрагента')
    signatory_name = fields.Char(string='ФИО подписанта')
    signatory_position = fields.Char(string='Должность подписанта', default='Директор')
    signatory_basis = fields.Char(string='Основание полномочий подписанта', default='Устава')

    contract_ids = fields.One2many('contract.contract', 'partner_id', string='Договоры')
    contract_count = fields.Integer(compute='_compute_contract_count')

    def _compute_contract_count(self):
        for p in self:
            p.contract_count = len(p.contract_ids)

    def action_open_partner_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Договоры',
            'res_model': 'contract.contract',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
