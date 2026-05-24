

from odoo import http
from odoo.http import AccessError, request
from odoo import fields
import logging
from datetime import datetime , date ,timedelta,time
import calendar
from dateutil.relativedelta import relativedelta
# from odoo.addons.portal.controllers.portal import CustomerPortal
# from odoo.addons.web.controllers.home import Home
from odoo.orm.models import UserError, ValidationError
from odoo.tools.pdf import errors
import base64
import pytz
from collections import defaultdict


_logger = logging.getLogger(__name__)


class PortalLoginController(http.Controller):
  


    @http.route('/my/employee-dashboard', type='http', auth='user', website=True , csrf=False, cache=False)
    def portal_dashboard(self, **kw):
    
        
        user = request.env.user
        employee = user.employee_id
        
        if not employee:
            return request.render('portal_login.portal_no_employee')

      
        
        today = date.today()
        today_str = datetime.today().strftime("%d %B, %Y, %A")  
        
        
        
        
        def safe_int(v, default):
            try:
                return int(v)
            except:
                return default
            

        def get_offday_weekdays(employee):
            """
            Returns a set of weekday numbers (0=Mon, 6=Sun) 
            that are offdays based on work schedule.
            A day is offday if ALL its slots are 'Break'.
            """
            offday_weekdays = set()
            
            calendar = employee.resource_calendar_id
            if not calendar:
                return {4} 
            
            # Group attendance lines by day_of_week
            day_slots = defaultdict(list)
            
            for line in calendar.attendance_ids:
                day_slots[int(line.dayofweek)].append(line.day_period)
            
          
            for weekday, periods in day_slots.items():
                non_break = [p for p in periods if p != 'break']
                if not non_break:
                    offday_weekdays.add(weekday)
            
           
            all_days = set(range(7))
            days_with_slots = set(day_slots.keys())
            offday_weekdays.update(all_days - days_with_slots)
            
            return offday_weekdays
        
        
    
        offday_weekdays = get_offday_weekdays(employee)
       
        # Month / Year Handling
        
        
        current = date.today()
        month_names = list(calendar.month_name)
        month_list = [{'number': i, 'name': calendar.month_name[i]} for i in range(1, 13)]
        year_list = list(range(today.year - 5, today.year + 6))
            
        month = safe_int(kw.get('month'), today.month)
        year = safe_int(kw.get('year'), today.year)
        
        total_days = calendar.monthrange(year, month)[1]
        cal = calendar.Calendar(firstweekday=6)  
        month_days = cal.monthdayscalendar(year, month)
        
        
        start_date = date(year, month, 1)
        end_date = date(year, month, total_days)
        
        
        # Attendance Dictionary
      
        attendance = {}   
        
        
        # Fetch attendance of selected month
      
        records = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', datetime.combine(start_date, datetime.min.time())),
            ('check_in', '<=', datetime.combine(end_date, datetime.max.time())),
        ])
        
        
        for rec in records:
            day = rec.check_in.day
            check_in_bd = rec._to_bangladesh_time(rec.check_in)
            weekday = check_in_bd.weekday()

            # # Determine office start based on shift
            # if rec.shift == 'morning':
            #     office_start = time(9, 0, 0)
            # else:
            #     office_start = time(15, 0, 0)
            
            # office_start_dt = datetime.combine(check_in_bd.date(), office_start)
            # office_start_dt = pytz.timezone('Asia/Dhaka').localize(office_start_dt)
            # tolerance_minutes = rec._get_tolerance_minutes()
            # tolerance_end = office_start_dt + timedelta(minutes=tolerance_minutes)

            # Live late check if check_out is None
            # is_late_now = False
            # if not rec.check_out and check_in_bd > tolerance_end:
            #     is_late_now = True

            # Status logic
            # if weekday == 4:
            #     status = "offday"
            # elif rec.is_absent:
            #     status = "absent"
            # elif rec._is_first_attendance_late():
            #     status = "late"
            # else:
            #     status = "present"

            # attendance[day] = status

            if weekday in offday_weekdays:  
                status = "offday"
            elif rec.is_absent:
                status = "absent"
            elif rec._is_first_attendance_late():
                status = "late"
            else:
                status = "present"

            attendance[day] = status


        # Fill absent/offday for remaining days
        # loop_day = start_date
        # while loop_day <= end_date:
        #     d = loop_day.day
        #     if d not in attendance:
        #         attendance[d] = 'offday' if loop_day.weekday() == 4 else 'absent'
        #     loop_day += timedelta(days=1)

        loop_day = start_date
        while loop_day <= end_date:
            d = loop_day.day
            if d not in attendance:
                attendance[d] = 'offday' if loop_day.weekday() in offday_weekdays else 'absent'
            loop_day += timedelta(days=1)
                    
            
       
        # Attendance summary
       
        present_count = sum(s == 'present' for s in attendance.values())
        late_count = sum(s == 'late' for s in attendance.values())
        absent_count = sum(s == 'absent' for s in attendance.values())
        offday_count = sum(s == 'offday' for s in attendance.values())
        movement_count = sum(s == 'movement' for s in attendance.values())
        
        
        
        # leave count
        leave_count = request.env['hr.leave'].sudo().search_count([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('request_date_from', '>=', start_date),
            ('request_date_to', '<=', end_date),
        ])
      
        if employee:
            leave_count = request.env['hr.leave'].sudo().search_count([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('request_date_from', '>=', start_date),
                ('request_date_to', '<=', end_date),
            ])
        else:
            leave_count = 0
            
    #    leave records of selected month
        leaves = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', end_date),
            ('request_date_to', '>=', start_date),
        ])

        # Add leave days to attendance dictionary
        for leave in leaves:
            leave_start = max(leave.request_date_from, start_date)
            leave_end = min(leave.request_date_to, end_date)
            loop_day = leave_start
            while loop_day <= leave_end:
                attendance[loop_day.day] = 'leave'
                loop_day += timedelta(days=1)
        
        
        # Re-evaluate attendance for days marked as 'leave' or 'offday' 
        for rec in records:
            attended_day = rec.check_in.day
            weekday = rec.check_in.astimezone(pytz.timezone('Asia/Dhaka')).weekday()

           
            if attendance.get(attended_day) == 'leave':

               
                if rec._is_first_attendance_late():
                    attendance[attended_day] = 'late'
                else:
                    attendance[attended_day] = 'present'

                continue
            

            if attendance.get(attended_day) == 'offday' and weekday in offday_weekdays:
                if rec._is_first_attendance_late():
                    attendance[attended_day] = 'late'
                else:
                    attendance[attended_day] = 'present'

                    
            # if attendance.get(attended_day) == 'offday' and weekday == 4:

            #     # Use rec.is_late from your computed field
            #     if getattr(rec, 'is_late', False):
            #         attendance[attended_day] = 'late'
            #     else:
            #         attendance[attended_day] = 'present'

                
                
        joining_date = employee.contract_date_start or False

        confirmation_date = employee.confirmation_date or False
        
        
        length_of_service_str = ""
        
        if joining_date:
            today_date = date.today()
            delta = relativedelta(today_date, joining_date)
            
           
            years = delta.years
            months = delta.months
            days = delta.days

           
            parts = []
            if years > 0:
                parts.append(f"{years} year{'s' if years > 1 else ''}")
            if months > 0:
                parts.append(f"{months} month{'s' if months > 1 else ''}")
            if days > 0:
                parts.append(f"{days} day{'s' if days > 1 else ''}")
            
            length_of_service_str = " ".join(parts)

                
        leave_balances = []
        manager_data = []
        attendance_logs = []
        

        allocations = request.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate')
        ])
        
        for alloc in allocations:
            taken_days = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', alloc.holiday_status_id.id),
                ('state', '=', 'validate'),
            ]).mapped('number_of_days')

            taken = sum(taken_days) if taken_days else 0
            remaining = alloc.number_of_days - taken

            leave_balances.append({
                'type': alloc.holiday_status_id.name,
                'taken': taken,
                'remaining': remaining,
                'status': 'Active' if remaining > 0 else 'Exhausted',
            })
            
        if employee.parent_id:
            manager_data.append({
                'name': employee.parent_id.name,
                'role': 'Supervisor',
                'icon': 'text-primary'
            })

        if employee.coach_id:
            manager_data.append({
                'name': employee.coach_id.name,
                'role': 'Dotted Supervisor',
                'icon': 'text-secondary'
            })

        if hasattr(employee, 'line_manager_id') and employee.line_manager_id:
            manager_data.append({
                'name': employee.line_manager_id.name,
                'role': 'Line Manager',
                'icon': 'text-secondary'
            })
                
        # Attendance Log & Today Working Period
        # attendance_logs = []
        # today_working_period = ""
        # active_session = False
        # running_seconds = 0

        # tz = pytz.timezone('Asia/Dhaka')
        # now_bd = datetime.now(tz)

        
        # logs = request.env['hr.attendance'].sudo().search(
        #     [('employee_id', '=', employee.id)],
        #     order='check_in desc',
        #     limit=10
        # )

        # for log in logs:
        #     check_in = log.check_in
        #     check_out = log.check_out

        #     if not check_in:
        #         continue

        #     # Convert to BD Time
        #     check_in_bd = check_in.astimezone(tz)
        #     check_out_bd = check_out.astimezone(tz) if check_out else None

           
        #     # if log.shift == 'morning':
        #     #     office_start = time(9, 0, 0)
        #     # else:
        #     #     office_start = time(15, 0, 0)
        #     # office_start_dt = tz.localize(datetime.combine(check_in_bd.date(), office_start))
        #     # tolerance_minutes = log._get_tolerance_minutes()
        #     # tolerance_end = office_start_dt + timedelta(minutes=tolerance_minutes)

          
        #     # late_status = log.is_late or (not check_out_bd and check_in_bd > tolerance_end)
        #     late_status = log._is_first_attendance_late()


           
        #     check_in_time = check_in_bd.strftime("%I:%M %p")
        #     if check_out_bd:
        #         check_out_time = check_out_bd.strftime("%I:%M %p")
        #     else:
        #         check_out_time = "—"  

           
           
        #     if check_out_bd:
        #         delta = check_out_bd - check_in_bd
        #         total_sec = int(delta.total_seconds())
        #         hours = total_sec // 3600
        #         minutes = (total_sec % 3600) // 60
        #         total_duration = f"{hours} hr {minutes} min"
        #     else:
               
        #         delta = now_bd - check_in_bd
        #         total_sec = int(delta.total_seconds())
        #         hours = total_sec // 3600
        #         minutes = (total_sec % 3600) // 60
        #         total_duration = f"{hours} hr {minutes} min (Running)"

        #     attendance_logs.append({
        #         'date': check_in_bd.strftime("%d %b, %Y"),
        #         'check_in': check_in_time,
        #         'check_out': check_out_time,
        #         'duration': total_duration,
        #         'late': late_status,
        #     })

       
        # today_start = tz.localize(datetime.combine(today, datetime.min.time()))
        # today_end = tz.localize(datetime.combine(today, datetime.max.time()))

        # today_records = request.env['hr.attendance'].sudo().search([
        #     ('employee_id', '=', employee.id),
        #     ('check_in', '>=', today_start),
        #     ('check_in', '<=', today_end),
        # ], order="check_in asc")

        # total_seconds = 0
        # active_seconds = 0

        # for rec in today_records:
        #     check_in_bd = rec.check_in.astimezone(tz)
        #     if rec.check_out:
        #         check_out_bd = rec.check_out.astimezone(tz)
        #         total_seconds += int((check_out_bd - check_in_bd).total_seconds())
        #     else:
                
        #         active_session = True
        #         active_seconds += int((now_bd - check_in_bd).total_seconds())

        
        # running_seconds = total_seconds + active_seconds
        # hours = running_seconds // 3600
        # minutes = (running_seconds % 3600) // 60
        # today_working_period = f"{hours} hr {minutes} min"

        attendance_logs = []
        today_working_period = ""
        active_session = False
        running_seconds = 0

        tz = pytz.timezone('Asia/Dhaka')
        now_bd = datetime.now(tz)

        logs = request.env['hr.attendance'].sudo().search(
            [('employee_id', '=', employee.id)],
            order='check_in desc',
            limit=10
        )

        MAX_WORK_SECONDS = 12 * 3600  # 12 hours limit

        for log in logs:
            check_in = log.check_in
            check_out = log.check_out

            if not check_in:
                continue

            # Convert to BD Time
            check_in_bd = check_in.astimezone(tz)
            check_out_bd = check_out.astimezone(tz) if check_out else None

            late_status = log._is_first_attendance_late()

            check_in_time = check_in_bd.strftime("%I:%M %p")
            if check_out_bd:
                check_out_time = check_out_bd.strftime("%I:%M %p")
            else:
                check_out_time = "—"

            # Calculate duration
            if check_out_bd:
                delta = check_out_bd - check_in_bd
            else:
                delta = now_bd - check_in_bd

            total_sec = int(delta.total_seconds())

           
            if total_sec > MAX_WORK_SECONDS:
                total_sec = MAX_WORK_SECONDS

            hours = total_sec // 3600
            minutes = (total_sec % 3600) // 60

            if check_out_bd:
                total_duration = f"{hours} hr {minutes} min"
            else:
                total_duration = f"{hours} hr {minutes} min (Running)"

            attendance_logs.append({
                'date': check_in_bd.strftime("%d %b, %Y"),
                'check_in': check_in_time,
                'check_out': check_out_time,
                'duration': total_duration,
                'late': late_status,
            })

        today_start = tz.localize(datetime.combine(today, datetime.min.time()))
        today_end = tz.localize(datetime.combine(today, datetime.max.time()))

        today_records = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', today_start),
            ('check_in', '<=', today_end),
        ], order="check_in asc")

        total_seconds = 0
        active_seconds = 0

        for rec in today_records:
            check_in_bd = rec.check_in.astimezone(tz)

            if rec.check_out:
                check_out_bd = rec.check_out.astimezone(tz)
                sec = int((check_out_bd - check_in_bd).total_seconds())
            else:
                active_session = True
                sec = int((now_bd - check_in_bd).total_seconds())

            if sec > MAX_WORK_SECONDS:
                sec = MAX_WORK_SECONDS

            total_seconds += sec

        running_seconds = total_seconds
        hours = running_seconds // 3600
        minutes = (running_seconds % 3600) // 60
        today_working_period = f"{hours} hr {minutes} min"

                
        
        # Fetch announcements 
        Ann = request.env['hr.announcement'].sudo()

        general = Ann.search([
            ('is_announcement', '=', True),
            ('state', '=', 'approved'),
            ('date_start', '<=', fields.Date.today()),
        ])

        emp = Ann.search([
            ('employee_ids', 'in', employee.id) if employee else [],
            ('state', '=', 'approved'),
            ('date_start', '<=', fields.Date.today()),
        ])

        dep = Ann.search([
            ('department_ids', 'in', employee.department_id.id) if employee else [],
            ('state', '=', 'approved'),
            ('date_start', '<=', fields.Date.today()),
        ])

        job = Ann.search([
            ('position_ids', 'in', employee.job_id.id) if employee else [],
            ('state', '=', 'approved'),
            ('date_start', '<=', fields.Date.today()),
        ])

        announcements = (general | emp | dep | job).sorted(key=lambda r: r.date_start, reverse=True)

                
        # company policies code by sohag
        Policy = request.env['company.policy'].sudo()

        general_policies = Policy.search([
            ('is_general', '=', True),
            ('date_start', '<=', fields.Date.today()),
            ('active', '=', True),
        ])

        employee_policies = Policy.search([
            ('employee_ids', 'in', employee.id) if employee else [],
            ('policy_type', '=', 'employee'),
            ('date_start', '<=', fields.Date.today()),
            ('active', '=', True),
        ])

        department_policies = Policy.search([
            ('department_ids', 'in', employee.department_id.id) if employee else [],
            ('policy_type', '=', 'department'),
            ('date_start', '<=', fields.Date.today()),
            ('active', '=', True),
        ])

        job_policies = Policy.search([
            ('position_ids', 'in', employee.job_id.id) if employee else [],
            ('policy_type', '=', 'job'),
            ('date_start', '<=', fields.Date.today()),
            ('active', '=', True),
        ])

        policies = (general_policies | employee_policies | department_policies | job_policies).sorted(
            key=lambda r: r.date_start, reverse=True
        )

            
        # my applications works 
        
        leaves = request.env['hr.leave'].sudo().search(
            [('employee_id', '=', employee.id)],
            order='request_date_from desc',
            limit=5  
        )

        return request.render('portal_login.portal_dashboard', {
            'user': user,
            'month': month,
            'year': year,
            'month_name': calendar.month_name[month],
            'month_days': month_days,
            'total_days': total_days,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'offday_count': offday_count,
            'attendance': attendance,
            'leave_balances': leave_balances,
            'manager_data': manager_data,
            'attendance_logs': attendance_logs,
            'joining_date': joining_date,
            'confirmation_date': confirmation_date,
            'length_of_service': length_of_service_str,
            'month_names': month_names,
            'month_list': month_list,
            'year_list': year_list,
            "today": today_str,
            'leave_count':leave_count,
            'movement_count':movement_count,
            'today_working_period': today_working_period,
            'active_session': active_session,
            'running_seconds': running_seconds,
            'announcements': announcements,
            'policies': policies,
            'leaves': leaves,
            'policies': policies,
        })
        

