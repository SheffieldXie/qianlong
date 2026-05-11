"""
久期回测脚本 - 乾六爻交易系统

获取过去2年 XAU/USD 日线数据，按年切割回测，输出年度指标。
同时标注重大事件节点，验证系统鲁棒性。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import datetime
import numpy as np
import pandas as pd
import yfinance as yf

from engine.core import analyze
from engine.paper_trading import PaperTradingEngine


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types"""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)

# ============================================================
# Major Events Timeline (2024-2026)
# Events that caused significant XAU/USD price movements
# ============================================================
MAJOR_EVENTS = [
    # 2024 Events
    {"date": "2024-03-20", "name": "FOMC 维持利率不变", "type": "fed",
     "desc": "美联储3月议息会议维持5.25-5.50%利率不变，但点阵图暗示年内降息3次"},
    {"date": "2024-04-12", "name": "中东局势升温", "type": "geopolitical",
     "desc": "以色列-伊朗冲突升级，避险需求推动金价突破$2400"},
    {"date": "2024-05-01", "name": "FOMC 维持利率", "type": "fed",
     "desc": "鲍威尔称不急于降息，通胀粘性超预期"},
    {"date": "2024-09-18", "name": "美联储首次降息50bp", "type": "fed",
     "desc": "美联储大幅降息50bp至4.75-5.00%，黄金飙升至$2600+"},
    {"date": "2024-11-06", "name": "美国大选结果出炉", "type": "political",
     "desc": "特朗普胜选，市场波动加剧，金价先跌后涨"},
    {"date": "2024-12-18", "name": "FOMC 降息25bp但鹰派指引", "type": "fed",
     "desc": "降息25bp但暗示2025年仅降息2次，金价短期承压"},

    # 2025 Events
    {"date": "2025-01-29", "name": "FOMC 维持利率不变", "type": "fed",
     "desc": "美联储1月维持利率不变，等待通胀数据进一步确认"},
    {"date": "2025-03-19", "name": "FOMC 维持利率 + 关税冲击", "type": "fed",
     "desc": "维持利率不变，同时市场对全球关税战担忧加剧，避险买盘涌入"},
    {"date": "2025-04-02", "name": "全球关税战升级", "type": "geopolitical",
     "desc": "多国宣布报复性关税，贸易战升级，黄金作为避险资产大涨突破$3300"},
    {"date": "2025-06-11", "name": "FOMC 首次降息", "type": "fed",
     "desc": "经济放缓信号明确，美联储开启新一轮降息周期"},
    {"date": "2025-09-17", "name": "连续降息 + 银行危机隐忧", "type": "fed",
     "desc": "美联储再次降息，同时商业地产坏账引发银行业担忧"},
    {"date": "2025-11-04", "name": "中期选举结果", "type": "political",
     "desc": "中期选举结果出炉，政策不确定性引发市场波动"},

    # 2026 Events
    {"date": "2026-01-28", "name": "FOMC 大幅降息50bp", "type": "fed",
     "desc": "经济衰退风险上升，美联储紧急降息50bp刺激经济"},
    {"date": "2026-03-18", "name": "全球央行增持黄金", "type": "central_bank",
     "desc": "多国央行大幅增持黄金储备，金价创新高后回调"},
    {"date": "2026-05-01", "name": "地缘冲突再升级", "type": "geopolitical",
     "desc": "新一轮地缘政治紧张局势，避险需求再次推动金价"},
]


