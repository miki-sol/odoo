{
    'name': 'Belarus: Учёт договоров с клиентами и поставщиками',
    'version': '19.0.1.0.0',
    'summary': 'Реестр договоров, шаблоны DOCX, связь с заказами, контроль сроков. Адаптировано под РБ.',
    'description': (
        'Единый модуль учёта договоров (продажи + закупки): карточка договора, '
        'жизненный цикл, библиотека шаблонов, автогенерация DOCX из шаблона, '
        'связь с sale.order/purchase.order, контроль лимита рамочных договоров, '
        'ежедневный контроль сроков с уведомлениями (60/30/14/7/0 дней), '
        'допсоглашения, автопродление.'
    ),
    'author': 'miki-sol',
    'category': 'Sales',
    'depends': [
        'base',
        'mail',
        'sale_management',
        'purchase',
        'account',
        'l10n_by_company',
    ],
    'external_dependencies': {
        'python': ['docxtpl', 'num2words'],
    },
    'data': [
        'security/contract_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        'data/contract_template_data.xml',
        'views/contract_views.xml',
        'views/contract_template_views.xml',
        'views/contract_amendment_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
