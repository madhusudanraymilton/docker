from odoo import models, fields, api
from datetime import timedelta


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    salary_base = fields.Selection([
        ('wage', 'Wage'),
        ('gross', 'Gross Salary'),
        ('net', 'Net Salary'),
    ], string="Salary Type")

    custom_wage = fields.Float(
        string="Wage",
        compute='_compute_custom_wage',
        store=True,
        readonly=False  # manually edit-ও করা যাবে
    )

    gross_salary = fields.Float(string="Gross Salary", store=True)
    net_salary = fields.Float(string="Net Salary", store=True)

    percentage = fields.Float(string="Percentage (%)")

    festival_bonus = fields.Float(
        string="Festival Bonus",
        compute="_compute_festival_bonus",
        store=True
    )

    # festival_bonus_start_date = fields.Date(string="Festival Bonus Start Date")
    # festival_bonus_end_date = fields.Date(
    #     string="Festival Bonus End Date",
    #     compute='_compute_end_date',
    #     store=True
    # )

    @api.depends('wage')  # hr.employee এর built-in wage field
    def _compute_custom_wage(self):
        for rec in self:
            rec.custom_wage = rec.wage or 0.0

    @api.depends('percentage', 'salary_base', 'custom_wage', 'gross_salary', 'net_salary')
    def _compute_festival_bonus(self):
        for rec in self:
            base_amount = 0.0

            if rec.salary_base == 'wage':
                base_amount = rec.custom_wage
            elif rec.salary_base == 'gross':
                base_amount = rec.gross_salary or rec.custom_wage
            elif rec.salary_base == 'net':
                base_amount = rec.net_salary or rec.custom_wage

            rec.festival_bonus = (
                (base_amount * rec.percentage) / 100
                if rec.percentage else 0.0
            )

    # @api.depends('festival_bonus_start_date')
    # def _compute_end_date(self):
    #     for rec in self:
    #         if rec.festival_bonus_start_date:
    #             rec.festival_bonus_end_date = (
    #                 rec.festival_bonus_start_date + timedelta(days=30)
    #             )
    #         else:
    #             rec.festival_bonus_end_date = False

    def compute_pf_amounts(self):
        employees = self.env['hr.employee'].search([])
        for emp in employees:
            basic_wage = emp.basic_wage or 0.0
            monthly_pf = basic_wage * 0.10
            total_pf = monthly_pf * 12

            emp.write({
                'pf_deduct_amount': monthly_pf,
                'provident_fund_amount': total_pf,
            })