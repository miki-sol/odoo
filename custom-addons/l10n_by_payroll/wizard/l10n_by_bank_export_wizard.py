import base64
import csv
import io
from xml.etree import ElementTree as ET

from odoo import _, fields, models
from odoo.exceptions import UserError


BANK_FORMATS = [
    ('csv_generic', 'Универсальный CSV (любой банк)'),
    ('xml_belarusbank', 'Беларусбанк (пример XML)'),
    ('xml_priorbank', 'Приорбанк (пример XML)'),
    ('xml_alfabank', 'Альфа-Банк (пример XML)'),
    ('xml_belinvestbank', 'Белинвестбанк (пример XML)'),
]


class L10nByBankExportWizard(models.TransientModel):
    _name = 'l10n.by.bank.export.wizard'
    _description = 'Выгрузка зарплатной ведомости в банк'

    period_id = fields.Many2one(
        'l10n.by.payroll.period',
        string='Расчётный период',
        required=True,
    )
    bank_format = fields.Selection(
        BANK_FORMATS,
        string='Формат',
        required=True,
        default='csv_generic',
    )
    file_data = fields.Binary(string='Файл', readonly=True)
    file_name = fields.Char(readonly=True)
    note = fields.Text(readonly=True, default=lambda self: _(
        'Реальные форматы белорусских банков являются проприетарными и периодически '
        'меняются. CSV принимается большинством клиент-банков напрямую. XML-форматы '
        'здесь — упрощённые шаблоны: при внедрении в конкретный банк потребуется '
        'согласовать схему с интеграционным отделом банка.'
    ))

    def action_generate(self):
        self.ensure_one()
        if self.period_id.state != 'approved':
            raise UserError(_('Выгрузка возможна только для утверждённого периода.'))
        rows = self._collect_rows()
        if not rows:
            raise UserError(_('Нет расчётных листов с заполненным IBAN и положительной суммой.'))
        if self.bank_format == 'csv_generic':
            content, filename = self._render_csv(rows)
        else:
            content, filename = self._render_xml(rows)
        self.file_data = base64.b64encode(content)
        self.file_name = filename
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _collect_rows(self):
        rows = []
        for slip in self.period_id.payslip_ids:
            iban = slip.employee_id.l10n_by_iban
            if not iban or slip.net_amount <= 0:
                continue
            rows.append({
                'name': slip.employee_id.name or '',
                'iban': iban.replace(' ', ''),
                'amount': round(slip.net_amount, 2),
            })
        return rows

    def _render_csv(self, rows):
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=';')
        writer.writerow(['ФИО', 'IBAN', 'Сумма BYN'])
        for r in rows:
            writer.writerow([r['name'], r['iban'], f"{r['amount']:.2f}"])
        return buf.getvalue().encode('utf-8-sig'), f"payroll_{self.period_id.year}_{self.period_id.month}.csv"

    def _render_xml(self, rows):
        bank_code = self.bank_format.replace('xml_', '')
        root = ET.Element('PayrollBatch', attrib={
            'bank': bank_code,
            'period': self.period_id.display_name or '',
            'currency': 'BYN',
            'count': str(len(rows)),
            'totalAmount': f"{sum(r['amount'] for r in rows):.2f}",
        })
        for r in rows:
            payment = ET.SubElement(root, 'Payment')
            ET.SubElement(payment, 'Beneficiary').text = r['name']
            ET.SubElement(payment, 'Account').text = r['iban']
            ET.SubElement(payment, 'Amount').text = f"{r['amount']:.2f}"
        xml_str = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8')
        return xml_str, f"payroll_{bank_code}_{self.period_id.year}_{self.period_id.month}.xml"
