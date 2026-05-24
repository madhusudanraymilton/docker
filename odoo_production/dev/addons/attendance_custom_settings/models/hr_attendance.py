"""
hr_attendance.py  –  Punishment Hours override for hr.attendance

punishment_hours is now a fully COMPUTED+STORED field (like worked_hours).
It recomputes live whenever check_in, check_out, or employee_id changes —
so the UI reflects the correct value before Save & Close.

_compute_worked_hours depends on punishment_hours: if punishment > 0 it
returns punishment_hours directly; otherwise falls back to standard Odoo logic.

Two checkout conditions trigger punishment:

  Case 1 – Forgotten check-out (no check_out, check_in on a previous day)
      Handled by the daily cron _cron_missed_checkout_punishment which sets
      a synthetic check_out = shift_end + post_tolerance, then the compute
      method takes care of the rest automatically.

  Case 2 – Late check-out (check_out > shift_end + post_tolerance)
      Detected inside _compute_punishment_hours live.

Punishment reduction by lateness:
    late_hours = max(0, check_in_decimal_local − shift_start_hour)
    achieved   = max(0, base_punishment − late_hours)
"""

from datetime import datetime, timedelta

import pytz
from pytz import utc, timezone

from odoo import api, fields, models
from odoo.tools.translate import _ as _t
from odoo.exceptions import ValidationError
from odoo.tools.intervals import Intervals


# ── Utility ──────────────────────────────────────────────────────────────────

def _hours_to_hhmm(decimal_hours):
    """Convert decimal hours (e.g. 8.5) → 'HH:MM' string."""
    h = int(decimal_hours)
    m = round((decimal_hours - h) * 60)
    return f"{h:02d}:{m:02d}"


