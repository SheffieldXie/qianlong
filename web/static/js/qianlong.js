/* ============================================================
   乾六爻交易系统 — Dashboard JavaScript
   ============================================================ */

let charts = {};
let updateInterval = null;
let currentSignal = 'wait';

const PHASE_INFO = {
    'phase2_bull': {
        name: '② 趋势主导期 · 多头能量潮',
        iching: '飞龙在天 — 火上浇油, 借势而飞',
        advice: 'MACD慢线>+6.5, RSI节奏管理: >75持有, 回落70减半, 跌破50清加仓',
        badge: 'PHASE ②',
        color: '#D4A017',
        banner: 'phase2',
    },
    'phase2_bear': {
        name: '② 趋势主导期 · 空头能量潮',
        iching: '亢龙有悔 — 空头趋势, 顺势做空',
        advice: 'MACD慢线<-6.5, RSI<25持有, 上穿30减半, 上穿50清加仓',
        badge: 'PHASE ②',
        color: '#C41E3A',
        banner: 'phase2',
    },
    'phase3_chaos': {
        name: '③ 混沌震荡期 · 盲点套利',
        iching: '见龙在田 — 低吸高抛, 不恋战',
        advice: 'MACD∈[-6.5,+6.5], RSI≤30做多4份, RSI≥70做空4份, RSI至50减半',
        badge: 'PHASE ③',
        color: '#8888AA',
        banner: 'phase3',
    },
    'phase1': {
        name: '① 三维共振起势期',
        iching: '或跃在渊 — 底仓为道之本, 不求暴利但求正源',
        advice: '等待四维共振: 价格穿EMA144 + SAR翻号 + DEA穿0 + RSI突破',
        badge: 'PHASE ①',
        color: '#4A90D9',
        banner: 'phase1',
    },
    'default': {
        name: '潜龙勿用 · 观望',
        iching: '仓即是妄念, 观即是修行',
        advice: '市场无趋势时出手, 非勇乃愚',
        badge: 'WAIT',
        color: '#555544',
        banner: 'phase3',
    },
};

const SIGNAL_LABELS = {
    'wait': { text: '观望', desc: '潜龙勿用 — 等待信号确认', class: 'signal-wait' },
    'entry_long_4': { text: '买入 4份', desc: '①三维共振: 价格>EMA144 + SAR翻多 + DEA>0 + RSI>60 → 底仓4份', class: 'signal-entry' },
    'entry_short_4': { text: '卖空 4份', desc: '①三维共振: 价格<EMA144 + SAR翻空 + DEA<0 + RSI<40 → 底仓4份', class: 'signal-entry' },
    'add_long_4': { text: '加仓做多 4份', desc: '②MACD>+6.5: 火上浇油, 必须加仓', class: 'signal-entry' },
    'add_short_4': { text: '加仓做空 4份', desc: '②MACD<-6.5: 火上浇油, 必须加仓', class: 'signal-entry' },
    'arb_long_4': { text: '套利做多 4份', desc: '③混沌期: RSI≤30超卖, 盲点套利做多', class: 'signal-arb' },
    'arb_short_4': { text: '套利做空 4份', desc: '③混沌期: RSI≥70超买, 盲点套利做空', class: 'signal-arb' },
    'cut_half': { text: '减半仓', desc: '按PDF规则: 止损或RSI回落, 减半持仓', class: 'signal-exit' },
    'clear_addons': { text: '清除加仓', desc: '仅保留底仓, 清空金区加仓部分', class: 'signal-exit' },
    'clear_all': { text: '清仓!', desc: 'SAR翻转: 信号即道, 不与道争 — 无条件清仓', class: 'signal-exit' },
    'restore_long': { text: '回补多头', desc: 'RSI重新上破60, 加回被减仓位', class: 'signal-entry' },
    'restore_short': { text: '回补空头', desc: 'RSI重新下破40, 加回被减仓位', class: 'signal-entry' },
};

// ============================================================
// Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initIChingLines();
    initCitadelBar();
    loadStatus();
    
    // Auto-refresh every 10 seconds
    updateInterval = setInterval(loadStatus, 10000);
});

// ============================================================
// Load Status
// ============================================================

async function loadStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        if (data.cache_status === 'loading') {
            document.getElementById('status-text').textContent = '数据加载中...';
            return;
        }
        
        document.getElementById('status-text').textContent = '运行中';
        document.querySelector('.status-dot').className = 'status-dot ready';
        
        updatePhaseBanner(data.latest);
        updateSignalCard(data.latest);
        updatePosition(data.position);
        updateRisk(data.risk);
        loadChartData();
        
    } catch (e) {
        console.error('Status load failed:', e);
        document.getElementById('status-text').textContent = '连接断开';
        document.querySelector('.status-dot').className = 'status-dot error';
    }
}

// ============================================================
// Phase Banner
// ============================================================

function updatePhaseBanner(latest) {
    const phase = latest.phase || 'default';
    const info = PHASE_INFO[phase] || PHASE_INFO['default'];
    
    const banner = document.getElementById('phase-banner');
    banner.className = `phase-banner ${info.banner}`;
    
    document.getElementById('phase-name').textContent = info.name;
    document.getElementById('phase-name').style.color = info.color;
    document.getElementById('phase-iching').textContent = info.iching;
    document.getElementById('phase-advice').textContent = info.advice;
    document.getElementById('phase-badge').textContent = info.badge;
    document.getElementById('phase-badge').style.borderColor = info.color;
    document.getElementById('phase-badge').style.color = info.color;
    
    // Update I Ching active line
    updateIChingActive(phase);
    
    // Update MACD phase indicator
    const macdEl = document.getElementById('macd-phase');
    if (macdEl) {
        const dea = latest.dea || 0;
        if (dea > 6.5) macdEl.innerHTML = '<span style="color:#D4A017">多头能量潮 >+6.5</span>';
        else if (dea > 0) macdEl.innerHTML = '<span style="color:#4A90D9">偏多震荡 0~+6.5</span>';
        else if (dea > -6.5) macdEl.innerHTML = '<span style="color:#8888AA">偏空震荡 -6.5~0</span>';
        else macdEl.innerHTML = '<span style="color:#C41E3A">空头能量潮 <-6.5</span>';
    }
}

// ============================================================
// Signal Card
// ============================================================

