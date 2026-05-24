# -*- coding: utf-8 -*-
{
    'name': 'Employee Inter/Intra Company Transfer',
    'version': '19.0.1.0.0',
    'category': 'afzal',
    'summary': 'Manage Inter-Company and Intra-Company Employee Transfers',
    'description': """
        This module provides comprehensive employee transfer management:
        - Inter-Company Transfers (permanent and temporary)
        - Intra-Company Transfers
        - Automatic contract archival and creation
        - Leave allocation carry-forward
        - Email notifications at each stage
        - Scheduled cron job for temporary transfer reversal
    """,
    'author': 'Odoo Apps',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_holidays',
        'mail',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/email_templates.xml',
        'data/cron_jobs.xml',
        'views/hr_company_transfer_views.xml',
        'views/hr_intra_transfer_views.xml',
        'views/hr_employee_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
