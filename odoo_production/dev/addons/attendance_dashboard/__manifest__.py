{
    'name': 'Attendance Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Dashboard',
    'author': 'Md Sohag Hossain',
    'depends': ['base', 'web', 'mail','hr','hr_attendance','hr_holidays'],
    'data': [
        "security/ir.model.access.csv",
        "views/attendance_menue.xml",
    ],
    'assets': {
        'web.assets_backend': [
            "attendance_dashboard/static/src/css/attendance_dashboard.css",
            "attendance_dashboard/static/src/js/attendance_dashboard.js",
            "attendance_dashboard/static/src/xml/dashboard.xml",
        ],
        'web.assets_backend_lazy': [
            # 'vac_bams_dashboard/static/src/xml/bam_dashboard.xml',
        ],
    },
    'images': [
        'static/description/icon.png',
        ], 
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}


