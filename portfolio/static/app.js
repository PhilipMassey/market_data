// Antigravity Markets - Portfolio Valuation Dashboard Javascript Logic

// Global Application State
const state = {
    // Valuation View State
    valuation: {
        rawPositions: [],
        filteredPositions: [],
        totals: {},
        pageSize: 15,
        currentPage: 1,
        sortBy: 'dynamic_value',
        sortDir: 'desc',
        searchQuery: ''
    },
    // Comparison View State
    comparison: {
        rawPositions: [],
        filteredPositions: [],
        totals: {},
        pageSize: 15,
        currentPage: 1,
        sortBy: 'change_dollar',
        sortDir: 'desc',
        searchQuery: ''
    },
    businessDays: [],
    snapshotDates: [],
    allocationChart: null,
    flatpickrStartInstance: null,
    flatpickrEndInstance: null,
    // Rankings View State
    ranks: {
        rawTickers: [],
        filteredTickers: [],
        sectorsIndustries: {},
        dirsPortfolios: {},
        optionsLoaded: false,
        dataLoaded: false,
        period: '1 Month',
        directory: '',
        portfolio: '',
        sector: '',
        industry: '',
        rankFilter: 100,
        pageSize: 15,
        currentPage: 1,
        sortBy: 'risk_reward_rank',
        sortDir: 'asc',
        searchQuery: ''
    }
};

