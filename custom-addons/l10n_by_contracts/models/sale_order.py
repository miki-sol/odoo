from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    contract_id = fields.Many2one(
        'contract.contract', string='Договор',
        domain="[('side','=','sale'),('partner_id','=',partner_id),('state','=','active')]",
        tracking=True,
    )

    @api.onchange('contract_id')
    def _onchange_contract(self):
        if self.contract_id:
            self.partner_id = self.contract_id.partner_id
            if self.contract_id.currency_id:
                self.currency_id = self.contract_id.currency_id

    @api.constrains('contract_id', 'partner_id')
    def _check_contract_partner(self):
        for order in self:
            if order.contract_id and order.contract_id.partner_id != order.partner_id:
                raise UserError(_(
                    'Контрагент заказа должен совпадать с контрагентом договора %s.'
                ) % order.contract_id.name)

    def _check_contract_constraints(self):
        for order in self:
            if not order.contract_id:
                continue
            order.contract_id._check_can_have_orders()
            order.contract_id._check_amount_limit(order.amount_total, exclude_order=order)

    def action_confirm(self):
        self._check_contract_constraints()
        return super().action_confirm()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_contract_constraints()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('contract_id', 'order_line', 'partner_id')):
            self._check_contract_constraints()
        return res
