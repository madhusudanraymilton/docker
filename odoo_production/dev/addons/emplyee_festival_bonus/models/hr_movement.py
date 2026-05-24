from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class HrLeaveMovement(models.Model):
    _inherit = 'hr.leave'

    movement_type = fields.Selection([
        ('personal', 'Personal Movement'),
        ('company',  'Company Movement'),
    ], string="Movement Type")

    is_movement = fields.Boolean(string="Is Movement", default=False)

    supporting_document = fields.Binary(string="Supporting Document", attachment=True)
    supporting_document_name = fields.Char(string="Document Name")


    def _raw_hours(self):
        if self.date_from and self.date_to:
            return (self.date_to - self.date_from).total_seconds() / 3600.0
        return 0.0


    def _compute_date_from(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            super(HrLeaveMovement, rest)._compute_date_from()

    def _compute_date_to(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            super(HrLeaveMovement, rest)._compute_date_to()

    def _compute_date_from_to(self):
        """Odoo 17/18/19 combined compute that replaces the two above."""
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._compute_date_from_to()
            except (AttributeError, Exception) as e:
                _logger.debug("_compute_date_from_to non-mv: %s", e)

    def _inverse_date_from(self):
        """Called when date_from is written via ORM.
        Default implementation snaps to 08:00 via _get_work_limits().
        Skip for movements so the user's exact time is preserved."""
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._inverse_date_from()
            except Exception as e:
                _logger.debug("_inverse_date_from non-mv: %s", e)

    def _inverse_date_to(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._inverse_date_to()
            except Exception as e:
                _logger.debug("_inverse_date_to non-mv: %s", e)



    @api.depends('date_from', 'date_to', 'is_movement', 'employee_id',
                 'holiday_status_id', 'state')
    def _compute_description(self):
        mv   = self.filtered(lambda l: l.is_movement)
        rest = self - mv
        if rest:
            try:
                super(HrLeaveMovement, rest)._compute_description()
            except Exception as e:
                _logger.debug("_compute_description non-mv: %s", e)

        for leave in mv:
            hours = leave._raw_hours()
            h     = int(hours)
            m     = int(round((hours - h) * 60))
            hr_label   = f"{h}:{str(m).zfill(2)}"
            date_label = ''
            if leave.date_from:
                try:
                    from pytz import utc as pytz_utc, timezone as pytz_tz
                    tz         = pytz_tz(leave.env.user.tz or 'UTC')
                    local_dt   = pytz_utc.localize(leave.date_from).astimezone(tz)
                    date_label = local_dt.strftime('(%m/%d/%Y)')
                except Exception:
                    date_label = str(leave.date_from.date())
            emp_name = leave.employee_id.name or 'Employee'
            try:
                leave.name = f"{emp_name} on Movement: {hr_label} hours {date_label}"
            except Exception:
                pass  

    @api.depends('date_from', 'date_to', 'is_movement', 'employee_id')
    def _compute_number_of_hours(self):
        mv, rest = self.filtered(lambda l: l.is_movement), self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._compute_number_of_hours()
            except Exception:
                pass
        for leave in mv:
            h = leave._raw_hours()
            try:
                leave.number_of_hours = h
            except Exception:
                pass
            try:
                leave.number_of_days = h / 8.0
            except Exception:
                pass

    @api.depends('date_from', 'date_to', 'is_movement')
    def _compute_number_of_hours_display(self):
        mv, rest = self.filtered(lambda l: l.is_movement), self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._compute_number_of_hours_display()
            except Exception:
                pass
        for leave in mv:
            try:
                leave.number_of_hours_display = leave._raw_hours()
            except Exception:
                pass

    @api.depends('date_from', 'date_to', 'is_movement', 'employee_id', 'holiday_status_id')
    def _compute_duration_display(self):
        mv, rest = self.filtered(lambda l: l.is_movement), self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._compute_duration_display()
            except Exception:
                pass
        for leave in mv:
            h_total = leave._raw_hours()
            h = int(h_total)
            m = int(round((h_total - h) * 60))
            try:
                leave.duration_display = f"{h}h {m}m" if m else f"{h}h"
            except Exception:
                pass


    def _check_date(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            super(HrLeaveMovement, rest)._check_date()

    def _check_date_and_days(self, values=None):
        rest = self.filtered(lambda l: not l.is_movement)
        if not rest:
            return
        try:
            if values is not None:
                super(HrLeaveMovement, rest)._check_date_and_days(values)
            else:
                super(HrLeaveMovement, rest)._check_date_and_days()
        except TypeError:
            try:
                super(HrLeaveMovement, rest)._check_date_and_days()
            except Exception:
                pass

    def _check_validity(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._check_validity()
            except Exception:
                pass

    def _check_work_schedule(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._check_work_schedule()
            except Exception:
                pass

    def _check_work_days(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._check_work_days()
            except Exception:
                pass

    def _validate_leave_request(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._validate_leave_request()
            except Exception:
                pass

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_date_state(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._check_date_state()
            except Exception:
                pass

    @api.constrains('date_from', 'date_to', 'employee_id', 'state')
    def _check_date_overlaps(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._check_date_overlaps()
            except Exception:
                pass

    def _check_overlap(self):
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._check_overlap()
            except Exception:
                pass

    def _check_approval_update(self, state, **kwargs):
        """Odoo 19 added raise_if_not_possible kwarg — accept **kwargs."""
        rest = self.filtered(lambda l: not l.is_movement)
        if rest:
            try:
                super(HrLeaveMovement, rest)._check_approval_update(state, **kwargs)
            except Exception:
                pass
        return True


    def action_validate1(self):
        mv, rest = self.filtered(lambda l: l.is_movement), self.filtered(lambda l: not l.is_movement)
        res = True
        if rest:
            try:
                res = super(HrLeaveMovement, rest).action_validate1()
            except Exception as e:
                _logger.error("action_validate1 non-mv: %s", e)
        for leave in mv:
            try:
                leave.sudo()._write({'state': 'validate1'})
                _logger.info("Movement %s → validate1", leave.id)
            except Exception as e:
                _logger.error("action_validate1 mv %s: %s", leave.id, e)
        return res

    def action_validate(self):
        mv, rest = self.filtered(lambda l: l.is_movement), self.filtered(lambda l: not l.is_movement)
        res = True
        if rest:
            try:
                res = super(HrLeaveMovement, rest).action_validate()
            except Exception as e:
                _logger.error("action_validate non-mv: %s", e)
        for leave in mv:
            try:
                leave.sudo()._write({'state': 'validate'})
                _logger.info("Movement %s → validate", leave.id)
            except Exception as e:
                _logger.error("action_validate mv %s: %s", leave.id, e)
                continue
            try:
                leave.sudo()._write({'payslip_state': 'blocked'})
            except Exception:
                pass
            if leave.movement_type == 'personal':
                try:
                    leave._deduct_personal_attendance()
                except Exception as e:
                    _logger.error("Attendance deduction mv %s: %s", leave.id, e, exc_info=True)
        return res


    def _deduct_personal_attendance(self):
        date_from, date_to, employee = self.date_from, self.date_to, self.employee_id
        if not date_from or not date_to or not employee:
            return
        _logger.info("Deducting attendance mv=%s emp=%s %s→%s",
                     self.id, employee.name, date_from, date_to)
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '<', date_to),
            '|', ('check_out', '>', date_from), ('check_out', '=', False),
        ])
        for att in atts:
            ci, co = att.check_in, att.check_out
            if not co:
                att.write({'check_out': date_from}) if ci < date_from else att.sudo().unlink()
                continue
            if ci >= date_from and co <= date_to:
                att.sudo().unlink()
            elif ci < date_from and co > date_to:
                att.write({'check_out': date_from})
                self.env['hr.attendance'].sudo().create({
                    'employee_id': employee.id, 'check_in': date_to, 'check_out': co,
                })
            elif ci < date_from and co > date_from:
                att.write({'check_out': date_from})
            elif ci >= date_from and ci < date_to:
                att.write({'check_in': date_to}) if co > date_to else att.sudo().unlink()