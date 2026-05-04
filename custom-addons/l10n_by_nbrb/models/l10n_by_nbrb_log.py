from odoo import fields, models


RUN_TYPES = [
    ('auto', 'Авто (cron)'),
    ('manual', 'Ручная'),
    ('historical', 'Исторический период'),
    ('test', 'Проверка соединения'),
]

STATES = [
    ('success', 'Успех'),
    ('partial', 'Частично'),
    ('skip', 'Пропуск (выходной/праздник)'),
    ('empty', 'Пусто (API без данных)'),
    ('error', 'Ошибка'),
]


class L10nByNbrbLog(models.Model):
    _name = 'l10n.by.nbrb.log'
    _description = 'Журнал загрузок курсов НБ РБ'
    _order = 'run_at desc'

    run_at = fields.Datetime(string='Дата и время', default=fields.Datetime.now, required=True)
    run_type = fields.Selection(RUN_TYPES, string='Тип запуска', required=True)
    state = fields.Selection(STATES, string='Результат', required=True)
    target_date = fields.Date(string='Дата курса', help='Дата, на которую запрашивались курсы.')
    rates_loaded = fields.Integer(string='Загружено валют', default=0)
    currency_codes = fields.Char(string='Коды валют')
    message = fields.Text(string='Сообщение')
    error_traceback = fields.Text(string='Стек ошибки')
    duration_ms = fields.Integer(string='Длительность, мс')
    triggered_by_user_id = fields.Many2one('res.users', string='Запустил',
                                           default=lambda self: self.env.user)
