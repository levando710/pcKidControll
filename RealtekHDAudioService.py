"""Optional, visible application-usage reporter (legacy source filename)."""

import argparse
import logging
import time
from datetime import datetime

import psutil
import pywintypes
import win32gui
import win32process

from app_config import Settings, configure_console, load_settings
from telegram_client import MAX_MESSAGE_CHARACTERS, TelegramDeliveryError, send_message

SAMPLE_INTERVAL_SECONDS = 5
MIN_REPORT_USAGE_SECONDS = 60
SECONDS_PER_MINUTE = 60
IGNORED_PROCESSES = frozenset(
    name.casefold() for name in (
        "explorer.exe", "SearchApp.exe", "LockApp.exe", "Idle", "System",
        "ShellExperienceHost.exe", "Taskmgr.exe",
    )
)
LOGGER = logging.getLogger(__name__)


def get_active_process_name() -> str | None:
    try:
        window = win32gui.GetForegroundWindow()
        if not window:
            return None
        _, pid = win32process.GetWindowThreadProcessId(window)
        return psutil.Process(pid).name() if pid > 0 else None
    except (psutil.NoSuchProcess, psutil.AccessDenied, pywintypes.error):
        return None


def send_session_report(
    settings: Settings, usage: dict[str, float], counts: dict[str, int], start: datetime,
) -> None:
    header = f"PC Kid Control — Báo cáo {start:%H:%M} - {datetime.now():%H:%M}\n"
    messages = []
    message = header
    for app, seconds in sorted(usage.items(), key=lambda item: item[1], reverse=True):
        if seconds < MIN_REPORT_USAGE_SECONDS:
            continue
        # Process names are untrusted text; keep each report entry on one line.
        safe_name = " ".join(app.split())
        line = f"{safe_name}: {int(seconds) // SECONDS_PER_MINUTE} phút ({counts.get(app, 0)} lượt focus)\n"
        if len(message) + len(line) > MAX_MESSAGE_CHARACTERS:
            messages.append(message)
            message = header
        message += line
    if message != header:
        messages.append(message)
    for message in messages:
        send_message(settings, message)


def main_loop(settings: Settings) -> None:
    usage: dict[str, float] = {}
    counts: dict[str, int] = {}
    start = datetime.now()
    last_sample = last_report = time.monotonic()
    previous_app = get_active_process_name()
    print("PC Kid Control: đang thống kê tên ứng dụng và thời gian focus. Ctrl+C để dừng.", flush=True)
    while True:
        time.sleep(SAMPLE_INTERVAL_SECONDS)
        now = time.monotonic()
        elapsed = min(now - last_sample, SAMPLE_INTERVAL_SECONDS)
        last_sample = now
        active_app = get_active_process_name()
        if previous_app and previous_app.casefold() not in IGNORED_PROCESSES:
            if previous_app not in usage:
                counts[previous_app] = 1
            usage[previous_app] = usage.get(previous_app, 0.0) + elapsed
        if active_app and active_app != previous_app and active_app in counts:
            counts[active_app] += 1
        previous_app = active_app
        if now - last_report >= settings.report_interval_seconds:
            try:
                send_session_report(settings, usage, counts, start)
            except TelegramDeliveryError as error:
                LOGGER.warning("%s Dữ liệu phiên vẫn giữ trong RAM để gửi lại.", error)
            else:
                usage.clear()
                counts.clear()
                start = datetime.now()
            last_report = now


def main() -> None:
    configure_console()
    parser = argparse.ArgumentParser(description="PC Kid Control — báo cáo sử dụng ứng dụng qua Telegram.")
    parser.add_argument("--enable-reporting", action="store_true", help="Xác nhận bật báo cáo sử dụng.")
    args = parser.parse_args()
    if not args.enable_reporting:
        parser.error("Chỉ chạy khi đã thông báo cho người dùng: thêm --enable-reporting.")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        main_loop(load_settings())
    except KeyboardInterrupt:
        print("Đã dừng báo cáo. Dữ liệu chưa gửi trong RAM được bỏ.")
    except (OSError, ValueError) as error:
        parser.exit(status=1, message=f"Không khởi động được: {error}\n")


if __name__ == "__main__":
    main()
