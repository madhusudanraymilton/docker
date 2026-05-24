# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class ZKBioTerminal(models.Model):
    _name = 'zkbio.terminal'
    _description = 'ZKBio Terminal/Device'
    _rec_name = 'name'

    name = fields.Char(string='Terminal Name', required=True)
    serial_number = fields.Char(string='Serial Number', required=True, index=True)
    terminal_id = fields.Char(string='Terminal ID', index=True)
    ip_address = fields.Char(string='IP Address')
    port = fields.Integer(string='Port', default=4370)

    config_id = fields.Many2one('zkbio.config', string='API Configuration', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', related='config_id.company_id', store=True)

    # Status and details
    state = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Error')
    ], string='Status', default='offline')

    active = fields.Boolean(string='Active', default=True)
    last_activity = fields.Datetime(string='Last Activity')
    firmware_version = fields.Char(string='Firmware Version')
    device_model = fields.Char(string='Device Model')

    # Location
    location = fields.Char(string='Location/Department')

    # Statistics
    total_users = fields.Integer(string='Total Users', readonly=True)
    total_transactions = fields.Integer(string='Total Transactions', readonly=True)

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('serial_number_unique', 'unique(serial_number)', 'Serial number must be unique!')
    ]

    def action_refresh_status(self):
        """Refresh terminal status from API"""
        self.ensure_one()
        config = self.config_id

        try:
            url = f"{config.api_url.rstrip('/')}/iclock/api/terminals/{self.terminal_id or self.serial_number}/"
            headers = config._get_headers()

            _logger.info(f"Refreshing terminal status: {url}")
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Map API state values to our selection values
                api_state = str(data.get('state', '0'))
                state_mapping = {
                    '0': 'offline',
                    '1': 'online',
                    '2': 'error',
                    'offline': 'offline',
                    'online': 'online',
                    'error': 'error',
                }
                state = state_mapping.get(api_state, 'offline')

                self.write({
                    'name': data.get('alias') or data.get('sn', self.name),
                    'serial_number': data.get('sn', self.serial_number),
                    'ip_address': data.get('ip_address', self.ip_address),
                    'state': state,
                    'last_activity': fields.Datetime.now(),
                    'firmware_version': data.get('fw_version'),
                    'device_model': data.get('platform'),
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Terminal status refreshed successfully'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_(f'Failed to refresh status: {response.status_code}'))

        except requests.exceptions.RequestException as e:
            _logger.error(f"Status refresh failed: {str(e)}")
            raise UserError(_(f'Refresh failed: {str(e)}'))

    def action_sync_attendance(self):
        """Sync attendance data from this terminal"""
        self.ensure_one()
        # This will be implemented based on specific API endpoints for attendance
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Info'),
                'message': _('Attendance sync functionality will be implemented based on API specifications'),
                'type': 'info',
                'sticky': False,
            }
        }
