from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LoanRepayment(models.Model):
    _name = 'hr.loan.repayment'
    _description = 'Loan Repayment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char(string='Reference', readonly=True, copy=False, default=lambda self: _('New'))
    loan_id = fields.Many2one('hr.loan', string='Loan', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', related='loan_id.employee_id', store=True)
    partner_id = fields.Many2one('res.partner', string='Partner', related='loan_id.partner_id', store=True, readonly=True)
    
    # Add company_id field
    company_id = fields.Many2one(
        'res.company', 
        string='Company',
        default=lambda self: self.env.company
    )
    
    date = fields.Date(string='Repayment Date', required=True, default=fields.Date.today)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', related='loan_id.currency_id', store=True)
    
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('payroll', 'Payroll Deduction'),
        ('other', 'Other')
    ], string='Payment Method', default='cash', required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    journal_id = fields.Many2one('account.journal', string='Journal')
    account_debit = fields.Many2one('account.account', string='Debit Account')
    account_credit = fields.Many2one('account.account', string='Credit Account')
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)
    
    notes = fields.Text(string='Notes')
    
    # Relationship to loan lines
    loan_line_ids = fields.One2many('hr.loan.line', 'repayment_id', string='Installments Paid')
    
    # sohag code here
    
    balance_amount = fields.Monetary(
    string='Due amount',
    related='loan_id.balance_amount',
    readonly=True,
    store=False
    )
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.loan.repayment') or _('New')
        repayments = super().create(vals_list)
        
        # Set fields from loan if not provided
        for repayment in repayments:
            if repayment.loan_id:
                # Automatically set partner from loan
                repayment.partner_id = repayment.loan_id.partner_id.id
                if not repayment.company_id:
                    repayment.company_id = repayment.loan_id.company_id.id
                if not repayment.account_debit:
                    repayment.account_debit = repayment.loan_id.account_debit.id
                if not repayment.account_credit:
                    repayment.account_credit = repayment.loan_id.account_credit.id
        
        return repayments

    @api.onchange('loan_id')
    def _onchange_loan_id(self):
        """Set fields from loan when loan is selected"""
        if self.loan_id:
            self.employee_id = self.loan_id.employee_id.id
            self.partner_id = self.loan_id.partner_id.id
            self.company_id = self.loan_id.company_id.id
            self.account_debit = self.loan_id.account_debit.id
            self.account_credit = self.loan_id.account_credit.id
    
    def action_confirm(self):
        """Confirm repayment and allocate to installments"""
        for repayment in self:
            if repayment.state != 'draft':
                continue
                
            if repayment.amount <= 0:
                raise ValidationError(_('Repayment amount must be greater than zero.'))
            
            if repayment.amount > repayment.loan_id.balance_amount:
                raise ValidationError(_('Repayment amount cannot exceed the loan balance.'))
            
            # Allocate to installments
            repayment._allocate_to_installments()
            
            # Create accounting entry
            repayment._create_payment_entry()
            
            # Update state
            repayment.write({'state': 'paid'})
            
            # Update loan status if fully paid
            if repayment.loan_id.balance_amount <= 0:
                repayment.loan_id.action_mark_as_paid()
    
    def action_cancel(self):
        """Cancel repayment and unallocate from installments"""
        for repayment in self:
            if repayment.state == 'paid':
                # Unlink from loan lines
                repayment.loan_line_ids.write({
                    'state': 'unpaid',
                    'payment_date': False,
                    'repayment_id': False
                })
                
                # Cancel accounting entry
                if repayment.move_id:
                    repayment.move_id.button_cancel()
                    repayment.move_id.unlink()
            
            repayment.write({'state': 'cancelled'})
     
            
    def _allocate_to_installments(self):
        """Allocate repayment to unpaid/partial installments"""
        self.ensure_one()

        lines = self.loan_id.loan_line_ids.filtered(
            lambda l: l.state in ['unpaid', 'partial', 'overdue']
        ).sorted('due_date')

        remaining_amount = self.amount
        paid_lines = self.env['hr.loan.line']

        for line in lines:
            if remaining_amount <= 0:
                break

            already_paid = line.paid_amount or 0.0
            remaining_line_amount = line.amount - already_paid

            if remaining_amount >= remaining_line_amount:
                # ✅ Fully pay this installment
                line.write({
                    'state': 'paid',
                    'paid_amount': line.amount,
                    'payment_date': self.date,
                    'repayment_id': self.id,
                })
                remaining_amount -= remaining_line_amount
            else:
                # ✅ Still partial
                line.write({
                    'state': 'partial',
                    'paid_amount': already_paid + remaining_amount,
                    'payment_date': self.date,
                    'repayment_id': self.id,
                })
                remaining_amount = 0

            paid_lines |= line

        self.loan_line_ids = [(6, 0, paid_lines.ids)]

    
    # def _allocate_to_installments(self):
    #     """Allocate repayment to unpaid installments"""
    #     self.ensure_one()
    #     unpaid_lines = self.loan_id.loan_line_ids.filtered(
    #         lambda l: l.state in ['unpaid', 'overdue']
    #     ).sorted('due_date')
        
    #     remaining_amount = self.amount
    #     paid_lines = self.env['hr.loan.line']
        
    #     for line in unpaid_lines:
    #         if remaining_amount <= 0:
    #             break
            
    #         if remaining_amount >= line.amount:
    #             line.write({
    #                 'state': 'paid',
    #                 'payment_date': self.date,
    #                 'repayment_id': self.id
    #             })
    #             paid_lines += line
    #             remaining_amount -= line.amount
    #         else:
    #             # Partial payment for installment
    #             line.write({
    #                 'state': 'partial',
    #                 'payment_date': self.date,
    #                 'repayment_id': self.id,
    #                 'paid_amount': remaining_amount
    #             })
    #             paid_lines += line
    #             remaining_amount = 0
        
    #     # Update the one2many field
    #     self.loan_line_ids = [(6, 0, paid_lines.ids)]
    
    def _create_payment_entry(self):
        """Create accounting entry for repayment"""
        self.ensure_one()
        
        if not self.journal_id:
            # Use loan's journal if not specified
            self.journal_id = self.loan_id.journal_id
        
        if not self.account_debit:
            # Use loan's debit account if not specified
            self.account_debit = self.loan_id.account_debit
        
        if not self.account_credit:
            # Use loan's credit account if not specified
            self.account_credit = self.loan_id.account_credit
        
        if not self.journal_id or not self.account_debit or not self.account_credit:
            raise ValidationError(_('Please configure journal and accounts for repayment.'))
        
        move_vals = {
            'date': self.date,
            'journal_id': self.journal_id.id,
            'ref': f'Loan Repayment: {self.name} for {self.loan_id.name}',
            'partner_id': self.partner_id.id if self.partner_id else False,  # Partner in move header
            'line_ids': [
                (0, 0, {
                    'account_id': self.account_debit.id,
                    'debit': self.amount,
                    'credit': 0,
                    'name': f'Loan Repayment: {self.loan_id.name} - {self.employee_id.name}',
                    'partner_id': self.partner_id.id if self.partner_id else False,
                }),
                (0, 0, {
                    'account_id': self.account_credit.id,
                    'debit': 0,
                    'credit': self.amount,
                    'name': f'Loan Receivable Reduction: {self.loan_id.name}',
                    'partner_id': self.partner_id.id if self.partner_id else False,
                }),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        self.move_id = move.id
    
    @api.constrains('amount')
    def _check_amount(self):
        for repayment in self:
            if repayment.amount <= 0:
                raise ValidationError(_('Repayment amount must be greater than zero.'))
            
    
    def action_print_report(self):
        """Print Repayment Report"""
        self.ensure_one()
        return self.env.ref('loan_management.action_report_loan_repayment').report_action(self)