def fetch_long_term_data():
    """获取2年+ XAU/USD 日线数据"""
    print("[LongTerm] 获取 XAU/USD 历史数据...")

    gold = yf.Ticker('GC=F')
    df = gold.history(start="2024-01-01", end="2026-12-31", interval="1d")

    if df.empty:
        print("[LongTerm] GC=F 失败，尝试 XAUUSD=X")
        gold = yf.Ticker('XAUUSD=X')
        df = gold.history(start="2024-01-01", end="2026-12-31", interval="1d")

    if df.empty:
        raise ValueError("无法获取 XAU/USD 数据")

    # 标准化格式
    df = df.reset_index()
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]

    if 'datetime' in df.columns:
        df = df.rename(columns={'datetime': 'date'})

    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if 'open' in cl: col_map[c] = 'open'
        elif 'high' in cl: col_map[c] = 'high'
        elif 'low' in cl: col_map[c] = 'low'
        elif 'close' in cl: col_map[c] = 'close'
        elif 'volume' in cl: col_map[c] = 'volume'
        elif 'date' in cl or 'time' in cl: col_map[c] = 'date'

    df = df.rename(columns=col_map)
    df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    print(f"[LongTerm] 获取 {len(df)} 条日线数据")
    print(f"[LongTerm] 时间范围: {df.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {df.iloc[-1]['date'].strftime('%Y-%m-%d')}")

    return df


def run_yearly_backtest(df, initial_capital=100000, contract_size=100, config=None):
    """按年切割数据，分别回测"""
    df['year'] = df['date'].dt.year

    years = sorted(df['year'].unique())
    results = {}

    for year in years:
        # 前一年12月数据作为预热期 (用于EMA/MACD计算)
        year_df = df[df['year'] == year].copy().reset_index(drop=True)
        prev_month = df[df['date'] < pd.Timestamp(f"{year}-01-01")].tail(21)
        if len(prev_month) > 0:
            year_df = pd.concat([prev_month, year_df]).reset_index(drop=True)

        print(f"\n{'='*60}")
        print(f"[LongTerm] {year}年回测 ({len(year_df)} 个交易日, 含21天预热)")
        print(f"{'='*60}")

        # Run analysis with custom config
        analyzed = analyze(year_df, config=config)

        # Run paper trading
        engine = PaperTradingEngine(
            initial_capital=initial_capital,
            contract_size=contract_size,
        )
        report = engine.run(analyzed)

        # Find event dates within this year
        year_events = [e for e in MAJOR_EVENTS if e['date'].startswith(str(year))]

        # Calculate additional metrics for robustness assessment
        equity_curve = pd.DataFrame(report['equity_curve'])
        trades = report['trades']

        # Drawdown duration analysis
        equity = equity_curve['equity']
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        in_drawdown = drawdown < 0
        drawdown_periods = []
        start_dd = None
        for i, in_dd in enumerate(in_drawdown):
            if in_dd and start_dd is None:
                start_dd = i
            elif not in_dd and start_dd is not None:
                drawdown_periods.append(i - start_dd)
                start_dd = None
        if start_dd is not None:
            drawdown_periods.append(len(in_drawdown) - start_dd)

        max_dd_duration = max(drawdown_periods) if drawdown_periods else 0

        # Trade frequency
        closed_trades = [t for t in trades if 'pnl' in t]
        trade_freq = len(closed_trades) / len(year_df) * 252 if len(year_df) > 0 else 0

        # Consecutive wins/losses
        if closed_trades:
            pnls = [t['pnl'] for t in closed_trades]
            max_win_streak = 0
            max_loss_streak = 0
            cur_win = 0
            cur_loss = 0
            for p in pnls:
                if p > 0:
                    cur_win += 1
                    cur_loss = 0
                    max_win_streak = max(max_win_streak, cur_win)
                else:
                    cur_loss += 1
                    cur_win = 0
                    max_loss_streak = max(max_loss_streak, cur_loss)
        else:
            max_win_streak = 0
            max_loss_streak = 0
            pnls = []

        year_result = {
            'year': year,
            'trading_days': len(year_df),
            'metrics': report['metrics'],
            'events': year_events,
            'robustness': {
                'max_drawdown_duration_days': max_dd_duration,
                'trade_frequency_per_year': round(trade_freq, 1),
                'max_consecutive_wins': max_win_streak,
                'max_consecutive_losses': max_loss_streak,
                'avg_trade_pnl': round(np.mean(pnls), 2) if pnls else 0,
                'std_trade_pnl': round(np.std(pnls), 2) if pnls else 0,
            },
            # Store key data points for charting
            'equity_points': _serialize_equity_points(equity_curve),
            'trade_dates': [t['date'] for t in closed_trades],
            'event_impacts': _calculate_event_impacts(year_df, year_events),
        }

        # Print summary
        m = report['metrics']
        print(f"  初始资金:  ${m['initial_capital']:,.0f}")
        print(f"  最终权益:  ${m['final_equity']:,.2f}")
        print(f"  总收益率:  {m['total_return']*100:.2f}%")
        print(f"  年化收益:  {m['annual_return']*100:.2f}%")
        print(f"  夏普比率:  {m['sharpe_ratio']:.2f}")
        print(f"  最大回撤:  {m['max_drawdown']*100:.2f}%")
        print(f"  胜率:      {m['win_rate']*100:.1f}%")
        print(f"  总交易:    {m['total_trades']}")
        print(f"  重大事件:  {len(year_events)} 个")

        results[year] = year_result

    return results


