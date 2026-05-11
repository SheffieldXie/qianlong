"""
乾六爻久期回测 — 按年度拆解 + 重大事件标注 + 鲁棒性验证

用法: python3 scripts/long_term_backtest.py
数据: data/cache/xauusd_2y_1d.pkl
输出:
  - data/cache/backtest_2y_result.json  (完整结果，前端消费)
  - data/cache/backtest_yearly_*.json   (按年拆解)
"""
import sys
import os
import json
import numpy as np
import pandas as pd

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.core import analyze, get_latest_state
from engine.paper_trading import PaperTradingEngine

# ============================================================
# 重大事件标注 (2024-05 ~ 2026-05)
# ============================================================
MAJOR_EVENTS = [
    {
        "date": "2024-06-12",
        "label": "美联储维持利率不变",
        "impact": "中性偏鹰，金价短线承压",
        "category": "fed"
    },
    {
        "date": "2024-07-15",
        "label": "特朗普遇刺未遂事件",
        "impact": "避险情绪飙升，金价急涨",
        "category": "geopolitical"
    },
    {
        "date": "2024-09-18",
        "label": "美联储降息50bp",
        "impact": "大幅降息，金价创历史新高",
        "category": "fed"
    },
    {
        "date": "2024-11-05",
        "label": "美国大选（特朗普胜选）",
        "impact": "美元走强但通胀预期升温，金价波动加剧",
        "category": "political"
    },
    {
        "date": "2024-12-18",
        "label": "美联储降息25bp + 点阵图偏鹰",
        "impact": "降息但暗示2025年仅两次降息，金价回调",
        "category": "fed"
    },
    {
        "date": "2025-01-20",
        "label": "特朗普就职",
        "impact": "关税政策预期升温，避险买盘",
        "category": "political"
    },
    {
        "date": "2025-02-01",
        "label": "对加墨加征关税生效",
        "impact": "贸易战升级，金价震荡上行",
        "category": "trade"
    },
    {
        "date": "2025-04-02",
        "label": "全球关税大战（解放日关税）",
        "impact": "全球市场暴跌，金价暴涨避险",
        "category": "trade"
    },
    {
        "date": "2025-04-09",
        "label": "对等关税暂停90天",
        "impact": "市场反弹，金价短期回落",
        "category": "trade"
    },
    {
        "date": "2025-06-18",
        "label": "美联储维持利率不变",
        "impact": "通胀回落缓慢，降息预期推迟",
        "category": "fed"
    },
    {
        "date": "2025-09-17",
        "label": "美联储降息25bp",
        "impact": "年内首次降息，金价走强",
        "category": "fed"
    },
    {
        "date": "2025-12-10",
        "label": "美联储降息25bp",
        "impact": "持续宽松周期，金价再创新高",
        "category": "fed"
    },
    {
        "date": "2025-03-15",
        "label": "硅谷银行事件余波 / 区域性银行危机",
        "impact": "银行业动荡延续，避险支撑金价",
        "category": "banking"
    },
    {
        "date": "2025-08-05",
        "label": "日央行加息 / 日元套息交易平仓",
        "impact": "全球流动性冲击，金价先跌后涨",
        "category": "central_bank"
    },
    {
        "date": "2026-01-15",
        "label": "美伊紧张局势升级",
        "impact": "中东地缘风险，金价跳涨",
        "category": "geopolitical"
    },
    {
        "date": "2026-03-20",
        "label": "美联储政策转向讨论",
        "impact": "加息讨论引发市场震荡",
        "category": "fed"
    },
]


def run_backtest(df, label="full"):
    """对一段数据运行完整回测"""
    df_analyzed = analyze(df)
    engine = PaperTradingEngine(initial_capital=100000, contract_size=100)
    result = engine.run(df_analyzed)
    return df_analyzed, result


