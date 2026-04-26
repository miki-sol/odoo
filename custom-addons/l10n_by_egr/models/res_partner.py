import logging
from datetime import datetime, date

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_EGR_BASE = 'https://egr.gov.by/api/v2/egr'
_TIMEOUT = 10

_STATUS_MAP = {
    '1': '1',
    '2': '2',
    '3': '3',
}


class _EgrNotFound(Exception):
    pass


class _EgrServiceError(Exception):
    pass


class ResPartner(models.Model):
    _inherit = 'res.partner'

    egr_full_name = fields.Char(string='Полное наименование', readonly=True)
    egr_full_name_be = fields.Char(string='Полное наименование (бел.)', readonly=True)
    egr_firm_name = fields.Char(string='Фирменное наименование', readonly=True)
    egr_status = fields.Selection(
        selection=[
            ('1', 'Действующая'),
            ('2', 'Исключена из ЕГР'),
            ('3', 'В процессе ликвидации'),
        ],
        string='Статус в ЕГР',
        readonly=True,
    )
    egr_reg_date = fields.Date(string='Дата регистрации', readonly=True)
    egr_excl_date = fields.Date(string='Дата исключения', readonly=True)
    egr_entity_type = fields.Char(string='Вид субъекта хозяйствования', readonly=True)
    egr_authority = fields.Char(string='Регистрирующий орган', readonly=True)
    egr_oked = fields.Char(string='ОКЭД', readonly=True)
    egr_sync_date = fields.Datetime(string='Последняя синхронизация с ЕГР', readonly=True)
    egr_button_visible = fields.Boolean(
        compute='_compute_egr_button_visible',
    )

    def _compute_egr_button_visible(self):
        for partner in self:
            vat = partner.vat or ''
            partner.egr_button_visible = (
                partner.is_company and vat.isdigit() and len(vat) == 9
            )

    # ------------------------------------------------------------------ #
    #  Onchange — auto-fill on УНП entry                                  #
    # ------------------------------------------------------------------ #

    @api.onchange('vat')
    def _onchange_vat_egr(self):
        unp = (self.vat or '').strip()
        if not (unp.isdigit() and len(unp) == 9):
            return
        try:
            data = self._egr_fetch_all(unp)
        except _EgrNotFound:
            return {'warning': {
                'title': _('ЕГР'),
                'message': _(
                    'По УНП %(unp)s данные в ЕГР не найдены. '
                    'Проверьте правильность номера или введите данные вручную.',
                    unp=unp,
                ),
            }}
        except _EgrServiceError:
            return {'warning': {
                'title': _('ЕГР'),
                'message': _('Сервис ЕГР временно недоступен. Попробуйте позже или введите данные вручную.'),
            }}
        except requests.Timeout:
            return {'warning': {
                'title': _('ЕГР'),
                'message': _('Превышено время ожидания ответа от ЕГР.'),
            }}
        except requests.ConnectionError:
            return {'warning': {
                'title': _('ЕГР'),
                'message': _('Не удалось подключиться к серверу ЕГР. Проверьте интернет-соединение.'),
            }}
        vals = self._egr_build_vals(data, unp)
        for field, value in vals.items():
            setattr(self, field, value)

    # ------------------------------------------------------------------ #
    #  Public action (button — manual re-fetch)                           #
    # ------------------------------------------------------------------ #

    def action_load_from_egr(self):
        self.ensure_one()
        unp = (self.vat or '').strip()
        if not (unp.isdigit() and len(unp) == 9):
            raise UserError(_('УНП должен содержать 9 цифр.'))

        try:
            data = self._egr_fetch_all(unp)
        except _EgrNotFound:
            raise UserError(
                _(
                    'По УНП %(unp)s данные в ЕГР не найдены. '
                    'Проверьте правильность номера или введите данные вручную.',
                    unp=unp,
                )
            )
        except _EgrServiceError:
            raise UserError(_('Сервис ЕГР временно недоступен. Попробуйте позже или введите данные вручную.'))
        except requests.Timeout:
            raise UserError(_('Превышено время ожидания ответа от ЕГР.'))
        except requests.ConnectionError:
            raise UserError(
                _('Не удалось подключиться к серверу ЕГР. Проверьте интернет-соединение.')
            )

        vals = self._egr_build_vals(data, unp)
        self.write(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('ЕГР'),
                'message': _('Данные успешно загружены из ЕГР.'),
                'type': 'success',
                'sticky': False,
            },
        }

    # ------------------------------------------------------------------ #
    #  API helpers                                                         #
    # ------------------------------------------------------------------ #

    def _egr_get(self, method, unp, required=False):
        url = f'{_EGR_BASE}/{method}/{unp}'
        resp = requests.get(url, timeout=_TIMEOUT, headers={'Accept': 'application/json'})
        if resp.status_code == 204:
            if required:
                raise _EgrNotFound()
            return None
        if resp.status_code != 200:
            _logger.warning('EGR %s → HTTP %s', url, resp.status_code)
            if required:
                raise _EgrServiceError()
            return None
        return resp.json()

    def _egr_fetch_all(self, unp):
        short = self._egr_get('getShortInfoByRegNum', unp, required=True)

        names = self._egr_get('getJurNamesByRegNum', unp) or []
        address = self._egr_get('getAddressByRegNum', unp) or []
        base = self._egr_get('getBaseInfoByRegNum', unp) or {}
        ved = self._egr_get('getVEDByRegNum', unp) or []

        is_ip = self._egr_is_ip(short)
        fio = {}
        if is_ip:
            fio = self._egr_get('getIPFIOByRegNum', unp) or {}

        return {
            'short': short,
            'names': names,
            'address': address,
            'base': base,
            'ved': ved,
            'fio': fio,
            'is_ip': is_ip,
        }

    @staticmethod
    def _egr_is_ip(short):
        if isinstance(short, list) and short:
            short = short[0]
        if not isinstance(short, dict):
            return False
        vtype = short.get('vtype', '') or ''
        return 'ИП' in vtype or 'индивидуальный предприниматель' in vtype.lower()

    @staticmethod
    def _egr_active_record(records):
        if not isinstance(records, list):
            return records if isinstance(records, dict) else {}
        today = date.today()
        for rec in records:
            if not isinstance(rec, dict):
                continue
            if rec.get('cact') == '1':
                dto_raw = rec.get('dto', '')
                if not dto_raw:
                    return rec
                try:
                    dto = datetime.strptime(dto_raw, '%d.%m.%Y').date()
                    if dto >= today:
                        return rec
                except ValueError:
                    return rec
        return records[0] if records else {}

    @staticmethod
    def _egr_parse_date(raw):
        if not raw:
            return False
        try:
            return datetime.strptime(raw, '%d.%m.%Y').date()
        except ValueError:
            return False

    # ------------------------------------------------------------------ #
    #  Value builders                                                      #
    # ------------------------------------------------------------------ #

    def _egr_build_vals(self, data, unp):
        short = data['short']
        if isinstance(short, list) and short:
            short = short[0]

        names_rec = self._egr_active_record(data['names'])
        addr_rec = self._egr_active_record(data['address'])
        base = data['base']
        if isinstance(base, list) and base:
            base = base[0]
        ved_rec = self._egr_active_record(data['ved'])
        fio = data['fio']
        if isinstance(fio, list) and fio:
            fio = fio[0]

        vals = {}

        # --- company name ---
        if data['is_ip']:
            vfio = (fio.get('vfio') or '').strip()
            vals['name'] = vfio or names_rec.get('vn') or names_rec.get('vnaim') or self.name
        else:
            vn = (names_rec.get('vn') or '').strip()
            vals['name'] = vn or names_rec.get('vnaim') or self.name

        # --- EGR readonly fields ---
        vals['egr_full_name'] = (names_rec.get('vnaim') or '').strip() or False
        vals['egr_full_name_be'] = (names_rec.get('vnaimb') or '').strip() or False
        vals['egr_firm_name'] = (names_rec.get('vfn') or '').strip() or False

        status_raw = str(short.get('nsi00219', '') or '')
        vals['egr_status'] = _STATUS_MAP.get(status_raw) or False

        vals['egr_reg_date'] = self._egr_parse_date(base.get('dfrom'))
        vals['egr_excl_date'] = self._egr_parse_date(base.get('dto'))

        entity_type_val = base.get('nsi00211')
        if isinstance(entity_type_val, dict):
            vals['egr_entity_type'] = entity_type_val.get('vnaimp') or entity_type_val.get('vnaim') or False
        else:
            vals['egr_entity_type'] = str(entity_type_val).strip() if entity_type_val else False

        authority_val = base.get('nsi00212')
        if isinstance(authority_val, dict):
            vals['egr_authority'] = authority_val.get('vnaimp') or authority_val.get('vnaim') or False
        else:
            vals['egr_authority'] = str(authority_val).strip() if authority_val else False

        oked_val = ved_rec.get('nsi00114')
        if isinstance(oked_val, dict):
            vals['egr_oked'] = oked_val.get('vnaimp') or oked_val.get('vnaim') or False
        else:
            vals['egr_oked'] = str(oked_val).strip() if oked_val else False

        # --- company_registry (ngrn) ---
        ngrn = str(short.get('ngrn') or '').strip()
        if ngrn and ngrn.isdigit() and len(ngrn) == 9:
            vals['company_registry'] = ngrn

        # --- contact fields (only if currently empty) ---
        vemail = (addr_rec.get('vemail') or '').strip()
        if vemail and not self.email:
            vals['email'] = vemail

        vtels = (addr_rec.get('vtels') or '').strip()
        if vtels and not self.phone:
            first_phone = vtels.split(',')[0].split(';')[0].replace(' ', '').strip()
            vals['phone'] = first_phone

        vsite = (addr_rec.get('vsite') or '').strip()
        if vsite and not self.website:
            if not vsite.startswith(('http://', 'https://')):
                vsite = 'https://' + vsite
            vals['website'] = vsite

        # --- address (always overwrite per spec) ---
        vals.update(self._egr_build_address(addr_rec))

        vals['egr_sync_date'] = fields.Datetime.now()
        return vals

    def _egr_build_address(self, addr_rec):
        vals = {}

        # country = Belarus
        by = self.env['res.country'].search([('code', '=', 'BY')], limit=1)
        if by:
            vals['country_id'] = by.id

        # zip
        nindex = (str(addr_rec.get('nindex') or '')).strip()
        if nindex:
            vals['zip'] = nindex

        # city: prefix from nsi00239 + settlement name
        city_parts = []
        np_type = addr_rec.get('nsi00239')
        if isinstance(np_type, dict):
            prefix = (np_type.get('vkrat') or np_type.get('vnaim') or '').strip()
            if prefix:
                city_parts.append(prefix + '.')
        vnp = (addr_rec.get('vnp') or '').strip()
        if vnp:
            city_parts.append(vnp)
        if city_parts:
            vals['city'] = ' '.join(city_parts)

        # state (region)
        vregion = addr_rec.get('vregion')
        region_name = ''
        if isinstance(vregion, dict):
            region_name = (vregion.get('vnaimp') or vregion.get('vnaim') or '').strip()
        elif isinstance(vregion, str):
            region_name = vregion.strip()
        if region_name and by:
            state = self.env['res.country.state'].search(
                [('country_id', '=', by.id), ('name', 'ilike', region_name)],
                limit=1,
            )
            if not state:
                state = self.env['res.country.state'].create({
                    'country_id': by.id,
                    'name': region_name,
                    'code': region_name[:3].upper(),
                })
            vals['state_id'] = state.id

        # street: type + street name + house + building
        street_parts = []
        st_type = addr_rec.get('nsi00226')
        if isinstance(st_type, dict):
            st_prefix = (st_type.get('vkrat') or st_type.get('vnaim') or '').strip()
            if st_prefix:
                street_parts.append(st_prefix + '.')
        vulitsa = (addr_rec.get('vulitsa') or '').strip()
        if vulitsa:
            street_parts.append(vulitsa)
        vdom = (addr_rec.get('vdom') or '').strip()
        if vdom:
            street_parts.append(f'д. {vdom}')
        vkorp = (addr_rec.get('vkorp') or '').strip()
        if vkorp:
            street_parts.append(f'корп. {vkorp}')
        if street_parts:
            vals['street'] = ', '.join(street_parts)

        # street2: office/premises + remark
        street2_parts = []
        pom_type = addr_rec.get('nsi00227')
        vpom = (addr_rec.get('vpom') or '').strip()
        if vpom:
            pom_prefix = ''
            if isinstance(pom_type, dict):
                pom_prefix = (pom_type.get('vkrat') or pom_type.get('vnaim') or '').strip()
            street2_parts.append((pom_prefix + '. ' + vpom).strip(' .'))
        vadrprim = (addr_rec.get('vadrprim') or '').strip()
        if vadrprim:
            street2_parts.append(vadrprim)
        if street2_parts:
            vals['street2'] = ', '.join(street2_parts)

        return vals
