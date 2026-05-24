# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    company_transfer_count = fields.Integer(
        string='Inter Transfer Count',
        compute='_compute_company_transfer_count',
    )
    intra_transfer_count = fields.Integer(
        string='Intra Transfer Count',
        compute='_compute_intra_transfer_count',
    )

    def _compute_company_transfer_count(self):
        for emp in self:
            emp.company_transfer_count = self.env['hr.company.transfer'].search_count([
                ('employee_id', '=', emp.id),
            ])

    def _compute_intra_transfer_count(self):
        for emp in self:
            emp.intra_transfer_count = self.env['hr.intra.transfer'].search_count([
                ('employee_id', '=', emp.id),
            ])

    def action_view_company_transfers(self):
        self.ensure_one()
        return {
            'name': _('Inter-Company Transfers'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.company.transfer',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_view_intra_transfers(self):
        self.ensure_one()
        return {
            'name': _('Intra-Company Transfers'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.intra.transfer',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    company_transfer_id = fields.Many2one(
        'hr.company.transfer',
        string='Company Transfer',
        ondelete='set null',
    )