function updateSignalCard(latest) {
    const sig = latest.signal_type || 'wait';
    const info = SIGNAL_LABELS[sig] || SIGNAL_LABELS['wait'];
    
    currentSignal = sig;
    
    const typeEl = document.getElementById('signal-type');
    typeEl.textContent = info.text;
    typeEl.className = `signal-type ${info.class}`;
    
    document.getElementById('signal-desc').textContent = info.desc;
    document.getElementById('signal-confidence').textContent =
        `置信度: ${(latest.signal_confidence * 100).toFixed(0)}%`;
    
    // Enable/disable execute button
    const btn = document.getElementById('execute-btn');
    btn.disabled = sig === 'wait';
    btn.style.opacity = sig === 'wait' ? 0.4 : 1;
}

// ============================================================
// Position (The Citadel)
// ============================================================

function updateCitadelBar(position) {
    const bar = document.getElementById('citadel-bar');
    bar.innerHTML = '';
    
    for (let i = 0; i < 12; i++) {
        const unit = position.unit_details?.[i] || { position: 'empty', type: 'empty' };
        const div = document.createElement('div');
        div.className = 'citadel-unit';
        
        if (unit.position === 'long') div.classList.add('long');
        else if (unit.position === 'short') div.classList.add('short');
        
        if (i < 4) div.classList.add('base');
        else div.classList.add('addon');
        
        // Show type label
        const typeLabel = unit.type === 'base' ? '①' : unit.type === 'addon' ? '②' : unit.type === 'arb' ? '③' : '';
        div.textContent = typeLabel || (i + 1);
        div.title = `Unit ${i + 1}: ${unit.position} ${unit.entry_price ? '@ ' + unit.entry_price.toFixed(2) : ''}`;
        
        bar.appendChild(div);
    }
}

function updatePosition(position) {
    if (!position) return;
    
    updateCitadelBar(position);
    
    document.getElementById('stat-units').textContent = `${position.total_units}/12`;
    
    const dirText = position.direction > 0 ? '多头' :
                    position.direction < 0 ? '空头' : '空仓';
    document.getElementById('stat-direction').textContent = dirText;
    
    const pnl = position.unrealized_pnl || 0;
    const pnlEl = document.getElementById('stat-pnl');
    pnlEl.textContent = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
    pnlEl.style.color = pnl >= 0 ? 'var(--green)' : 'var(--red)';
    
    // Show breakdown
    const breakdownEl = document.getElementById('stat-breakdown');
    if (breakdownEl) {
        breakdownEl.textContent = `底仓${position.base_units} 加仓${position.addon_units} 套利${position.arb_units}`;
    }
    
    // Unit details
    const details = document.getElementById('unit-details');
    if (position.unit_details) {
        const activeUnits = position.unit_details.filter(u => u.position !== 'empty');
        if (activeUnits.length > 0) {
            details.innerHTML = activeUnits.map(u => {
                const typeLabel = u.type === 'base' ? '①' : u.type === 'addon' ? '②' : u.type === 'arb' ? '③' : '';
                return `<div class="stat-row">
                    <span>Unit ${u.index + 1} ${u.position === 'long' ? '多' : '空'} ${typeLabel}</span>
                    <span style="color:${u.pnl >= 0 ? 'var(--green)' : 'var(--red)'}">
                        ${u.pnl >= 0 ? '+' : ''}$${u.pnl.toFixed(2)}
                    </span>
                </div>`;
            }).join('');
        }
    }
}

// ============================================================
// Risk (Kill Switch)
// ============================================================

function updateRisk(risk) {
    if (!risk) return;
    
    const pnlPct = risk.daily_pnl_pct || 0;
    const pnlEl = document.getElementById('risk-daily-pnl');
    pnlEl.textContent = `${(pnlPct * 100).toFixed(2)}%`;
    pnlEl.className = pnlPct >= -0.03 ? (pnlPct >= 0 ? 'safe' : 'warning') : 'danger';
    
    const lossEl = document.getElementById('risk-consecutive');
    lossEl.textContent = `${risk.consecutive_losses}/3`;
    lossEl.className = risk.consecutive_losses === 0 ? 'safe' :
                       risk.consecutive_losses < 2 ? 'warning' : 'danger';
    
    const coolEl = document.getElementById('risk-cooling');
    if (risk.is_cooling) {
        coolEl.textContent = `冷却至 ${risk.cooldown_until?.substring(0, 19) || '?'}`;
        coolEl.className = 'danger';
    } else {
        coolEl.textContent = '正常';
        coolEl.className = 'safe';
    }
}

// ============================================================
// I Ching Lines
// ============================================================

function initIChingLines() {
    fetch('/api/iching')
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('iching-lines');
            container.innerHTML = data.lines.map((line, i) => `
                <div class="iching-line" id="iching-line-${i}">
                    <span class="line-num">${line.name}</span>
                    <span class="line-chinese">${line.chinese}</span>
                    <span class="line-english">${line.english}</span>
                    <span class="line-state">${line.desc}</span>
                </div>
            `).join('');
        });
    
    // Also update the iching data to match PDF
    const ichingData = {
        'lines': [
            {'line': 1, 'name': '初九', 'chinese': '潜龙勿用', 'english': 'Hidden Dragon', 'state': '观望不妄动', 'desc': '市场未成势'},
            {'line': 2, 'name': '九二', 'chinese': '见龙在田', 'english': 'Dragon in Field', 'state': '③混沌套利', 'desc': '盲点套利,高抛低吸'},
            {'line': 3, 'name': '九三', 'chinese': '夕惕若厉', 'english': 'Diligent', 'state': '③→①过渡', 'desc': '守盈待命'},
            {'line': 4, 'name': '九四', 'chinese': '或跃在渊', 'english': 'Leaping', 'state': '①三维共振', 'desc': '建立底仓'},
            {'line': 5, 'name': '九五', 'chinese': '飞龙在天', 'english': 'Flying Dragon', 'state': '②趋势主导', 'desc': '火上浇油'},
            {'line': 6, 'name': '上九', 'chinese': '亢龙有悔', 'english': 'Arrogant Dragon', 'state': '趋势极端', 'desc': '防暴毙反噬'},
        ]
    };
    
    const container = document.getElementById('iching-lines');
    container.innerHTML = ichingData.lines.map((line, i) => `
        <div class="iching-line" id="iching-line-${i}">
            <span class="line-num">${line.name}</span>
            <span class="line-chinese">${line.chinese}</span>
            <span class="line-english">${line.english}</span>
            <span class="line-state">${line.state}</span>
        </div>
    `).join('');
}

