{
    'name': 'Belarus: EGR Integration',
    'version': '19.0.1.0.0',
    'summary': 'Load company data from egr.gov.by by УНП with one click.',
    'author': 'miki-sol',
    'category': 'Accounting/Localizations',
    'depends': ['l10n_by_company'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
