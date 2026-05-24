from odoo import models, fields, api
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeExtended(models.Model):
    _inherit = 'hr.employee'

   
    portal_team_leader_id = fields.Many2one(
        'hr.employee',
        string='Portal Team Leader',
        help='Team leader who will approve leave requests from portal',
        domain=[('user_id.active', '=', True)]
    )
  
    barcode = fields.Char(
        string="Badge ID",
        help="ID used for employee identification.",
        copy=False,
        
        groups=False
    )

    # employee er expens 
    # asset_line_ids = fields.One2many(
    #     'employee.asset.line',
    #     'employee_id',
    #     string='Employee Assets'
    # )


       
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade'
    )

    responsible_person_id = fields.Many2one(
        'res.users',
        string='Responsible Person'
    )

    product_description = fields.Char(string='Product Description')
    serial_no = fields.Char(string='Serial No')
    quantity = fields.Integer(string='Quantity', default=1)

    reason = fields.Text(string='Reason')
    device_condition = fields.Selection([
        ('new', 'New'),
        ('used', 'Used'),
        ('damaged', 'Damaged'),
    ], string='Device Condition')

    issued_by_team = fields.Char(string='Issued By (Team)')
    returned_status = fields.Boolean(string='Returned')

    return_date = fields.Date(string='Return Date')
    return_device_condition = fields.Selection([
        ('good', 'Good'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
    ], string='Return Device Condition')

    remark = fields.Text(string='Remark')
    issue_date = fields.Date(string='Date')
    team_company_name = fields.Char(string='Team / Company Name')

    bill_allowance = fields.Float(string= "Bill Allowance")


    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        """
        Portal users can READ all active employees (for delegation)
        but model-level methods still apply (no write/create/unlink)
        """
       
        return super(HrEmployeeExtended, self).search(domain, offset=offset, limit=limit, order=order)

    def _read_format(self, fnames, load='_classic_read'):
        """
        Override _read_format to allow portal users to read barcode field
        This is called internally when reading records
        """
        if self.env.user.has_group('base.group_portal') and 'barcode' in fnames:
         
            return super(HrEmployeeExtended, self.sudo())._read_format(fnames, load=load)

        return super(HrEmployeeExtended, self)._read_format(fnames, load=load)

    def read(self, fields=None, load='_classic_read'):
        """
        Portal users can READ all active employees (for delegation dropdown)
        This is safe because they still can't modify any employee data
        """
     
        return super(HrEmployeeExtended, self).read(fields=fields, load=load)

    def write(self, vals):
        """
        Block manual edits by portal users, but allow internal system writes
        (e.g., login timezone sync, employee sync).
        """


        if self.env.su:
            return super().write(vals)

        
        if not self.env.user.has_group('base.group_portal'):
            return super().write(vals)

     
        if self.env.context.get('install_mode') or self.env.context.get('sync_employee'):
            return super().write(vals)

       
        raise AccessError("Portal users cannot modify employee records.")

    def create(self, vals_list):
        """
        Prevent portal users from creating employee records
        """
        if self.env.user.has_group('base.group_portal'):
            raise AccessError("Portal users cannot create employee records.")

        return super(HrEmployeeExtended, self).create(vals_list)

    def unlink(self):
        """
        Prevent portal users from deleting employee records
        """
        if self.env.user.has_group('base.group_portal'):
            raise AccessError("Portal users cannot delete employee records.")

        return super(HrEmployeeExtended, self).unlink()
