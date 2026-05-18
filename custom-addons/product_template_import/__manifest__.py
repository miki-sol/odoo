{
    'name': 'Product Template Import (XLSX)',
    'version': '19.0.1.0.0',
    'summary': 'Import products into product.template from an Excel file.',
    'author': 'miki-sol',
    'category': 'Inventory',
    'depends': ['product_sku'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/product_template_import_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
