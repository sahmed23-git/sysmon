"""
Telegram Bot — sends alerts to a configured Telegram chat.
"""
import os
import json
import requests


class TelegramBot:
    def __init__(self):
        self.token = os.environ.get('TELEGRAM_TOKEN', '')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        self._load_from_settings()

    def _load_from_settings(self):
        cfg_path = 'instance/settings.json'
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                cfg = json.load(f)
                self.token = cfg.get('telegram_token', self.token)
                self.chat_id = cfg.get('telegram_chat_id', self.chat_id)

    def update_credentials(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def send(self, message: str) -> bool:
        """
        Sends a message to the configured Telegram chat.
        Returns True if successful.
        """
        if not self.token or not self.chat_id:
            print(f"[Telegram] Not configured. Message: {message}")
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            resp = requests.post(url, json={
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }, timeout=10)
            if resp.status_code == 200:
                print(f"[Telegram] Sent: {message[:60]}...")
                return True
            else:
                print(f"[Telegram] Failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"[Telegram] Error: {e}")
        return False
