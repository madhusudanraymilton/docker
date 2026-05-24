from odoo import models, fields


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        res = super().action_payslip_done()

        for payslip in self:
            employee = payslip.employee_id

            gross = 0.0
            net = 0.0

            for line in payslip.line_ids:
                if line.code == 'GROSS':
                    gross = line.total
                if line.code == 'NET':
                    net = line.total

            update_vals = {}
            if gross:
                update_vals['gross_salary'] = gross
            if net:
                update_vals['net_salary'] = net

            if update_vals:
                employee.sudo().write(update_vals)
                employee.sudo()._compute_festival_bonus()

        return res


    festival_bonus = fields.Float(
        string="Festival Bonus",
        related='employee_id.festival_bonus',
        store=True)
    
    provident_fund_amount = fields.Float(
        string="Total PF Amount",
        related='employee_id.provident_fund_amount',
        store=True
    )