function updateIChingActive(phase) {
    const lineMap = {
        'phase3_chaos': 1,  // 见龙在田 (Line 2)
        'phase1': 3,        // 或跃在渊 (Line 4)
        'phase2_bull': 4,   // 飞龙在天 (Line 5)
        'phase2_bear': 5,   // 亢龙有悔 (Line 6)
    };
    
    const activeIdx = lineMap[phase] ?? -1;
    
    for (let i = 0; i < 6; i++) {
        const el = document.getElementById(`iching-line-${i}`);
        if (el) {
            el.classList.toggle('active', i === activeIdx);
        }
    }
}

// ============================================================
// Citadel Bar
// ============================================================

function initCitadelBar() {
    const bar = document.getElementById('citadel-bar');
    bar.innerHTML = '';
    for (let i = 0; i < 12; i++) {
        const div = document.createElement('div');
        div.className = 'citadel-unit';
        div.textContent = i + 1;
        if (i < 4) div.classList.add('base');
        else div.classList.add('addon');
        bar.appendChild(div);
    }
}

// ============================================================
// Charts
// ============================================================

async function loadChartData() {
    try {
        const res = await fetch('/api/chart?limit=200');
        const data = await res.json();
        
        if (!data || data.length === 0) return;
        
        renderMainChart(data);
        renderMACDChart(data);
        renderRSIChart(data);
        
    } catch (e) {
        console.error('Chart data failed:', e);
    }
}

function renderMainChart(data) {
    const labels = data.map(d => d.date.substring(5, 16));
    const closes = data.map(d => d.close);
    const ema144 = data.map(d => d.ema144 || null);
    const sar = data.map(d => d.sar || null);
    
    if (charts['main']) charts['main'].destroy();
    
    charts['main'] = new Chart(document.getElementById('main-chart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'EMA144',
                    data: ema144,
                    type: 'line',
                    borderColor: '#F0C75E',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    order: 3,
                },
                {
                    label: 'SAR',
                    data: sar,
                    type: 'line',
                    borderColor: '#4A90D9',
                    borderWidth: 1,
                    pointRadius: 2,
                    pointBackgroundColor: '#4A90D9',
                    fill: false,
                    order: 3,
                },
                {
                    label: 'Price',
                    data: closes,
                    type: 'line',
                    borderColor: '#E8E6E1',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.1,
                    order: 1,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, labels: { color: '#999988', boxWidth: 12 } },
            },
            scales: {
                x: {
                    ticks: { color: '#555544', maxTicksLimit: 15, maxRotation: 0 },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
                y: {
                    ticks: { color: '#555544' },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                    beginAtZero: false,
                },
            },
        },
    });
}

function renderMACDChart(data) {
    const labels = data.map(d => d.date.substring(5, 16));
    const dea = data.map(d => d.dea || 0);
    const hist = data.map(d => d.macd_hist || 0);
    
    if (charts['macd']) charts['macd'].destroy();
    
    const histColors = hist.map(v => v >= 0 ? 'rgba(0, 200, 83, 0.6)' : 'rgba(196, 30, 58, 0.6)');
    
    charts['macd'] = new Chart(document.getElementById('macd-chart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'DEA (慢线)',
                    data: dea,
                    type: 'line',
                    borderColor: '#D4A017',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    order: 1,
                },
                {
                    label: 'MACD柱',
                    data: hist,
                    backgroundColor: histColors,
                    order: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, labels: { color: '#999988', boxWidth: 10 } },
            },
            scales: {
                x: {
                    ticks: { color: '#555544', maxTicksLimit: 10, maxRotation: 0 },
                    grid: { display: false },
                },
                y: {
                    ticks: { color: '#555544' },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
            },
        },
    });
}

function renderRSIChart(data) {
    const labels = data.map(d => d.date.substring(5, 16));
    const rsi = data.map(d => d.rsi || 50);
    
    if (charts['rsi']) charts['rsi'].destroy();
    
    charts['rsi'] = new Chart(document.getElementById('rsi-chart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'RSI(14)',
                data: rsi,
                borderColor: '#8B5CF6',
                borderWidth: 1.5,
                pointRadius: 0,
                fill: false,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                annotation: {
                    annotations: {
                        line70: {
                            type: 'line',
                            yMin: 70, yMax: 70,
                            borderColor: 'rgba(196, 30, 58, 0.5)',
                            borderWidth: 1,
                            borderDash: [4, 4],
                        },
                        line30: {
                            type: 'line',
                            yMin: 30, yMax: 30,
                            borderColor: 'rgba(0, 200, 83, 0.5)',
                            borderWidth: 1,
                            borderDash: [4, 4],
                        },
                        line50: {
                            type: 'line',
                            yMin: 50, yMax: 50,
                            borderColor: 'rgba(153, 153, 136, 0.3)',
                            borderWidth: 1,
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: '#555544', maxTicksLimit: 10, maxRotation: 0 },
                    grid: { display: false },
                },
                y: {
                    min: 0, max: 100,
                    ticks: { color: '#555544', stepSize: 25 },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
            },
        },
    });
}

// ============================================================
// Actions
// ============================================================

async function reloadData(period) {
    document.getElementById('status-text').textContent = '重新加载中...';
    document.querySelector('.status-dot').className = 'status-dot loading';
    
    try {
        await fetch('/api/reload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ period: period || '30d' }),
        });
        
        // Wait a moment then reload status
        setTimeout(loadStatus, 2000);
    } catch (e) {
        console.error('Reload failed:', e);
    }
}

async function executeSignal() {
    if (currentSignal === 'wait') return;
    
    try {
        const res = await fetch('/api/trade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ signal_type: currentSignal }),
        });
        const data = await res.json();
        
        if (data.status === 'blocked') {
            alert(`Kill Switch激活: ${data.reason}`);
        } else {
            alert(`执行: ${data.action}`);
        }
        
        loadStatus();
    } catch (e) {
        console.error('Trade execution failed:', e);
    }
}

async function activateKillSwitch() {
    if (!confirm('确定要手动激活Kill Switch (停盘24小时) 吗?')) return;
    try {
        await fetch('/api/killswitch', { method: 'POST' });
        loadStatus();
    } catch (e) { console.error('Kill switch failed:', e); }
}

// ============================================================
// Indicator Configuration
// ============================================================

let currentConfig = {};

function openIndicatorConfig() {
    fetch('/api/config')
        .then(r => r.json())
        .then(cfg => {
            currentConfig = cfg;
            document.getElementById('cfg-ema-period').value = cfg.ema_period || 144;
            document.getElementById('cfg-macd-fast').value = cfg.macd_fast || 20;
            document.getElementById('cfg-macd-slow').value = cfg.macd_slow || 52;
            document.getElementById('cfg-macd-signal').value = cfg.macd_signal || 2;
            document.getElementById('cfg-macd-threshold').value = cfg.macd_threshold || 6.5;
            document.getElementById('cfg-rsi-period').value = cfg.rsi_period || 14;
            document.getElementById('cfg-sar-step').value = cfg.sar_step || 0.02;
            document.getElementById('cfg-sar-max').value = cfg.sar_max || 0.2;
            document.getElementById('config-modal').classList.add('active');
        });
}