def compute_yearly_results(df_full):
    """按年度拆解回测 — 用30天预热期保证指标有效"""
    df_full = df_full.copy()
    if df_full['date'].dt.tz is not None:
        df_full['date'] = df_full['date'].dt.tz_localize(None)
    
    years = sorted(df_full['date'].dt.year.unique())
    yearly = {}
    
    for yr in years:
        yr_start = pd.Timestamp(f"{yr}-01-01")
        yr_end = pd.Timestamp(f"{yr}-12-31")
        warmup_start = yr_start - pd.Timedelta(days=45)
        
        df_yr = df_full[
            (df_full['date'] >= warmup_start) &
            (df_full['date'] <= yr_end)
        ].copy().reset_index(drop=True)
        
        if len(df_yr) < 30:
            continue
        
        df_yr_core = df_yr[df_yr['date'] >= yr_start].copy()
        if df_yr_core.empty:
            continue
        
        price_start = float(df_yr_core.iloc[0]['close'])
        price_end = float(df_yr_core.iloc[-1]['close'])
        price_change = (price_end - price_start) / price_start * 100
        
        try:
            df_yr_analyzed = analyze(df_yr)
            eng = PaperTradingEngine(initial_capital=100000, contract_size=100)
            res = eng.run(df_yr_analyzed)
            
            # 只取该年关闭的交易
            yr_trades = res.get('trades', [])
            yr_closed = [t for t in yr_trades if 'pnl' in t]
            
            # 用权益曲线算该年指标
            eq_curve = res.get('equity_curve', [])
            if len(eq_curve) > 1:
                eq_df = pd.DataFrame(eq_curve)
                initial = eq_df.iloc[0]['equity']
                final = eq_df.iloc[-1]['equity']
                total_ret = (final - initial) / initial
                returns = eq_df['equity'].pct_change().dropna()
                daily_vol = returns.std()
                ann_vol = float(daily_vol * np.sqrt(252)) if daily_vol > 0 else 0
                ann_ret = float((1 + total_ret) ** (252 / max(len(eq_df), 1)) - 1)
                sharpe = float((ann_ret - 0.03) / ann_vol) if ann_vol > 0 else 0
                cummax = eq_df['equity'].cummax()
                drawdown = (eq_df['equity'] - cummax) / cummax
                max_dd = float(drawdown.min())
            else:
                total_ret = 0; ann_ret = 0; sharpe = 0; max_dd = 0
            
            if yr_closed:
                wins = sum(1 for t in yr_closed if t['pnl'] > 0)
                win_rate = wins / len(yr_closed)
                avg_win = float(np.mean([t['pnl'] for t in yr_closed if t['pnl'] > 0])) if wins > 0 else 0
                avg_loss = float(abs(np.mean([t['pnl'] for t in yr_closed if t['pnl'] < 0]))) if len(yr_closed) - wins > 0 else 1.0
                pf = float(avg_win / avg_loss) if avg_loss > 0 else 0
                total_pnl = sum(t['pnl'] for t in yr_closed)
            else:
                win_rate = 0; avg_win = 0; avg_loss = 0; pf = 0; total_pnl = 0
            
            yearly[str(yr)] = {
                "date_range": f"{df_yr_core.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {df_yr_core.iloc[-1]['date'].strftime('%Y-%m-%d')}",
                "data_points": len(df_yr_core),
                "price_start": round(price_start, 2),
                "price_end": round(price_end, 2),
                "price_change_pct": round(price_change, 2),
                "metrics": {
                    "total_return": round(total_ret, 4),
                    "total_pnl": round(total_pnl, 2),
                    "annual_return": round(ann_ret, 4),
                    "sharpe_ratio": round(sharpe, 2),
                    "max_drawdown": round(max_dd, 4),
                    "win_rate": round(win_rate, 4),
                    "profit_factor": round(pf, 2),
                    "total_trades": len(yr_closed),
                    "avg_win": round(avg_win, 2),
                    "avg_loss": round(avg_loss, 2),
                },
                "trades": yr_closed[:50],
            }
        except Exception as e:
            print(f"  年度 {yr} 回测失败: {e}")
            import traceback
            traceback.print_exc()
            yearly[str(yr)] = {"error": str(e)}
    
    return yearly


def find_event_impacts(df_full, result_full):
    """找出重大事件前后价格波动和策略表现"""
    # 确保 date 列无时区
    df = df_full.copy()
    if df['date'].dt.tz is not None:
        df['date'] = df['date'].dt.tz_localize(None)
    
    events_with_impact = []
    
    for evt in MAJOR_EVENTS:
        evt_date = pd.Timestamp(evt["date"])
        # 事件前后各5个交易日
        window_before = df[
            (df['date'] >= evt_date - pd.Timedelta(days=10)) &
            (df['date'] < evt_date)
        ]
        window_after = df[
            (df['date'] >= evt_date) &
            (df['date'] <= evt_date + pd.Timedelta(days=10))
        ]
        
        if len(window_before) < 2 or len(window_after) < 2:
            continue
        
        price_before = window_before.iloc[0]['close']
        price_after_start = window_after.iloc[0]['close']
        price_after_end = window_after.iloc[-1]['close']
        
        move_1d = (price_after_start - price_before) / price_before * 100
        move_5d = (price_after_end - price_before) / price_before * 100
        max_move = (window_after['high'].max() - price_before) / price_before * 100
        
        events_with_impact.append({
            "date": evt["date"],
            "label": evt["label"],
            "category": evt["category"],
            "impact_desc": evt["impact"],
            "price_before": round(price_before, 2),
            "price_after_start": round(price_after_start, 2),
            "price_after_end": round(price_after_end, 2),
            "move_1d_pct": round(move_1d, 2),
            "move_5d_pct": round(move_5d, 2),
            "max_move_pct": round(max_move, 2),
        })
    
    return events_with_impact


