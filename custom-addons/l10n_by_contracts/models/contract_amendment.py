from odoo import _, api, fields, models


class ContractAmendment(models.Model):
    _name = 'contract.amendment'
    _description = 'Дополнительное соглашение к договору'
    _inherit = ['mail.thread']
    _order = 'date_signed desc, id desc'

    name = fields.Char(string='Номер ДС', required=True, copy=False, default=lambda s: _('Новый'))
    contract_id = fields.Many2one('contract.contract', string='Договор', required=True, ondelete='cascade')
    subject = fields.Char(string='Предмет изменения', required=True)
    date_signed = fields.Date(string='Дата подписания', default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', 'Черновик'),
        ('signed', 'Подписан'),
    ], default='draft', tracking=True)
    note = fields.Text(string='Комментарий')
    attachment = fields.Binary(string='Скан подписанного ДС', attachment=True)
    attachment_filename = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Новый')) == _('Новый'):
                contract = self.env['contract.contract'].browse(vals.get('contract_id'))
                seq = self.env['ir.sequence'].next_by_code('contract.amendment') or '1'
                base = contract.name or 'XXX'
                vals['name'] = f"ДС-{seq} к {base}"
        return super().create(vals_list)
