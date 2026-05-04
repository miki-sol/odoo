from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nByNbrbHistoryWizard(models.TransientModel):
    _name = 'l10n.by.nbrb.history.wizard'
    _description = 'Загрузка курсов НБ РБ за период'

    date_from = fields.Date(string='Дата с', required=True,
                            default=lambda self: fields.Date.today() - timedelta(days=7))
    date_to = fields.Date(string='Дата по', required=True,
                          default=lambda self: fields.Date.today())
    currency_ids = fields.Many2many(
        'res.currency',
        relation='l10n_by_nbrb_history_wizard_currency_rel',
        string='Валюты',
        help='Если пусто — берутся отслеживаемые валюты из настроек.',
    )

    loaded_days = fields.Integer(readonly=True)
    error_days = fields.Integer(readonly=True)
    weekend_days = fields.Integer(readonly=True)

    def action_load(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_('«Дата по» не может быть раньше «Дата с».'))
        if (self.date_to - self.date_from).days > 366:
            raise UserError(_('Диапазон не должен превышать 366 дней '
                              '(чтобы не нагружать API).'))
        currencies = self.currency_ids
        if not currencies:
            currencies = self.env['l10n.by.nbrb.settings'].get_settings().tracked_currency_ids
        loaded, errors, weekends = self.env['l10n.by.nbrb.service'].load_historical_range(
            self.date_from, self.date_to, currencies=currencies,
        )
        self.write({
            'loaded_days': loaded,
            'error_days': errors,
            'weekend_days': weekends,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_logs(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.by.nbrb.log',
            'view_mode': 'list,form',
            'domain': [
                ('run_type', '=', 'historical'),
                ('target_date', '>=', self.date_from),
                ('target_date', '<=', self.date_to),
            ],
            'target': 'current',
        }