// Utilities & Formatters
function formatCurrency(val) {
    if (val === null || val === undefined || isNaN(val)) return '-';
    const num = parseFloat(val);
    const sign = num < 0 ? '-' : '';
    return sign + '$' + Math.abs(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function formatPercent(val) {
    if (val === null || val === undefined || isNaN(val)) return '-';
    const num = parseFloat(val);
    const prefix = num > 0 ? '+' : '';
    return prefix + num.toFixed(2) + '%';
}

function formatQuantity(val) {
    if (val === null || val === undefined || isNaN(val)) return '-';
    return parseFloat(val).toLocaleString('en-US', {
        maximumFractionDigits: 4
    });
}

// Show/Hide Loading Overlay
function showLoading(show) {
    const loader = document.getElementById('loading-overlay');
    if (loader) {
        if (show) loader.classList.remove('hidden');
        else loader.classList.add('hidden');
    }
}

// Show Error Alert
function showError(message) {
    const banner = document.getElementById('error-banner');
    const msgSpan = document.getElementById('error-message');
    if (banner && msgSpan) {
        msgSpan.textContent = message || 'An error occurred while fetching portfolio data.';
        banner.classList.remove('hidden');
        setTimeout(() => {
            banner.classList.add('hidden');
        }, 8000);
    }
}

// Tab Swapping Logic
function initTabs() {
    const valTabBtn = document.getElementById('tab-btn-valuation');
    const compTabBtn = document.getElementById('tab-btn-comparison');
    const ranksTabBtn = document.getElementById('tab-btn-ranks');
    const valView = document.getElementById('view-valuation');
    const compView = document.getElementById('view-comparison');
    const ranksView = document.getElementById('view-ranks');

    valTabBtn.addEventListener('click', () => {
        valTabBtn.classList.add('active');
        compTabBtn.classList.remove('active');
        ranksTabBtn.classList.remove('active');
        valView.classList.remove('hidden');
        compView.classList.add('hidden');
        ranksView.classList.add('hidden');
    });

    compTabBtn.addEventListener('click', () => {
        compTabBtn.classList.add('active');
        valTabBtn.classList.remove('active');
        ranksTabBtn.classList.remove('active');
        compView.classList.remove('hidden');
        valView.classList.add('hidden');
        ranksView.classList.add('hidden');
        
        // Lazy load snapshot dates if not loaded
        if (!state.snapshotDates || state.snapshotDates.length === 0) {
            loadSnapshotDates();
        }
    });

    ranksTabBtn.addEventListener('click', () => {
        ranksTabBtn.classList.add('active');
        valTabBtn.classList.remove('active');
        compTabBtn.classList.remove('active');
        ranksView.classList.remove('hidden');
        valView.classList.add('hidden');
        compView.classList.add('hidden');
        
        // Lazy load rankings & options if not loaded
        if (!state.ranks.optionsLoaded) {
            loadRanksOptions();
        }
        if (!state.ranks.dataLoaded) {
            loadRanksData();
        }
    });
}

// Load NYSE Business Days
async function loadBusinessDays() {
    try {
        const res = await fetch('/data/business-days');
        if (!res.ok) throw new Error('Failed to load business days');
        state.businessDays = await res.json();
    } catch (err) {
        console.error(err);
    }
}

// Load Snapshot Dates from DB
async function loadSnapshotDates() {
    try {
        const res = await fetch('/data/snapshot-dates');
        if (!res.ok) throw new Error('Failed to load snapshot dates');
        state.snapshotDates = await res.json();
        initDatePicker();
        
        if (state.snapshotDates && state.snapshotDates.length >= 2) {
            loadComparisonData();
        }
    } catch (err) {
        console.error(err);
        showError('Could not load portfolio snapshot dates.');
        initDatePicker();
    }
}

// Init Flatpickr Date Picker
function initDatePicker() {
    const commonConfig = {
        mode: 'single',
        dateFormat: 'Y-m-d',
        theme: 'dark',
        maxDate: 'today'
    };
    
    const startConfig = { ...commonConfig };
    const endConfig = { ...commonConfig };
    
    // If we have snapshot dates from DB, set defaults
    if (state.snapshotDates && state.snapshotDates.length > 0) {
        // Default range (latest two snapshots)
        const defaultEnd = state.snapshotDates[0];
        const defaultStart = state.snapshotDates[1] || state.snapshotDates[0];
        
        startConfig.defaultDate = defaultStart;
        endConfig.defaultDate = defaultEnd;
        
        const startEl = document.getElementById('compare-start-date');
        const endEl = document.getElementById('compare-end-date');
        if (startEl) startEl.value = defaultStart;
        if (endEl) endEl.value = defaultEnd;
    }
    
    state.flatpickrStartInstance = flatpickr('#compare-start-date', startConfig);
    state.flatpickrEndInstance = flatpickr('#compare-end-date', endConfig);
}

// Fetch and load Valuation Data
async function loadValuationData() {
    showLoading(true);
    try {
        const res = await fetch('/data/portfolio');
        if (!res.ok) throw new Error('Failed to fetch valuation data');
        const data = await res.json();
        
        if (!data.date) {
            showError('No portfolio snapshot records found in the database.');
            showLoading(false);
            return;
        }

        // Save state
        state.valuation.rawPositions = data.positions;
        state.valuation.totals = data.totals;
        
        // Update header snapshot date
        document.getElementById('snapshot-date').textContent = data.date;
        
        // Render valuation dashboard
        renderValuationDashboard();
    } catch (err) {
        console.error(err);
        showError(err.message);
    } finally {
        showLoading(false);
    }
}

// Render Valuation Cards, Charts, Stats and Tables
function renderValuationDashboard() {
    // 1. Populate Metrics Cards
    const totals = state.valuation.totals;
    document.getElementById('total-val').textContent = formatCurrency(totals.total_value);
    document.getElementById('total-cost').textContent = formatCurrency(totals.total_cost);
    
    const gainVal = totals.total_gain_dollar;
    const gainPct = totals.total_gain_percent;
    const gainCard = document.getElementById('total-gain');
    const gainPctSpan = document.getElementById('total-gain-percent');
    const gainIconContainer = document.getElementById('total-gain-icon-container');
    const gainIcon = document.getElementById('total-gain-icon');
    
    gainCard.textContent = formatCurrency(gainVal);
    gainPctSpan.textContent = formatPercent(gainPct);
    
    if (gainVal >= 0) {
        gainPctSpan.className = 'metric-subtext green-text';
        gainIconContainer.className = 'card-icon green';
        gainIcon.className = 'fa-solid fa-arrow-trend-up';
    } else {
        gainPctSpan.className = 'metric-subtext red-text';
        gainIconContainer.className = 'card-icon red';
        gainIcon.className = 'fa-solid fa-arrow-trend-down';
    }
    
    const cashVal = totals.cash_value || 0;
    const cashPct = totals.total_value > 0 ? (cashVal / totals.total_value * 100) : 0;
    document.getElementById('total-cash').textContent = formatCurrency(cashVal);
    document.getElementById('cash-percentage').textContent = `${cashPct.toFixed(1)}% Cash Sweep`;

    // 2. Render Allocation Chart
    renderAllocationChart();
    
    // 3. Render Key Stats and Top Holdings
    renderKeyStats();

    // 4. Filter, Sort, Paginate and Render Table
    filterAndRenderValuationTable();
}

// Draw allocation doughnut chart using Chart.js
function renderAllocationChart() {
    const canvas = document.getElementById('allocation-chart');
    if (!canvas) return;
    
    // Aggregate data for chart
    const positions = state.valuation.rawPositions;
    if (positions.length === 0) return;
    
    // Sort positions by value descending
    const sortedPositions = [...positions].sort((a, b) => b.dynamic_value - a.dynamic_value);
    
    // Group smaller allocations into 'Other' if > 6 positions
    const labels = [];
    const values = [];
    const backgroundColors = [
        '#6366f1', // Indigo
        '#10b981', // Emerald
        '#a855f7', // Purple
        '#f59e0b', // Warning
        '#0ea5e9', // Sky Blue
        '#f43f5e', // Rose
        '#84cc16', // Lime
        '#64748b'  // Slate
    ];
    
    const threshold = 6;
    let otherSum = 0;
    
    sortedPositions.forEach((pos, idx) => {
        if (idx < threshold) {
            labels.push(pos.symbol);
            values.push(pos.dynamic_value);
        } else {
            otherSum += pos.dynamic_value;
        }
    });
    
    if (otherSum > 0) {
        labels.push('Other');
        values.push(otherSum);
    }
    
    if (state.allocationChart) {
        state.allocationChart.destroy();
    }
    
    state.allocationChart = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: backgroundColors.slice(0, labels.length),
                borderWidth: 1,
                borderColor: 'rgba(255, 255, 255, 0.08)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#94a3b8',
                        font: {
                            family: 'Inter',
                            size: 11
                        },
                        boxWidth: 12,
                        padding: 10
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const val = context.raw;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = (val / total * 100).toFixed(1);
                            return ` ${context.label}: ${formatCurrency(val)} (${pct}%)`;
                        }
                    }
                }
            },
            cutout: '65%'
        }
    });
}