def _serialize_equity_points(equity_curve):
    """Convert equity curve to JSON-serializable format"""
    points = []
    for _, row in equity_curve.iterrows():
        d = row['date']
        if hasattr(d, 'strftime'):
            d = d.strftime('%Y-%m-%d %H:%M:%S')
        points.append({
            'date': str(d)[:19],
            'equity': float(row['equity']),
        })
    return points


def _calculate_event_impacts(df, events):
    """计算事件前后的价格影响"""
    impacts = []
    # Normalize dates to string for comparison
    df_dates = df['date'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)[:10])

    for event in events:
        try:
            event_str = event['date'][:10]
            # Find closest trading day
            matches = df_dates[df_dates == event_str]
            if len(matches) == 0:
                continue
            idx = matches.index[0]

            # 5 days before and after
            before_idx = max(0, idx - 5)
            after_idx = min(len(df) - 1, idx + 5)

            price_before = df.iloc[before_idx]['close']
            price_after = df.iloc[after_idx]['close']
            price_event = df.iloc[idx]['close']

            change = (price_after - price_before) / price_before * 100

            impacts.append({
                'date': event['date'],
                'name': event['name'],
                'price_before': round(price_before, 2),
                'price_after': round(price_after, 2),
                'change_pct': round(change, 2),
            })
        except Exception as e:
            print(f"  [Warning] Event impact calc failed for {event['date']}: {e}")

    return impacts


def generate_robustness_report(results):
    """生成整体鲁棒性评估"""
    all_metrics = []
    for year, data in results.items():
        m = data['metrics']
        all_metrics.append({
            'year': year,
            'total_return': m['total_return'],
            'sharpe': m['sharpe_ratio'],
            'max_dd': m['max_drawdown'],
            'win_rate': m['win_rate'],
            'profit_factor': m['profit_factor'],
            'trades': m['total_trades'],
        })

    df_m = pd.DataFrame(all_metrics)

    # Overall assessment
    assessment = {
        'years_covered': len(results),
        'avg_annual_return': round(df_m['total_return'].mean(), 4),
        'avg_sharpe': round(df_m['sharpe'].mean(), 2),
        'avg_max_drawdown': round(df_m['max_dd'].mean(), 4),
        'avg_win_rate': round(df_m['win_rate'].mean(), 4),
        'avg_profit_factor': round(df_m['profit_factor'].mean(), 2),
        'total_trades_all_years': int(df_m['trades'].sum()),
        'positive_years': int((df_m['total_return'] > 0).sum()),
        'total_years': len(results),
        'consistency_score': _calc_consistency(df_m),
        'robustness_grade': _grade_robustness(df_m),
    }

    return assessment


def _calc_consistency(df_m):
    """计算一致性评分 (0-100)"""
    # Based on: positive years ratio, sharpe consistency, drawdown control
    positive_ratio = (df_m['total_return'] > 0).sum() / len(df_m)
    sharpe_consistency = 1 - df_m['sharpe'].std() / max(abs(df_m['sharpe'].mean()), 0.01)
    dd_control = 1 - abs(df_m['max_dd'].mean())

    score = (positive_ratio * 0.4 + max(0, sharpe_consistency) * 0.3 + max(0, dd_control) * 0.3) * 100
    return round(min(max(score, 0), 100), 1)


