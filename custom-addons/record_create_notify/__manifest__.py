{
    'name': 'Уведомления о создании контактов и сотрудников',
    'version': '19.0.1.0.0',
    'summary': 'Автоматические уведомления ответственным при создании res.partner и hr.employee '
               '(Discuss, chatter, email).',
    'description': (
        'Реализация ТЗ «Механизм уведомлений при создании карточки контакта и сотрудника».\n'
        'При создании новой записи контакта (res.partner) или сотрудника (hr.employee) '
        'ответственным лицам направляется уведомление в ленту записи, во входящие Discuss и '
        'по email на основе настраиваемого шаблона (mail.template). Получатели, каналы доставки '
        'и включение/отключение по каждому типу записи задаются администратором в «Настройках» '
        'без правки кода. Технические записи (импорт, миграция, дочерние контакты) исключаются.'
    ),
    'author': 'miki-sol',
    'category': 'Productivity',
    'depends': [
        'mail',
        'contacts',
        'hr',
    ],
    'data': [
        'data/mail_template_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
