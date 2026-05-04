{
    'name': 'Belarus: Payroll',
    'version': '19.0.1.1.0',
    'summary': 'Расчёт заработной платы по правилам Республики Беларусь.',
    'description': (
        'Расчёт ЗП по законодательству РБ: подоходный налог 13%, '
        'стандартный/детский/льготный вычеты, ФСЗН (1% работник, 34% наниматель), '
        'Белгосстрах. История ставок по дате, ежемесячные расчётные периоды, '
        'бухгалтерские проводки, PDF-расчётка с email-рассылкой, отпускные и '
        'больничные по среднему, выгрузка ведомости в банк, отчётность ПУ-3 и ФОТ.'
    ),
    'author': 'miki-sol',
    'category': 'Human Resources/Payroll',
    'depends': ['hr', 'account', 'mail', 'l10n_by_company'],
    'data': [
        'security/ir.model.access.csv',
        'data/l10n_by_payroll_config_data.xml',
        'report/payslip_report.xml',
        'data/mail_template_data.xml',
        'report/l10n_by_fot_report_views.xml',
        'wizard/l10n_by_vacation_wizard_views.xml',
        'wizard/l10n_by_sickleave_wizard_views.xml',
        'wizard/l10n_by_bank_export_wizard_views.xml',
        'wizard/l10n_by_pu3_wizard_views.xml',
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
