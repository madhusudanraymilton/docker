# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrPayslipManualPaymentWizard(models.TransientModel):
    _name = 'hr.payslip.manual.payment.wizard'
    _description = 'Manual Payment Wizard'

    # ── Core Fields ──────────────────────────────────────────────────────────

    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        readonly=True,
    )

    all_slip_ids_str = fields.Char(
        string='All Payslip IDs',
        help="Comma-separated IDs of ALL payslips for this employee. "
             "Payment is distributed across these in order when confirmed.",
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        readonly=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
    )

    amount = fields.Monetary(
        string='Total Amount',
        required=True,
        currency_field='currency_id',
    )

    deduction = fields.Monetary(
        string='Pay Now',
        currency_field='currency_id',
        default=0.0,
    )

    net_payable = fields.Monetary(
        string='Net Payable',
        currency_field='currency_id',
        compute='_compute_net_payable',
        store=False,
        help="Remaining salary still owed to the employee. "
             "Only updates after a payment is confirmed — not affected by Deduction field.",
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.today,
    )

    memo = fields.Char(
        string='Memo / Reference',
        default='Manual Payslip Payment',
    )

    # ── Payment Type ─────────────────────────────────────────────────────────

    payment_type = fields.Selection(
        selection=[
            ('bank', 'Bank Transfer'),
            ('cash', 'Cash'),
        ],
        string='Payment Method',
        required=True,
        default='bank',
    )

    # ── Journals ─────────────────────────────────────────────────────────────

    bank_journal_id = fields.Many2one(
        'account.journal',
        string='Salaries Journal',
        # Salaries journal can be ANY type (bank, cash, or miscellaneous).
        # Filter by name only — do NOT restrict by type.
        domain=[('name', 'ilike', 'salar')],
    )

    cash_journal_id = fields.Many2one(
        'account.journal',
        string='Salaries Journal',
        # Always the Salaries journal — same as bank. Credit account determines bank vs cash.
        domain=[('name', 'ilike', 'salar')],
    )

    partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string="Employee Bank Account",
    )

    # ── Debit Account ────────────────────────────────────────────────────────
    # Shows ONLY salary/wage liability accounts from the Chart of Accounts.
    # 'payroll' keyword removed — too broad (includes tax/pension liabilities).
    account_debit = fields.Many2one(
        'account.account',
        string='Debit Account',
        domain=[
            ('account_type', 'in', ['liability_payable', 'liability_current']),
            '|',
            ('name', 'ilike', 'salary'),
            ('name', 'ilike', 'wage'),
        ],
        help="Salary Payable account — shows only salary/wage liability accounts "
             "from the Chart of Accounts (mirrors account_debit on hr.salary.rule).",
    )

    # ── Credit Account ───────────────────────────────────────────────────────
    # Bank payment  → ONLY accounts that are the default_account_id of a BANK journal
    # Cash payment  → ONLY accounts that are the default_account_id of a CASH journal
    #
    # Why not use account_type='asset_cash'?
    # Because BOTH bank and cash accounts share account_type='asset_cash' in Odoo.
    # The only reliable separator is: which journal type owns that account.
    account_credit = fields.Many2one(
        'account.account',
        string='Credit Account',
        help="Bank: shows only bank journal accounts. Cash: shows only cash journal accounts.",
    )

    # Computed Many2many fields used as domain source in the XML view.
    # They hold the actual account IDs linked to bank/cash journals respectively.
    bank_account_ids = fields.Many2many(
        'account.account',
        relation='wizard_bank_account_rel',
        column1='wizard_id',
        column2='account_id',
        compute='_compute_journal_account_ids',
        string='Bank Journal Accounts',
    )
    cash_account_ids = fields.Many2many(
        'account.account',
        relation='wizard_cash_account_rel',
        column1='wizard_id',
        column2='account_id',
        compute='_compute_journal_account_ids',
        string='Cash Journal Accounts',
    )

    # ── Computed ─────────────────────────────────────────────────────────────

    @api.depends('payslip_id', 'payslip_id.manual_paid_amount', 'all_slip_ids_str')
    def _compute_net_payable(self):
        """
        Net Payable = remaining after payments so far.

        Rules:
          - manual_paid_amount = 0  → Net Payable = 0   (nothing paid yet)
          - manual_paid_amount > 0  → Net Payable = net_wage - manual_paid_amount

        NO live reaction to Pay Now field.
        Only changes after Confirm Payment is clicked.
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

    @api.depends('payment_type', 'bank_journal_id', 'cash_journal_id')
    def _compute_journal_account_ids(self):
        """
        Populate bank_account_ids and cash_account_ids with the default_account_id
        of every bank/cash journal in the current company.

        These are used as the domain for account_credit in the XML view:
            Bank mode  → ('id', 'in', bank_account_ids)
            Cash mode  → ('id', 'in', cash_account_ids)

        This is the ONLY correct way to separate bank accounts from cash accounts
        in Odoo's Chart of Accounts — both share account_type='asset_cash'.
        """
        # Credit account for BANK payment → always from type='bank' journals.
        # This is independent of the Salaries journal (which is used for posting only).
        # Both bank & cash share account_type='asset_cash', so we use journal ownership.
        bank_journals = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id),
        ])
        cash_journals = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.env.company.id),
        ])

        bank_accounts = bank_journals.mapped('default_account_id')
        cash_accounts = cash_journals.mapped('default_account_id')

        for rec in self:
            rec.bank_account_ids = bank_accounts
            rec.cash_account_ids = cash_accounts

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_salaries_journal(self, journal_type=None):
        """
        Return the Salaries journal by NAME only.
        Type is NOT filtered — Salaries journal can be Miscellaneous, Bank, or Cash.
        journal_type param kept for backward compat but intentionally ignored.
        """
        return self.env['account.journal'].search([
            ('name', 'ilike', 'salar'),
        ], limit=1)

    def _get_default_salary_payable_account(self):
        """
        Return the best Salary Payable account for the debit side.
        Pass 1: liability account whose name contains 'salary' or 'wage'.
        Pass 2: any liability_payable account (last resort).
        """
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

    def _get_default_credit_account(self, journal):
        """
        Return the default account of the given journal.
        If the journal has no default_account_id (e.g. Salaries = Miscellaneous type),
        fall back to the first bank-type journal's default account.
        This ensures Credit Account is always auto-filled on wizard open.
        """
        if journal and journal.default_account_id:
            return journal.default_account_id
        # Fallback: Salaries journal has no default account (it is Miscellaneous).
        # Use the first bank-type journal's default account instead.
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

        # Both bank and cash use the Salaries journal for posting.
        # Credit account is what differs: bank account for Bank, cash account for Cash.
        salaries_journal = self._get_salaries_journal()
        if salaries_journal:
            res['bank_journal_id'] = salaries_journal.id
            res['cash_journal_id'] = salaries_journal.id

        salary_payable = self._get_default_salary_payable_account()
        if salary_payable:
            res['account_debit'] = salary_payable.id

        # Default credit = bank account (payment_type defaults to 'bank')
        actual_bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        credit_account = self._get_default_credit_account(actual_bank_journal)
        if credit_account:
            res['account_credit'] = credit_account.id

        return res

    # ── Onchanges ─────────────────────────────────────────────────────────────

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        """
        Both bank and cash use the Salaries journal.
        Only the Credit Account changes based on payment type:
          Bank → credit account from bank-type journal (e.g. 101401 Bank)
          Cash → credit account from cash-type journal (e.g. 101501 Cash)
        """
        self.account_credit = False
        if self.payment_type == 'bank':
            actual_bank = self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            self.account_credit = self._get_default_credit_account(actual_bank)
        else:
            actual_cash = self.env['account.journal'].search([
                ('type', '=', 'cash'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if actual_cash and actual_cash.default_account_id:
                self.account_credit = actual_cash.default_account_id

    @api.onchange('bank_journal_id')
    def _onchange_bank_journal_id(self):
        """Auto-update credit account when bank journal changes."""
        if self.payment_type == 'bank':
            self.account_credit = self._get_default_credit_account(self.bank_journal_id)

    @api.onchange('cash_journal_id')
    def _onchange_cash_journal_id(self):
        """When cash payment selected, credit account comes from actual cash-type journal."""
        if self.payment_type == 'cash':
            actual_cash = self.env['account.journal'].search([
                ('type', '=', 'cash'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if actual_cash and actual_cash.default_account_id:
                self.account_credit = actual_cash.default_account_id

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        self.partner_bank_id = False
        self.partner_id = False
        if self.employee_id:
            partner = (
                self.employee_id.work_contact_id
                or self.employee_id.partner_id
                or self.employee_id.user_id.partner_id
            )
            if partner:
                self.partner_id = partner
                bank_account = self.env['res.partner.bank'].search(
                    [('partner_id', '=', partner.id)], limit=1
                )
                self.partner_bank_id = bank_account

    # ── Action: Confirm Payment ───────────────────────────────────────────────

    def action_confirm_payment(self):
        self.ensure_one()

        if self.payment_type == 'bank':
            if not self.bank_journal_id:
                raise UserError(_("Please select a Bank Journal before confirming."))
            journal = self.bank_journal_id
        else:
            if not self.cash_journal_id:
                raise UserError(_("Please select a Cash Journal before confirming."))
            journal = self.cash_journal_id

        if not self.account_debit:
            raise UserError(_("Please select a Debit Account (Salary Payable) before confirming."))
        if not self.account_credit:
            raise UserError(_("Please select a Credit Account before confirming."))

        if self.deduction < 0:
            raise UserError(_("Pay Now amount cannot be negative."))
        if self.deduction > self.amount:
            raise UserError(_("Pay Now amount cannot exceed Total Amount."))
        if self.deduction <= 0:
            raise UserError(_("Pay Now amount must be greater than zero."))

        # pay_now = deduction = amount being paid in this transaction
        # remaining = amount - deduction = what still owed after this payment
        pay_now = self.deduction
        remaining = self.amount - self.deduction

        partner = (
            self.partner_id
            or self.employee_id.work_contact_id
            or self.employee_id.partner_id
            or self.employee_id.user_id.partner_id
        )
        if not partner:
            raise UserError(_(
                "Employee '%s' has no linked partner or contact. "
                "Please set a Work Contact on the employee form first.",
                self.employee_id.name
            ))

        move, payment_ref = self._create_direct_journal_entry(journal, partner, pay_now)

        # Sync pay_now to ALL payslips for this employee.
        # manual_paid_amount tracks total paid — same value across all payslips.
        # Total shown = each payslip's own net_wage - this shared paid amount.
        if self.all_slip_ids_str:
            ids = [int(x) for x in self.all_slip_ids_str.split(',') if x.strip()]
            all_slips = self.env['hr.payslip'].browse(ids)
        elif self.payslip_id:
            all_slips = self.payslip_id
        else:
            all_slips = self.env['hr.payslip']

        for slip in all_slips:
            slip.manual_paid_amount = (slip.manual_paid_amount or 0.0) + pay_now
        all_slips._check_and_mark_paid()

        if self.payslip_id:
            self.payslip_id.message_post(
                body=_(
                    "Manual payment posted via %(type)s journal '%(journal)s' on %(date)s. "
                    "Total Salary: %(total)s | Paid Now: %(paid_now)s | "
                    "Remaining: %(remaining)s | Journal Entry: %(ref)s ✅",
                    total=f"{self.currency_id.symbol}{self.amount:,.2f}",
                    paid_now=f"{self.currency_id.symbol}{pay_now:,.2f}",
                    remaining=f"{self.currency_id.symbol}{remaining:,.2f}",
                    type=dict(self._fields['payment_type'].selection)[self.payment_type],
                    journal=journal.name,
                    date=self.payment_date,
                    ref=payment_ref,
                )
            )

        msg = (
            f"Paid: {self.currency_id.symbol}{pay_now:,.2f} | "
            f"Remaining: {self.currency_id.symbol}{remaining:,.2f} | "
            f"Journal Entry: {payment_ref}"
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payment Posted ✅'),
                'message': msg,
                'sticky': True,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # ── Direct Journal Entry ──────────────────────────────────────────────────

    def _create_direct_journal_entry(self, journal, partner, net_payable):
        """
        Debit  → account_debit  (Salary Payable — clears the liability)
        Credit → account_credit (Bank account or Cash account)
        """
        memo = self.memo or f"Manual Payment - {self.employee_id.name}"

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
                    'debit':       net_payable,
                    'credit':      0.0,
                    'currency_id': self.currency_id.id,
                }),
                (0, 0, {
                    'account_id':  self.account_credit.id,
                    'partner_id':  partner.id,
                    'name':        memo,
                    'debit':       0.0,
                    'credit':      net_payable,
                    'currency_id': self.currency_id.id,
                }),
            ],
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()

        if move.state != 'posted':
            raise UserError(_(
                "Journal entry could not be posted. "
                "Please check your journal and account configuration."
            ))

        return move, move.name or '/'

    def _get_payment_method_line(self, journal):
        method_line = self.env['account.payment.method.line'].search([
            ('journal_id', '=', journal.id),
            ('payment_type', '=', 'outbound'),
        ], limit=1)
        return method_line.id if method_line else False