# Announcement Attachment  code only knows by sohag 
class AnnouncementPortalController(http.Controller):
    
    @http.route('/portal/announcement/attachment/<int:attachment_id>', 
                type='http', auth='public')
    def portal_announcement_attachment(self, attachment_id, **kw):

        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)

        
        if not attachment.exists():
            return request.not_found()

        if attachment.res_model != "hr.announcement":
            return request.not_found()

        if not attachment.datas:
            return request.not_found()

        
        filecontent = base64.b64decode(attachment.datas)

        mimetype = attachment.mimetype or 'application/octet-stream'

        return request.make_response(
            filecontent,
            headers=[
                ('Content-Type', mimetype),
                ('Content-Disposition',
                 'inline; filename="%s"' % attachment.name)
            ]
        )

# class PortalRedirect(Home):
    
#     """
#     Supervisor Information Page
#     ---------------------------
#     User er supervisor, coach, line manager details eikhane show korbe.
#     """

#     def _login_redirect(self, uid, redirect=None):
#         """Redirect portal users to /my and employees to backend."""
#         user = request.env['res.users'].sudo().browse(uid)
      
#         if user.has_group("base.group_user"):
#             return super()._login_redirect(uid, redirect)

#         if user.has_group("base.group_portal"):
            
#             return "/my/employee-dashboard"
        
