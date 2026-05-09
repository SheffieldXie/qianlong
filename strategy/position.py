"""
资金管理: The Citadel (共12份) — 严格按PDF

PDF Page 6 仓位系统:
阶段        仓位结构    说明
③套利期      4份        区间震荡, 轻仓套利
①起势期      4份        底仓确立, 保守持有
②强势期      4份        趋势火上浇油
总计        12份       全周期最大敞口上限

所有仓位均有独立的止损与减仓条件。
若趋势演进顺利: ③→①→②的仓位可连锁形成10份整体趋势持仓。
若趋势夭折或暴毙: SAR翻号 → 无条件清空。
"""


class PositionManager:
    """12份仓位管理器 — 严格按PDF"""
    
    MAX_UNITS = 12
    PHASE3_UNITS = 4    # ③ 套利期
    PHASE1_UNITS = 4    # ① 起势期底仓
    PHASE2_UNITS = 4    # ② 强势期加仓
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        # 12 units: 0=空, 1=多头, -1=空头
        self.units = [0] * self.MAX_UNITS
        # 分类
        # units[0:4]   = ③套利仓 + ①底仓 (蓝区)
        # units[4:8]   = ②加仓1 (金区)
        # units[8:12]  = ②加仓2 (金区)
        self.unit_type = [''] * self.MAX_UNITS  # 'arb'/'base'/'addon'/'empty'
        self.entry_prices = [0.0] * self.MAX_UNITS
        self.trades = []
        self.daily_pnl = 0
        self.consecutive_losses = 0
    
    def get_long_units(self):
        return sum(1 for u in self.units if u == 1)
    
    def get_short_units(self):
        return sum(1 for u in self.units if u == -1)
    
    def get_total_exposure(self):
        return sum(1 for u in self.units if u != 0)
    
    def get_arb_units(self, direction=1):
        """③套利仓 (units 0-3)"""
        return sum(1 for u in self.units[:4] if u == direction)
    
    def get_base_units(self, direction=1):
        """①底仓 (units 0-3)"""
        return sum(1 for u in self.units[:4] if u == direction)
    
    def get_addon_units(self, direction=1):
        """②加仓 (units 4-11)"""
        return sum(1 for u in self.units[4:] if u == direction)
    
    def execute_signal(self, signal_type, price, date=""):
        """
        执行信号 — 严格按PDF规则
        
        PDF规则映射:
        - entry_long_4: ①多维共振 → 建立多头底仓4份
        - entry_short_4: ①多维共振 → 建立空头底仓4份
        - add_long_4: ②MACD>+6.5 → 加仓4份
        - add_short_4: ②MACD<-6.5 → 加仓4份
        - arb_long_4: ③RSI≤30 → 套利做多4份
        - arb_short_4: ③RSI≥70 → 套利做空4份
        - cut_half: 减半仓
        - clear_addons: 清空加仓保留底仓
        - clear_all: 无条件清仓 (SAR翻转)
        - restore_long/short: 回补被减仓位
        """
        action = "观望"
        
        if signal_type == 'clear_all':
            count = self.get_total_exposure()
            self._close_all(price, date)
            action = f"清仓: 平{count}份 @ {price:.2f} — SAR翻转, 无条件执行"
        
        elif signal_type == 'entry_long_4':
            # ①建立多头底仓: 占蓝区4份
            if self.get_total_exposure() == 0:
                self._buy_range(0, 4, price, 'base', date)
                action = f"①建仓: 买4份底仓(蓝区) @ {price:.2f}"
            elif self.get_long_units() == 0:
                # 先清空空头
                self._close_all(price, date)
                self._buy_range(0, 4, price, 'base', date)
                action = f"①反转做多: 买4份底仓 @ {price:.2f}"
        
        elif signal_type == 'entry_short_4':
            if self.get_total_exposure() == 0:
                self._sell_range(0, 4, price, 'base', date)
                action = f"①建仓: 卖4份底仓(蓝区) @ {price:.2f}"
            elif self.get_short_units() == 0:
                self._close_all(price, date)
                self._sell_range(0, 4, price, 'base', date)
                action = f"①反转做空: 卖4份底仓 @ {price:.2f}"
        
        elif signal_type == 'arb_long_4':
            # ③套利做多
            available = self.PHASE3_UNITS - self.get_arb_units(1)
            if available > 0 and self.get_short_units() == 0:
                start = 4 - self.get_arb_units(1) - available
                self._buy_range(start, start + available, price, 'arb', date)
                action = f"③套利: 买{available}份多 @ {price:.2f}"
        
        elif signal_type == 'arb_short_4':
            available = self.PHASE3_UNITS - self.get_arb_units(-1)
            if available > 0 and self.get_long_units() == 0:
                start = 4 - self.get_arb_units(-1) - available
                self._sell_range(start, start + available, price, 'arb', date)
                action = f"③套利: 卖{available}份空 @ {price:.2f}"
        
        elif signal_type == 'add_long_4':
            # ②趋势加仓: 占金区(4-11)
            current_addon = self.get_addon_units(1)
            available = self.PHASE2_UNITS - current_addon
            if available > 0 and self.get_long_units() > 0:
                start_idx = 4 + current_addon
                count = min(available, 4)
                self._buy_range(start_idx, start_idx + count, price, 'addon', date)
                action = f"②加仓: 买{count}份(金区) @ {price:.2f} — 火上浇油"
        
        elif signal_type == 'add_short_4':
            current_addon = self.get_addon_units(-1)
            available = self.PHASE2_UNITS - current_addon
            if available > 0 and self.get_short_units() > 0:
                start_idx = 4 + current_addon
                count = min(available, 4)
                self._sell_range(start_idx, start_idx + count, price, 'addon', date)
                action = f"②加仓: 卖{count}份(金区) @ {price:.2f} — 火上浇油"
        
        elif signal_type == 'cut_half':
            # 减半: 从顶部开始平
            half = max(1, self.get_total_exposure() // 2)
            if self.get_long_units() > self.get_short_units():
                self._sell_from_top(half, price, date)
                action = f"减半: 平{half}份多 @ {price:.2f}"
            else:
                self._buy_from_top(half, price, date)
                action = f"减半: 平{half}份空 @ {price:.2f}"
        
        elif signal_type == 'clear_addons':
            # 清空加仓(金区), 保留底仓(蓝区)
            addon_count = self.get_addon_units(1) + self.get_addon_units(-1)
            if addon_count > 0:
                # 平掉所有金区仓位
                for i in range(4, self.MAX_UNITS):
                    if self.units[i] != 0:
                        self._close_unit(i, price, date)
                action = f"清除加仓: 平{addon_count}份(金区), 保留底仓 @ {price:.2f}"
        
        elif signal_type == 'restore_long':
            # 回补多头加仓
            available = self.PHASE2_UNITS - self.get_addon_units(1)
            if available > 0 and self.get_long_units() > 0:
                count = min(available, 4)
                start_idx = 4 + self.get_addon_units(1)
                self._buy_range(start_idx, start_idx + count, price, 'addon', date)
                action = f"回补: 买{count}份(金区) @ {price:.2f}"
        
        elif signal_type == 'restore_short':
            available = self.PHASE2_UNITS - self.get_addon_units(-1)
            if available > 0 and self.get_short_units() > 0:
                count = min(available, 4)
                start_idx = 4 + self.get_addon_units(-1)
                self._sell_range(start_idx, start_idx + count, price, 'addon', date)
                action = f"回补: 卖{count}份(金区) @ {price:.2f}"
        
        return action
    
    def _buy_range(self, start, end, price, utype, date):
        for i in range(start, min(end, self.MAX_UNITS)):
            if self.units[i] == 0:
                self.units[i] = 1
                self.unit_type[i] = utype
                self.entry_prices[i] = price
                self.trades.append({'date': date, 'action': 'BUY', 'unit': i+1, 'price': price, 'type': utype})
    
    def _sell_range(self, start, end, price, utype, date):
        for i in range(start, min(end, self.MAX_UNITS)):
            if self.units[i] == 0:
                self.units[i] = -1
                self.unit_type[i] = utype
                self.entry_prices[i] = price
                self.trades.append({'date': date, 'action': 'SELL', 'unit': i+1, 'price': price, 'type': utype})
    
    def _sell_from_top(self, count, price, date):
        for i in range(self.MAX_UNITS - 1, -1, -1):
            if count <= 0: break
            if self.units[i] == 1:
                self._close_unit(i, price, date)
                count -= 1
    
    def _buy_from_top(self, count, price, date):
        for i in range(self.MAX_UNITS - 1, -1, -1):
            if count <= 0: break
            if self.units[i] == -1:
                self._close_unit(i, price, date)
                count -= 1
    
    def _close_unit(self, idx, price, date):
        self.trades.append({
            'date': date, 'action': 'CLOSE',
            'unit': idx+1, 'price': price,
            'type': self.unit_type[idx],
            'pnl': (price - self.entry_prices[idx]) if self.units[idx] == 1 else (self.entry_prices[idx] - price),
        })
        self.units[idx] = 0
        self.unit_type[idx] = 'empty'
        self.entry_prices[idx] = 0
    
    def _close_all(self, price, date):
        for i in range(self.MAX_UNITS):
            if self.units[i] != 0:
                self._close_unit(i, price, date)
    
    def get_unrealized_pnl(self, current_price):
        pnl = 0
        for i in range(self.MAX_UNITS):
            if self.units[i] == 1:
                pnl += current_price - self.entry_prices[i]
            elif self.units[i] == -1:
                pnl += self.entry_prices[i] - current_price
        return pnl
    
    def get_state(self, current_price):
        return {
            'total_units': self.get_total_exposure(),
            'long_units': self.get_long_units(),
            'short_units': self.get_short_units(),
            'base_units': self.get_base_units(1) + self.get_base_units(-1),
            'addon_units': self.get_addon_units(1) + self.get_addon_units(-1),
            'arb_units': self.get_arb_units(1) + self.get_arb_units(-1),
            'direction': self.get_long_units() - self.get_short_units(),
            'unrealized_pnl': self.get_unrealized_pnl(current_price),
            'consecutive_losses': self.consecutive_losses,
            'unit_details': [
                {
                    'index': i,
                    'position': 'long' if u == 1 else ('short' if u == -1 else 'empty'),
                    'type': self.unit_type[i],
                    'entry_price': self.entry_prices[i] if u != 0 else 0,
                    'pnl': (current_price - self.entry_prices[i]) if u == 1 else ((self.entry_prices[i] - current_price) if u == -1 else 0),
                }
                for i, u in enumerate(self.units)
            ],
            'recent_trades': self.trades[-15:],
        }