def robustness_check(df_full, result_full):
    """鲁棒性验证：不同市场环境下的表现"""
    df = df_full.copy()
    if df['date'].dt.tz is not None:
        df['date'] = df['date'].dt.tz_localize(None)
    
    metrics = result_full.get('metrics', {})
    equity_curve = result_full.get('equity_curve', [])
    
    # 1. 分段表现 (上下半年)
    df['month'] = df['date'].dt.month
    df['half'] = df['date'].dt.year.astype(str) + '-' + df['month'].apply(lambda m: 'H1' if m <= 6 else 'H2').astype(str)
    
    half_results = {}
    for half, grp in df.groupby('half'):
        if len(grp) < 30:
            continue
        try:
            _, half_res = run_backtest(grp.reset_index(drop=True), label=half)
            half_results[half] = half_res.get('metrics', {})
        except:
            pass
    
    # 2. 最大连续亏损
    trades = result_full.get('trades', [])
    closed = [t for t in trades if 'pnl' in t]
    if closed:
        max_consec_loss = 0
        curr = 0
        for t in closed:
            if t['pnl'] < 0:
                curr += 1
                max_consec_loss = max(max_consec_loss, curr)
            else:
                curr = 0
    else:
        max_consec_loss = 0
    
    # 3. 波动率分层表现
    df_daily_ret = pd.DataFrame(equity_curve)
    if not df_daily_ret.empty and len(df_daily_ret) > 1:
        df_daily_ret['daily_ret'] = df_daily_ret['equity'].pct_change()
        high_vol = df_daily_ret[df_daily_ret['daily_ret'].abs() > df_daily_ret['daily_ret'].abs().quantile(0.9)]
        low_vol = df_daily_ret[df_daily_ret['daily_ret'].abs() <= df_daily_ret['daily_ret'].abs().quantile(0.9)]
        
        high_vol_mean_ret = float(high_vol['daily_ret'].mean()) if not high_vol.empty else 0
        low_vol_mean_ret = float(low_vol['daily_ret'].mean()) if not low_vol.empty else 0
    else:
        high_vol_mean_ret = 0
        low_vol_mean_ret = 0
    
    return {
        "total_return_pct": round(metrics.get('total_return', 0) * 100, 2),
        "annual_return_pct": round(metrics.get('annual_return', 0) * 100, 2),
        "sharpe_ratio": round(metrics.get('sharpe_ratio', 0), 2),
        "max_drawdown_pct": round(metrics.get('max_drawdown', 0) * 100, 2),
        "win_rate_pct": round(metrics.get('win_rate', 0) * 100, 2),
        "profit_factor": round(metrics.get('profit_factor', 0), 2),
        "max_consecutive_losses": max_consec_loss,
        "total_trades": len(closed),
        "half_year_performance": half_results,
        "high_volatility_avg_return": round(high_vol_mean_ret * 100, 4),
        "low_volatility_avg_return": round(low_vol_mean_ret * 100, 4),
        "data_interval": "1d (日线)",
        "note": "日线级别回测，信号频率低于15m，但能捕捉中长期趋势",
    }


