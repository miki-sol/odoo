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


def post_init_hook(env):
    _set_default_product_accounts(env)
