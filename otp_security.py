"""Single-use authorization codes, driven by a monotonic clock."""

import secrets
import string
import time
from collections.abc import Callable

from app_config import Settings

OTP_LENGTH = 6


class OtpSession:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic):
        self.settings = settings
        self.clock = clock
        self._code = ""
        self._expires_at = 0.0
        self._last_request: float | None = None
        self._attempts = 0
        self.authorized_until = 0.0

    def issue(self) -> str:
        now = self.clock()
        if self._last_request is not None and now - self._last_request < self.settings.request_cooldown_seconds:
            raise ValueError("Vui lòng chờ hết thời gian giữa hai lần xin mã.")
        self.invalidate()
        self._last_request = now
        self._code = "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))
        self._expires_at = now + self.settings.otp_ttl_seconds
        return self._code

    def invalidate(self) -> None:
        self._code = ""
        self._expires_at = 0.0
        self._attempts = 0

    def verify(self, candidate: str) -> bool:
        now = self.clock()
        if not self._code or now >= self._expires_at:
            self.invalidate()
            return False
        self._attempts += 1
        if candidate.isascii() and secrets.compare_digest(candidate, self._code):
            self.authorized_until = max(now, self.authorized_until) + self.settings.time_limit_seconds
            self.invalidate()
            return True
        if self._attempts >= self.settings.otp_max_attempts:
            self.invalidate()
        return False

    def remaining_seconds(self) -> float:
        return max(0.0, self.authorized_until - self.clock())