function closeIndicatorConfig() {
    document.getElementById('config-modal').classList.remove('active');
}

async function applyConfig() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '计算中...';
    
    const config = {
        ema_period: parseInt(document.getElementById('cfg-ema-period').value),
        macd_fast: parseInt(document.getElementById('cfg-macd-fast').value),
        macd_slow: parseInt(document.getElementById('cfg-macd-slow').value),
        macd_signal: parseInt(document.getElementById('cfg-macd-signal').value),
        macd_threshold: parseFloat(document.getElementById('cfg-macd-threshold').value),
        rsi_period: parseInt(document.getElementById('cfg-rsi-period').value),
        sar_step: parseFloat(document.getElementById('cfg-sar-step').value),
        sar_max: parseFloat(document.getElementById('cfg-sar-max').value),
    };
    
    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        await res.json();
        closeIndicatorConfig();
        // Poll for update
        setTimeout(() => loadStatus(), 3000);
    } catch (e) {
        console.error('Apply config failed:', e);
    }
    
    btn.disabled = false;
    btn.textContent = '✓ 应用并重新计算';
}

async function resetConfig() {
    try {
        const res = await fetch('/api/config/defaults', { method: 'POST' });
        const cfg = await res.json();
        document.getElementById('cfg-ema-period').value = cfg.ema_period;
        document.getElementById('cfg-macd-fast').value = cfg.macd_fast;
        document.getElementById('cfg-macd-slow').value = cfg.macd_slow;
        document.getElementById('cfg-macd-signal').value = cfg.macd_signal;
        document.getElementById('cfg-macd-threshold').value = cfg.macd_threshold;
        document.getElementById('cfg-rsi-period').value = cfg.rsi_period;
        document.getElementById('cfg-sar-step').value = cfg.sar_step;
        document.getElementById('cfg-sar-max').value = cfg.sar_max;
    } catch (e) {
        console.error('Reset config failed:', e);
    }
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.id === 'config-modal') closeIndicatorConfig();
    if (e.target.id === 'paper-modal') closePaperTrading();
});

// ============================================================
// Paper Trading
// ============================================================

let paperEquityChart = null;
let paperReturnsChart = null;
let paperDrawdownChart = null;

function runPaperTrading() {
    document.getElementById('paper-modal').classList.add('active');
    
    // Set default dates for custom selection
    const today = new Date();
    const endDate = today.toISOString().split('T')[0];
    const startDate = new Date(today - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    document.getElementById('bt-end-date').value = endDate;
    document.getElementById('bt-start-date').value = startDate;
    
    showPaperConfig();
}

function showPaperConfig() {
    document.getElementById('paper-config-section').style.display = 'block';
    document.getElementById('paper-results').style.display = 'none';
}

function closePaperTrading() {
    document.getElementById('paper-modal').classList.remove('active');
}

// Toggle custom date inputs
document.addEventListener('DOMContentLoaded', () => {
    const periodSelect = document.getElementById('bt-period-select');
    if (periodSelect) {
        periodSelect.addEventListener('change', () => {
            const customDiv = document.getElementById('bt-custom-dates');
            customDiv.style.display = periodSelect.value === 'custom' ? 'block' : 'none';
        });
    }
});

async function executePaperRun() {
    const btn = document.getElementById('paper-run-btn');
    btn.disabled = true;
    btn.textContent = '回测中...';
    
    // Gather parameters
    const period = document.getElementById('bt-period-select').value;
    const initialCapital = parseFloat(document.getElementById('bt-capital').value) || 100000;
    const contractSize = parseFloat(document.getElementById('bt-contract').value) || 100;
    
    let startDate = null;
    let endDate = null;
    if (period === 'custom') {
        startDate = document.getElementById('bt-start-date').value;
        endDate = document.getElementById('bt-end-date').value;
        if (!startDate || !endDate) {
            alert('请选择开始和结束日期');
            btn.disabled = false;
            btn.textContent = '▶ 开始回测';
            return;
        }
    }
    
    try {
        const res = await fetch('/api/paper/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                initial_capital: initialCapital,
                contract_size: contractSize,
                period: period !== 'custom' ? period : '60d',
                start_date: startDate,
                end_date: endDate,
            }),
        });
        
        const data = await res.json();
        
        if (data.error) {
            alert(data.error);
        } else {
            showPaperResults({ status: 'complete', ...data });
        }
    } catch (e) {
        console.error('Paper run failed:', e);
        alert('模拟盘运行失败: ' + e.message);
    }
    
    btn.disabled = false;
    btn.textContent = '▶ 开始回测';
}

function showPaperResults(data) {
    document.getElementById('paper-config-section').style.display = 'none';
    document.getElementById('paper-results').style.display = 'block';
    
    const m = data.metrics || {};
    const cfg = data.config || {};
    
    // Config Summary
    const summaryEl = document.getElementById('paper-config-summary');
    if (summaryEl && cfg.date_range) {
        const intervalLabel = cfg.interval === '1h' ? '1小时' : cfg.interval === '1d' ? '日线' : '15分钟';
        summaryEl.innerHTML = `
            <div class="config-summary-bar">
                <span class="summary-item"><strong>资金:</strong> $${cfg.initial_capital?.toLocaleString() || '100,000'}</span>
                <span class="summary-item"><strong>合约:</strong> ${cfg.contract_size || 100} oz</span>
                <span class="summary-item"><strong>区间:</strong> ${cfg.date_range}</span>
                <span class="summary-item"><strong>粒度:</strong> ${intervalLabel}</span>
                <span class="summary-item"><strong>数据点:</strong> ${cfg.data_points || '—'}</span>
            </div>
        `;
    }
    
    // Metrics
    document.getElementById('paper-metrics').innerHTML = `
        <div class="paper-metric">
            <div class="metric-label">初始资金</div>
            <div class="metric-value">$${m.initial_capital?.toLocaleString() || '100,000'}</div>
            <div class="metric-sub">USD</div>
        </div>
        <div class="paper-metric">
            <div class="metric-label">最终权益</div>
            <div class="metric-value" style="color:${m.final_equity >= m.initial_capital ? 'var(--green)' : 'var(--red)'}">
                $${m.final_equity?.toLocaleString() || '—'}
            </div>
            <div class="metric-sub">收益率: ${((m.total_return || 0) * 100).toFixed(2)}%</div>
        </div>
        <div class="paper-metric">
            <div class="metric-label">夏普比率</div>
            <div class="metric-value" style="color:${m.sharpe_ratio >= 0 ? 'var(--green)' : 'var(--red)'}">
                ${m.sharpe_ratio?.toFixed(2) || '—'}
            </div>
            <div class="metric-sub">年化波动: ${((m.annual_volatility || 0) * 100).toFixed(1)}%</div>
        </div>
        <div class="paper-metric">
            <div class="metric-label">最大回撤</div>
            <div class="metric-value" style="color:var(--red)">${((m.max_drawdown || 0) * 100).toFixed(2)}%</div>
            <div class="metric-sub">胜率: ${((m.win_rate || 0) * 100).toFixed(1)}%</div>
        </div>
        <div class="paper-metric">
            <div class="metric-label">总交易次数</div>
            <div class="metric-value">${m.total_trades || 0}</div>
            <div class="metric-sub">盈亏比: ${m.profit_factor?.toFixed(2) || '—'}</div>
        </div>
    `;
    
    // Equity Chart
    renderPaperEquityChart(data.equity_curve || []);
    
    // Returns Distribution Chart
    renderPaperReturnsChart(data.daily_returns || [], data.equity_curve || []);
    
    // Drawdown Chart
    renderPaperDrawdownChart(data.equity_curve || []);
    
    // Trade Log
    renderPaperTrades(data.trades || []);
}

