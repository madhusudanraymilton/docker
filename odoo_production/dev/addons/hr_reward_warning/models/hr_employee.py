
from odoo import fields, models, _

class HrEmployee(models.Model):
    """ Inherited model 'hr.employee' with additional
    fields and methods related to announcements."""
    _inherit = 'hr.employee'

    announcement_count = fields.Integer(compute='_compute_announcement_count',
                                        string='# Announcements',
                                        help="Count of Announcements")

    def _compute_announcement_count(self):
        """ Compute announcement count for an employee """
        for employee in self:
            announcement_ids_general = self.env[
                'hr.announcement'].sudo().search_count(
                [('is_announcement', '=', True),
                 ('state', '=', 'approved'),
                 ('date_start', '<=', fields.Date.today())])
            announcement_ids_emp = (self.env['hr.announcement'].
            sudo().search_count(
                [('employee_ids', 'in', self.id),
                 ('state', '=', 'approved'),
                 ('date_start', '<=', fields.Date.today())]))
            announcement_ids_dep = (self.env['hr.announcement'].
            sudo().search_count(
                [('department_ids', 'in', self.department_id.id),
                 ('state', '=', 'approved'),
                 ('date_start', '<=', fields.Date.today())]))
            announcement_ids_job = (self.env['hr.announcement'].
            sudo().search_count(
                [('position_ids', 'in', self.job_id.id),
                 ('state', '=', 'approved'),
                 ('date_start', '<=', fields.Date.today())]))
            employee.announcement_count = (announcement_ids_general +
                                           announcement_ids_emp +
                                           announcement_ids_dep +
                                           announcement_ids_job)

    def action_open_announcements(self):
        """ Open a view displaying announcements related to the employee. """
        announcement_ids_general = self.env[
            'hr.announcement'].sudo().search(
            [('is_announcement', '=', True),
             ('state', '=', 'approved'),
             ('date_start', '<=', fields.Date.today())])
        announcement_ids_emp = self.env['hr.announcement'].sudo().search(
            [('employee_ids', 'in', self.id),
             ('state', '=', 'approved'),
             ('date_start', '<=', fields.Date.today())])
        announcement_ids_dep = self.env['hr.announcement'].sudo().search(
            [('department_ids', 'in', self.department_id.id),
             ('state', '=', 'approved'),
             ('date_start', '<=', fields.Date.today())])
        announcement_ids_job = self.env['hr.announcement'].sudo().search(
            [('position_ids', 'in', self.job_id.id),
             ('state', '=', 'approved'),
             ('date_start', '<=', fields.Date.today())])
        announcement_ids = (announcement_ids_general.ids +
                            announcement_ids_emp.ids +
                            announcement_ids_job.ids + announcement_ids_dep.ids)
        view_id = self.env.ref('hr_reward_warning.hr_announcement_view_form').id
        if announcement_ids:
            if len(announcement_ids) > 1:
                value = {
                    'domain': [('id', 'in', announcement_ids)],
                    'view_mode': 'list,form',
                    'res_model': 'hr.announcement',
                    'type': 'ir.actions.act_window',
                    'name': _('Announcements'),
                }
            else:
                value = {
                    'view_mode': 'form',
                    'res_model': 'hr.announcement',
                    'view_id': view_id,
                    'type': 'ir.actions.act_window',
                    'name': _('Announcements'),
                    'res_id': announcement_ids and announcement_ids[0],
                }
            return value



# company policy work
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    policy_count = fields.Integer(
        compute='_compute_policy_count',
        string='Policies'
    )

    def _compute_policy_count(self):
        for emp in self:
            general_count = self.env['company.policy'].sudo().search_count([
                ('is_general', '=', True),
                ('date_start', '<=', fields.Date.today()),
                ('date_end', '>=', fields.Date.today()),
            ])

            employee_count = self.env['company.policy'].sudo().search_count([
                ('employee_ids', 'in', emp.id),
                ('date_start', '<=', fields.Date.today()),
                ('date_end', '>=', fields.Date.today()),
            ])

            department_count = self.env['company.policy'].sudo().search_count([
                ('department_ids', 'in', emp.department_id.id),
                ('date_start', '<=', fields.Date.today()),
                ('date_end', '>=', fields.Date.today()),
            ])

            emp.policy_count = general_count + employee_count + department_count

    def action_open_policies(self):
        general = self.env['company.policy'].sudo().search([
            ('is_general', '=', True),
            ('date_start', '<=', fields.Date.today()),
            ('date_end', '>=', fields.Date.today()),
        ])

        emp_specific = self.env['company.policy'].sudo().search([
            ('employee_ids', 'in', self.id),
            ('date_start', '<=', fields.Date.today()),
            ('date_end', '>=', fields.Date.today()),
        ])

        dep_specific = self.env['company.policy'].sudo().search([
            ('department_ids', 'in', self.department_id.id),
            ('date_start', '<=', fields.Date.today()),
            ('date_end', '>=', fields.Date.today()),
        ])

        policy_ids = (general + emp_specific + dep_specific).ids

        return {
            'domain': [('id', 'in', policy_ids)],
            'view_mode': 'tree,form',
            'res_model': 'company.policy',
            'type': 'ir.actions.act_window',
            'name': 'Company Policies',
        }
