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

function runPaperTrading() {
    document.getElementById('paper-modal').classList.add('active');
    
    // Check if we have cached results
    fetch('/api/paper')
        .then(r => r.json())
        .then(data => {
            if (data.status === 'complete') {
                showPaperResults(data);
            } else {
                document.getElementById('paper-status-section').style.display = 'block';
                document.getElementById('paper-results').style.display = 'none';
            }
        });
}

function closePaperTrading() {
    document.getElementById('paper-modal').classList.remove('active');
}

async function executePaperRun() {
    const btn = document.getElementById('paper-run-btn');
    btn.disabled = true;
    btn.textContent = '回测中...';
    
    try {
        const res = await fetch('/api/paper/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                initial_capital: 100000,
                contract_size: 100,
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
    btn.textContent = '开始回测';
}

function showPaperResults(data) {
    document.getElementById('paper-status-section').style.display = 'none';
    document.getElementById('paper-results').style.display = 'block';
    
    const m = data.metrics || {};
    
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
    `;
    
    // Equity Chart
    renderPaperEquityChart(data.equity_curve || []);
    
    // Trade Log
    renderPaperTrades(data.trades || []);
}

function renderPaperEquityChart(equityData) {
    if (paperEquityChart) paperEquityChart.destroy();
    
    const labels = equityData.map(d => d.date?.substring(0, 16) || '');
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
                    ticks: { color: '#555544', maxTicksLimit: 12, maxRotation: 0 },
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
