from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CompanyPolicy(models.Model):
    _name = 'company.policy'
    _description = 'Company Policies'
    _rec_name = 'title'
    _order = 'create_date desc'

    title = fields.Char(string="Policy Title", required=True)
    description = fields.Text(string="Policy Description")

    is_general = fields.Boolean(string="Is General Policy?")

    policy_type = fields.Selection([
        ('employee', 'By Employee'),
        ('department', 'By Department'),
        ('job', 'By Job Position'),  
    ], string="Policy Type")

    employee_ids = fields.Many2many(
        'hr.employee', 'company_policy_employee_rel',
        'policy_id', 'employee_id',
        string="Employees"
    )

    department_ids = fields.Many2many(
        'hr.department', 'company_policy_department_rel',
        'policy_id', 'department_id',
        string="Departments"
    )

  
    position_ids = fields.Many2many(
        'hr.job',
        'company_policy_job_rel',
        'policy_id',
        'job_id',
        string="Job Positions"
    )

    date_start = fields.Date(default=fields.Date.today(), required=True)
    date_end = fields.Date(default=fields.Date.today(), required=True)

    active = fields.Boolean(default=True)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start > rec.date_end:
                raise ValidationError(_("Start Date must be before End Date."))
