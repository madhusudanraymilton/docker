# loan.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date

class Loan(models.Model):
    _name = 'hr.loan'
    _description = 'Employee Loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(
        string='Loan Reference', 
        readonly=True, 
        copy=False, 
        default=lambda self: _('New')
    )

    employee_id = fields.Many2one(
        'hr.employee', 
        string='Employee Name', 
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

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        tracking=True
    )

    job_position_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        related='employee_id.job_id',
        store=True,
        tracking=True
    )

    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )

    loan_amount = fields.Monetary(
        string='Loan Amount',
        required=True,
        tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    no_of_installments = fields.Integer(
        string='Number of Installments',
        required=True,
        default=1,
        tracking=True
    )

    installment_amount = fields.Monetary(
        string='Installment Amount',
        compute='_compute_installment_amount',
        store=True
    )

    payment_start_date = fields.Date(
        string='Payment Start Date',
        required=True,
        tracking=True
    )

    # State Management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Fully Paid'),
    ], string='Status', default='draft', tracking=True)

    loan_line_ids = fields.One2many(
        'hr.loan.line',
        'loan_id',
        string='Loan Installments'
    )

    # Loan repayment tracking
    repayment_ids = fields.One2many('hr.loan.repayment', 'loan_id', string='Repayments')

    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_amounts',
        store=True
    )

    total_paid = fields.Monetary(
        string='Total Paid',
        compute='_compute_amounts',
        store=True
    )

    balance_amount = fields.Monetary(
        string='Balance Amount',
        compute='_compute_amounts',
        store=True
    )

    company_id = fields.Many2one(
        'res.company', 
        string='Company',
        default=lambda self: self.env.company
    )

    # Accounting fields
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain=[('type', 'in', ['general', 'cash'])]
    )
    account_debit = fields.Many2one('account.account', string='Debit Account')
    account_credit = fields.Many2one('account.account', string='Credit Account')
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)
    disbursement_date = fields.Date(string='Disbursement Date')
    
    # Additional Information
    reason = fields.Text(string='Purpose of Loan')
    notes = fields.Text(string='Notes')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.loan') or _('New')
        return super(Loan, self).create(vals_list)

    @api.depends('employee_id')
    def _compute_partner_id(self):
        """Automatically set partner from employee's related partner"""
        for loan in self:
            if loan.employee_id:
                # Get the partner from employee's user
                if loan.employee_id.user_id:
                    loan.partner_id = loan.employee_id.user_id.partner_id.id
                else:
                    # If employee doesn't have user, search by name
                    partner = self.env['res.partner'].search([
                        ('name', 'ilike', loan.employee_id.name),
                        ('is_company', '=', False)
                    ], limit=1)
                    if not partner:
                        # Create new partner
                        partner = self.env['res.partner'].create({
                            'name': loan.employee_id.name,
                            'is_company': False,
                        })
                    loan.partner_id = partner.id
            else:
                loan.partner_id = False

    @api.depends('loan_amount', 'no_of_installments')
    def _compute_installment_amount(self):
        for loan in self:
            if loan.no_of_installments > 0:
                loan.installment_amount = loan.loan_amount / loan.no_of_installments
            else:
                loan.installment_amount = 0.0

    @api.depends('loan_amount', 'repayment_ids.amount', 'loan_line_ids.repayment_id','repayment_ids.state' , 'loan_line_ids.state','loan_line_ids.amount','loan_line_ids.paid_amount')
    def _compute_amounts(self):
        for loan in self:
            loan.total_amount = loan.loan_amount
    
            total_paid = 0.0
            for line in loan.loan_line_ids:
                if line.state == 'paid':
                    total_paid += line.amount
                elif line.state == 'partial':
                    total_paid += line.paid_amount or 0.0

            loan.total_paid = total_paid
            loan.balance_amount = loan.loan_amount - total_paid

            if loan.state in ['disbursed', 'partially_paid', 'approved']:
                if loan.balance_amount <= 0:
                    loan.state = 'paid'
                elif loan.balance_amount < loan.loan_amount:
                    loan.state = 'partially_paid'

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})
        # Create payment schedule
        self._create_payment_schedule()

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_disburse(self):
        """Pay button action - disburse the loan"""
        self.write({'state': 'disbursed', 'disbursement_date': fields.Date.today()})
        self._create_accounting_entry()

    def action_pay(self):
        """Pay button action - disburse the loan"""
        self.action_disburse()
    
    def action_mark_as_paid(self):
        self.write({'state': 'paid'})
    
    def action_create_repayment(self):
        """Create and open repayment form from loan"""
        self.ensure_one()
        
        repayment_vals = {
            'loan_id': self.id,
            'date': fields.Date.today(),
            'amount': min(self.balance_amount, self.installment_amount) if self.installment_amount > 0 else self.balance_amount,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id,
            'account_debit': self.account_debit.id,
            'account_credit': self.account_credit.id,
        }
        
        repayment = self.env['hr.loan.repayment'].create(repayment_vals)
        
        return {
            'name': _('Record Repayment'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan.repayment',
            'view_mode': 'form',
            'res_id': repayment.id,
            'target': 'current',
            'context': {'default_loan_id': self.id},
        }
    
    def open_repayment(self):
        """Open repayment form (used in tree view button)"""
        self.ensure_one()
        return {
            'name': _('Repayment'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan.repayment',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def _create_payment_schedule(self):
        self.ensure_one()
        self.loan_line_ids.unlink()  # Remove existing lines

        payment_date = self.payment_start_date
        
        for i in range(self.no_of_installments):
            self.env['hr.loan.line'].create({
                'loan_id': self.id,
                'sequence': i + 1,
                'due_date': payment_date,
                'amount': self.installment_amount,
                'state': 'unpaid',
            })
            
            # Calculate next month
            if payment_date.month == 12:
                payment_date = payment_date.replace(year=payment_date.year + 1, month=1)
            else:
                payment_date = payment_date.replace(month=payment_date.month + 1)

    def _create_accounting_entry(self):
        self.ensure_one()

        if not self.journal_id or not self.account_debit or not self.account_credit:
            raise ValidationError(_("Please configure accounting fields before disbursement."))

        recipient_name = self.employee_id.name
        partner_id = self.partner_id.id if self.partner_id else False

        move_vals = {
            'journal_id': self.journal_id.id,
            'date': self.disbursement_date or fields.Date.today(),
            'ref': self.name,
            'partner_id': partner_id,  # Add partner_id to move header
            'line_ids': [
                (0, 0, {
                    'account_id': self.account_debit.id,
                    'debit': self.loan_amount,
                    'credit': 0,
                    'name': _('Loan Disbursement to %s') % recipient_name,
                    'partner_id': partner_id,
                }),
                (0, 0, {
                    'account_id': self.account_credit.id,
                    'debit': 0,
                    'credit': self.loan_amount,
                    'name': _('Loan Receivable from %s') % recipient_name,
                    'partner_id': partner_id,  # Add partner_id to credit line too
                }),
            ],
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()
        self.move_id = move.id
    
    @api.constrains('loan_amount')
    def _check_loan_amount(self):
        for loan in self:
            if loan.loan_amount <= 0:
                raise ValidationError(_('Loan amount must be greater than zero.'))
    
    @api.constrains('no_of_installments')
    def _check_installments(self):
        for loan in self:
            if loan.no_of_installments <= 0:
                raise ValidationError(_('Number of installments must be greater than zero.'))
    
    @api.constrains('payment_start_date')
    def _check_payment_start_date(self):
        for loan in self:
            if loan.payment_start_date < loan.date:
                raise ValidationError(_('Payment start date cannot be earlier than loan date.'))
    
    def action_print_report(self):
        """Print Loan Report"""
        self.ensure_one()
        return self.env.ref('loan_management.action_report_loan').report_action(self)