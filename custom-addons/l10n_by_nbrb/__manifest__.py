{
    'name': 'Belarus: NBRB Currency Rates',
    'version': '19.0.1.0.0',
    'summary': 'Автоматическая загрузка курсов валют Национального банка РБ через api.nbrb.by.',
    'description': (
        'Интеграция с открытым REST API НБ РБ. Ежедневный cron, ручная загрузка, '
        'историческая загрузка за период, конвертер валют, журнал загрузок, '
        'уведомления о сбоях и резком изменении курса, графики динамики.'
    ),
    'author': 'miki-sol',
    'category': 'Accounting/Localizations',
    'depends': ['base', 'mail', 'account', 'l10n_by_company'],
    'data': [
        'security/ir.model.access.csv',
        'data/l10n_by_nbrb_settings_data.xml',
        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        'data/res_currency_nbrb_data.xml',
        'wizard/l10n_by_nbrb_history_wizard_views.xml',
        'wizard/l10n_by_nbrb_converter_wizard_views.xml',
        'views/res_currency_views.xml',
        'views/l10n_by_nbrb_log_views.xml',
        'views/l10n_by_nbrb_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
