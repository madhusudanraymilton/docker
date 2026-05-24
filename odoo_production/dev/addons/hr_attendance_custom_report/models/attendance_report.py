# from odoo import models, fields, api
# from datetime import datetime, time, timedelta
# from dateutil.relativedelta import relativedelta
# import pytz

# class AttendanceReport(models.Model):
#     _inherit = 'hr.attendance'

#     #  necessary fields 
#     emp_code = fields.Char(related='employee_id.identification_id', store=True)
#     department_id = fields.Many2one(related='employee_id.department_id', store=True)

#     shift = fields.Selection([
#         ('morning', 'Morning Shift'),
#         ('night', 'Night Shift'),
#     ], string="Shift", compute="_compute_shift", store=True)

#     working_hours = fields.Char(string="Working Hours", compute="_compute_extra", store=True)
#     extra_hours = fields.Char(string="Extra Hours", compute="_compute_extra", store=True)
    
#     late_time = fields.Char(string="Late Time", compute="_compute_extra", store=True)
#     early_out = fields.Char(string="Early Out", compute="_compute_extra", store=True)

#     is_absent = fields.Boolean(string="Absent", compute="_compute_absent", store=True)
#     leave_type = fields.Selection([
#         ('cl', 'Casual Leave'),
#         ('sl', 'Sick Leave'),
#         ('ml', 'Medical Leave'),
#     ], string='Leave Type')

#     # Late Deduction Fields
#     is_late = fields.Boolean(string="Late", compute="_compute_extra", store=True)
#     late_count_monthly = fields.Integer(string="Monthly Late Count", compute="_compute_late_deduction", store=True)
    
#     # Leave Deduction Fields
#     leave_deduction_days = fields.Float(string="Leave Deduction Days", compute="_compute_late_deduction", store=True)
#     deducted_leave_type = fields.Char(string="Deducted Leave Type", compute="_compute_late_deduction", store=True)

#     # Status Badge Field
#     status_badge = fields.Html(string="Status", compute="_compute_status_badge", sanitize=False)

#     # ---------------------------------------------
#     # Get Tolerance Time from Settings
#     # ---------------------------------------------
#     def _get_tolerance_minutes(self):
#         """Get tolerance time in minutes from system parameters"""
#         params = self.env['ir.config_parameter'].sudo()
#         tolerance_time = float(params.get_param('hr_attendance_custom_report.tolerance_time', 15))
#         return tolerance_time

#     # ---------------------------------------------
#     # Get Late Deduction Settings from Admin
#     # ---------------------------------------------
#     def _get_late_deduction_settings(self):
#         """Get late deduction settings from system parameters"""
#         params = self.env['ir.config_parameter'].sudo()
        
#         # Default: 3 lates = 1 day casual leave deduction
#         lates_per_deduction = int(params.get_param('hr_attendance_custom_report.lates_per_deduction', 3))
#         deduction_leave_type = params.get_param('hr_attendance_custom_report.deduction_leave_type', 'cl')
        
#         return {
#             'lates_per_deduction': lates_per_deduction,
#             'deduction_leave_type': deduction_leave_type,
#         }
        
#     # ---------------------------------------------
#     # Convert float hours to HH:MM format
#     # ---------------------------------------------
#     def _hours_to_hh_mm(self, hours_float):
#         """Convert float hours to HH:MM format string"""
#         if not hours_float:
#             return "00:00"
        
#         total_minutes = int(hours_float * 60)
#         hours = total_minutes // 60
#         minutes = total_minutes % 60
        
#         return f"{hours:02d}:{minutes:02d}"

#     # ---------------------------------------------
#     # Convert to Bangladesh Time (UTC+6) with 12-hour format
#     # ---------------------------------------------
#     def _to_bangladesh_time(self, dt):
#         if not dt:
#             return False
#         bd_tz = pytz.timezone('Asia/Dhaka')
#         if dt.tzinfo is None:
#             utc_tz = pytz.timezone('UTC')
#             dt = utc_tz.localize(dt)
#         return dt.astimezone(bd_tz)

#     # ---------------------------------------------
#     # Auto-detect Shift based on Check-in Time
#     # ---------------------------------------------
#     @api.depends('check_in')
#     def _compute_shift(self):
#         for rec in self:
#             if rec.check_in:
#                 bd_time = rec._to_bangladesh_time(rec.check_in)
#                 hour = bd_time.hour
#                 minute = bd_time.minute
                
