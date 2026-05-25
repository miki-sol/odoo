import logging

from odoo import api, models

from . import record_notify

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_employee_created()
        return records

    def _notify_employee_created(self):
        if record_notify.is_technical_context(self.env):
            return
        if not record_notify.flag(self.env, 'employee_enabled'):
            return
        try:
            record_notify.notify_created(
                self,
                'record_create_notify.mail_template_employee_created',
                'employee_user_ids',
            )
        except Exception:
            # A notification failure must never block employee creation.
            _logger.exception('record_create_notify: employee creation notification failed')
