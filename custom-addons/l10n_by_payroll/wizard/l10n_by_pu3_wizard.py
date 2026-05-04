import base64
from xml.etree import ElementTree as ET

from odoo import _, fields, models
from odoo.exceptions import UserError


QUARTERS = [('1', 'I'), ('2', 'II'), ('3', 'III'), ('4', 'IV')]


class L10nByPu3Wizard(models.TransientModel):
    _name = 'l10n.by.pu3.wizard'
    _description = 'Формирование ПУ-3 (квартальная отчётность ФСЗН)'

    year = fields.Integer(string='Год', required=True,
                          default=lambda self: fields.Date.today().year)
    quarter = fields.Selection(
        QUARTERS, string='Квартал', required=True,
        default=lambda self: str((fields.Date.today().month - 1) // 3 + 1),
    )
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)
    employee_count = fields.Integer(readonly=True)
    note = fields.Text(readonly=True, default=lambda self: _(
        'XML формируется в упрощённом представлении полей ПУ-3 (ФИО, ПИН, '
        'начисления, удержанные/начисленные взносы по сотруднику и месяцам '
        'квартала). Перед сдачей в ФСЗН формат должен быть согласован с '
        'актуальной XSD-схемой ФСЗН на портале ssf.gov.by.'
    ))

    def _quarter_months(self):
        q = int(self.quarter)
        return [str((q - 1) * 3 + i + 1) for i in range(3)]

    def action_generate(self):
        self.ensure_one()
        months = self._quarter_months()
        slips = self.env['l10n.by.payslip'].search([
            ('period_id.year', '=', self.year),
            ('period_id.month', 'in', months),
            ('period_state', '=', 'approved'),
        ])
        if not slips:
            raise UserError(_('Нет утверждённых расчётов за этот квартал.'))

        per_employee = {}
        for slip in slips:
            per_employee.setdefault(slip.employee_id, []).append(slip)

        root = ET.Element('PU3', attrib={
            'year': str(self.year),
            'quarter': self.quarter,
            'employees': str(len(per_employee)),
        })
        for emp, emp_slips in per_employee.items():
            emp_node = ET.SubElement(root, 'Employee')
            ET.SubElement(emp_node, 'FullName').text = emp.name or ''
            ET.SubElement(emp_node, 'PIN').text = emp.identification_id or ''
            total_gross = sum(s.gross_amount for s in emp_slips)
            total_fszn_emp = sum(s.fszn_employee for s in emp_slips)
            total_fszn_company = sum(s.fszn_employer for s in emp_slips)
            ET.SubElement(emp_node, 'TotalGross').text = f'{total_gross:.2f}'
            ET.SubElement(emp_node, 'TotalFsznEmployee').text = f'{total_fszn_emp:.2f}'
            ET.SubElement(emp_node, 'TotalFsznEmployer').text = f'{total_fszn_company:.2f}'
            months_node = ET.SubElement(emp_node, 'Months')
            for slip in sorted(emp_slips, key=lambda s: int(s.period_id.month)):
                m = ET.SubElement(months_node, 'Month',
                                  attrib={'month': slip.period_id.month})
                ET.SubElement(m, 'Gross').text = f'{slip.gross_amount:.2f}'
                ET.SubElement(m, 'FsznEmployee').text = f'{slip.fszn_employee:.2f}'
                ET.SubElement(m, 'FsznEmployer').text = f'{slip.fszn_employer:.2f}'

        xml_str = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8')
        self.file_data = base64.b64encode(xml_str)
        self.file_name = f'PU3_{self.year}_Q{self.quarter}.xml'
        self.employee_count = len(per_employee)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
