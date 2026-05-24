from odoo import models, fields


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    shift_code = fields.Char(string='Shift Code', required=True)
