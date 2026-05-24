from odoo import api, models, fields
import logging



class HREmployee(models.Model):
    _inherit = 'hr.employee'
    
    confirmation_date = fields.Date(string="Confirmation Date")

    allow_manual_attendance = fields.Boolean(
        string="Manual Attendance",
        help="If enabled, this employee can manually Check In/Check Out from portal."
    )


    provident_fund_amount = fields.Float(
        string="Total PF Amount",
        default=0.0,
        tracking=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    
    pf_deduct_amount = fields.Float(
        string="PF Monthly Deduction",
        default=0.0,
        tracking=True
    )
    
    
    blood_group = fields.Selection(
        [('a+', 'A+'), ('a-', 'A-'), ('b+', 'B+'), ('b-', 'B-'),
         ('ab+', 'AB+'), ('ab-', 'AB-'), ('o+', 'O+'), ('o-', 'O-')],
        string="Blood Group"
    )
    religion = fields.Char(string="Religion")


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    employee_barcode = fields.Char(
        string="Employee Barcode",
        related="employee_id.barcode",
        store=True,
        readonly=True
    )



