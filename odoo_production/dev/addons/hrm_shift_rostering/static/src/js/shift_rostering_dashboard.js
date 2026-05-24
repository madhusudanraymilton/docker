/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

// ─── Date helpers ─────────────────────────────────────────────────────────────

function fmtDate(d) {
    return d.getFullYear() + '-' +
        String(d.getMonth() + 1).padStart(2, '0') + '-' +
        String(d.getDate()).padStart(2, '0');
}

function parseDate(s) {
    const p = s.split('-');
    return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
}

function addDays(d, n) {
    const r = new Date(d.getTime());
    r.setDate(r.getDate() + n);
    return r;
}

function startOfMonth(d)   { return new Date(d.getFullYear(), d.getMonth(), 1); }
function endOfMonth(d)     { return new Date(d.getFullYear(), d.getMonth() + 1, 0); }
function startOfWeek(d)    {
    const r = new Date(d.getTime());
    const day = r.getDay();
    r.setDate(r.getDate() - (day === 0 ? 6 : day - 1));
    return r;
}
function endOfWeek(d)      { return addDays(startOfWeek(d), 6); }
function startOfQuarter(d) { return new Date(d.getFullYear(), Math.floor(d.getMonth() / 3) * 3, 1); }
function endOfQuarter(d)   { return new Date(d.getFullYear(), Math.floor(d.getMonth() / 3) * 3 + 3, 0); }
function startOfYear(d)    { return new Date(d.getFullYear(), 0, 1); }
function endOfYear(d)      { return new Date(d.getFullYear(), 11, 31); }

function buildDateRange(fromStr, toStr) {
    const dates = [];
    const end = parseDate(toStr);
    let cur = parseDate(fromStr);
    while (cur <= end) {
        dates.push(fmtDate(cur));
        cur = addDays(cur, 1);
    }
    return dates;
}

function buildDisplayRange(fromStr, toStr) {
    function f(d) {
        return String(d.getDate()).padStart(2, '0') + '/' +
            String(d.getMonth() + 1).padStart(2, '0') + '/' +
            d.getFullYear();
    }
    return f(parseDate(fromStr)) + ' \u2192 ' + f(parseDate(toStr));
}

function getDayLabel(s)  { return ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][parseDate(s).getDay()]; }
function getDateNum(s)   { return String(parseDate(s).getDate()).padStart(2, '0'); }
function checkWeekend(s) { const d = parseDate(s).getDay(); return d === 0 || d === 6; }
function checkToday(s)   { return s === fmtDate(new Date()); }
function checkPast(s)    { return s < fmtDate(new Date()); }

// ─── Colour chips ─────────────────────────────────────────────────────────────

const CHIPS = ['chip-blue','chip-green','chip-amber','chip-rose','chip-teal','chip-indigo','chip-orange'];

function calcChipColor(code) {
    if (!code) return '';
    let h = 0;
    for (let i = 0; i < code.length; i++) {
        h = (h * 31 + code.charCodeAt(i)) % CHIPS.length;
    }
    return CHIPS[Math.abs(h)];
}

// ─── ShiftCell ────────────────────────────────────────────────────────────────
// Uses a shared `openKey` string in parent state to ensure only one dropdown
// is open at a time. openKey === empId+':'+date means this cell is open.

class ShiftCell extends Component {
    static template = "hrm_shift_rostering.ShiftCell";
    static props = {
        empKey:        String,
        employeeId:    Number,
        date:          String,
        shiftId:       { optional: true },
        shiftCode:     { type: String, optional: true },
        shifts:        Array,
        openKey:       String,
        searchQ:       String,
        isPast:        Boolean,
        isSelected:    Boolean,
        selectionSize: Number,
        onToggle:      Function,
        onSearch:      Function,
        onPick:        Function,
        onClear:       Function,
    };