# ── Model extension ───────────────────────────────────────────────────────────

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # ── punishment_hours: computed + stored ──────────────────────────────────
    #
    # Making this computed means it recalculates live as the user changes
    # check_out in the form — the UI shows the correct value before saving.
    # store=True persists it so cron and reports can query it in SQL.

    punishment_hours = fields.Float(
        string='Punishment Hours',
        compute='_compute_punishment_hours',
        store=True,
        readonly=True,
        help=(
            'Achieved punishment hours based on check-out time. '
            'When > 0, Worked Time is locked to this value. '
            'Recomputes live as check_out changes.'
        ),
    )

    # ── Step 1: compute punishment_hours ─────────────────────────────────────

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_punishment_hours(self):
        """
        Compute punishment_hours live from check_in / check_out.

        Returns > 0 only when check_out exists AND is after
        (shift_end + post_checkout_tolerance).

        When check_out is absent → 0  (open attendance, no punishment yet;
        the cron will set a synthetic check_out the next day).
        """
        for record in self:
            record.punishment_hours = self._calc_punishment(record)

    def _calc_punishment(self, record):
        """
        Core punishment calculation. Returns achieved punishment hours (float).
        Returns 0.0 when no punishment applies.

        Two cases trigger punishment:

        Case 1 – Forgotten check-out:
            check_out is NULL AND check_in date is before today (local tz).
            Punishment applies immediately — no need to wait for the cron.
            The cron will later set a real check_out, but the punishment is
            already visible from the moment the next day begins.

        Case 2 – Late check-out:
            check_out exists AND check_out > shift_end + post_checkout_tolerance.
        """
        if not record.check_in or not record.employee_id:
            return 0.0

        company, resource_calendar, shift_tz = self._resolve_shift_context(record)
        if not resource_calendar:
            return 0.0

        base_punishment = company.attendance_checkout_punishment_hours
        if not base_punishment:
            return 0.0

        check_in_local = utc.localize(record.check_in).astimezone(shift_tz)
        shift_start_hour, shift_end_hour = self._get_shift_bounds(
            check_in_local, resource_calendar
        )
        if shift_end_hour is None:
            return 0.0

        # ── Case 1: No check_out and check_in was on a previous day ──────────
        if not record.check_out:
            now_utc   = datetime.utcnow()
            now_local = utc.localize(now_utc).astimezone(shift_tz)
            if check_in_local.date() < now_local.date():
                # Forgot to check out — full punishment reduced by lateness
                return self._compute_achieved_punishment(
                    record, base_punishment, shift_tz, shift_start_hour
                )
            # Still same day and no check_out → currently working, no punishment
            return 0.0

        # ── Case 2: check_out exists — check if it is after the tolerance ────
        post_tol = company.attendance_post_checkout_tolerance
        if not post_tol:
            return 0.0

        shift_end_utc      = self._shift_bound_as_utc(record.check_in, shift_tz, shift_end_hour)
        latest_allowed_utc = shift_end_utc + timedelta(hours=post_tol)

        if record.check_out <= latest_allowed_utc:
            return 0.0  # Within tolerance — no punishment

        # Late checkout → compute achieved punishment reduced by lateness
        return self._compute_achieved_punishment(
            record, base_punishment, shift_tz, shift_start_hour
        )

    # ── Step 2: worked_hours depends on punishment_hours ─────────────────────

    # -- Clear overtime for punished records ---------------------------------

    def _update_overtime(self, attendance_domain=None):
        """
        After Odoo computes overtime lines, remove any that belong to
        punished attendance records — a punished employee should not earn
        Extra Hours credit.
        """
        result = super()._update_overtime(attendance_domain)
        punished = self.filtered(lambda r: r.punishment_hours > 0)
        if punished:
            punished.linked_overtime_ids.unlink()
        return result

    @api.depends('check_in', 'check_out', 'employee_id', 'punishment_hours')
    def _compute_worked_hours(self):
        """
        If punishment_hours > 0 → worked_hours = punishment_hours (locked).
        Otherwise → standard Odoo logic (lunch-interval-aware).
        """
        for attendance in self:
            if attendance.punishment_hours:
                attendance.worked_hours = attendance.punishment_hours
                continue

            # Standard Odoo logic (verbatim from hr_attendance.py)
            if attendance.check_out and attendance.check_in and attendance.employee_id:
                calendar = attendance._get_employee_calendar()
                resource = attendance.employee_id.resource_id
                tz = (
                    timezone(resource.tz)
                    if not calendar
                    else timezone(calendar.tz)
                )
                check_in_tz  = attendance.check_in.astimezone(tz)
                check_out_tz = attendance.check_out.astimezone(tz)
                lunch_intervals = []
                if not resource._is_flexible():
                    lunch_intervals = attendance.employee_id \
                        ._employee_attendance_intervals(check_in_tz, check_out_tz, lunch=True)
                attendance_intervals = (
                    Intervals([(check_in_tz, check_out_tz, attendance)])
                    - lunch_intervals
                )
                delta = sum(
                    (i[1] - i[0]).total_seconds() for i in attendance_intervals
                )
                attendance.worked_hours = delta / 3600.0
            else:
                attendance.worked_hours = False

    # ── Constraint: Pre Check-In Tolerance (block mode only) ─────────────────

    @api.constrains('check_in', 'employee_id')
    def _check_pre_checkin_tolerance(self):
        """Block check-in strictly before (shift_start − pre_checkin_tolerance)."""
        for record in self:
            if not record.check_in or not record.employee_id:
                continue

            company, resource_calendar, shift_tz = self._resolve_shift_context(record)
            if not resource_calendar:
                continue

            tolerance_hours = company.attendance_pre_checkin_tolerance
            if not tolerance_hours:
                continue

            check_in_local = utc.localize(record.check_in).astimezone(shift_tz)
            shift_start_hour, _ = self._get_shift_bounds(check_in_local, resource_calendar)
            if shift_start_hour is None:
                continue

            shift_start_utc = self._shift_bound_as_utc(
                record.check_in, shift_tz, shift_start_hour
            )
            earliest_utc = shift_start_utc - timedelta(hours=tolerance_hours)

            if record.check_in < earliest_utc:
                earliest_local = utc.localize(earliest_utc).astimezone(shift_tz)
                raise ValidationError(_t(
                    "Early check-in not allowed!\n\n"
                    "Employee         : %(employee)s\n"
                    "Shift starts at  : %(shift)s\n"
                    "Tolerance        : %(tol).2f hour(s)\n"
                    "Earliest allowed : %(earliest)s\n"
                    "Attempted        : %(actual)s\n\n"
                    "Please check in at or after %(earliest)s.",
                    employee=record.employee_id.name,
                    shift=_hours_to_hhmm(shift_start_hour),
                    tol=tolerance_hours,
                    earliest=earliest_local.strftime('%H:%M'),
                    actual=check_in_local.strftime('%H:%M'),
                ))

    # ── Constraint: Late check-out block (when base_punishment == 0) ─────────

    @api.constrains('check_out', 'check_in', 'employee_id')
    def _check_post_checkout_tolerance(self):
        """
        When base_punishment == 0 (block mode): raise error on late check-out.
        When base_punishment > 0: punishment_hours handles it via compute — no action needed here.
        """
        for record in self:
            if not record.check_out or not record.check_in or not record.employee_id:
                continue

            company, resource_calendar, shift_tz = self._resolve_shift_context(record)
            if not resource_calendar:
                continue

            post_tol = company.attendance_post_checkout_tolerance
            if not post_tol:
                continue

            # If punishment hours configured → compute method handles it silently
            if company.attendance_checkout_punishment_hours:
                continue

            # Block mode: no punishment configured → raise error
            check_in_local = utc.localize(record.check_in).astimezone(shift_tz)
            _, shift_end_hour = self._get_shift_bounds(check_in_local, resource_calendar)
            if shift_end_hour is None:
                continue

            shift_end_utc      = self._shift_bound_as_utc(record.check_in, shift_tz, shift_end_hour)
            latest_allowed_utc = shift_end_utc + timedelta(hours=post_tol)

            if record.check_out > latest_allowed_utc:
                latest_local = utc.localize(latest_allowed_utc).astimezone(shift_tz)
                actual_local = utc.localize(record.check_out).astimezone(shift_tz)
                raise ValidationError(_t(
                    "Late check-out not allowed!\n\n"
                    "Employee              : %(employee)s\n"
                    "Shift ends at         : %(shift_end)s\n"
                    "Post Check-Out Tol.   : %(tol).2f hour(s)\n"
                    "Latest allowed        : %(latest)s\n"
                    "Attempted             : %(actual)s\n\n"
                    "Check-out after %(latest)s is not permitted.",
                    employee=record.employee_id.name,
                    shift_end=_hours_to_hhmm(shift_end_hour),
                    tol=post_tol,
                    latest=latest_local.strftime('%H:%M'),
                    actual=actual_local.strftime('%H:%M'),
                ))

    # ── Cron: Forgotten check-outs (Case 1) ──────────────────────────────────

    @api.model
    def _cron_missed_checkout_punishment(self):
        """
        Case 1 — Daily cron for forgotten check-outs.

        Sets a synthetic check_out = shift_end + post_tolerance on any open
        attendance whose check_in is from a previous day.  Once check_out is
        set, _compute_punishment_hours and _compute_worked_hours handle the
        rest automatically on next recompute.

        Timeline example  (shift 08:00-18:00, post_tol=2 h, base=5 h)
        ----------------------------------------------------------------
        Employee A  check_in 08:00 yesterday  → check_out set to 20:00
                    → punishment=5 h  → Worked Time 05:00

        Employee B  check_in 10:00 yesterday  → check_out set to 20:00
                    → punishment=3 h  → Worked Time 03:00

        Employee C  check_in 13:30 yesterday  → check_out set to 20:00
                    → punishment=0 h  → Worked Time 00:00
        """
        now_utc = datetime.utcnow()

        open_records = self.search([('check_out', '=', False)])
        if not open_records:
            return

        for record in open_records:
            if not record.check_in or not record.employee_id:
                continue

            company, resource_calendar, shift_tz = self._resolve_shift_context(record)

            check_in_local = utc.localize(record.check_in).astimezone(shift_tz)
            now_local      = utc.localize(now_utc).astimezone(shift_tz)

            # Only process records whose check_in is on a previous local date
            if check_in_local.date() >= now_local.date():
                continue

            if not resource_calendar:
                # No calendar — close at now with zero hours
                record.sudo().write({'check_out': now_utc})
                continue

            shift_start_hour, shift_end_hour = self._get_shift_bounds(
                check_in_local, resource_calendar
            )

            if shift_end_hour is None:
                record.sudo().write({'check_out': now_utc})
                continue

            post_tol          = company.attendance_post_checkout_tolerance
            shift_end_utc     = self._shift_bound_as_utc(record.check_in, shift_tz, shift_end_hour)
            auto_checkout_utc = shift_end_utc + timedelta(hours=post_tol)

            # Cap to now if still in the future
            if auto_checkout_utc > now_utc:
                auto_checkout_utc = now_utc

            # Writing check_out triggers recompute of punishment_hours and worked_hours
            record.sudo().write({'check_out': auto_checkout_utc})

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _resolve_shift_context(self, record):
        company = record.employee_id.company_id or self.env.company
        resource_calendar = (
            record.employee_id.resource_calendar_id
            or company.resource_calendar_id
        )
        if not resource_calendar:
            return company, None, None
        shift_tz = self._get_shift_tz(resource_calendar, company)
        return company, resource_calendar, shift_tz

    def _get_shift_tz(self, resource_calendar, company):
        for tz_str in (
            getattr(resource_calendar, 'tz', None),
            getattr(getattr(company, 'partner_id', None), 'tz', None),
        ):
            if tz_str:
                try:
                    return pytz.timezone(tz_str)
                except pytz.UnknownTimeZoneError:
                    pass
        return utc

    def _get_shift_bounds(self, dt_local, resource_calendar):
        dow = str(dt_local.weekday())
        lines = resource_calendar.attendance_ids.filtered(
            lambda a: a.dayofweek == dow
        )
        if not lines:
            return None, None
        return min(lines.mapped('hour_from')), max(lines.mapped('hour_to'))

    def _shift_bound_as_utc(self, check_in_utc_naive, shift_tz, decimal_hour):
        check_in_local = utc.localize(check_in_utc_naive).astimezone(shift_tz)
        h = int(decimal_hour)
        m = round((decimal_hour % 1) * 60)
        shift_local = check_in_local.replace(hour=h, minute=m, second=0, microsecond=0)
        return shift_local.astimezone(utc).replace(tzinfo=None)

    def _compute_achieved_punishment(self, record, base_punishment, shift_tz, shift_start_hour):
        if not record.check_in or shift_start_hour is None:
            return base_punishment
        check_in_local = utc.localize(record.check_in).astimezone(shift_tz)
        check_in_decimal = (
            check_in_local.hour
            + check_in_local.minute / 60.0
            + check_in_local.second / 3600.0
        )
        late_hours = max(0.0, check_in_decimal - shift_start_hour)
        return max(0.0, base_punishment - late_hours)

    # ── Optional: hook into Odoo's own auto-checkout cron ────────────────────

    def _cron_auto_check_out(self):
        """
        Extend Odoo's built-in auto-checkout cron if it exists.
        Since punishment_hours is now fully computed, no extra SQL needed —
        just call super() and the recompute handles everything.
        """
        try:
            return super()._cron_auto_check_out()
        except (NotImplementedError, AttributeError):
            return
