def _set_default_product_accounts(env):
    """Set company-level fallback income/expense accounts so invoice lines
    always resolve an account, even when products/categories leave it empty
    (see account.product._get_product_accounts)."""
    Account = env['account.account']
    for company in env['res.company'].search([]):
        if not company.income_account_id:
            income = Account.search(
                [('company_ids', 'in', company.id), ('account_type', '=', 'income')],
                order='code', limit=1,
            )
            if income:
                company.income_account_id = income.id
        if not company.expense_account_id:
            expense = Account.search(
                [('company_ids', 'in', company.id), ('account_type', '=', 'expense')],
                order='code', limit=1,
            )
            if expense:
                company.expense_account_id = expense.id


# (account_type, partner property, fallback code/name when none exists)
_PARTNER_ACCOUNTS = [
    ('asset_receivable', 'property_account_receivable_id', '6210', 'Расчёты с покупателями и заказчиками'),
    ('liability_payable', 'property_account_payable_id', '6010', 'Расчёты с поставщиками и подрядчиками'),
]


def _set_default_partner_accounts(env):
    """Guarantee every company has a receivable/payable account and register it
    as the company-dependent default on res.partner. Without this the invoice
    payment-term line resolves no account and the move is rejected by
    account_move_line._check_accountable_required_fields."""
    Account = env['account.account']
    IrDefault = env['ir.default']
    for company in env['res.company'].search([]):
        company_account = Account.with_company(company)
        for account_type, field, code, name in _PARTNER_ACCOUNTS:
            account = company_account.search(
                [('company_ids', 'in', company.id), ('account_type', '=', account_type)],
                order='code', limit=1,
            )
            if not account:
                account = company_account.create({
                    'name': name,
                    'code': company_account._search_new_account_code(code),
                    'account_type': account_type,
                })
            IrDefault.set('res.partner', field, account.id, company_id=company.id)


def post_init_hook(env):
    _set_default_product_accounts(env)
    _set_default_partner_accounts(env)
