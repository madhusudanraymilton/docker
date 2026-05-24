from odoo import api, models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    
    portal_access_date = fields.Datetime(string='Portal Access Date', default=fields.Datetime.now)
    
    
    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)

        for user in users:
            if not user.share or not user.partner_id:
                continue

            
            employee = self.env['hr.employee'].sudo().search([
                '|',
                ('user_id', '=', user.id),
                ('work_email', '=', user.email)
            ], limit=1)

            if employee:
                
                employee.write({'user_id': user.id})
            else:
                
                self.env['hr.employee'].sudo().create({
                    'name': user.name,
                    'user_id': user.id,
                    'work_email': user.email,
                    'work_phone': getattr(user, 'phone', False),
                    'active': True,
                })

        return users