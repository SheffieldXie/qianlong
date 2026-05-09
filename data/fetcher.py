"""
数据获取模块

XAU/USD (现货黄金) 数据源:
- yfinance: Yahoo Finance
- 本地缓存: 避免重复请求

Yahoo Finance 限制:
- 1m: 7天
- 2m/5m/15m/30m: 60天
- 1h: 730天
- 1d: 无限制
"""

import os
import json
import datetime
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _period_to_days(period):
    """解析 period 字符串为天数"""
    if period.endswith('d'):
        return int(period[:-1])
    elif period.endswith('m'):
        return int(period[:-1]) // 60
    elif period.endswith('y'):
        return int(period[:-1]) * 365
    return 60


def _select_interval(period, start_date=None, end_date=None):
    """根据时间跨度自动选择最优K线粒度"""
    if start_date and end_date:
        try:
            delta = pd.to_datetime(end_date) - pd.to_datetime(start_date)
            days = delta.days
        except:
            days = 60
    else:
        days = _period_to_days(period)
    
    if days <= 7:
        return '15m', '15m'
    elif days <= 60:
        return '15m', '15m'
    elif days <= 730:
        return '1h', '1h'
    else:
        return '1d', '1d'


def fetch_xauusd(period="60d", start_date=None, end_date=None):
    """
    获取XAU/USD K线数据 (自动选择最优粒度)
    
    参数:
    - period: 时间跨度, 如 "7d", "30d", "60d", "180d"
    - start_date: 自定义起始日期 (str: "YYYY-MM-DD"), 覆盖 period
    - end_date: 自定义结束日期 (str: "YYYY-MM-DD")
    
    返回: (DataFrame, interval_label) 元组
    DataFrame columns: [date, open, high, low, close, volume]
    """
    interval, label = _select_interval(period, start_date, end_date)
    days = _period_to_days(period) if not start_date else None
    
    # Build cache key
    if start_date and end_date:
        cache_key = f"xauusd_{start_date}_{end_date}_{label}"
    else:
        cache_key = f"xauusd_{period}_{label}"
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    cache_meta = os.path.join(CACHE_DIR, f"{cache_key}_meta.json")
    
    # 检查缓存 (30分钟有效)
    if os.path.exists(cache_path) and os.path.exists(cache_meta):
        with open(cache_meta) as f:
            meta = json.load(f)
        age = datetime.datetime.now().timestamp() - meta.get('timestamp', 0)
        if age < 1800:
            return pd.read_pickle(cache_path), label
    
    try:
        import yfinance as yf
        
        # XAU/USD on Yahoo Finance: GC=F (Gold Futures) or XAUUSD=X
        for ticker in ["GC=F", "XAUUSD=X"]:
            try:
                gold = yf.Ticker(ticker)
                
                if start_date and end_date:
                    df = gold.history(start=start_date, end=end_date, interval=interval)
                else:
                    df = gold.history(period=period, interval=interval)
                
                if not df.empty and len(df) > 50:
                    df = df.reset_index()
                    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
                    
                    if 'datetime' in df.columns:
                        df = df.rename(columns={'datetime': 'date'})
                    elif 'date' not in df.columns:
                        df = df.rename(columns={df.columns[0]: 'date'})
                    
                    # 标准化列名
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
                    
                    # 精确裁剪到请求的天数 (Yahoo 可能返回多余数据)
                    if days is not None:
                        cutoff = df['date'].max() - pd.Timedelta(days=days)
                        df = df[df['date'] >= cutoff].reset_index(drop=True)
                    
                    # 保存缓存
                    df.to_pickle(cache_path)
                    with open(cache_meta, 'w') as f:
                        json.dump({'timestamp': datetime.datetime.now().timestamp(), 
                                   'ticker': ticker, 'interval': label}, f)
                    
                    print(f"[Data] 获取 {len(df)} 条{label} K线 ({ticker}), 区间={df.iloc[0]['date']} ~ {df.iloc[-1]['date']}")
                    return df, label
            except Exception as e:
                print(f"[Data] {ticker} 失败: {e}")
                continue
        
        # 两个ticker都失败, 返回缓存
        if os.path.exists(cache_path):
            return pd.read_pickle(cache_path), label
        
    except ImportError:
        print("[Data] yfinance未安装, 使用模拟数据")
    
    # 返回模拟数据
    mock_days = days if days is not None else 30
    return generate_mock_data(mock_days), label


# Backward compatibility alias
def fetch_xauusd_15m(period="60d", start_date=None, end_date=None):
    """兼容旧接口, 调用新函数"""
    df, _ = fetch_xauusd(period, start_date, end_date)
    return df


def generate_mock_data(days=30):
    """生成模拟XAU/USD 15m数据用于开发测试 — 包含真实趋势和信号"""
    import numpy as np
    
    np.random.seed(42)
    n_bars = days * 96
    
    dates = pd.date_range(end=datetime.datetime.now(), periods=n_bars, freq='15min')
    
    # 生成有趋势的行情: 多个上升/下降周期
    base_price = 2300
    trend = np.zeros(n_bars)
    
    # 创建3-4个大趋势周期
    for cycle in range(4):
        start = int(cycle * n_bars / 4)
        end = int((cycle + 1) * n_bars / 4)
        if cycle % 2 == 0:
            # 上升趋势
            trend[start:end] = np.linspace(0, 80, end - start) + np.random.randn(end - start) * 2
        else:
            # 下降趋势
            trend[start:end] = np.linspace(80, -40, end - start) + np.random.randn(end - start) * 2
    
    # 叠加短期波动
    noise = np.cumsum(np.random.randn(n_bars) * 1.5)
    
    prices = base_price + trend + noise
    
    opens = prices[:-1]
    opens = np.append(opens, prices[-1])
    closes = prices + np.random.randn(n_bars) * 1
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n_bars) * 2)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n_bars) * 2)
    volumes = np.random.randint(100, 1000, n_bars)
    
    df = pd.DataFrame({
        'date': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
    })
    
    cache_path = os.path.join(CACHE_DIR, "mock_15m.pkl")
    df.to_pickle(cache_path)
    
    print(f"[Data] 生成 {len(df)} 条模拟15m K线 (含趋势)")
    return df
