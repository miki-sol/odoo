from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nByNbrbConverterWizard(models.TransientModel):
    _name = 'l10n.by.nbrb.converter.wizard'
    _description = 'Конвертер валют (по курсу НБ РБ)'

    amount_from = fields.Float(string='Сумма', required=True, default=1.0)
    currency_from_id = fields.Many2one('res.currency', string='Из валюты', required=True)
    currency_to_id = fields.Many2one('res.currency', string='В валюту', required=True)
    rate_date = fields.Date(string='Дата курса', default=fields.Date.today, required=True)

    amount_to = fields.Float(string='Эквивалент', readonly=True)
    rate_from_text = fields.Char(readonly=True)
    rate_to_text = fields.Char(readonly=True)

    @api.onchange('amount_from', 'currency_from_id', 'currency_to_id', 'rate_date')
    def _onchange_compute(self):
        if not (self.currency_from_id and self.currency_to_id and self.rate_date):
            return
        self._do_compute()

    def _do_compute(self):
        if self.currency_from_id == self.currency_to_id:
            self.amount_to = self.amount_from
            self.rate_from_text = self.rate_to_text = '1.0'
            return
        company = self.env.company
        amount_byn = self.currency_from_id._convert(
            self.amount_from, company.currency_id, company, self.rate_date,
        )
        self.amount_to = company.currency_id._convert(
            amount_byn, self.currency_to_id, company, self.rate_date,
        )
        rate_from = self._get_rate(self.currency_from_id, self.rate_date)
        rate_to = self._get_rate(self.currency_to_id, self.rate_date)
        self.rate_from_text = f'{self.currency_from_id.name}: {rate_from:.4f}'
        self.rate_to_text = f'{self.currency_to_id.name}: {rate_to:.4f}'

    def _get_rate(self, currency, target_date):
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', currency.id),
            ('company_id', '=', self.env.company.id),
            ('name', '<=', target_date),
        ], order='name desc', limit=1)
        return rate.rate if rate else 1.0

    def action_compute(self):
        self.ensure_one()
        if not (self.currency_from_id and self.currency_to_id):
            raise UserError(_('Укажите обе валюты.'))
        self._do_compute()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
