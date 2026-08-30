"""Continuous Telemetry & Instant Alert Dispatcher (Phase 3.3).

Dispatches structured trade entry, fill, cycle settlement, circuit breaker,
and forward validation alerts to Discord/Telegram webhooks and local telemetry streams.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import logging
import os
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger("TelemetryAlerts")


class TelemetryAlertDispatcher:
    """Dispatches quantitative trading telemetry and instant alerts to Webhooks."""

    def __init__(
        self,
        discord_webhook_url: Optional[str] = None,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ) -> None:
        self.discord_webhook_url = discord_webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.telegram_bot_token = telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or getattr(self._session, "closed", False) is True:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5.0))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def send_order_alert(
        self,
        ticker: str,
        side: str,
        contracts: int,
        price: Decimal | float,
        cost: Decimal | float,
        fee: Decimal | float,
        ai_prob: float,
        vpin: float,
        execution_mode: str = "demo",
    ) -> None:
        """Dispatch instant alert when an order is executed."""
        title = f"🚀 [{execution_mode.upper()}] Trade Fill: {side.upper()} {contracts}x {ticker}"
        msg = (
            f"**Action:** `{side.upper()}` | **Contracts:** `{contracts}`\n"
            f"**Fill Price:** `${float(price):.2f}` | **Total Cost:** `${float(cost):.2f}` (Fee: `${float(fee):.2f}`)\n"
            f"**AI Probability:** `{ai_prob * 100.0:.1f}%` | **VPIN Toxicity:** `{vpin:.2f}`\n"
            f"**Time:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        )
        await self._dispatch(title, msg, color=0x00D084 if side.lower() == "yes" else 0xFF4D4D)

    async def send_settlement_alert(
        self,
        ticker: str,
        side: str,
        contracts: int,
        pnl: Decimal | float,
        roi_pct: float,
        outcome: str,
        balance_after: Decimal | float,
        strike_price: float,
        settlement_btc_price: float,
    ) -> None:
        """Dispatch instant alert when a 15-minute cycle settles."""
        is_win = outcome.lower() == "win"
        pnl_val = float(pnl)
        pnl_str = f"+${pnl_val:.2f}" if pnl_val >= 0 else f"-${abs(pnl_val):.2f}"
        icon = "🟢 WIN" if is_win else "🔴 LOSS"
        title = f"{icon} | 15M Cycle Settled: {ticker} ({pnl_str})"
        msg = (
            f"**Outcome:** `{outcome.upper()}` ({pnl_str} / `{roi_pct:+.1f}%` ROI)\n"
            f"**Target Strike:** `${strike_price:,.2f}` | **Spot Settlement:** `${settlement_btc_price:,.2f}`\n"
            f"**Position:** `{side.upper()}` ({contracts} contracts)\n"
            f"**New Account Balance:** `${float(balance_after):,.2f}`\n"
            f"**Time:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        )
        await self._dispatch(title, msg, color=0x00D084 if is_win else 0xFF4D4D)

    async def send_circuit_breaker_alert(
        self,
        reason: str,
        current_drawdown_pct: float,
        daily_loss_dollars: float,
    ) -> None:
        """Dispatch critical circuit breaker trip alert."""
        title = "🚨 CIRCUIT BREAKER TRIPPED: Automated Trading Halted"
        msg = (
            f"**Reason:** `{reason}`\n"
            f"**Current Drawdown:** `{current_drawdown_pct:.1f}%`\n"
            f"**Daily Loss:** `-${abs(daily_loss_dollars):.2f}`\n"
            f"**Action Taken:** All new order entries rejected. Manual reset required.\n"
            f"**Time:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        )
        await self._dispatch(title, msg, color=0xFF0055)

    async def _dispatch(self, title: str, content: str, color: int = 0x00D084) -> None:
        """Internal dispatch to configured external endpoints."""
        logger.info("[TELEMETRY ALERT] %s\n%s", title, content.replace("**", ""))

        # 1. Discord Webhook
        if self.discord_webhook_url:
            try:
                session = await self._get_session()
                payload = {
                    "embeds": [
                        {
                            "title": title,
                            "description": content,
                            "color": color,
                            "footer": {"text": "Kalshi Quantitative Terminal • Autonomous Safety Guard"},
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ]
                }
                async with session.post(self.discord_webhook_url, json=payload) as resp:
                    if resp.status not in (200, 204):
                        logger.warning("Discord webhook returned HTTP %d", resp.status)
            except Exception as exc:
                logger.warning("Failed to send Discord alert: %s", exc)

        # 2. Telegram Bot
        if self.telegram_bot_token and self.telegram_chat_id:
            try:
                session = await self._get_session()
                tg_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": f"*{title}*\n\n{content}",
                    "parse_mode": "Markdown",
                }
                async with session.post(tg_url, json=payload) as resp:
                    if resp.status != 200:
                        logger.warning("Telegram bot returned HTTP %d", resp.status)
            except Exception as exc:
                logger.warning("Failed to send Telegram alert: %s", exc)