// Render Key Stats Sidebar Panel
function renderKeyStats() {
    const positions = state.valuation.rawPositions;
    const totals = state.valuation.totals;
    
    // Total Unique positions
    document.getElementById('stat-total-positions').textContent = positions.length;
    
    // Equity Allocation
    const eqVal = totals.equity_value || 0;
    const eqPct = totals.total_value > 0 ? (eqVal / totals.total_value * 100) : 0;
    document.getElementById('stat-equity-alloc').textContent = `${formatCurrency(eqVal)} (${eqPct.toFixed(1)}%)`;
    
    // Cash Allocation
    const cashVal = totals.cash_value || 0;
    const cashPct = totals.total_value > 0 ? (cashVal / totals.total_value * 100) : 0;
    document.getElementById('stat-cash-alloc').textContent = `${formatCurrency(cashVal)} (${cashPct.toFixed(1)}%)`;

    // Render Top 5 Holdings list
    const topHoldingsContainer = document.getElementById('top-holdings-list');
    topHoldingsContainer.innerHTML = '';
    
    const sorted = [...positions].sort((a, b) => b.dynamic_value - a.dynamic_value).slice(0, 5);
    
    sorted.forEach(pos => {
        const weight = totals.total_value > 0 ? (pos.dynamic_value / totals.total_value * 100) : 0;
        const div = document.createElement('div');
        div.className = 'top-holding-item';
        div.innerHTML = `
            <div class="holding-meta">
                <span class="holding-symbol">${pos.symbol}</span>
                <span class="holding-account">${pos.account_name || 'N/A'}</span>
            </div>
            <div class="holding-value-group">
                <span class="holding-val">${formatCurrency(pos.dynamic_value)}</span>
                <span class="holding-weight">${weight.toFixed(1)}%</span>
            </div>
        `;
        topHoldingsContainer.appendChild(div);
    });
}

// Valuation Table Processing
function filterAndRenderValuationTable() {
    let list = [...state.valuation.rawPositions];
    
    // 1. Apply Search Query
    const query = state.valuation.searchQuery.toLowerCase().trim();
    if (query !== '') {
        list = list.filter(pos => {
            const sym = (pos.symbol || '').toLowerCase();
            const acc = (pos.account_name || '').toLowerCase();
            return sym.includes(query) || acc.includes(query);
        });
    }
    
    // 2. Apply Sorting
    const sortBy = state.valuation.sortBy;
    const dir = state.valuation.sortDir === 'asc' ? 1 : -1;
    
    list.sort((a, b) => {
        let valA = a[sortBy];
        let valB = b[sortBy];
        
        // Handle null values
        if (valA === null || valA === undefined) return 1;
        if (valB === null || valB === undefined) return -1;
        
        // String comparisons
        if (typeof valA === 'string') {
            return valA.localeCompare(valB) * dir;
        }
        
        // Numeric comparisons
        return (valA - valB) * dir;
    });
    
    state.valuation.filteredPositions = list;
    
    // Update count label
    document.getElementById('filtered-count').textContent = `(${list.length} positions)`;
    
    // 3. Paginate
    const pageSize = state.valuation.pageSize;
    const totalEntries = list.length;
    let paginatedList = [];
    
    if (pageSize === 'all') {
        state.valuation.currentPage = 1;
        paginatedList = list;
        document.getElementById('pag-start').textContent = totalEntries > 0 ? 1 : 0;
        document.getElementById('pag-end').textContent = totalEntries;
    } else {
        const limit = parseInt(pageSize);
        const totalPages = Math.ceil(totalEntries / limit) || 1;
        
        if (state.valuation.currentPage > totalPages) {
            state.valuation.currentPage = totalPages;
        }
        if (state.valuation.currentPage < 1) {
            state.valuation.currentPage = 1;
        }
        
        const startIdx = (state.valuation.currentPage - 1) * limit;
        const endIdx = Math.min(startIdx + limit, totalEntries);
        paginatedList = list.slice(startIdx, endIdx);
        
        document.getElementById('pag-start').textContent = totalEntries > 0 ? startIdx + 1 : 0;
        document.getElementById('pag-end').textContent = endIdx;
    }
    
    document.getElementById('pag-total').textContent = totalEntries;
    
    // 4. Render Rows
    const tbody = document.getElementById('holdings-table-body');
    tbody.innerHTML = '';
    
    if (paginatedList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align: center; padding: 2rem;">No matching positions found.</td></tr>';
        renderPaginationControls('valuation');
        return;
    }
    
    paginatedList.forEach(pos => {
        const tr = document.createElement('tr');
        
        const changeClass = pos.gain_loss_dollar >= 0 ? 'green-text' : 'red-text';
        const isCashPos = pos.symbol === 'Money Market' || (pos.symbol && pos.symbol.endsWith('**'));
            
        tr.innerHTML = `
            <td class="text-bold">${pos.symbol}</td>
            <td><span class="text-muted">${pos.account_name || '-'}</span></td>
            <td class="text-right">${formatQuantity(pos.quantity)}</td>
            <td class="text-right">${formatCurrency(pos.cost_basis_total)}</td>
            <td class="text-right text-bold">${formatCurrency(pos.dynamic_value)}</td>
            <td class="text-right ${changeClass} text-bold">${isCashPos ? '-' : formatCurrency(pos.gain_loss_dollar)}</td>
            <td class="text-right ${changeClass} text-bold">${isCashPos ? '-' : formatPercent(pos.gain_loss_percent)}</td>
        `;
        tbody.appendChild(tr);
    });
    
    renderPaginationControls('valuation');
}