#         return super()._login_redirect(uid, redirect)


# class MasterPortalRedirect(CustomerPortal):
    
#     @http.route(['/my', '/my/home'], type='http', auth="user", website=True)
#     def home(self, **kw):
        
#         _logger.info(f"MASTER REDIRECT: Portal home override for user {request.env.user.id}")
        
#         return request.redirect('/my/employee-dashboard')
    




# mhadu bhai code here 

class PortalLeaveController(http.Controller):

    @http.route('/my/leave/apply', type='http', auth='user', website=True)
    def apply_leave(self, **kw):
        """Render leave application form"""
        try:
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not employee:
                return request.render('portal_login.portal_no_employee', {
                    'error': 'No employee record found for your account. Please contact HR.',
                    'page_name': 'apply_leave',
                })

            team_members = request.env['hr.employee'].sudo().search([
                ('portal_team_leader_id', '=', employee.id),
                ('active', '=', True)
            ])
            is_team_leader = len(team_members) > 0

            pending_team_count = 0
            if is_team_leader:
                pending_team_count = request.env['hr.leave'].sudo().search_count([
                    ('employee_id.portal_team_leader_id', '=', employee.id),
                    ('state', '=', 'team_leader_approval')
                ])
           

            
            allocations = request.env['hr.leave.allocation'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('holiday_status_id.active', '=', True),
            ])

            allocated_leave_type_ids = allocations.mapped('holiday_status_id').ids
            leave_types = request.env['hr.leave.type'].sudo().browse(allocated_leave_type_ids).sorted('name')

            
            employees = request.env['hr.employee'].sudo().search([
                ('id', '!=', employee.id),
                ('active', '=', True)
            ], order='name')

           
            leave_balances = {}
            for leave_type in leave_types:
                allocation = allocations.filtered(lambda a: a.holiday_status_id.id == leave_type.id)
                if allocation:
                    total = sum(allocation.mapped('number_of_days'))
                    used = sum(allocation.mapped('leaves_taken'))
                    leave_balances[leave_type.id] = {
                        'total': total,
                        'used': used,
                        'remaining': total - used
                    }
                else:
                    leave_balances[leave_type.id] = {
                        'total': 0,
                        'used': 0,
                        'remaining': 0
                    }

            return request.render('portal_login.portal_apply_leave', {
                'leave_types': leave_types,
                'employees': employees,
                'allocations': allocations,
                'employee': employee,
                'leave_balances': leave_balances,
                'error': kw.get('error'),
                'success': kw.get('success'),
                'page_name': 'apply_leave',
                'is_team_leader': is_team_leader,  
                'pending_team_count': pending_team_count,  
            })

        except Exception as e:
            _logger.error(f"Error in apply_leave: {str(e)}", exc_info=True)
            return request.render('portal_login.portal_error', {
                'error': f'An unexpected error occurred: {str(e)}',
                'page_name': 'apply_leave',
            })

    @http.route('/my/leave/submit', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def submit_leave(self, **post):
        """Handle leave submission with comprehensive validation"""
        try:
            user = request.env.user

            
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)

            if not employee:
                _logger.error(f"No employee record found for user {user.login}")
                return request.redirect('/my/leave/apply?error=No employee record found. Please contact HR.')

           
            date_from = post.get('date_from')
            date_to = post.get('date_to')
            leave_type_id = post.get('leave_type')
            reason = post.get('reason', '').strip()

            if not date_from or not date_to:
                return request.redirect('/my/leave/apply?error=Please provide both start and end dates')

            if not leave_type_id:
                return request.redirect('/my/leave/apply?error=Please select a leave type')

            if not reason:
                return request.redirect('/my/leave/apply?error=Please provide a reason for leave')

           
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError as e:
                _logger.error(f"Date parsing error: {str(e)}")
                return request.redirect('/my/leave/apply?error=Invalid date format')

           
            if date_from_obj > date_to_obj:
                return request.redirect('/my/leave/apply?error=Start date cannot be after end date')

            today = datetime.now().date()
            if date_from_obj < today:
                return request.redirect('/my/leave/apply?error=Cannot apply for past dates')

            
            try:
                leave_type = request.env['hr.leave.type'].sudo().browse(int(leave_type_id))
                if not leave_type.exists():
                    _logger.error(f"Leave type {leave_type_id} not found")
                    return request.redirect('/my/leave/apply?error=Invalid leave type selected')
            except ValueError as e:
                _logger.error(f"Invalid leave_type_id: {leave_type_id}, error: {str(e)}")
                return request.redirect('/my/leave/apply?error=Invalid leave type')

        
            overlapping = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', 'not in', ['refuse', 'cancel']),
                ('request_date_from', '<=', date_to),
                ('request_date_to', '>=', date_from),
            ])

            if overlapping:
                return request.redirect('/my/leave/apply?error=You already have a leave request for overlapping dates')

            
            if leave_type.requires_allocation != 'no':
                allocation = request.env['hr.leave.allocation'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('holiday_status_id', '=', leave_type.id),
                    ('state', '=', 'validate')
                ], limit=1)

                if allocation:
                    remaining = allocation.number_of_days - allocation.leaves_taken
                    requested_days = (date_to_obj - date_from_obj).days + 1

                    if remaining < requested_days:
                        return request.redirect(
                            f'/my/leave/apply?error=Insufficient leave balance. Available: {remaining} days')
                else:
                    return request.redirect('/my/leave/apply?error=No leave allocation found for this leave type')

            
            initial_state = 'team_leader_approval' if employee.portal_team_leader_id else 'confirm'

           
            vals = {
                'employee_id': employee.id,
                'holiday_status_id': int(leave_type_id),
                'request_date_from': date_from,
                'request_date_to': date_to,
                'name': reason,
                'state': initial_state,  
            }

            _logger.info(f"Creating leave with state: {initial_state} (Team leader: {employee.portal_team_leader_id.name if employee.portal_team_leader_id else 'None'})")

            
            delegate_id = post.get('delegate_employee_id')
            if delegate_id and delegate_id.strip() and delegate_id != 'None' and delegate_id != '':
                try:
                    delegate_id_int = int(delegate_id)
                    if delegate_id_int == employee.id:
                        return request.redirect('/my/leave/apply?error=You cannot delegate to yourself')

                    delegate_employee = request.env['hr.employee'].sudo().browse(delegate_id_int)
                    if delegate_employee.exists():
                        vals['delegate_employee_id'] = delegate_id_int
                        _logger.info(f"Delegation set to employee ID: {delegate_id_int}")
                    else:
                        _logger.warning(f"Invalid delegate employee ID: {delegate_id_int}")
                except ValueError as e:
                    _logger.warning(f"Invalid delegate_id value: {delegate_id}, error: {str(e)}")

            
            try:
                leave = request.env['hr.leave'].sudo().create(vals)
                _logger.info(f"✓ Leave request created successfully: ID {leave.id}, State: {leave.state}, Team Leader Required: {bool(employee.portal_team_leader_id)}")
            except Exception as e:
                _logger.error(f"Error creating leave record: {str(e)}", exc_info=True)
                return request.redirect('/my/leave/apply?error=Failed to create leave request. Please try again.')

            if not leave:
                _logger.error("Leave creation returned False/None")
                return request.redirect('/my/leave/apply?error=Failed to create leave request')

           
            if 'attachment' in request.httprequest.files:
                attachment_file = request.httprequest.files['attachment']
                if attachment_file and attachment_file.filename:
                    try:
                       
                        attachment_file.seek(0, 2)
                        file_size = attachment_file.tell()
                        attachment_file.seek(0)

                        if file_size > 5 * 1024 * 1024:
                            leave.sudo().unlink()
                            return request.redirect('/my/leave/apply?error=File size exceeds 5MB limit')

                       
                        allowed_extensions = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png']
                        file_ext = attachment_file.filename.split('.')[-1].lower()

                        if file_ext not in allowed_extensions:
                            leave.sudo().unlink()
                            return request.redirect(
                                '/my/leave/apply?error=Invalid file type. Allowed: PDF, DOC, DOCX, JPG, JPEG, PNG')

                        attachment_data = base64.b64encode(attachment_file.read())
                        request.env['ir.attachment'].sudo().create({
                            'name': attachment_file.filename,
                            'type': 'binary',
                            'datas': attachment_data,
                            'res_model': 'hr.leave',
                            'res_id': leave.id,
                            'mimetype': attachment_file.content_type,
                        })
                    except Exception as e:
                        _logger.error(f"Error uploading attachment: {str(e)}", exc_info=True)

            
            success_message = 'Leave request submitted successfully'
            if initial_state == 'team_leader_approval':
                success_message += ' and is pending team leader approval'
            else:
                success_message += ' and is pending HR approval'

            return request.redirect(f'/my/leave/history?success={success_message}')

        except Exception as e:
            _logger.error(f"Unexpected error in submit_leave: {str(e)}", exc_info=True)
            return request.redirect('/my/leave/apply?error=An unexpected error occurred. Please try again or contact support.')

    @http.route('/my/leave/history', type='http', auth='user', website=True)
    def leave_history(self, **kw):
        """Display leave history with filters and pagination"""
        try:
            user = request.env.user

            # Get employee
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)

            if not employee:
                return request.render('portal_login.portal_no_employee', {
                    'error': 'No employee record found',
                    'page_name': 'leave_history',
                })

          
            team_members = request.env['hr.employee'].sudo().search([
                ('portal_team_leader_id', '=', employee.id),
                ('active', '=', True)
            ])
            is_team_leader = len(team_members) > 0

            # Count pending team approvals
            pending_team_count = 0
            if is_team_leader:
                pending_team_count = request.env['hr.leave'].sudo().search_count([
                    ('employee_id.portal_team_leader_id', '=', employee.id),
                    ('state', '=', 'team_leader_approval')
                ])
            


            
            domain = [('employee_id', '=', employee.id)]

           
            status_filter = kw.get('status')
            if status_filter:
                domain.append(('state', '=', status_filter))

            leaves = request.env['hr.leave'].sudo().search(
                domain,
                order='request_date_from desc, id desc'
            )

           
            all_leaves = request.env['hr.leave'].sudo().search([('employee_id', '=', employee.id)])
            stats = {
                'total': len(all_leaves),
                'pending': len(all_leaves.filtered(lambda l: l.state in ['confirm', 'team_leader_approval'])),
                'approved': len(all_leaves.filtered(lambda l: l.state == 'validate')),
                'refused': len(all_leaves.filtered(lambda l: l.state == 'refuse')),
                'draft': len(all_leaves.filtered(lambda l: l.state == 'draft')),
            }

            
            allocations = request.env['hr.leave.allocation'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate')
            ])

            return request.render('portal_login.portal_leave_history', {
                'leaves': leaves,
                'stats': stats,
                'allocations': allocations,
                'status_filter': status_filter,
                'success': kw.get('success'),
                'error': kw.get('error'),
                'employee': employee,
                'page_name': 'leave_history',
                'is_team_leader': is_team_leader,  
                'pending_team_count': pending_team_count,  
            })

        except Exception as e:
            _logger.error(f"Error in leave_history: {str(e)}", exc_info=True)
            return request.render('portal_login.portal_error', {
                'error': f'An unexpected error occurred: {str(e)}',
                'page_name': 'leave_history',
            })

    @http.route('/my/leave/cancel/<int:leave_id>', type='http', auth='user', website=True, csrf=True)
    def cancel_leave(self, leave_id, **kw):
        """Cancel a pending leave request"""
        try:
            leave = request.env['hr.leave'].sudo().browse(leave_id)

            if not leave.exists():
                return request.redirect('/my/leave/history?error=Leave request not found')

            if leave.employee_id.user_id.id != request.env.user.id:
                return request.redirect('/my/leave/history?error=Unauthorized access')

            # Allow cancellation of draft, pending, or team_leader_approval
            if leave.state not in ['draft', 'confirm', 'team_leader_approval']:
                return request.redirect(
                    '/my/leave/history?error=Cannot cancel this leave request. Current status does not allow cancellation')

            leave.sudo().action_refuse()
            _logger.info(f"Leave request {leave_id} cancelled by user {request.env.user.name}")

            return request.redirect('/my/leave/history?success=Leave request cancelled successfully')

        except Exception as e:
            _logger.error(f"Error in cancel_leave: {str(e)}", exc_info=True)
            return request.redirect(f'/my/leave/history?error=Error cancelling leave request')

    @http.route('/my/leave/team-approvals', type='http', auth='user', website=True)
    def team_leader_approvals(self, **kw):
        """Display leaves pending team leader approval - ONLY for actual team leaders"""
        try:
            user = request.env.user

            # Get employee
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)

            if not employee:
                return request.render('portal_login.portal_no_employee', {
                    'error': 'No employee record found',
                    'page_name': 'team_approvals',
                })

           
            team_members = request.env['hr.employee'].sudo().search([
                ('portal_team_leader_id', '=', employee.id),
                ('active', '=', True)
            ])

            if not team_members:
                return request.render('portal_login.portal_not_team_leader_page', {
                    'page_name': 'team_approvals',
                })

            _logger.info(f"✓ Team leader {employee.name} accessing approvals page. Team size: {len(team_members)}")

            
            pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id.portal_team_leader_id', '=', employee.id),
                ('state', '=', 'team_leader_approval')
            ], order='request_date_from desc')

           
            all_team_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id.portal_team_leader_id', '=', employee.id)
            ], order='request_date_from desc')

            stats = {
                'pending': len(pending_leaves),
                'total': len(all_team_leaves),
                'approved': len(all_team_leaves.filtered(lambda l: l.team_leader_approved)),
                'team_members': len(team_members),
            }

            _logger.info(f"Team leader stats: {stats}")

            return request.render('portal_login.portal_team_leader_approvals', {
                'pending_leaves': pending_leaves,
                'all_leaves': all_team_leaves,
                'team_members': team_members,
                'stats': stats,
                'success': kw.get('success'),
                'error': kw.get('error'),
                'employee': employee,
                'page_name': 'team_approvals',
            })

        except Exception as e:
            _logger.error(f"Error in team_leader_approvals: {str(e)}", exc_info=True)
            return request.render('portal_login.portal_error', {
                'error': f'An unexpected error occurred: {str(e)}',
                'page_name': 'team_approvals',
            })

    @http.route('/my/leave/team-leader/approve/<int:leave_id>', type='http', auth='user', website=True, csrf=True)
    def team_leader_approve_leave(self, leave_id, **kw):
        """Team leader approves a leave request"""
        try:
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not employee:
                return request.redirect('/my/leave/team-approvals?error=No employee record found')

            leave = request.env['hr.leave'].sudo().browse(leave_id)

            if not leave.exists():
                return request.redirect('/my/leave/team-approvals?error=Leave request not found')

            
            if not leave.employee_id.portal_team_leader_id:
                return request.redirect('/my/leave/team-approvals?error=This leave has no team leader assigned')

            if leave.employee_id.portal_team_leader_id.id != employee.id:
                _logger.warning(f"Unauthorized: {employee.name} tried to approve {leave.employee_id.name}'s leave")
                return request.redirect('/my/leave/team-approvals?error=You are not authorized to approve this request')

            if leave.state != 'team_leader_approval':
                return request.redirect('/my/leave/team-approvals?error=This leave is not pending your approval')

           
            leave.action_team_leader_approve()
            _logger.info(f"✓ Team leader {employee.name} approved leave {leave_id}")

            return request.redirect('/my/leave/team-approvals?success=Leave request approved successfully')

        except Exception as e:
            _logger.error(f"Error in team_leader_approve_leave: {str(e)}", exc_info=True)
            return request.redirect(f'/my/leave/team-approvals?error=Error approving leave request')

    @http.route('/my/leave/team-leader/refuse/<int:leave_id>', type='http', auth='user', website=True, csrf=True)
    def team_leader_refuse_leave(self, leave_id, **kw):
        """Team leader refuses a leave request"""
        try:
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not employee:
                return request.redirect('/my/leave/team-approvals?error=No employee record found')

            leave = request.env['hr.leave'].sudo().browse(leave_id)

            if not leave.exists():
                return request.redirect('/my/leave/team-approvals?error=Leave request not found')

            
            if not leave.employee_id.portal_team_leader_id:
                return request.redirect('/my/leave/team-approvals?error=This leave has no team leader assigned')

            if leave.employee_id.portal_team_leader_id.id != employee.id:
                _logger.warning(f"Unauthorized: {employee.name} tried to refuse {leave.employee_id.name}'s leave")
                return request.redirect('/my/leave/team-approvals?error=You are not authorized to refuse this request')

            if leave.state != 'team_leader_approval':
                return request.redirect('/my/leave/team-approvals?error=This leave is not pending your approval')

         
            try:
                leave.action_team_leader_refuse()
                
            except (UserError, ValidationError, AccessError) as business_error:
                
                _logger.warning(f"Business warning but leave was refused: {business_error}")
                pass  
                _logger.info(f"✓ Team leader {employee.name} refused leave {leave_id}")

            return request.redirect('/my/leave/team-approvals?success=Leave request refused')

        except Exception as e:
            _logger.error(f"Error in team_leader_refuse_leave: {str(e)}", exc_info=True)
            return request.redirect(f'/my/leave/team-approvals?error=Error refusing leave request')

    @http.route('/my/leave/balance/<int:leave_type_id>', type='json', auth='user')
    def get_leave_balance(self, leave_type_id):
        """Get remaining leave balance for a specific leave type"""
        try:
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not employee:
                return {'error': 'No employee record found'}

            allocation = request.env['hr.leave.allocation'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', int(leave_type_id)),
                ('state', '=', 'validate')
            ])

            if allocation:
                total = sum(allocation.mapped('number_of_days'))
                used = sum(allocation.mapped('leaves_taken'))
                return {
                    'success': True,
                    'total': total,
                    'used': used,
                    'remaining': total - used
                }

            return {
                'success': True,
                'total': 0,
                'used': 0,
                'remaining': 0,
                'message': 'No allocation found'
            }

        except Exception as e:
            _logger.error(f"Error in get_leave_balance: {str(e)}", exc_info=True)
            return {'error': str(e)}
        
        
        
