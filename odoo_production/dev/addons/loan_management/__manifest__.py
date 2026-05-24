{
    'name': 'BDcalling Loan Management',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Employee Loan and Salary Advance Management System',
    'description': """
        Comprehensive loan management system for employees including salary advances.
        Integrates with HR, Payroll, and Accounting modules.
        Features include:
        - Employee loan requests and approvals
        - Salary advance management
        - Loan repayment tracking
        - Installment schedule generation
        - Accounting integration
        - Payroll deduction support
    """,
    'author': 'Anwar',
    'website': 'https://github.com/anwarhossen',
    'depends': [
        'base',
        'hr',
        'account',
        'hr_payroll',
        'mail',
    ],
    'data': [
        # Security files
        'security/ir.model.access.csv',
        'security/loan_security.xml',
        
        # Data files
        'data/loan_data.xml',
        
        # View files (in correct order)
        'views/loan_views.xml',
        'views/loan_repayment_views.xml',
        'views/salary_advance_views.xml',
        'views/menu_views.xml',
      
        
        # Report files
        'reports/loan_report.xml',
        'reports/loan_report_templates.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}