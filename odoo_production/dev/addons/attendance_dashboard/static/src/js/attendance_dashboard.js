import { Component, onWillStart, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

(function () {
    if (window.Chart) return;
    const s = document.createElement("script");
    s.src = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js";
    s.async = false;
    document.head.appendChild(s);
})();

function fmt(n, d = 0) {
    if (n === null || n === undefined) return "—";
    return Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function round1(n) {
    return Math.round(n * 10) / 10;
}

function niceAxis(arr) {
    const v = arr.filter(x => x !== null && x !== undefined && !isNaN(x));
    if (!v.length) return { min: 0, max: 10, stepSize: 2 };
    const hi = Math.max(...v);
    if (hi === 0) return { min: 0, max: 10, stepSize: 2 };
    const rough = hi / 5;
    const mag   = Math.pow(10, Math.floor(Math.log10(rough)));
    let step = mag;
    for (const s of [1,2,2.5,5,10,20,25,50,100,200,500]) {
        if (s * mag >= rough) { step = s * mag; break; }
    }
    return { min: 0, max: Math.ceil((hi + step * 0.1) / step) * step, stepSize: step };
}



const C = {
    blue:"#3b82f6", blueA:"rgba(59,130,246,0.18)", blueD:"#1d4ed8",
    purple:"#8b5cf6", purpleA:"rgba(139,92,246,0.18)",
    teal:"#14b8a6", tealA:"rgba(20,184,166,0.18)",
    green:"#22c55e", amber:"#f59e0b", red:"#ef4444",
    indigo:"#6366f1", pink:"#ec4899",
    grid:"rgba(0,0,0,0.05)", text:"#374151",
};

const TT = {
    backgroundColor:"rgba(17,24,39,0.92)", titleColor:"#f9fafb",
    bodyColor:"#d1d5db", borderColor:"rgba(255,255,255,0.1)",
    borderWidth:1, cornerRadius:4,
    padding:{ top:6, right:10, bottom:6, left:10 },
};

export class AttendanceDashboard extends Component {
    static template = "attendance_dashboard.AttendanceDashboard";
    static props = {
        action:            { type: Object,   optional: true },
        actionId:          { type: Number,   optional: true },
        updateActionState: { type: Function, optional: true },
        className:         { type: String,   optional: true },
    };

    setup() {
        this.actionService = useService("action");
        this.state = useState({
            loading:      true,
            error:        null,
            data:         null,
            chartData:    null,
            departments:  [],
            selectedDept: "all",
            selectedDate: new Date().toISOString().split("T")[0],
            activeTab:    "overview",
            deptData:     [],
            deptLoading:  false,
            overtimeData: [],
            companies:       [],
            selectedCompany: "all",
            expenseData:    null,
            expenseLoading: false,
            payrollData:    null,
            payrollLoading: false,
            loanData:       null,
            loanLoading:    false,
            fleetData:       null,
            fleetLoading:    false,
            frontdeskData:    null,
            frontdeskLoading: false,
            lunchData:    null,
            lunchLoading: false,
            recruitmentData:    null,
            recruitmentLoading: false,

            
        });
        this._charts = {};

        onWillStart(async () => {
            await this._loadDepartments();
            await this._loadCompanies();
            await this._loadPayroll();
            await this._loadExpenses();

            await Promise.all([this._loadAll(),this._loadLoanSummary(),
                this._loadDeptAttendance(), 
                this._loadFleetCost() ,
                this._loadFrontdesk(),
                this._loadLunchSummary(),
                this._loadRecruitment(),
            ]);
        });
        onMounted(() => { this._buildCharts(); });
        onWillUnmount(() => { this._destroyCharts(); });

    }


    

    get kpi() { return this.state.data || {}; }
    get cd()  { return this.state.chartData || {}; }

    //  Data loaders 

    async _loadDepartments() {
        try {
            const d = await rpc("/hr/dashboard/departments", {});
            this.state.departments = d || [];
        } catch (e) { console.error("depts", e); }
    }

    async _loadCompanies() {
        try {
            const c = await rpc("/hr/dashboard/companies", {});
            this.state.companies = c || [];
        } catch (e) { console.error("companies", e); }
    }

    async onCompanyChange(ev) {
        this.state.selectedCompany = ev.target.value;
        this._destroyCharts();
        await Promise.all([
            this._loadAll(), 
            this._loadDeptAttendance() , 
            this._loadPayroll(),
            this._loadExpenses(),
            this._loadLoanSummary(),
            this._loadFleetCost(),
            this._loadFrontdesk(),
            this._loadRecruitment(),
        ]);
        await new Promise(r => setTimeout(r, 60));
        this._buildCharts();
    }


    async _loadExpenses() {
        try {
            this.state.expenseLoading = true;
            const d = await rpc("/hr/dashboard/expense_summary", {
                company_id: this.state.selectedCompany,
                dept_id:    this.state.selectedDept,
            });
            this.state.expenseData    = d || null;
            this.state.expenseLoading = false;
        } catch (e) {
            console.error("expenses", e);
            this.state.expenseLoading = false;
        }
    }

    async _loadLoanSummary() {
        try {
            this.state.loanLoading = true;
            const d = await rpc("/hr/dashboard/loan_summary", {
                company_id: this.state.selectedCompany,
                dept_id:    this.state.selectedDept,
            });
            this.state.loanData    = d || null;
            this.state.loanLoading = false;
        } catch (e) {
            console.error("loan_summary", e);
            this.state.loanLoading = false;
        }
    }


    async _loadFleetCost() {
        try {
            this.state.fleetLoading = true;
            const d = await rpc("/hr/dashboard/fleet_cost_summary", {
                company_id: this.state.selectedCompany,
            });
            this.state.fleetData    = d || null;
            this.state.fleetLoading = false;
        } catch (e) {
            console.error("fleet_cost", e);
            this.state.fleetLoading = false;
        }
    }


    async _loadRecruitment() {
        try {
            this.state.recruitmentLoading = true;
            const d = await rpc("/hr/dashboard/recruitment_summary", {
                company_id: this.state.selectedCompany,
                dept_id:    this.state.selectedDept,
            });
            this.state.recruitmentData    = d || null;
            this.state.recruitmentLoading = false;
        } catch (e) {
            console.error("recruitment", e);
            this.state.recruitmentLoading = false;
        }
    }


    async _loadFrontdesk() {
        try {
            this.state.frontdeskLoading = true;
            const d = await rpc("/hr/dashboard/frontdesk_summary", {
                company_id: this.state.selectedCompany,
            });
            this.state.frontdeskData    = d || null;
            this.state.frontdeskLoading = false;
        } catch (e) {
            console.error("frontdesk", e);
            this.state.frontdeskLoading = false;
        }
    }

    async _loadLunchSummary() {
        try {
            this.state.lunchLoading = true;
            const d = await rpc("/hr/dashboard/lunch_summary", {
                company_id: this.state.selectedCompany,
            });
            this.state.lunchData    = d || null;
            this.state.lunchLoading = false;
        } catch (e) {
            console.error("lunch_summary", e);
            this.state.lunchLoading = false;
        }
    }

    async _loadPayroll() {
        try {
            this.state.payrollLoading = true;
            const d = await rpc("/hr/dashboard/payroll_summary", {
                company_id: this.state.selectedCompany,
                dept_id:    this.state.selectedDept,
            });
            this.state.payrollData    = d || null;
            this.state.payrollLoading = false;
        } catch (e) {
            console.error("payroll", e);
            this.state.payrollLoading = false;
        }
    }



    async _loadAll() {
        try {
            this.state.loading = true;
            this.state.error   = null;

            const [main, charts, overtime] = await Promise.all([
                rpc("/hr/dashboard/data", {
                    dept_id: this.state.selectedDept,
                    selected_date: this.state.selectedDate,
                    company_id:    this.state.selectedCompany,
                }),
                rpc("/hr/dashboard/chart_data", {
                    dept_id: this.state.selectedDept,
                    company_id: this.state.selectedCompany,
                }),
                rpc("/hr/dashboard/overtime_data", {
                    dept_id: this.state.selectedDept,
                    company_id: this.state.selectedCompany,
                }).catch(e => {
                    console.error("overtime rpc failed", e);
                    return [];
                }),
            ]);

            this.state.data         = main;
            this.state.chartData    = charts;
            this.state.overtimeData = overtime || [];
            this.state.loading      = false;

        } catch (e) {
            console.error("loadAll", e);
            this.state.error   = "Failed to load dashboard data. Please refresh.";
            this.state.loading = false;
        }
    }

    


    async _loadDeptAttendance() {
        try {
            this.state.deptLoading = true;
            const d = await rpc("/hr/dashboard/dept_attendance", {
                company_id: this.state.selectedCompany,
            });
            this.state.deptData    = d || [];
            this.state.deptLoading = false;
        } catch (e) {
            console.error("deptAtt", e);
            this.state.deptData    = [];
            this.state.deptLoading = false;
        }
    }

    //Event handlers 

    async onDeptChange(ev) {
        this.state.selectedDept = ev.target.value;
        this._destroyCharts();
        await Promise.all([
            this._loadAll(),
            this._loadDeptAttendance(), 
            this._loadPayroll(),
            this._loadExpenses(),
            this._loadLoanSummary(),
            this._loadFleetCost(),
            this._loadFrontdesk(),
            this._loadRecruitment(),
        ]);
        await new Promise(r => setTimeout(r, 60));
        this._buildCharts();
        
    }

    async onDateChange(ev) {
        this.state.selectedDate = ev.target.value;
        this._destroyCharts();
        await this._loadAll();
        await new Promise(r => setTimeout(r, 60));
        this._buildCharts();
    }

    async onRefresh() {
        this._destroyCharts();
        await Promise.all([
            this._loadAll(), 
            this._loadDeptAttendance() , 
            this._loadPayroll(),
            this._loadExpenses(),
            this._loadLoanSummary(), 
            this._loadFleetCost(),
            this._loadRecruitment(),
        
        ]);
        await new Promise(r => setTimeout(r, 80));
        this._buildCharts();
    }

    // setTab(tab) {
    //     this.state.activeTab = tab;
    //     this._destroyCharts();
    //     setTimeout(() => this._buildCharts(), 80);
    // }

    setTab(tab) {
        this.setTab = this.setTab.bind(this);
    }

    openModel(model) {
        const map = {
            employees:"hr.employee", attendance:"hr.attendance",
            leaves:"hr.leave", departments:"hr.department",
        };
        if (map[model]) {
            this.actionService.doAction({
                type:"ir.actions.act_window", res_model: map[model],
                view_mode:"list,form", views:[[false,"list"],[false,"form"]], target:"current",
            });
        }

        // const map2 = {


        //     person = "hr.employee", person_atten = "hr.attendance",
        //     person_leave_report = "hr.leave", person_dept_finder = "hr.department",
        // };
      
    }

    //Charts 

    _destroyCharts() {
        Object.values(this._charts).forEach(c => c && c.destroy());
        this._charts = {};
    }

    _buildCharts() {
        if (!window.Chart) { setTimeout(() => this._buildCharts(), 300); return; }
        window.Chart.defaults.font  = { family:"'Nunito','Segoe UI',sans-serif", size:11 };
        window.Chart.defaults.color = C.text;

        const d   = this.state.chartData;
        const kpi = this.state.data || {};
        if (!d) return;

        const tab = this.state.activeTab;

        if (tab === "overview") {
            // Work Mode
            this._bar("chart_work_mode", ["WFO","WFH"],
                [kpi.wfo_count||0, kpi.wfh_count||0],
                [C.teal, C.blue], true,
                v => ` ${fmt(v)} employees`);

            // Absence Trend
            this._line("chart_absence_trend", d.absence_labels, [{
                label:"Absences", data:d.absence_trend,
                borderColor:C.purple, backgroundColor:C.purpleA,
            }], "Employees");

            // Leave Pattern
            this._bar(
                "chart_leave_pattern",
                d.lp_labels,
                d.leave_pattern,
                d.leave_pattern.map(v => v > 30 ? C.red : v > 15 ? C.amber : C.blue),
                false,
                v => ` ${fmt(v)} leaves`
            );
            // this._line("chart_leave_pattern", d.lp_labels, [{
            //     label:"On Leave", data:d.leave_pattern,
            //     borderColor:C.blue, backgroundColor:C.blueA,
            // }], "Count", Math.ceil((d.lp_labels||[]).length/10));




            // Experience
            this._bar("chart_experience", d.exp_labels||["0-1","1-3","3-5","5-7","7+"],
                d.exp_data||[0,0,0,0,0],
                [C.amber,C.teal,C.blue,C.purple,C.green], false,
                v => ` ${fmt(v)} employees`);
        }

        // if (tab === "analytics") {
        //     this._line("chart_absence_trend_a", d.absence_labels, [{
        //         label:"Absences", data:d.absence_trend,
        //         borderColor:C.purple, backgroundColor:C.purpleA,
        //     }], "Employees");

        //     this._line("chart_leave_pattern_a", d.lp_labels, [{
        //         label:"On Leave", data:d.leave_pattern,
        //         borderColor:C.blue, backgroundColor:C.blueA,
        //     }], "Count", Math.ceil((d.lp_labels||[]).length/10));

         
        //     if (d.lt_labels && d.lt_labels.length) {
        //         const cols = [C.teal,C.blue,C.purple,C.amber,C.green,C.pink,C.indigo,C.red];
        //         this._hbar("chart_leave_type_a", d.lt_labels, d.lt_pcts,
        //             d.lt_labels.map((_,i)=>cols[i%cols.length]), v => ` ${v}%`, true);
        //     }

        //     // Dept att chart
        //     if (d.dept_labels && d.dept_labels.length) {
        //         this._hbar("chart_dept_att_a", d.dept_labels, d.dept_rates,
        //             d.dept_rates.map(r => r>=90 ? C.blueD : r>=75 ? C.blue : "rgba(59,130,246,0.4)"),
        //             v => ` ${v}%`, true);
        //     }
        // }

        // if (tab === "workforce") {
        //     this._bar("chart_experience_w", d.exp_labels||["0-1","1-3","3-5","5-7","7+"],
        //         d.exp_data||[0,0,0,0,0],
        //         [C.amber,C.teal,C.blue,C.purple,C.green], false,
        //         v => ` ${fmt(v)} employees`);

        //     this._bar("chart_work_mode_w", ["WFO","WFH"],
        //         [kpi.wfo_count||0, kpi.wfh_count||0],
        //         [C.teal, C.blue], true,
        //         v => ` ${fmt(v)} employees`);
        // }

        this._overtimeChart("chart_overtime");
        this._payrollHistoryChart("chart_payroll_history");
        this._expenseChart("chart_emp_distribution");

        this._loanTrendChart("chart_loan_trend");
        this._advTrendChart("chart_adv_trend");
        this._fleetCostChart("chart_fleet_cost");
        this._frontdeskVisitorChart("chart_visitor_trend");
        this._frontdeskDrinkChart("chart_drink_summary");
        this._lunchTrendChart("chart_lunch_trend"); 
        this._lunchLocationChart("chart_lunch_location");

        this._recruitmentTrendChart("chart_recruitment_trend");
        this._recruitmentStageChart("chart_recruitment_stage");
    }



    _expenseChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const ed = this.state.expenseData;
        if (!ed || !ed.dept_breakdown || !ed.dept_breakdown.length) return;

        const labels = ed.dept_breakdown.map(r => r.dept);
        const data   = ed.dept_breakdown.map(r => r.total);
        const cols   = [C.teal, C.blue, C.purple, C.amber, C.green, C.pink, C.indigo, C.red];

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: labels.map((_, i) => cols[i % cols.length]),
                    borderColor:     labels.map((_, i) => cols[i % cols.length]),
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false,
                    barThickness: 22,
                }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ` $${Number(ctx.parsed.x).toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { color: C.grid },
                        beginAtZero: true,
                        ticks: {
                            callback: v => '$' + (v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v),
                            font: { size: 10 },
                        },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: "600" } },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }


    _overtimeChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const ot = this.state.overtimeData || [];
        if (!ot.length) return;

        const labels    = ot.map(r => r.month);
        const hoursData = ot.map(r => r.overtime_hours);
        const empData   = ot.map(r => r.employee_count);

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Overtime Hours",
                        data: hoursData,
                        backgroundColor: C.amber,
                        borderColor: C.amber,
                        borderRadius: 6,
                        yAxisID: "yHrs",
                        order: 2,
                    },
                    {
                        type: "line",
                        label: "Employees with Overtime",
                        data: empData,
                        borderColor: C.teal,
                        backgroundColor: C.tealA,
                        yAxisID: "yEmp",
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 2.5,
                        pointBackgroundColor: C.teal,
                        fill: true,
                        order: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        display: true,
                        position: "top",
                        labels: { boxWidth: 12, font: { size: 11 } },
                    },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => {
                                if (ctx.dataset.yAxisID === "yHrs")
                                    return ` Overtime Hours: ${ctx.parsed.y} hrs`;
                                return ` Employees: ${ctx.parsed.y}`;
                            }
                        }
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 10 } },
                    },
                    yHrs: {
                        position: "left",
                        beginAtZero: true,
                        grid: { color: C.grid },
                        ticks: {
                            callback: v => v + " hrs",
                            font: { size: 10 },
                        },
                        title: {
                            display: true,
                            text: "Hours",
                            font: { size: 10 },
                        },
                    },
                    yEmp: {
                        position: "right",
                        beginAtZero: true,
                        grid: { display: false },
                        ticks: {
                            stepSize: 1,
                            font: { size: 10 },
                        },
                        title: {
                            display: true,
                            text: "Employees",
                            font: { size: 10 },
                        },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }


    // loan summary code added here 

    _loanTrendChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const ld = this.state.loanData;
        if (!ld || !ld.loan_trend || !ld.loan_trend.length) return;

        const labels = ld.loan_trend.map(r => r.label);
        const totals = ld.loan_trend.map(r => r.total);
        const counts = ld.loan_trend.map(r => r.count);

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Loan Amount",
                        data: totals,
                        backgroundColor: C.blue,
                        borderColor: C.blue,
                        borderRadius: 6,
                        yAxisID: "yAmt",
                        order: 2,
                    },
                    {
                        type: "line",
                        label: "No. of Loans",
                        data: counts,
                        borderColor: C.amber,
                        backgroundColor: C.tealA,
                        yAxisID: "yCnt",
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 2.5,
                        pointBackgroundColor: C.amber,
                        fill: false,
                        order: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: true, position: "top", labels: { boxWidth: 12, font: { size: 10 } } },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ctx.dataset.yAxisID === "yAmt"
                                ? ` Amount: $${Number(ctx.parsed.y).toLocaleString('en-US')}`
                                : ` Loans: ${ctx.parsed.y}`,
                        },
                    },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    yAmt: {
                        position: "left", beginAtZero: true, grid: { color: C.grid },
                        ticks: { callback: v => '$' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v), font: { size: 10 } },
                    },
                    yCnt: {
                        position: "right", beginAtZero: true, grid: { display: false },
                        ticks: { stepSize: 1, font: { size: 10 } },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }

    // loan summary code added here 
    _advTrendChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const ld = this.state.loanData;
        if (!ld || !ld.adv_trend || !ld.adv_trend.length) return;

        const labels = ld.adv_trend.map(r => r.label);
        const totals = ld.adv_trend.map(r => r.total);
        const counts = ld.adv_trend.map(r => r.count);

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Advance Amount",
                        data: totals,
                        backgroundColor: C.purple,
                        borderColor: C.purple,
                        borderRadius: 6,
                        yAxisID: "yAmt",
                        order: 2,
                    },
                    {
                        type: "line",
                        label: "No. of Advances",
                        data: counts,
                        borderColor: C.teal,
                        backgroundColor: C.tealA,
                        yAxisID: "yCnt",
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 2.5,
                        pointBackgroundColor: C.teal,
                        fill: false,
                        order: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: true, position: "top", labels: { boxWidth: 12, font: { size: 10 } } },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ctx.dataset.yAxisID === "yAmt"
                                ? ` Amount: $${Number(ctx.parsed.y).toLocaleString('en-US')}`
                                : ` Advances: ${ctx.parsed.y}`,
                        },
                    },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    yAmt: {
                        position: "left", beginAtZero: true, grid: { color: C.grid },
                        ticks: { callback: v => '$' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v), font: { size: 10 } },
                    },
                    yCnt: {
                        position: "right", beginAtZero: true, grid: { display: false },
                        ticks: { stepSize: 1, font: { size: 10 } },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }



    // fleet cost summary code added here

    _fleetCostChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const fd = this.state.fleetData;
        if (!fd || !fd.monthly_trend || !fd.monthly_trend.length) return;

        const labels   = fd.monthly_trend.map(r => r.label);
        const contract = fd.monthly_trend.map(r => r.contract);
        const service  = fd.monthly_trend.map(r => r.service);

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Contract",
                        data: contract,
                        backgroundColor: "#3b82f6",
                        borderColor: "#3b82f6",
                        borderRadius: 5,
                        stack: "cost",
                        order: 2,
                    },
                    {
                        label: "Service",
                        data: service,
                        backgroundColor: "#f472b6",
                        borderColor: "#f472b6",
                        borderRadius: 5,
                        stack: "cost",
                        order: 3,
                    },
                    {
                        type: "line",
                        label: "Sum",
                        data: fd.monthly_trend.map(r => r.total),
                        borderColor: "#e2e8f0",
                        backgroundColor: "transparent",
                        yAxisID: "y",
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 2,
                        pointBackgroundColor: "#e2e8f0",
                        fill: false,
                        order: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        display: true,
                        position: "bottom",
                        labels: { boxWidth: 12, font: { size: 10 } },
                    },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ` ${ctx.dataset.label}: $${Number(ctx.parsed.y).toLocaleString('en-US', { minimumFractionDigits: 0 })}`,
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 10 } },
                        stacked: true,
                    },
                    y: {
                        grid: { color: C.grid },
                        stacked: true,
                        beginAtZero: true,
                        ticks: {
                            callback: v => '$' + (v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v),
                            font: { size: 10 },
                        },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }

    _frontdeskVisitorChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const fd = this.state.frontdeskData;
        if (!fd || !fd.visitor_trend || !fd.visitor_trend.length) return;

        const labels = fd.visitor_trend.map(r => r.label);
        const counts = fd.visitor_trend.map(r => r.count);

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Visitors",
                    data: counts,
                    backgroundColor: counts.map(v =>
                        v === Math.max(...counts) ? C.teal : "rgba(20,184,166,0.45)"
                    ),
                    borderColor: C.teal,
                    borderRadius: 6,
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ` ${ctx.parsed.y} visitors`,
                        },
                    },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    y: {
                        beginAtZero: true,
                        grid: { color: C.grid },
                        ticks: { stepSize: 1, font: { size: 10 } },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }

    _frontdeskDrinkChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const fd = this.state.frontdeskData;
        if (!fd || !fd.drink_summary || !fd.drink_summary.length) return;

        const labels = fd.drink_summary.map(r => r.name);
        const qtys   = fd.drink_summary.map(r => r.qty);
        const cols   = [C.teal, C.blue, C.purple, C.amber, C.green, C.pink, C.indigo, C.red];

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    data: qtys,
                    backgroundColor: labels.map((_, i) => cols[i % cols.length]),
                    borderColor:     labels.map((_, i) => cols[i % cols.length]),
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false,
                    barThickness: 22,
                }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ` ${ctx.parsed.x} served`,
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { color: C.grid },
                        beginAtZero: true,
                        ticks: { font: { size: 10 } },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: "600" } },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }


    _lunchTrendChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const ld = this.state.lunchData;
        if (!ld || !ld.monthly_trend || !ld.monthly_trend.length) return;

        const labels  = ld.monthly_trend.map(r => r.label);
        const counts  = ld.monthly_trend.map(r => r.count);
        const amounts = ld.monthly_trend.map(r => r.amount);

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Orders",
                        data: counts,
                        backgroundColor: C.amber,
                        borderColor: C.amber,
                        borderRadius: 6,
                        yAxisID: "yCnt",
                        order: 2,
                    },
                    {
                        type: "line",
                        label: "Amount",
                        data: amounts,
                        borderColor: C.teal,
                        backgroundColor: C.tealA,
                        yAxisID: "yAmt",
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 2.5,
                        pointBackgroundColor: C.teal,
                        fill: false,
                        order: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        display: true, position: "top",
                        labels: { boxWidth: 12, font: { size: 10 } },
                    },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ctx.dataset.yAxisID === "yCnt"
                                ? ` Orders: ${ctx.parsed.y}`
                                : ` Amount: $${Number(ctx.parsed.y).toLocaleString('en-US')}`,
                        },
                    },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    yCnt: {
                        position: "left", beginAtZero: true, grid: { color: C.grid },
                        ticks: { stepSize: 1, font: { size: 10 } },
                        title: { display: true, text: "Orders", font: { size: 10 } },
                    },
                    yAmt: {
                        position: "right", beginAtZero: true, grid: { display: false },
                        ticks: {
                            callback: v => '$' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v),
                            font: { size: 10 },
                        },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }

    _lunchLocationChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const ld = this.state.lunchData;
        if (!ld || !ld.location_breakdown || !ld.location_breakdown.length) return;

        const labels = ld.location_breakdown.map(r => r.location);
        const counts = ld.location_breakdown.map(r => r.count);
        const cols   = [C.amber, C.teal, C.blue, C.purple, C.green, C.pink, C.indigo, C.red];

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    data: counts,
                    backgroundColor: labels.map((_, i) => cols[i % cols.length]),
                    borderColor:     labels.map((_, i) => cols[i % cols.length]),
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false,
                    barThickness: 22,
                }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ` ${ctx.parsed.x} orders`,
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { color: C.grid },
                        beginAtZero: true,
                        ticks: { font: { size: 10 } },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: "600" } },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }



    _recruitmentTrendChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const rd = this.state.recruitmentData;
        if (!rd || !rd.monthly_trend || !rd.monthly_trend.length) return;

        const labels  = rd.monthly_trend.map(r => r.label);
        const applied = rd.monthly_trend.map(r => r.applied);
        const hired   = rd.monthly_trend.map(r => r.hired);

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Applied",
                        data: applied,
                        backgroundColor: "rgba(99,102,241,0.7)",
                        borderColor: C.indigo,
                        borderRadius: 6,
                        order: 2,
                    },
                    {
                        label: "Hired",
                        data: hired,
                        backgroundColor: C.teal,
                        borderColor: C.teal,
                        borderRadius: 6,
                        order: 3,
                    },
                    {
                        type: "line",
                        label: "Conversion %",
                        data: rd.monthly_trend.map(r =>
                            r.applied ? round1((r.hired / r.applied) * 100) : 0
                        ),
                        borderColor: C.amber,
                        backgroundColor: "transparent",
                        yAxisID: "yPct",
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 2.5,
                        pointBackgroundColor: C.amber,
                        fill: false,
                        order: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        display: true, position: "top",
                        labels: { boxWidth: 12, font: { size: 10 } },
                    },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => {
                                if (ctx.dataset.yAxisID === "yPct")
                                    return ` Conversion: ${ctx.parsed.y}%`;
                                return ` ${ctx.dataset.label}: ${ctx.parsed.y}`;
                            },
                        },
                    },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    y: {
                        position: "left", beginAtZero: true, grid: { color: C.grid },
                        ticks: { stepSize: 1, font: { size: 10 } },
                        title: { display: true, text: "Count", font: { size: 10 } },
                    },
                    yPct: {
                        position: "right", beginAtZero: true,
                        max: 100, grid: { display: false },
                        ticks: {
                            callback: v => v + "%",
                            font: { size: 10 },
                        },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }

    _recruitmentStageChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const rd = this.state.recruitmentData;
        if (!rd || !rd.stage_breakdown || !rd.stage_breakdown.length) return;

        const labels = rd.stage_breakdown.map(r => r.stage);
        const counts = rd.stage_breakdown.map(r => r.count);
        const cols   = [C.indigo, C.blue, C.teal, C.green, C.amber, C.purple, C.pink, C.red];

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    data: counts,
                    backgroundColor: labels.map((_, i) => cols[i % cols.length]),
                    borderColor:     labels.map((_, i) => cols[i % cols.length]),
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false,
                    barThickness: 22,
                }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ` ${ctx.parsed.x} applicants`,
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { color: C.grid },
                        beginAtZero: true,
                        ticks: { stepSize: 1, font: { size: 10 } },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: "600" } },
                    },
                },
                animation: { duration: 700, easing: "easeInOutQuart" },
            },
        });
    }



    //  _loanTrendChart(id) {
    //     const el = document.getElementById(id);
    //     if (!el || this._charts[id]) return;
    //     const ld = this.state.loanData;
    //     if (!ld || !ld.loan_trend || !ld.loan_trend.length) return;

    //     const labels = ld.loan_trend.map(r => r.label);
    //     const totals = ld.loan_trend.map(r => r.total);
    //     const counts = ld.loan_trend.map(r => r.count);

    //     this._charts[id] = new window.Chart(el, {
    //         type: "bar",
    //         data: {
    //             labels,
    //             datasets: [
    //                 {
    //                     label: "Loan Amount",
    //                     data: totals,
    //                     backgroundColor: C.blue,
    //                     borderColor: C.blue,
    //                     borderRadius: 6,
    //                     yAxisID: "yAmt",
    //                     order: 2,
    //                 },
    //                 {
    //                     type: "line",
    //                     label: "No. of Loans",
    //                     data: counts,
    //                     borderColor: C.amber,
    //                     backgroundColor: "rgba(245,158,11,0.1)",
    //                     yAxisID: "yCnt",
    //                     tension: 0.4,
    //                     pointRadius: 4,
    //                     pointHoverRadius: 7,
    //                     borderWidth: 2.5,
    //                     pointBackgroundColor: C.amber,
    //                     fill: false,
    //                     order: 1,
    //                 },
    //             ],
    //         },
    //         options: {
    //             responsive: true,
    //             maintainAspectRatio: false,
    //             interaction: { mode: "index", intersect: false },
    //             plugins: {
    //                 legend: { display: true, position: "top", labels: { boxWidth: 12, font: { size: 10 } } },
    //                 tooltip: {
    //                     ...TT,
    //                     callbacks: {
    //                         label: ctx => ctx.dataset.yAxisID === "yAmt"
    //                             ? ` Amount: $${Number(ctx.parsed.y).toLocaleString('en-US')}`
    //                             : ` Loans: ${ctx.parsed.y}`,
    //                     },
    //                 },
    //             },
    //             scales: {
    //                 x: { grid: { display: false }, ticks: { font: { size: 10 } } },
    //                 yAmt: {
    //                     position: "left", beginAtZero: true, grid: { color: C.grid },
    //                     ticks: {
    //                         callback: v => '$' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v),
    //                         font: { size: 10 },
    //                     },
    //                 },
    //                 yCnt: {
    //                     position: "right", beginAtZero: true, grid: { display: false },
    //                     ticks: { stepSize: 1, font: { size: 10 } },
    //                 },
    //             },
    //             animation: { duration: 700, easing: "easeInOutQuart" },
    //         },
    //     });
    // }

    // _advTrendChart(id) {
    //     const el = document.getElementById(id);
    //     if (!el || this._charts[id]) return;
    //     const ld = this.state.loanData;
    //     if (!ld || !ld.adv_trend || !ld.adv_trend.length) return;

    //     const labels = ld.adv_trend.map(r => r.label);
    //     const totals = ld.adv_trend.map(r => r.total);
    //     const counts = ld.adv_trend.map(r => r.count);

    //     this._charts[id] = new window.Chart(el, {
    //         type: "bar",
    //         data: {
    //             labels,
    //             datasets: [
    //                 {
    //                     label: "Advance Amount",
    //                     data: totals,
    //                     backgroundColor: C.purple,
    //                     borderColor: C.purple,
    //                     borderRadius: 6,
    //                     yAxisID: "yAmt",
    //                     order: 2,
    //                 },
    //                 {
    //                     type: "line",
    //                     label: "No. of Advances",
    //                     data: counts,
    //                     borderColor: C.teal,
    //                     backgroundColor: C.tealA,
    //                     yAxisID: "yCnt",
    //                     tension: 0.4,
    //                     pointRadius: 4,
    //                     pointHoverRadius: 7,
    //                     borderWidth: 2.5,
    //                     pointBackgroundColor: C.teal,
    //                     fill: false,
    //                     order: 1,
    //                 },
    //             ],
    //         },
    //         options: {
    //             responsive: true,
    //             maintainAspectRatio: false,
    //             interaction: { mode: "index", intersect: false },
    //             plugins: {
    //                 legend: { display: true, position: "top", labels: { boxWidth: 12, font: { size: 10 } } },
    //                 tooltip: {
    //                     ...TT,
    //                     callbacks: {
    //                         label: ctx => ctx.dataset.yAxisID === "yAmt"
    //                             ? ` Amount: $${Number(ctx.parsed.y).toLocaleString('en-US')}`
    //                             : ` Advances: ${ctx.parsed.y}`,
    //                     },
    //                 },
    //             },
    //             scales: {
    //                 x: { grid: { display: false }, ticks: { font: { size: 10 } } },
    //                 yAmt: {
    //                     position: "left", beginAtZero: true, grid: { color: C.grid },
    //                     ticks: {
    //                         callback: v => '$' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v),
    //                         font: { size: 10 },
    //                     },
    //                 },
    //                 yCnt: {
    //                     position: "right", beginAtZero: true, grid: { display: false },
    //                     ticks: { stepSize: 1, font: { size: 10 } },
    //                 },
    //             },
    //             animation: { duration: 700, easing: "easeInOutQuart" },
    //         },
    //     });
    // }

    _payrollHistoryChart(id) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const pd = this.state.payrollData;
        if (!pd || !pd.monthly_history || !pd.monthly_history.length) return;

        const labels = pd.monthly_history.map(r => r.label);
        const gross  = pd.monthly_history.map(r => r.gross);
        const net    = pd.monthly_history.map(r => r.net);

        this._charts[id] = new window.Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Gross",
                        data: gross,
                        backgroundColor: "#0d9488",
                        borderColor: "#0d9488",
                        borderRadius: 5,
                        order: 2,
                    },
                    {
                        label: "Net",
                        data: net,
                        backgroundColor: "rgba(13,148,136,0.25)",
                        borderColor: "rgba(13,148,136,0.25)",
                        borderRadius: 5,
                        order: 3,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: true, position: "top", labels: { boxWidth: 10, font: { size: 10 } } },
                    tooltip: {
                        ...TT,
                        callbacks: {
                            label: ctx => ` ${ctx.dataset.label}: $${Number(ctx.parsed.y).toLocaleString('en-US', {minimumFractionDigits:2})}`
                        }
                    },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    y: {
                        grid: { color: "rgba(0,0,0,0.05)" },
                        ticks: {
                            callback: v => '$' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v),
                            font: { size: 10 },
                        },
                        beginAtZero: true,
                    },
                },
                animation: { duration: 600, easing: "easeInOutQuart" },
            },
        });
    }

    _line(id, labels, datasets, yLabel, everyNth=1) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        const allData = datasets.flatMap(ds => ds.data||[]);
        const ax = niceAxis(allData);
        this._charts[id] = new window.Chart(el, {
            type:"line",
            data:{ labels, datasets: datasets.map(ds => ({
                ...ds, fill:true, tension:0.4,
                pointRadius:4, pointHoverRadius:7,
                pointBackgroundColor: ds.borderColor, borderWidth:2.5,
            }))},
            options:{
                responsive:true, maintainAspectRatio:false,
                interaction:{ mode:"index", intersect:false },
                plugins:{
                    legend:{ display: datasets.length>1 },
                    tooltip:{ ...TT, callbacks:{ label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.parsed.y)} ${yLabel}` }},
                },
                scales:{
                    x:{ grid:{display:false}, ticks:{ font:{size:10}, maxRotation:45,
                        callback:(v,i) => i % everyNth === 0 ? labels[i] : "" }},
                    y:{ min:ax.min, max:ax.max, grid:{color:C.grid},
                        ticks:{ stepSize:ax.stepSize } },
                },
                animation:{ duration:600, easing:"easeInOutQuart" },
            },
        });
    }

    _bar(id, labels, data, colors, horizontal, tooltipCb) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        this._charts[id] = new window.Chart(el, {
            type:"bar",
            data:{ labels, datasets:[{
                data, backgroundColor:colors, borderColor:colors,
                borderWidth:1, borderRadius:6, borderSkipped:false,
            }]},
            options:{
                indexAxis: horizontal ? "y" : "x",
                responsive:true, maintainAspectRatio:false,
                plugins:{
                    legend:{display:false},
                    tooltip:{ ...TT, callbacks:{ label: ctx => tooltipCb(horizontal ? ctx.parsed.x : ctx.parsed.y) }},
                },
                scales:{
                    x:{ grid:{color: horizontal ? C.grid : "transparent"}, beginAtZero:true,
                        ticks:{font:{size:11, weight:horizontal?"400":"600"}}},
                    y:{ grid:{color: horizontal ? "transparent" : C.grid}, beginAtZero:true,
                        ticks:{font:{size:11, weight:horizontal?"600":"400"}}},
                },
                animation:{ duration:600, easing:"easeInOutQuart" },
            },
        });
    }

    _hbar(id, labels, data, colors, tooltipCb, percentAxis=false) {
        const el = document.getElementById(id);
        if (!el || this._charts[id]) return;
        this._charts[id] = new window.Chart(el, {
            type:"bar",
            data:{ labels, datasets:[{
                data, backgroundColor:colors, borderColor:colors,
                borderWidth:1, borderRadius:5, borderSkipped:false, barThickness:22,
            }]},
            options:{
                indexAxis:"y", responsive:true, maintainAspectRatio:false,
                plugins:{
                    legend:{display:false},
                    tooltip:{ ...TT, callbacks:{ label: ctx => tooltipCb(ctx.parsed.x) }},
                },
                scales:{
                    x:{ min:0, max: percentAxis ? 100 : undefined,
                        grid:{color:C.grid},
                        ticks:{ callback: v => percentAxis ? v+"%" : v, font:{size:10} }},
                    y:{ grid:{display:false}, ticks:{font:{size:11, weight:"600"}} },
                },
                animation:{ duration:700, easing:"easeInOutQuart" },
            },
        });
    }

    // today attendance status cards click handler

    openTodayFilter(type) {
        const data = this.state.data || {};
        let ids = [];
        let name = '';

        if (type === 'present') {
            ids  = data.today_present_ids || [];
            name = "Today's Present Employees";
        } else if (type === 'absent') {
            ids  = data.today_absent_ids || [];
            name = "Today's Absent Employees";
        } else if (type === 'leave') {
            ids  = data.today_leave_ids || [];
            name = "Today's On Leave Employees";
        }

        if (!ids.length) return;

        this.actionService.doAction({
            type:      'ir.actions.act_window',
            name:      name,
            res_model: 'hr.employee',
            view_mode: 'list,form',
            views:     [[false, 'list'], [false, 'form']],
            target:    'current',
            domain:    [['id', 'in', ids]],
        });
    }



}


registry.category("actions").add(
    "attendance_dashboard.AttendanceDashboard",
    AttendanceDashboard
);