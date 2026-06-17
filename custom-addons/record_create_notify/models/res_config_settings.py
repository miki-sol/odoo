from odoo import api, fields, models

PARTNER_RECIPIENTS_PARAM = 'record_create_notify.partner_user_ids'
EMPLOYEE_RECIPIENTS_PARAM = 'record_create_notify.employee_user_ids'
SALE_ORDER_RECIPIENTS_PARAM = 'record_create_notify.sale_order_user_ids'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rcn_partner_enabled = fields.Boolean(
        string='Уведомлять о создании контактов',
        default=True,
        config_parameter='record_create_notify.partner_enabled',
    )
    rcn_employee_enabled = fields.Boolean(
        string='Уведомлять о создании сотрудников',
        default=True,
        config_parameter='record_create_notify.employee_enabled',
    )
    rcn_sale_order_enabled = fields.Boolean(
        string='Уведомлять о создании заказов на продажу',
        default=True,
        config_parameter='record_create_notify.sale_order_enabled',
    )
    rcn_channel_internal = fields.Boolean(
        string='Внутреннее уведомление (Discuss)',
        default=True,
        config_parameter='record_create_notify.channel_internal',
    )
    rcn_channel_email = fields.Boolean(
        string='Уведомление по email',
        default=True,
        config_parameter='record_create_notify.channel_email',
    )
    rcn_skip_child_contacts = fields.Boolean(
        string='Не уведомлять о дочерних контактах',
        default=True,
        config_parameter='record_create_notify.skip_child_contacts',
        help='Контактные лица внутри организации (с заполненной родительской компанией) '
             'считаются техническими записями и не порождают уведомление.',
    )
    rcn_partner_user_ids = fields.Many2many(
        'res.users',
        'record_create_notify_partner_user_rel', 'config_id', 'user_id',
        string='Получатели уведомлений о контактах',
    )
    rcn_employee_user_ids = fields.Many2many(
        'res.users',
        'record_create_notify_employee_user_rel', 'config_id', 'user_id',
        string='Получатели уведомлений о сотрудниках',
        help='Персональные данные сотрудников направляются только этим лицам '
             '(руководитель, кадровая служба).',
    )
    rcn_sale_order_user_ids = fields.Many2many(
        'res.users',
        'record_create_notify_sale_order_user_rel', 'config_id', 'user_id',
        string='Получатели уведомлений о заказах на продажу',
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()

        def _ids(key):
            raw = params.get_param(key, '')
            return [int(x) for x in raw.split(',') if x]

        res.update(
            rcn_partner_user_ids=[(6, 0, _ids(PARTNER_RECIPIENTS_PARAM))],
            rcn_employee_user_ids=[(6, 0, _ids(EMPLOYEE_RECIPIENTS_PARAM))],
            rcn_sale_order_user_ids=[(6, 0, _ids(SALE_ORDER_RECIPIENTS_PARAM))],
        )
        return res

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(PARTNER_RECIPIENTS_PARAM, ','.join(map(str, self.rcn_partner_user_ids.ids)))
        params.set_param(EMPLOYEE_RECIPIENTS_PARAM, ','.join(map(str, self.rcn_employee_user_ids.ids)))
        params.set_param(SALE_ORDER_RECIPIENTS_PARAM, ','.join(map(str, self.rcn_sale_order_user_ids.ids)))
