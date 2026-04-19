from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sku = fields.Integer(
        string='SKU',
        required=True,
        copy=False,
        index=True,
        default=lambda self: self._default_sku(),
        help='Unique numeric identifier used for Excel-based sale order line imports.',
    )

    _sql_constraints = [
        ('sku_unique', 'UNIQUE(sku)', 'SKU must be unique across all products.'),
    ]

    @api.model
    def _default_sku(self):
        seq = self.env['ir.sequence'].next_by_code('product.template.sku')
        return int(seq) if seq else 0
