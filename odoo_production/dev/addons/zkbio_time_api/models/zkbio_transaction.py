# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZKBioTransaction(models.Model):
    _name = 'zkbio.transaction'
    _description = 'ZKBio Attendance Transaction'
    _order = 'punch_time desc'
    _rec_name = 'emp_code'

    # Employee Information
    emp_code = fields.Char(string='Employee Code', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', index=True)

    # Transaction Details
    punch_time = fields.Datetime(string='Punch Time', required=True, index=True)
    punch_state = fields.Char(string='Punch State')
    verify_type = fields.Integer(string='Verify Type')
    work_code = fields.Char(string='Work Code')

    # Terminal Information
    terminal_sn = fields.Char(string='Terminal Serial Number', index=True)
    terminal_id = fields.Many2one('zkbio.terminal', string='Terminal', index=True)
    terminal_alias = fields.Char(string='Terminal Name')

    # Upload Information
    upload_time = fields.Datetime(string='Upload Time')

    # Configuration
    config_id = fields.Many2one('zkbio.config', string='API Configuration', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', related='config_id.company_id', store=True)

    # Processing Status
    is_processed = fields.Boolean(string='Processed', default=False, index=True)
    hr_attendance_id = fields.Many2one('hr.attendance', string='HR Attendance', readonly=True)
    error_message = fields.Text(string='Error Message')

    # Additional Data
    temperature = fields.Float(string='Temperature')
    mask_flag = fields.Boolean(string='Wearing Mask')

    _sql_constraints = [
        ('unique_transaction', 'unique(emp_code, punch_time, terminal_sn, config_id)',
         'This transaction already exists!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-link employee and terminal"""
        # Ensure vals_list is always a list
        if not isinstance(vals_list, list):
            vals_list = [vals_list]

        for vals in vals_list:
            # Try to find employee by emp_code using multiple matching methods
            if vals.get('emp_code') and not vals.get('employee_id'):
                emp_code = vals['emp_code']

                # Method 1: Try barcode field (RFID/Badge Number - most common)
                employee = self.env['hr.employee'].search([
                    ('barcode', '=', emp_code)
                ], limit=1)

                # Method 2: Try PIN field if barcode didn't match
                if not employee:
                    employee = self.env['hr.employee'].search([
                        ('pin', '=', emp_code)
                    ], limit=1)

                # Method 3: Try identification_id field
                if not employee:
                    employee = self.env['hr.employee'].search([
                        ('identification_id', '=', emp_code)
                    ], limit=1)

                # Method 4: Try searching by name (exact match)
                if not employee:
                    employee = self.env['hr.employee'].search([
                        ('name', '=', emp_code)
                    ], limit=1)

                if employee:
                    vals['employee_id'] = employee.id
                    _logger.info(f"Matched employee {employee.name} (ID: {employee.id}) for emp_code: {emp_code}")
                else:
                    _logger.warning(f"No employee found for emp_code: {emp_code}")

            # Try to find terminal by serial number
            if vals.get('terminal_sn'):
                terminal = self.env['zkbio.terminal'].search([
                    ('serial_number', '=', vals['terminal_sn'])
                ], limit=1)
                if terminal:
                    vals['terminal_id'] = terminal.id
                    vals['terminal_alias'] = terminal.name

        return super(ZKBioTransaction, self).create(vals_list)

    def action_process_to_attendance(self):
        """
        Process transactions to HR Attendance using FIRST IN - LAST OUT per day logic.

        Rules:
        - For each employee, per day:
          * First punch of the day = Check In
          * Last punch of the day = Check Out
          * All middle punches = Ignored
        - If only 1 punch exists for the day, creates attendance with check-in only (no check-out)
        - Worked hours = Difference between first & last punch

        Example:
          09:02 → Check In
          01:05 → Ignored
          02:00 → Ignored
          05:18 → Check Out
          Result: One attendance record (09:02 - 05:18)
        """
        from datetime import datetime

        # Process only unprocessed transactions with employee linked
        transactions_to_process = self.filtered(lambda r: not r.is_processed and r.employee_id and r.punch_time)

        if not transactions_to_process:
            _logger.info("No valid transactions to process")
            return

        # Group transactions by employee and date
        grouped_transactions = {}
        for trans in transactions_to_process:
            # Extract date from punch_time (UTC datetime stored in Odoo)
            punch_date = trans.punch_time.date()
            key = (trans.employee_id.id, punch_date)

            if key not in grouped_transactions:
                grouped_transactions[key] = []
            grouped_transactions[key].append(trans)

        _logger.info(f"Processing {len(transactions_to_process)} transactions grouped into {len(grouped_transactions)} employee-days")

        # Process each employee-day group
        for (employee_id, punch_date), trans_list in grouped_transactions.items():
            employee = self.env['hr.employee'].browse(employee_id)

            # Sort transactions by punch_time (ascending - oldest first)
            trans_list.sort(key=lambda t: t.punch_time)

            # Get first and last punch
            first_trans = trans_list[0]
            last_trans = trans_list[-1]

            first_punch = first_trans.punch_time
            last_punch = last_trans.punch_time if len(trans_list) > 1 else False

            try:
                # Check if attendance already exists for this date
                # Look for attendance where check_in is on the same date
                existing_attendance = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee_id),
                    ('check_in', '>=', datetime.combine(punch_date, datetime.min.time())),
                    ('check_in', '<', datetime.combine(punch_date, datetime.max.time()))
                ], limit=1, order='check_in asc')

                if existing_attendance:
                    # Update existing attendance
                    update_vals = {}

                    # Update check-in if our first punch is earlier
                    if first_punch < existing_attendance.check_in:
                        update_vals['check_in'] = first_punch

                    # Update check-out if we have a last punch
                    if last_punch:
                        if not existing_attendance.check_out or last_punch > existing_attendance.check_out:
                            update_vals['check_out'] = last_punch

                    if update_vals:
                        existing_attendance.write(update_vals)
                        _logger.info(f"Updated attendance {existing_attendance.id} for {employee.name} on {punch_date}: {update_vals}")

                    # Link all transactions to this attendance
                    for trans in trans_list:
                        trans.write({
                            'is_processed': True,
                            'hr_attendance_id': existing_attendance.id,
                            'error_message': False
                        })

                    _logger.info(f"Linked {len(trans_list)} transactions to existing attendance {existing_attendance.id}")

                else:
                    # Create new attendance record
                    attendance_vals = {
                        'employee_id': employee_id,
                        'check_in': first_punch,
                    }

                    if last_punch:
                        attendance_vals['check_out'] = last_punch

                    attendance = self.env['hr.attendance'].create(attendance_vals)

                    # Link all transactions to this attendance
                    for trans in trans_list:
                        trans.write({
                            'is_processed': True,
                            'hr_attendance_id': attendance.id,
                            'error_message': False
                        })

                    punch_summary = f"{len(trans_list)} punches"
                    time_info = f"Check-In: {first_punch}"
                    if last_punch:
                        time_info += f", Check-Out: {last_punch}"

                    _logger.info(f"Created attendance {attendance.id} for {employee.name} on {punch_date} with {punch_summary} ({time_info})")

            except Exception as e:
                error_msg = f"Processing failed: {str(e)}"
                _logger.error(f"Failed to process transactions for {employee.name} on {punch_date}: {str(e)}", exc_info=True)

                # Mark all transactions in this group with error
                for trans in trans_list:
                    trans.write({'error_message': error_msg})

    def action_process_batch(self):
        """
        Process multiple transactions to HR Attendance using First IN - Last OUT per day logic.
        This method groups all transactions by employee and date, then creates one attendance
        record per employee per day with first punch as check-in and last punch as check-out.
        """
        # Count initial state
        initial_unprocessed = len(self.filtered(lambda r: not r.is_processed))

        _logger.info(f"Starting batch processing of {initial_unprocessed} unprocessed transactions")

        # Call the main processing method (it handles grouping and batch processing internally)
        self.action_process_to_attendance()

        # Count results after processing
        processed_count = len(self.filtered(lambda r: r.is_processed))
        failed_count = len(self.filtered(lambda r: not r.is_processed and r.error_message))
        no_employee_count = len(self.filtered(lambda r: not r.is_processed and not r.employee_id and not r.error_message))

        # Build notification message
        message = f'Processed {processed_count} transactions to Attendance Logs using First IN - Last OUT per day logic'
        if failed_count > 0:
            message += f', {failed_count} failed (check error messages)'
        if no_employee_count > 0:
            message += f', {no_employee_count} awaiting employee match'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Processing Complete'),
                'message': _(message),
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': False,
            }
        }

    def action_retry_failed(self):
        """Retry processing failed transactions using First IN - Last OUT per day logic"""
        failed = self.filtered(lambda r: not r.is_processed and r.error_message)

        _logger.info(f"Retrying {len(failed)} failed transactions")

        # Clear error messages and retry with batch processing
        failed.write({'error_message': False})
        failed.action_process_to_attendance()

        processed_count = len(failed.filtered(lambda r: r.is_processed))
        still_failed = len(failed.filtered(lambda r: not r.is_processed))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Retry Complete'),
                'message': _(f'Successfully processed {processed_count} transactions, {still_failed} still failed'),
                'type': 'success' if still_failed == 0 else 'warning',
                'sticky': False,
            }
        }
