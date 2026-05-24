# loan_line.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LoanLine(models.Model):
    _name = 'hr.loan.line'
    _description = 'Loan Installment Line'
    _order = 'due_date asc'
    
    name = fields.Char(string='Description', compute='_compute_name', store=True)
    loan_id = fields.Many2one('hr.loan', string='Loan', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', related='loan_id.employee_id', store=True)
    
    sequence = fields.Integer(string='Sequence', required=True, default=1)
    due_date = fields.Date(string='Due Date', required=True)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    paid_amount = fields.Monetary(string='Paid Amount', default=0.0, currency_field='currency_id')
    
    currency_id = fields.Many2one('res.currency', string='Currency', related='loan_id.currency_id', store=True)
    
    state = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='unpaid')  # REMOVED: tracking=True
    
    payment_date = fields.Date(string='Payment Date')
    repayment_id = fields.Many2one('hr.loan.repayment', string='Repayment')
    payslip_id = fields.Many2one('hr.payslip', string='Payslip')
    
    @api.depends('sequence', 'due_date', 'amount')
    def _compute_name(self):
        for line in self:
            line.name = f"Installment {line.sequence} - {line.due_date} - {line.amount}"
    
    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_('Installment amount must be greater than zero.'))