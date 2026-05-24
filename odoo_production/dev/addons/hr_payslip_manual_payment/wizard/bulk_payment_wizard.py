# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrPayslipBulkPaymentWizard(models.TransientModel):
    """
    Bulk Manual Payment Wizard — opened from Actions menu on payslip list.
    Processes one payment line per selected payslip.
    Each line shows: Employee | Total Remaining | Pay Now | Net Payable After
    One shared journal + accounts for all lines.
    """
    _name = 'hr.payslip.bulk.payment.wizard'
    _description = 'Bulk Manual Payment Wizard'

    # ── Shared Payment Settings ───────────────────────────────────────────────

    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.today,
    )

    payment_type = fields.Selection(
        selection=[
            ('bank', 'Bank Transfer'),
            ('cash', 'Cash'),
        ],
        string='Payment Method',
        required=True,
        default='bank',
    )

    bank_journal_id = fields.Many2one(
        'account.journal',
        string='Salaries Journal',
        domain=[('name', 'ilike', 'salar')],
    )

    cash_journal_id = fields.Many2one(
        'account.journal',
        string='Salaries Journal',
        # Always the Salaries journal — same as bank. Credit account determines bank vs cash.
        domain=[('name', 'ilike', 'salar')],
    )

    account_debit = fields.Many2one(
        'account.account',
        string='Debit Account (Salary Payable)',
        domain=[
            ('account_type', 'in', ['liability_payable', 'liability_current']),
            '|',
            ('name', 'ilike', 'salary'),
            ('name', 'ilike', 'wage'),
        ],
        required=True,
    )

    account_credit = fields.Many2one(
        'account.account',
        string='Credit Account',
        required=True,
    )

    bank_account_ids = fields.Many2many(
        'account.account',
        relation='bulk_wizard_bank_account_rel',
        column1='wizard_id',
        column2='account_id',
        compute='_compute_journal_account_ids',
    )
    cash_account_ids = fields.Many2many(
        'account.account',
        relation='bulk_wizard_cash_account_rel',
        column1='wizard_id',
        column2='account_id',
        compute='_compute_journal_account_ids',
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    memo = fields.Char(
        string='Memo / Reference',
        default='Bulk Manual Payslip Payment',
    )

    # ── Per-Employee Payment Lines ────────────────────────────────────────────

    line_ids = fields.One2many(
        'hr.payslip.bulk.payment.line',
        'wizard_id',
        string='Payment Lines',
    )

    # ── Computed ─────────────────────────────────────────────────────────────

    @api.depends('payment_type')
    def _compute_journal_account_ids(self):
        bank_journals = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id),
        ])
        cash_journals = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.env.company.id),
        ])
        for rec in self:
            rec.bank_account_ids = bank_journals.mapped('default_account_id')
            rec.cash_account_ids = cash_journals.mapped('default_account_id')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_salaries_journal(self):
        return self.env['account.journal'].search([
            ('name', 'ilike', 'salar'),
        ], limit=1)

    def _get_default_salary_payable_account(self):
        account = self.env['account.account'].search([
            ('account_type', 'in', ['liability_payable', 'liability_current']),
            '|',
            ('name', 'ilike', 'salary'),
            ('name', 'ilike', 'wage'),
            ('company_ids', 'in', self.env.company.id),
        ], limit=1)
        if not account:
            account = self.env['account.account'].search([
                ('account_type', 'in', ['liability_payable', 'liability_current']),
                ('company_ids', 'in', self.env.company.id),
            ], limit=1)
        return account

    def _get_default_credit_account(self):
        bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if bank_journal and bank_journal.default_account_id:
            return bank_journal.default_account_id
        return self.env['account.account']

    # ── default_get ───────────────────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Both bank and cash use the Salaries journal for posting
        salaries_journal = self._get_salaries_journal()
        if salaries_journal:
            res['bank_journal_id'] = salaries_journal.id
            res['cash_journal_id'] = salaries_journal.id

        # Account defaults
        debit_account = self._get_default_salary_payable_account()
        if debit_account:
            res['account_debit'] = debit_account.id

        credit_account = self._get_default_credit_account()
        if credit_account:
            res['account_credit'] = credit_account.id

        # Build payment lines — ONE line per employee.
        # Total = first payslip's net wage (no summing).
        # Payment syncs to ALL payslips for that employee equally.
        payslip_ids = self.env.context.get('active_ids', [])
        payslips = self.env['hr.payslip'].browse(payslip_ids)

        # ONE line per employee.
        # Total = first selected payslip's remaining (no summing).
        # Both records have $5,000 → shows $5,000.
        # Pay $1,000 → manual_paid_amount += $1,000 on ALL payslips → both show $4,000.
        employee_map = {}
        for slip in payslips:
            emp_id = slip.employee_id.id
            if emp_id in employee_map:
                continue  # already have this employee
            net = slip.net_wage if hasattr(slip, 'net_wage') else 0.0
            remaining = (net or 0.0) - (slip.manual_paid_amount or 0.0)
            partner = (
                slip.employee_id.work_contact_id
                or slip.employee_id.partner_id
                or slip.employee_id.user_id.partner_id
            )
            employee_map[emp_id] = {
                'partner':    partner,
                'payslip_id': slip.id,
                'total':      remaining,  # this payslip only, no summing
            }

        lines = []
        for emp_id, data in employee_map.items():
            # All payslips for this employee — payment syncs to all
            all_emp_slips = self.env['hr.payslip'].search([
                ('employee_id', '=', emp_id),
                ('state', 'not in', ['cancel']),
            ])
            all_ids_str = ','.join(str(s.id) for s in all_emp_slips)

            lines.append((0, 0, {
                'employee_id':     emp_id,
                'partner_id':      data['partner'].id if data['partner'] else False,
                'payslip_id':      data['payslip_id'],
                'payslip_ids_str': all_ids_str,
                'total_amount':    data['total'],
                'pay_now':         0.0,
            }))

        if lines:
            res['line_ids'] = lines

        return res

    # ── Onchanges ─────────────────────────────────────────────────────────────

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        """
        Both bank and cash use the Salaries journal.
        Only Credit Account changes:
          Bank → from bank-type journal account (e.g. 101401 Bank)
          Cash → from cash-type journal account (e.g. 101501 Cash)
        """
        self.account_credit = False
        if self.payment_type == 'bank':
            bank_journal = self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if bank_journal and bank_journal.default_account_id:
                self.account_credit = bank_journal.default_account_id
        else:
            cash_journal = self.env['account.journal'].search([
                ('type', '=', 'cash'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if cash_journal and cash_journal.default_account_id:
                self.account_credit = cash_journal.default_account_id

    @api.onchange('bank_journal_id')
    def _onchange_bank_journal_id(self):
        if self.payment_type == 'bank' and self.bank_journal_id:
            bank_journal = self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if bank_journal and bank_journal.default_account_id:
                self.account_credit = bank_journal.default_account_id

    @api.onchange('cash_journal_id')
    def _onchange_cash_journal_id(self):
        """When cash selected, credit account from actual cash-type journal."""
        if self.payment_type == 'cash':
            cash_journal = self.env['account.journal'].search([
                ('type', '=', 'cash'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if cash_journal and cash_journal.default_account_id:
                self.account_credit = cash_journal.default_account_id

    # ── Confirm All Payments ──────────────────────────────────────────────────

    def action_confirm_bulk_payment(self):
        self.ensure_one()

        if self.payment_type == 'bank':
            if not self.bank_journal_id:
                raise UserError(_("Please select a Salaries Journal."))
            journal = self.bank_journal_id
        else:
            if not self.cash_journal_id:
                raise UserError(_("Please select a Cash Journal."))
            journal = self.cash_journal_id

        if not self.account_debit:
            raise UserError(_("Please select a Debit Account (Salary Payable)."))
        if not self.account_credit:
            raise UserError(_("Please select a Credit Account."))
        if not self.line_ids:
            raise UserError(_("No payment lines found."))

        paid_count = 0
        errors = []

        for line in self.line_ids:
            if not line.pay_now or line.pay_now <= 0:
                continue
            if line.pay_now > line.total_amount:
                errors.append(
                    f"{line.employee_id.name}: Pay Now ({line.pay_now}) "
                    f"exceeds remaining ({line.total_amount})"
                )
                continue

            try:
                partner = (
                    line.partner_id
                    or line.employee_id.work_contact_id
                    or line.employee_id.partner_id
                    or line.employee_id.user_id.partner_id
                )
                if not partner:
                    errors.append(f"{line.employee_id.name}: No linked partner found.")
                    continue

                memo = self.memo or f"Bulk Payment - {line.employee_id.name}"
                move_vals = {
                    'move_type':  'entry',
                    'date':        self.payment_date,
                    'journal_id':  journal.id,
                    'ref':         memo,
                    'partner_id':  partner.id,
                    'line_ids': [
                        (0, 0, {
                            'account_id':  self.account_debit.id,
                            'partner_id':  partner.id,
                            'name':        memo,
                            'debit':       line.pay_now,
                            'credit':      0.0,
                            'currency_id': self.currency_id.id,
                        }),
                        (0, 0, {
                            'account_id':  self.account_credit.id,
                            'partner_id':  partner.id,
                            'name':        memo,
                            'debit':       0.0,
                            'credit':      line.pay_now,
                            'currency_id': self.currency_id.id,
                        }),
                    ],
                }
                move = self.env['account.move'].create(move_vals)
                move.action_post()

                if move.state == 'posted':
                    # Sync pay_now equally to ALL payslips for this employee.
                    # Same logic as single wizard — every payslip gets same update.
                    all_payslip_ids = []
                    if line.payslip_ids_str:
                        all_payslip_ids = [
                            int(x) for x in line.payslip_ids_str.split(',') if x.strip()
                        ]
                    else:
                        all_payslip_ids = [line.payslip_id.id]

                    # Sync pay_now to ALL payslips for this employee
                    all_slips = self.env['hr.payslip'].browse(all_payslip_ids)
                    for slip in all_slips:
                        slip.manual_paid_amount = (
                            (slip.manual_paid_amount or 0.0) + line.pay_now
                        )
                    all_slips._check_and_mark_paid()

                    remaining_total = max(line.total_amount - line.pay_now, 0.0)
                    line.payslip_id.message_post(
                        body=_(
                            "Bulk manual payment posted: %(paid)s paid | "
                            "%(remaining)s remaining | Journal Entry: %(ref)s ✅",
                            paid=f"{self.currency_id.symbol}{line.pay_now:,.2f}",
                            remaining=f"{self.currency_id.symbol}{remaining_total:,.2f}",
                            ref=move.name or '/',
                        )
                    )
                    paid_count += 1

            except Exception as e:
                errors.append(f"{line.employee_id.name}: {str(e)}")

        if errors:
            raise UserError(
                _("%(count)s payment(s) posted. Errors:\n%(errors)s",
                  count=paid_count,
                  errors='\n'.join(errors))
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Payment Posted ✅'),
                'message': f"{paid_count} payment(s) posted successfully.",
                'sticky': True,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


    # ── Open Wizard ───────────────────────────────────────────────────────────

    def action_open(self):
        """Called by the server action in Actions menu — opens this wizard in a popup."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bulk Manual Payment',
            'res_model': 'hr.payslip.bulk.payment.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'view_id': self.env.ref(
                'hr_payslip_manual_payment.view_hr_payslip_bulk_payment_wizard_form'
            ).id,
        }

class HrPayslipBulkPaymentLine(models.TransientModel):
    """One line per payslip in the bulk payment wizard."""
    _name = 'hr.payslip.bulk.payment.line'
    _description = 'Bulk Payment Line'

    wizard_id = fields.Many2one(
        'hr.payslip.bulk.payment.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )

    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        readonly=True,
        help="Primary payslip — used for net_payable tracking.",
    )

    payslip_ids_str = fields.Char(
        string='All Payslip IDs',
        help="Comma-separated IDs of ALL payslips for this employee in the selection. "
             "Payment is distributed across these payslips when confirmed.",
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        readonly=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
    )

    total_amount = fields.Monetary(
        string='Total Remaining',
        currency_field='currency_id',
        readonly=True,
        help="Remaining salary still owed to this employee.",
    )

    pay_now = fields.Monetary(
        string='Pay Now',
        currency_field='currency_id',
        help="Amount to pay in this transaction.",
    )

    net_payable = fields.Monetary(
        string='Net Payable After',
        currency_field='currency_id',
        compute='_compute_net_payable',
        store=False,
        help="What will still be owed after this payment.",
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.currency_id',
    )

    @api.depends('payslip_id', 'payslip_id.manual_paid_amount')
    def _compute_net_payable(self):
        """
        Net Payable After = remaining AFTER payments so far.

        Rules:
          - manual_paid_amount = 0  → Net Payable = 0   (nothing paid yet)
          - manual_paid_amount > 0  → Net Payable = net_wage - manual_paid_amount

        NO summing across payslips. NO live reaction to Pay Now field.
        """
        for rec in self:
            if rec.payslip_id:
                paid = rec.payslip_id.manual_paid_amount or 0.0
                if paid <= 0:
                    rec.net_payable = 0.0
                else:
                    net = rec.payslip_id.net_wage if hasattr(rec.payslip_id, 'net_wage') else 0.0
                    rec.net_payable = max((net or 0.0) - paid, 0.0)
            else:
                rec.net_payable = 0.0

