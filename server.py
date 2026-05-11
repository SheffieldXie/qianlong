"""
乾六爻交易系统 — Flask Dashboard Server

端口: 5040 (按用户设定)
"""

import os
import sys
import json
import datetime
import threading

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request

from engine.core import analyze, get_latest_state
from data.fetcher import fetch_xauusd, fetch_xauusd_15m, generate_mock_data
from strategy.position import PositionManager
from risk.manager import RiskManager
from engine.paper_trading import PaperTradingEngine

# Add after the imports section
INDICATOR_CONFIG = {
    'ema_period': 144,
    'macd_fast': 20,
    'macd_slow': 52,
    'macd_signal': 2,
    'rsi_period': 14,
    'sar_step': 0.02,
    'sar_max': 0.2,
    'macd_threshold': 6.5,
}

# Paper trading cache
paper_cache = None

web_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
    template_folder=os.path.join(web_dir, "web", "templates"),
    static_folder=os.path.join(web_dir, "web", "static"),
    static_url_path="/static"
)

# ============================================================
# Global State
# ============================================================

position_mgr = PositionManager()
risk_mgr = RiskManager()
analysis_cache = None
analysis_lock = threading.Lock()
last_update = None


def run_analysis():
    """后台运行分析"""
    global analysis_cache, last_update
    
    try:
        print("[Engine] 获取XAU/USD数据...")
        df = fetch_xauusd_15m("30d")
        
        if df is None or df.empty:
            df = generate_mock_data(30)
        
        print(f"[Engine] 分析 {len(df)} 条K线...")
        df = analyze(df)
        
        # 用仓位管理器执行信号来更新持仓
        pm = PositionManager()
        for i, row in df.iterrows():
            sig = row.get('signal_type', 'wait')
            price = row['close']
            date = str(row.get('date', ''))
            if sig != 'wait':
                pm.execute_signal(sig, price, date)
        
        # 把最终持仓状态写到最后一行
        last_state = pm.get_state(df.iloc[-1]['close'])
        df.loc[df.index[-1], 'position_state'] = str(last_state)
        
        with analysis_lock:
            analysis_cache = df
            last_update = datetime.datetime.now()
            # 同步全局仓位
            position_mgr.units = pm.units[:]
            position_mgr.unit_type = pm.unit_type[:]
            position_mgr.entry_prices = pm.entry_prices[:]
            position_mgr.trades = pm.trades[:]
        
        print(f"[Engine] 分析完成, 最新信号: {get_latest_state(df)}")
    
    except Exception as e:
        print(f"[Engine] 分析失败: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# API Routes
# ============================================================

@app.route("/")
def index():
    """渲染首页，预加载久期回测缓存"""
    # 预加载久期回测缓存
    longterm_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "longterm")
    results_path = os.path.join(longterm_dir, "backtest_results.json")
    longterm_cache = None
    if os.path.exists(results_path):
        with open(results_path) as f:
            longterm_cache = json.load(f)

    return render_template("qianlong.html", longterm_cache=longterm_cache)


@app.route("/api/status")
def api_status():
    """系统状态"""
    global analysis_cache, last_update
    
    with analysis_lock:
        if analysis_cache is not None:
            latest = get_latest_state(analysis_cache)
        else:
            latest = {}
    
    return jsonify({
        'latest': latest,
        'last_update': str(last_update) if last_update else None,
        'cache_status': 'ready' if analysis_cache is not None else 'loading',
        'risk': risk_mgr.get_status(),
        'position': position_mgr.get_state(latest.get('close', 0)),
    })


@app.route("/api/chart")
def api_chart():
    """K线 + 指标数据"""
    global analysis_cache
    
    limit = request.args.get('limit', 200, type=int)
    
    with analysis_lock:
        if analysis_cache is None:
            return jsonify({'error': '数据加载中'})
        
        df = analysis_cache.tail(limit).copy()
    
    # 转换为前端可用的格式
    data = []
    for _, row in df.iterrows():
        data.append({
            'date': str(row['date']),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume']),
            'ema144': float(row.get('ema144', 0)),
            'dea': float(row.get('dea', 0)),
            'macd_hist': float(row.get('macd_hist', 0)),
            'rsi': float(row.get('rsi', 50)),
            'sar': float(row.get('sar', 0)),
            'phase': str(row.get('phase', '')),
            'signal': str(row.get('signal_type', 'wait')),
        })
    
    return jsonify(data)


@app.route("/api/reload", methods=["POST"])
def api_reload():
    """重新加载数据并分析"""
    data = request.get_json() or {}
    period = data.get("period", "30d")
    
    # 在新线程中运行
    t = threading.Thread(target=run_analysis)
    t.start()
    
    return jsonify({'status': 'reloading', 'period': period})


