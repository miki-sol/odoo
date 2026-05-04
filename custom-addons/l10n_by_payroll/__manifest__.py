{
    'name': 'Belarus: Payroll',
    'version': '19.0.1.0.0',
    'summary': 'Расчёт заработной платы по правилам Республики Беларусь.',
    'description': (
        'Расчёт ЗП по законодательству РБ: подоходный налог 13%, '
        'стандартный/детский/льготный вычеты, ФСЗН (1% работник, 34% наниматель), '
        'Белгосстрах. История ставок по дате, ежемесячные расчётные периоды.'
    ),
    'author': 'miki-sol',
    'category': 'Human Resources/Payroll',
    'depends': ['hr', 'l10n_by_company'],
    'data': [
        'security/ir.model.access.csv',
        'data/l10n_by_payroll_config_data.xml',
        'views/l10n_by_payroll_config_views.xml',
        'views/hr_employee_views.xml',
        'views/l10n_by_payslip_views.xml',
        'views/l10n_by_payroll_period_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