#                 decimal_time = hour + (minute / 60.0)
                
#                 if 6.0 <= decimal_time < 12.0:
#                     rec.shift = 'morning'
#                 elif decimal_time >= 12.0:
#                     rec.shift = 'night'
#                 else:
#                     rec.shift = 'night'
#             else:
#                 rec.shift = 'morning'

#     # ---------------------------------------------
#     # Working / Late / Early Out / Extra Hours
#     # ---------------------------------------------
#     @api.depends('shift', 'check_in', 'check_out')
#     def _compute_extra(self):
#         for rec in self:
#             rec.working_hours = "00:00"
#             rec.extra_hours = "00:00"
#             rec.late_time = "00:00"
#             rec.early_out = "00:00"
#             rec.is_late = False

#             if not rec.check_in or not rec.check_out:
#                 continue

#             tolerance_minutes = rec._get_tolerance_minutes()
#             check_in_bd = rec._to_bangladesh_time(rec.check_in)
#             check_out_bd = rec._to_bangladesh_time(rec.check_out)

#             # Calculate working hours without any break deduction
#             time_difference = check_out_bd - check_in_bd
#             total_seconds = time_difference.total_seconds()
            
#             # No break time deduction - direct calculation
#             total_hours = total_seconds / 3600.0
#             hours = int(total_hours)
#             minutes = int((total_hours - hours) * 60)
            
#             rec.working_hours = f"{hours:02d}:{minutes:02d}"

#             # Office timings
#             if rec.shift == 'morning':
#                 office_start = time(9, 0, 0)
#                 office_end = time(18, 0, 0)
#             else:
#                 office_start = time(15, 0, 0)
#                 office_end = time(23, 0, 0)

#             office_start_dt = datetime.combine(check_in_bd.date(), office_start)
#             office_end_dt = datetime.combine(check_in_bd.date(), office_end)
#             bd_tz = pytz.timezone('Asia/Dhaka')
#             office_start_dt = bd_tz.localize(office_start_dt)
#             office_end_dt = bd_tz.localize(office_end_dt)

#             # Late Time Calculation
            
#             # modifiy by sohag
#             first_attendance = rec._get_first_attendance_of_day(
#                 rec.employee_id, check_in_bd.date()
#             )
#             # Default
#             rec.is_late = False
#             rec.late_time = "00:00"

#             # Late will be calculated ONLY for first check-in
#             if first_attendance and rec.id == first_attendance.id:
#                 tolerance_end = office_start_dt + timedelta(minutes=tolerance_minutes)

#                 if check_in_bd > tolerance_end:
#                     late_delta = check_in_bd - office_start_dt
#                     late_hours = late_delta.total_seconds() / 3600.0
#                     rec.late_time = self._hours_to_hh_mm(late_hours)
#                     rec.is_late = True

            
#             # tolerance_end = office_start_dt + timedelta(minutes=tolerance_minutes)
#             # if check_in_bd > tolerance_end:
#             #     late_delta = check_in_bd - office_start_dt
#             #     late_hours = late_delta.total_seconds() / 3600.0
#             #     rec.late_time = self._hours_to_hh_mm(late_hours)
#             #     rec.is_late = True

#             # Early Out Calculation
#             if check_out_bd < office_end_dt:
#                 early_delta = office_end_dt - check_out_bd
#                 early_hours = early_delta.total_seconds() / 3600.0
#                 rec.early_out = self._hours_to_hh_mm(early_hours)

#            # Extra Hours Calculation
#             if check_out_bd > office_end_dt:
#                 extra_delta = check_out_bd - office_end_dt
#                 extra_hours_float = extra_delta.total_seconds() / 3600.0
#                 rec.extra_hours = self._hours_to_hh_mm(extra_hours_float)

#     # ---------------------------------------------
#     # UPDATED: Late Deduction Calculation - Admin Controlled Leave Type
#     # ---------------------------------------------
#     @api.depends('is_late', 'check_in', 'employee_id')
#     def _compute_late_deduction(self):
#         for rec in self:
#             if not rec.employee_id or not rec.check_in:
#                 rec.late_count_monthly = 0
#                 rec.leave_deduction_days = 0.0
#                 rec.deducted_leave_type = ''
#                 continue

