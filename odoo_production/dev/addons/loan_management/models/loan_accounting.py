from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LoanAccounting(models.Model):
    _name = 'loan.accounting.config'
    _description = 'Loan Accounting Configuration'
    
    name = fields.Char(string='Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    # Default accounts
    loan_account_debit = fields.Many2one('account.account', string='Loan Debit Account', required=True)
    loan_account_credit = fields.Many2one('account.account', string='Loan Credit Account', required=True)
    salary_advance_debit = fields.Many2one('account.account', string='Salary Advance Debit Account', required=True)
    salary_advance_credit = fields.Many2one('account.account', string='Salary Advance Credit Account', required=True)
    
    # Default journals
    loan_journal = fields.Many2one('account.journal', string='Loan Journal', required=True)
    salary_advance_journal = fields.Many2one('account.journal', string='Salary Advance Journal', required=True)
    
    # Payroll integration
    payroll_deduction_code = fields.Char(string='Payroll Deduction Code', help="Code to use in payroll rules for loan deductions")
    
    @api.model
    def get_company_config(self, company_id=None):
        if not company_id:
            company_id = self.env.company.id
        config = self.search([('company_id', '=', company_id)], limit=1)
        if not config:
            raise ValidationError(_("Please configure loan accounting settings first."))
        return config