{
    'name': 'Attendance Custom Settings',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Attendances',
    'summary': (
        'Pre Check-In Tolerance, Post Check-Out Tolerance, '
        'Punishment Hours (late/forgotten check-out)'
    ),
    'author': 'Custom Development',
    'depends': ['hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/res_config_settings_views.xml',
        'views/hr_attendance_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
