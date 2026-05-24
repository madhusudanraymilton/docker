from odoo import api, models, fields

from odoo.exceptions import ValidationError

class AccountAsset(models.Model):
    _inherit = 'account.asset'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        help='Responsible Employee'
    )


    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        tracking=True,
    )


    location_id = fields.Many2one(
        'stock.location',
        string='Used in Location',
        tracking=True
    )


    partner_id = fields.Many2one(
        'res.partner',
        string="Vendor",
        tracking = True,
    )

    partner_ref = fields.Char(

        string="Vendor Reference",
        tracking = True
    )


    serial_no = fields.Char(
        string="Serial Number",
        required=True,
        tracking=True
    )


    batch_id = fields.Char(

        string="Batch",
        tracking=True
    )

    # batch_id = fields.Many2one(
    #     'asset.batch',
    #     string="Batch",
    #     tracking=True
    # )

    effective_date = fields.Date(
        string="Effective Date",
        tracking=True
    )

    cost = fields.Monetary(
        string="Cost",
        currency_field='currency_id',
        tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        default=lambda self: self.env.company.currency_id
    )

    warranty_expiration_date = fields.Date(
        string="Warranty Expiration Date",
        tracking=True
    )




    @api.constrains('serial_no')
    def _check_serial(self):
        for record in self:
            if record.serial_no:
                if not record.serial_no.startswith('#'):
                    raise ValidationError("Serial must start with '#'")

                existing = self.search([
                    ('serial_no', '=', record.serial_no),
                    ('id', '!=', record.id)
                ], limit=1)

                if existing:
                    raise ValidationError("Serial Number must be unique!")

    
    @api.onchange('serial_no')
    def _onchange_serial_no(self):

        if self.serial_no and not self.serial_no.startswith('#'):
            self.serial_no = '#' + self.serial_no


    appreciation_account_id = fields.Many2one(
        'account.account',
        string='Appreciation Account',
        help='Account used for asset appreciation entries.'
    )

    income_account_id = fields.Many2one(
        'account.account',
        string='Income Account',
        help='Account used for asset income or appreciation entries.'
    )


    assignment_history_ids = fields.One2many(
        'account.asset.assignment',
        'asset_id',
        string="Assignment History"
    )

    # current_employee_id = fields.Many2one(
    #     'hr.employee',
    #     string='Currently Assigned To',
    #     compute='_compute_current_employee',
    #     store=True
    # )

    # @api.depends('employee_id')
    # def _compute_current_employee(self):
    #     for asset in self:
    #         asset.current_employee = asset.employee_id



    already_appreciated_amount_import = fields.Monetary(
        string='Appreciation Amount',
        tracking=True,
        states={'draft': [('readonly', False)]},
        readonly=True, 
        help='Value already appreciated before importing this asset.'
    )


    def action_assign_asset(self):
        self.ensure_one()

        active_assignment = self.assignment_history_ids.filtered(
            lambda l: l.state == 'assigned'
        )

        if active_assignment:
            active_assignment.write({
                'end_date': fields.Date.today(),
                'state': 'returned'
            })

        self.env['account.asset.assignment'].create({
            'asset_id': self.id,
            'employee_id': self.employee_id.id,
            'start_date': fields.Date.today(),
            'state': 'assigned'
        })


    




# class AssetBatch(models.Model):
#     _name = 'asset.batch'
#     _description = 'Asset Batch'

#     name = fields.Char(
#         string="Batch Code",
#         required=True,
#         copy=False
#     )

#     asset_ids = fields.One2many(
#         'account.asset',
#         'batch_id',
#         string="Assets"
#     )

   