// Render Table Pagination Controls
function renderPaginationControls(viewType) {
    const viewState = state[viewType];
    const containerId = viewType === 'valuation' ? 'pagination-nav' : 'comparison-pagination-nav';
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = '';
    
    if (viewState.pageSize === 'all') return;
    
    const limit = parseInt(viewState.pageSize);
    const totalEntries = viewState.filteredPositions.length;
    const totalPages = Math.ceil(totalEntries / limit) || 1;
    
    // Prev Button
    const prevBtn = document.createElement('button');
    prevBtn.className = 'pag-btn';
    prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
    prevBtn.disabled = viewState.currentPage === 1;
    prevBtn.addEventListener('click', () => {
        viewState.currentPage--;
        if (viewType === 'valuation') filterAndRenderValuationTable();
        else filterAndRenderComparisonTable();
    });
    container.appendChild(prevBtn);
    
    // Page Numbers (Simple logic, shows 1, 2, ... if many, but keeping it direct for usability)
    const maxVisible = 5;
    let startPage = Math.max(1, viewState.currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    
    if (endPage - startPage + 1 < maxVisible) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const btn = document.createElement('button');
        btn.className = `pag-btn ${i === viewState.currentPage ? 'active' : ''}`;
        btn.textContent = i;
        btn.addEventListener('click', () => {
            viewState.currentPage = i;
            if (viewType === 'valuation') filterAndRenderValuationTable();
            else filterAndRenderComparisonTable();
        });
        container.appendChild(btn);
    }
    
    // Next Button
    const nextBtn = document.createElement('button');
    nextBtn.className = 'pag-btn';
    nextBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
    nextBtn.disabled = viewState.currentPage === totalPages;
    nextBtn.addEventListener('click', () => {
        viewState.currentPage++;
        if (viewType === 'valuation') filterAndRenderValuationTable();
        else filterAndRenderComparisonTable();
    });
    container.appendChild(nextBtn);
}

