"""
风控守则: The Kill Switch (铁血液则)

PPT严格设定:
- Rule 1: 单日净亏损 > 5% → 强制停盘 (24h冷却)
- Rule 2: 连续3次止损 → 停盘复盘
- Rule 3: 重大新闻前1小时 → 自动减仓至3/12
- Rule 4: K线收盘确认原则 (不提前抢跑)
"""

import datetime


class RiskManager:
    """乾六爻风控管理器"""
    
    MAX_DAILY_LOSS_PCT = 0.05      # 5%
    MAX_CONSECUTIVE_LOSSES = 3      # 3次连续止损
    NEWS_REDUCE_POSITION = 3        # 新闻前减仓到3份
    NEWS_HOURS_BEFORE = 1           # 新闻前1小时
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.start_equity = 0
        self.current_equity = 0
        self.daily_pnl = 0
        self.consecutive_losses = 0
        self.cooldown_until = None  # 冷却截止时间
        self.is_cooling = False
        self.news_event_time = None  # 下次重大新闻时间
    
    def set_equity(self, equity):
        if self.start_equity == 0:
            self.start_equity = equity
        self.current_equity = equity
        self.daily_pnl = equity - self.start_equity
    
    def check_kill_switch(self):
        """
        检查Kill Switch
        
        返回: (is_blocked, reason)
        """
        # 冷却期检查
        if self.is_cooling:
            if self.cooldown_until and datetime.datetime.now() > self.cooldown_until:
                self.is_cooling = False
                self.cooldown_until = None
                return (False, '')
            else:
                return (True, f"冷却期: 至 {self.cooldown_until}")
        
        # Rule 1: 单日净亏损 > 5%
        if self.start_equity > 0:
            daily_loss_pct = self.daily_pnl / self.start_equity
            if daily_loss_pct < -self.MAX_DAILY_LOSS_PCT:
                self.is_cooling = True
                self.cooldown_until = datetime.datetime.now() + datetime.timedelta(hours=24)
                return (True, f"Rule 1: 日亏损{daily_loss_pct:.1%} > 5%, 24h冷却")
        
        # Rule 2: 连续3次止损
        if self.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            self.is_cooling = True
            self.cooldown_until = datetime.datetime.now() + datetime.timedelta(hours=24)
            return (True, f"Rule 2: 连续{self.consecutive_losses}次止损, 停盘复盘")
        
        return (False, '')
    
    def check_news_event(self):
        """
        Rule 3: 重大新闻前1小时
        
        返回: 是否需要减仓 (bool)
        """
        if self.news_event_time:
            time_left = self.news_event_time - datetime.datetime.now()
            if 0 < time_left.total_seconds() < self.NEWS_HOURS_BEFORE * 3600:
                return True
        return False
    
    def record_loss(self):
        """记录一次止损"""
        self.consecutive_losses += 1
    
    def record_win(self):
        """记录一次盈利, 重置连续止损"""
        self.consecutive_losses = 0
    
    def get_status(self):
        """获取风控状态"""
        daily_loss_pct = self.daily_pnl / self.start_equity if self.start_equity > 0 else 0
        
        return {
            'is_cooling': self.is_cooling,
            'cooldown_until': str(self.cooldown_until) if self.cooldown_until else None,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': daily_loss_pct,
            'consecutive_losses': self.consecutive_losses,
            'max_daily_loss_pct': self.MAX_DAILY_LOSS_PCT,
            'max_consecutive_losses': self.MAX_CONSECUTIVE_LOSSES,
            'news_reduce': self.check_news_event(),
            'start_equity': self.start_equity,
            'current_equity': self.current_equity,
        }
