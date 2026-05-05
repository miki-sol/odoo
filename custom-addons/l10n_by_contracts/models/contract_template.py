from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


CONTRACT_SIDE_SELECTION = [
    ('sale', 'Продажа (мы продавец)'),
    ('purchase', 'Закупка (мы покупатель)'),
]

CONTRACT_TYPE_SELECTION = [
    ('supply', 'Поставка'),
    ('services', 'Оказание услуг'),
    ('framework', 'Рамочный'),
    ('onetime', 'Разовый'),
    ('agency', 'Агентский'),
]

PAYMENT_TERMS_SELECTION = [
    ('prepay_100', 'Предоплата 100%'),
    ('prepay_50_50', '50% предоплата / 50% по факту'),
    ('postpay_7', 'Постоплата 7 дней'),
    ('postpay_14', 'Постоплата 14 дней'),
    ('postpay_30', 'Постоплата 30 дней'),
    ('on_fact', 'По факту'),
]

DELIVERY_METHOD_SELECTION = [
    ('pickup', 'Самовывоз'),
    ('our_transport', 'Доставка нашим транспортом'),
    ('carrier', 'Транспортная компания'),
]


class ContractTemplate(models.Model):
    _name = 'contract.template'
    _description = 'Шаблон договора'
    _order = 'side, sequence, name'

    name = fields.Char(string='Название шаблона', required=True, translate=False)
    sequence = fields.Integer(default=10)
    side = fields.Selection(CONTRACT_SIDE_SELECTION, string='Сторона', required=True)
    contract_type = fields.Selection(CONTRACT_TYPE_SELECTION, string='Тип договора')
    default_payment_terms = fields.Selection(
        PAYMENT_TERMS_SELECTION, string='Условия оплаты по умолчанию'
    )
    description = fields.Text(string='Описание (когда применяется)')
    template_file = fields.Binary(string='Файл DOCX-шаблона', attachment=True)
    template_filename = fields.Char(string='Имя файла')
    active = fields.Boolean(default=True)

    @api.constrains('template_filename')
    def _check_extension(self):
        for tpl in self:
            if tpl.template_filename and not tpl.template_filename.lower().endswith('.docx'):
                raise ValidationError(_('Шаблон должен быть в формате DOCX.'))