#payslip work here sohag code


# class PortalPayslipController(http.Controller):

#     @http.route(['/my/payslips'], type='http', auth='user', website=True)
#     def portal_payslip_list(self, **kwargs):
#         user = request.env.user

#         employee = request.env['hr.employee'].sudo().search([
#             ('user_id', '=', user.id)
#         ], limit=1)

#         # print(f"[DEBUG] Employee fetched: {employee.name if employee else 'No employee found'}")
        
#         payslips = request.env['hr.payslip'].sudo().search([
#             ('employee_id', '=', employee.id)
#         ], order="id desc")

#         # print(f"[DEBUG] Payslips fetched: {len(payslips)}")
        
#         # for sl in payslips:
#         #     print(f"[DEBUG] Payslip: {sl.name}, From: {sl.date_from}, To: {sl.date_to}, State: {sl.state}")

#         return request.render("portal_login.portal_payslip_list", {
#             'employee': employee,
#             'payslips': payslips,
#         })


        
#     @http.route('/my/payslip/print/<int:payslip_id>', type='http', auth='user', website=True)
#     def portal_payslip_print(self, payslip_id, **kw):
#         payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
#         if not payslip.exists():
#             return request.not_found()

#         report_action = request.env.ref('hr_payroll.action_report_payslip')
#         pdf_content, _ = report_action._render(report_action.report_name, [payslip.id])

