from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    

    tolerance_time = fields.Float(
        string='Tolerance Time (Minutes)',
        default=15,
        help='Tolerance time for late calculation in minutes'
    )

    lates_per_deduction = fields.Integer(
        string='Late Days for 1 Day Leave Deduction',
        default=3,
        help='Number of late days that equal 1 day leave deduction'
    )

    deduction_leave_type = fields.Selection([
        ('', 'No Deduction'), 
        ('cl', 'Casual Leave'),
        ('sl', 'Sick Leave'),
        ('ml', 'Medical Leave'),
        ('el', 'Earned Leave'),
        ('lop', 'Loss of Pay'),
    ], string='Deduction Leave Type', default='cl', help='Type of leave to deduct for late attendance')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            tolerance_time=float(params.get_param('hr_attendance_custom_report.tolerance_time', 15)),
            lates_per_deduction=int(params.get_param('hr_attendance_custom_report.lates_per_deduction', 3)),
            deduction_leave_type=params.get_param('hr_attendance_custom_report.deduction_leave_type', 'cl')
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'hr_attendance_custom_report.tolerance_time', 
            self.tolerance_time
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'hr_attendance_custom_report.lates_per_deduction', 
            self.lates_per_deduction
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'hr_attendance_custom_report.deduction_leave_type', 
            self.deduction_leave_type
        )