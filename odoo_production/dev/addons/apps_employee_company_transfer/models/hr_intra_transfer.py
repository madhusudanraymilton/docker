# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date


class HrIntraTransfer(models.Model):
    _name = 'hr.intra.transfer'
    _description = 'Intra-Company Employee Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'id desc'

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Transfer reference must be unique!'),
    ]

    name = fields.Char(string='Reference', readonly=True, copy=False,
                       default=lambda self: _('New'), tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='employee_id.company_id', store=True, readonly=True)
    from_department_id = fields.Many2one('hr.department', string='From Department', tracking=True)
    to_department_id = fields.Many2one('hr.department', string='To Department', tracking=True)
    from_job_id = fields.Many2one('hr.job', string='From Job', tracking=True)
    to_job_id = fields.Many2one('hr.job', string='To Job', tracking=True)
    supervisor_id = fields.Many2one('hr.employee', string='New Supervisor', tracking=True)
    reporting_head_id = fields.Many2one('hr.employee', string='New Reporting Head', tracking=True)
    transfer_date = fields.Date(string='Transfer Date', required=True, tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'),
         ('transferred', 'Transferred'), ('rejected', 'Rejected')],
        string='Status', default='draft', tracking=True, readonly=True, copy=False)
    note = fields.Text(string='Notes')
    rejection_reason = fields.Text(string='Rejection Reason', tracking=True)

    # Stored originals for potential reversal
    original_department_id = fields.Many2one('hr.department', string='Original Department', readonly=True)
    original_job_id = fields.Many2one('hr.job', string='Original Job', readonly=True)
    original_supervisor_id = fields.Many2one('hr.employee', string='Original Supervisor', readonly=True)
    original_reporting_head_id = fields.Many2one('hr.employee', string='Original Reporting Head', readonly=True)

    # Searchable computed field for "This Year" filter (Odoo 19 compatible)
    is_this_year = fields.Boolean(
        string='Is This Year',
        compute='_compute_is_this_year',
        search='_search_is_this_year',
    )

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends('transfer_date')
    def _compute_is_this_year(self):
        current_year = date.today().year
        for rec in self:
            rec.is_this_year = bool(rec.transfer_date) and rec.transfer_date.year == current_year

    def _search_is_this_year(self, operator, value):
        current_year = date.today().year
        year_start = date(current_year, 1, 1)
        year_end = date(current_year, 12, 31)
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('transfer_date', '>=', year_start), ('transfer_date', '<=', year_end)]
        else:
            return ['|', ('transfer_date', '<', year_start), ('transfer_date', '>', year_end)]

   
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            emp = self.employee_id
            self.from_department_id = emp.department_id
            self.from_job_id = emp.job_id
            self.supervisor_id = emp.parent_id
            self.reporting_head_id = emp.coach_id

   
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.intra.transfer') or _('New')
        return super().create(vals_list)

    
    def action_submit(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft transfers can be submitted.'))
        self.write({'state': 'submitted'})
        self.message_post(body=_('Intra-company transfer request submitted for approval.'),
                          subtype_xmlid='mail.mt_note')
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_intra_transfer_submitted',
                            raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)

    def action_approve(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('Only submitted transfers can be approved.'))
        self.write({'state': 'approved'})
        self.message_post(body=_('Intra-company transfer request approved.'), subtype_xmlid='mail.mt_note')
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_intra_transfer_approved',
                            raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)

    def action_reject(self):
        self.ensure_one()
        if self.state not in ('submitted', 'approved'):
            raise UserError(_('Only submitted or approved transfers can be rejected.'))
        self.write({'state': 'rejected'})
        self.message_post(
            body=_('Transfer request rejected. Reason: %s') % (self.rejection_reason or _('No reason provided.')),
            subtype_xmlid='mail.mt_note')
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_intra_transfer_rejected',
                            raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)

    def action_transfer(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Only approved transfers can be executed.'))

        employee = self.employee_id

        self.write({
            'original_department_id': employee.department_id.id if employee.department_id else False,
            'original_job_id': employee.job_id.id if employee.job_id else False,
            'original_supervisor_id': employee.parent_id.id if employee.parent_id else False,
            'original_reporting_head_id': employee.coach_id.id if employee.coach_id else False,
        })

        update_vals = {
            'department_id': self.to_department_id.id if self.to_department_id else False,
            'job_id': self.to_job_id.id if self.to_job_id else False,
            'parent_id': self.supervisor_id.id if self.supervisor_id else False,
            'coach_id': self.reporting_head_id.id if self.reporting_head_id else False,
        }
        employee.write(update_vals)
        self.write({'state': 'transferred'})

        self.message_post(
            body=_('Employee %(emp)s transferred from %(from_dept)s to %(to_dept)s.') % {
                'emp': employee.name,
                'from_dept': self.from_department_id.name if self.from_department_id else _('N/A'),
                'to_dept': self.to_department_id.name if self.to_department_id else _('N/A'),
            }, subtype_xmlid='mail.mt_note')
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_intra_transfer_completed',
                            raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)
