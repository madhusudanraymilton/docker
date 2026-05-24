{
    'name': "HRM Shift Rostering",
    'version': '19.0.2.0',
    'summary': "Shift Rostering Dashboard with XLSX Import/Export",
    'author': "Md. Nadim Hossain",
    'website': "https://betopia.com/",
    'category': 'HRM',
    'depends': ['hr', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/resource_calendar_view.xml',
        'views/shift_rostering_dashboard_view.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hrm_shift_rostering/static/src/css/shift_rostering.css',
            'hrm_shift_rostering/static/src/js/shift_rostering_dashboard.js',
            'hrm_shift_rostering/static/src/xml/shift_rostering_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'auto_install': False,
}