def _grade_robustness(df_m):
    """鲁棒性评级"""
    positive_ratio = (df_m['total_return'] > 0).sum() / len(df_m)
    avg_sharpe = df_m['sharpe'].mean()
    avg_dd = abs(df_m['max_dd'].mean())

    if positive_ratio >= 0.8 and avg_sharpe > 1.0 and avg_dd < 0.15:
        return {"grade": "A", "label": "极强", "color": "#00C853"}
    elif positive_ratio >= 0.6 and avg_sharpe > 0.5 and avg_dd < 0.25:
        return {"grade": "B", "label": "良好", "color": "#4A90D9"}
    elif positive_ratio >= 0.5 and avg_sharpe > 0:
        return {"grade": "C", "label": "一般", "color": "#D4A017"}
    else:
        return {"grade": "D", "label": "较弱", "color": "#C41E3A"}


def main():
    import sys as _sys
    
    print("=" * 60)
    print("  乾六爻交易系统 - 久期回测 (2024-2026)")
    print("=" * 60)

    # 可选: 读取自定义配置
    config = None
    if len(_sys.argv) > 1:
        config_path = _sys.argv[1]
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            print(f"\n[LongTerm] 使用自定义配置: {config_path}")
            print(f"  布林带: {config.get('bb_mult_trend',1.5)}σ趋势 / {config.get('bb_mult_extreme',3.0)}σ极端")
            print(f"  MACD阈值: {config.get('macd_threshold',6.5)}")
        else:
            print(f"[LongTerm] 配置文件不存在: {config_path}")

    # 1. Fetch data
    df = fetch_long_term_data()

    # 2. Save data for frontend
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "longterm")
    os.makedirs(data_dir, exist_ok=True)

    # Save raw data as JSON for frontend
    data_json = df.to_dict('records')
    for row in data_json:
        if isinstance(row.get('date'), pd.Timestamp):
            row['date'] = row['date'].strftime('%Y-%m-%d')

    with open(os.path.join(data_dir, "xauusd_2yr.json"), 'w') as f:
        json.dump(data_json, f, indent=2)
    print(f"[LongTerm] 数据已保存到 data/longterm/xauusd_2yr.json")

    # 3. Run yearly backtest with custom config
    results = run_yearly_backtest(df, config=config)

    # 4. Generate robustness report
    assessment = generate_robustness_report(results)

    print(f"\n{'='*60}")
    print("  整体鲁棒性评估")
    print(f"{'='*60}")
    print(f"  覆盖年份: {assessment['years_covered']} 年")
    print(f"  正收益年份: {assessment['positive_years']}/{assessment['total_years']}")
    print(f"  平均年化收益: {assessment['avg_annual_return']*100:.2f}%")
    print(f"  平均夏普: {assessment['avg_sharpe']:.2f}")
    print(f"  平均最大回撤: {assessment['avg_max_drawdown']*100:.2f}%")
    print(f"  平均胜率: {assessment['avg_win_rate']*100:.1f}%")
    print(f"  一致性评分: {assessment['consistency_score']}/100")
    print(f"  鲁棒性评级: {assessment['robustness_grade']['grade']} ({assessment['robustness_grade']['label']})")

    # 5. Save results
    # Prepare results for JSON serialization
    serializable_results = {}
    for year, data in results.items():
        serializable_results[str(year)] = {
            'year': year,
            'trading_days': data['trading_days'],
            'metrics': data['metrics'],
            'events': data['events'],
            'robustness': data['robustness'],
            'event_impacts': data['event_impacts'],
            'equity_points': data['equity_points'],
            'trade_dates': data['trade_dates'],
        }

    output = {
        'results': serializable_results,
        'assessment': assessment,
        'all_events': MAJOR_EVENTS,
    }

    with open(os.path.join(data_dir, "backtest_results.json"), 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    print(f"[LongTerm] 回测结果已保存到 data/longterm/backtest_results.json")

    return output


if __name__ == "__main__":
    main()
