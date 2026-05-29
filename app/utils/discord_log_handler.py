"""
Forward Python logging WARNING/ERROR/CRITICAL records to Discord alerts webhook.
"""
from __future__ import annotations

import logging

from app.services.discord_service import discord_service
from app.utils.discord_dedup import dedup_key, should_send_discord_alert


class DiscordAlertHandler(logging.Handler):
    """Send WARNING+ log records to Discord (deduplicated)."""

    MAX_LEN = 1900

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return
        try:
            msg = self.format(record)
            title = f"{record.name}"
            level = record.levelname
            key = dedup_key("logger", f"{level}:{title}", msg)
            if not should_send_discord_alert(key):
                return
            discord_service.notify(level, title, msg[: self.MAX_LEN], source="logger")
        except Exception:
            self.handleError(record)


def install_discord_alert_handler(level: int = logging.WARNING) -> None:
    """Attach Discord handler to root logger (idempotent)."""
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, DiscordAlertHandler):
            return
    handler = DiscordAlertHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(handler)
