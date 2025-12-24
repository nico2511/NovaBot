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

    def send_log(self, message: str):
        self._send(self.log_url, content=f"`[LOG]` {message}")

    def send_trade_signal(self, symbol: str, side: str, price: float, analysis: str):
        color = "00ff00" if side.upper() == "BUY" else "ff0000"
        title = f"🚀 SIGNAL: {side.upper()} {symbol}"
        desc = (
            f"**Price:** {price}\n"
            f"**Analysis:** {analysis}"
        )
        self.send_alert(title, desc, color=color)

discord_service = DiscordService()