function renderPaperEquityChart(equityData) {
    if (paperEquityChart) paperEquityChart.destroy();
    
    if (!equityData || equityData.length === 0) {
        return;
    }
    
    // Dynamic tick count based on data points
    const n = equityData.length;
    const maxTicks = n <= 100 ? 12 : n <= 500 ? 10 : 8;
    const labelFormat = n <= 500 ? 'date' : 'date-month';
    
    const labels = equityData.map(d => {
        if (!d.date) return '';
        if (labelFormat === 'date') return d.date.substring(5, 16); // MM-DD HH:MM
        return d.date.substring(0, 10); // YYYY-MM-DD
    });
    const equities = equityData.map(d => d.equity || 0);
    
    const ctx = document.getElementById('paper-equity-chart').getContext('2d');
    
    paperEquityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Equity',
                data: equities,
                borderColor: '#D4A017',
                backgroundColor: 'rgba(212, 160, 23, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                tension: 0.1,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                x: {
                    ticks: { color: '#555544', maxTicksLimit: maxTicks, maxRotation: n > 300 ? 30 : 0, autoSkip: true, autoSkipPadding: 10 },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
                y: {
                    ticks: {
                        color: '#555544',
                        callback: v => '$' + v.toLocaleString(),
                    },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
            },
        },
    });
}

