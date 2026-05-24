from odoo import http, fields
from odoo.http import request
import base64
import logging
import traceback

_logger = logging.getLogger(__name__)


class FestivalExpensePortal(http.Controller):

    @http.route('/my/expenses', auth='user', website=True)
    def portal_expense_form(self, **kw):
        if not request.env.user.has_group(
            'emplyee_festival_bonus.group_portal_expense_access'
        ):
            return request.redirect('/my')
        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return request.render('website.403', {})
        try:
            products  = request.env['product.product'].sudo().search([('can_be_expensed', '=', True)])
            managers  = request.env['hr.employee'].sudo().search([])
            employees = request.env['hr.employee'].sudo().search([])
            expenses  = request.env['hr.expense'].sudo().search([
                ('employee_id', '=', employee.id)], order='date desc')
        except Exception as e:
            _logger.error("Expense portal error: %s", e)
            products = managers = employees = expenses = request.env['hr.expense'].sudo().browse([])
        return request.render('emplyee_festival_bonus.portal_expense_form', {
            'employee': employee, 'products': products, 'managers': managers,
            'employees': employees, 'expenses': expenses, 'today': fields.Date.today(),
        })

    @http.route('/my/expenses/submit', auth='user', type='http', website=True, csrf=False)
    def portal_expense_submit(self, **post):
        if not request.env.user.has_group('emplyee_festival_bonus.group_portal_expense_access'):
            return request.redirect('/my')
        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return request.redirect('/my')
        vals = {
            'name': post.get('description'),
            'product_id': int(post.get('product_id')),
            'total_amount_currency': float(post.get('amount') or 0),
            'employee_id': employee.id,
            'payment_mode': post.get('paid_by'),
            'date': post.get('expense_date'),
        }
        if post.get('manager_id'):
            vals['manager_id'] = int(post.get('manager_id'))
        request.env['hr.expense'].sudo().create(vals)
        return request.redirect('/my/expenses?success=1')

    @http.route('/my/check-expense-access', auth='user', type='json', website=True)
    def check_expense_access(self):
        return {'has_access': request.env.user.has_group(
            'emplyee_festival_bonus.group_portal_expense_access')}


