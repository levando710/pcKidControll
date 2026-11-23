"""Bounded HTTPS delivery without exposing token-bearing URLs in errors."""

import requests

from app_config import Settings

CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 10
MAX_MESSAGE_CHARACTERS = 4000


class TelegramDeliveryError(Exception):
    """Safe error text that can be displayed or logged."""


def send_message(settings: Settings, message: str) -> None:
    if not message or len(message) > MAX_MESSAGE_CHARACTERS:
        raise TelegramDeliveryError("Nội dung Telegram trống hoặc quá dài.")
    try:
        with requests.post(
            f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",
            data={"chat_id": settings.chat_id, "text": message},
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            allow_redirects=False,
        ) as response:
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or result.get("ok") is not True:
                raise TelegramDeliveryError("Telegram chưa xác nhận gửi thành công.")
    except (requests.RequestException, ValueError):
        # Request errors and Telegram responses can contain the secret URL.
        raise TelegramDeliveryError("Không gửi được Telegram. Kiểm tra mạng và cấu hình bot.") from None
