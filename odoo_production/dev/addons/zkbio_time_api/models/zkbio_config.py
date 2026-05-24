# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)


class ZKBioConfig(models.Model):
    _name = 'zkbio.config'
    _description = 'ZKBio Time API Configuration'
    _rec_name = 'name'

    name = fields.Char(string='Configuration Name', required=True, default='ZKBio Time API')
    api_url = fields.Char(
        string='API URL',
        required=True,
        default='http://103.91.230.83:8088',
        help='Base URL for ZKBio Time API'
    )
    api_token = fields.Char(
        string='API Token',
        required=True,
        help='Authentication token for API access'
    )
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # Timezone configuration
    device_timezone = fields.Selection(
        selection=lambda self: self.env['res.partner']._fields['tz'].selection,
        string='Device Timezone',
        default='Asia/Dhaka',
        required=True,
        help='Timezone of the biometric devices. Timestamps from API will be converted from this timezone to UTC.'
    )

    # Auto-sync configuration
    auto_sync_enabled = fields.Boolean(
        string='Enable Auto-sync',
        default=True,
        help='Automatically sync attendance data at regular intervals'
    )
    sync_interval = fields.Integer(
        string='Sync Interval (Minutes)',
        default=20,
        help='Interval in minutes between automatic attendance syncs'
    )
    sync_page_size = fields.Integer(
        string='Records Per Page',
        default=1000,
        help='Number of records to fetch per API request. Higher values reduce API calls but may timeout. Recommended: 500-1000'
    )
    auto_process_attendance = fields.Boolean(
        string='Auto-process to Attendance Logs',
        default=True,
        help='Automatically process synced transactions to HR Attendance Logs'
    )

    # Status fields
    last_sync_date = fields.Datetime(string='Last Sync Date', readonly=True)
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('connected', 'Connected'),
        ('failed', 'Connection Failed')
    ], string='Connection Status', default='not_tested', readonly=True)
    status_message = fields.Text(string='Status Message', readonly=True)

    @api.constrains('active')
    def _check_active_config(self):
        """Ensure only one active configuration per company"""
        for record in self:
            if record.active:
                other_active = self.search([
                    ('id', '!=', record.id),
                    ('active', '=', True),
                    ('company_id', '=', record.company_id.id)
                ])
                if other_active:
                    raise UserError(_('Only one active ZKBio configuration is allowed per company.'))

    @api.constrains('sync_page_size')
    def _check_sync_page_size(self):
        """Ensure page size is within reasonable limits"""
        for record in self:
            if record.sync_page_size and (record.sync_page_size < 10 or record.sync_page_size > 5000):
                raise UserError(_('Records Per Page must be between 10 and 5000. Recommended: 500-1000'))

    def _get_headers(self):
        """Get API request headers"""
        self.ensure_one()
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Token {self.api_token}'
        }

    def _convert_to_utc(self, datetime_str, from_timezone=None):
        """
        Convert datetime string from local timezone to UTC

        Args:
            datetime_str: Datetime string from API (assumed to be in local timezone)
            from_timezone: Source timezone (if None, uses device_timezone from config)

        Returns:
            Datetime string in UTC
        """
        if not datetime_str:
            return False

        # Use configured device timezone if not specified
        if from_timezone is None:
            from_timezone = self.device_timezone or 'Asia/Dhaka'

        try:
            # Parse the datetime string
            # Handle common formats: '2024-02-28 14:30:00' or '2024-02-28T14:30:00'
            if 'T' in str(datetime_str):
                dt = datetime.fromisoformat(str(datetime_str).replace('Z', '+00:00'))
                # If already has timezone info, convert to UTC
                if dt.tzinfo is not None:
                    return dt.astimezone(pytz.UTC).replace(tzinfo=None)
            else:
                # Parse naive datetime
                dt = datetime.strptime(str(datetime_str), '%Y-%m-%d %H:%M:%S')

            # Localize to source timezone (treat as local time)
            local_tz = pytz.timezone(from_timezone)
            local_dt = local_tz.localize(dt)

            # Convert to UTC and remove timezone info (Odoo stores naive UTC)
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

            _logger.debug(f"Converted '{datetime_str}' from {from_timezone} to UTC: {utc_dt}")
            return utc_dt

        except Exception as e:
            _logger.warning(f"Failed to convert datetime '{datetime_str}' from {from_timezone}: {str(e)}")
            # Return original value if conversion fails
            return datetime_str

    def action_test_connection(self):
        """Test API connection"""
        self.ensure_one()
        try:
            url = f"{self.api_url.rstrip('/')}/iclock/api/terminals/"
            headers = self._get_headers()

            _logger.info(f"Testing connection to ZKBio API: {url}")
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                self.write({
                    'connection_status': 'connected',
                    'status_message': f'Connection successful! Response: {response.status_code}'
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Successfully connected to ZKBio Time API'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                self.write({
                    'connection_status': 'failed',
                    'status_message': f'Connection failed with status code: {response.status_code}'
                })
                raise UserError(_(f'Connection failed with status code: {response.status_code}\nResponse: {response.text}'))

        except requests.exceptions.RequestException as e:
            _logger.error(f"Connection test failed: {str(e)}")
            self.write({
                'connection_status': 'failed',
                'status_message': f'Connection error: {str(e)}'
            })
            raise UserError(_(f'Connection failed: {str(e)}'))

    def action_sync_terminals(self):
        """Sync terminals from API"""
        self.ensure_one()
        try:
            url = f"{self.api_url.rstrip('/')}/iclock/api/terminals/"
            headers = self._get_headers()

            _logger.info(f"Syncing terminals from: {url}")
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                terminal_obj = self.env['zkbio.terminal']

                # Handle both list and paginated responses
                terminals_data = data if isinstance(data, list) else data.get('data', data.get('results', []))

                synced_count = 0
                for terminal_data in terminals_data:
                    # Map API state values to our selection values
                    api_state = str(terminal_data.get('state', '0'))
                    state_mapping = {
                        '0': 'offline',
                        '1': 'online',
                        '2': 'error',
                        'offline': 'offline',
                        'online': 'online',
                        'error': 'error',
                    }
                    state = state_mapping.get(api_state, 'offline')

                    terminal_vals = {
                        'name': terminal_data.get('alias') or terminal_data.get('sn', 'Unknown'),
                        'serial_number': terminal_data.get('sn'),
                        'terminal_id': terminal_data.get('terminal_id') or terminal_data.get('id'),
                        'ip_address': terminal_data.get('ip_address'),
                        'state': state,
                        'config_id': self.id,
                    }

                    # Find existing terminal by serial number
                    existing = terminal_obj.search([('serial_number', '=', terminal_vals['serial_number'])], limit=1)
                    if existing:
                        existing.write(terminal_vals)
                    else:
                        terminal_obj.create(terminal_vals)
                    synced_count += 1

                self.write({'last_sync_date': fields.Datetime.now()})

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _(f'Successfully synced {synced_count} terminals'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_(f'Sync failed with status code: {response.status_code}\nResponse: {response.text}'))

        except requests.exceptions.RequestException as e:
            _logger.error(f"Terminal sync failed: {str(e)}")
            raise UserError(_(f'Sync failed: {str(e)}'))

    def action_sync_attendance(self):
        """Sync attendance transactions from API with full pagination support"""
        self.ensure_one()
        try:
            # Get start date (last sync or default to 30 days ago)
            if self.last_sync_date:
                start_time = self.last_sync_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                from datetime import datetime, timedelta
                start_time = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

            # Build initial URL with page_size parameter to fetch more records per request
            base_url = f"{self.api_url.rstrip('/')}/iclock/api/transactions/"
            page_size = self.sync_page_size or 1000
            url = f"{base_url}?start_time={start_time}&page_size={page_size}"
            headers = self._get_headers()

            transaction_obj = self.env['zkbio.transaction']
            new_transactions = transaction_obj.browse()  # Empty recordset to collect new transactions
            synced_count = 0
            total_fetched = 0
            page_count = 0

            _logger.info(f"Starting attendance sync from: {start_time}")
            _logger.info(f"Initial URL: {url}")

            # Pagination loop - fetch ALL pages
            while url:
                page_count += 1
                _logger.info(f"Fetching page {page_count}: {url}")

                response = requests.get(url, headers=headers, timeout=30)

                if response.status_code != 200:
                    raise UserError(_(f'Attendance sync failed with status code: {response.status_code}\nResponse: {response.text}'))

                data = response.json()

                # Handle both list and paginated responses
                if isinstance(data, list):
                    transactions_data = data
                    next_url = None  # No pagination for list response
                else:
                    # Paginated response - try different response formats
                    transactions_data = data.get('data', data.get('results', []))
                    # Check for next page URL
                    next_url = data.get('next') or data.get('next_page_url')

                page_records = len(transactions_data)
                total_fetched += page_records
                _logger.info(f"Page {page_count}: Retrieved {page_records} transactions (Total so far: {total_fetched})")

                # Process transactions from this page
                for trans_data in transactions_data:
                    # Convert punch_time and upload_time from local timezone (GMT+6) to UTC
                    punch_time_utc = self._convert_to_utc(trans_data.get('punch_time'))
                    upload_time_utc = self._convert_to_utc(trans_data.get('upload_time'))

                    trans_vals = {
                        'emp_code': trans_data.get('emp_code'),
                        'punch_time': punch_time_utc,
                        'punch_state': trans_data.get('punch_state'),
                        'verify_type': trans_data.get('verify_type'),
                        'work_code': trans_data.get('work_code'),
                        'terminal_sn': trans_data.get('terminal_sn') or trans_data.get('terminal'),
                        'terminal_alias': trans_data.get('terminal_alias'),
                        'upload_time': upload_time_utc,
                        'temperature': trans_data.get('temperature'),
                        'mask_flag': trans_data.get('mask_flag'),
                        'config_id': self.id,
                    }

                    # Check if transaction already exists
                    existing = transaction_obj.search([
                        ('emp_code', '=', trans_vals['emp_code']),
                        ('punch_time', '=', trans_vals['punch_time']),
                        ('terminal_sn', '=', trans_vals['terminal_sn']),
                        ('config_id', '=', self.id)
                    ], limit=1)

                    if not existing:
                        new_trans = transaction_obj.create(trans_vals)
                        new_transactions |= new_trans  # Add to recordset
                        synced_count += 1

                # Check if there's a next page
                if next_url:
                    url = next_url
                    _logger.info(f"Next page URL found: {url}")
                else:
                    # No more pages
                    url = None
                    _logger.info(f"No more pages. Pagination complete.")

            _logger.info(f"Sync complete: Fetched {total_fetched} transactions across {page_count} pages, {synced_count} new records created")

            self.write({'last_sync_date': fields.Datetime.now()})

            # Auto-process transactions to HR Attendance if enabled
            processed_count = 0
            if self.auto_process_attendance and new_transactions:
                _logger.info(f"Auto-processing {len(new_transactions)} transactions to HR Attendance using First IN - Last OUT per day logic")
                # Process all transactions at once (method handles grouping by employee and date internally)
                new_transactions.action_process_to_attendance()
                # Count how many were successfully processed
                processed_count = len(new_transactions.filtered(lambda t: t.is_processed))

            message = f'Successfully synced {synced_count} new attendance records from {total_fetched} total fetched across {page_count} pages'
            if self.auto_process_attendance and processed_count > 0:
                message += f' and processed {processed_count} to Attendance Logs'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _(message),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.RequestException as e:
            _logger.error(f"Attendance sync failed: {str(e)}")
            raise UserError(_(f'Attendance sync failed: {str(e)}'))

    @api.model
    def cron_sync_attendance(self):
        """Scheduled action to sync attendance from all active configurations"""
        active_configs = self.search([('active', '=', True), ('auto_sync_enabled', '=', True)])

        for config in active_configs:
            try:
                _logger.info(f"Cron: Syncing attendance for config: {config.name}")
                config.action_sync_attendance()
            except Exception as e:
                _logger.error(f"Cron: Failed to sync attendance for config {config.name}: {str(e)}")
                # Continue with next config even if one fails
                continue

    def write(self, vals):
        """Override write to update cron interval when sync settings change"""
        result = super(ZKBioConfig, self).write(vals)

        if 'sync_interval' in vals or 'auto_sync_enabled' in vals:
            self._update_cron_interval()

        return result

    def _update_cron_interval(self):
        """Update the cron job interval based on configuration"""
        cron = self.env.ref('zkbio_time_api.ir_cron_sync_attendance', raise_if_not_found=False)

        if cron:
            # Get the minimum interval from all active configs with auto-sync enabled
            active_configs = self.search([('active', '=', True), ('auto_sync_enabled', '=', True)])

            if active_configs:
                min_interval = min(active_configs.mapped('sync_interval'))
                cron.write({
                    'interval_number': min_interval,
                    'active': True
                })
                _logger.info(f"Updated cron interval to {min_interval} minutes")
            else:
                # No active configs with auto-sync, disable the cron
                cron.write({'active': False})
                _logger.info("Disabled cron job (no active auto-sync configs)")