function renderPaperTrades(trades) {
    const container = document.getElementById('paper-trades');
    
    if (!trades || trades.length === 0) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">无交易记录</div>';
        return;
    }
    
    // Show last 50 trades
    const recent = trades.slice(-50).reverse();
    
    let html = `
        <div class="paper-trade-row header">
            <span>日期</span>
            <span>方向</span>
            <span>价格</span>
            <span>盈亏</span>
            <span>备注</span>
        </div>
    `;
    
    for (const t of recent) {
        const actionClass = t.action?.includes('OPEN') ? 'action-open' : 'action-close';
        const pnlClass = (t.pnl || 0) >= 0 ? 'pnl-positive' : 'pnl-negative';
        const pnlText = t.pnl !== undefined ? `$${t.pnl.toFixed(2)}` : '—';
        const dirText = t.direction === 1 ? '多' : t.direction === -1 ? '空' : '—';
        const noteText = t.reason || t.type || '';
        
        html += `
            <div class="paper-trade-row">
                <span>${t.date?.substring(0, 16) || ''}</span>
                <span class="${actionClass}">${t.action || ''}</span>
                <span>$${t.price?.toFixed(2) || ''}</span>
                <span class="${pnlClass}">${pnlText}</span>
                <span style="color:var(--text-muted)">${noteText}</span>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function renderPaperReturnsChart(dailyReturns, equityData) {
    if (paperReturnsChart) paperReturnsChart.destroy();
    
    if (!dailyReturns || dailyReturns.length === 0) {
        return;
    }
    
    // Create histogram bins
    const min = Math.min(...dailyReturns);
    const max = Math.max(...dailyReturns);
    const binCount = 20;
    const binWidth = (max - min) / binCount || 0.001;
    const bins = new Array(binCount).fill(0);
    const labels = [];
    
    for (let i = 0; i < binCount; i++) {
        const lo = min + i * binWidth;
        labels.push((lo * 100).toFixed(2) + '%');
    }
    
    dailyReturns.forEach(r => {
        let idx = Math.floor((r - min) / binWidth);
        if (idx >= binCount) idx = binCount - 1;
        if (idx < 0) idx = 0;
        bins[idx]++;
    });
    
    const bgColors = labels.map(l => {
        const val = parseFloat(l);
        return val >= 0 ? 'rgba(0, 200, 83, 0.6)' : 'rgba(196, 30, 58, 0.6)';
    });
    
    const ctx = document.getElementById('paper-returns-chart').getContext('2d');
    paperReturnsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Frequency',
                data: bins,
                backgroundColor: bgColors,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                x: {
                    ticks: { color: '#555544', maxTicksLimit: 8, maxRotation: 45, font: { size: 9 } },
                    grid: { display: false },
                    title: { display: true, text: '日收益率', color: '#888' },
                },
                y: {
                    ticks: { color: '#555544' },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
            },
        },
    });
}

function renderPaperDrawdownChart(equityData) {
    if (paperDrawdownChart) paperDrawdownChart.destroy();
    
    if (!equityData || equityData.length === 0) {
        return;
    }
    
    const n = equityData.length;
    const maxTicks = n <= 100 ? 12 : n <= 500 ? 10 : 8;
    
    const labels = equityData.map(d => {
        if (!d.date) return '';
        return n > 500 ? d.date.substring(0, 10) : d.date.substring(5, 16);
    });
    const drawdowns = [];
    let peak = 0;
    
    equityData.forEach(d => {
        const eq = d.equity || 0;
        if (eq > peak) peak = eq;
        const dd = peak > 0 ? (eq - peak) / peak * 100 : 0;
        drawdowns.push(dd);
    });
    
    const ctx = document.getElementById('paper-drawdown-chart').getContext('2d');
    paperDrawdownChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Drawdown %',
                data: drawdowns,
                borderColor: '#C41E3A',
                backgroundColor: 'rgba(196, 30, 58, 0.2)',
                borderWidth: 1.5,
                pointRadius: 0,
                fill: true,
                tension: 0.1,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                x: {
                    ticks: { color: '#555544', maxTicksLimit: maxTicks, maxRotation: n > 300 ? 30 : 0, autoSkip: true, autoSkipPadding: 10, font: { size: 9 } },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
                y: {
                    ticks: { color: '#555544', callback: v => v.toFixed(1) + '%' },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
            },
        },
    });
}

// ============================================================
// Long-Term Backtest Module
// ============================================================

let longtermEquityChart = null;

async function loadLongtermBacktest() {
    const loadingEl = document.getElementById('longterm-loading');
    const resultsEl = document.getElementById('longterm-results');

    loadingEl.style.display = 'block';
    resultsEl.style.display = 'none';

    try {
        const res = await fetch('/api/longterm');
        const data = await res.json();

        if (data.status === 'not_run') {
            loadingEl.innerHTML = '<p>' + data.message + '</p>';
            return;
        }

        renderLongtermAssessment(data.assessment);
        renderLongtermYears(data.results, data.events);
        renderLongtermEvents(data.events, data.results);
        renderLongtermEquityChart(data.results);

        loadingEl.style.display = 'none';
        resultsEl.style.display = 'block';

    } catch (e) {
        console.error('Longterm backtest load failed:', e);
        loadingEl.innerHTML = '<p style="color:var(--red)">加载失败, 请检查服务器日志</p>';
    }
}

function renderLongtermAssessment(assessment) {
    const el = document.getElementById('longterm-assessment');
    const g = assessment.robustness_grade;
    const avgReturnColor = assessment.avg_annual_return >= 0 ? 'var(--green)' : 'var(--red)';

    el.innerHTML = '<div class="assessment-grid">' +
        '<div class="assessment-grade">' +
        '<span class="grade-badge" style="color:' + g.color + '">' + g.grade + '</span>' +
        '<div class="grade-label">鲁棒性: ' + g.label + '</div>' +
        '</div>' +
        '<div class="assessment-stat"><div class="stat-value">' + assessment.positive_years + '/' + assessment.total_years + '</div><div class="stat-label">正收益年份</div></div>' +
        '<div class="assessment-stat"><div class="stat-value" style="color:' + avgReturnColor + '">' + (assessment.avg_annual_return * 100).toFixed(1) + '%</div><div class="stat-label">平均年化收益</div></div>' +
        '<div class="assessment-stat"><div class="stat-value">' + assessment.avg_sharpe.toFixed(2) + '</div><div class="stat-label">平均夏普比率</div></div>' +
        '<div class="assessment-stat"><div class="stat-value" style="color:var(--red)">' + (assessment.avg_max_drawdown * 100).toFixed(1) + '%</div><div class="stat-label">平均最大回撤</div></div>' +
        '<div class="assessment-stat"><div class="stat-value">' + (assessment.avg_win_rate * 100).toFixed(1) + '%</div><div class="stat-label">平均胜率</div></div>' +
        '<div class="assessment-stat"><div class="stat-value">' + assessment.total_trades_all_years + '</div><div class="stat-label">总交易次数</div></div>' +
        '<div class="assessment-stat"><div class="stat-value">' + assessment.consistency_score + '/100</div><div class="stat-label">一致性评分</div></div>' +
        '</div>';
}

function renderLongtermYears(results, allEvents) {
    const el = document.getElementById('longterm-years');
    let html = '';

    for (const [yearStr, data] of Object.entries(results).sort()) {
        const m = data.metrics;
        const returnClass = m.total_return >= 0 ? 'positive' : 'negative';
        const returnSign = m.total_return >= 0 ? '+' : '';
        const finalEq = (m.final_equity || 0).toLocaleString(undefined, {maximumFractionDigits: 0});

        let eventTags = '';
        for (const ev of data.events) {
            const typeClass = ev.type || 'fed';
            eventTags += '<span class="event-tag ' + typeClass + '"><span class="event-dot"></span>' + ev.name + '</span>';
        }

        const r = data.robustness || {};

        html += '<div class="year-card">' +
            '<div class="year-card-header">' +
            '<span class="year">' + yearStr + '</span>' +
            '<span class="year-return ' + returnClass + '">' + returnSign + (m.total_return * 100).toFixed(1) + '%</span>' +
            '</div>' +
            '<div class="year-card-body">' +
            '<div class="year-metrics">' +
            '<div class="year-metric"><div class="ym-value">$' + finalEq + '</div><div class="ym-label">最终权益</div></div>' +
            '<div class="year-metric"><div class="ym-value">' + (m.sharpe_ratio ? m.sharpe_ratio.toFixed(2) : '—') + '</div><div class="ym-label">夏普比率</div></div>' +
            '<div class="year-metric"><div class="ym-value" style="color:var(--red)">' + (m.max_drawdown * 100).toFixed(1) + '%</div><div class="ym-label">最大回撤</div></div>' +
            '<div class="year-metric"><div class="ym-value">' + (m.win_rate * 100).toFixed(1) + '%</div><div class="ym-label">胜率</div></div>' +
            '<div class="year-metric"><div class="ym-value">' + m.total_trades + '</div><div class="ym-label">交易次数</div></div>' +
            '<div class="year-metric"><div class="ym-value">' + (m.profit_factor ? m.profit_factor.toFixed(2) : '—') + '</div><div class="ym-label">盈亏比</div></div>' +
            '</div>' +
            '<div class="year-events">' +
            '<div class="year-events-title">&#9889; 重大事件 (' + data.events.length + ')</div>' +
            eventTags +
            '</div>' +
            '<div class="robustness-section">' +
            '<div class="robustness-title">系统鲁棒性</div>' +
            '<div class="robustness-grid">' +
            '<div class="robustness-item">最大回撤持续: <strong>' + (r.max_drawdown_duration_days || 0) + ' 天</strong></div>' +
            '<div class="robustness-item">年交易频率: <strong>' + (r.trade_frequency_per_year || 0) + '/年</strong></div>' +
            '<div class="robustness-item">最大连胜: <strong>' + (r.max_consecutive_wins || 0) + '</strong></div>' +
            '<div class="robustness-item">最大连亏: <strong>' + (r.max_consecutive_losses || 0) + '</strong></div>' +
            '</div></div></div></div>';
    }

    el.innerHTML = html;
}

function renderLongtermEvents(events, results) {
    const el = document.getElementById('longterm-events');
    let html = '';

    for (const ev of events) {
        const typeClass = ev.type || 'fed';
        const typeLabel = ev.type === 'fed' ? '美联储' : ev.type === 'geopolitical' ? '地缘冲突' : ev.type === 'political' ? '政治事件' : '央行';

        let impactHtml = '';
        for (const [yearStr, data] of Object.entries(results)) {
            const impacts = data.event_impacts || [];
            const match = impacts.find(i => i.date === ev.date);
            if (match) {
                const impClass = match.change_pct > 0 ? 'positive' : match.change_pct < 0 ? 'negative' : 'neutral';
                const sign = match.change_pct > 0 ? '+' : '';
                impactHtml = '<div class="event-card-impact ' + impClass + '">价格影响: ' + sign + match.change_pct + '% (' + match.price_before + ' → ' + match.price_after + ')</div>';
                break;
            }
        }

        html += '<div class="event-card">' +
            '<div class="event-card-header">' +
            '<span class="event-tag ' + typeClass + '" style="font-size:10px;padding:2px 8px;"><span class="event-dot"></span>' + typeLabel + '</span>' +
            '<span class="event-card-date">' + ev.date + '</span>' +
            '</div>' +
            '<div class="event-card-name">' + ev.name + '</div>' +
            '<div class="event-card-desc">' + ev.desc + '</div>' +
            impactHtml +
            '</div>';
    }

    el.innerHTML = html;
}

function renderLongtermEquityChart(results) {
    if (longtermEquityChart) longtermEquityChart.destroy();

    const ctx = document.getElementById('longterm-equity-chart').getContext('2d');
    const colors = { '2024': '#D4A017', '2025': '#00C853', '2026': '#C41E3A' };

    const datasets = [];
    for (const [yearStr, data] of Object.entries(results).sort()) {
        const eqPoints = data.equity_points || [];
        if (eqPoints.length === 0) continue;

        datasets.push({
            label: yearStr + '年',
            data: eqPoints.map(p => p.equity),
            borderColor: colors[yearStr] || '#888',
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.1,
        });
    }

    longtermEquityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: datasets.length > 0 ? datasets[0].data.map((_, i) => i) : [],
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, labels: { color: '#999988', boxWidth: 12, font: { size: 12 } } },
            },
            scales: {
                x: {
                    title: { display: true, text: '交易日', color: '#888' },
                    ticks: { color: '#555544', maxTicksLimit: 20 },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
                y: {
                    title: { display: true, text: '权益 ($)', color: '#888' },
                    ticks: { color: '#555544', callback: v => '$' + v.toLocaleString() },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
            },
        },
    });
}

// Auto-load longterm data on page load — use pre-cached data if available
document.addEventListener('DOMContentLoaded', () => {
    const cacheEl = document.getElementById('longterm-cache');
    if (cacheEl) {
        try {
            const data = JSON.parse(cacheEl.textContent);
            // Show cached results immediately
            renderLongtermAssessment(data.assessment);
            renderLongtermYears(data.results, data.events);
            renderLongtermEvents(data.events, data.results);
            renderLongtermEquityChart(data.results);

            document.getElementById('longterm-loading').style.display = 'none';
            document.getElementById('longterm-results').style.display = 'block';
        } catch (e) {
            console.error('Cache parse error:', e);
            loadLongtermBacktest(); // fallback to API
        }
    }
});

// ============================================================
// Long-Term Backtest
// ============================================================

let ltEquityChart = null;

async function loadLongtermBacktest() {
    try {
        const res = await fetch('/api/long_backtest');
        const data = await res.json();
        
        if (data.error) {
            document.getElementById('yearly-tbody').innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--red);">${data.error}</td></tr>`;
            return;
        }
        
        renderYearlyTable(data.yearly || {});
        renderEquityCurve(data.full_period || {});
        renderEventsTable(data.events_impact || []);
        renderRobustness(data.robustness || {});
        
    } catch (e) {
        console.error('Long-term backtest load failed:', e);
        document.getElementById('yearly-tbody').innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--red);">加载失败</td></tr>';
    }
}

