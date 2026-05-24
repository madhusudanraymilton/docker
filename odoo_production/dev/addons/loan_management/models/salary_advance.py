# hr_salary_advance.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HRSalaryAdvance(models.Model):
    _name = 'hr.salary.advance'
    _description = 'HR Salary Advance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    # Basic Information
    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default=lambda self: _('New')
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True
    )
    
    # Auto-set partner from employee
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        compute='_compute_partner_id',
        store=True,
        readonly=True,
        help="Automatically set from employee's related partner"
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    
    amount = fields.Monetary(
        string='Advance Amount',
        required=True,
        tracking=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    
    # State Management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    # Accounting fields
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain=[('type', 'in', ['general', 'cash', 'bank'])],
        required=True
    )
    
    account_debit = fields.Many2one(
        'account.account',
        string='Debit Account',
       
        required=True
    )
    
    account_credit = fields.Many2one(
        'account.account',
        string='Credit Account',
        required=True
    )
    
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True
    )
    
    # Additional Information
    reason = fields.Text(
        string='Purpose/Reason',
        help='Reason for salary advance'
    )
    
    notes = fields.Text(string='Notes')
    
    # Department and Job Position (for reporting)
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True
    )
    
    job_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        related='employee_id.job_id',
        store=True
    )
    
    # Deduction Information
    deduction_month = fields.Date(
        string='Deduction Month',
        help='Month when advance will be deducted from salary'
    )
    
    # Sequence generation
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.salary.advance') or _('New')
        return super(HRSalaryAdvance, self).create(vals_list)
    
    @api.depends('employee_id')
    def _compute_partner_id(self):
        """Automatically set partner from employee's related partner"""
        for advance in self:
            if advance.employee_id:
                # Get the partner from employee's user
                if advance.employee_id.user_id:
                    advance.partner_id = advance.employee_id.user_id.partner_id.id
                else:
                    # If employee doesn't have user, search by name
                    partner = self.env['res.partner'].search([
                        ('name', 'ilike', advance.employee_id.name),
                        ('is_company', '=', False)
                    ], limit=1)
                    if not partner:
                        # Create new partner
                        partner = self.env['res.partner'].create({
                            'name': advance.employee_id.name,
                            'is_company': False,
                        })
                    advance.partner_id = partner.id
            else:
                advance.partner_id = False
    
    # State change methods
    def action_submit(self):
        for advance in self:
            advance.write({'state': 'submitted'})
    
    def action_approve(self):
        for advance in self:
            advance.write({'state': 'approved'})
    
    def action_reject(self):
        for advance in self:
            advance.write({'state': 'rejected'})
    
    def action_pay(self):
        """Create accounting entry for salary advance payment"""
        for advance in self:
            if advance.state != 'approved':
                raise ValidationError(_('Only approved advances can be paid.'))
            
            if not advance.journal_id or not advance.account_debit or not advance.account_credit:
                raise ValidationError(_('Please configure accounting fields before payment.'))
            
            # Create accounting entry
            move_vals = {
                'journal_id': advance.journal_id.id,
                'date': advance.date,
                'ref': advance.name,
                'partner_id': advance.partner_id.id if advance.partner_id else False,
                'line_ids': [
                    (0, 0, {
                        'account_id': advance.account_debit.id,
                        'debit': advance.amount,
                        'credit': 0,
                        'name': _('Salary Advance to %s') % advance.employee_id.name,
                        'partner_id': advance.partner_id.id if advance.partner_id else False,
                    }),
                    (0, 0, {
                        'account_id': advance.account_credit.id,
                        'debit': 0,
                        'credit': advance.amount,
                        'name': _('Salary Advance from %s') % advance.employee_id.name,
                        'partner_id': advance.partner_id.id if advance.partner_id else False,
                    }),
                ],
            }
            
            move = self.env['account.move'].create(move_vals)
            move.action_post()
            
            # Update advance record
            advance.write({
                'state': 'paid',
                'move_id': move.id
            })
    
    def action_cancel_payment(self):
        """Cancel the payment and accounting entry"""
        for advance in self:
            if advance.state == 'paid' and advance.move_id:
                advance.move_id.button_cancel()
                advance.move_id.unlink()
                advance.write({'state': 'approved', 'move_id': False})
    
    def action_set_to_draft(self):
        for advance in self:
            advance.write({'state': 'draft'})
    
    # Constraints
    @api.constrains('amount')
    def _check_amount(self):
        for advance in self:
            if advance.amount <= 0:
                raise ValidationError(_('Advance amount must be greater than zero.'))
    
    @api.constrains('date')
    def _check_date(self):
        for advance in self:
            if advance.date > fields.Date.today():
                raise ValidationError(_('Advance date cannot be in the future.'))
            
    def action_print_report(self):
        """Print Salary Advance Report"""
        self.ensure_one()
        return self.env.ref('loan_management.action_report_salary_advance').report_action(self)
    
    
    
    
  # advanced salary debar logic  sohag code here 
    
    @api.constrains('employee_id', 'amount')
    def _check_employee_loan_and_wage(self):
        for advance in self:
            if not advance.employee_id:
                continue

            employee = advance.employee_id

            # -------------------------------
            # RULE 1: Block if active loan exists
            # -------------------------------
            active_loan = self.env['hr.loan'].search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['approved', 'disbursed', 'partially_paid'])
            ], limit=1)

            if active_loan:
                raise ValidationError(_(
                    "Salary Advance is not allowed.\n"
                    "Employee already has an active loan (%s)."
                ) % active_loan.name)

            # ------------------------------------------------
            # RULE 2: Advance amount must not exceed Wage
            # ------------------------------------------------
            if not employee.wage or employee.wage <= 0:
                raise ValidationError(_(
                    "Employee does not have a wage configured."
                ))

            if advance.amount > employee.wage:
                raise ValidationError(_(
                    "Salary Advance amount (%.2f) cannot be greater than "
                    "employee's monthly salary (%.2f)."
                ) % (advance.amount, employee.wage))
