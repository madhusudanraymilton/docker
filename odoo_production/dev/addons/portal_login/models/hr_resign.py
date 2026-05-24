from odoo import models, fields, api
from odoo.exceptions import AccessError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrResign(models.Model):
    _name = 'hr.resign'
    _description = 'Employee Resignation Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New'
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True,
        ondelete='cascade'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True
    )

    job_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        related='employee_id.job_id',
        store=True,
        readonly=True
    )

    manager_id = fields.Many2one(
        'hr.employee',
        string='Reporting Manager',
        related='employee_id.parent_id',
        store=True,
        readonly=True
    )

    request_date = fields.Date(
        string='Application Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )

    notice_period_days = fields.Integer(
        string='Notice Period (Days)',
        default=30,
        required=True
    )

    last_working_date = fields.Date(
        string='Last Working Date',
        required=True,
        tracking=True
    )

    reason = fields.Text(
        string='Reason for Resignation',
        required=True,
        tracking=True
    )

    additional_notes = fields.Text(
        string='Additional Notes / Handover Details',
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('hr_review', 'Under HR Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)

    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True
    )

    approved_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )

    rejection_reason = fields.Text(
        string='Rejection / HR Notes',
        tracking=True
    )

    pdf_template = fields.Selection([
        ('new_opportunity', 'Resignation – New Opportunity'),
        ('advance_notice', 'Resignation – Advance Notice'),
        ('not_good_fit', 'Resignation – Not a Good Fit'),
    ], string='PDF Template', default='new_opportunity')

    joining_date = fields.Date(
        string='Joining Date',
        related='employee_id.contract_date_start',
        readonly=True,
        store=False
    )

    # ── Sequence ──────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.resign') or 'RES/0001'
        return super().create(vals_list)

    # ── State transitions ─────────────────────────────────────────
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError('Only draft resignation requests can be submitted.')
            rec.write({'state': 'submitted'})
            _logger.info(f"Resignation {rec.name} submitted by {self.env.user.name}")

    def action_hr_review(self):
        for rec in self:
            rec.write({'state': 'hr_review'})

    def action_approve(self):
        for rec in self:
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            # ── Auto-archive the employee on approval ──────────────
            if rec.employee_id and rec.employee_id.active:
                rec.employee_id.sudo().write({'active': False})
                _logger.info(
                    f"Employee {rec.employee_id.name} archived after resignation "
                    f"{rec.name} approved by {self.env.user.name}"
                )
            rec.message_post(
                body=f"✅ Resignation <b>approved</b> by {self.env.user.name}. "
                     f"Employee has been archived. Last working date: {rec.last_working_date}",
                message_type='notification',
            )

    def action_reject(self):
        for rec in self:
            rec.write({'state': 'rejected'})
            rec.message_post(
                body=f"❌ Resignation <b>rejected</b> by {self.env.user.name}.",
                message_type='notification',
            )

    # ── Smart button: open employee ────────────────────────────────
    def action_open_employee(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Employee',
            'res_model': 'hr.employee',
            'res_id': self.employee_id.id,
            'view_mode': 'form',
            'context': {'active_test': False},
        }

    def action_cancel(self):
        for rec in self:
            if rec.state in ['approved']:
                raise ValidationError('Approved resignations cannot be cancelled.')
            rec.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ['cancelled', 'rejected']:
                raise ValidationError('Only cancelled or rejected requests can be reset to draft.')
            rec.write({'state': 'draft'})

    # ── Portal security ────────────────────────────────────────────
    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        if self.env.user.has_group('base.group_portal'):
            self.env.cr.execute("""
                SELECT id FROM hr_employee
                WHERE user_id = %s AND active = true LIMIT 1
            """, (self.env.user.id,))
            result = self.env.cr.fetchone()
            if result:
                domain = [('employee_id', '=', result[0])] + (domain or [])
            else:
                domain = [('id', '=', False)]
        return super().search(domain, offset=offset, limit=limit, order=order)

    def read(self, fields=None, load='_classic_read'):
        if self.env.user.has_group('base.group_portal'):
            self.env.cr.execute("""
                SELECT id FROM hr_employee
                WHERE user_id = %s AND active = true LIMIT 1
            """, (self.env.user.id,))
            result = self.env.cr.fetchone()
            employee_id = result[0] if result else None
            for rec in self:
                if not employee_id or rec.employee_id.id != employee_id:
                    raise AccessError("You can only view your own resignation requests.")
        return super().read(fields=fields, load=load)

    def write(self, vals):
        if self.env.user.has_group('base.group_portal'):
            self.env.cr.execute("""
                SELECT id FROM hr_employee
                WHERE user_id = %s AND active = true LIMIT 1
            """, (self.env.user.id,))
            result = self.env.cr.fetchone()
            employee_id = result[0] if result else None
            for rec in self:
                if not employee_id or rec.employee_id.id != employee_id:
                    raise AccessError("You can only modify your own resignation requests.")
                if rec.state not in ['draft']:
                    raise AccessError("Submitted requests cannot be edited.")
        return super().write(vals)

    def unlink(self):
        if self.env.user.has_group('base.group_portal'):
            raise AccessError("Portal users cannot delete resignation requests.")
        return super().unlink()

    # ── Constraints ────────────────────────────────────────────────
    @api.constrains('request_date', 'last_working_date')
    def _check_dates(self):
        for rec in self:
            if rec.last_working_date and rec.request_date:
                if rec.last_working_date <= rec.request_date:
                    raise ValidationError('Last working date must be after the application date.')

    @api.constrains('employee_id', 'state')
    def _check_duplicate_active(self):
        for rec in self:
            if rec.state in ['submitted', 'hr_review', 'approved']:
                existing = self.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', 'in', ['submitted', 'hr_review', 'approved']),
                    ('id', '!=', rec.id),
                ])
                if existing:
                    raise ValidationError(
                        'An active resignation request already exists for this employee.'
                    )
