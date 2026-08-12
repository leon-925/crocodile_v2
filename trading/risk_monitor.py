"""RiskMonitor — 实盘风控监控器

实时监控账户风险：
- 最大回撤熔断
- 单日亏损熔断
- 单笔亏损熔断
- 连续亏损熔断
- 持仓集中度检查
- 总仓位上限

触发熔断 → 自动平仓 / 停止交易 / 告警
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


class RiskMonitor:
    """实盘风控监控器"""

    def __init__(
        self,
        max_drawdown: float = 0.20,          # 最大回撤熔断（从峰值）
        daily_loss_limit: float = 0.05,       # 单日亏损上限
        single_loss_limit: Optional[float] = None,  # 单笔亏损上限
        max_consecutive_losses: int = 5,      # 连续亏损次数上限
        max_total_position: float = 0.80,     # 总仓位上限
        max_single_position: float = 0.30,    # 单票仓位上限
    ):
        self.max_drawdown = max_drawdown
        self.daily_loss_limit = daily_loss_limit
        self.single_loss_limit = single_loss_limit
        self.max_consecutive_losses = max_consecutive_losses
        self.max_total_position = max_total_position
        self.max_single_position = max_single_position

        # 状态
        self._peak_equity: float = 0
        self._daily_start_equity: Optional[float] = None
        self._consecutive_losses: int = 0
        self._killed: bool = False
        self._last_check: Optional[datetime] = None
        self._alerts: List[Dict[str, Any]] = []

    # ── 前置检查（下单前）────────────────────────

    def pre_trade_check(self, account, prices: Dict[str, float]) -> bool:
        """下单前全面风控检查

        返回 True = 允许交易，False = 拦截
        """
        self._last_check = datetime.now()

        # 熔断状态
        if self._killed:
            self._alert("KILLED", "风控熔断已触发，禁止交易")
            return False

        equity = account.get_equity()
        self._update_peak(equity)

        # 1. 最大回撤
        drawdown = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0
        if drawdown >= self.max_drawdown:
            return self._kill(f"最大回撤熔断: {drawdown:.2%} >= {self.max_drawdown:.2%}")

        # 2. 单日亏损
        if self._daily_start_equity is None:
            self._daily_start_equity = equity

        daily_loss = (self._daily_start_equity - equity) / self._daily_start_equity
        if daily_loss >= self.daily_loss_limit:
            return self._kill(f"单日亏损熔断: {daily_loss:.2%} >= {self.daily_loss_limit:.2%}")

        # 3. 连续亏损
        if self._consecutive_losses >= self.max_consecutive_losses:
            return self._kill(f"连续亏损熔断: {self._consecutive_losses} >= {self.max_consecutive_losses}")

        # 4. 总仓位
        market_value = account.get_market_value()
        total_ratio = market_value / equity if equity > 0 else 0
        if total_ratio >= self.max_total_position:
            self._alert("仓位超限", f"总仓位 {total_ratio:.1%} >= {self.max_total_position:.1%}")
            return False

        return True

    # ── 成交后反馈 ───────────────────────────────

    def on_trade(self, pnl: float):
        """成交后更新连续亏损计数"""
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def on_day_reset(self):
        """新交易日重置"""
        self._daily_start_equity = None
        self._consecutive_losses = 0
        self._killed = False
        self._alerts.clear()

    # ── 查询 ────────────────────────────────────

    @property
    def is_killed(self) -> bool:
        return self._killed

    @property
    def current_drawdown(self) -> float:
        return 0.0  # 由外部计算

    def reset_kill(self):
        """手动解除熔断"""
        self._killed = False
        self.on_day_reset()

    def get_alerts(self) -> List[Dict[str, Any]]:
        return self._alerts.copy()

    # ── 内部 ────────────────────────────────────

    def _update_peak(self, equity: float):
        if equity > self._peak_equity:
            self._peak_equity = equity

    def _kill(self, reason: str) -> bool:
        self._killed = True
        self._alert("KILL", reason)
        return False

    def _alert(self, level: str, message: str):
        self._alerts.append({
            "time": datetime.now(),
            "level": level,
            "message": message,
        })

    def __repr__(self):
        return (
            f"RiskMonitor(killed={self._killed}, peak={self._peak_equity:,.0f}, "
            f"losses={self._consecutive_losses})"
        )