#         headers = [
#             ('Content-Type', 'application/pdf'),
#             ('Content-Length', str(len(pdf_content))),
#             ('Content-Disposition', f'attachment; filename="payslip_{payslip.name}.pdf"'),
#         ]
#         return request.make_response(pdf_content, headers=headers)
    


# class PortalPayslipController(http.Controller):

   
#     @http.route(['/my/payslips'], type='http', auth='user', website=True)
#     def portal_payslip_list(self, **kwargs):

#         user = request.env.user

#         # Logged in portal user's employee
#         employee = request.env['hr.employee'].sudo().search([
#             ('user_id', '=', user.id)
#         ], limit=1)

#         payslips = request.env['hr.payslip'].sudo().search([
#             ('employee_id', '=', employee.id)
#         ], order="id desc")

#         return request.render("portal_login.portal_payslip_list", {
#             'employee': employee,
#             'payslips': payslips,
#         })

   
#     @http.route('/my/payslip/print/<int:payslip_id>', type='http', auth='user', website=True)
#     def portal_payslip_print(self, payslip_id, **kw):

#         user = request.env.user

       
#         employee = request.env['hr.employee'].sudo().search([
#             ('user_id', '=', user.id)
#         ], limit=1)

#         if not employee:
#             return request.not_found()

        
#         payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
#         if not payslip.exists():
#             return request.not_found()

        
#         if payslip.employee_id.id != employee.id:
#             return request.not_found()

       
#         report_action = request.env.ref(
#             'hr_payroll.action_report_payslip'
#         ).sudo()