#             # Get current month start and end dates
#             check_in_bd = rec._to_bangladesh_time(rec.check_in)
#             month_start = check_in_bd.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
#             next_month = month_start + relativedelta(months=1)
#             month_end = next_month - timedelta(days=1)

#             # Count late days for this employee in current month
#             late_records = self.search([
#                 ('employee_id', '=', rec.employee_id.id),
#                 ('check_in', '>=', month_start),
#                 ('check_in', '<=', month_end),
#                 ('is_late', '=', True)
#             ])
            
            
#             # modifiy by sohag 
#             late_dates = set()
#             for att in late_records:
#                 bd_time = rec._to_bangladesh_time(att.check_in)
#                 late_dates.add(bd_time.date())

#             rec.late_count_monthly = len(late_dates)
            
            
#             # Get deduction settings from admin anwer 
#             deduction_settings = rec._get_late_deduction_settings()
#             lates_per_deduction = deduction_settings['lates_per_deduction']
#             deduction_leave_type = deduction_settings['deduction_leave_type']
            
#             # Calculate leave deduction based on admin settings
#             rec.leave_deduction_days = rec.late_count_monthly // lates_per_deduction
            
#             # Set deducted leave type properly based on admin settings
#             leave_type_mapping = {
#                 'cl': 'Casual Leave',
#                 'sl': 'Sick Leave', 
#                 'ml': 'Medical Leave',
#                 'el': 'Earned Leave',
#                 'lop': 'Loss of Pay'
#             }
#             rec.deducted_leave_type = leave_type_mapping.get(deduction_leave_type, '')
#         else:
#             rec.deducted_leave_type = '' 

#     # ---------------------------------------------
#     # COMPLETELY REWRITTEN: Daily Absent Calculation
#     # ---------------------------------------------
#     @api.depends('check_in', 'employee_id')
#     def _compute_absent(self):
#         """Calculate absent on daily basis - যদি কোনো specific date-এ attendance না থাকে"""
#         for rec in self:
#             if not rec.employee_id or not rec.check_in:
#                 rec.is_absent = False
#                 continue

#             # Get the current date from check_in
#             check_in_bd = rec._to_bangladesh_time(rec.check_in)
#             current_date = check_in_bd.date()
            
#             # Check if it's Friday (Offday)
#             if current_date.weekday() == 4:  # Friday = 4
#                 rec.is_absent = False  # Friday is offday, not absent
#                 continue
            
#             # Get ALL attendance records for this employee on this specific date
#             daily_attendances = self.search([
#                 ('employee_id', '=', rec.employee_id.id),
#                 ('check_in', '>=', datetime.combine(current_date, time(0, 0, 0))),
#                 ('check_in', '<', datetime.combine(current_date + timedelta(days=1), time(0, 0, 0)))
#             ])

#             # যদি এই date-এ কোনো attendance না থাকে (empty list)
#             if not daily_attendances:
#                 rec.is_absent = True
#             else:
#                 rec.is_absent = False

#     # ---------------------------------------------
#     # UPDATED: Status Badge Computation with Offday
#     # ---------------------------------------------
#     @api.depends('is_late', 'is_absent', 'check_in', 'check_out')
#     def _compute_status_badge(self):
#         for rec in self:
#             if not rec.check_in:
#                 rec.status_badge = '''
#                     <span style="
#                         background: #6c757d; 
#                         color: white; 
#                         padding: 4px 12px; 
#                         border-radius: 15px; 
#                         font-size: 12px; 
#                         font-weight: bold;
#                         display: inline-block;
#                     ">No Data</span>
#                 '''
#                 continue

#             # Check if it's Friday (Offday)
#             check_in_bd = rec._to_bangladesh_time(rec.check_in)
#             current_date = check_in_bd.date()
#             # Offday (Friday)
#             if current_date.weekday() == 4:
#                 # If check_in exists → treat like normal day (Late/Present)
#                 if rec.check_in:
#                     # Just DON'T continue → let normal status logic run
#                     pass
#                 else:
#                     # No attendance → Offday
#                     rec.status_badge = '''
#                         <span style="
#                             background: #17a2b8; 
#                             color: white; 
#                             padding: 4px 12px; 
#                             border-radius: 15px; 
#                             font-size: 12px; 
#                             font-weight: bold;
#                             display: inline-block;
#                         ">Offday</span>
#                     '''
#                     continue