    get isOpen()       { return !this.props.isPast && !this.props.selectionSize && this.props.openKey === this.props.empKey; }
    get colorClass()   { return calcChipColor(this.props.shiftCode); }
    getChipColor(code) { return calcChipColor(code); }

    get filtered() {
        const q = this.props.searchQ.toLowerCase();
        if (!q) return this.props.shifts;
        return this.props.shifts.filter(s =>
            s.shift_code.toLowerCase().includes(q) ||
            s.name.toLowerCase().includes(q)
        );
    }

    onToggleClick(ev) {
        ev.stopPropagation();
        // In selection mode, chip click does nothing — td wrapper handles selection
        if (this.props.selectionSize > 0) return;
        this.props.onToggle(this.props.empKey);
    }

    onPickClick(ev) {
        ev.stopPropagation();
        const shiftId = parseInt(ev.currentTarget.dataset.shiftid, 10);
        this.props.onPick(this.props.employeeId, this.props.date, shiftId);
    }

    onClearClick(ev) {
        ev.stopPropagation();
        this.props.onClear(this.props.employeeId, this.props.date);
    }

    onDropdownClick(ev) {
        ev.stopPropagation();
    }

    onSearchInput(ev) {
        this.props.onSearch(ev.target.value);
    }
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

class ShiftRosteringDashboard extends Component {
    static template  = "hrm_shift_rostering.Dashboard";
    static components = { ShiftCell };
    static props      = {};

    setup() {
        this.notification = useService("notification");

        const today = new Date();
        this.state = useState({
            dateFrom:     fmtDate(startOfMonth(today)),
            dateTo:       fmtDate(endOfMonth(today)),
            viewMode:     'month',
            showPicker:   false,
            tempFrom:     fmtDate(startOfMonth(today)),
            tempTo:       fmtDate(endOfMonth(today)),

            employees:    [],
            shifts:       [],
            assignments:  {},

            loading:      true,

            // Single shared dropdown state — only one cell open at a time
            openCellKey:  '',
            cellSearchQ:  '',

            showGear:     false,
            importing:    false,
            importResult: null,

            searchEmp:    '',
            filterDept:   '',
            defaultShift: null,   // { id, shift_code } or null — applied to NS cells on present/future

            // ── Multi-cell selection ──────────────────────────────────────────
            selectedCells:    {},   // { [empKey]: true } — plain object for OWL reactivity
            selectionShiftId: '',   // chosen shift in the bulk action bar
        });

        onMounted(async () => {
            document.addEventListener('click', this._onDocClick.bind(this));
            document.addEventListener('keydown', this._onKeyDown.bind(this));
            await Promise.all([this._loadShifts(), this._loadEmployees()]);
            await this._loadAssignments();
        });

        onWillUnmount(() => {
            document.removeEventListener('click', this._onDocClick.bind(this));
            document.removeEventListener('keydown', this._onKeyDown.bind(this));
        });
    }

    _onDocClick() {
        // Clicking anywhere outside closes dropdowns (but NOT selection — that's intentional)
        this.state.openCellKey = '';
        this.state.cellSearchQ = '';
        this.state.showPicker  = false;
        this.state.showGear    = false;
    }

    _onKeyDown(ev) {
        if (ev.key === 'Escape') {
            this.state.selectedCells    = {};
            this.state.selectionShiftId = '';
            this.state.openCellKey      = '';
            this.state.cellSearchQ      = '';
        }
    }

    closeAll() {
        this.state.openCellKey = '';
        this.state.cellSearchQ = '';
        this.state.showPicker  = false;
        this.state.showGear    = false;
    }

    // ── Data ──────────────────────────────────────────────────────────────────

    async _loadShifts() {
        this.state.shifts = await rpc('/shift_rostering/get_shifts', {});
    }

    async _loadEmployees() {
        this.state.employees = await rpc('/shift_rostering/get_employees', {});
    }

