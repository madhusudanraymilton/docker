# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TransferRejectWizard(models.TransientModel):
    """Wizard to capture rejection reason before rejecting a transfer."""
    _name = 'transfer.reject.wizard'
    _description = 'Transfer Rejection Wizard'

    transfer_id = fields.Many2one(
        'hr.company.transfer',
        string='Transfer',
    )
    intra_transfer_id = fields.Many2one(
        'hr.intra.transfer',
        string='Intra Transfer',
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        required=True,
    )

    def action_confirm_reject(self):
        self.ensure_one()
        if self.transfer_id:
            self.transfer_id.write({'rejection_reason': self.rejection_reason})
            self.transfer_id.action_reject()
        elif self.intra_transfer_id:
            self.intra_transfer_id.write({'rejection_reason': self.rejection_reason})
            self.intra_transfer_id.action_reject()
        return {'type': 'ir.actions.act_window_close'}