#         pdf_content, _ = report_action._render(
#             report_action.report_name,
#             [payslip.id]
#         )

#         headers = [
#             ('Content-Type', 'application/pdf'),
#             ('Content-Length', str(len(pdf_content))),
#             ('Content-Disposition',
#              f'attachment; filename="payslip_{payslip.name}.pdf"'),
#         ]

#         return request.make_response(pdf_content, headers=headers)


class PortalEmployeeProfileController(http.Controller):

    @http.route(['/my/profile'], type='http', auth='user', website=True)
    def portal_employee_profile(self, **kwargs):
        user = request.env.user

        # Fetch employee record
        employee = (
            request.env['hr.employee']
            .sudo()
            .search([('user_id', '=', user.id)], limit=1)
        )

        if not employee:
            return request.redirect('/')
        

        # _logger.info("Birthday: %s", employee.birthday)
        # _logger.info("Place of Birth: %s", employee.place_of_birth)
        # _logger.info("Identification No: %s", employee.identification_id)
        # _logger.info("Passport No: %s", employee.passport_id) 
        # _logger.info("Disabled: %s", employee.disabled)
     
       
       

        # Render template with full employee context
        return request.render("portal_login.portal_employee_profile", {
            'employee': employee,
          
        }) 

    @http.route(['/my/profile/update'], type='http', auth='user', methods=['POST'], website=True ,  csrf=True)
    def portal_employee_profile_update(self, **kwargs):
        user = request.env.user

        employee = (
            request.env['hr.employee']
            .sudo()
            .search([('user_id', '=', user.id)], limit=1)
        )
        
        
        if employee:

            vals = {
                'mobile_phone': kwargs.get('mobile_phone'),
                'work_email': kwargs.get('work_email'),
                'private_email': kwargs.get('private_email'),
                'private_phone': kwargs.get('private_phone'),
                'emergency_contact': kwargs.get('emergency_contact'),
                'emergency_phone': kwargs.get('emergency_phone'),
                'marital': kwargs.get('marital'),
                'children': int(kwargs.get('children')) if kwargs.get('children') else 0,
                'certificate': kwargs.get('certificate'),
                'study_field': kwargs.get('study_field'),
                'passport_id': kwargs.get('passport_id'),

               
                'private_street': kwargs.get('private_street'),
                'private_street2': kwargs.get('private_street2'),
                'private_city': kwargs.get('private_city'),
                'private_zip': kwargs.get('private_zip'),
                'private_state_id': kwargs.get('private_state_id'),
                'private_country_id': kwargs.get('private_country_id'),
            }
            
            file = request.httprequest.files.get('profile_image')
            if file:
                image_data = file.read()
                if image_data:
                    vals['image_1920'] = base64.b64encode(image_data)

            employee.sudo().write(vals)
            
        return request.redirect('/my/profile')
    
    
    

# class PortalAttendance(http.Controller):

#     @http.route('/portal/attendance/check_in', auth='user')
#     def portal_check_in(self):
#         employee = request.env.user.employee_id
#          # Permission check
         
#         if not employee or not employee.allow_manual_attendance:
#             request.session['portal_status'] = ("danger", "You are not allowed to mark attendance.")
#             return request.redirect('/my')

#         # Auto check in
#         request.env['hr.attendance'].sudo().create({
#             'employee_id': employee.id,
#             'check_in': fields.Datetime.now(),
#         })
#         request.session['portal_status'] = ("success", "You have successfully Checked In.")
#         return request.redirect('/my')

#     @http.route('/portal/attendance/check_out', auth='user')
#     def portal_check_out(self):
#         employee = request.env.user.employee_id
        
        
#         if not employee or not employee.allow_manual_attendance:
#             request.session['portal_status'] = ("danger", "You are not allowed to mark attendance.")
#             return request.redirect('/my')

#         # Last open attendance record
#         attendance = request.env['hr.attendance'].sudo().search([
#             ('employee_id', '=', employee.id),
#             ('check_out', '=', False)
#         ], limit=1, order='check_in desc')

#         if attendance:
#             attendance.sudo().write({
#                 'check_out': fields.Datetime.now()
#             })
#             request.session['portal_status'] = ("success", "You have successfully Checked Out.")
#         else:
#             request.session['portal_status'] = ("danger", "No active check-in found!")


#         return request.redirect('/my')



# class PortalAttendance(http.Controller):

#     @http.route('/portal/attendance/check_in', auth='user', website=True)
#     def portal_check_in(self, location=None):
#         employee = request.env.user.employee_id

#         if not employee or not employee.allow_manual_attendance:
#             request.session['portal_status'] = ("danger", "You are not allowed to mark attendance.")
#             return request.redirect('/my')

#         request.env['hr.attendance'].sudo().create({
#             'employee_id': employee.id,
#             'check_in': fields.Datetime.now(),
#             'in_location': location,
#         })

#         request.session['portal_status'] = ("success", "You have successfully Checked In.")
#         return request.redirect('/my')

#     @http.route('/portal/attendance/check_out', auth='user', website=True)
#     def portal_check_out(self, location=None):
#         employee = request.env.user.employee_id

#         if not employee or not employee.allow_manual_attendance:
#             request.session['portal_status'] = ("danger", "You are not allowed to mark attendance.")
#             return request.redirect('/my')

#         attendance = request.env['hr.attendance'].sudo().search([
#             ('employee_id', '=', employee.id),
#             ('check_out', '=', False)
#         ], limit=1, order='check_in desc')

#         if attendance:
#             attendance.write({
#                 'check_out': fields.Datetime.now(),
#                 'out_location': location,
#             })
#             request.session['portal_status'] = ("success", "You have successfully Checked Out.")
#         else:
#             request.session['portal_status'] = ("danger", "No active check-in found!")

#         return request.redirect('/my')


# class PortalAttendance(http.Controller):

#     def _get_address_from_latlon(self, lat, lon):
#         if not lat or not lon:
#             return False

#         url = "https://nominatim.openstreetmap.org/reverse"
#         params = {
#             "lat": lat,
#             "lon": lon,
#             "format": "json"
#         }
#         headers = {
#             "User-Agent": "Odoo19-Attendance"
#         }

#         try:
#             res = request.get(url, params=params, headers=headers, timeout=5)
#             if res.status_code == 200:
#                 return res.json().get("display_name")
#         except Exception:
#             pass

#         return False

#     @http.route('/portal/attendance/check_in', auth='user', website=True)
#     def portal_check_in(self, lat=None, lon=None):
#         employee = request.env.user.employee_id

#         if not employee or not employee.allow_manual_attendance:
#             request.session['portal_status'] = ("danger", "You are not allowed.")
#             return request.redirect('/my')

#         address = self._get_address_from_latlon(lat, lon)

#         request.env['hr.attendance'].sudo().create({
#             'employee_id': employee.id,
#             'check_in': fields.Datetime.now(),
#             'in_location': address or f"{lat},{lon}",
#         })

#         request.session['portal_status'] = ("success", "Checked In successfully.")
#         return request.redirect('/my/employee-dashboard')

#     @http.route('/portal/attendance/check_out', auth='user', website=True)
#     def portal_check_out(self, lat=None, lon=None):
#         employee = request.env.user.employee_id

#         attendance = request.env['hr.attendance'].sudo().search([
#             ('employee_id', '=', employee.id),
#             ('check_out', '=', False)
#         ], limit=1)

#         address = self._get_address_from_latlon(lat, lon)

#         if attendance:
#             attendance.write({
#                 'check_out': fields.Datetime.now(),
#                 'out_location': address or f"{lat},{lon}",
#             })
#             request.session['portal_status'] = ("success", "Checked Out successfully.")

#         return request.redirect('/my/employee-dashboard')



from odoo.http import request
import requests