function renderYearlyTable(yearly) {
    const tbody = document.getElementById('yearly-tbody');
    const years = Object.keys(yearly).sort();
    
    if (years.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#555544;">无数据</td></tr>';
        return;
    }
    
    tbody.innerHTML = years.map(yr => {
        const y = yearly[yr];
        if (y.error) return `<tr><td>${yr}</td><td colspan="9" style="color:var(--red);">${y.error}</td></tr>`;
        
        const m = y.metrics || {};
        const totalRet = (m.total_return || 0) * 100;
        const annRet = (m.annual_return || 0) * 100;
        const sharpe = m.sharpe_ratio || 0;
        const maxDD = (m.max_drawdown || 0) * 100;
        const winRate = (m.win_rate || 0) * 100;
        const pf = m.profit_factor || 0;
        const trades = m.total_trades || 0;
        const priceChange = y.price_change_pct || 0;
        
        const retClass = totalRet >= 0 ? 'positive' : 'negative';
        const ddClass = maxDD > -20 ? 'safe' : maxDD > -35 ? 'warning' : 'danger';
        
        return `<tr>
            <td style="font-weight:700;color:var(--gold);">${yr}</td>
            <td>$${y.price_start?.toLocaleString() || '—'} → $${y.price_end?.toLocaleString() || '—'}</td>
            <td class="${priceChange >= 0 ? 'positive' : 'negative'}">${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(1)}%</td>
            <td class="${retClass}" style="font-weight:700;">${totalRet >= 0 ? '+' : ''}${totalRet.toFixed(1)}%</td>
            <td>${annRet >= 0 ? '+' : ''}${annRet.toFixed(1)}%</td>
            <td style="color:${sharpe > 1 ? 'var(--green)' : sharpe > 0 ? 'var(--gold)' : 'var(--red)'}">${sharpe.toFixed(2)}</td>
            <td class="${ddClass}">${maxDD.toFixed(1)}%</td>
            <td>${winRate.toFixed(1)}%</td>
            <td>${pf.toFixed(2)}</td>
            <td>${trades}</td>
        </tr>`;
    }).join('');
}

