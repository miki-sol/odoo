{
    'name': 'Sale Order Line Import (XLSX)',
    'version': '19.0.1.0.0',
    'summary': 'Import sale order lines from an Excel file using product SKU.',
    'author': 'miki-sol',
    'category': 'Sales',
    'depends': ['sale_management', 'product_sku'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/sale_order_line_import_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
