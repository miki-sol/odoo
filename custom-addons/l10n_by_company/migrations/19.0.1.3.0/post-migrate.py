from odoo import api, SUPERUSER_ID

from odoo.addons.l10n_by_company.hooks import _set_default_partner_accounts


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _set_default_partner_accounts(env)