// Fetch and load Comparison Data
async function loadComparisonData() {
    const startInput = document.getElementById('compare-start-date');
    const endInput = document.getElementById('compare-end-date');
    if (!startInput || !startInput.value || !endInput || !endInput.value) {
        showError('Please select both start and end dates first.');
        return;
    }
    
    const startDate = startInput.value;
    const endDate = endInput.value;
    
    showLoading(true);
    try {
        const url = `/data/compare?start_date=${startDate}&end_date=${endDate}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch comparison data');
        const data = await res.json();
        
        state.comparison.rawPositions = data.positions;
        state.comparison.totals = data.totals;
        
        // Render comparison dashboard
        renderComparisonDashboard(data.start_date, data.end_date);
    } catch (err) {
        console.error(err);
        showError(err.message);
    } finally {
        showLoading(false);
    }
}

// Render Comparison Cards and Tables
function renderComparisonDashboard(startDate, endDate) {
    const totals = state.comparison.totals;
    
    // 1. Metrics Cards
    document.getElementById('comp-start-val').textContent = formatCurrency(totals.start_value);
    document.getElementById('comp-start-date-label').textContent = `As of ${startDate}`;
    
    document.getElementById('comp-end-val').textContent = formatCurrency(totals.end_value);
    document.getElementById('comp-end-date-label').textContent = `As of ${endDate}`;
    
    const gainVal = totals.change_dollar;
    const gainPct = totals.change_percent;
    
    const gainCard = document.getElementById('comp-gain');
    const gainPctSpan = document.getElementById('comp-gain-percent');
    const gainIconContainer = document.getElementById('comp-gain-icon-container');
    const gainIcon = document.getElementById('comp-gain-icon');
    
    gainCard.textContent = formatCurrency(gainVal);
    gainPctSpan.textContent = formatPercent(gainPct);
    
    if (gainVal >= 0) {
        gainPctSpan.className = 'metric-subtext green-text';
        gainIconContainer.className = 'card-icon green';
        gainIcon.className = 'fa-solid fa-arrow-trend-up';
    } else {
        gainPctSpan.className = 'metric-subtext red-text';
        gainIconContainer.className = 'card-icon red';
        gainIcon.className = 'fa-solid fa-arrow-trend-down';
    }
    
    // 2. Filter, Sort and Render comparison table
    filterAndRenderComparisonTable();
}

// Comparison Table Processing
function filterAndRenderComparisonTable() {
    let list = [...state.comparison.rawPositions];
    
    // 1. Search Query
    const query = state.comparison.searchQuery.toLowerCase().trim();
    if (query !== '') {
        list = list.filter(pos => {
            const sym = (pos.symbol || '').toLowerCase();
            const acc = (pos.account_name || '').toLowerCase();
            return sym.includes(query) || acc.includes(query);
        });
    }
    
    // 2. Sorting
    const sortBy = state.comparison.sortBy;
    const dir = state.comparison.sortDir === 'asc' ? 1 : -1;
    
    list.sort((a, b) => {
        let valA = a[sortBy];
        let valB = b[sortBy];
        
        if (valA === null || valA === undefined) return 1;
        if (valB === null || valB === undefined) return -1;
        
        if (typeof valA === 'string') {
            return valA.localeCompare(valB) * dir;
        }
        
        return (valA - valB) * dir;
    });
    
    state.comparison.filteredPositions = list;
    
    // Count Label
    document.getElementById('comp-filtered-count').textContent = `(${list.length} positions)`;
    
    // 3. Paginate
    const pageSize = state.comparison.pageSize;
    const totalEntries = list.length;
    let paginatedList = [];
    
    if (pageSize === 'all') {
        state.comparison.currentPage = 1;
        paginatedList = list;
        document.getElementById('comp-pag-start').textContent = totalEntries > 0 ? 1 : 0;
        document.getElementById('comp-pag-end').textContent = totalEntries;
    } else {
        const limit = parseInt(pageSize);
        const totalPages = Math.ceil(totalEntries / limit) || 1;
        
        if (state.comparison.currentPage > totalPages) {
            state.comparison.currentPage = totalPages;
        }
        if (state.comparison.currentPage < 1) {
            state.comparison.currentPage = 1;
        }
        
        const startIdx = (state.comparison.currentPage - 1) * limit;
        const endIdx = Math.min(startIdx + limit, totalEntries);
        paginatedList = list.slice(startIdx, endIdx);
        
        document.getElementById('comp-pag-start').textContent = totalEntries > 0 ? startIdx + 1 : 0;
        document.getElementById('comp-pag-end').textContent = endIdx;
    }
    
    document.getElementById('comp-pag-total').textContent = totalEntries;
    
    // 4. Render rows
    const tbody = document.getElementById('comparison-table-body');
    tbody.innerHTML = '';
    
    if (paginatedList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align: center; padding: 2rem;">No matching positions found.</td></tr>';
        renderPaginationControls('comparison');
        return;
    }
    
    paginatedList.forEach(pos => {
        const tr = document.createElement('tr');
        const changeClass = pos.change_dollar >= 0 ? 'green-text' : 'red-text';
        const isCashPos = pos.symbol === 'Money Market' || (pos.symbol && pos.symbol.endsWith('**'));
        
        let qtyChangeStr = '-';
        let qtyChangeClass = 'text-muted';
        if (pos.qty_change !== null && pos.qty_change !== undefined) {
            const qtyDiff = pos.qty_change;
            if (qtyDiff > 0) {
                qtyChangeStr = `+${formatQuantity(qtyDiff)}`;
                qtyChangeClass = 'green-text text-bold';
            } else if (qtyDiff < 0) {
                qtyChangeStr = formatQuantity(qtyDiff);
                qtyChangeClass = 'red-text text-bold';
            } else {
                qtyChangeStr = '0';
                qtyChangeClass = '';
            }
        }
        
        tr.innerHTML = `
            <td class="text-bold">${pos.symbol}</td>
            <td><span class="text-muted">${pos.account_name || '-'}</span></td>
            <td class="text-right ${qtyChangeClass}">${qtyChangeStr}</td>
            <td class="text-right">${formatCurrency(pos.start_value)}</td>
            <td class="text-right">${formatCurrency(pos.end_value)}</td>
            <td class="text-right ${changeClass} text-bold">${isCashPos ? '-' : formatCurrency(pos.change_dollar)}</td>
            <td class="text-right ${changeClass} text-bold">${isCashPos ? '-' : formatPercent(pos.change_percent)}</td>
        `;
        tbody.appendChild(tr);
    });
    
    renderPaginationControls('comparison');
}

// Bind sorting listeners to table headers
function initSortHeaders() {
    // Holdings table headers
    document.querySelectorAll('#holdings-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const field = th.dataset.sort;
            if (state.valuation.sortBy === field) {
                state.valuation.sortDir = state.valuation.sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                state.valuation.sortBy = field;
                state.valuation.sortDir = 'desc'; // default high to low
            }
            
            // Update icons
            document.querySelectorAll('#holdings-table th.sortable i').forEach(i => {
                i.className = 'fa-solid fa-sort';
            });
            const icon = th.querySelector('i');
            icon.className = state.valuation.sortDir === 'asc' ? 'fa-solid fa-sort-up' : 'fa-solid fa-sort-down';
            
            filterAndRenderValuationTable();
        });
    });
    
    // Comparison table headers
    document.querySelectorAll('#comparison-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const field = th.dataset.sort;
            if (state.comparison.sortBy === field) {
                state.comparison.sortDir = state.comparison.sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                state.comparison.sortBy = field;
                state.comparison.sortDir = 'desc';
            }
            
            // Update icons
            document.querySelectorAll('#comparison-table th.sortable i').forEach(i => {
                i.className = 'fa-solid fa-sort';
            });
            const icon = th.querySelector('i');
            icon.className = state.comparison.sortDir === 'asc' ? 'fa-solid fa-sort-up' : 'fa-solid fa-sort-down';
            
            filterAndRenderComparisonTable();
        });
    });

    // Ranks table headers
    document.querySelectorAll('#ranks-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const field = th.dataset.sort;
            const isRankField = field.endsWith('_rank');
            if (state.ranks.sortBy === field) {
                state.ranks.sortDir = state.ranks.sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                state.ranks.sortBy = field;
                // Ranks are usually sorted asc (1, 2, 3...) whereas percentages are sorted desc (high to low)
                state.ranks.sortDir = isRankField ? 'asc' : 'desc';
            }
            
            // Update icons
            document.querySelectorAll('#ranks-table th.sortable i').forEach(i => {
                i.className = 'fa-solid fa-sort';
            });
            const icon = th.querySelector('i');
            icon.className = state.ranks.sortDir === 'asc' ? 'fa-solid fa-sort-up' : 'fa-solid fa-sort-down';
            
            filterAndRenderRanksTable();
        });
    });
}

// Bind search and size controls
function initToolbarControls() {
    // Valuation Search
    const searchVal = document.getElementById('search-input');
    searchVal.addEventListener('input', (e) => {
        state.valuation.searchQuery = e.target.value;
        state.valuation.currentPage = 1;
        filterAndRenderValuationTable();
    });
    
    // Valuation Page Size
    const sizeVal = document.getElementById('page-size-select');
    sizeVal.addEventListener('change', (e) => {
        state.valuation.pageSize = e.target.value;
        state.valuation.currentPage = 1;
        filterAndRenderValuationTable();
    });
    
    // Comparison Search
    const searchComp = document.getElementById('compare-search-input');
    searchComp.addEventListener('input', (e) => {
        state.comparison.searchQuery = e.target.value;
        state.comparison.currentPage = 1;
        filterAndRenderComparisonTable();
    });
    
    // Comparison Page Size
    const sizeComp = document.getElementById('compare-page-size-select');
    sizeComp.addEventListener('change', (e) => {
        state.comparison.pageSize = e.target.value;
        state.comparison.currentPage = 1;
        filterAndRenderComparisonTable();
    });
    
    // Refresh Button click
    document.getElementById('btn-refresh').addEventListener('click', () => {
        loadValuationData();
    });
    
    // Compare Button click
    document.getElementById('btn-compare').addEventListener('click', () => {
        loadComparisonData();
    });

    // Ranks Search Input
    const searchRanks = document.getElementById('ranks-search-input');
    searchRanks.addEventListener('input', (e) => {
        state.ranks.searchQuery = e.target.value;
        state.ranks.currentPage = 1;
        filterAndRenderRanksTable();
    });

    // Ranks Period select
    const periodRanks = document.getElementById('rank-period-select');
    periodRanks.addEventListener('change', (e) => {
        state.ranks.period = e.target.value;
        state.ranks.currentPage = 1;
        loadRanksData();
    });

    // Ranks Portfolio select
    const portRanks = document.getElementById('rank-port-select');
    portRanks.addEventListener('change', (e) => {
        state.ranks.portfolio = e.target.value;
        state.ranks.currentPage = 1;
        loadRanksData();
    });

    // Ranks Industry select
    const indRanks = document.getElementById('rank-industry-select');
    indRanks.addEventListener('change', (e) => {
        state.ranks.industry = e.target.value;
        state.ranks.currentPage = 1;
        loadRanksData();
    });

    // Ranks Slider Threshold Input
    const sliderRanks = document.getElementById('rank-slider-input');
    const sliderVal = document.getElementById('rank-slider-val');
    sliderRanks.addEventListener('input', (e) => {
        const val = parseInt(e.target.value);
        sliderVal.textContent = val === 100 ? 'All' : `Top ${val}`;
        state.ranks.rankFilter = val;
        state.ranks.currentPage = 1;
        loadRanksData();
    });

    // Detail Panel close button click
    const btnCloseDetail = document.getElementById('btn-close-detail');
    btnCloseDetail.addEventListener('click', () => {
        document.getElementById('ranks-detail-panel').classList.add('hidden');
    });
}

// Load Rankings Options (folders, portfolios, sectors, industries)
async function loadRanksOptions() {
    try {
        const res = await fetch('/data/ticker-ranks/options');
        if (!res.ok) throw new Error('Failed to load ranking options');
        const data = await res.json();
        
        state.ranks.sectorsIndustries = data.sectors_industries;
        state.ranks.dirsPortfolios = data.dirs_portfolios;
        state.ranks.optionsLoaded = true;
        
        populateRanksFilters();
    } catch (err) {
        showError('Error loading ranking options: ' + err.message);
    }
}

// Populate Rankings Filter Dropdowns
function populateRanksFilters() {
    const dirSelect = document.getElementById('rank-dir-select');
    const sectorSelect = document.getElementById('rank-sector-select');
    
    // Clear and populate Folders
    dirSelect.innerHTML = '<option value="">-- All Folders --</option>';
    Object.keys(state.ranks.dirsPortfolios).forEach(folder => {
        const opt = document.createElement('option');
        opt.value = folder;
        opt.textContent = folder;
        dirSelect.appendChild(opt);
    });
    
    // Clear and populate Sectors
    sectorSelect.innerHTML = '<option value="">-- All Sectors --</option>';
    Object.keys(state.ranks.sectorsIndustries).forEach(sector => {
        const opt = document.createElement('option');
        opt.value = sector;
        opt.textContent = sector;
        sectorSelect.appendChild(opt);
    });
    
    // Wire up dynamic dependency listeners
    dirSelect.addEventListener('change', (e) => {
        state.ranks.directory = e.target.value;
        state.ranks.portfolio = '';
        state.ranks.currentPage = 1;
        populateRanksPortfolios(e.target.value);
        loadRanksData();
    });
    
    sectorSelect.addEventListener('change', (e) => {
        state.ranks.sector = e.target.value;
        state.ranks.industry = '';
        state.ranks.currentPage = 1;
        populateRanksIndustries(e.target.value);
        loadRanksData();
    });
}

function populateRanksPortfolios(folder) {
    const portSelect = document.getElementById('rank-port-select');
    portSelect.innerHTML = '<option value="">-- All Portfolios --</option>';
    if (folder && state.ranks.dirsPortfolios[folder]) {
        state.ranks.dirsPortfolios[folder].forEach(port => {
            const opt = document.createElement('option');
            opt.value = port;
            opt.textContent = port;
            portSelect.appendChild(opt);
        });
    }
}

function populateRanksIndustries(sector) {
    const indSelect = document.getElementById('rank-industry-select');
    indSelect.innerHTML = '<option value="">-- All Industries --</option>';
    if (sector && state.ranks.sectorsIndustries[sector]) {
        state.ranks.sectorsIndustries[sector].forEach(ind => {
            const opt = document.createElement('option');
            opt.value = ind;
            opt.textContent = ind;
            indSelect.appendChild(opt);
        });
    }
}

// Load Rankings Data from Server
async function loadRanksData() {
    showLoading(true);
    try {
        let url = `/data/ticker-ranks?period=${state.ranks.period}`;
        if (state.ranks.directory) url += `&directory=${state.ranks.directory}`;
        if (state.ranks.portfolio) url += `&portfolio=${state.ranks.portfolio}`;
        if (state.ranks.sector) url += `&sector=${encodeURIComponent(state.ranks.sector)}`;
        if (state.ranks.industry) url += `&industry=${encodeURIComponent(state.ranks.industry)}`;
        if (state.ranks.rankFilter < 100) url += `&rank_filter=${state.ranks.rankFilter}`;
        
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to load ranking data');
        state.ranks.rawTickers = await res.json();
        state.ranks.dataLoaded = true;
        
        filterAndRenderRanksTable();
    } catch (err) {
        showError('Error loading ranking data: ' + err.message);
    } finally {
        showLoading(false);
    }
}

// Filter and Render the Ranks Table
function filterAndRenderRanksTable() {
    let tickers = [...state.ranks.rawTickers];
    
    // Apply client-side text search
    if (state.ranks.searchQuery) {
        const query = state.ranks.searchQuery.toUpperCase();
        tickers = tickers.filter(t => t.ticker.toUpperCase().includes(query));
    }
    
    // Sort
    const field = state.ranks.sortBy;
    const dir = state.ranks.sortDir === 'asc' ? 1 : -1;
    tickers.sort((a, b) => {
        let valA = a[field];
        let valB = b[field];
        
        if (valA === null || valA === undefined) return 1;
        if (valB === null || valB === undefined) return -1;
        
        if (typeof valA === 'string') {
            return valA.localeCompare(valB) * dir;
        }
        return (valA - valB) * dir;
    });
    
    state.ranks.filteredTickers = tickers;
    document.getElementById('ranks-filtered-count').textContent = `(${tickers.length} tickers)`;
    
    // Pagination
    const total = tickers.length;
    const size = state.ranks.pageSize === 'all' ? total : parseInt(state.ranks.pageSize);
    const totalPages = Math.ceil(total / size) || 1;
    
    if (state.ranks.currentPage > totalPages) {
        state.ranks.currentPage = totalPages;
    }
    
    const startIdx = (state.ranks.currentPage - 1) * size;
    const endIdx = Math.min(startIdx + size, total);
    const paginated = tickers.slice(startIdx, endIdx);
    
    // Update pagination info label
    document.getElementById('ranks-pag-start').textContent = total === 0 ? 0 : startIdx + 1;
    document.getElementById('ranks-pag-end').textContent = endIdx;
    document.getElementById('ranks-pag-total').textContent = total;
    
    // Render Rows
    const tbody = document.getElementById('ranks-table-body');
    tbody.innerHTML = '';
    
    if (paginated.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No ranked tickers found matching current filters.</td></tr>`;
        renderRanksPagination(totalPages);
        return;
    }
    
    paginated.forEach(t => {
        const tr = document.createElement('tr');
        tr.className = 'clickable-row';
        tr.innerHTML = `
            <td class="text-bold">${t.ticker}</td>
            <td class="text-right rank-highlight">#${t.risk_reward_rank}</td>
            <td class="text-right ${t.over_pc >= 0 ? 'green-text' : 'red-text'}">${t.over_pc.toFixed(2)}%</td>
            <td class="text-right">${t.pc_mean.toFixed(3)}%</td>
            <td class="text-right">${t.pc_std.toFixed(3)}%</td>
            <td class="text-right">#${t.prob_green_day_rank}</td>
            <td class="text-right">#${t.stretch_score_rank}</td>
            <td class="text-right">#${t.kelly_fraction_rank}</td>
        `;
        tr.addEventListener('click', () => showRanksDetail(t.ticker));
        tbody.appendChild(tr);
    });
    
    renderRanksPagination(totalPages);
}

