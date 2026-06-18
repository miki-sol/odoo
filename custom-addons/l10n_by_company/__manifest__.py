{
    'name': 'Belarus: Company Fields',
    'version': '19.0.1.3.0',
    'summary': 'Adapt res.company fields for Belarusian business (УНП, ЕГР, IBAN).',
    'author': 'miki-sol',
    'category': 'Accounting/Localizations',
    'depends': ['base', 'account'],
    'data': [
        'data/res_country_data.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'license': 'LGPL-3',
}