class MovementPortal(http.Controller):

    def _get_or_create_movement_leave_type(self):
        lt = request.env['hr.leave.type'].sudo().search([('name', 'ilike', 'Movement')], limit=1)
        if not lt:
            lt = request.env['hr.leave.type'].sudo().create({
                'name': 'Movement',
                'leave_validation_type': 'both',
                'requires_allocation': 'no',
            })
        elif lt.leave_validation_type != 'both':
            lt.sudo().write({'leave_validation_type': 'both'})
        return lt

    def _resolve_tz(self, employee=None):
        import pytz
        for fn in [
            lambda: request.env.user.tz,
            lambda: employee.tz if employee else None,
            lambda: request.env.company.partner_id.tz,
            lambda: request.env['ir.config_parameter'].sudo().get_param('timezone'),
            lambda: 'Asia/Dhaka',
        ]:
            try:
                name = fn()
                if name and name in pytz.all_timezones_set:
                    return pytz.timezone(name)
            except Exception:
                pass
        import pytz as _p
        return _p.timezone('Asia/Dhaka')

    def _fmt_dt(self, dt_utc, user_tz):
        import pytz
        if not dt_utc:
            return ''
        try:
            return pytz.utc.localize(dt_utc).astimezone(user_tz).strftime('%d %b %Y %H:%M')
        except Exception:
            return str(dt_utc)

    @http.route('/my/movement', auth='user', website=True)
    def movement_form(self, movement_type=None, **kw):
        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return request.redirect('/my')
        colleagues = request.env['hr.employee'].sudo().search([('id', '!=', employee.id)])
        all_movements = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id), ('is_movement', '=', True),
        ], order='date_from desc')
        user_tz = self._resolve_tz(employee)

        def _dur(df, dt):
            if not df or not dt:
                return '-'
            mins = int((dt - df).total_seconds() // 60)
            if mins <= 0:
                return '-'
            h, m = divmod(mins, 60)
            return f'{h}h {m}m' if m else f'{h}h'

        movements_display = [{
            'movement_type': mv.movement_type or 'personal',
            'date_from_fmt': self._fmt_dt(mv.date_from, user_tz),
            'date_to_fmt':   self._fmt_dt(mv.date_to,   user_tz),
            'duration':      _dur(mv.date_from, mv.date_to),
            'state':         mv.state,
        } for mv in all_movements]

        return request.render('emplyee_festival_bonus.portal_movement_form', {
            'employee': employee, 'colleagues': colleagues,
            'movement_type': movement_type or 'personal',
            'today': fields.Date.today(),
            'total_movements': len(all_movements),
            'personal_count': sum(1 for m in all_movements if m.movement_type == 'personal'),
            'company_count':  sum(1 for m in all_movements if m.movement_type == 'company'),
            'movements_display': movements_display,
        })

    @http.route('/my/movement/submit', auth='user', type='http', website=True, csrf=False)
    def movement_submit(self, **post):
        from datetime import datetime
        import pytz

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return request.redirect('/my')

        movement_type = post.get('movement_type', 'personal')
        user_tz       = self._resolve_tz(employee)

        def parse_date_hour(date_str, hour_val, time_raw=None):
            """Returns (utc_naive, local_naive) from a date string + hour float."""
            if not date_str:
                return None, None
            try:
                hour_f = None
                if hour_val:
                    try:
                        hour_f = float(hour_val)
                    except Exception:
                        pass
                if hour_f is None and time_raw:
                    try:
                        parts  = time_raw.strip().split(':')
                        hour_f = int(parts[0]) + int(parts[1] if len(parts) > 1 else 0) / 60.0
                    except Exception:
                        pass
                if hour_f is None:
                    _logger.error("No hour value for date=%r hour_val=%r time_raw=%r",
                                  date_str, hour_val, time_raw)
                    return None, None

                hour_i   = int(hour_f)
                minute_i = int(round((hour_f - hour_i) * 60))
                local    = datetime.strptime(date_str.strip(), '%Y-%m-%d').replace(
                    hour=hour_i, minute=minute_i, second=0, microsecond=0
                )
                aware    = user_tz.localize(local, is_dst=False)
                utc      = aware.astimezone(pytz.utc).replace(tzinfo=None)
                return utc, local
            except Exception as e:
                _logger.error("parse_date_hour error date=%r hour=%r: %s", date_str, hour_val, e)
                return None, None

        utc_from, local_from = parse_date_hour(
            post.get('request_date_from'),
            post.get('request_hour_from'),
            post.get('request_hour_from_raw'),
        )
        utc_to, local_to = parse_date_hour(
            post.get('request_date_to'),
            post.get('request_hour_to'),
            post.get('request_hour_to_raw'),
        )

        if not utc_from or not utc_to or utc_to <= utc_from:
            _logger.error(
                "Invalid dates | date_from=%r hour_from=%r | date_to=%r hour_to=%r",
                post.get('request_date_from'), post.get('request_hour_from'),
                post.get('request_date_to'),   post.get('request_hour_to'),
            )
            return request.redirect(f'/my/movement?error=1&movement_type={movement_type}')

        _logger.info(
            "Movement | TZ=%s | local %s→%s | UTC %s→%s",
            user_tz.zone,
            local_from.strftime('%Y-%m-%d %H:%M'), local_to.strftime('%Y-%m-%d %H:%M'),
            utc_from.strftime('%Y-%m-%d %H:%M:%S'), utc_to.strftime('%Y-%m-%d %H:%M:%S'),
        )

        secs      = (utc_to - utc_from).total_seconds()
        raw_hours = secs / 3600.0
        raw_days  = raw_hours / 8.0
        h, m_     = divmod(int(secs // 60), 60)
        dur_str   = f"{h}h {m_}m" if m_ else f"{h}h"
        rec_name  = (
            f"{employee.name or 'Employee'} on Movement: "
            f"{h}:{str(m_).zfill(2)} hours "
            f"({local_from.strftime('%m/%d/%Y')})"
        )

        try:
            leave_type = self._get_or_create_movement_leave_type()
        except Exception:
            _logger.error("Leave type error:\n%s", traceback.format_exc())
            return request.redirect(f'/my/movement?error=1&movement_type={movement_type}')

        notes       = post.get('reason', '') or ''
        delegate_id = None
        if post.get('delegate_id'):
            try:
                did = int(post.get('delegate_id'))
                d   = request.env['hr.employee'].sudo().browse(did)
                if d.exists():
                    delegate_id = did
            except Exception:
                pass

        doc_b64  = None
        doc_name = None
        doc = request.httprequest.files.get('supporting_document')
        if doc and doc.filename:
            doc_b64  = base64.b64encode(doc.read())
            doc_name = doc.filename

        create_vals = {
            'name':              rec_name,
            'holiday_status_id': leave_type.id,
            'employee_id':       employee.id,
            'notes':             notes,
            'is_movement':       True,
            'movement_type':     movement_type,
            'date_from':         utc_from,
            'date_to':           utc_to,
        }
        if delegate_id:
            create_vals['delegate_employee_id'] = delegate_id
        if doc_b64:
            create_vals['supporting_document']      = doc_b64
            create_vals['supporting_document_name'] = doc_name

        try:
            leave    = request.env['hr.leave'].sudo().create(create_vals)
            leave_id = leave.id
            _logger.info("Movement created id=%s with dates %s→%s",
                         leave_id,
                         utc_from.strftime('%Y-%m-%d %H:%M'),
                         utc_to.strftime('%Y-%m-%d %H:%M'))
        except Exception:
            _logger.error("create() failed:\n%s", traceback.format_exc())
            return request.redirect(f'/my/movement?error=1&movement_type={movement_type}')

        cr = request.env.cr

        def _sql(col, val, cast=None):
            sp  = f"mvsp_{col}"
            sql = (
                f"UPDATE hr_leave SET {col} = %s::{cast} WHERE id = %s"
                if cast else
                f"UPDATE hr_leave SET {col} = %s WHERE id = %s"
            )
            try:
                cr.execute(f"SAVEPOINT {sp}")
                cr.execute(sql, (val, leave_id))
                cr.execute(f"RELEASE SAVEPOINT {sp}")
                _logger.debug("SQL OK: %s = %r", col, val)
            except Exception as ex:
                try:
                    cr.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                    cr.execute(f"RELEASE SAVEPOINT {sp}")
                except Exception:
                    pass
                _logger.debug("SQL skip %s: %s", col, ex)

        _sql('request_date_from', local_from.strftime('%Y-%m-%d'), cast='date')
        _sql('request_date_to',   local_to.strftime('%Y-%m-%d'),   cast='date')

        _sql('request_hour_from', local_from.hour + local_from.minute / 60.0)
        _sql('request_hour_to',   local_to.hour   + local_to.minute   / 60.0)

        _sql('number_of_hours',         raw_hours)
        _sql('number_of_hours_display', raw_hours)
        _sql('number_of_days',          raw_days)
        _sql('duration_display',        dur_str)

        _sql('state', 'confirm')
        _sql('name',  rec_name)

        try:
            leave.invalidate_recordset()
        except Exception:
            try:
                leave.invalidate_cache()
            except Exception:
                pass

        try:
            cr.execute(
                "SELECT date_from, date_to, request_hour_from, request_hour_to, state "
                "FROM hr_leave WHERE id=%s", (leave_id,)
            )
            row = cr.fetchone()
            if row:
                _logger.info(
                    "Movement %s VERIFIED | DB date_from=%s date_to=%s "
                    "req_hour=%.2f→%.2f state=%s",
                    leave_id, str(row[0])[:16], str(row[1])[:16],
                    row[2] or 0, row[3] or 0, row[4],
                )
                exp_f = utc_from.strftime('%Y-%m-%d %H:%M')
                exp_t = utc_to.strftime('%Y-%m-%d %H:%M')
                got_f = str(row[0])[:16]
                got_t = str(row[1])[:16]
                if got_f != exp_f or got_t != exp_t:
                    _logger.error(
                        "Movement %s DATE MISMATCH: stored %s→%s, expected %s→%s",
                        leave_id, got_f, got_t, exp_f, exp_t,
                    )
        except Exception as e:
            _logger.warning("Verify query failed: %s", e)

        return request.redirect(f'/my/movement?success=1&movement_type={movement_type}')