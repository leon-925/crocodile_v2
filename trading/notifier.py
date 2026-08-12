"""Notifier — 告警推送系统

支持多渠道推送：控制台 / 文件 / Webhook / 邮件。
可扩展 Telegram / 微信 / 钉钉。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── 抽象基类 ────────────────────────────────────

class Notifier(ABC):
    """通知器抽象基类"""

    @abstractmethod
    def send(self, title: str, message: str, level: str = "info") -> bool:
        """发送通知

        level: info | warning | error | trade
        """
        ...


# ── 内置实现 ────────────────────────────────────

class ConsoleNotifier(Notifier):
    """控制台打印通知"""

    def __init__(self, timestamp: bool = True):
        self.timestamp = timestamp
        self._emojis = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "trade": "📊"}

    def send(self, title: str, message: str, level: str = "info") -> bool:
        emoji = self._emojis.get(level, "")
        ts = f"[{datetime.now().strftime('%H:%M:%S')}] " if self.timestamp else ""
        print(f"{ts}{emoji} {title}")
        if message:
            print(f"   {message}")
        return True


class FileNotifier(Notifier):
    """文件日志通知"""

    def __init__(self, log_path: str = "trading.log"):
        self.log_path = Path(log_path)

    def send(self, title: str, message: str, level: str = "info") -> bool:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            ts = datetime.now().isoformat()
            f.write(f"[{ts}] [{level.upper()}] {title}\n")
            if message:
                for line in message.split("\n"):
                    f.write(f"  {line}\n")
            f.write("\n")
        return True


class WebhookNotifier(Notifier):
    """Webhook 推送（企业微信/钉钉/Slack 等）"""

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}

    def send(self, title: str, message: str, level: str = "info") -> bool:
        try:
            import requests
            payload = {
                "title": title,
                "text": message,
                "level": level,
                "timestamp": datetime.now().isoformat(),
            }
            resp = requests.post(self.url, json=payload, headers=self.headers, timeout=10)
            return resp.status_code < 400
        except ImportError:
            return False
        except Exception:
            return False


# ── 组合通知器 ──────────────────────────────────

class MultiNotifier(Notifier):
    """多通道同时推送"""

    def __init__(self, *notifiers: Notifier):
        self.notifiers = list(notifiers) or [ConsoleNotifier()]

    def add(self, notifier: Notifier) -> "MultiNotifier":
        self.notifiers.append(notifier)
        return self

    def send(self, title: str, message: str, level: str = "info") -> bool:
        ok = True
        for n in self.notifiers:
            try:
                if not n.send(title, message, level):
                    ok = False
            except Exception:
                ok = False
        return ok


# ── 快捷创建 ─────────────────────────────────────

def create_notifier(
    console: bool = True,
    log_file: Optional[str] = "trading.log",
    webhook_url: Optional[str] = None,
) -> Notifier:
    """一行创建通知器

    notifier = create_notifier(console=True, log_file="robot.log", webhook_url="https://...")
    """
    parts: List[Notifier] = []
    if console:
        parts.append(ConsoleNotifier())
    if log_file:
        parts.append(FileNotifier(log_file))
    if webhook_url:
        parts.append(WebhookNotifier(webhook_url))
    return MultiNotifier(*parts)