    async _loadAssignments() {
        this.state.loading = true;
        this.state.assignments = await rpc('/shift_rostering/get_assignments', {
            date_from: this.state.dateFrom,
            date_to:   this.state.dateTo,
        });
        this.state.loading = false;
    }

    // ── ShiftCell callbacks (passed as props, no this-binding issues) ─────────

    onCellToggle(empKey) {
        // Toggle: open this cell, close if already open
        if (this.state.openCellKey === empKey) {
            this.state.openCellKey = '';
            this.state.cellSearchQ = '';
        } else {
            this.state.openCellKey = empKey;
            this.state.cellSearchQ = '';
        }
    }

    onCellSearch(q) {
        this.state.cellSearchQ = q;
    }

    async onCellPick(empId, date, shiftId) {
        this.state.openCellKey = '';
        this.state.cellSearchQ = '';
        await rpc('/shift_rostering/set_shift', {
            employee_id: empId,
            date:        date,
            shift_id:    shiftId,
        });
        if (!this.state.assignments[empId]) {
            this.state.assignments[empId] = {};
        }
        const shift = this.state.shifts.find(s => s.id === shiftId);
        this.state.assignments[empId][date] = {
            shift_id:   shiftId,
            shift_code: shift ? shift.shift_code : '',
        };
    }

    async onCellClear(empId, date) {
        this.state.openCellKey = '';
        this.state.cellSearchQ = '';
        await rpc('/shift_rostering/set_shift', {
            employee_id: empId,
            date:        date,
            shift_id:    false,
        });
        if (this.state.assignments[empId]) {
            delete this.state.assignments[empId][date];
        }
    }

    getShiftId(empId, date) {
        const emp = this.state.assignments[empId];
        const rec = emp ? emp[date] : null;
        return rec ? rec.shift_id : false;
    }

    getShiftCode(empId, date) {
        const emp = this.state.assignments[empId];
        const rec = emp ? emp[date] : null;
        return rec ? (rec.shift_code || '') : '';
    }

    getCellKey(empId, date) {
        return empId + ':' + date;
    }

    // ── Multi-cell selection ───────────────────────────────────────────────────

    get selectionSize() {
        return Object.keys(this.state.selectedCells).length;
    }

    isCellSelected(empId, date) {
        return !!this.state.selectedCells[empId + ':' + date];
    }

    // Called when user clicks a <td> date cell — reads empid/date from data attributes
    onCellTdClick(ev) {
        const empId = parseInt(ev.currentTarget.dataset.empid, 10);
        const date  = ev.currentTarget.dataset.date;
        if (checkPast(date)) return;            // past cells not selectable
        ev.stopPropagation();
        const key  = empId + ':' + date;
        const next = Object.assign({}, this.state.selectedCells);
        if (next[key]) {
            delete next[key];
        } else {
            next[key] = true;
        }
        this.state.selectedCells = next;        // full reassign → OWL re-renders
        // Close any open per-cell dropdown
        this.state.openCellKey = '';
        this.state.cellSearchQ = '';
    }

    clearSelection(ev) {
        if (ev) ev.stopPropagation();
        this.state.selectedCells    = {};
        this.state.selectionShiftId = '';
    }

    clearSelectionShiftId(ev) {
        if (ev) ev.stopPropagation();
        this.state.selectionShiftId = '';
    }