def main():
    cache_path = os.path.join(os.path.dirname(__file__), "../data/cache/xauusd_2y_1d.pkl")
    if not os.path.exists(cache_path):
        print("ERROR: 找不到2年数据文件，请先运行 fetch_2y_data.py")
        sys.exit(1)
    
    print("=" * 60)
    print("  乾六爻久期回测系统 — 2年数据")
    print("=" * 60)
    
    df_full = pd.read_pickle(cache_path)
    # 统一去掉时区
    if df_full['date'].dt.tz is not None:
        df_full['date'] = df_full['date'].dt.tz_localize(None)
    print(f"\n数据加载: {len(df_full)} 根日线 K线")
    print(f"区间: {df_full.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {df_full.iloc[-1]['date'].strftime('%Y-%m-%d')}")
    print(f"价格: ${df_full['close'].min():.2f} ~ ${df_full['close'].max():.2f}")
    
    # 1. 完整回测
    print("\n[1/4] 运行完整2年回测...")
    df_analyzed, result_full = run_backtest(df_full, label="2y")
    metrics = result_full.get('metrics', {})
    print(f"  初始资金: ${metrics.get('initial_capital', 0):,.0f}")
    print(f"  最终权益: ${metrics.get('final_equity', 0):,.2f}")
    print(f"  总收益率: {metrics.get('total_return', 0)*100:.2f}%")
    print(f"  年化收益: {metrics.get('annual_return', 0)*100:.2f}%")
    print(f"  夏普比率: {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  最大回撤: {metrics.get('max_drawdown', 0)*100:.2f}%")
    print(f"  胜率:     {metrics.get('win_rate', 0)*100:.2f}%")
    print(f"  盈亏比:   {metrics.get('profit_factor', 0):.2f}")
    print(f"  交易次数: {metrics.get('total_trades', 0)}")
    
    # 2. 按年回测
    print("\n[2/4] 按年度拆解回测...")
    yearly = compute_yearly_results(df_full)
    for yr, data in yearly.items():
        if 'error' in data:
            print(f"  {yr}: 失败 - {data['error']}")
            continue
        m = data['metrics']
        print(f"  {yr}: 收益 {m.get('total_return',0)*100:+.2f}% | 夏普 {m.get('sharpe_ratio',0):.2f} | "
              f"回撤 {m.get('max_drawdown',0)*100:.2f}% | 胜率 {m.get('win_rate',0)*100:.1f}% | "
              f"交易 {m.get('total_trades',0)}笔")
    
    # 3. 事件影响分析
    print("\n[3/4] 重大事件影响分析...")
    events_impact = find_event_impacts(df_full, result_full)
    for evt in events_impact:
        print(f"  {evt['date']} | {evt['label']}")
        print(f"    价格变动: 1日 {evt['move_1d_pct']:+.2f}% | 5日 {evt['move_5d_pct']:+.2f}% | 最大 {evt['max_move_pct']:+.2f}%")
    
    # 4. 鲁棒性验证
    print("\n[4/4] 鲁棒性验证...")
    robustness = robustness_check(df_full, result_full)
    print(f"  总收益率: {robustness['total_return_pct']:+.2f}%")
    print(f"  年化收益: {robustness['annual_return_pct']:+.2f}%")
    print(f"  最大回撤: {robustness['max_drawdown_pct']:+.2f}%")
    print(f"  连续最大亏损: {robustness['max_consecutive_losses']}")
    print(f"  高波动期日均收益: {robustness['high_volatility_avg_return']:+.4f}%")
    print(f"  低波动期日均收益: {robustness['low_volatility_avg_return']:+.4f}%")
    
    # 组装完整结果
    full_result = {
        "full_period": {
            "date_range": f"{df_full.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {df_full.iloc[-1]['date'].strftime('%Y-%m-%d')}",
            "data_points": len(df_full),
            "price_start": round(float(df_full.iloc[0]['close']), 2),
            "price_end": round(float(df_full.iloc[-1]['close']), 2),
            "price_change_pct": round((df_full.iloc[-1]['close'] - df_full.iloc[0]['close']) / df_full.iloc[0]['close'] * 100, 2),
            "metrics": metrics,
            "equity_curve": result_full.get('equity_curve', []),
        },
        "yearly": yearly,
        "events_impact": events_impact,
        "robustness": robustness,
        "major_events": MAJOR_EVENTS,
    }
    
    # 输出 JSON
    out_dir = os.path.join(os.path.dirname(__file__), "../data/cache")
    out_path = os.path.join(out_dir, "backtest_2y_result.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(full_result, f, ensure_ascii=False, indent=2, default=str)
    
    # 也输出到 server.py 可以读取的 public 目录
    public_dir = os.path.join(os.path.dirname(__file__), "../web/static/data")
    os.makedirs(public_dir, exist_ok=True)
    public_path = os.path.join(public_dir, "backtest_2y_result.json")
    with open(public_path, 'w', encoding='utf-8') as f:
        json.dump(full_result, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n结果已保存: {out_path}")
    print(f"前端数据: {public_path}")
    print("\n" + "=" * 60)
    print("  回测完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
