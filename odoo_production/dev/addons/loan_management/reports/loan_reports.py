from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LoanReport(models.AbstractModel):
    _name = 'report.loan_management.loan_report'
    _description = 'Loan Report'
    
    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.loan'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.loan',
            'docs': docs,
            'data': data,
        }


class SalaryAdvanceReport(models.AbstractModel):
    _name = 'report.loan_management.salary_advance_report'
    _description = 'Salary Advance Report'
    
    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.salary.advance'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.salary.advance',
            'docs': docs,
            'data': data,
        }