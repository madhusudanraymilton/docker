# from odoo import models, fields, api, _
# from odoo.exceptions import UserError


# class HrLeaveCustomApproval(models.Model):
#     _inherit = 'hr.leave'

#     # Add tracking fields for approvers (Odoo 19 doesn't have these by default)
#     first_approver_id = fields.Many2one(
#         'hr.employee',
#         string='First Approver',
#         readonly=True,
#         tracking=True,
#         help='Employee who provided the first approval (Manager)'
#     )

#     second_approver_id = fields.Many2one(
#         'hr.employee',
#         string='Second Approver',
#         readonly=True,
#         tracking=True,
#         help='Time Off Officer who provided the final approval'
#     )

#     def _check_approval_rights(self, approval_level):
#         """
#         Check if current user has rights to approve at specific level

#         :param approval_level: 'first' or 'second'
#         :return: Boolean
#         """
#         self.ensure_one()
#         current_user = self.env.user
#         current_employee = self.env.user.employee_id

#         if approval_level == 'first':
#             # First approval: Only employee's direct approver (manager)
#             if self.employee_id.parent_id.user_id == current_user:
#                 return True
#             return False

#         elif approval_level == 'second':
#             # Second approval: Only Time Off Officers
#             if current_user.has_group('hr_holidays.group_hr_holidays_user'):
#                 return True
#             return False

#         return False

#     def action_approve(self, check_state=None):
#         """
#         Override the approval method to enforce strict two-level approval

#         IMPORTANT: This assumes validation_type is set to 'both'
#         (By Employee's Approver and Time Off Officer)
#         """
#         current_employee = self.env.user.employee_id

#         if not current_employee:
#             raise UserError(_('Your user account is not linked to an employee record.'))

#         for leave in self:
#             # Prevent self-approval
#             if leave.employee_id == current_employee:
#                 raise UserError(_('You cannot approve your own time off request.'))

#             # Check current state and determine required approval level
#             if leave.state == 'confirm':
#                 # Need first approval - Only Manager
#                 if not leave._check_approval_rights('first'):
#                     raise UserError(_(
#                         'Only the employee\'s direct manager (%s) can provide the first approval.\n\n'
#                         'Current state: Waiting for first approval'
#                     ) % (leave.employee_id.parent_id.name if leave.employee_id.parent_id else 'Not Set'))

#                 # Proceed with first approval
#                 leave.write({
#                     'state': 'validate1',
#                     'first_approver_id': current_employee.id,
#                 })

#                 # Post message in chatter
#                 leave.message_post(
#                     body=_('First approval granted by %s') % current_employee.name,
#                     subtype_xmlid='mail.mt_note'
#                 )

#             elif leave.state == 'validate1':
#                 # Need second approval - Only Time Off Officer
#                 if not leave._check_approval_rights('second'):
#                     raise UserError(_(
#                         'Only Time Off Officers can provide the second and final approval.\n\n'
#                         'Current state: Waiting for second approval'
#                     ))

#                 # Check if first approval exists
#                 if not leave.first_approver_id:
#                     raise UserError(_(
#                         'This request must be approved by the employee\'s manager first.'
#                     ))

#                 # Proceed with second approval (final)
#                 leave.write({
#                     'state': 'validate',
#                     'second_approver_id': current_employee.id,
#                 })

#                 # Call parent method to handle leave allocation/deduction
#                 leave._validate_leave_request()

#                 # Post message in chatter
#                 leave.message_post(
#                     body=_('Second and final approval granted by %s') % current_employee.name,
#                     subtype_xmlid='mail.mt_comment'
#                 )

#             else:
#                 raise UserError(_(
#                     'This time off request is in "%s" state and cannot be approved at this time.'
#                 ) % dict(leave._fields['state'].selection).get(leave.state))
#         return True

#     def action_validate(self):
#         """
#         Legacy validation method - redirect to action_approve for consistency
#         """
#         return self.action_approve()

#     def action_refuse(self):
#         """
#         Override refuse to allow both approvers to refuse at their stage
#         """
#         current_user = self.env.user

#         for leave in self:
#             # Check if user has any approval rights
#             is_first_approver = leave._check_approval_rights('first')
#             is_second_approver = leave._check_approval_rights('second')

#             # Allow refusal if user can approve at current or higher level
#             if leave.state == 'confirm' and not is_first_approver:
#                 raise UserError(_(
#                     'Only the employee\'s direct manager can refuse this request at this stage.'
#                 ))

#             if leave.state == 'validate1' and not is_second_approver:
#                 raise UserError(_(
#                     'Only Time Off Officers can refuse this request at this stage.'
#                 ))

#         return super(HrLeaveCustomApproval, self).action_refuse()

#     @api.constrains('employee_id')
#     def _check_employee_has_manager(self):
#         """
#         Ensure employee has a manager set for approval workflow
#         """
#         for leave in self:
#             if leave.state in ['confirm', 'validate1', 'validate']:
#                 if not leave.employee_id.parent_id:
#                     raise UserError(_(
#                         'Employee %s does not have a manager set. '
#                         'Please set a manager in the employee record before requesting time off.'
#                     ) % leave.employee_id.name)