@app.route("/api/trade", methods=["POST"])
def api_trade():
    """执行交易信号 (模拟)"""
    data = request.get_json()
    signal_type = data.get("signal_type", "wait")
    
    global analysis_cache
    with analysis_lock:
        if analysis_cache is not None:
            price = analysis_cache.iloc[-1]['close']
            date = str(analysis_cache.iloc[-1]['date'])
        else:
            price = 2300
            date = ""
    
    # 检查Kill Switch
    blocked, reason = risk_mgr.check_kill_switch()
    if blocked:
        return jsonify({'status': 'blocked', 'reason': reason})
    
    # 执行
    action = position_mgr.execute_signal(signal_type, price, date)
    
    # 更新风控
    risk_mgr.set_equity(100000 + position_mgr.get_unrealized_pnl(price))
    
    return jsonify({
        'status': 'executed',
        'action': action,
        'signal': signal_type,
        'position': position_mgr.get_state(price),
        'risk': risk_mgr.get_status(),
    })


@app.route("/api/iching")
def api_iching():
    """乾卦六爻状态映射"""
    return jsonify({
        'lines': [
            {'line': 1, 'name': '初九', 'chinese': '潜龙勿用', 'english': 'Hidden Dragon', 'state': 'wait', 'desc': '观望, 不妄动'},
            {'line': 2, 'name': '九二', 'chinese': '见龙在田', 'english': 'Dragon in Field', 'state': 'phase3', 'desc': '混沌套利, 高抛低吸'},
            {'line': 3, 'name': '九三', 'chinese': '夕惕若厉', 'english': 'Diligent', 'state': 'transition', 'desc': '利润保护, 伺机转换'},
            {'line': 4, 'name': '九四', 'chinese': '或跃在渊', 'english': 'Leaping', 'state': 'phase1', 'desc': '三维共振, 建立底仓'},
            {'line': 5, 'name': '九五', 'chinese': '飞龙在天', 'english': 'Flying Dragon', 'state': 'phase2', 'desc': '火上浇油, 激进加仓'},
            {'line': 6, 'name': '上九', 'chinese': '亢龙有悔', 'english': 'Arrogant Dragon', 'state': 'exit', 'desc': '信号反转, 无条件清仓'},
        ]
    })


@app.route("/api/paper")
def api_paper():
    """获取模拟盘状态和结果"""
    global paper_cache
    
    if paper_cache is None:
        return jsonify({
            'status': 'not_run',
            'message': '模拟盘尚未运行, 请先点击 "运行模拟盘"',
        })
    
    return jsonify({
        'status': 'complete',
        'metrics': paper_cache.get('metrics', {}),
        'equity_curve': paper_cache.get('equity_curve', []),
        'trade_count': len(paper_cache.get('trades', [])),
    })


@app.route("/api/paper/trades")
def api_paper_trades():
    """获取模拟盘交易记录"""
    global paper_cache
    
    if paper_cache is None:
        return jsonify([])
    
    return jsonify(paper_cache.get('trades', []))


@app.route("/api/news", methods=["POST"])
def api_set_news():
    """设置重大新闻时间 (Rule 3)"""
    data = request.get_json()
    news_time = data.get("news_time")
    
    if news_time:
        risk_mgr.news_event_time = datetime.datetime.fromisoformat(news_time)
        return jsonify({'status': 'set', 'news_time': news_time})
    
    risk_mgr.news_event_time = None
    return jsonify({'status': 'cleared'})


@app.route("/api/backtest")
def api_backtest():
    """回测: 用历史数据跑完整策略"""
    global analysis_cache
    
    with analysis_lock:
        if analysis_cache is None:
            return jsonify({'error': '数据未加载'})
        
        df = analysis_cache.copy()
    
    # 模拟回测
    pm = PositionManager()
    rm = RiskManager()
    rm.start_equity = 100000
    
    results = []
    for i, row in df.iterrows():
        signal = row.get('signal_type', 'wait')
        price = row['close']
        
        if signal != 'wait':
            action = pm.execute_signal(signal, price, str(row['date']))
            results.append({
                'date': str(row['date']),
                'price': price,
                'signal': signal,
                'action': action,
                'units': pm.total_units,
                'pnl': pm.get_unrealized_pnl(price),
            })
    
    total_pnl = pm.get_unrealized_pnl(df.iloc[-1]['close'])
    
    return jsonify({
        'total_pnl': total_pnl,
        'final_units': pm.total_units,
        'trade_count': len(results),
        'trades': results[-50:],  # 最近50笔
    })


