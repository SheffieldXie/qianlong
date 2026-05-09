"""
模拟盘引擎 — 严格按乾六爻策略执行模拟交易

核心逻辑:
1. 接收已分析的历史数据(含所有信号)
2. 按信号执行交易, 记录每笔交易
3. 跟踪账户权益曲线
4. 计算回测指标
"""

import pandas as pd
import numpy as np


class PaperTradingEngine:
    """模拟盘引擎 — 严格遵循乾六爻交易规则"""
    
    def __init__(self, initial_capital=100000, contract_size=100):
        """
        参数:
        - initial_capital: 初始资金 (美元)
        - contract_size: 每份合约大小 (XAU/USD 通常1手=100盎司)
        """
        self.initial_capital = initial_capital
        self.contract_size = contract_size
        
        self.reset()
    
    def reset(self):
        self.equity = self.initial_capital
        self.cash = self.initial_capital
        self.positions = []  # list of {units, direction, entry_price, entry_date, type}
        self.trades = []     # closed trades
        self.equity_curve = []  # (date, equity, cash, position_value)
        self.daily_returns = []
        
    def run(self, df):
        """
        完整模拟盘运行
        
        df: 已分析的数据, 包含 signal_type, signal_desc, close, high, low, date
        """
        self.reset()
        
        for i, row in df.iterrows():
            signal = row.get('signal_type', 'wait')
            price = row['close']
            high = row.get('high', price)
            low = row.get('low', price)
            date = str(row.get('date', ''))
            
            # 先检查持仓止损 (SAR翻转已经在信号中处理)
            # 执行信号
            if signal != 'wait':
                self._execute_signal(signal, price, high, low, date, row)
            
            # 计算当前权益
            pos_value = self._calc_position_value(price)
            current_equity = self.cash + pos_value
            
            self.equity_curve.append({
                'date': date,
                'equity': round(current_equity, 2),
                'cash': round(self.cash, 2),
                'position_value': round(pos_value, 2),
                'total_units': len(self.positions),
            })
            
            # 日收益率
            if len(self.equity_curve) > 1:
                prev_equity = self.equity_curve[-2]['equity']
                if prev_equity > 0:
                    daily_ret = (current_equity - prev_equity) / prev_equity
                    self.daily_returns.append(daily_ret)
        
        return self._generate_report()
    
    def _execute_signal(self, signal, price, high, low, date, row):
        """执行交易信号"""
        
        if signal == 'entry_long_4':
            # 清掉空头, 建立多头底仓
            self._close_all_positions(price, date, 'SIGNAL_ENTRY_LONG')
            self._open_positions(4, 1, price, date, 'base')
        
        elif signal == 'entry_short_4':
            self._close_all_positions(price, date, 'SIGNAL_ENTRY_SHORT')
            self._open_positions(4, -1, price, date, 'base')
        
        elif signal == 'arb_long_4':
            self._open_positions(4, 1, price, date, 'arb')
        
        elif signal == 'arb_short_4':
            self._open_positions(4, -1, price, date, 'arb')
        
        elif signal == 'add_long_4':
            # 检查是否有多头底仓
            if any(p['direction'] == 1 for p in self.positions):
                self._open_positions(4, 1, price, date, 'addon')
        
        elif signal == 'add_short_4':
            if any(p['direction'] == -1 for p in self.positions):
                self._open_positions(4, -1, price, date, 'addon')
        
        elif signal == 'cut_half':
            # 减半: 平掉一半仓位
            half = max(1, len(self.positions) // 2)
            self._close_positions(half, price, date, signal)
        
        elif signal == 'clear_addons':
            # 只平掉加仓部分
            addons = [p for p in self.positions if p['type'] == 'addon']
            for _ in range(len(addons)):
                self._close_one_position(price, date, signal)
        
        elif signal == 'clear_all':
            self._close_all_positions(price, date, signal)
        
        elif signal == 'restore_long':
            if any(p['direction'] == 1 and p['type'] != 'addon' for p in self.positions):
                self._open_positions(4, 1, price, date, 'addon')
        
        elif signal == 'restore_short':
            if any(p['direction'] == -1 and p['type'] != 'addon' for p in self.positions):
                self._open_positions(4, -1, price, date, 'addon')
    
    def _open_positions(self, count, direction, price, date, ptype):
        """开仓"""
        margin = count * self.contract_size * price
        if margin > self.cash * 0.9:  # 最多用90%资金
            available_units = int(self.cash * 0.9 / (self.contract_size * price))
            count = max(1, available_units)
        
        for _ in range(count):
            self.positions.append({
                'direction': direction,
                'entry_price': price,
                'entry_date': date,
                'type': ptype,
                'units': 1,
            })
        
        self.trades.append({
            'date': date,
            'action': 'OPEN' if direction == 1 else 'OPEN_SHORT',
            'price': price,
            'count': count,
            'direction': direction,
            'type': ptype,
            'value': count * self.contract_size * price,
        })
    
    def _close_one_position(self, price, date, reason):
        """平掉一个仓位"""
        if not self.positions:
            return
        
        # 优先平掉加仓, 再平套利, 最后平底仓
        close_idx = -1
        for i in range(len(self.positions) - 1, -1, -1):
            if self.positions[i]['type'] == 'addon':
                close_idx = i
                break
        if close_idx < 0:
            for i in range(len(self.positions) - 1, -1, -1):
                if self.positions[i]['type'] == 'arb':
                    close_idx = i
                    break
        if close_idx < 0:
            close_idx = len(self.positions) - 1
        
        pos = self.positions.pop(close_idx)
        pnl = self._calc_pnl(pos, price)
        
        self.cash += pnl
        
        self.trades.append({
            'date': date,
            'action': 'CLOSE',
            'price': price,
            'direction': pos['direction'],
            'type': pos['type'],
            'entry_price': pos['entry_price'],
            'pnl': round(pnl, 2),
            'reason': reason,
        })
    
    def _close_positions(self, count, price, date, reason):
        """平掉多个仓位"""
        for _ in range(min(count, len(self.positions))):
            self._close_one_position(price, date, reason)
    
    def _close_all_positions(self, price, date, reason):
        """清仓"""
        count = len(self.positions)
        for _ in range(count):
            self._close_one_position(price, date, reason)
    
    def _calc_pnl(self, position, exit_price):
        """计算单笔盈亏"""
        if position['direction'] == 1:
            return (exit_price - position['entry_price']) * self.contract_size
        else:
            return (position['entry_price'] - exit_price) * self.contract_size
    
    def _calc_position_value(self, current_price):
        """计算当前持仓价值"""
        value = 0
        for pos in self.positions:
            value += self._calc_pnl(pos, current_price)
        return value
    
    def _generate_report(self):
        """生成回测报告"""
        equity_df = pd.DataFrame(self.equity_curve)
        if equity_df.empty:
            return {}
        
        initial = self.initial_capital
        final = equity_df['equity'].iloc[-1]
        total_return = (final - initial) / initial
        
        n_days = len(equity_df)
        trading_days = n_days
        years = trading_days / 252
        if years > 0:
            annual_return = float((1 + total_return) ** (1 / years) - 1)
        else:
            annual_return = 0.0
        
        returns = equity_df['equity'].pct_change().dropna()
        daily_vol = returns.std()
        annual_vol = float(daily_vol * np.sqrt(252)) if daily_vol > 0 else 0.0
        sharpe = float((annual_return - 0.03) / annual_vol) if annual_vol > 0 else 0.0
        
        cummax = equity_df['equity'].cummax()
        drawdown = (equity_df['equity'] - cummax) / cummax
        max_drawdown = float(drawdown.min())
        
        closed_trades = [t for t in self.trades if 'pnl' in t]
        if closed_trades:
            wins = sum(1 for t in closed_trades if t['pnl'] > 0)
            win_rate = float(wins / len(closed_trades))
            avg_win = float(np.mean([t['pnl'] for t in closed_trades if t['pnl'] > 0])) if wins > 0 else 0
            avg_loss = float(abs(np.mean([t['pnl'] for t in closed_trades if t['pnl'] < 0]))) if len(closed_trades) - wins > 0 else 1.0
            profit_factor = float(avg_win / avg_loss) if avg_loss > 0 else 0
        else:
            win_rate = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            profit_factor = 0.0
        
        # Convert equity curve to native Python types
        equity_list = []
        for row in equity_df.itertuples():
            equity_list.append({
                'date': str(row.date),
                'equity': float(row.equity),
                'cash': float(row.cash),
                'position_value': float(row.position_value),
                'total_units': int(row.total_units),
            })
        
        # Convert trades to native Python types
        trades_list = []
        for t in self.trades:
            trade = {}
            for k, v in t.items():
                if isinstance(v, (np.integer,)):
                    trade[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    trade[k] = float(v)
                else:
                    trade[k] = v
            trades_list.append(trade)
        
        return {
            'metrics': {
                'initial_capital': int(initial),
                'final_equity': round(float(final), 2),
                'total_return': round(float(total_return), 4),
                'annual_return': round(annual_return, 4),
                'annual_volatility': round(annual_vol, 4),
                'sharpe_ratio': round(sharpe, 2),
                'max_drawdown': round(max_drawdown, 4),
                'win_rate': round(win_rate, 4),
                'profit_factor': round(profit_factor, 2),
                'total_trades': len(closed_trades),
                'n_days': n_days,
            },
            'equity_curve': equity_list,
            'trades': trades_list,
            'daily_returns': [float(r) for r in self.daily_returns],
        }
