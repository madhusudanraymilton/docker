from odoo import models
import logging

_logger = logging.getLogger(__name__)


class HrVersion(models.Model):
    _inherit = 'hr.version'

    def _recompute_work_entries(self, date_from, date_to):
        try:
            return super()._recompute_work_entries(date_from, date_to)
        except ValueError as e:
            if 'Expected singleton' in str(e):
                _logger.warning(
                    "Skipping work entry recompute for hr.version %s due to "
                    "singleton error (likely duplicate overtime lines): %s",
                    self.ids, str(e)
                )
                return
            raise