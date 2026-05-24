from dateutil.utils import today

from odoo import http
from odoo.http import request
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class HrAttendanceDashboardController(http.Controller):

    #  Helper 

    def _dept_domain(self, dept_id):
        if dept_id and str(dept_id) != 'all':
            try:
                return [('department_id', '=', int(dept_id))]
            except (TypeError, ValueError):
                pass
        return []

    def _to_date(self, val):
        if not val:
            return None
        try:
            return val.date() if hasattr(val, 'date') else val
        except Exception:
            return None
        

    def _get_years(self, emp, today):
        
        val = getattr(emp, 'contract_date_start', None)
        if val:
            try:
                d = self._to_date(val)
                if d:
                    return (today - d).days / 365.0
            except Exception:
                pass
        

        for fname in ('joining_date', 'contract_date', 'first_contract_date', 'create_date'):
            val = getattr(emp, fname, None)
            if val:
                try:
                    d = self._to_date(val)
                    if d:
                        return (today - d).days / 365.0
                except Exception:
                    pass
        return 0

    # def _get_years(self, emp, today):
    #     for fname in ('joining_date', 'contract_date', 'first_contract_date', 'create_date'):
    #         val = getattr(emp, fname, None)
    #         if val:
    #             try:
    #                 d = self._to_date(val)
    #                 if d:
    #                     return (today - d).days / 365.0
    #             except Exception:
    #                 pass
    #     return 0

    #Route 1: Departments dropdown

    @http.route('/hr/dashboard/departments', type='json', auth='user', methods=['POST'], csrf=False)
    def get_departments(self, **kwargs):
        try:
            depts = request.env['hr.department'].sudo().search([], order='name asc')
            return [{'id': d.id, 'name': d.name} for d in depts]
        except Exception as e:
            _logger.error("get_departments: %s", e)
            return []

    #Route 2: KPI card data

    @http.route('/hr/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, dept_id=None, selected_date=None, company_id=None, **kwargs):
        try:
            env   = request.env
            today = date.today()
            if selected_date:
                try:
                    today = datetime.strptime(selected_date, '%Y-%m-%d').date()
                except Exception:
                    pass

            month_start = today.replace(day=1)
            month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)

            company_domain = []

            if company_id and str(company_id) != 'all':
                try:
                    company_domain = [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass

            emp_domain = self._dept_domain(dept_id) + company_domain + [('active', '=', True)]

            # emp_domain = self._dept_domain(dept_id) + [('active', '=', True)]
            employees  = env['hr.employee'].sudo().search(emp_domain)
            total_emp  = len(employees)
            emp_ids    = employees.ids or [0]

            wfo_count = sum(1 for e in employees if (getattr(e, 'work_location_type', '') or '') != 'home')
            wfh_count = total_emp - wfo_count

            working_days = sum(
                1 for i in range((today - month_start).days + 1)
                if (month_start + timedelta(days=i)).weekday() < 5
            ) or 1

            # Attendance
            try:
                att_records = env['hr.attendance'].sudo().search([
                    ('employee_id', 'in', emp_ids),
                    ('check_in', '>=', datetime.combine(month_start, datetime.min.time())),
                    ('check_in', '<=', datetime.combine(today, datetime.max.time())),
                ])
            except Exception:
                att_records = []

            actual_att     = len(att_records)
            expected_att   = total_emp * working_days
            attendance_pct = round((actual_att / expected_att) * 100, 1) if expected_att else 0
            absence_pct    = round(max(0.0, 100.0 - attendance_pct), 1)

            # Leaves
            try:
                all_leaves = env['hr.leave'].sudo().search([
                    ('employee_id', 'in', emp_ids),
                    ('date_from',   '<=', str(month_end)),
                    ('date_to',     '>=', str(month_start)),
                ])
            except Exception:
                all_leaves = []

            validated       = [l for l in all_leaves if l.state == 'validate']
            validated_count = len(validated)
            total_leave_req = len(all_leaves)
            pending         = [l for l in all_leaves if l.state in ('draft', 'confirm', 'validate1')]
            refused         = [l for l in all_leaves if l.state == 'refuse']
            leave_appr_pct  = round((validated_count / total_leave_req) * 100, 1) if total_leave_req else 0

            # Unscheduled
            unscheduled_count = 0
            for lv in all_leaves:
                try:
                    df_d = self._to_date(lv.date_from)
                    cd_d = self._to_date(lv.create_date)
                    if df_d and cd_d and (df_d - cd_d).days <= 1:
                        unscheduled_count += 1
                except Exception:
                    pass

            # Sick vs Casual
            sick_count = casual_count = 0
            try:
                sick_ids   = env['hr.leave.type'].sudo().search([('name', 'ilike', 'sick')]).ids
                casual_ids = env['hr.leave.type'].sudo().search([('name', 'ilike', 'casual')]).ids
                for lv in validated:
                    lt_id = lv.holiday_status_id.id
                    if lt_id in sick_ids:      sick_count   += 1
                    elif lt_id in casual_ids:  casual_count += 1
            except Exception:
                pass

            # Leave type dist
            lt_map = {}
            for lv in validated:
                try:
                    n = lv.holiday_status_id.name or 'Other'
                    lt_map[n] = lt_map.get(n, 0) + 1
                except Exception:
                    pass
            leave_type_dist = [
                {'name': n, 'count': c,
                 'pct': round((c / validated_count) * 100, 1) if validated_count else 0}
                for n, c in sorted(lt_map.items(), key=lambda x: -x[1])
            ]

            # Exp groups
            exp_groups = {'0-1': 0, '1-3': 0, '3-5': 0, '5-7': 0, '7+': 0}
            for emp in employees:
                yrs = self._get_years(emp, today)
                if yrs < 1:    exp_groups['0-1'] += 1
                elif yrs < 3:  exp_groups['1-3'] += 1
                elif yrs < 5:  exp_groups['3-5'] += 1
                elif yrs < 7:  exp_groups['5-7'] += 1
                else:          exp_groups['7+']  += 1

            present_ids = []
            try:
                present_ids = list(set(att_records.mapped('employee_id.id')))
            except Exception:
                pass


            # Today's present/absent/leave

            today_str = str(today)

       
            today_att = env['hr.attendance'].sudo().search([
                ('employee_id', 'in', emp_ids),
                ('check_in', '>=', datetime.combine(today, datetime.min.time())),
                ('check_in', '<=', datetime.combine(today, datetime.max.time())),
            ])
            today_present_ids = list(set(today_att.mapped('employee_id.id')))
            today_present = len(today_present_ids)

            
            today_leave_emps = env['hr.leave'].sudo().search([
                ('employee_id', 'in', emp_ids),
                ('state', '=', 'validate'),
                ('date_from', '<=', datetime.combine(today, datetime.max.time())),
                ('date_to',   '>=', datetime.combine(today, datetime.min.time())),
            ])
            today_leave_ids  = list(set(today_leave_emps.mapped('employee_id.id')))
            today_on_leave   = len(today_leave_ids)

            today_absent_ids = [
                e for e in emp_ids
                if e not in today_present_ids and e not in today_leave_ids
            ]
            today_absent = len(today_absent_ids)


            return {
                'today':             str(today),
                'month_label':       today.strftime('%B %Y'),
                'total_emp':         total_emp,
                'attendance_pct':    attendance_pct,
                'absence_pct':       absence_pct,
                'leave_appr_pct':    leave_appr_pct,
                'sick_count':        sick_count,
                'casual_count':      casual_count,
                'unscheduled_count': unscheduled_count,
                'unplanned_count':   max(0, total_emp - len(present_ids)),
                'wfo_count':         wfo_count,
                'wfh_count':         wfh_count,
                'other_count':       max(0, total_emp - wfo_count - wfh_count),
                'leave_type_dist':   leave_type_dist[:8],
                'exp_groups':        exp_groups,
                'total_leave_req':   total_leave_req,
                'validated_leaves':  validated_count,
                'pending_leaves':    len(pending),
                'refused_leaves':    len(refused),
                'today_present':     today_present,
                'today_present_ids': today_present_ids,
                'today_on_leave':    today_on_leave,
                'today_leave_ids':   today_leave_ids,
                'today_absent':      today_absent,
                'today_absent_ids':  today_absent_ids,
            }

        except Exception as e:
            _logger.error("get_dashboard_data FATAL: %s", e, exc_info=True)
            return {
                'today': str(date.today()), 'month_label': date.today().strftime('%B %Y'),
                'total_emp': 0, 'attendance_pct': 0, 'absence_pct': 0,
                'leave_appr_pct': 0, 'sick_count': 0, 'casual_count': 0,
                'unscheduled_count': 0, 'unplanned_count': 0,
                'wfo_count': 0, 'wfh_count': 0, 'other_count': 0,
                'leave_type_dist': [], 'exp_groups': {'0-1': 0, '1-3': 0, '3-5': 0, '5-7': 0, '7+': 0},
                'total_leave_req': 0, 'validated_leaves': 0,
                'pending_leaves': 0, 'refused_leaves': 0,
            }

    # Route 3: Chart data

    @http.route('/hr/dashboard/chart_data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_chart_data(self, dept_id=None, company_id=None, **kwargs):
        try:
            env         = request.env
            today       = date.today()
            month_start = today.replace(day=1)


            
            company_domain = []
            if company_id and str(company_id) != 'all':
                try:
                    company_domain = [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass

            emp_domain = self._dept_domain(dept_id) + company_domain + [('active', '=', True)]

            # emp_domain = self._dept_domain(dept_id) + [('active', '=', True)]
            employees  = env['hr.employee'].sudo().search(emp_domain)
            emp_ids    = employees.ids or [0]

            # Absence trend (last 3 months)
            abs_labels    = []
            absence_trend = []
            for i in range(2, -1, -1):
                m   = today - relativedelta(months=i)
                m_s = m.replace(day=1)
                m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)
                cnt = env['hr.leave'].sudo().search_count([
                    ('employee_id', 'in', emp_ids),
                    ('state', '=', 'validate'),
                    ('date_from', '<=', str(m_e)),
                    ('date_to',   '>=', str(m_s)),
                ])
                abs_labels.append(m.strftime('%b %Y'))
                absence_trend.append(cnt)

            # Leave pattern last month (daily)
            lp_labels     = []
            leave_pattern = []
            for i in range(11, -1, -1):
                m   = today - relativedelta(months=i)
                m_s = m.replace(day=1)
                m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)
                cnt = env['hr.leave'].sudo().search_count([
                    ('employee_id', 'in', emp_ids),
                    ('state',       '=', 'validate'),
                    ('date_from',   '<=', str(m_e)),
                    ('date_to',     '>=', str(m_s)),
                ])
                lp_labels.append(m.strftime('%b %y'))
                leave_pattern.append(cnt)
            # lp_labels     = []
            # leave_pattern = []
            # lm_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            # lm_end   = today.replace(day=1) - timedelta(days=1)
            # lv_last  = env['hr.leave'].sudo().search([
            #     ('employee_id', 'in', emp_ids),
            #     ('state', '=', 'validate'),
            #     ('date_from', '<=', str(lm_end)),
            #     ('date_to',   '>=', str(lm_start)),
            # ])
            # for i in range((lm_end - lm_start).days + 1):
            #     d = lm_start + timedelta(days=i)
            #     lp_labels.append(d.strftime('%d/%m'))
            #     count = 0
            #     for lv in lv_last:
            #         try:
            #             df = self._to_date(lv.date_from)
            #             dt = self._to_date(lv.date_to)
            #             if df and dt and df <= d <= dt:
            #                 count += 1
            #         except Exception:
            #             pass
            #     leave_pattern.append(count)

            # Dept attendance rates
            dept_labels = []
            dept_rates  = []
            wdays = sum(
                1 for i in range((today - month_start).days + 1)
                if (month_start + timedelta(days=i)).weekday() < 5
            ) or 1
            for dept in env['hr.department'].sudo().search([]):
                de = env['hr.employee'].sudo().search([
                    ('department_id', '=', dept.id), ('active', '=', True)
                ])
                if not de:
                    continue
                da = env['hr.attendance'].sudo().search([
                    ('employee_id', 'in', de.ids),
                    ('check_in', '>=', datetime.combine(month_start, datetime.min.time())),
                    ('check_in', '<=', datetime.combine(today, datetime.max.time())),
                ])
                dept_labels.append(dept.name)
                dept_rates.append(round((len(da) / (len(de) * wdays)) * 100, 1) if de else 0)

            # Leave type dist
            lt_labels = []
            lt_counts = []
            lt_pcts   = []
            try:
                ml = env['hr.leave'].sudo().search([
                    ('employee_id', 'in', emp_ids),
                    ('state', '=', 'validate'),
                    ('date_from', '>=', str(month_start)),
                ])
                tv = len(ml)
                lt_map = {}
                for lv in ml:
                    n = lv.holiday_status_id.name or 'Other'
                    lt_map[n] = lt_map.get(n, 0) + 1
                for n, c in sorted(lt_map.items(), key=lambda x: -x[1]):
                    lt_labels.append(n)
                    lt_counts.append(c)
                    lt_pcts.append(round((c / tv) * 100, 1) if tv else 0)
            except Exception:
                pass

            # Experience groups
            exp_labels = ['0-1', '1-3', '3-5', '5-7', '7+']
            exp_data   = [0, 0, 0, 0, 0]
            for emp in employees:
                yrs = self._get_years(emp, today)
                if yrs < 1:    exp_data[0] += 1
                elif yrs < 3:  exp_data[1] += 1
                elif yrs < 5:  exp_data[2] += 1
                elif yrs < 7:  exp_data[3] += 1
                else:          exp_data[4] += 1

            wfo = sum(1 for e in employees if (getattr(e, 'work_location_type', '') or '') != 'home')
            wfh = len(employees) - wfo

            return {
                'absence_labels': abs_labels,  'absence_trend': absence_trend,
                'lp_labels':      lp_labels,   'leave_pattern': leave_pattern,
                'dept_labels':    dept_labels, 'dept_rates':    dept_rates,
                'lt_labels':      lt_labels,   'lt_counts':     lt_counts,  'lt_pcts': lt_pcts,
                'exp_labels':     exp_labels,  'exp_data':      exp_data,
                'wfo':            wfo,         'wfh':           wfh,
            }

        except Exception as e:
            _logger.error("get_chart_data FATAL: %s", e, exc_info=True)
            return {
                'absence_labels': [], 'absence_trend': [],
                'lp_labels': [],      'leave_pattern': [],
                'dept_labels': [],    'dept_rates': [],
                'lt_labels': [],      'lt_counts': [], 'lt_pcts': [],
                'exp_labels': ['0-1', '1-3', '3-5', '5-7', '7+'],
                'exp_data':   [0, 0, 0, 0, 0],
                'wfo': 0, 'wfh': 0,
            }

    # Route 4: Dept Attendance (separate card)



    @http.route('/hr/dashboard/dept_attendance', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dept_attendance(self, company_id=None, **kwargs):
        try:
            env         = request.env
            today       = date.today()
            month_start = today.replace(day=1)
            working_days = sum(
                1 for i in range((today - month_start).days + 1)
                if (month_start + timedelta(days=i)).weekday() < 5
            ) or 1

            # Company filter
            company_domain = []
            if company_id and str(company_id) != 'all':
                try:
                    company_domain = [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass

            result = []
            for dept in env['hr.department'].sudo().search(company_domain):
                emp_domain = [('department_id', '=', dept.id), ('active', '=', True)]
                if company_domain:
                    emp_domain += company_domain
                emps = env['hr.employee'].sudo().search(emp_domain)
                if not emps:
                    continue
                att = env['hr.attendance'].sudo().search([
                    ('employee_id', 'in', emps.ids),
                    ('check_in', '>=', datetime.combine(month_start, datetime.min.time())),
                    ('check_in', '<=', datetime.combine(today, datetime.max.time())),
                ])
                d_exp = len(emps) * working_days

                attended_emp_count = len(set(att.mapped('employee_id.id')))

                result.append({
                    'dept':           dept.name,
                    'rate':           round((len(att) / d_exp) * 100, 1) if d_exp else 0,
                    'total_emp':      len(emps),
                    'attended_count': attended_emp_count,
                })
            result.sort(key=lambda x: -x['rate'])
            return result
        except Exception as e:
            _logger.error("get_dept_attendance: %s", e)
            return []
        

    # @http.route('/hr/dashboard/dept_attendance', type='json', auth='user', methods=['POST'], csrf=False)
    # def get_dept_attendance(self, **kwargs):
    #     try:
    #         env         = request.env
    #         today       = date.today()
    #         month_start = today.replace(day=1)
    #         working_days = sum(
    #             1 for i in range((today - month_start).days + 1)
    #             if (month_start + timedelta(days=i)).weekday() < 5
    #         ) or 1
    #         result = []
    #         for dept in env['hr.department'].sudo().search([]):
    #             emps = env['hr.employee'].sudo().search([
    #                 ('department_id', '=', dept.id), ('active', '=', True),
    #             ])
    #             if not emps:
    #                 continue
    #             att = env['hr.attendance'].sudo().search([
    #                 ('employee_id', 'in', emps.ids),
    #                 ('check_in', '>=', datetime.combine(month_start, datetime.min.time())),
    #                 ('check_in', '<=', datetime.combine(today, datetime.max.time())),
    #             ])
    #             d_exp = len(emps) * working_days
    #             result.append({
    #                 'dept': dept.name,
    #                 'rate': round((len(att) / d_exp) * 100, 1) if d_exp else 0
    #             })
    #         result.sort(key=lambda x: -x['rate'])
    #         return result
    #     except Exception as e:
    #         _logger.error("get_dept_attendance: %s", e)
    #         return []



    
        

    # compayne data
    @http.route('/hr/dashboard/companies', type='json', auth='user', methods=['POST'], csrf=False)
    def get_companies(self, **kwargs):
        try:
            companies = request.env['res.company'].sudo().search([], order='name asc')
            return [{'id': c.id, 'name': c.name} for c in companies]
        except Exception as e:
            _logger.error("get_companies: %s", e)
            return []

    @http.route('/hr/dashboard/overtime_data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_overtime_data(self, dept_id=None,  company_id=None, **kwargs):
        try:
            env   = request.env
            today = date.today()
            result = []

            for i in range(11, -1, -1):
                m     = today - relativedelta(months=i)
                m_s   = m.replace(day=1)
                m_e   = (m_s + relativedelta(months=1)) - timedelta(days=1)

                company_domain = []
                if company_id and str(company_id) != 'all':
                    try:
                        company_domain = [('company_id', '=', int(company_id))]
                    except (TypeError, ValueError):
                        pass

                emp_domain = self._dept_domain(dept_id) + company_domain + [('active', '=', True)]

                # emp_domain = self._dept_domain(dept_id) + [('active', '=', True)]
                employees  = env['hr.employee'].sudo().search(emp_domain)
                emp_ids    = employees.ids or [0]
                total_emp  = len(employees) or 1

                attendances = env['hr.attendance'].sudo().search([
                    ('employee_id', 'in', emp_ids),
                    ('check_in', '>=', datetime.combine(m_s, datetime.min.time())),
                    ('check_in', '<=', datetime.combine(m_e, datetime.max.time())),
                ])

                overtime_hours   = 0.0
                overtime_emp_ids = set()
                for att in attendances:
                    wh = att.worked_hours or 0
                    if wh > 8:
                        overtime_hours += (wh - 8)
                        overtime_emp_ids.add(att.employee_id.id)

                emp_count = len(overtime_emp_ids)

                result.append({
                    'month':          m.strftime('%b %y'),
                    'overtime_hours': round(overtime_hours, 1),
                    'employee_count': emp_count,
                })

            return result

        except Exception as e:
            _logger.error("get_overtime_data: %s", e, exc_info=True)
            return []
    # @http.route('/hr/dashboard/overtime_data', type='json', auth='user', methods=['POST'], csrf=False)
    # def get_overtime_data(self, dept_id=None, **kwargs):
    #     try:
    #         env   = request.env
    #         today = date.today()
    #         result = []

    #         for i in range(11, -1, -1):
    #             m     = today - relativedelta(months=i)
    #             m_s   = m.replace(day=1)
    #             m_e   = (m_s + relativedelta(months=1)) - timedelta(days=1)

    #             emp_domain = self._dept_domain(dept_id) + [('active', '=', True)]
    #             employees  = env['hr.employee'].sudo().search(emp_domain)
    #             emp_ids    = employees.ids or [0]
    #             total_emp  = len(employees) or 1

    #             att = env['hr.attendance'].sudo().search([
    #                 ('employee_id', 'in', emp_ids),
    #                 ('check_in', '>=', datetime.combine(m_s, datetime.min.time())),
    #                 ('check_in', '<=', datetime.combine(m_e, datetime.max.time())),
    #             ])

               
    #             overtime_hours = 0.0
    #             overtime_emp_ids = set()
    #             for a in att:
    #                 wh = getattr(a, 'worked_hours', 0) or 0
    #                 if wh > 8:
    #                     overtime_hours += (wh - 8)
    #                     overtime_emp_ids.add(a.employee_id.id)

    #             overtime_emp_count = len(overtime_emp_ids)
    #             overtime_pct       = round((overtime_emp_count / total_emp) * 100, 1)
    #             avg_per_emp        = round(overtime_hours / overtime_emp_count, 1) if overtime_emp_count else 0

    #             result.append({
    #                 'month':          m.strftime('%b %y'),
    #                 'overtime_pct':   overtime_pct,
    #                 'overtime_hours': round(overtime_hours, 0),
    #                 'avg_per_emp':    avg_per_emp,
    #             })

    #         return result

    #     except Exception as e:
    #         _logger.error("get_overtime_data: %s", e, exc_info=True)
    #         return []



    @http.route('/hr/dashboard/expense_summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_expense_summary(self, company_id=None, dept_id=None, **kwargs):
        try:
            env         = request.env
            today       = date.today()
            month_start = today.replace(day=1)
            month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)
            prev_start  = month_start - relativedelta(months=1)
            prev_end    = month_start - timedelta(days=1)

            base_domain = [('state', 'in', ('draft', 'reported', 'posted', 'done'))]

            if company_id and str(company_id) != 'all':
                try:
                    base_domain += [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass

            if dept_id and str(dept_id) != 'all':
                try:
                    emp_ids = env['hr.employee'].sudo().search(
                        [('department_id', '=', int(dept_id)), ('active', '=', True)]
                    ).ids
                    base_domain += [('employee_id', 'in', emp_ids)]
                except (TypeError, ValueError):
                    pass

            # def get_expenses(start, end):
            #     return env['hr.expense'].sudo().search(base_domain + [
            #         ('date', '>=', str(start)),
            #         ('date', '<=', str(end)),
            #     ])
            

            def get_expenses(start, end):
                domain = base_domain.copy()
                
                try:
                    fields = env['hr.expense'].sudo().fields_get(['date', 'expense_date'])
                    date_field = 'date' if 'date' in fields else 'expense_date'
                except Exception:
                    date_field = 'date'
                
                return env['hr.expense'].sudo().search(domain + [
                    (date_field, '>=', str(start)),
                    (date_field, '<=', str(end)),
                ])

            curr_expenses = get_expenses(month_start, month_end)
            prev_expenses = get_expenses(prev_start, prev_end)

            curr_total = round(sum(e.total_amount for e in curr_expenses), 2)
            prev_total = round(sum(e.total_amount for e in prev_expenses), 2)

            # % change
            change = None
            if prev_total:
                change = round(((curr_total - prev_total) / prev_total) * 100, 1)

            # Department-wise breakdown (current month)
            dept_map = {}
            for exp in curr_expenses:
                dept_name = exp.employee_id.department_id.name or 'Unknown'
                dept_map[dept_name] = dept_map.get(dept_name, 0) + (exp.total_amount or 0)

            dept_breakdown = sorted(
                [{'dept': k, 'total': round(v, 2)} for k, v in dept_map.items()],
                key=lambda x: -x['total']
            )

            # Last 6 months trend
            trend = []
            for i in range(5, -1, -1):
                m   = today - relativedelta(months=i)
                m_s = m.replace(day=1)
                m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)
                exps = env['hr.expense'].sudo().search(base_domain + [
                    ('date', '>=', str(m_s)),
                    ('date', '<=', str(m_e)),
                ])
                trend.append({
                    'label': m.strftime('%b %y'),
                    'total': round(sum(e.total_amount for e in exps), 2),
                })

            return {
                'month_label':     today.strftime('%B %Y'),
                'curr_total':      curr_total,
                'prev_total':      prev_total,
                'change':          change,
                'dept_breakdown':  dept_breakdown[:8],
                'trend':           trend,
                'total_count':     len(curr_expenses),
            }

        except Exception as e:
            _logger.error("get_expense_summary: %s", e, exc_info=True)
            return {
                'month_label': date.today().strftime('%B %Y'),
                'curr_total': 0, 'prev_total': 0, 'change': None,
                'dept_breakdown': [], 'trend': [], 'total_count': 0,
            }


    @http.route('/hr/dashboard/payroll_summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_payroll_summary(self, company_id=None, dept_id=None, **kwargs):
        try:
            env         = request.env
            today       = date.today()
            month_start = today.replace(day=1)
            month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)

            prev_start  = month_start - relativedelta(months=1)
            prev_end    = month_start - timedelta(days=1)

            # Filters
            base_domain = [('state', '!=', 'cancel')]
            if company_id and str(company_id) != 'all':
                try:
                    base_domain += [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass
            if dept_id and str(dept_id) != 'all':
                try:
                    base_domain += [('department_id', '=', int(dept_id))]
                except (TypeError, ValueError):
                    pass

            def get_slips(start, end):
                return env['hr.payslip'].sudo().search(base_domain + [
                    ('date_from', '>=', str(start)),
                    ('date_to',   '<=', str(end)),
                ])

            def sum_line(slips, code):
                total = 0.0
                for slip in slips:
                    for line in slip.line_ids:
                        if line.code == code:
                            total += line.total or 0.0
                return round(total, 2)

            # Current month slips
            curr_slips = get_slips(month_start, month_end)
            prev_slips = get_slips(prev_start, prev_end)

            def calc_totals(slips):
                gross = net = employer_cost = 0.0
                for slip in slips:
                    gross         += slip.gross_wage       or 0.0
                    net           += slip.net_wage         or 0.0
                    # employer cost = gross + employer contributions
                    # GROSS line code usually 'GROSS', NET = 'NET'
                    # Fallback: use wage fields
                return round(gross, 2), round(net, 2)

            # Better approach — use payslip line codes
            def calc_by_lines(slips):
                gross = net = cost = 0.0
                for slip in slips:
                    for line in slip.line_ids:
                        c = line.code or ''
                        if c == 'GROSS':
                            gross += line.total or 0.0
                        elif c == 'NET':
                            net += line.total or 0.0
                        elif c in ('TOTAL_COMP', 'EMPLOYER_COST', 'EMP_COST'):
                            cost += line.total or 0.0
                
                if cost == 0:
                    cost = gross
                return round(gross, 2), round(net, 2), round(cost, 2)

            curr_gross, curr_net, curr_cost = calc_by_lines(curr_slips)
            prev_gross, prev_net, prev_cost = calc_by_lines(prev_slips)

            def pct_change(curr, prev):
                if prev == 0:
                    return None
                return round(((curr - prev) / prev) * 100, 1)

            
            status_count = {'draft': 0, 'verify': 0, 'done': 0, 'paid': 0}
            for slip in curr_slips:
                s = slip.state
                if s in status_count:
                    status_count[s] += 1

            
            emp_rows = []
            for slip in curr_slips:
                g = p = n = 0.0
                for line in slip.line_ids:
                    c = line.code or ''
                    if c == 'GROSS': g = line.total or 0.0
                    elif c == 'NET':  n = line.total or 0.0
                if g == 0: g = slip.gross_wage or 0.0
                if n == 0: n = slip.net_wage   or 0.0
                emp_rows.append({
                    'name':          slip.employee_id.name,
                    'dept':          slip.department_id.name  if slip.department_id  else '',
                    'gross':         round(g, 2),
                    'net':           round(n, 2),
                    'employer_cost': round(g, 2),   
                    'state':         slip.state,
                    'date_from':     str(slip.date_from),
                    'date_to':       str(slip.date_to),
                })
            emp_rows.sort(key=lambda x: -x['gross'])



            avg_salary = round(curr_gross / len(curr_slips), 2) if curr_slips else 0

            outstanding = 0.0
            for slip in curr_slips:
                if slip.state in ('draft', 'verify'):
                    for line in slip.line_ids:
                        if line.code == 'NET':
                            outstanding += line.total or 0.0
            if outstanding == 0:
                for slip in curr_slips:
                    if slip.state in ('draft', 'verify'):
                        outstanding += slip.net_wage or 0.0
            outstanding = round(outstanding, 2)

           
            monthly_history = []
            for i in range(7, -1, -1):
                ms = month_start - relativedelta(months=i)
                me = (ms + relativedelta(months=1)) - timedelta(days=1)
                sl = get_slips(ms, me)
                g = n = 0.0
                for s in sl:
                    for ln in s.line_ids:
                        if ln.code == 'GROSS': g += ln.total or 0.0
                        elif ln.code == 'NET':  n += ln.total or 0.0
                    if g == 0: g += s.gross_wage or 0.0
                    if n == 0: n += s.net_wage   or 0.0
                monthly_history.append({
                    'label': ms.strftime('%b %y'),
                    'gross': round(g, 2),
                    'net':   round(n, 2),
                })

            return {
                'month_label':      today.strftime('%B %Y'),
                'prev_month_label': prev_start.strftime('%B %Y'),
               
                'curr_gross':       curr_gross,
                'curr_net':         curr_net,
                'curr_cost':        curr_cost,
               
                'prev_gross':       prev_gross,
                'prev_net':         prev_net,
                'prev_cost':        prev_cost,
              
                'gross_change':     pct_change(curr_gross, prev_gross),
                'net_change':       pct_change(curr_net,   prev_net),
                'cost_change':      pct_change(curr_cost,  prev_cost),
               
                'status_count':     status_count,
                'total_slips':      len(curr_slips),
                
                'emp_rows':         emp_rows[:50],   

                'avg_salary':       avg_salary,
                'outstanding':      outstanding,
                'total_slips':      len(curr_slips),
                'monthly_history':  monthly_history,
            }

        except Exception as e:
            _logger.error("get_payroll_summary: %s", e, exc_info=True)
            return {
                'month_label': date.today().strftime('%B %Y'),
                'curr_gross': 0, 'curr_net': 0, 'curr_cost': 0,
                'prev_gross': 0, 'prev_net': 0, 'prev_cost': 0,
                'gross_change': None, 'net_change': None, 'cost_change': None,
                'status_count': {'draft': 0, 'verify': 0, 'done': 0, 'paid': 0},
                'total_slips': 0, 'emp_rows': [],
            }
        

    # loan summay added for anwer bhai module 
        
    @http.route('/hr/dashboard/loan_summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_loan_summary(self, company_id=None, dept_id=None, **kwargs):
        try:
            env         = request.env
            today       = date.today()
            month_start = today.replace(day=1)
            month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)
            prev_start  = month_start - relativedelta(months=1)
            prev_end    = month_start - timedelta(days=1)

  
            IrModel = env['ir.model'].sudo()
            has_loan    = IrModel.search([('model', '=', 'hr.loan')],    limit=1)
            has_advance = IrModel.search([('model', '=', 'hr.salary.advance')], limit=1)

    
            company_domain = []
            if company_id and str(company_id) != 'all':
                try:
                    company_domain = [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass

            dept_emp_ids = None
            if dept_id and str(dept_id) != 'all':
                try:
                    dept_emp_ids = env['hr.employee'].sudo().search(
                        [('department_id', '=', int(dept_id)), ('active', '=', True)]
                    ).ids
                except (TypeError, ValueError):
                    pass

            def emp_filter(field='employee_id'):
                if dept_emp_ids is not None:
                    return [(field, 'in', dept_emp_ids)]
                return []

            curr_loan_total = prev_loan_total = 0.0
            loan_dept_breakdown = []
            loan_trend          = []
            loan_status_count   = {'draft':0,'submitted':0,'approved':0,
                                'disbursed':0,'partially_paid':0,'paid':0,'rejected':0}
            total_loan_count = 0

            if has_loan:
                base_loan = [('state', 'not in', ['rejected', 'draft'])] \
                        + company_domain + emp_filter()

                def get_loans(start, end):
                    return env['hr.loan'].sudo().search(base_loan + [
                        ('date', '>=', str(start)),
                        ('date', '<=', str(end)),
                    ])

                curr_loans  = get_loans(month_start, month_end)
                prev_loans  = get_loans(prev_start,  prev_end)

                curr_loan_total = round(sum(l.loan_amount for l in curr_loans), 2)
                prev_loan_total = round(sum(l.loan_amount for l in prev_loans), 2)
                total_loan_count = len(curr_loans)

                
                all_loans = env['hr.loan'].sudo().search(base_loan)
                for loan in all_loans:
                    s = loan.state
                    if s in loan_status_count:
                        loan_status_count[s] += 1

                # Dept breakdown (current month)
                dept_map = {}
                for loan in curr_loans:
                    dept_name = loan.department_id.name or 'Unknown'
                    dept_map[dept_name] = dept_map.get(dept_name, 0) + (loan.loan_amount or 0)
                loan_dept_breakdown = sorted(
                    [{'dept': k, 'total': round(v, 2)} for k, v in dept_map.items()],
                    key=lambda x: -x['total']
                )[:8]

                # 6-month trend
                for i in range(5, -1, -1):
                    m   = today - relativedelta(months=i)
                    m_s = m.replace(day=1)
                    m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)
                    sl  = get_loans(m_s, m_e)
                    loan_trend.append({
                        'label': m.strftime('%b %y'),
                        'total': round(sum(l.loan_amount for l in sl), 2),
                        'count': len(sl),
                    })

            curr_adv_total = prev_adv_total = 0.0
            adv_dept_breakdown = []
            adv_trend          = []
            adv_status_count   = {'draft':0,'submitted':0,'approved':0,'rejected':0,'paid':0}
            total_adv_count    = 0

            if has_advance:
                base_adv = [('state', 'not in', ['rejected', 'draft'])] \
                        + company_domain + emp_filter()

                def get_advances(start, end):
                    return env['hr.salary.advance'].sudo().search(base_adv + [
                        ('date', '>=', str(start)),
                        ('date', '<=', str(end)),
                    ])

                curr_adv   = get_advances(month_start, month_end)
                prev_adv   = get_advances(prev_start,  prev_end)

                curr_adv_total = round(sum(a.amount for a in curr_adv), 2)
                prev_adv_total = round(sum(a.amount for a in prev_adv), 2)
                total_adv_count = len(curr_adv)

                # Status count
                all_adv = env['hr.salary.advance'].sudo().search(base_adv)
                for adv in all_adv:
                    s = adv.state
                    if s in adv_status_count:
                        adv_status_count[s] += 1

                # Dept breakdown
                dept_map2 = {}
                for adv in curr_adv:
                    dept_name = adv.department_id.name or 'Unknown'
                    dept_map2[dept_name] = dept_map2.get(dept_name, 0) + (adv.amount or 0)
                adv_dept_breakdown = sorted(
                    [{'dept': k, 'total': round(v, 2)} for k, v in dept_map2.items()],
                    key=lambda x: -x['total']
                )[:8]

                # 6-month trend
                for i in range(5, -1, -1):
                    m   = today - relativedelta(months=i)
                    m_s = m.replace(day=1)
                    m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)
                    sl  = get_advances(m_s, m_e)
                    adv_trend.append({
                        'label': m.strftime('%b %y'),
                        'total': round(sum(a.amount for a in sl), 2),
                        'count': len(sl),
                    })


            def pct(curr, prev):
                if not prev:
                    return None
                return round(((curr - prev) / prev) * 100, 1)

            return {
                'month_label':          today.strftime('%B %Y'),
                'has_loan':             bool(has_loan),
                'has_advance':          bool(has_advance),

                'curr_loan_total':      curr_loan_total,
                'prev_loan_total':      prev_loan_total,
                'loan_change':          pct(curr_loan_total, prev_loan_total),
                'total_loan_count':     total_loan_count,
                'loan_status_count':    loan_status_count,
                'loan_dept_breakdown':  loan_dept_breakdown,
                'loan_trend':           loan_trend,

                'curr_adv_total':       curr_adv_total,
                'prev_adv_total':       prev_adv_total,
                'adv_change':           pct(curr_adv_total, prev_adv_total),
                'total_adv_count':      total_adv_count,
                'adv_status_count':     adv_status_count,
                'adv_dept_breakdown':   adv_dept_breakdown,
                'adv_trend':            adv_trend,
            }

        except Exception as e:
            _logger.error("get_loan_summary: %s", e, exc_info=True)
            return {
                'month_label': date.today().strftime('%B %Y'),
                'has_loan': False, 'has_advance': False,
                'curr_loan_total': 0, 'prev_loan_total': 0,
                'loan_change': None, 'total_loan_count': 0,
                'loan_status_count': {}, 'loan_dept_breakdown': [], 'loan_trend': [],
                'curr_adv_total': 0, 'prev_adv_total': 0,
                'adv_change': None, 'total_adv_count': 0,
                'adv_status_count': {}, 'adv_dept_breakdown': [], 'adv_trend': [],
            }
        



    #fleet cost summary code here

    @http.route('/hr/dashboard/fleet_cost_summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_fleet_cost_summary(self, company_id=None, **kwargs):
        try:
            env   = request.env
            today = date.today()

         
            IrModel   = env['ir.model'].sudo()
            has_fleet = IrModel.search([('model', '=', 'fleet.vehicle.cost.report')], limit=1)
            if not has_fleet:
                return {
                    'has_fleet': False,
                    'monthly_trend': [], 'curr_total': 0,
                    'prev_total': 0, 'change': None,
                    'contract_total': 0, 'service_total': 0,
                    'vehicle_breakdown': [],
                }

            #Company filter 
            company_domain = []
            if company_id and str(company_id) != 'all':
                try:
                    company_domain = [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass

            month_start = today.replace(day=1)
            month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)
            prev_start  = month_start - relativedelta(months=1)
            prev_end    = month_start - timedelta(days=1)

            #Cost query helper fleet.vehicle.cost.report
            def get_costs(start, end, cost_type=None):
                domain = company_domain + [
                    ('date_start', '>=', str(start)),
                    ('date_start', '<=', str(end)),
                ]
                if cost_type:
                    domain += [('cost_type', '=', cost_type)]
                return env['fleet.vehicle.cost.report'].sudo().search(domain)

            # Current & Previous month totals 
            curr_all  = get_costs(month_start, month_end)
            prev_all  = get_costs(prev_start,  prev_end)

            curr_total = round(sum(c.cost for c in curr_all), 2)
            prev_total = round(sum(c.cost for c in prev_all), 2)

            change = None
            if prev_total:
                change = round(((curr_total - prev_total) / prev_total) * 100, 1)

            #Contract vs Service (current month) 
            contract_costs = get_costs(month_start, month_end, 'contract')
            service_costs  = get_costs(month_start, month_end, 'service')

            contract_total = round(sum(c.cost for c in contract_costs), 2)
            service_total  = round(sum(c.cost for c in service_costs),  2)

            # 6 month trend
            monthly_trend = []
            for i in range(5, -1, -1):
                m   = today - relativedelta(months=i)
                m_s = m.replace(day=1)
                m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)

                m_contract = get_costs(m_s, m_e, 'contract')
                m_service  = get_costs(m_s, m_e, 'service')
                m_all      = get_costs(m_s, m_e)

                monthly_trend.append({
                    'label':    m.strftime('%b %y'),
                    'contract': round(sum(c.cost for c in m_contract), 2),
                    'service':  round(sum(c.cost for c in m_service),  2),
                    'total':    round(sum(c.cost for c in m_all),      2),
                })

            #Vehicle-wise breakdown (current month, top 8)
            veh_map = {}
            for c in curr_all:
                vname = c.name or 'Unknown'   
                if vname not in veh_map:
                    veh_map[vname] = {'contract': 0, 'service': 0}
                if c.cost_type == 'contract':
                    veh_map[vname]['contract'] += c.cost or 0
                else:
                    veh_map[vname]['service'] += c.cost or 0

            vehicle_breakdown = sorted([
                {'vehicle': k,'contract': round(v['contract'], 2),
                    'service':  round(v['service'],  2), 
                    'total':    round(v['contract'] + v['service'], 2)}

                for k, v in veh_map.items()],

                key=lambda x: -x['total']
            )[:8]

            return {
                'has_fleet':          True,
                'month_label':        today.strftime('%B %Y'),
                'curr_total':         curr_total,
                'prev_total':         prev_total,
                'change':             change,
                'contract_total':     contract_total,
                'service_total':      service_total,
                'monthly_trend':      monthly_trend,
                'vehicle_breakdown':  vehicle_breakdown,
            }

        except Exception as e:
            _logger.error("get_fleet_cost_summary: %s", e, exc_info=True)
            return {
                'has_fleet': False,
                'monthly_trend': [], 'curr_total': 0,
                'prev_total': 0, 'change': None,
                'contract_total': 0, 'service_total': 0,
                'vehicle_breakdown': [],
            }
        


    @http.route('/hr/dashboard/frontdesk_summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_frontdesk_summary(self, company_id=None, **kwargs):
        try:
            env   = request.env
            today = date.today()

            #Module check 
            IrModel = env['ir.model'].sudo()
            has_visitor = IrModel.search([('model', '=', 'frontdesk.visitor')], limit=1)
            has_drink   = IrModel.search([('model', '=', 'frontdesk.drink')],   limit=1)

            if not has_visitor:
                return {'has_frontdesk': False}

            # Dates 
            month_start = today.replace(day=1)
            month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)
            prev_start  = month_start - relativedelta(months=1)
            prev_end    = month_start - timedelta(days=1)

            #Company filter 
            company_domain = []
            if company_id and str(company_id) != 'all':
                try:
                    company_domain = [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass

            #  Visitor fields check (check_in or arrival_date)
            try:
                v_fields = env['frontdesk.visitor'].sudo().fields_get(
                    ['check_in', 'arrival_date', 'visit_date', 'date']
                )
                date_field = next(
                    (f for f in ['check_in', 'arrival_date', 'visit_date', 'date'] if f in v_fields),
                    'check_in'
                )
            except Exception:
                date_field = 'check_in'

            #Visitor query helper
            def get_visitors(start, end):
                domain = company_domain + [
                    (date_field, '>=', str(start)),
                    (date_field, '<=', str(end)),
                ]
                return env['frontdesk.visitor'].sudo().search(domain)

            curr_visitors = get_visitors(month_start, month_end)
            prev_visitors = get_visitors(prev_start,  prev_end)

            curr_visitor_count = len(curr_visitors)
            prev_visitor_count = len(prev_visitors)

            visitor_change = None
            if prev_visitor_count:
                visitor_change = round(
                    ((curr_visitor_count - prev_visitor_count) / prev_visitor_count) * 100, 1
                )

            #6-month visitor trend
            visitor_trend = []
            for i in range(5, -1, -1):
                m   = today - relativedelta(months=i)
                m_s = m.replace(day=1)
                m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)
                vst = get_visitors(m_s, m_e)
                visitor_trend.append({
                    'label': m.strftime('%b %y'),
                    'count': len(vst),
                })

            #  Today's visitors 
            today_visitors = env['frontdesk.visitor'].sudo().search(
                company_domain + [
                    (date_field, '>=', str(today)),
                    (date_field, '<=', str(today)),
                ]
            )
            today_count = len(today_visitors)

            #  State breakdown (current month) 
            state_map = {}
            for v in curr_visitors:
                s = getattr(v, 'state', None) or 'unknown'
                state_map[s] = state_map.get(s, 0) + 1

            # Purpose/Host breakdown 
            purpose_map = {}
            for v in curr_visitors:
                p = getattr(v, 'purpose', None) or \
                    getattr(v, 'visit_reason', None) or 'Other'
                if hasattr(p, 'name'):
                    p = p.name
                purpose_map[str(p)] = purpose_map.get(str(p), 0) + 1

            purpose_breakdown = sorted(
                [{'purpose': k, 'count': c} for k, c in purpose_map.items()],
                key=lambda x: -x['count']
            )[:6]

            
            #  DRINKS
            drink_summary    = []
            total_drink_qty  = 0
            curr_drink_count = 0
            prev_drink_count = 0
            drink_change     = None

            if has_drink:
                try:
                  
                    d_fields = env['frontdesk.drink'].sudo().fields_get(
                        ['date', 'visit_date', 'check_in']
                    )
                    drink_date_field = next(
                        (f for f in ['date', 'visit_date', 'check_in'] if f in d_fields),
                        None
                    )

                    if drink_date_field:
                        def get_drinks(start, end):
                            return env['frontdesk.drink'].sudo().search(
                                company_domain + [
                                    (drink_date_field, '>=', str(start)),
                                    (drink_date_field, '<=', str(end)),
                                ]
                            )
                        curr_drinks = get_drinks(month_start, month_end)
                        prev_drinks = get_drinks(prev_start,  prev_end)
                    else:
                        
                        curr_drinks = env['frontdesk.drink'].sudo().search(company_domain)
                        prev_drinks = env['frontdesk.drink'].sudo().browse([])

                    curr_drink_count = len(curr_drinks)
                    prev_drink_count = len(prev_drinks)

                    if prev_drink_count:
                        drink_change = round(
                            ((curr_drink_count - prev_drink_count) / prev_drink_count) * 100, 1
                        )

               
                    drink_map = {}
                    for d in curr_drinks:
                        dname = getattr(d, 'name', None) or \
                                getattr(d, 'product_id', None) or 'Unknown'
                        if hasattr(dname, 'name'):
                            dname = dname.name
                        qty = getattr(d, 'quantity', None) or \
                            getattr(d, 'qty', None) or 1
                        try:
                            qty = float(qty)
                        except Exception:
                            qty = 1
                        drink_map[str(dname)] = drink_map.get(str(dname), 0) + qty
                        total_drink_qty += qty

                    drink_summary = sorted(
                        [{'name': k, 'qty': round(v, 0)} for k, v in drink_map.items()],
                        key=lambda x: -x['qty']
                    )[:8]

                except Exception as e:
                    _logger.warning("frontdesk drink error: %s", e)

            return {
                'has_frontdesk':       True,
                'month_label':         today.strftime('%B %Y'),

                # Visitors
                'curr_visitor_count':  curr_visitor_count,
                'prev_visitor_count':  prev_visitor_count,
                'visitor_change':      visitor_change,
                'today_count':         today_count,
                'visitor_trend':       visitor_trend,
                'state_map':           state_map,
                'purpose_breakdown':   purpose_breakdown,

                # Drinks
                'has_drink':           bool(has_drink),
                'curr_drink_count':    curr_drink_count,
                'prev_drink_count':    prev_drink_count,
                'drink_change':        drink_change,
                'total_drink_qty':     int(total_drink_qty),
                'drink_summary':       drink_summary,
            }

        except Exception as e:
            _logger.error("get_frontdesk_summary: %s", e, exc_info=True)
            return {'has_frontdesk': False}
        



# Lunch summary  
    @http.route('/hr/dashboard/lunch_summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_lunch_summary(self, company_id=None, **kwargs):
        try:
            env   = request.env
            today = date.today()

           
            IrModel  = env['ir.model'].sudo()
            has_lunch = IrModel.search([('model', '=', 'lunch.order')], limit=1)
            if not has_lunch:
                return {'has_lunch': False}

        
            month_start = today.replace(day=1)
            month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)
            prev_start  = month_start - relativedelta(months=1)
            prev_end    = month_start - timedelta(days=1)

           
            company_domain = []
            if company_id and str(company_id) != 'all':
                try:
                    company_domain = [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass

    
            def get_orders(start, end):
                return env['lunch.order'].sudo().search(
                    company_domain + [
                        ('date', '>=', str(start)),
                        ('date', '<=', str(end)),
                    ]
                )

            curr_orders  = get_orders(month_start, month_end)
            prev_orders  = get_orders(prev_start,  prev_end)
            today_orders = env['lunch.order'].sudo().search(
                company_domain + [('date', '=', str(today))]
            )

            curr_count  = len(curr_orders)
            prev_count  = len(prev_orders)
            today_count = len(today_orders)

            order_change = None
            if prev_count:
                order_change = round(((curr_count - prev_count) / prev_count) * 100, 1)

           
            today_amount = round(sum(
                (o.price or 0) for o in today_orders
            ), 2)

          
            curr_amount = round(sum(
                (o.price or 0) for o in curr_orders
            ), 2)

   
            today_state = {}
            for o in today_orders:
                s = getattr(o, 'state', 'unknown') or 'unknown'
                today_state[s] = today_state.get(s, 0) + 1

        
                     
            month_state = {}
            for o in curr_orders:
                s = getattr(o, 'state', 'unknown') or 'unknown'
                month_state[s] = month_state.get(s, 0) + 1

           
            location_map = {}
            for o in curr_orders:
          
                loc = None
                if getattr(o, 'supplier_id', None):
                    loc = o.supplier_id.name
                elif getattr(o, 'lunch_location_id', None):
                    loc = o.lunch_location_id.name
                elif getattr(o, 'product_id', None):
                    sup = getattr(o.product_id, 'supplier_id', None)
                    if sup:
                        loc = sup.name
                loc = loc or 'Unknown'
                if loc not in location_map:
                    location_map[loc] = {'count': 0, 'amount': 0.0}
                location_map[loc]['count']  += 1
                location_map[loc]['amount'] += (o.price or 0)

            location_breakdown = sorted(
                [{'location': k,
                'count':    v['count'],
                'amount':   round(v['amount'], 2)}
                for k, v in location_map.items()],
                key=lambda x: -x['count']
            )[:8]

          
            product_map = {}
            for o in curr_orders:
                pname = None
                if getattr(o, 'product_id', None):
                    pname = o.product_id.name
                pname = pname or 'Unknown'
                product_map[pname] = product_map.get(pname, 0) + 1

            product_breakdown = sorted(
                [{'name': k, 'count': v} for k, v in product_map.items()],
                key=lambda x: -x['count']
            )[:6]

         
            monthly_trend = []
            for i in range(5, -1, -1):
                m   = today - relativedelta(months=i)
                m_s = m.replace(day=1)
                m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)
                ords = get_orders(m_s, m_e)
                monthly_trend.append({
                    'label':  m.strftime('%b %y'),
                    'count':  len(ords),
                    'amount': round(sum((o.price or 0) for o in ords), 2),
                })

            return {
                'has_lunch':           True,
                'month_label':         today.strftime('%B %Y'),

                
                'curr_count':          curr_count,
                'prev_count':          prev_count,
                'order_change':        order_change,
                'today_count':         today_count,
                'today_amount':        today_amount,
                'curr_amount':         curr_amount,

               
                'today_state':         today_state,
                'month_state':         month_state,

                
                'location_breakdown':  location_breakdown,
                'product_breakdown':   product_breakdown,
                'monthly_trend':       monthly_trend,
            }

        except Exception as e:
            _logger.error("get_lunch_summary: %s", e, exc_info=True)
            return {'has_lunch': False}


    #  Recruitment summary 

    @http.route('/hr/dashboard/recruitment_summary', type='json', auth='user', methods=['POST'], csrf=False)
    def get_recruitment_summary(self, company_id=None, dept_id=None, **kwargs):
        try:
            env   = request.env
            today = date.today()

            IrModel = env['ir.model'].sudo()
            has_recruitment = IrModel.search([('model', '=', 'hr.applicant')], limit=1)
            if not has_recruitment:
                return {'has_recruitment': False}

          
            month_start = today.replace(day=1)
            month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)
            prev_start  = month_start - relativedelta(months=1)
            prev_end    = month_start - timedelta(days=1)

      
            base_domain = []
            if company_id and str(company_id) != 'all':
                try:
                    base_domain += [('company_id', '=', int(company_id))]
                except (TypeError, ValueError):
                    pass
            if dept_id and str(dept_id) != 'all':
                try:
                    base_domain += [('department_id', '=', int(dept_id))]
                except (TypeError, ValueError):
                    pass

  
      
            def get_applicants(start, end):
                return env['hr.applicant'].sudo().search(
                    base_domain + [
                        ('create_date', '>=', datetime.combine(start, datetime.min.time())),
                        ('create_date', '<=', datetime.combine(end,   datetime.max.time())),
                    ]
                )

            def get_applicants(start, end):
                return env['hr.applicant'].sudo().with_context(active_test=False).search(
                    base_domain + [
                        ('create_date', '>=', datetime.combine(start, datetime.min.time())),
                        ('create_date', '<=', datetime.combine(end,   datetime.max.time())),
                    ]
                )


            curr_apps = get_applicants(month_start, month_end)
            prev_apps = get_applicants(prev_start,  prev_end)

            curr_count = len(curr_apps)
            prev_count = len(prev_apps)

            apply_change = None
            if prev_count:
                apply_change = round(((curr_count - prev_count) / prev_count) * 100, 1)

            def is_hired(app):
                try:
                   
                    if app.stage_id and getattr(app.stage_id, 'hired_stage', False):
                        return True
                  
                    if app.date_closed and app.active:
                        return True
                    return False
                except Exception:
                    return False
                
            # def is_not_hired(app):

            #     try:
            #         if app.stage_id and getatter(app.stage_id, "hired_stage"  'contract' in (app.stage_id.name or ''))

            def is_refused(app):
                try:
                 
                    if not app.active:
                        return True
                    
                    if getattr(app, 'refuse_reason', None):
                        return True
                    status = getattr(app, 'application_status', None)
                    if status and str(status) in ('refused', 'cancelled'):
                        return True
                    return False
                except Exception:
                    return False

        
            hired_apps   = [a for a in curr_apps if is_hired(a)]
            refused_apps = [a for a in curr_apps if is_refused(a)]
            in_progress  = [a for a in curr_apps
                            if not is_hired(a) and not is_refused(a)]

            hired_count    = len(hired_apps)
            refused_count  = len(refused_apps)
            progress_count = len(in_progress)

            # Conversion rate
            conversion_rate = round((hired_count / curr_count) * 100, 1) if curr_count else 0

       
            all_active = env['hr.applicant'].sudo().search(
                base_domain + [('active', '=', True)]
            )
            pipeline_total = len(all_active)

            stage_map = {}
            for app in all_active:
                sname = app.stage_id.name if app.stage_id else 'Unknown'
                if sname not in stage_map:
                    stage_map[sname] = {'count': 0, 'hired': 0}
                stage_map[sname]['count'] += 1
                if is_hired(app):
                    stage_map[sname]['hired'] += 1

            stage_breakdown = sorted(
                [{'stage': k, 'count': v['count'], 'hired': v['hired']}
                for k, v in stage_map.items()],
                key=lambda x: -x['count']
            )[:8]

            dept_map = {}
            for app in curr_apps:
                dname = app.department_id.name if app.department_id else 'No Dept'
                if dname not in dept_map:
                    dept_map[dname] = {'applied': 0, 'hired': 0}
                dept_map[dname]['applied'] += 1
                if is_hired(app):
                    dept_map[dname]['hired'] += 1

            dept_breakdown = sorted(
                [{'dept': k, 'applied': v['applied'], 'hired': v['hired']}
                for k, v in dept_map.items()],
                key=lambda x: -x['applied']
            )[:8]

            job_map = {}
            for app in curr_apps:
                jname = app.job_id.name if app.job_id else 'Unknown'
                job_map[jname] = job_map.get(jname, 0) + 1

            job_breakdown = sorted(
                [{'job': k, 'count': v} for k, v in job_map.items()],
                key=lambda x: -x['count']
            )[:6]

            source_map = {}
            for app in curr_apps:
                src = None
                if getattr(app, 'source_id', None):
                    src = app.source_id.name
                elif getattr(app, 'ref_user_id', None):
                    src = 'Internal Referral'
                src = src or 'Direct'
                source_map[src] = source_map.get(src, 0) + 1

            source_breakdown = sorted(
                [{'source': k, 'count': v} for k, v in source_map.items()],
                key=lambda x: -x['count']
            )[:6]

            monthly_trend = []
            for i in range(5, -1, -1):
                m   = today - relativedelta(months=i)
                m_s = m.replace(day=1)
                m_e = (m_s + relativedelta(months=1)) - timedelta(days=1)
                apps = get_applicants(m_s, m_e)
                h    = sum(1 for a in apps if is_hired(a))
                monthly_trend.append({
                    'label':   m.strftime('%b %y'),
                    'applied': len(apps),
                    'hired':   h,
                })

        
            days_list = []
            for app in hired_apps:
                try:
                    if app.create_date and app.date_closed:
                      
                        cd = app.create_date.date() if hasattr(app.create_date, 'date') else app.create_date
                        dc = app.date_closed.date() if hasattr(app.date_closed, 'date') else app.date_closed
                        diff = (dc - cd).days
                        if diff >= 0:
                            days_list.append(diff)
                except Exception:
                    pass
            avg_days_to_hire = round(sum(days_list) / len(days_list), 1) if days_list else None


            return {
                'has_recruitment':   True,
                'month_label':       today.strftime('%B %Y'),

              
                'curr_count':        curr_count,
                'prev_count':        prev_count,
                'apply_change':      apply_change,
                'hired_count':       hired_count,
                'refused_count':     refused_count,
                'progress_count':    progress_count,
                'conversion_rate':   conversion_rate,
                'pipeline_total':    pipeline_total,
                'avg_days_to_hire':  avg_days_to_hire,

                'stage_breakdown':   stage_breakdown,
                'dept_breakdown':    dept_breakdown,
                'job_breakdown':     job_breakdown,
                'source_breakdown':  source_breakdown,
                'monthly_trend':     monthly_trend,
            }

        except Exception as e:
            _logger.error("get_recruitment_summary: %s", e, exc_info=True)
            return {'has_recruitment': False}