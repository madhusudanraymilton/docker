{
    'name': 'HR Payslip Manual Payment',
    'version': '19.0.1.0.0',
    'category': 'Payroll',
    'summary': 'Manual & Bulk Payment wizard for HR Payslips',
    'depends': ['hr_payroll', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_payslip_views.xml',
        'views/manual_payment_wizard_views.xml',
        'views/bulk_payment_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
