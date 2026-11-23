"""Visible PC Kid Control application; legacy source filename retained."""

import queue
import threading
import tkinter as tk
from tkinter import messagebox

import psutil

from app_config import Settings, load_settings
from otp_security import OtpSession
from telegram_client import TelegramDeliveryError, send_message

MONITOR_INTERVAL_MS = 1000
DELIVERY_POLL_INTERVAL_MS = 100
SECONDS_PER_MINUTE = 60
WINDOW_GEOMETRY = "410x280"


class GameControllerApp:
    def __init__(self, root: tk.Tk, settings: Settings):
        self.root = root
        self.settings = settings
        self.session = OtpSession(settings)
        self.delivery_results: queue.Queue[str | None] = queue.Queue()
        self.sending = False
        root.title("PC Kid Control — Quản lý thời gian")
        root.geometry(WINDOW_GEOMETRY)
        root.resizable(False, False)
        self.label_status = tk.Label(root, text="Trạng thái: ĐANG KHÓA", fg="red")
        self.label_status.pack(pady=5)
        tk.Label(root, text=f"Ứng dụng được quản lý: {settings.game_name}").pack()
        self.btn_get_code = tk.Button(root, text="Xin mã từ người quản lý", command=self.request_code)
        self.btn_get_code.pack(pady=5)
        self.entry_code = tk.Entry(root, justify="center", width=15, show="*")
        self.entry_code.pack(pady=5)
        self.btn_submit = tk.Button(root, text="Xác nhận / Nạp thêm giờ", command=self.verify_code)
        self.btn_submit.pack(pady=5)
        self.label_timer = tk.Label(root, text="Thời gian còn lại: 00:00")
        self.label_timer.pack(pady=5)
        tk.Label(root, text="Đóng cửa sổ để thu nhỏ. Dừng bằng Task Manager.").pack()
        root.protocol("WM_DELETE_WINDOW", root.iconify)
        self.monitor_game()
        root.after(DELIVERY_POLL_INTERVAL_MS, self.poll_delivery)

    def request_code(self) -> None:
        if self.sending:
            return
        try:
            code = self.session.issue()
        except ValueError as error:
            messagebox.showerror("Chưa thể xin mã", str(error))
            return
        self.sending = True
        self.btn_get_code.config(state=tk.DISABLED)
        self.btn_submit.config(state=tk.DISABLED)
        threading.Thread(target=self.deliver_code, args=(code,), daemon=True).start()

    def deliver_code(self, code: str) -> None:
        try:
            send_message(
                self.settings,
                f"Yêu cầu mở {self.settings.game_name}.\nMã OTP: {code}\n"
                f"Hiệu lực {self.settings.otp_ttl_seconds} giây, dùng một lần.\n"
                f"Mỗi mã cộng {self.settings.time_limit_seconds} giây.",
            )
        except TelegramDeliveryError as error:
            self.delivery_results.put(str(error))
        else:
            self.delivery_results.put(None)

    def poll_delivery(self) -> None:
        try:
            error = self.delivery_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.sending = False
            self.btn_get_code.config(state=tk.NORMAL)
            self.btn_submit.config(state=tk.NORMAL)
            if error is not None:
                self.session.invalidate()
                messagebox.showerror("Gửi mã thất bại", error)
            else:
                messagebox.showinfo("Đã gửi", "Telegram đã nhận yêu cầu. Xin mã từ người quản lý.")
        self.root.after(DELIVERY_POLL_INTERVAL_MS, self.poll_delivery)

    def verify_code(self) -> None:
        if self.sending:
            return
        candidate = self.entry_code.get().strip()
        self.entry_code.delete(0, tk.END)
        if self.session.verify(candidate):
            self.root.iconify()
        else:
            messagebox.showerror("Không mở khóa", "Mã sai, hết hạn hoặc đã hết lượt thử. Xin mã mới nếu cần.")

    def monitor_game(self) -> None:
        remaining = self.session.remaining_seconds()
        minutes, seconds = divmod(int(remaining), SECONDS_PER_MINUTE)
        unlocked = remaining > 0
        self.label_timer.config(text=f"Thời gian còn lại: {minutes:02d}:{seconds:02d}")
        self.label_status.config(
            text="Trạng thái: ĐÃ MỞ KHÓA" if unlocked else "Trạng thái: ĐANG KHÓA",
            fg="green" if unlocked else "red",
        )
        if not unlocked:
            game_found = False
            for process in psutil.process_iter(["name"]):
                try:
                    if (process.info["name"] or "").casefold() == self.settings.game_name.casefold():
                        game_found = True
                        process.terminate()
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    self.label_status.config(text="Không đủ quyền dừng ứng dụng.", fg="red")
            if game_found and self.root.state() in {"iconic", "withdrawn"}:
                self.root.deiconify()
        self.root.after(MONITOR_INTERVAL_MS, self.monitor_game)


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        settings = load_settings()
    except (OSError, ValueError) as error:
        messagebox.showerror("Cấu hình không hợp lệ", str(error), parent=root)
        root.destroy()
        return
    GameControllerApp(root, settings)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
