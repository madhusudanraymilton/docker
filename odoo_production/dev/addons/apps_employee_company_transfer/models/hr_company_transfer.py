# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date

_CONTRACT_MODEL = 'hr.' + 'contract'

class HrCompanyTransfer(models.Model):
    _name = 'hr.company.transfer'
    _description = 'Inter-Company Employee Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'id desc'


    name = fields.Char(string='Reference', readonly=True, copy=False,
                       default=lambda self: _('New'), tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    
    from_company_id = fields.Many2one('res.company', string='From Company', tracking=True, readonly=True)
    from_department_id = fields.Many2one('hr.department', string='From Department', tracking=True, readonly=True)
    from_job_id = fields.Many2one('hr.job', string='From Job Position', tracking=True, readonly=True)
    from_work_location_id = fields.Many2one('hr.work.location', string='From Work Location', tracking=True, readonly=True)
    from_address_id = fields.Many2one('res.partner', string='From Work Address', tracking=True, readonly=True)

    # To fields (editable in draft only)
    to_company_id = fields.Many2one('res.company', string='To Company', required=True, tracking=True)
    to_department_id = fields.Many2one('hr.department', string='To Department', tracking=True)
    to_job_id = fields.Many2one('hr.job', string='To Job Position', tracking=True)
    to_work_location_id = fields.Many2one('hr.work.location', string='To Work Location', tracking=True)
    to_address_id = fields.Many2one('res.partner', string='To Work Address', tracking=True)

    # Contract stored as Integer IDs to avoid triggering hr_contract module dependency
    from_contract_id_int = fields.Integer(string='Current Contract ID', copy=False)
    from_contract_name = fields.Char(string='Current Contract', compute='_compute_contract_names', store=False)
    new_contract_id_int = fields.Integer(string='New Contract ID', copy=False, readonly=True)
    new_contract_name = fields.Char(string='New Contract', compute='_compute_contract_names', store=False)
    original_contract_id_int = fields.Integer(string='Original Contract ID', copy=False, readonly=True)

    transfer_type = fields.Selection(
        [('permanent', 'Permanent'), ('temporary', 'Temporary')],
        string='Transfer Type', required=True, default='permanent', tracking=True)
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)
    duration_days = fields.Integer(string='Duration (Days)', compute='_compute_duration_days', store=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'),
         ('transferred', 'Transferred'), ('rejected', 'Rejected'), ('reversed', 'Reversed')],
        string='Status', default='draft', tracking=True, readonly=True, copy=False)
    grade = fields.Char(string='Grade', tracking=True)
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor', tracking=True)
    reporting_head_id = fields.Many2one('hr.employee', string='Reporting Head', tracking=True)
    leave_ids = fields.One2many('hr.leave.allocation', 'company_transfer_id', string='Leave Allocations')
    note = fields.Text(string='Notes')
    rejection_reason = fields.Text(string='Rejection Reason', tracking=True)

    # Original values for reversal
    original_company_id = fields.Many2one('res.company', string='Original Company', readonly=True)
    original_department_id = fields.Many2one('hr.department', string='Original Department', readonly=True)
    original_job_id = fields.Many2one('hr.job', string='Original Job', readonly=True)
    original_work_location_id = fields.Many2one('hr.work.location', string='Original Work Location', readonly=True)
    original_address_id = fields.Many2one('res.partner', string='Original Work Address', readonly=True)

    # Searchable computed field for "This Year" filter
    is_this_year = fields.Boolean(
        string='Is This Year',
        compute='_compute_is_this_year',
        search='_search_is_this_year',
    )

    def _contract_model(self):
        return self.env[_CONTRACT_MODEL] if _CONTRACT_MODEL in self.env else None

    def _get_contract(self, contract_id_int):
        if not contract_id_int:
            return None
        m = self._contract_model()
        if m is None:
            return None
        rec = m.sudo().browse(contract_id_int)
        return rec if rec.exists() else None

    @api.depends('from_contract_id_int', 'new_contract_id_int')
    def _compute_contract_names(self):
        for rec in self:
            c = rec._get_contract(rec.from_contract_id_int)
            rec.from_contract_name = c.name if c else ''
            c2 = rec._get_contract(rec.new_contract_id_int)
            rec.new_contract_name = c2.name if c2 else ''

    @api.depends('start_date', 'end_date')
    def _compute_duration_days(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duration_days = (rec.end_date - rec.start_date).days
            else:
                rec.duration_days = 0

    @api.depends('start_date')
    def _compute_is_this_year(self):
        current_year = date.today().year
        for rec in self:
            rec.is_this_year = bool(rec.start_date) and rec.start_date.year == current_year

    def _search_is_this_year(self, operator, value):
        current_year = date.today().year
        year_start = date(current_year, 1, 1)
        year_end = date(current_year, 12, 31)
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('start_date', '>=', year_start), ('start_date', '<=', year_end)]
        else:
            return ['|', ('start_date', '<', year_start), ('start_date', '>', year_end)]

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if not self.employee_id:
            return
        emp = self.employee_id
        self.from_company_id = emp.company_id
        self.from_department_id = emp.department_id
        self.from_job_id = emp.job_id
        self.from_work_location_id = emp.work_location_id if 'work_location_id' in emp._fields else False
        self.from_address_id = emp.address_id if 'address_id' in emp._fields else False
        self.supervisor_id = emp.parent_id
        self.reporting_head_id = emp.coach_id

        m = self._contract_model()
        if m is not None:
            contract = m.sudo().search(
                [('employee_id', '=', emp.id), ('state', 'in', ['open', 'running'])],
                order='date_start desc', limit=1)
            if not contract:
                contract = m.sudo().search(
                    [('employee_id', '=', emp.id), ('state', '!=', 'cancel')],
                    order='date_start desc', limit=1)
            self.from_contract_id_int = contract.id if contract else 0
        else:
            self.from_contract_id_int = 0

    @api.onchange('to_company_id')
    def _onchange_to_company_id(self):
        if not self.to_company_id:
            self.to_address_id = False
            self.to_work_location_id = False
            return
        self.to_address_id = self.to_company_id.partner_id if self.to_company_id.partner_id else False
        work_loc = self.env['hr.work.location'].search(
            [('company_id', '=', self.to_company_id.id)], limit=1)
        self.to_work_location_id = work_loc if work_loc else False

   
    @api.constrains('from_company_id', 'to_company_id')
    def _check_different_companies(self):
        for rec in self:
            if rec.from_company_id and rec.to_company_id and rec.from_company_id == rec.to_company_id:
                raise ValidationError(_(
                    'Source company and destination company must be different for an inter-company transfer.'))

    @api.constrains('start_date', 'end_date', 'transfer_type')
    def _check_dates(self):
        for rec in self:
            if rec.transfer_type == 'temporary':
                if not rec.end_date:
                    raise ValidationError(_('End date is required for temporary transfers.'))
                if rec.end_date <= rec.start_date:
                    raise ValidationError(_('End date must be after start date.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.company.transfer') or _('New')
        return super().create(vals_list)
    
    def action_submit(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft transfers can be submitted.'))
        self.write({'state': 'submitted'})
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_transfer_submitted', raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)

    def action_approve(self):
        self.ensure_one()
        if self.state == 'transferred':
            raise UserError(_('This transfer has already been executed. You cannot approve it again.'))
        if self.state != 'submitted':
            raise UserError(_('Only submitted transfers can be approved.'))
        self.write({'state': 'approved'})
        self.message_post(body=_('Transfer request approved.'), subtype_xmlid='mail.mt_note')
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_transfer_approved', raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)
        # Auto-execute transfer immediately after approval
        self.action_transfer()

    def action_reject(self):
        self.ensure_one()
        if self.state not in ('submitted', 'approved'):
            raise UserError(_('Only submitted or approved transfers can be rejected.'))
        self.write({'state': 'rejected'})
        self.message_post(
            body=_('Transfer request rejected. Reason: %s') % (self.rejection_reason or _('No reason provided.')),
            subtype_xmlid='mail.mt_note')
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_transfer_rejected', raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)

    def action_transfer(self):
        self.ensure_one()
        if self.state == 'transferred':
            # Already transferred — prevent duplicate execution silently
            return
        if self.state != 'approved':
            raise UserError(_('Only approved transfers can be executed.'))

        employee = self.employee_id

        # Save original values for possible reversal
        self.write({
            'original_company_id': employee.company_id.id,
            'original_department_id': employee.department_id.id if employee.department_id else False,
            'original_job_id': employee.job_id.id if employee.job_id else False,
            'original_contract_id_int': self.from_contract_id_int or 0,
            'original_work_location_id': employee.work_location_id.id if 'work_location_id' in employee._fields and employee.work_location_id else False,
            'original_address_id': employee.address_id.id if 'address_id' in employee._fields and employee.address_id else False,
        })

        old_contract = self._get_contract(self.from_contract_id_int)
        if old_contract:
            self._cancel_contract(old_contract)

        new_contract = self._create_new_contract()

        # Resolve work address
        new_address_id = (
            self.to_address_id.id if self.to_address_id
            else (self.to_company_id.partner_id.id if self.to_company_id.partner_id else False)
        )

        # Resolve work location
        if self.to_work_location_id:
            new_work_location_id = self.to_work_location_id.id
        else:
            wl = self.env['hr.work.location'].search(
                [('company_id', '=', self.to_company_id.id)], limit=1)
            new_work_location_id = wl.id if wl else False

        update_vals = {
            'company_id': self.to_company_id.id,
            'department_id': self.to_department_id.id if self.to_department_id else False,
            'job_id': self.to_job_id.id if self.to_job_id else False,
            'parent_id': self.supervisor_id.id if self.supervisor_id else False,
            'coach_id': self.reporting_head_id.id if self.reporting_head_id else False,
        }
        if 'address_id' in employee._fields:
            update_vals['address_id'] = new_address_id
        if 'work_location_id' in employee._fields:
            update_vals['work_location_id'] = new_work_location_id

        employee.sudo().write(update_vals)

        self._carry_forward_leaves()

        self.write({
            'state': 'transferred',
            'new_contract_id_int': new_contract.id if new_contract else 0,
        })
        
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_transfer_completed', raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)

    def _cancel_contract(self, contract):
        try:
            contract.sudo().write({'state': 'cancel'})
        except Exception:
            contract.sudo().write({'active': False})

    def _reactivate_contract(self, contract):
        for state in ('open', 'running'):
            try:
                contract.sudo().write({'state': state, 'active': True})
                return
            except Exception:
                continue
        contract.sudo().write({'active': True})

    def _create_new_contract(self):
        self.ensure_one()
        m = self._contract_model()
        if m is None:
            return False
        old = self._get_contract(self.from_contract_id_int)
        if not old:
            return False
        vals = {
            'name': _('Contract - %s - %s') % (self.employee_id.name, self.to_company_id.name),
            'employee_id': self.employee_id.id,
            'company_id': self.to_company_id.id,
            'department_id': self.to_department_id.id if self.to_department_id else False,
            'job_id': self.to_job_id.id if self.to_job_id else False,
            'date_start': self.start_date,
            'wage': old.wage,
            'state': 'open',
        }
        if self.transfer_type == 'temporary' and self.end_date:
            vals['date_end'] = self.end_date
        for fname in ('resource_calendar_id', 'structure_type_id', 'hr_responsible_id', 'currency_id'):
            if fname in m._fields:
                v = getattr(old, fname, False)
                if v:
                    vals[fname] = v.id
        for fname in ('notes', 'trial_date_end'):
            if fname in m._fields:
                v = getattr(old, fname, False)
                if v:
                    vals[fname] = v
        return m.sudo().create(vals)

    def _carry_forward_leaves(self):
        self.ensure_one()
        if 'hr.leave.allocation' not in self.env:
            return
        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
        ])
        new_ids = []
        for alloc in allocations:
            if alloc.number_of_days > 0:
                new_alloc = alloc.copy({
                    'employee_id': self.employee_id.id,
                    'number_of_days': alloc.number_of_days,
                    'company_transfer_id': self.id,
                })
                try:
                    new_alloc.action_validate()
                except Exception:
                    new_alloc.write({'state': 'validate'})
                new_ids.append(new_alloc.id)
        if new_ids:
            self.write({'leave_ids': [(4, nid) for nid in new_ids]})

    def action_reverse(self):
        self.ensure_one()
        if self.state != 'transferred':
            raise UserError(_('Only transferred records can be reversed.'))
        employee = self.employee_id

        orig_contract = self._get_contract(self.original_contract_id_int)
        if orig_contract:
            self._reactivate_contract(orig_contract)
        new_contract = self._get_contract(self.new_contract_id_int)
        if new_contract:
            self._cancel_contract(new_contract)

        restore_vals = {
            'company_id': self.original_company_id.id if self.original_company_id else employee.company_id.id,
            'department_id': self.original_department_id.id if self.original_department_id else False,
            'job_id': self.original_job_id.id if self.original_job_id else False,
        }
        if 'work_location_id' in employee._fields:
            restore_vals['work_location_id'] = self.original_work_location_id.id if self.original_work_location_id else False
        if 'address_id' in employee._fields:
            restore_vals['address_id'] = self.original_address_id.id if self.original_address_id else False

        employee.sudo().write(restore_vals)

        self.write({'state': 'reversed'})
        self.message_post(
            body=_('Transfer reversed. %s returned to %s.') % (
                employee.name,
                self.original_company_id.name if self.original_company_id else _('original company')),
            subtype_xmlid='mail.mt_note')
        tmpl = self.env.ref('apps_employee_company_transfer.email_template_transfer_reversal', raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)

    @api.model
    def _cron_check_temporary_transfer_expiry(self):
        today = fields.Date.today()
        expired = self.search([
            ('transfer_type', '=', 'temporary'),
            ('state', '=', 'transferred'),
            ('end_date', '<=', today),
        ])
        for transfer in expired:
            try:
                transfer.action_reverse()
                transfer.message_post(
                    body=_('Temporary transfer auto-reversed by scheduled action on %s.') % today,
                    subtype_xmlid='mail.mt_note')
            except Exception as e:
                transfer.message_post(
                    body=_('Auto-reversal failed: %s') % str(e),
                    subtype_xmlid='mail.mt_note')