#             # If check_out is not done yet, determine late based on check_in and tolerance
#             if not rec.check_out:
#                 tolerance_minutes = rec._get_tolerance_minutes()
#                 bd_time = rec._to_bangladesh_time(rec.check_in)

#                 # Office start time based on shift
#                 if rec.shift == 'morning':
#                     office_start = time(9, 0, 0)
#                 else:
#                     office_start = time(15, 0, 0)

#                 office_start_dt = datetime.combine(bd_time.date(), office_start)
#                 bd_tz = pytz.timezone('Asia/Dhaka')
#                 office_start_dt = bd_tz.localize(office_start_dt)
#                 tolerance_end = office_start_dt + timedelta(minutes=tolerance_minutes)

#                 if bd_time > tolerance_end:
#                     rec.status_badge = '''
#                         <span style="
#                             background: #dc3545; 
#                             color: white; 
#                             padding: 4px 12px; 
#                             border-radius: 15px; 
#                             font-size: 12px; 
#                             font-weight: bold;
#                             display: inline-block;
#                         ">Late</span>
#                     '''
#                     continue

#             # Default cases based on computed fields
#             if rec.is_absent:
#                 rec.status_badge = '''
#                     <span style="
#                         background: #fd7e14; 
#                         color: white; 
#                         padding: 4px 12px; 
#                         border-radius: 15px; 
#                         font-size: 12px; 
#                         font-weight: bold;
#                         display: inline-block;
#                     ">Absent</span>
#                 '''
            
#             elif rec._is_first_attendance_late():
#                 rec.status_badge = '''
#                     <span style="
#                         background: #dc3545; 
#                         color: white; 
#                         padding: 4px 12px; 
#                         border-radius: 15px; 
#                         font-size: 12px; 
#                         font-weight: bold;
#                         display: inline-block;
#                     ">Late</span>
#                 '''

#             else:
#                 rec.status_badge = '''
#                     <span style="
#                         background: #28a745; 
#                         color: white; 
#                         padding: 4px 12px; 
#                         border-radius: 15px; 
#                         font-size: 12px; 
#                         font-weight: bold;
#                         display: inline-block;
#                     ">Present</span>
#                 '''

#     # ---------------------------------------------
#     # Method to create absent records for missing dates
#     # ---------------------------------------------
#     def create_absent_records(self):
#         """Create absent records for dates with no attendance"""
#         # Get all employees
#         employees = self.env['hr.employee'].search([])
        
#         # Get current month dates
#         today = datetime.now()
#         month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
#         next_month = month_start + relativedelta(months=1)
#         month_end = next_month - timedelta(days=1)
        
#         for employee in employees:
#             # Get all attendance dates for this employee in current month
#             attendance_records = self.search([
#                 ('employee_id', '=', employee.id),
#                 ('check_in', '>=', month_start),
#                 ('check_in', '<=', month_end)
#             ])
            
#             # Get unique dates with attendance
#             attendance_dates = set()
#             for record in attendance_records:
#                 if record.check_in:
#                     bd_time = record._to_bangladesh_time(record.check_in)
#                     attendance_dates.add(bd_time.date())
            
#             # Find missing dates (excluding Fridays)
#             current_date = month_start.date()
#             while current_date <= month_end.date():
#                 # Skip Fridays (Offday)
#                 if current_date.weekday() != 4:  # Not Friday
#                     if current_date not in attendance_dates:
#                         # Create absent record for this missing date
#                         absent_check_in = datetime.combine(current_date, time(9, 0, 0))
#                         self.create({
#                             'employee_id': employee.id,
#                             'check_in': absent_check_in,
#                             'check_out': absent_check_in,  # Same as check_in for absent
#                             'is_absent': True,
#                         })
#                         print(f"Created absent record for {employee.name} on {current_date}")
                
#                 current_date += timedelta(days=1)
                
                
#     # modifiy by sohag
#     def _get_first_attendance_of_day(self, employee, date):
#         start = datetime.combine(date, time.min)
#         end = datetime.combine(date, time.max)