class PortalAttendance(http.Controller):

    def _reverse_geocode(self, lat, lon):
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return False

        if not lat or not lon:
            return False

        url = "https://nominatim.openstreetmap.org/reverse"

        try:
            response = requests.get(
                url,
                params={
                    "format": "json",
                    "lat": lat,
                    "lon": lon,
                },
                headers={
                    "User-Agent": "Odoo19-Portal-Attendance"
                },
                timeout=5
            )
            response.raise_for_status()

            data = response.json()
            return data.get("display_name")

        except requests.RequestException:
            return False


    @http.route('/portal/attendance/check_in', auth='user', website=True)
    def portal_check_in(self, lat=None, lon=None):

        employee = request.env.user.employee_id

        if not employee or not employee.allow_manual_attendance:
            request.session['portal_status'] = ("danger", "You are not allowed.")
            return request.redirect('/my')

        address = self._reverse_geocode(lat, lon)

        request.env['hr.attendance'].sudo().create({
            'employee_id': employee.id,
            'check_in': fields.Datetime.now(),
            'in_latitude': float(lat) if lat else False,
            'in_longitude': float(lon) if lon else False,
            'in_location': address or f"{lat},{lon}",
        })

        request.session['portal_status'] = ("success", "Checked In successfully.")
        return request.redirect('/my/employee-dashboard')

    @http.route('/portal/attendance/check_out', auth='user', website=True)
    def portal_check_out(self, lat=None, lon=None):

        employee = request.env.user.employee_id

        attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)

        if not attendance:
            request.session['portal_status'] = ("danger", "No active attendance found.")
            return request.redirect('/my/employee-dashboard')

        address = self._reverse_geocode(lat, lon)

        attendance.write({
            'check_out': fields.Datetime.now(),
            'out_latitude': float(lat) if lat else False,
            'out_longitude': float(lon) if lon else False,
            'out_location': address or f"{lat},{lon}",
        })

        request.session['portal_status'] = ("success", "Checked Out successfully.")
        return request.redirect('/my/employee-dashboard')
    
    
class PortalExpenses(http.Controller):

    
    @http.route('/my/expenses', auth='user', website=True)
    def portal_expense_form(self, **kw):
        employee = request.env.user.employee_id
        if not employee:
            return request.redirect('/my')

        products = request.env['product.product'].sudo().search([
            ('can_be_expensed', '=', True)
        ])

        managers = request.env['hr.employee'].sudo().search([])

        return request.render('portal_login.portal_expense_form', {
            'employee': employee,
            'products': products,
            'managers': managers,
            'today': fields.Date.today(),
        })

    # Expense submit
    @http.route('/my/expenses/submit', auth='user', type='http', website=True, csrf=False)
    def portal_expense_submit(self, **post):
        employee = request.env.user.employee_id
        if not employee:
            return request.redirect('/my')

        request.env['hr.expense'].sudo().create({
            'name': post.get('description'),
            'product_id': int(post.get('product_id')),
            'total_amount_currency': float(post.get('amount')),
            'employee_id': employee.id,
            'payment_mode': post.get('paid_by'),
            'date': post.get('expense_date'),
            'manager_id': post.get('manager')
        })

        request.session['portal_status'] = (
            "success",
            "Expense submitted successfully."
        )

        return request.redirect('/my')



# aysha apu code here 

# ─────────────────────────────────────────────────────────────────────────────
# PORTAL RESIGN CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────
class PortalResignController(http.Controller):

    # ── Helper ──────────────────────────────────────────────────────
    def _get_employee_or_redirect(self):
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.user.id)], limit=1
        )
        return employee

    # ── Apply for Resign (GET) ──────────────────────────────────────
    @http.route('/my/resign/apply', type='http', auth='user', website=True)
    def resign_apply(self, **kw):
        employee = self._get_employee_or_redirect()
        if not employee:
            return request.render('portal_login.portal_no_employee', {
                'error': 'No employee record found. Please contact HR.',
                'page_name': 'resign_apply',
            })

        # Check if there's already an active request
        active_resign = request.env['hr.resign'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['submitted', 'hr_review', 'approved']),
        ], limit=1)

        # All resignation history
        resign_history = request.env['hr.resign'].sudo().search([
            ('employee_id', '=', employee.id),
        ], order='request_date desc')

        # Team leader info for navigation badge
        team_members = request.env['hr.employee'].sudo().search([
            ('portal_team_leader_id', '=', employee.id), ('active', '=', True)
        ])
        is_team_leader = len(team_members) > 0
        pending_team_count = 0
        if is_team_leader:
            pending_team_count = request.env['hr.leave'].sudo().search_count([
                ('employee_id.portal_team_leader_id', '=', employee.id),
                ('state', '=', 'team_leader_approval'),
            ])

        return request.render('portal_login.portal_resign_apply', {
            'employee': employee,
            'active_resign': active_resign,
            'resign_history': resign_history,
            'error': kw.get('error'),
            'success': kw.get('success'),
            'page_name': 'resign_apply',
            'is_team_leader': is_team_leader,
            'pending_team_count': pending_team_count,
        })

    # ── Submit Resign (POST) ────────────────────────────────────────
    @http.route('/my/resign/submit', type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def resign_submit(self, **post):
        employee = self._get_employee_or_redirect()
        if not employee:
            return request.redirect('/my/resign/apply?error=No employee record found.')

        # Duplicate check
        active = request.env['hr.resign'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['submitted', 'hr_review', 'approved']),
        ], limit=1)
        if active:
            return request.redirect(
                '/my/resign/apply?error=You already have an active resignation request (Ref: %s).' % active.name
            )

        # Validate inputs
        reason = (post.get('reason') or '').strip()
        last_working_date = post.get('last_working_date')
        notice_period = post.get('notice_period_days', '30')
        additional_notes = (post.get('additional_notes') or '').strip()
        pdf_template = post.get('pdf_template', 'new_opportunity')

        if not reason:
            return request.redirect('/my/resign/apply?error=Please provide a reason for resignation.')
        if not last_working_date:
            return request.redirect('/my/resign/apply?error=Please specify your last working date.')

        try:
            from datetime import date as dt_date
            lwd = datetime.strptime(last_working_date, '%Y-%m-%d').date()
            if lwd <= dt_date.today():
                return request.redirect(
                    '/my/resign/apply?error=Last working date must be in the future.')
        except ValueError:
            return request.redirect('/my/resign/apply?error=Invalid date format for last working date.')

        try:
            notice_period = int(notice_period)
        except (ValueError, TypeError):
            notice_period = 30

        vals = {
            'employee_id': employee.id,
            'reason': reason,
            'last_working_date': last_working_date,
            'notice_period_days': notice_period,
            'additional_notes': additional_notes,
            'pdf_template': pdf_template,
            'state': 'submitted',
        }

        try:
            resign = request.env['hr.resign'].sudo().create(vals)
            _logger.info(f"Resignation {resign.name} submitted by {request.env.user.name}")
        except Exception as e:
            _logger.error(f"Error creating resignation: {e}", exc_info=True)
            return request.redirect('/my/resign/apply?error=Failed to submit resignation. Please try again.')

        return request.redirect(
            f'/my/resign/status/{resign.id}?success=Resignation submitted successfully! Reference: {resign.name}'
        )

    # ── Status Page ─────────────────────────────────────────────────
    @http.route('/my/resign/status/<int:resign_id>', type='http', auth='user', website=True)
    def resign_status(self, resign_id, **kw):
        employee = self._get_employee_or_redirect()
        if not employee:
            return request.render('portal_login.portal_no_employee', {})

        resign = request.env['hr.resign'].sudo().browse(resign_id)
        if not resign.exists() or resign.employee_id.id != employee.id:
            return request.redirect('/my/resign/apply?error=Resignation request not found.')

        team_members = request.env['hr.employee'].sudo().search([
            ('portal_team_leader_id', '=', employee.id), ('active', '=', True)
        ])
        is_team_leader = len(team_members) > 0
        pending_team_count = 0
        if is_team_leader:
            pending_team_count = request.env['hr.leave'].sudo().search_count([
                ('employee_id.portal_team_leader_id', '=', employee.id),
                ('state', '=', 'team_leader_approval'),
            ])

        return request.render('portal_login.portal_resign_status', {
            'resign': resign,
            'employee': employee,
            'success': kw.get('success'),
            'error': kw.get('error'),
            'page_name': 'resign_apply',
            'is_team_leader': is_team_leader,
            'pending_team_count': pending_team_count,
        })

    # ── Cancel Resign ────────────────────────────────────────────────
    @http.route('/my/resign/cancel/<int:resign_id>', type='http', auth='user',
                website=True, csrf=True)
    def resign_cancel(self, resign_id, **kw):
        employee = self._get_employee_or_redirect()
        if not employee:
            return request.redirect('/my/resign/apply?error=No employee record found.')

        resign = request.env['hr.resign'].sudo().browse(resign_id)
        if not resign.exists() or resign.employee_id.id != employee.id:
            return request.redirect('/my/resign/apply?error=Resignation request not found.')

        if resign.state == 'approved':
            return request.redirect(
                f'/my/resign/status/{resign_id}?error=Approved resignations cannot be cancelled. Contact HR.'
            )

        resign.sudo().write({'state': 'cancelled'})
        _logger.info(f"Resignation {resign.name} cancelled by {request.env.user.name}")
        return request.redirect('/my/resign/apply?success=Resignation request cancelled successfully.')

    # ── PDF Download ─────────────────────────────────────────────────
    @http.route('/my/resign/pdf/<int:resign_id>', type='http', auth='user', website=True)
    def resign_pdf(self, resign_id, **kw):
        employee = self._get_employee_or_redirect()
        if not employee:
            return request.not_found()

        resign = request.env['hr.resign'].sudo().browse(resign_id)
        if not resign.exists() or resign.employee_id.id != employee.id:
            return request.not_found()

        # Map template key → QWeb report name directly (bypasses stale DB records)
        template_map = {
            'new_opportunity': 'portal_login.report_resign_new_opportunity_doc',
            'advance_notice':  'portal_login.report_resign_advance_notice_doc',
            'not_good_fit':    'portal_login.report_resign_not_good_fit_doc',
            # Legacy fallbacks — old records saved before the upgrade
            'formal':          'portal_login.report_resign_new_opportunity_doc',
            'simple':          'portal_login.report_resign_advance_notice_doc',
            'acknowledgement': 'portal_login.report_resign_not_good_fit_doc',
        }
        report_name = template_map.get(
            resign.pdf_template,
            'portal_login.report_resign_new_opportunity_doc'
        )
        report_sudo = request.env['ir.actions.report'].sudo()
        pdf_content, _ = report_sudo._render_qweb_pdf(report_name, [resign.id])

        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Length', str(len(pdf_content))),
                ('Content-Disposition',
                 f'attachment; filename="resignation_{resign.name}.pdf"'),
            ]
        )


