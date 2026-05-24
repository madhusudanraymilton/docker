from odoo import http
from odoo.http import request


class ShiftRosteringController(http.Controller):

    @http.route('/shift_rostering/get_employees', type='json', auth='user')
    def get_employees(self):
        employees = request.env['hr.employee'].search_read(
            [],
            ['id', 'name', 'barcode', 'department_id', 'job_id', 'image_128'],
            order='name asc',
        )
        return employees

    @http.route('/shift_rostering/get_shifts', type='json', auth='user')
    def get_shifts(self):
        shifts = request.env['resource.calendar'].search_read(
            [],
            ['id', 'name', 'shift_code'],
            order='shift_code asc',
        )
        return shifts

    @http.route('/shift_rostering/get_assignments', type='json', auth='user')
    def get_assignments(self, date_from, date_to):
        return request.env['shift.assignment'].get_roster_data(date_from, date_to)

    @http.route('/shift_rostering/set_shift', type='json', auth='user')
    def set_shift(self, employee_id, date, shift_id):
        request.env['shift.assignment'].set_shift(employee_id, date, shift_id)
        return True

    @http.route('/shift_rostering/set_shift_bulk', type='json', auth='user')
    def set_shift_bulk(self, assignments, overwrite=False):
        """
        assignments: list of {employee_id, date, shift_id}
        overwrite=False: only fills blank cells (default shift behaviour)
        overwrite=True:  upserts all cells (explicit multi-select apply)
        Returns {saved: N}
        """
        return request.env['shift.assignment'].set_shift_bulk(assignments, overwrite=overwrite)

    @http.route('/shift_rostering/export_xlsx', type='json', auth='user')
    def export_xlsx(self, date_from, date_to):
        b64 = request.env['shift.assignment'].export_xlsx(date_from, date_to)
        return {'content': b64}

    @http.route('/shift_rostering/import_xlsx', type='json', auth='user')
    def import_xlsx(self, file_b64):
        return request.env['shift.assignment'].import_xlsx(file_b64)
