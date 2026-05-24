from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_pre_checkin_tolerance = fields.Float(
        related='company_id.attendance_pre_checkin_tolerance',
        readonly=False,
        string='Pre Check-In Tolerance',
    )

    attendance_post_checkout_tolerance = fields.Float(
        related='company_id.attendance_post_checkout_tolerance',
        readonly=False,
        string='Post Check-Out Tolerance',
    )

    attendance_checkout_punishment_hours = fields.Float(
        related='company_id.attendance_checkout_punishment_hours',
        readonly=False,
        string='Punishment Hours of Check-Out',
    )