function renderEquityCurve(fullPeriod) {
    const eq = fullPeriod.equity_curve || [];
    if (eq.length === 0) return;
    
    const dateRange = document.getElementById('lt-date-range');
    if (dateRange) dateRange.textContent = fullPeriod.date_range || '';
    
    const labels = eq.map(e => {
        const d = new Date(e.date);
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    });
    const equities = eq.map(e => e.equity);
    
    // Sample data for performance (every Nth point)
    const maxPoints = 300;
    const step = Math.max(1, Math.floor(eq.length / maxPoints));
    const sampleLabels = labels.filter((_, i) => i % step === 0);
    const sampleEquities = equities.filter((_, i) => i % step === 0);
    
    if (ltEquityChart) ltEquityChart.destroy();
    
    ltEquityChart = new Chart(document.getElementById('lt-equity-chart'), {
        type: 'line',
        data: {
            labels: sampleLabels,
            datasets: [{
                label: '账户权益',
                data: sampleEquities,
                borderColor: '#D4A017',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                backgroundColor: 'rgba(212, 160, 23, 0.1)',
                tension: 0.1,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => `$${ctx.parsed.y.toLocaleString()}`,
                    },
                },
                annotation: {
                    annotations: {
                        baseLine: {
                            type: 'line',
                            yMin: 100000, yMax: 100000,
                            borderColor: 'rgba(153, 153, 136, 0.3)',
                            borderWidth: 1,
                            borderDash: [6, 4],
                            label: { display: true, content: '初始资金 $100K', position: 'start', color: '#555544', font: { size: 10 } },
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: '#555544', maxTicksLimit: 12, maxRotation: 0 },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
                y: {
                    ticks: { color: '#555544', callback: v => '$' + (v/1000) + 'K' },
                    grid: { color: 'rgba(42, 42, 42, 0.5)' },
                },
            },
        },
    });
}

function renderEventsTable(events) {
    const tbody = document.getElementById('events-tbody');
    if (!events || events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#555544;">无事件数据</td></tr>';
        return;
    }
    
    const categoryLabels = {
        fed: '美联储', geopolitical: '地缘政治', political: '政治',
        trade: '贸易', banking: '银行业', central_bank: '央行',
    };
    
    tbody.innerHTML = events.map(evt => {
        const move1d = evt.move_1d_pct || 0;
        const move5d = evt.move_5d_pct || 0;
        const maxMove = evt.max_move_pct || 0;
        
        return `<tr>
            <td style="font-family:var(--font-mono);font-size:12px;">${evt.date}</td>
            <td style="font-weight:600;">${evt.label}</td>
            <td><span class="event-tag ${evt.category}"><span class="event-dot"></span>${categoryLabels[evt.category] || evt.category}</span></td>
            <td class="${move1d >= 0 ? 'positive' : 'negative'}">${move1d >= 0 ? '+' : ''}${move1d.toFixed(2)}%</td>
            <td class="${move5d >= 0 ? 'positive' : 'negative'}">${move5d >= 0 ? '+' : ''}${move5d.toFixed(2)}%</td>
            <td class="${maxMove >= 0 ? 'positive' : 'negative'}">${maxMove >= 0 ? '+' : ''}${maxMove.toFixed(2)}%</td>
            <td style="font-size:11px;color:var(--text-secondary);max-width:200px;">${evt.impact_desc || ''}</td>
        </tr>`;
    }).join('');
}

function renderRobustness(r) {
    const grid = document.getElementById('robustness-grid');
    if (!r || Object.keys(r).length === 0) {
        grid.innerHTML = '<div style="text-align:center;color:#555544;">无数据</div>';
        return;
    }
    
    const sharpeColor = r.sharpe_ratio > 1 ? 'var(--green)' : r.sharpe_ratio > 0 ? 'var(--gold)' : 'var(--red)';
    const returnColor = r.total_return_pct >= 0 ? 'var(--green)' : 'var(--red)';
    const ddClass = r.max_drawdown_pct > -20 ? 'safe' : r.max_drawdown_pct > -35 ? 'warning' : 'danger';
    
    grid.innerHTML = `
        <div class="assessment-grid">
            <div class="assessment-stat">
                <div class="stat-value" style="color:${returnColor};">${r.total_return_pct >= 0 ? '+' : ''}${r.total_return_pct.toFixed(1)}%</div>
                <div class="stat-label">总收益率</div>
            </div>
            <div class="assessment-stat">
                <div class="stat-value" style="color:${returnColor};">${r.annual_return_pct >= 0 ? '+' : ''}${r.annual_return_pct.toFixed(1)}%</div>
                <div class="stat-label">年化收益</div>
            </div>
            <div class="assessment-stat">
                <div class="stat-value" style="color:${sharpeColor};">${r.sharpe_ratio?.toFixed(2) || '—'}</div>
                <div class="stat-label">夏普比率</div>
            </div>
            <div class="assessment-stat">
                <div class="stat-value ${ddClass}">${r.max_drawdown_pct?.toFixed(1) || '—'}%</div>
                <div class="stat-label">最大回撤</div>
            </div>
            <div class="assessment-stat">
                <div class="stat-value">${r.win_rate_pct?.toFixed(1) || '—'}%</div>
                <div class="stat-label">胜率</div>
            </div>
            <div class="assessment-stat">
                <div class="stat-value">${r.profit_factor?.toFixed(2) || '—'}</div>
                <div class="stat-label">盈亏比</div>
            </div>
            <div class="assessment-stat">
                <div class="stat-value">${r.total_trades || '—'}</div>
                <div class="stat-label">总交易次数</div>
            </div>
            <div class="assessment-stat">
                <div class="stat-value">${r.max_consecutive_losses || '—'}</div>
                <div class="stat-label">最大连续亏损</div>
            </div>
        </div>
        <div style="margin-top:16px;padding:12px 16px;background:var(--bg-secondary);border-radius:8px;">
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">波动率分层表现</div>
            <div style="display:flex;gap:20px;flex-wrap:wrap;">
                <div style="font-size:13px;">
                    <span style="color:var(--text-secondary);">高波动期日均收益：</span>
                    <span style="color:${r.high_volatility_avg_return >= 0 ? 'var(--green)' : 'var(--red)'};font-weight:700;">
                        ${r.high_volatility_avg_return >= 0 ? '+' : ''}${(r.high_volatility_avg_return || 0).toFixed(4)}%
                    </span>
                </div>
                <div style="font-size:13px;">
                    <span style="color:var(--text-secondary);">低波动期日均收益：</span>
                    <span style="color:${r.low_volatility_avg_return >= 0 ? 'var(--green)' : 'var(--red)'};font-weight:700;">
                        ${r.low_volatility_avg_return >= 0 ? '+' : ''}${(r.low_volatility_avg_return || 0).toFixed(4)}%
                    </span>
                </div>
            </div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:8px;">
                ${r.note || '日线级别回测，信号频率低于15m，但能捕捉中长期趋势'}
            </div>
        </div>
    `;
}
