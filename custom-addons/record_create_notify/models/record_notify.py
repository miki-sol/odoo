"""Shared notification logic for record-creation alerts (res.partner, hr.employee).

Config is stored as ir.config_parameter under the ``record_create_notify.*`` namespace
and edited via res.config.settings.
"""
from odoo import Command
from odoo.tools import str2bool

PARAM_PREFIX = 'record_create_notify'


def param(env, suffix, default=''):
    return env['ir.config_parameter'].sudo().get_param(f'{PARAM_PREFIX}.{suffix}', default)


def flag(env, suffix, default=True):
    return str2bool(param(env, suffix, str(default)), default)


def is_technical_context(env):
    """True for non-interactive creation (install/data load, import, migration)."""
    ctx = env.context
    return bool(
        ctx.get('install_mode')
        or ctx.get('import_file')
        or ctx.get('tracking_disable')
        or ctx.get('skip_create_notification')
    )


def recipients(env, users_suffix):
    raw = param(env, users_suffix)
    ids = [int(x) for x in raw.split(',') if x]
    return env['res.users'].browse(ids).exists() if ids else env['res.users']


def notify_created(records, template_xmlid, users_suffix):
    env = records.env
    template = env.ref(template_xmlid, raise_if_not_found=False)
    if not template:
        return
    users = recipients(env, users_suffix)
    internal_on = flag(env, 'channel_internal')
    email_on = flag(env, 'channel_email')
    if not users or not (internal_on or email_on):
        return
    for record in records:
        _deliver_one(record, template, users, internal_on, email_on)


def _deliver_one(record, template, users, internal_on, email_on):
    subject = template._render_field('subject', [record.id])[record.id]
    body = template._render_field('body_html', [record.id])[record.id]

    record.message_post(
        body=body,
        subject=subject,
        message_type='notification',
        subtype_xmlid='mail.mt_note',
        partner_ids=users.partner_id.ids if internal_on else [],
    )

    if email_on:
        # The post above already e-mails recipients whose preference is e-mail;
        # force-send only to the remainder so nobody receives a duplicate.
        targets = users if not internal_on else users.filtered(
            lambda u: u.notification_type != 'email'
        )
        if targets:
            template.send_mail(
                record.id,
                force_send=True,
                email_values={'recipient_ids': [Command.set(targets.partner_id.ids)]},
            )
