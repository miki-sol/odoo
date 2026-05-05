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
    rate_text = fields.Char(string='Курс', readonly=True)
    rate_from_byn_text = fields.Char(string='Курс источника к BYN', readonly=True)
    rate_to_byn_text = fields.Char(string='Курс цели к BYN', readonly=True)

    @api.onchange('amount_from', 'currency_from_id', 'currency_to_id', 'rate_date')
    def _onchange_compute(self):
        if not (self.currency_from_id and self.currency_to_id and self.rate_date):
            return
        self._do_compute()

    def _do_compute(self):
        company = self.env.company
        if self.currency_from_id == self.currency_to_id:
            self.amount_to = self.amount_from
            self.rate_text = f'1 {self.currency_from_id.name} = 1 {self.currency_to_id.name}'
            self.rate_from_byn_text = self.rate_to_byn_text = ''
            return

        self.amount_to = self.currency_from_id._convert(
            self.amount_from, self.currency_to_id, company, self.rate_date,
        )
        # Прямой курс пары: «1 источник = X цели»
        one_unit_converted = self.currency_from_id._convert(
            1.0, self.currency_to_id, company, self.rate_date, round=False,
        )
        self.rate_text = (
            f'1 {self.currency_from_id.name} = {one_unit_converted:.4f} '
            f'{self.currency_to_id.name}'
        )
        # Дополнительно показываем курсы каждой стороны к BYN (как публикует НБ РБ).
        byn = company.currency_id
        if self.currency_from_id != byn:
            from_to_byn = self.currency_from_id._convert(
                1.0, byn, company, self.rate_date, round=False,
            )
            self.rate_from_byn_text = (
                f'1 {self.currency_from_id.name} = {from_to_byn:.4f} {byn.name}'
            )
        else:
            self.rate_from_byn_text = ''
        if self.currency_to_id != byn:
            to_to_byn = self.currency_to_id._convert(
                1.0, byn, company, self.rate_date, round=False,
            )
            self.rate_to_byn_text = (
                f'1 {self.currency_to_id.name} = {to_to_byn:.4f} {byn.name}'
            )
        else:
            self.rate_to_byn_text = ''

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
