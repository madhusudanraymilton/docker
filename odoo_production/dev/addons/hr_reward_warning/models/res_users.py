from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_announcement_access = fields.Boolean(
        string="Allow Announcement Module Access",
        store=False,
    )

    # def _compute_announcement_access(self):
    #    
    #     group = self.env.ref(
    #         'hr_reward_warning.group_announcement_access',
    #         raise_if_not_found=False
    #     )
    #     for user in self:
    #         if group:
               
    #             self.env.cr.execute(
    #                 "SELECT 1 FROM res_groups_users_rel "
    #                 "WHERE gid = %s AND uid = %s",
    #                 (group.id, user.id)
    #             )
    #             user.allow_announcement_access = bool(
    #                 self.env.cr.fetchone()
    #             )
    #         else:
    #             user.allow_announcement_access = False

    # def _inverse_announcement_access(self):
    #     
    #     group = self.env.ref(
    #         'hr_reward_warning.group_announcement_access',
    #         raise_if_not_found=False
    #     )
    #     if not group:
    #         return

    #     for user in self:
    #         if user.allow_announcement_access:
    #             self.env.cr.execute(
    #                 "INSERT INTO res_groups_users_rel (gid, uid) "
    #                 "VALUES (%s, %s) ON CONFLICT DO NOTHING",
    #                 (group.id, user.id)
    #             )
    #         else:
    #             self.env.cr.execute(
    #                 "DELETE FROM res_groups_users_rel "
    #                 "WHERE gid = %s AND uid = %s",
    #                 (group.id, user.id)
    #             )

    #     self.env['res.users'].invalidate_model()
    #     self.env.registry.clear_cache()