{
    "name": "BDcalling HR Attendance Custom Report",
    "version": "19.0.1.0",
    "sequence": 10,
    "summary": "Custom Attendance Report for HR & Payroll (Enterprise Supported)",
    "category": "Human Resources",
    "Author": "Anwar Hossain",
    "depends": [
        "web",
        "hr",
        "hr_attendance",
        "hr_payroll",
        "hr_payroll_attendance",   
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/hr_attendance_inherit_view.xml",
        "views/attendance_report_view.xml",
        "views/res_config_settings_views.xml",
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         'hr_attendance_custom_report/static/src/css/custom_attendance.css',
    #     ],
    # },
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
