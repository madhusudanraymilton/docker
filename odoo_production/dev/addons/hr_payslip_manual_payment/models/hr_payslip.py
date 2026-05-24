# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # ── Manual Payment Tracking ───────────────────────────────────────────────

    manual_paid_amount = fields.Monetary(
        string='Manual Paid Amount',
        currency_field='currency_id',
        default=0.0,
        help="Total amount already paid via Manual Payment wizard.",
    )

    manual_remaining_amount = fields.Monetary(
        string='Remaining Amount',
        currency_field='currency_id',
        compute='_compute_manual_remaining_amount',
        store=False,
        help="Net Wage minus what has already been manually paid.",
    )

    @api.depends('manual_paid_amount')
    def _compute_manual_remaining_amount(self):
        for rec in self:
            net = rec.net_wage if hasattr(rec, 'net_wage') else 0.0
            rec.manual_remaining_amount = max(
                (net or 0.0) - (rec.manual_paid_amount or 0.0), 0.0
            )

    def _check_and_mark_paid(self):
        """
        If manual_paid_amount >= net_wage, mark the payslip as paid.
        Called after every manual payment confirmation.
        """
        for rec in self:
            net = rec.net_wage if hasattr(rec, 'net_wage') else 0.0
            paid = rec.manual_paid_amount or 0.0
            if net and paid >= net and rec.state not in ('paid', 'cancel'):
                rec.write({'state': 'paid'})

    # ── Open Wizard ───────────────────────────────────────────────────────────

    def action_open_manual_payment_wizard(self):
        """
        Open the Manual Payment wizard.

        All payslips for the same employee share ONE payment pool.
        The total shown = sum of net_wage across ALL employee payslips
                        - sum of manual_paid_amount across ALL employee payslips.

        Scenario:
          Mitchell Admin Payslip 1: $3,000 net | Payslip 2: same employee
          Shared pool = $3,000

          Open from Payslip 1 → Total = $3,000
          Pay $2,000 → pool remaining = $1,000
          (distributed across payslips in order)

          Open from Payslip 2 (same employee) → Total = $1,000 ✅
          Open from Payslip 1 again           → Total = $1,000 ✅
        """
        self.ensure_one()

        partner = (
            self.employee_id.work_contact_id
            or self.employee_id.partner_id
            or self.employee_id.user_id.partner_id
        )

        bank_account = False
        if partner:
            bank_account = self.env['res.partner.bank'].search(
                [('partner_id', '=', partner.id)], limit=1
            )

        # Total = THIS payslip's net_wage - manual_paid_amount (shared across all payslips).
        # Paying from any payslip updates manual_paid_amount on ALL same-employee payslips.
        net = self.net_wage if hasattr(self, 'net_wage') else 0.0
        remaining = max((net or 0.0) - (self.manual_paid_amount or 0.0), 0.0)

        # Collect ALL payslips for this employee for syncing
        all_slips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'not in', ['cancel']),
        ])
        all_slip_ids_str = ','.join(str(s.id) for s in all_slips)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Manual Payment',
            'res_model': 'hr.payslip.manual.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payslip_id':       self.id,
                'default_employee_id':      self.employee_id.id,
                'default_amount':           remaining,
                'default_all_slip_ids_str': all_slip_ids_str,
                'default_partner_bank_id':  bank_account.id if bank_account else False,
                'default_partner_id':       partner.id if partner else False,
            },
        }
