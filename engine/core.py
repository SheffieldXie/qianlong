"""
乾六爻核心引擎 — 严格按PDF，支持自定义参数
"""

import numpy as np
import pandas as pd


def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calc_ema144(close, period=144):
    return calc_ema(close, period)


def calc_macd(close, fast=20, slow=52, signal=2):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = 2 * (dif - dea)
    return dif, dea, macd_hist


def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_atr(high, low, close, period=14):
    """Average True Range — 波动率测量"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def calc_bollinger(close, period=144, mult_trend=1.5, mult_extreme=3.0):
    """
    布林带变体 — 中轨=EMA, 非SMA
    1.5σ 带宽: 趋势判断 (价格突破此带 = 进入趋势)
    3.0σ 带宽: 极端判断 (价格触及此带 = 超买超卖区)
    """
    ema = calc_ema(close, period)
    std = close.rolling(window=period).std()
    
    upper_trend = ema + mult_trend * std
    lower_trend = ema - mult_trend * std
    upper_extreme = ema + mult_extreme * std
    lower_extreme = ema - mult_extreme * std
    
    return ema, upper_trend, lower_trend, upper_extreme, lower_extreme, std


def calc_sar(high, low, acceleration=0.02, max_acceleration=0.2):
    sar = np.zeros(len(high))
    trend = np.zeros(len(high))
    ep = np.zeros(len(high))
    af = np.zeros(len(high))
    
    if low[1] < low[0]:
        trend[0] = -1; sar[0] = high[0]; ep[0] = low[0]
    else:
        trend[0] = 1; sar[0] = low[0]; ep[0] = high[0]
    af[0] = acceleration
    
    for i in range(1, len(high)):
        current_sar = sar[i-1] + af[i-1] * (ep[i-1] - sar[i-1])
        if trend[i-1] == 1:
            if i >= 2:
                current_sar = min(current_sar, min(low[i-1], low[i-2]))
            if low[i] < current_sar:
                trend[i] = -1; sar[i] = ep[i-1]; ep[i] = low[i]; af[i] = acceleration
                continue
        else:
            if i >= 2:
                current_sar = max(current_sar, max(high[i-1], high[i-2]))
            if high[i] > current_sar:
                trend[i] = 1; sar[i] = ep[i-1]; ep[i] = high[i]; af[i] = acceleration
                continue
        
        trend[i] = trend[i-1]
        sar[i] = current_sar
        ep[i] = ep[i-1]
        af[i] = af[i-1]
        
        if trend[i-1] == 1 and high[i] > ep[i-1]:
            ep[i] = high[i]; af[i] = min(af[i-1] + acceleration, max_acceleration)
        elif trend[i-1] == -1 and low[i] < ep[i-1]:
            ep[i] = low[i]; af[i] = min(af[i-1] + acceleration, max_acceleration)
    
    return sar, trend


def get_macd_state(dea, threshold=6.5):
    if dea > threshold: return "strong_bull"
    elif dea > 0: return "weak_bull"
    elif dea > -threshold: return "weak_bear"
    else: return "strong_bear"


def get_rsi_state(rsi):
    if rsi >= 75: return "super_overbought"
    elif rsi >= 70: return "overbought"
    elif rsi >= 60: return "bull_strong"
    elif rsi >= 40: return "chaos"
    elif rsi >= 30: return "bear_strong"
    elif rsi >= 15: return "oversold"
    else: return "super_oversold"


def detect_phase(dea, threshold=6.5):
    if dea > threshold: return "phase2_bull"
    elif dea < -threshold: return "phase2_bear"
    elif abs(dea) <= threshold: return "phase3_chaos"
    else: return "phase1"


def detect_signal(row):
    dea = row.get('dea', 0)
    rsi = row.get('rsi', 50)
    prev_rsi = row.get('prev_rsi', 50)
    prev_dea = row.get('prev_dea', 0)
    price = row.get('close', 0)
    ema144 = row.get('ema144', 0)
    sar_trend = row.get('sar_trend', 0)
    sar_flip = row.get('sar_flip', False)
    
    has_long_base = row.get('has_long_base', False)
    has_short_base = row.get('has_short_base', False)
    has_long_addon = row.get('has_long_addon', False)
    has_short_addon = row.get('has_short_addon', False)
    has_arb_long = row.get('has_arb_long', False)
    has_arb_short = row.get('has_arb_short', False)
    total_long = row.get('total_long', 0)
    total_short = row.get('total_short', 0)
    macd_threshold = row.get('macd_threshold', 6.5)
    
    # ── 布林带参数 (可配置) ──
    bb_upper_trend = row.get('bb_upper_trend', float('inf'))
    bb_lower_trend = row.get('bb_lower_trend', float('-inf'))
    bb_upper_extreme = row.get('bb_upper_extreme', float('inf'))
    bb_lower_extreme = row.get('bb_lower_extreme', float('-inf'))
    bb_std = row.get('bb_std', 0)
    atr = row.get('atr', 0)
    # 浮动阈值: 当价格突破1.5σ趋势带时，MACD阈值动态放大
    bb_trend_breakout = price > bb_upper_trend or price < bb_lower_trend
    # 3σ极端区
    bb_at_extreme_high = price >= bb_upper_extreme
    bb_at_extreme_low = price <= bb_lower_extreme
    
    phase = detect_phase(dea, macd_threshold)
    
    # ── SAR 翻转 (最高优先级) ──
    if sar_flip:
        if sar_trend == -1 and (has_long_base or has_long_addon or has_arb_long):
            return ('clear_all', 1.0, 'SAR翻空: 无条件清空全部多单')
        elif sar_trend == 1 and (has_short_base or has_short_addon or has_arb_short):
            return ('clear_all', 1.0, 'SAR翻多: 无条件清空全部空单')
    
    # ── BB 极端区 + RSI 抄底/抄顶 ──
    # 价格触及3σ上轨 + RSI超买 → 潜在做空信号
    if bb_at_extreme_high and rsi >= 70:
        if not has_short_base and not has_short_addon and total_short == 0:
            return ('entry_short_4', 0.85, f'BB极端区+RSI超买: 价格触及3σ上轨, RSI={rsi:.0f} → 做空')
        if has_short_base and total_short < 8:
            return ('add_short_4', 0.8, 'BB极端区+RSI超买: 加仓做空')
    
    # 价格触及3σ下轨 + RSI超卖 → 潜在做多信号
    if bb_at_extreme_low and rsi <= 30:
        if not has_long_base and not has_long_addon and total_long == 0:
            return ('entry_long_4', 0.85, f'BB极端区+RSI超卖: 价格触及3σ下轨, RSI={rsi:.0f} → 做多')
        if has_long_base and total_long < 8:
            return ('add_long_4', 0.8, 'BB极端区+RSI超卖: 加仓做多')
    
    # BB极端区止盈
    if has_long_addon and bb_at_extreme_high:
        return ('clear_addons', 0.75, 'BB极端区: 清掉多单加仓部分, 仅保留底仓')
    if has_short_addon and bb_at_extreme_low:
        return ('clear_addons', 0.75, 'BB极端区: 清掉空单加仓部分, 仅保留底仓')
    if has_arb_long and bb_at_extreme_high:
        return ('clear_all', 0.85, 'BB极端区+套利多: 全部清仓')
    if has_arb_short and bb_at_extreme_low:
        return ('clear_all', 0.85, 'BB极端区+套利空: 全部清仓')
    
    # ── Phase 2: 趋势主导期 (DEA 突破浮动阈值) ──
    if phase == 'phase2_bull':
        if not has_long_base and not has_long_addon and total_long == 0:
            return ('entry_long_4', 0.95, '强趋势MACD>+阈值: 立即建立多单底仓')
        if has_long_base and not has_long_addon and total_long < 8:
            return ('add_long_4', 0.95, 'MACD>+阈值: 必须加仓4份(火上浇油)')
        if has_long_base and has_long_addon and total_long < 12:
            return ('add_long_4', 0.9, 'MACD>+阈值: 继续加仓')
        if rsi > 75: return ('wait', 0.9, 'RSI>75: 趋势强势, 持仓不动')
        if prev_rsi >= 70 and rsi < 70 and (has_long_addon or has_arb_long):
            return ('cut_half', 0.8, 'RSI回落至70: 减半仓')
        if prev_rsi >= 50 and rsi < 50 and (has_long_addon or has_arb_long):
            return ('clear_addons', 0.85, 'RSI跌破50: 清空加仓部分, 仅保留底仓')
        if prev_rsi <= 60 and rsi > 60 and has_long_base and not has_long_addon:
            return ('restore_long', 0.7, 'RSI重新上破60: 加回被减仓位')
        if prev_dea > macd_threshold and dea <= macd_threshold and dea > 0 and has_long_addon:
            return ('clear_addons', 0.7, 'MACD下破+阈值但>0: 保持减仓观察')
        if prev_dea > 0 and dea <= 0 and has_long_base:
            return ('cut_half', 0.9, 'MACD慢线跌破0轴: 减半底仓')
        return ('wait', 0.5, '②多头趋势持有中')
    
    elif phase == 'phase2_bear':
        if not has_short_base and not has_short_addon and total_short == 0:
            return ('entry_short_4', 0.95, '强趋势MACD<-阈值: 立即建立空单底仓')
        if has_short_base and not has_short_addon and total_short < 8:
            return ('add_short_4', 0.95, 'MACD<-阈值: 必须加仓4份(火上浇油)')
        if has_short_base and has_short_addon and total_short < 12:
            return ('add_short_4', 0.9, 'MACD<-阈值: 继续加仓')
        if rsi < 25: return ('wait', 0.9, 'RSI<25: 空头强势, 持仓不动')
        if prev_rsi <= 30 and rsi > 30 and (has_short_addon or has_arb_short):
            return ('cut_half', 0.8, 'RSI上穿30: 减半仓')
        if prev_rsi <= 50 and rsi > 50 and (has_short_addon or has_arb_short):
            return ('clear_addons', 0.85, 'RSI上穿50: 清空加仓, 仅保留底仓')
        if prev_rsi >= 40 and rsi < 40 and has_short_base and not has_short_addon:
            return ('restore_short', 0.7, 'RSI重新下破40: 加回被减仓位')
        if prev_dea < -macd_threshold and dea >= -macd_threshold and dea < 0 and has_short_addon:
            return ('clear_addons', 0.7, 'MACD上破-阈值但<0: 维持减仓观察')
        if prev_dea < 0 and dea >= 0 and has_short_base:
            return ('cut_half', 0.9, 'MACD慢线上穿0轴: 减半底仓')
        return ('wait', 0.5, '②空头趋势持有中')
    
    elif phase == 'phase3_chaos':
        if rsi <= 30 and prev_rsi > 30 and not has_arb_long and total_short == 0:
            return ('arb_long_4', 0.85, '③混沌期: RSI≤30超卖, 建多头套利仓4份')
        if rsi >= 70 and prev_rsi < 70 and not has_arb_short and total_long == 0:
            return ('arb_short_4', 0.85, '③混沌期: RSI≥70超买, 建空头套利仓4份')
        if has_arb_long:
            if prev_rsi <= 50 and rsi > 50: return ('cut_half', 0.75, '③套利多: RSI至50, 减半仓')
            if prev_rsi <= 70 and rsi > 70: return ('clear_all', 0.8, '③套利多: RSI至70, 清空剩余')
            if dea < -macd_threshold: return ('clear_all', 0.9, '③套利多: MACD跌破-阈值, 趋势反转出清')
        if has_arb_short:
            if prev_rsi >= 50 and rsi < 50: return ('cut_half', 0.75, '③套利空: RSI至50, 减半仓')
            if prev_rsi >= 30 and rsi < 30: return ('clear_all', 0.8, '③套利空: RSI至30, 清空剩余')
            if dea > macd_threshold: return ('clear_all', 0.9, '③套利空: MACD上破+阈值, 趋势反转出清')
        return ('wait', 0.3, '③混沌期观望')
    
    # ── Phase 1: 三维共振 ──
    if (dea > 0 and prev_dea <= 0 and sar_trend == 1 and price > ema144 and
        rsi > 60 and total_long == 0):
        return ('entry_long_4', 0.95, '①三维共振做多: 价格>EMA144+SAR翻多+DEA>0+RSI>60 → 底仓4份')
    if (dea < 0 and prev_dea >= 0 and sar_trend == -1 and price < ema144 and
        rsi < 40 and total_short == 0):
        return ('entry_short_4', 0.95, '①三维共振做空: 价格<EMA144+SAR翻空+DEA<0+RSI<40 → 底仓4份')
    if has_long_base and dea <= 0:
        return ('cut_half', 0.8, '①底仓: MACD跌破0轴, 减半/清仓')
    if has_short_base and dea >= 0:
        return ('cut_half', 0.8, '①底仓: MACD上穿0轴, 减半/清仓')
    return ('wait', 0.2, f'{phase}: 观望')


def analyze(df, config=None):
    """
    对OHLCV数据进行完整分析
    
    config: 自定义参数 dict
        - ema_period: EMA周期 (default 144)
        - macd_fast, macd_slow, macd_signal: MACD参数 (default 20,52,2)
        - rsi_period: RSI周期 (default 14)
        - sar_step, sar_max: SAR参数 (default 0.02, 0.2)
        - macd_threshold: MACD阈值 (default 6.5)
        - bb_mult_trend: 布林带趋势带倍数 (default 1.5)
        - bb_mult_extreme: 布林带极端带倍数 (default 3.0)
        - atr_period: ATR周期 (default 14)
    """
    if config is None:
        config = {}
    
    ema_period = config.get('ema_period', 144)
    macd_fast = config.get('macd_fast', 20)
    macd_slow = config.get('macd_slow', 52)
    macd_signal_period = config.get('macd_signal', 2)
    rsi_period = config.get('rsi_period', 14)
    sar_step = config.get('sar_step', 0.02)
    sar_max = config.get('sar_max', 0.2)
    macd_threshold = config.get('macd_threshold', 6.5)
    bb_mult_trend = config.get('bb_mult_trend', 1.5)
    bb_mult_extreme = config.get('bb_mult_extreme', 3.0)
    atr_period = config.get('atr_period', 14)
    
    close = df['close']
    high = df['high']
    low = df['low']
    
    df['ema144'] = calc_ema144(close, ema_period)
    df['dif'], df['dea'], df['macd_hist'] = calc_macd(close, macd_fast, macd_slow, macd_signal_period)
    df['rsi'] = calc_rsi(close, rsi_period)
    df['sar'], df['sar_trend'] = calc_sar(high, low, sar_step, sar_max)
    
    # 布林带 (中轨=EMA)
    bb_ema, bb_upper_trend, bb_lower_trend, bb_upper_extreme, bb_lower_extreme, bb_std = \
        calc_bollinger(close, ema_period, bb_mult_trend, bb_mult_extreme)
    df['bb_upper_trend'] = bb_upper_trend
    df['bb_lower_trend'] = bb_lower_trend
    df['bb_upper_extreme'] = bb_upper_extreme
    df['bb_lower_extreme'] = bb_lower_extreme
    df['bb_std'] = bb_std
    
    # ATR
    df['atr'] = calc_atr(high, low, close, atr_period)
    
    df['prev_close'] = df['close'].shift(1)
    df['prev_dea'] = df['dea'].shift(1)
    df['prev_rsi'] = df['rsi'].shift(1)
    df['sar_prev_trend'] = df['sar_trend'].shift(1)
    df['sar_flip'] = (df['sar_trend'] != df['sar_prev_trend']) & (df['sar_trend'] != 0)
    df.loc[df.index[0], 'sar_flip'] = False
    df['macd_threshold'] = macd_threshold
    df['bb_mult_trend'] = bb_mult_trend
    df['bb_mult_extreme'] = bb_mult_extreme
    
    df['macd_state'] = df['dea'].apply(lambda x: get_macd_state(x, macd_threshold))
    df['rsi_state'] = df['rsi'].apply(get_rsi_state)
    df['phase'] = df['dea'].apply(lambda x: detect_phase(x, macd_threshold))
    
    df = _simulate_positions(df, macd_threshold)
    
    signals = df.apply(detect_signal, axis=1)
    df['signal_type'] = [s[0] for s in signals]
    df['signal_confidence'] = [s[1] for s in signals]
    df['signal_desc'] = [s[2] for s in signals]
    
    return df


def _simulate_positions(df, macd_threshold=6.5):
    has_long_base = has_short_base = has_long_addon = has_short_addon = False
    has_arb_long = has_arb_short = False
    
    long_base_list = []; short_base_list = []; long_addon_list = []; short_addon_list = []
    arb_long_list = []; arb_short_list = []
    
    for i, row in df.iterrows():
        sig = row.get('signal_type', 'wait')
        if sig == 'entry_long_4': has_long_base = True; has_short_base = False; has_arb_long = False; has_arb_short = False
        elif sig == 'entry_short_4': has_short_base = True; has_long_base = False; has_arb_long = False; has_arb_short = False
        elif sig == 'add_long_4': has_long_addon = True
        elif sig == 'add_short_4': has_short_addon = True
        elif sig == 'arb_long_4': has_arb_long = True
        elif sig == 'arb_short_4': has_arb_short = True
        elif sig == 'cut_half':
            if has_long_addon: has_long_addon = False
            elif has_arb_long: has_arb_long = False
            elif has_long_base: has_long_base = False
            elif has_short_addon: has_short_addon = False
            elif has_arb_short: has_arb_short = False
            elif has_short_base: has_short_base = False
        elif sig == 'clear_addons': has_long_addon = False; has_short_addon = False
        elif sig == 'clear_all': has_long_base = False; has_short_base = False; has_long_addon = False; has_short_addon = False; has_arb_long = False; has_arb_short = False
        elif sig == 'restore_long': has_long_addon = True
        elif sig == 'restore_short': has_short_addon = True
        elif sig == 'convert_to_base': has_arb_long = False; has_long_base = True
        
        long_base_list.append(has_long_base); short_base_list.append(has_short_base)
        long_addon_list.append(has_long_addon); short_addon_list.append(has_short_addon)
        arb_long_list.append(has_arb_long); arb_short_list.append(has_arb_short)
    
    df['has_long_base'] = long_base_list; df['has_short_base'] = short_base_list
    df['has_long_addon'] = long_addon_list; df['has_short_addon'] = short_addon_list
    df['has_arb_long'] = arb_long_list; df['has_arb_short'] = arb_short_list
    df['total_long'] = [sum(1 for x in [lb, la, al] if x) for lb, la, al in zip(long_base_list, long_addon_list, arb_long_list)]
    df['total_short'] = [sum(1 for x in [sb, sa, as_] if x) for sb, sa, as_ in zip(short_base_list, short_addon_list, arb_short_list)]
    return df


def get_latest_state(df):
    if df.empty: return {}
    row = df.iloc[-1]
    return {
        'date': str(row.get('date', '')), 'close': float(row.get('close', 0)),
        'ema144': float(row.get('ema144', 0)), 'dea': float(row.get('dea', 0)),
        'dif': float(row.get('dif', 0)), 'rsi': float(row.get('rsi', 50)),
        'sar': float(row.get('sar', 0)), 'sar_trend': int(row.get('sar_trend', 0)),
        'sar_flip': bool(row.get('sar_flip', False)),
        'macd_state': str(row.get('macd_state', '')), 'rsi_state': str(row.get('rsi_state', '')),
        'phase': str(row.get('phase', 'unknown')),
        'signal_type': str(row.get('signal_type', 'wait')),
        'signal_confidence': float(row.get('signal_confidence', 0)),
        'signal_desc': str(row.get('signal_desc', '')),
        'macd_hist': float(row.get('macd_hist', 0)),
    }
