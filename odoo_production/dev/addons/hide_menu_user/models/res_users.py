
from odoo import api, fields, models


class ResUsers(models.Model):
    """
    Model to handle hiding specific menu items for certain users.
    """
    _inherit = 'res.users'

    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', string="Hidden Menu",
        store=True, help='Select menu items that need to '
                         'be hidden to this user.')
    is_show_specific_menu = fields.Boolean(string='Is Show Specific Menu',
        compute='_compute_is_show_specific_menu',
        help='Field determine to show the hide specific menu'
    )

    def write(self, vals):
       
        #old menu er sahte new menu compere kore new menu add 
        old_hide_menu_map = {record.id: record.hide_menu_ids for record in self}
        res = super().write(vals)
        for record in self:
            old_hide_menu_ids = old_hide_menu_map.get(record.id,
                self.env['ir.ui.menu']
            )

            for menu in record.hide_menu_ids:
                menu.sudo().write({'restrict_user_ids': [fields.Command.link(record.id)]})
            
            removed_menus = old_hide_menu_ids - record.hide_menu_ids
            # what im do now and what hapns previous one
            for menu in removed_menus:
                menu.sudo().write({'restrict_user_ids': [fields.Command.unlink(record.id)]})
        return res
    

    # @api.depends('group_ids')
    # def _compute_is_show_specific_menu(self):
    #     group = self.env.ref('base.group_user', raise_if_not_found=False)
    #     for rec in self:
    #         rec.is_show_specific_menu = not (
    #             group and group.id in rec.group_ids.ids
    #         )

    @api.depends('group_ids')
    def _compute_is_show_specific_menu(self):
       
        group_id = self.env.ref('base.group_user')
        
        for rec in self:
            if group_id and group_id.id in rec.group_ids.ids:
                rec.is_show_specific_menu = False
            else:
                for menu in rec.hide_menu_ids:
                    menu.restrict_user_ids = [fields.Command.unlink(rec.id)]
                rec.hide_menu_ids = [fields.Command.clear()]
                rec.is_show_specific_menu = True
