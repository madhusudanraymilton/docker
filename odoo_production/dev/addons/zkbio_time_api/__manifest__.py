# -*- coding: utf-8 -*-
{
    'name': 'ZKBio Time API',
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Integration with ZKBio Time API for biometric attendance management',
    'description': """
ZKBio Time API Integration
===========================
This module provides integration with ZKBio Time API for managing biometric devices and attendance data.

Features:
---------
* Connect to ZKBio Time API
* Manage biometric terminals
* Sync attendance data automatically every 20 minutes
* Full pagination support - fetches ALL transaction data
* Configurable page size for optimal performance
* Configure API settings
* Real-time attendance tracking
* Auto-process to HR Attendance using First IN - Last OUT per day logic
* Timezone conversion support (device timezone to UTC)

Attendance Logic (First IN - Last OUT):
---------------------------------------
For each employee, per day:
* First punch of the day = Check In
* Last punch of the day = Check Out
* All middle punches = Ignored
* Result: One attendance record per employee per day
* Worked hours = Difference between first & last punch

Example:
  09:02 AM → Check In
  01:05 PM → Ignored
  02:00 PM → Ignored
  05:18 PM → Check Out
  Final Attendance: 09:02 AM - 05:18 PM (8h 16m worked)
    """,
    'author': 'Soaeb Abdullah @ ZenCore LTD',
    'website': 'http://zencoreltd.com/',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'hr_attendance',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/zkbio_config_views.xml',
        'views/zkbio_terminal_views.xml',
        'views/zkbio_transaction_views.xml',
        'views/zkbio_transaction_search.xml',
        'views/zkbio_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
