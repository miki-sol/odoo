from odoo import fields, models


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    nbrb_cur_id = fields.Integer(
        string='Код НБ РБ',
        help='Внутренний идентификатор валюты в НБ РБ (Cur_ID), используется для запроса '
             'курса конкретной валюты через api.nbrb.by.',
        index=True,
    )
    nbrb_scale = fields.Integer(
        string='Масштаб (НБ РБ)',
        default=1,
        help='Cur_Scale из API НБ РБ. Курс публикуется за эту единицу валюты. '
             'При сохранении в res.currency.rate курс делится на масштаб, чтобы '
             'хранить как «BYN за 1 единицу».',
    )

    def action_load_rate_now(self):
        log = self.env['l10n.by.nbrb.service'].update_rates_for_today(
            run_type='manual', currencies=self,
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.by.nbrb.log',
            'res_id': log.id if log else False,
            'view_mode': 'form',
            'target': 'current',
        }