    async applySelectionShift(ev) {
        if (ev) ev.stopPropagation();
        const shiftId = this.state.selectionShiftId ? parseInt(this.state.selectionShiftId, 10) : null;
        if (!shiftId) {
            this.notification.add('Please select a shift first.', { type: 'warning' });
            return;
        }
        const shift = this.state.shifts.find(s => s.id === shiftId);
        if (!shift) return;

        const keys = Object.keys(this.state.selectedCells);
        if (!keys.length) {
            this.notification.add('No cells selected.', { type: 'warning' });
            return;
        }

        const toSave = keys.map(k => {
            const idx  = k.indexOf(':');
            const empId = parseInt(k.slice(0, idx), 10);
            const date  = k.slice(idx + 1);
            return { employee_id: empId, date, shift_id: shiftId };
        });

        this.state.loading = true;
        try {
            await rpc('/shift_rostering/set_shift_bulk', { assignments: toSave, overwrite: true });

            // Update local state — full reassign for reactivity
            const newAssignments = Object.assign({}, this.state.assignments);
            for (const a of toSave) {
                if (!newAssignments[a.employee_id]) newAssignments[a.employee_id] = {};
                newAssignments[a.employee_id] = Object.assign({}, newAssignments[a.employee_id], {
                    [a.date]: { shift_id: shiftId, shift_code: shift.shift_code },
                });
            }
            this.state.assignments = newAssignments;

            this.notification.add(
                `"${shift.shift_code}" applied to ${toSave.length} cell(s).`,
                { type: 'success' }
            );
            this.state.selectedCells = {};
        } catch (err) {
            this.notification.add('Failed to apply shift: ' + (err.message || String(err)), { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }

    async clearSelectionShifts(ev) {
        if (ev) ev.stopPropagation();
        const keys = Object.keys(this.state.selectedCells);
        if (!keys.length) return;

        this.state.loading = true;
        try {
            await Promise.all(keys.map(k => {
                const idx   = k.indexOf(':');
                const empId = parseInt(k.slice(0, idx), 10);
                const date  = k.slice(idx + 1);
                return rpc('/shift_rostering/set_shift', { employee_id: empId, date, shift_id: false });
            }));

            const newAssignments = Object.assign({}, this.state.assignments);
            for (const k of keys) {
                const idx   = k.indexOf(':');
                const empId = parseInt(k.slice(0, idx), 10);
                const date  = k.slice(idx + 1);
                if (newAssignments[empId]) {
                    newAssignments[empId] = Object.assign({}, newAssignments[empId]);
                    delete newAssignments[empId][date];
                }
            }
            this.state.assignments = newAssignments;

            this.notification.add(`Cleared ${keys.length} cell(s).`, { type: 'success' });
            this.state.selectedCells = {};
        } catch (err) {
            this.notification.add('Failed to clear shifts: ' + (err.message || String(err)), { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }

    async setDefaultShift(ev) {
        const shiftId = ev.target.value ? parseInt(ev.target.value, 10) : null;
        if (!shiftId) {
            this.state.defaultShift = null;
            return;
        }
        const shift = this.state.shifts.find(s => s.id === shiftId);
        this.state.defaultShift = shift ? { id: shift.id, shift_code: shift.shift_code } : null;
        if (!this.state.defaultShift) return;

        // Collect all blank present/future cells across ALL employees and visible dates
        const today   = fmtDate(new Date());
        const allDates = this.dates.filter(d => d >= today);   // present + future only
        const toSave   = [];

        for (const emp of this.state.employees) {
            for (const date of allDates) {
                const empAssign = this.state.assignments[emp.id];
                const rec       = empAssign ? empAssign[date] : null;
                if (!rec || !rec.shift_id) {
                    toSave.push({ employee_id: emp.id, date, shift_id: shiftId });
                }
            }
        }

        if (toSave.length === 0) return;

        this.state.loading = true;
        try {
            const res = await rpc('/shift_rostering/set_shift_bulk', { assignments: toSave });

            // Update local assignments state for the cells we just saved
            for (const a of toSave) {
                if (!this.state.assignments[a.employee_id]) {
                    this.state.assignments[a.employee_id] = {};
                }
                // Only set if still blank (avoid race if user picked manually mid-flight)
                const cur = this.state.assignments[a.employee_id][a.date];
                if (!cur || !cur.shift_id) {
                    this.state.assignments[a.employee_id][a.date] = {
                        shift_id:   shiftId,
                        shift_code: shift.shift_code,
                    };
                }
            }

            if (res && res.saved) {
                this.notification.add(
                    `Default shift "${shift.shift_code}" applied to ${res.saved} cell(s).`,
                    { type: 'success' }
                );
            }
        } catch (err) {
            this.notification.add('Failed to apply default shift: ' + (err.message || String(err)), { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }

    // ── Navigation ────────────────────────────────────────────────────────────

    get dates() {
        return buildDateRange(this.state.dateFrom, this.state.dateTo);
    }

    get displayRange() {
        return buildDisplayRange(this.state.dateFrom, this.state.dateTo);
    }

    _applyRange(fromDate, toDate, mode) {
        this.state.dateFrom = fmtDate(fromDate);
        this.state.dateTo   = fmtDate(toDate);
        this.state.viewMode = mode;
    }

    async goBack() {
        const f    = parseDate(this.state.dateFrom);
        const t    = parseDate(this.state.dateTo);
        const mode = this.state.viewMode;
        let nf, nt;
        if (mode === 'day') {
            nf = nt = addDays(f, -1);
        } else if (mode === 'week') {
            nf = addDays(f, -7);
            nt = addDays(t, -7);
        } else if (mode === 'month') {
            nf = new Date(f.getFullYear(), f.getMonth() - 1, 1);
            nt = endOfMonth(nf);
        } else if (mode === 'quarter') {
            nf = new Date(f.getFullYear(), f.getMonth() - 3, 1);
            nt = endOfQuarter(nf);
        } else if (mode === 'year') {
            nf = new Date(f.getFullYear() - 1, 0, 1);
            nt = endOfYear(nf);
        } else {
            const days = Math.round((t.getTime() - f.getTime()) / 86400000) + 1;
            nf = addDays(f, -days);
            nt = addDays(t, -days);
        }
        this._applyRange(nf, nt, mode);
        await this._loadAssignments();
    }

    async goForward() {
        const f    = parseDate(this.state.dateFrom);
        const t    = parseDate(this.state.dateTo);
        const mode = this.state.viewMode;
        let nf, nt;
        if (mode === 'day') {
            nf = nt = addDays(t, 1);
        } else if (mode === 'week') {
            nf = addDays(f, 7);
            nt = addDays(t, 7);
        } else if (mode === 'month') {
            nf = new Date(f.getFullYear(), f.getMonth() + 1, 1);
            nt = endOfMonth(nf);
        } else if (mode === 'quarter') {
            nf = new Date(f.getFullYear(), f.getMonth() + 3, 1);
            nt = endOfQuarter(nf);
        } else if (mode === 'year') {
            nf = new Date(f.getFullYear() + 1, 0, 1);
            nt = endOfYear(nf);
        } else {
            const days = Math.round((t.getTime() - f.getTime()) / 86400000) + 1;
            nf = addDays(f, days);
            nt = addDays(t, days);
        }
        this._applyRange(nf, nt, mode);
        await this._loadAssignments();
    }

    async goToday() {
        const today = new Date();
        const mode  = this.state.viewMode;
        let nf, nt;
        if (mode === 'day') {
            nf = nt = today;
        } else if (mode === 'week') {
            nf = startOfWeek(today);
            nt = endOfWeek(today);
        } else if (mode === 'quarter') {
            nf = startOfQuarter(today);
            nt = endOfQuarter(today);
        } else if (mode === 'year') {
            nf = startOfYear(today);
            nt = endOfYear(today);
        } else {
            nf = startOfMonth(today);
            nt = endOfMonth(today);
        }
        this._applyRange(nf, nt, mode);
        await this._loadAssignments();
    }

    async setViewMode(ev) {
        ev.stopPropagation();
        const mode = ev.target.dataset.mode || ev.currentTarget.dataset.mode;
        const ref = parseDate(this.state.dateFrom);
        let nf, nt;
        if (mode === 'day') {
            nf = nt = ref;
        } else if (mode === 'week') {
            nf = startOfWeek(ref);
            nt = endOfWeek(ref);
        } else if (mode === 'month') {
            nf = startOfMonth(ref);
            nt = endOfMonth(ref);
        } else if (mode === 'quarter') {
            nf = startOfQuarter(ref);
            nt = endOfQuarter(ref);
        } else {
            nf = startOfYear(ref);
            nt = endOfYear(ref);
        }
        this._applyRange(nf, nt, mode);
        this.state.showPicker = false;
        await this._loadAssignments();
    }

    togglePicker(ev) {
        ev.stopPropagation();
        this.state.showGear   = false;
        this.state.showPicker = !this.state.showPicker;
        this.state.tempFrom   = this.state.dateFrom;
        this.state.tempTo     = this.state.dateTo;
    }

    async applyRange(ev) {
        ev.stopPropagation();
        this.state.dateFrom   = this.state.tempFrom;
        this.state.dateTo     = this.state.tempTo;
        this.state.viewMode   = 'custom';
        this.state.showPicker = false;
        await this._loadAssignments();
    }

    // ── Gear ──────────────────────────────────────────────────────────────────

    toggleGear(ev) {
        ev.stopPropagation();
        this.state.showPicker = false;
        this.state.showGear   = !this.state.showGear;
    }

    async doExport(ev) {
        ev.stopPropagation();
        this.state.showGear = false;
        try {
            const res = await rpc('/shift_rostering/export_xlsx', {
                date_from: this.state.dateFrom,
                date_to:   this.state.dateTo,
            });
            const a = document.createElement('a');
            a.href = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,' + res.content;
            a.download = 'shift_roster_' + this.state.dateFrom + '_to_' + this.state.dateTo + '.xlsx';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } catch (e) {
            this.notification.add('Export failed: ' + (e.message || String(e)), { type: 'danger' });
        }
    }

    triggerImport(ev) {
        ev.stopPropagation();
        this.state.showGear   = false;
        this.state.importResult = null;
        document.getElementById('sr-file-input').click();
    }

    async onFileChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        this.state.importing    = true;
        this.state.importResult = null;
        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const b64 = e.target.result.split(',')[1];
                const res = await rpc('/shift_rostering/import_xlsx', { file_b64: b64 });
                const hasError = !!(res.errors && res.errors.length > 0);
                this.state.importResult = {
                    imported:  res.imported,
                    skipped:   res.skipped,
                    errorText: hasError ? res.errors.join(' | ') : '',
                    hasError:  hasError,
                };
                if (res.imported > 0) {
                    await this._loadAssignments();
                }
            } catch (err) {
                this.notification.add('Import failed: ' + (err.message || String(err)), { type: 'danger' });
            } finally {
                this.state.importing = false;
                ev.target.value = '';
            }
        };
        reader.readAsDataURL(file);
    }

    clearImportResult() {
        this.state.importResult = null;
    }

    // ── Filters ───────────────────────────────────────────────────────────────

    get filteredEmployees() {
        const q    = this.state.searchEmp.trim().toLowerCase();
        const dept = this.state.filterDept;
        return this.state.employees.filter(e => {
            const nm = !q || e.name.toLowerCase().includes(q) ||
                             (e.barcode && e.barcode.toLowerCase().includes(q));
            const dp = !dept || (e.department_id && e.department_id[1] === dept);
            return nm && dp;
        });
    }

    get departments() {
        const s = new Set();
        this.state.employees.forEach(e => { if (e.department_id) s.add(e.department_id[1]); });
        return Array.from(s).sort();
    }

    // ── Template helpers ──────────────────────────────────────────────────────
    dayLabel(d)  { return getDayLabel(d); }
    dateNum(d)   { return getDateNum(d); }
    isWeekend(d) { return checkWeekend(d); }
    isToday(d)   { return checkToday(d); }
    isPast(d)    { return checkPast(d); }
}

registry.category("actions").add("shift_rostering_dashboard", ShiftRosteringDashboard);
