from discord_webhook import DiscordWebhook, DiscordEmbed
from app.core.config import config
import threading

class DiscordService:
    def __init__(self):
        self.alert_url = config.DISCORD_WEBHOOK_ALERTS
        self.log_url = config.DISCORD_WEBHOOK_LOGS

    def _send(self, url: str, content: str = None, embed: DiscordEmbed = None):
        if not url:
            return
        
        def run():
            try:
                webhook = DiscordWebhook(url=url, content=content)
                if embed:
                    webhook.add_embed(embed)
                webhook.execute()
            except Exception as e:
                print(f"Failed to send Discord webhook: {e}")

        # Non-blocking
        threading.Thread(target=run, daemon=True).start()

    def send_alert(self, title: str, description: str, color: str = "red"):
        embed = DiscordEmbed(title=title, description=description, color=color)
        embed.set_timestamp()
        self._send(self.alert_url, embed=embed)

    def send_execution_error(self, title: str, **fields):
        """Push a structured execution failure alert to the alerts webhook."""
        lines = []
        for key, value in fields.items():
            if value is None or value == "":
                continue
            label = key.replace("_", " ").title()
            lines.append(f"**{label}:** {value}")
        description = "\n".join(lines) if lines else "No details provided."
        self.send_alert(title, description, color="FF0000")

    def send_log(self, message: str):
        self._send(self.log_url, content=f"`[LOG]` {message}")
    
    def refresh_webhooks(self, alert_url: str = None, log_url: str = None):
        """Refresh webhook URLs dynamically (for hot-reload support)"""
        if alert_url:
            self.alert_url = alert_url
        if log_url:
            self.log_url = log_url

    def send_trade_signal(self, symbol: str, side: str, price: float, analysis: str):
        color = "00ff00" if side.upper() == "BUY" else "ff0000"
        title = f"🚀 SIGNAL: {side.upper()} {symbol}"
        desc = (
            f"**Price:** {price}\n"
            f"**Analysis:** {analysis}"
        )
        self.send_alert(title, desc, color=color)

discord_service = DiscordService()