@app.route("/api/paper/run", methods=["POST"])
def api_paper_run():
    """运行模拟盘回测 — 严格按策略信号执行"""
    global analysis_cache

    data = request.get_json() or {}
    initial_capital = data.get('initial_capital', 100000)
    contract_size = data.get('contract_size', 100)
    period = data.get('period', '30d')
    start_date = data.get('start_date', None)
    end_date = data.get('end_date', None)

    # Fetch data for the specified period (auto-selects interval)
    if start_date and end_date:
        df, interval_label = fetch_xauusd(period="60d", start_date=start_date, end_date=end_date)
    else:
        df, interval_label = fetch_xauusd(period)

    if df is None or df.empty:
        days = int(period[:-1]) if period.endswith('d') else 30
        df = generate_mock_data(days)
        interval_label = '15m'

    # Analyze the data
    df = analyze(df)

    engine = PaperTradingEngine(
        initial_capital=initial_capital,
        contract_size=contract_size,
    )

    result = engine.run(df)

    # Add config info to result
    result['config'] = {
        'initial_capital': initial_capital,
        'contract_size': contract_size,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'interval': interval_label,
        'data_points': len(df),
        'date_range': f"{df.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {df.iloc[-1]['date'].strftime('%Y-%m-%d')}" if not df.empty else '',
    }

    # Cache for future API calls
    global paper_cache
    paper_cache = result

    return jsonify(result)


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """Get/set indicator parameters"""
    global analysis_cache, last_update
    
    # Default config matching PDF
    default_config = {
        'ema_period': 144,
        'macd_fast': 20,
        'macd_slow': 52,
        'macd_signal': 2,
        'rsi_period': 14,
        'sar_step': 0.02,
        'sar_max': 0.2,
        'macd_threshold': 6.5,
    }
    
    if request.method == 'POST':
        data = request.get_json() or {}
        # Store in session or global (simple approach)
        global INDICATOR_CONFIG
        INDICATOR_CONFIG.update({k: float(v) for k, v in data.items() if v is not None})
        
        # Re-analyze with new config
        def reanalyze():
            global analysis_cache, last_update
            try:
                df = fetch_xauusd_15m("30d")
                if df is None or df.empty:
                    df = generate_mock_data(30)
                df = analyze(df, config=INDICATOR_CONFIG)
                pm = PositionManager()
                for i, row in df.iterrows():
                    sig = row.get('signal_type', 'wait')
                    price = row['close']
                    date = str(row.get('date', ''))
                    if sig != 'wait':
                        pm.execute_signal(sig, price, date)
                with analysis_lock:
                    analysis_cache = df
                    last_update = datetime.datetime.now()
                    position_mgr.units = pm.units[:]
                    position_mgr.unit_type = pm.unit_type[:]
                    position_mgr.entry_prices = pm.entry_prices[:]
                    position_mgr.trades = pm.trades[:]
            except Exception as e:
                print(f"[Engine] Re-analyze failed: {e}")
        
        t = threading.Thread(target=reanalyze)
        t.start()
        
        return jsonify({'status': 'updating', 'config': dict(INDICATOR_CONFIG)})
    
    return jsonify(INDICATOR_CONFIG)


@app.route("/api/config/defaults", methods=["POST"])
def api_config_defaults():
    """Reset to PDF default parameters"""
    global INDICATOR_CONFIG
    INDICATOR_CONFIG = {
        'ema_period': 144,
        'macd_fast': 20,
        'macd_slow': 52,
        'macd_signal': 2,
        'rsi_period': 14,
        'sar_step': 0.02,
        'sar_max': 0.2,
        'macd_threshold': 6.5,
    }
    return jsonify(INDICATOR_CONFIG)


@app.route("/api/killswitch", methods=["POST"])
def api_killswitch():
    """手动触发Kill Switch"""
    risk_mgr.is_cooling = True
    risk_mgr.cooldown_until = datetime.datetime.now() + datetime.timedelta(hours=24)
    return jsonify({'status': 'activated', 'cooldown_until': str(risk_mgr.cooldown_until)})


@app.route("/api/long_backtest")
def api_long_backtest():
    """获取久期回测结果"""
    # Try static data first, then cache
    for path in [
        os.path.join(web_dir, "web", "static", "data", "backtest_2y_result.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache", "backtest_2y_result.json"),
    ]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
    return jsonify({'error': '久期回测数据尚未生成，请先运行 scripts/long_term_backtest.py'})


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  乾六爻交易系统 — Qian Liu Yao")
    print("  XAU/USD | 15m | 信号即道")
    port = int(os.environ.get("PORT", 5048))
    print(f"  http://127.0.0.1:{port}")
    print("=" * 50 + "\n")
    
    # 初始加载
    run_analysis()
    
    app.run(host="0.0.0.0", port=port, debug=False)
