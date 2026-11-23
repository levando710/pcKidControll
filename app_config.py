"""Local settings and credentials; never embed credentials into an executable."""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIME_LIMIT_SECONDS = 1800
DEFAULT_OTP_TTL_SECONDS = 300
DEFAULT_OTP_MAX_ATTEMPTS = 5
DEFAULT_REQUEST_COOLDOWN_SECONDS = 60
DEFAULT_REPORT_INTERVAL_SECONDS = 1500
MAX_DURATION_SECONDS = 86400
MAX_OTP_ATTEMPTS = 10
MAX_CONFIG_BYTES = 16384
CONFIG_FILENAME = "config.json"


def configure_console() -> None:
    """Keep Vietnamese CLI output valid when Windows redirects its streams."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(repr=False)
    chat_id: str = field(repr=False)
    game_name: str = "Discord.exe"
    time_limit_seconds: int = DEFAULT_TIME_LIMIT_SECONDS
    otp_ttl_seconds: int = DEFAULT_OTP_TTL_SECONDS
    otp_max_attempts: int = DEFAULT_OTP_MAX_ATTEMPTS
    request_cooldown_seconds: int = DEFAULT_REQUEST_COOLDOWN_SECONDS
    report_interval_seconds: int = DEFAULT_REPORT_INTERVAL_SECONDS


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path if config_path is not None else application_directory() / CONFIG_FILENAME
    config = {}
    if path.exists():
        if path.stat().st_size > MAX_CONFIG_BYTES:
            raise ValueError("config.json quá lớn.")
        try:
            config = json.loads(path.read_text(encoding="utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError):
            raise ValueError("config.json phải là JSON UTF-8 hợp lệ.") from None
        if not isinstance(config, dict):
            raise ValueError("config.json phải chứa một object.")
    allowed = set(Settings.__dataclass_fields__) - {"bot_token", "chat_id"}
    if set(config) - allowed:
        raise ValueError("config.json chứa khóa không hỗ trợ; xem config.example.json.")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise ValueError("Cần đặt TELEGRAM_BOT_TOKEN hợp lệ trong biến môi trường.")
    if not re.fullmatch(r"-?[0-9]+", chat_id):
        raise ValueError("Cần đặt TELEGRAM_CHAT_ID dạng số trong biến môi trường.")
    settings = Settings(bot_token=token, chat_id=chat_id, **config)
    if not isinstance(settings.game_name, str) or not re.fullmatch(
        r"[^\\/:*?\"<>|\x00-\x1f]+\.exe", settings.game_name, re.IGNORECASE
    ):
        raise ValueError("game_name phải là tên tiến trình .exe, không phải đường dẫn.")
    for name in allowed - {"game_name", "otp_max_attempts"}:
        value = getattr(settings, name)
        if type(value) is not int or not 0 < value <= MAX_DURATION_SECONDS:
            raise ValueError(f"{name} phải là số nguyên từ 1 đến {MAX_DURATION_SECONDS}.")
    if type(settings.otp_max_attempts) is not int or not 0 < settings.otp_max_attempts <= MAX_OTP_ATTEMPTS:
        raise ValueError(f"otp_max_attempts phải từ 1 đến {MAX_OTP_ATTEMPTS}.")
    return settings
