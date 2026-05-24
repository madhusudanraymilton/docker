from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    attendance_pre_checkin_tolerance = fields.Float(
        string='Pre Check-In Tolerance',
        default=0.0,
        help='Hours before shift start an employee is allowed to check in. 0 = disabled.',
    )

    attendance_post_checkout_tolerance = fields.Float(
        string='Post Check-Out Tolerance',
        default=0.0,
        help='Hours after shift end that an employee is allowed to check out. 0 = disabled.',
    )

    attendance_checkout_punishment_hours = fields.Float(
        string='Punishment Hours of Check-Out',
        default=0.0,
        help=(
            'If an employee checks out after the Post Check-Out Tolerance window, '
            'their worked hours are overwritten with this penalty value (check_out = check_in + punishment). '
            '0 = block with error instead of silent punishment.'
        ),
    )