#         return self.search([
#             ('employee_id', '=', employee.id),
#             ('check_in', '>=', start),
#             ('check_in', '<=', end),
#         ], order='check_in asc', limit=1)
        
        
#     def _is_first_attendance_late(self):
#         self.ensure_one()

#         if not self.check_in:
#             return False

#         check_in_bd = self._to_bangladesh_time(self.check_in)
#         first_att = self._get_first_attendance_of_day(
#             self.employee_id, check_in_bd.date()
#         )

#         if not first_att or not first_att.check_in:
#             return False

#         office_start = time(9, 0, 0)
#         office_start_dt = datetime.combine(check_in_bd.date(), office_start)
#         bd_tz = pytz.timezone('Asia/Dhaka')
#         office_start_dt = bd_tz.localize(office_start_dt)

#         tolerance_end = office_start_dt + timedelta(
#             minutes=self._get_tolerance_minutes()
#         )

#         first_check_in_bd = self._to_bangladesh_time(first_att.check_in)

#         return first_check_in_bd > tolerance_end












from odoo import models, fields, api
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
import pytz

class AttendanceReport(models.Model):
    _inherit = 'hr.attendance'

    emp_code = fields.Char(related='employee_id.identification_id', store=True)
    badge_id = fields.Char(related='employee_id.barcode', string="Badge ID", store=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True)

    shift = fields.Many2one(
        'resource.calendar',
        string="Shift",
        compute="_compute_shift",
        store=True
    )

    working_hours = fields.Char(string="Working Hours", compute="_compute_extra", store=True)
    extra_hours = fields.Char(string="Extra Hours", compute="_compute_extra", store=True)
    late_time = fields.Char(string="Late Time", compute="_compute_extra", store=True)
    early_out = fields.Char(string="Early Out", compute="_compute_extra", store=True)

    is_absent = fields.Boolean(string="Absent", compute="_compute_absent", store=True)
    leave_type = fields.Selection([
        ('cl', 'Casual Leave'),
        ('sl', 'Sick Leave'),
        ('ml', 'Medical Leave'),
    ], string='Leave Type')

    is_late = fields.Boolean(string="Late", compute="_compute_extra", store=True)
    late_count_monthly = fields.Integer(string="Monthly Late Count", compute="_compute_late_deduction", store=True)
    leave_deduction_days = fields.Float(string="Leave Deduction Days", compute="_compute_late_deduction", store=True)
    deducted_leave_type = fields.Char(string="Deducted Leave Type", compute="_compute_late_deduction", store=True)
    status_badge = fields.Html(string="Status", compute="_compute_status_badge", sanitize=False)

    # Tolerance Time from Settings
    def _get_tolerance_minutes(self):
        params = self.env['ir.config_parameter'].sudo()
        return float(params.get_param('hr_attendance_custom_report.tolerance_time', 15))

    # Late Deduction Settings
    def _get_late_deduction_settings(self):
        params = self.env['ir.config_parameter'].sudo()
        lates_per_deduction = int(params.get_param('hr_attendance_custom_report.lates_per_deduction', 3))
        deduction_leave_type = params.get_param('hr_attendance_custom_report.deduction_leave_type', 'cl')
        return {
            'lates_per_deduction': lates_per_deduction,
            'deduction_leave_type': deduction_leave_type,
        }

    # Convert float hours to HH:MM
    def _hours_to_hh_mm(self, hours_float):
        if not hours_float:
            return "00:00"
        total_minutes = int(hours_float * 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"


    # Convert to Bangladesh Time (UTC+6)
    def _to_bangladesh_time(self, dt):
        if not dt:
            return False
        bd_tz = pytz.timezone('Asia/Dhaka')
        if dt.tzinfo is None:
            dt = pytz.timezone('UTC').localize(dt)
        return dt.astimezone(bd_tz)

    # Compute shift from employee's resource_calendar_id
    @api.depends('employee_id', 'check_in')
    def _compute_shift(self):
        for rec in self:
            rec.shift = rec.employee_id.resource_calendar_id or False

    # Get office start/end from shift (resource.calendar)
    def _get_office_hours_from_calendar(self, date):

        self.ensure_one()

        default_start = time(9, 0, 0)
        default_end = time(18, 0, 0)

        calendar = self.shift  
        if not calendar:
            calendar = self.employee_id.resource_calendar_id
        if not calendar:
            return default_start, default_end

        day_of_week = str(date.weekday())

        day_attendances = calendar.attendance_ids.filtered(
            lambda a: a.dayofweek == day_of_week
        )

        if not day_attendances:
            return default_start, default_end

        hour_from_min = min(day_attendances.mapped('hour_from'))
        hour_to_max = max(day_attendances.mapped('hour_to'))

        def float_to_time(f):
            h = int(f)
            m = int(round((f - h) * 60))
            return time(h, m, 0)

        return float_to_time(hour_from_min), float_to_time(hour_to_max)

    # Working / Late / Early Out / Extra Hours
    @api.depends('shift', 'check_in', 'check_out', 'employee_id')
    def _compute_extra(self):
        for rec in self:
            rec.working_hours = "00:00"
            rec.extra_hours = "00:00"
            rec.late_time = "00:00"
            rec.early_out = "00:00"
            rec.is_late = False

            if not rec.check_in or not rec.check_out:
                continue

            tolerance_minutes = rec._get_tolerance_minutes()
            check_in_bd = rec._to_bangladesh_time(rec.check_in)
            check_out_bd = rec._to_bangladesh_time(rec.check_out)

            # Working hours
            total_seconds = (check_out_bd - check_in_bd).total_seconds()
            total_hours = total_seconds / 3600.0
            rec.working_hours = f"{int(total_hours):02d}:{int((total_hours % 1) * 60):02d}"

            # Office hours from resource calendar
            office_start, office_end = rec._get_office_hours_from_calendar(check_in_bd.date())

            bd_tz = pytz.timezone('Asia/Dhaka')
            office_start_dt = bd_tz.localize(datetime.combine(check_in_bd.date(), office_start))
            office_end_dt = bd_tz.localize(datetime.combine(check_in_bd.date(), office_end))

            # Late 
            first_attendance = rec._get_first_attendance_of_day(rec.employee_id, check_in_bd.date())
            rec.is_late = False
            rec.late_time = "00:00"

            if first_attendance and rec.id == first_attendance.id:
                tolerance_end = office_start_dt + timedelta(minutes=tolerance_minutes)
                if check_in_bd > tolerance_end:
                    late_delta = check_in_bd - office_start_dt
                    rec.late_time = rec._hours_to_hh_mm(late_delta.total_seconds() / 3600.0)
                    rec.is_late = True

            # Early Out
            if check_out_bd < office_end_dt:
                early_delta = office_end_dt - check_out_bd
                rec.early_out = rec._hours_to_hh_mm(early_delta.total_seconds() / 3600.0)

            # Extra Hours
            if check_out_bd > office_end_dt:
                extra_delta = check_out_bd - office_end_dt
                rec.extra_hours = rec._hours_to_hh_mm(extra_delta.total_seconds() / 3600.0)

    # Late Deduction Calculation
    @api.depends('is_late', 'check_in', 'employee_id')
    def _compute_late_deduction(self):
        for rec in self:
            if not rec.employee_id or not rec.check_in:
                rec.late_count_monthly = 0
                rec.leave_deduction_days = 0.0
                rec.deducted_leave_type = ''
                continue

            check_in_bd = rec._to_bangladesh_time(rec.check_in)
            month_start = check_in_bd.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = month_start + relativedelta(months=1)
            month_end = next_month - timedelta(days=1)

            late_records = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('check_in', '>=', month_start),
                ('check_in', '<=', month_end),
                ('is_late', '=', True)
            ])

            late_dates = set()
            for att in late_records:
                bd_time = rec._to_bangladesh_time(att.check_in)
                late_dates.add(bd_time.date())

            rec.late_count_monthly = len(late_dates)

            deduction_settings = rec._get_late_deduction_settings()
            lates_per_deduction = deduction_settings['lates_per_deduction']
            deduction_leave_type = deduction_settings['deduction_leave_type']

            rec.leave_deduction_days = rec.late_count_monthly // lates_per_deduction

            leave_type_mapping = {
                'cl': 'Casual Leave',
                'sl': 'Sick Leave',
                'ml': 'Medical Leave',
                'el': 'Earned Leave',
                'lop': 'Loss of Pay'
            }
            rec.deducted_leave_type = leave_type_mapping.get(deduction_leave_type, '')

    # Daily Absent Calculation
    @api.depends('check_in', 'employee_id')
    def _compute_absent(self):
        for rec in self:
            if not rec.employee_id or not rec.check_in:
                rec.is_absent = False
                continue

            check_in_bd = rec._to_bangladesh_time(rec.check_in)
            current_date = check_in_bd.date()

            if current_date.weekday() == 4:  
                rec.is_absent = False
                continue

            daily_attendances = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('check_in', '>=', datetime.combine(current_date, time(0, 0, 0))),
                ('check_in', '<', datetime.combine(current_date + timedelta(days=1), time(0, 0, 0)))
            ])
            rec.is_absent = not bool(daily_attendances)

    # Status Badge
    @api.depends('is_late', 'is_absent', 'check_in', 'check_out', 'employee_id', 'shift')
    def _compute_status_badge(self):
        for rec in self:
            if not rec.check_in:
                rec.status_badge = rec._badge_html('#6c757d', 'No Data')
                continue

            check_in_bd = rec._to_bangladesh_time(rec.check_in)
            current_date = check_in_bd.date()

            if current_date.weekday() == 4 and not rec.check_in:
                rec.status_badge = rec._badge_html('#17a2b8', 'Offday')
                continue

            if not rec.check_out:
                tolerance_minutes = rec._get_tolerance_minutes()
                office_start, _ = rec._get_office_hours_from_calendar(current_date)
                bd_tz = pytz.timezone('Asia/Dhaka')
                office_start_dt = bd_tz.localize(datetime.combine(current_date, office_start))
                tolerance_end = office_start_dt + timedelta(minutes=tolerance_minutes)
                if check_in_bd > tolerance_end:
                    rec.status_badge = rec._badge_html('#fd7e14', 'Late')
                    continue

            if rec.is_absent:
                rec.status_badge = rec._badge_html('#dc3545', 'Absent')
            elif rec._is_first_attendance_late():
                rec.status_badge = rec._badge_html('#fd7e14', 'Late')
            else:
                rec.status_badge = rec._badge_html('#28a745', 'Present')

    def _badge_html(self, color, label):
        return f'''<span style="background:{color};color:white;padding:4px 12px;
            border-radius:15px;font-size:12px;font-weight:bold;
            display:inline-block;">{label}</span>'''

    # Helper Methods
    def _get_first_attendance_of_day(self, employee, date):
        start = datetime.combine(date, time.min)
        end = datetime.combine(date, time.max)
        return self.search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start),
            ('check_in', '<=', end),
        ], order='check_in asc', limit=1)

    def _is_first_attendance_late(self):
        self.ensure_one()
        if not self.check_in:
            return False

        check_in_bd = self._to_bangladesh_time(self.check_in)
        first_att = self._get_first_attendance_of_day(self.employee_id, check_in_bd.date())

        if not first_att or not first_att.check_in:
            return False

        office_start, _ = self._get_office_hours_from_calendar(check_in_bd.date())
        bd_tz = pytz.timezone('Asia/Dhaka')
        office_start_dt = bd_tz.localize(datetime.combine(check_in_bd.date(), office_start))
        tolerance_end = office_start_dt + timedelta(minutes=self._get_tolerance_minutes())

        first_check_in_bd = self._to_bangladesh_time(first_att.check_in)
        return first_check_in_bd > tolerance_end

    def create_absent_records(self):
        employees = self.env['hr.employee'].search([])
        today = datetime.now()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = month_start + relativedelta(months=1)
        month_end = next_month - timedelta(days=1)

        for employee in employees:
            attendance_records = self.search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', month_start),
                ('check_in', '<=', month_end)
            ])

            attendance_dates = set()
            for record in attendance_records:
                if record.check_in:
                    bd_time = record._to_bangladesh_time(record.check_in)
                    attendance_dates.add(bd_time.date())

            current_date = month_start.date()
            while current_date <= month_end.date():
                if current_date.weekday() != 4:
                    if current_date not in attendance_dates:
                        absent_check_in = datetime.combine(current_date, time(9, 0, 0))
                        self.create({
                            'employee_id': employee.id,
                            'check_in': absent_check_in,
                            'check_out': absent_check_in,
                            'is_absent': True,
                        })
                current_date += timedelta(days=1)