"""TradingRobot — 自动交易脑

Crocodile v2 的核心自动驾驶模块。串联所有组件执行完整的实盘交易循环：

行情 → 指标 → 策略 → 调仓 → 下单 → 成交 → 风控 → 告警

用法:
    robot = TradingRobot(
        data_source=ds,
        account=acc,
        broker=broker,
        strategy=strat,
        portfolio_manager=pm,
        notifier=notifier,
    )
    robot.run_loop(symbols=['600519.SH'], interval=60)  # 每60秒一轮
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, time as dtime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import pandas as pd


class RobotState(Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class TradingRobot:
    """自动交易机器人 — 全链路自动化"""

    def __init__(
        self,
        data_source=None,
        account=None,
        broker=None,
        strategy=None,
        portfolio_manager=None,
        risk_monitor=None,
        notifier=None,
        indicators_fn: Optional[Callable] = None,
        trade_log_path: Optional[str] = None,
    ):
        self.data_source = data_source
        self.account = account
        self.broker = broker
        self.strategy = strategy
        self.portfolio_manager = portfolio_manager
        self.risk_monitor = risk_monitor
        self.notifier = notifier
        self.indicators_fn = indicators_fn

        self.state = RobotState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 统计
        self.rounds: int = 0
        self.trades_today: int = 0
        self.start_time: Optional[datetime] = None
        self.last_round_time: Optional[datetime] = None
        self.errors: List[Dict[str, Any]] = []

        # 交易日时间窗口
        self.market_open = dtime(9, 30)
        self.market_close = dtime(15, 0)

        # 回调 hooks
        self.on_signal: Optional[Callable] = None
        self.on_order: Optional[Callable] = None
        self.on_fill: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_round: Optional[Callable] = None

    # ── 主循环 ──────────────────────────────────

    def run_loop(
        self,
        symbols: List[str],
        interval: float = 60.0,
        only_market_hours: bool = False,
        max_rounds: Optional[int] = None,
    ):
        """启动交易主循环（阻塞当前线程）

        参数:
            symbols: 交易标的列表
            interval: 轮询间隔（秒）
            only_market_hours: 是否只在交易时段运行
            max_rounds: 最大轮次（None=无限）
        """
        if self.state == RobotState.RUNNING:
            return

        self.state = RobotState.RUNNING
        self.start_time = datetime.now()
        self._stop_event.clear()

        self._notify("🤖 Trading Robot 启动", f"标的: {symbols}\n间隔: {interval}s")

        round_num = 0
        while not self._stop_event.is_set():
            if max_rounds and round_num >= max_rounds:
                break

            # 交易日检查
            if only_market_hours and not self._is_market_hours():
                time.sleep(30)
                continue

            # 暂停检查
            if self.state == RobotState.PAUSED:
                time.sleep(1)
                continue

            try:
                self._execute_round(symbols)
                round_num += 1
                self.rounds = round_num
                self.last_round_time = datetime.now()

                if self.on_round:
                    self.on_round(round_num, self.last_round_time)

            except Exception as e:
                self.errors.append({
                    "round": round_num,
                    "time": datetime.now(),
                    "error": str(e),
                })
                if self.on_error:
                    self.on_error(e)
                self._notify("⚠️ 交易轮次异常", str(e))

            self._stop_event.wait(interval)

        self.state = RobotState.STOPPED
        self._notify("🛑 Trading Robot 停止",
            f"运行轮次: {round_num}\n错误数: {len(self.errors)}")

    def run_async(
        self,
        symbols: List[str],
        interval: float = 60.0,
        only_market_hours: bool = False,
        max_rounds: Optional[int] = None,
    ):
        """后台线程启动交易循环"""
        self._thread = threading.Thread(
            target=self.run_loop,
            args=(symbols,),
            kwargs={"interval": interval, "only_market_hours": only_market_hours, "max_rounds": max_rounds},
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        """停止交易循环"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def pause(self):
        self.state = RobotState.PAUSED

    def resume(self):
        if self.state == RobotState.PAUSED:
            self.state = RobotState.RUNNING

    # ── 单轮执行 ────────────────────────────────

    def _execute_round(self, symbols: List[str]):
        """执行一轮完整的交易循环"""
        now = datetime.now()

        # 1. 拉取实时行情
        prices = {}
        try:
            if self.data_source:
                prices = self.data_source.get_realtime_prices(symbols)
        except Exception:
            pass

        if not prices:
            return  # 无行情，跳过

        # 2. 更新 Account 行情
        self.account.update_market_prices(prices)

        # 3. 拉取历史 + 计算指标 + 生成信号
        df = self._get_data_with_indicators(symbols)
        if df is None or df.empty:
            return

        signal_df = self.strategy.generate_signal(df)
        current_signal = signal_df.iloc[-1].get("signal", 0)

        if self.on_signal:
            self.on_signal(current_signal, prices)

        # 4. 风控前置检查
        if self.risk_monitor:
            if not self.risk_monitor.pre_trade_check(self.account, prices):
                return  # 风控拦截

        # 5. 信号 → 调仓
        if current_signal != 0 and self.portfolio_manager:
            if current_signal == 1:
                # 买入: 设为单一标的的目标仓位
                target = {s: 0.3 for s in symbols}
            else:
                target = {s: 0.0 for s in symbols}
            self.portfolio_manager.set_target_weights(target)

            orders = self.portfolio_manager.rebalance(prices)

            # 6. 提交 → 撮合
            for order in orders:
                try:
                    oid = self.broker.submit_order(
                        order.symbol, order.side.value, order.quantity,
                        price=prices.get(order.symbol, 0),
                        order_type="limit",
                    )
                    if self.on_order:
                        self.on_order(order)
                except Exception as e:
                    self._notify("❌ 下单失败", f"{order.symbol} {order.side.value}: {e}")
                    continue

            # 撮合
            filled = self.broker.match_orders(prices)

            if filled and self.on_fill:
                for oid in filled:
                    order = self.broker.get_order(oid)
                    if order:
                        self.on_fill(order)

            if filled:
                self.trades_today += len(filled)
                self._notify("📊 成交", f"本轮成交 {len(filled)} 笔")

        # 7. 快照
        self.account.snapshot(time=now)

    def _get_data_with_indicators(self, symbols: List[str]) -> Optional[pd.DataFrame]:
        """获取历史数据并计算指标"""
        if self.data_source is None:
            return None

        try:
            df = self.data_source.get_history_batch(
                symbols,
                end_date=pd.Timestamp.now().date(),
            )
            if df.empty:
                return None

            if self.indicators_fn:
                df = self.indicators_fn(df)
            return df
        except Exception:
            return None

    # ── 交易日判断 ──────────────────────────────

    def _is_market_hours(self) -> bool:
        now = datetime.now()
        if now.weekday() >= 5:
            return False  # 周末
        return self.market_open <= now.time() <= self.market_close

    # ── 通知 ────────────────────────────────────

    def _notify(self, title: str, message: str):
        if self.notifier:
            try:
                self.notifier.send(title, message)
            except Exception:
                pass

    # ── 状态查询 ────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self.state == RobotState.RUNNING

    def status_report(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "rounds": self.rounds,
            "trades_today": self.trades_today,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S") if self.start_time else None,
            "last_round": self.last_round_time.strftime("%H:%M:%S") if self.last_round_time else None,
            "errors": len(self.errors),
            "account": str(self.account) if self.account else None,
        }

    def __repr__(self):
        s = self.status_report()
        return f"TradingRobot(state={s['state']}, rounds={s['rounds']}, trades={s['trades_today']}, errors={s['errors']})"
