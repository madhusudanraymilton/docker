
from odoo import fields, models


class IrUiMenu(models.Model):
   
    _inherit = 'ir.ui.menu'

    restrict_user_ids = fields.Many2many(
        'res.users', string="Restricted Users",
        help='Users restricted from accessing this menu.')

    def _filter_visible_menus(self):
       
        menus = super()._filter_visible_menus()

       
       #if self.env.user.has_group('base.group_system'):
        if self.env.user.role == 'group_system':
            return menus
        return menus.filtered(
            lambda menu: self.env.user.id not in menu.restrict_user_ids.ids)


       # If user is admin (Settings group)
        # if self.env.user.has_group('base.group_system'):
        #     return menus

        # # Hide restricted menus
        # return menus.filtered(
        #     lambda menu: self.env.user.id not in menu.restrict_user_ids.ids
        # )