// Render Rankings Pagination Controls
function renderRanksPagination(totalPages) {
    const nav = document.getElementById('ranks-pagination-nav');
    nav.innerHTML = '';
    
    if (totalPages <= 1) return;
    
    // Prev Button
    const prevBtn = document.createElement('button');
    prevBtn.className = `btn btn-secondary btn-sm ${state.ranks.currentPage === 1 ? 'disabled' : ''}`;
    prevBtn.innerHTML = '<i class="fa-solid fa-angle-left"></i>';
    prevBtn.addEventListener('click', () => {
        if (state.ranks.currentPage > 1) {
            state.ranks.currentPage--;
            filterAndRenderRanksTable();
        }
    });
    nav.appendChild(prevBtn);
    
    // Page Numbers
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || Math.abs(state.ranks.currentPage - i) <= 1) {
            const pageBtn = document.createElement('button');
            pageBtn.className = `btn btn-sm ${state.ranks.currentPage === i ? 'btn-primary' : 'btn-secondary'}`;
            pageBtn.textContent = i;
            pageBtn.addEventListener('click', () => {
                state.ranks.currentPage = i;
                filterAndRenderRanksTable();
            });
            nav.appendChild(pageBtn);
        } else if (i === 2 || i === totalPages - 1) {
            const ellipsis = document.createElement('span');
            ellipsis.className = 'pagination-ellipsis';
            ellipsis.textContent = '...';
            nav.appendChild(ellipsis);
        }
    }
    
    // Next Button
    const nextBtn = document.createElement('button');
    nextBtn.className = `btn btn-secondary btn-sm ${state.ranks.currentPage === totalPages ? 'disabled' : ''}`;
    nextBtn.innerHTML = '<i class="fa-solid fa-angle-right"></i>';
    nextBtn.addEventListener('click', () => {
        if (state.ranks.currentPage < totalPages) {
            state.ranks.currentPage++;
            filterAndRenderRanksTable();
        }
    });
    nav.appendChild(nextBtn);
}

