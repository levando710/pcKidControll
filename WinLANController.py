"""Optional console watchdog; checks executable paths instead of process names."""

import argparse
import logging
import subprocess
import time
from pathlib import Path

import psutil

from app_config import application_directory, configure_console

MAIN_APP_NAME = "PCKidControl.exe"
CHECK_INTERVAL_SECONDS = 5
RESTART_DELAY_SECONDS = 30
LOGGER = logging.getLogger(__name__)


def is_running(app_path: Path) -> bool:
    for process in psutil.process_iter(["exe"]):
        try:
            executable = process.info["exe"]
            if executable and Path(executable).resolve() == app_path:
                return True
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            # If inspection is denied, avoid repeatedly starting extra copies.
            return True
    return False


def check_and_restart() -> None:
    app_path = (application_directory() / MAIN_APP_NAME).resolve()
    if not app_path.is_file():
        raise FileNotFoundError(f"Cần đặt {MAIN_APP_NAME} cạnh watchdog.")
    child: subprocess.Popen | None = None
    last_launch: float | None = None
    while True:
        now = time.monotonic()
        child_running = child is not None and child.poll() is None
        cooldown_over = last_launch is None or now - last_launch >= RESTART_DELAY_SECONDS
        if not child_running and cooldown_over and not is_running(app_path):
            last_launch = now
            try:
                child = subprocess.Popen([str(app_path)], cwd=str(app_path.parent))
                LOGGER.info("Đã khởi động %s.", MAIN_APP_NAME)
            except OSError:
                LOGGER.error("Không khởi động được ứng dụng; sẽ thử lại sau.")
        time.sleep(CHECK_INTERVAL_SECONDS)


def main() -> None:
    configure_console()
    parser = argparse.ArgumentParser(description="PC Kid Control — watchdog tùy chọn, Ctrl+C để dừng.")
    parser.add_argument("--enable-watchdog", action="store_true", help="Bật tự mở lại ứng dụng.")
    args = parser.parse_args()
    if not args.enable_watchdog:
        parser.error("Thêm --enable-watchdog để bật chức năng tự mở lại.")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        check_and_restart()
    except KeyboardInterrupt:
        print("Đã dừng watchdog. Ứng dụng chính có thể vẫn đang chạy.")
    except OSError as error:
        parser.exit(status=1, message=f"{error}\n")


if __name__ == "__main__":
    main()
