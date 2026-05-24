from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class FestivalBonusWizard(models.TransientModel):
    _name = 'festival.bonus.wizard'
    _description = 'Festival Bonus Wizard'

    pay_type = fields.Selection([
        ('festival_bonus',    'Festival Bonus'),
        ('performance_bonus', 'Performance Bonus'),
        ('special_bonus',     'Special Bonus'),
        ('other',             'Other'),
    ], string='Pay Type', required=True, default='festival_bonus')

    #  use selection fields
    festival_category = fields.Selection([
        ('eid_ul_fitr',    'Eid ul Fitr'),
        ('eid_ul_adha',    'Eid ul Adha'),
        ('durga_puja',     'Durga Puja'),
        ('christmas',      'Christmas'),
        ('buddha_purnima', 'Buddha Purnima'),
        ('other',          'Other'),
    ], string='Festival Category')

    date_from = fields.Date(
        string='Period From', required=True,
        default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(
        string='Period To', required=True,
        default=lambda self: date.today().replace(day=1) + relativedelta(months=1, days=-1))

    structure_id = fields.Many2one(
        'hr.payroll.structure', string='Salary Structure',
        domain=[('name', 'ilike', 'Festival')],
    )

    target_type = fields.Selection([
        ('employee',   'Employee'),
        ('department', 'Department'),
        ('company',    'Company'),
    ], string='Type', required=True, default='company')

    department_ids = fields.Many2many('hr.department', string='Departments')

    contract_length = fields.Integer(
        string='Minimum Contract Length (Months)',
        default=6,
        help='0 = No minimum. Enter months e.g. 6, 12, 24',
    )

    gender_filter = fields.Char(
        string='_gender_raw', default='__all__')
    religion_filter = fields.Char(
        string='_religion_raw', default='__all__')

    gender = fields.Selection(
        selection='_get_gender_selection',
        string='Gender', default='__all__')
    religion = fields.Selection(
        selection='_get_religion_selection',
        string='Religion', default='__all__')

    eligible_employee_ids = fields.Many2many(
        'hr.employee',
        'festival_bonus_wizard_emp_rel',
        'wizard_id', 'employee_id',
        string='Eligible Employees',
    )

    step = fields.Selection([
        ('filters',   'Set Filters'),
        ('employees', 'Select Employees'),
    ], default='filters')


    @api.model
    def _get_gender_selection(self):
        """Read sex/gender selection from hr.employee and prepend All."""
        emp_fields = self.env['hr.employee']._fields
        base = []
        for fname in ('sex', 'gender'):
            if fname in emp_fields:
                sel = emp_fields[fname].selection
                if callable(sel):
                    sel = sel(self.env['hr.employee'])
                base = list(sel)
                break
        return [('__all__', 'All Genders')] + base

    @api.model
    def _get_religion_selection(self):
        """
        hr.employee.religion is a Char field in Odoo 19 — not a Selection.
        We use a fixed list of common religions.
        The filter will do a case-insensitive search on the Char value.
        """
        return [
            ('__all__',     'All Religions'),
            ('islam',       'Islam'),
            ('hinduism',    'Hinduism'),
            ('christianity','Christianity'),
            ('buddhism',    'Buddhism'),
            ('other',       'Other'),
        ]

    @api.onchange('pay_type')
    def _onchange_pay_type(self):
        if self.pay_type != 'festival_bonus':
            self.festival_category = False

    def _get_gender_field(self):
        """Return actual field name for gender on hr.employee."""
        emp_fields = self.env['hr.employee']._fields
        for fname in ('sex', 'gender'):
            if fname in emp_fields:
                return fname
        return None

    def _get_religion_field(self):
        """Return actual field name for religion on hr.employee."""
        if 'religion' in self.env['hr.employee']._fields:
            return 'religion'
        return None

    def _compute_eligible(self):
        domain = [('active', '=', True)]

        if self.target_type == 'department' and self.department_ids:
            domain += [('department_id', 'in', self.department_ids.ids)]

        if self.gender and self.gender != '__all__':
            gf = self._get_gender_field()
            if gf:
                domain += [(gf, '=', self.gender)]

        if self.religion and self.religion != '__all__':
            rf = self._get_religion_field()
            if rf:
                emp_fields = self.env['hr.employee']._fields
                if emp_fields[rf].__class__.__name__ in ('Char', 'Text'):
                    domain += [(rf, 'ilike', self.religion)]
                else:
                    domain += [(rf, '=', self.religion)]

        employees = self.env['hr.employee'].sudo().search(domain)

        if self.contract_length and self.contract_length > 0 and employees:
            cutoff = date.today() - relativedelta(months=self.contract_length)

            emp_fields = self.env['hr.employee']._fields
            if 'contract_date_start' in emp_fields:
                employees = employees.filtered(
                    lambda e: e.contract_date_start and e.contract_date_start <= cutoff
                )
            else:
                versions = self.env['hr.version'].sudo().search([
                    ('employee_id', 'in', employees.ids),
                    ('contract_date_start', '<=', cutoff),
                ])
                eligible_ids = set(versions.mapped('employee_id').ids)
                employees = employees.filtered(lambda e: e.id in eligible_ids)

            _logger.info(
                "Contract filter: min=%d months, cutoff=%s, eligible=%s",
                self.contract_length, cutoff, employees.mapped('name')
            )

        return employees

    
    def action_load_employees(self):
        self.ensure_one()

        if self.pay_type == 'festival_bonus' and not self.festival_category:
            raise UserError("Please select a Festival Category.")
        if self.target_type == 'department' and not self.department_ids:
            raise UserError("Please select at least one Department.")

        employees = self._compute_eligible()
        if not employees:
            raise UserError(
                "No eligible employees found with the selected filters.\n\n"
                "Tips:\n"
                "• Try 'All Religions' or 'All Genders'\n"
                "• Try 'All (No Minimum)' for Contract Length\n"
                "• Check employee Personal tab for Religion and Gender values"
            )

        self.eligible_employee_ids = [(6, 0, employees.ids)]
        self.step = 'employees'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'festival.bonus.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'large'},
        }

    def action_back(self):
        self.step = 'filters'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'festival.bonus.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'medium'},
        }

    def action_generate(self):
        self.ensure_one()

        if not self.eligible_employee_ids:
            raise UserError("Please select at least one employee.")
        if self.date_to < self.date_from:
            raise UserError("Period end date must be after start date.")

        if self.pay_type == 'festival_bonus' and self.festival_category:
            cat_label = dict(self._fields['festival_category'].selection).get(
                self.festival_category, self.festival_category)
            run_name = f"{cat_label} – {self.date_from.strftime('%b %Y')}"
        else:
            type_label = dict(self._fields['pay_type'].selection).get(
                self.pay_type, self.pay_type)
            run_name = f"{type_label} – {self.date_from.strftime('%b %Y')}"

        structure = self.structure_id
        if not structure:
            structure = self.env['hr.payroll.structure'].sudo().search([
                ('name', 'ilike', 'Festival')
            ], limit=1)

        run_vals = {'name': run_name, 'date_start': self.date_from, 'date_end': self.date_to}
        if structure:
            run_vals['structure_id'] = structure.id
        pay_run = self.env['hr.payslip.run'].sudo().create(run_vals)

        Payslip = self.env['hr.payslip']
        default_values = Payslip.default_get(Payslip.fields_get())
        payslip_vals_list = []

        for employee in self.eligible_employee_ids:
            version = self.env['hr.version'].sudo().search([
                ('employee_id', '=', employee.id),
                ('contract_date_start', '<=', self.date_to),
                '|',
                ('contract_date_end', '=', False),
                ('contract_date_end', '>=', self.date_from),
            ], order='date_version desc', limit=1)

            vals = default_values | {
                'name':           run_name,
                'employee_id':    employee.id,
                'payslip_run_id': pay_run.id,
                'date_from':      self.date_from,
                'date_to':        self.date_to,
                'company_id':     pay_run.company_id.id,
            }
            if structure:
                vals['struct_id'] = structure.id
            if version:
                vals['version_id'] = version.id
            payslip_vals_list.append(vals)

        if payslip_vals_list:
            slips = Payslip.sudo().with_context(tracking_disable=True).create(payslip_vals_list)
            try:
                slips._compute_name()
            except Exception:
                pass
            try:
                slips.compute_sheet()
            except Exception:
                pass

        return {
            'type':      'ir.actions.act_window',
            'name':      run_name,
            'res_model': 'hr.payslip.run',
            'res_id':    pay_run.id,
            'view_mode': 'form',
            'target':    'current',
        }