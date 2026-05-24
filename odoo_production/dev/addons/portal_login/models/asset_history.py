from odoo import models, fields, api
from odoo.orm.model_classes import ValidationError

class AccountAssetAssignment(models.Model):
    _name = 'account.asset.assignment'
    _description = 'Asset Assignment History'
    _order = 'start_date desc'

    asset_id = fields.Many2one(
        'account.asset',
        string='Asset',
        required=True,
        ondelete='cascade'
    )


    product_id = fields.Many2one(
        related='asset_id.product_id',
        string="Product",
        store=True,
        readonly=True
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True
    )

    start_date = fields.Date(
        string='Assigned From',
        required=True,
        # default=fields.Date.today
    )

    end_date = fields.Date(
        string='Assigned To'
    )

    state = fields.Selection([
        ('assigned', 'Assigned'),
        ('returned', 'Returned')
    ],tracking=True, default='assigned')

    returned_condition = fields.Selection([
        ('good', 'Good'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
    ],tracking=True, string='Returned Condition')

    duration_days = fields.Integer(
        string='Total Days',
        compute='_compute_duration',
        store=True
    )


    @api.onchange('end_date')
    def _onchange_end_date(self):
        if self.end_date:
            self.state = 'returned'

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duration_days = (rec.end_date - rec.start_date).days
            else:
                rec.duration_days = 0


    @api.constrains('asset_id', 'state')
    def _check_active_assignment(self):
        for rec in self:
            if rec.state == 'assigned':
                existing = self.search([
                    ('asset_id', '=', rec.asset_id.id),
                    ('state', '=', 'assigned'),
                    ('id', '!=', rec.id)
                ])
                if existing:
                    raise ValidationError(
                        "This asset is already assigned to another employee."
                    )
    
    