// Show Ticker Rankings Multi-period Detail Cards
async function showRanksDetail(ticker) {
    const panel = document.getElementById('ranks-detail-panel');
    panel.classList.remove('hidden');
    
    document.getElementById('detail-ticker-name').textContent = ticker;
    document.getElementById('detail-company-info').textContent = 'Loading profile details...';
    
    const container = document.getElementById('detail-periods-container');
    container.innerHTML = '<div class="spinner-container"><div class="spinner"></div></div>';
    
    try {
        let url = `/data/ticker-ranks/detail?ticker=${ticker}`;
        if (state.ranks.rankFilter < 100) url += `&rank_filter=${state.ranks.rankFilter}`;
        
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to load ticker detail');
        const periods = await res.json();
        
        container.innerHTML = '';
        if (periods.length === 0) {
            container.innerHTML = '<p class="text-muted">No rankings records available for this ticker under current filters.</p>';
            return;
        }
        
        // Update profile labels
        const first = periods[0];
        document.getElementById('detail-company-info').textContent = `${first.sector || 'Unknown'} — ${first.industry || 'Unknown'}`;
        
        periods.forEach(p => {
            const card = document.createElement('div');
            card.className = 'period-detail-card';
            card.innerHTML = `
                <div class="period-detail-header">
                    <span>${p.Period}</span>
                    <span class="rank-highlight">Rank #${p.risk_reward_rank}</span>
                </div>
                <div class="period-detail-stats">
                    <div class="detail-stat-row">
                        <span>Return</span>
                        <span class="${p.over_pc >= 0 ? 'green-text' : 'red-text'}">${p.over_pc.toFixed(2)}%</span>
                    </div>
                    <div class="detail-stat-row">
                        <span>Mean Return</span>
                        <span>${p.pc_mean.toFixed(3)}%</span>
                    </div>
                    <div class="detail-stat-row">
                        <span>Volatility</span>
                        <span>${p.pc_std.toFixed(3)}%</span>
                    </div>
                    <div class="detail-stat-row">
                        <span>Prob Green</span>
                        <span class="rank-highlight">#${p.prob_green_day_rank} (${p['prob_green_day_%'].toFixed(1)}%)</span>
                    </div>
                    <div class="detail-stat-row">
                        <span>Stretch</span>
                        <span>#${p.stretch_score_rank} (${p.stretch_score.toFixed(2)})</span>
                    </div>
                    <div class="detail-stat-row">
                        <span>Kelly</span>
                        <span>#${p.kelly_fraction_rank} (${p.kelly_fraction.toFixed(2)})</span>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        container.innerHTML = `<p class="red-text">Error: ${err.message}</p>`;
    }
}

// Application Startup
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSortHeaders();
    initToolbarControls();
    
    // Initial fetch of current portfolio data
    loadValuationData();
});
