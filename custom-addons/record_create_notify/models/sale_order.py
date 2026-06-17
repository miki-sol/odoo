import logging

from odoo import api, models

from . import record_notify

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_sale_order_created()
        return records

    def _notify_sale_order_created(self):
        if record_notify.is_technical_context(self.env):
            return
        if not record_notify.flag(self.env, 'sale_order_enabled'):
            return
        try:
            record_notify.notify_created(
                self,
                'record_create_notify.mail_template_sale_order_created',
                'sale_order_user_ids',
            )
        except Exception:
            # A notification failure must never block sale order creation.
            _logger.exception('record_create_notify: sale order creation notification failed')