# ─────────────────────────────────────────────────────────────────────────────
# PORTAL HR RESIGN APPROVAL CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────
class PortalResignApprovalController(http.Controller):

    def _check_hr_user(self):
        """Return True if current user is HR Officer or Manager"""
        return (
            request.env.user.has_group('hr.group_hr_user') or
            request.env.user.has_group('hr.group_hr_manager')
        )

    # ── HR Approval List ────────────────────────────────────────────
    @http.route('/my/resign/approvals', type='http', auth='user', website=True)
    def resign_approvals(self, **kw):
        if not self._check_hr_user():
            return request.render('portal_login.portal_access_denied', {
                'message': 'You do not have permission to access this page.'
            })

        status_filter = kw.get('status', 'submitted')

        domain = []
        if status_filter and status_filter != 'all':
            domain = [('state', '=', status_filter)]

        resignations = request.env['hr.resign'].sudo().search(
            domain, order='request_date desc'
        )

        # Stats
        all_resigns = request.env['hr.resign'].sudo().search([])
        stats = {
            'submitted': len(all_resigns.filtered(lambda r: r.state == 'submitted')),
            'hr_review': len(all_resigns.filtered(lambda r: r.state == 'hr_review')),
            'approved':  len(all_resigns.filtered(lambda r: r.state == 'approved')),
            'rejected':  len(all_resigns.filtered(lambda r: r.state == 'rejected')),
            'total':     len(all_resigns),
        }

        # Team leader info for nav badge
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.user.id)], limit=1
        )
        is_team_leader = False
        pending_team_count = 0
        if employee:
            team_members = request.env['hr.employee'].sudo().search([
                ('portal_team_leader_id', '=', employee.id), ('active', '=', True)
            ])
            is_team_leader = len(team_members) > 0
            if is_team_leader:
                pending_team_count = request.env['hr.leave'].sudo().search_count([
                    ('employee_id.portal_team_leader_id', '=', employee.id),
                    ('state', '=', 'team_leader_approval'),
                ])

        return request.render('portal_login.portal_resign_approvals', {
            'resignations': resignations,
            'stats': stats,
            'status_filter': status_filter,
            'success': kw.get('success'),
            'error': kw.get('error'),
            'page_name': 'resign_approvals',
            'is_team_leader': is_team_leader,
            'pending_team_count': pending_team_count,
        })

    # ── HR Approve ──────────────────────────────────────────────────
    @http.route('/my/resign/hr/approve/<int:resign_id>', type='http',
                auth='user', website=True, csrf=True)
    def hr_approve_resign(self, resign_id, **kw):
        if not self._check_hr_user():
            return request.redirect('/my/resign/approvals?error=Access denied.')

        resign = request.env['hr.resign'].sudo().browse(resign_id)
        if not resign.exists():
            return request.redirect('/my/resign/approvals?error=Resignation not found.')

        if resign.state not in ['submitted', 'hr_review']:
            return request.redirect(
                '/my/resign/approvals?error=This resignation cannot be approved in its current state.'
            )

        try:
            resign.sudo().write({
                'state': 'approved',
                'approved_by': request.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            # Auto-archive the employee
            if resign.employee_id and resign.employee_id.active:
                resign.employee_id.sudo().write({'active': False})
                _logger.info(
                    f"Employee {resign.employee_id.name} archived via portal "
                    f"by HR {request.env.user.name}"
                )
            resign.sudo().message_post(
                body=f"✅ Resignation approved via portal by HR <b>{request.env.user.name}</b>. "
                     f"Employee has been automatically archived.",
                message_type='notification',
            )
            return request.redirect(
                f'/my/resign/approvals?success=Resignation of {resign.employee_id.name} '
                f'approved and employee archived successfully.'
            )
        except Exception as e:
            _logger.error(f"Error approving resignation {resign_id}: {e}", exc_info=True)
            return request.redirect(f'/my/resign/approvals?error=Error approving: {str(e)}')

    # ── HR Reject ───────────────────────────────────────────────────
    @http.route('/my/resign/hr/reject/<int:resign_id>', type='http',
                auth='user', website=True, csrf=True, methods=['POST'])
    def hr_reject_resign(self, resign_id, **kw):
        if not self._check_hr_user():
            return request.redirect('/my/resign/approvals?error=Access denied.')

        resign = request.env['hr.resign'].sudo().browse(resign_id)
        if not resign.exists():
            return request.redirect('/my/resign/approvals?error=Resignation not found.')

        rejection_reason = (kw.get('rejection_reason') or '').strip()
        if not rejection_reason:
            return request.redirect(
                '/my/resign/approvals?error=Please provide a rejection reason.'
            )

        try:
            resign.sudo().write({
                'state': 'rejected',
                'rejection_reason': rejection_reason,
            })
            resign.sudo().message_post(
                body=f"❌ Resignation rejected by HR <b>{request.env.user.name}</b>. "
                     f"Reason: {rejection_reason}",
                message_type='notification',
            )
            return request.redirect(
                f'/my/resign/approvals?success=Resignation of {resign.employee_id.name} rejected.'
            )
        except Exception as e:
            _logger.error(f"Error rejecting resignation {resign_id}: {e}", exc_info=True)
            return request.redirect(f'/my/resign/approvals?error=Error rejecting: {str(e)}')
