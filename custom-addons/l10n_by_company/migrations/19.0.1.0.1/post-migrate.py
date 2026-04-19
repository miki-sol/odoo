"""Force-refresh the Russian translation of vat/company_registry labels.

Odoo stores translatable field labels as a JSONB column keyed by language.
Re-declaring `string='УНП'` in Python updates only `en_US`; the Russian key
keeps its old value "Налоговый ID" / "ID компании". This migration overwrites
both languages so the new labels show for all users regardless of locale.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_fields
        SET field_description =
            COALESCE(field_description, '{}'::jsonb)
            || '{"en_US": "УНП", "ru_RU": "УНП"}'::jsonb
        WHERE model = 'res.company' AND name = 'vat'
        """
    )
    cr.execute(
        """
        UPDATE ir_model_fields
        SET field_description =
            COALESCE(field_description, '{}'::jsonb)
            || '{"en_US": "Регистрационный № в ЕГР",
                 "ru_RU": "Регистрационный № в ЕГР"}'::jsonb
        WHERE model = 'res.company' AND name = 'company_registry'
        """
    )
