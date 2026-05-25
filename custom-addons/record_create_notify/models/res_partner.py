import logging

from odoo import api, models

from . import record_notify

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_partner_created()
        return records

    def _notify_partner_created(self):
        if record_notify.is_technical_context(self.env):
            return
        if not record_notify.flag(self.env, 'partner_enabled'):
            return
        skip_children = record_notify.flag(self.env, 'skip_child_contacts')
        to_notify = self.filtered(lambda p: not (skip_children and p.parent_id))
        if not to_notify:
            return
        try:
            record_notify.notify_created(
                to_notify,
                'record_create_notify.mail_template_partner_created',
                'partner_user_ids',
            )
        except Exception:
            # A notification failure must never block contact creation.
            _logger.exception('record_create_notify: partner creation notification failed')
