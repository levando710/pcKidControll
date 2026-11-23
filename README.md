# PC Kid Control

Ứng dụng Python cho Windows giúp người quản lý cấp thời gian sử dụng một ứng dụng bằng mã OTP gửi qua Telegram. Có thêm báo cáo thời gian focus ứng dụng và watchdog tùy chọn.

## Trước khi sử dụng

- **Thu hồi token Telegram đã từng nằm trong mã nguồn cũ và tạo token mới qua [BotFather](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).** Không sử dụng lại token cũ. Các bản EXE trong `dist/` và dữ liệu build cũ trên máy có thể vẫn chứa token cũ; bản sửa không cập nhật chúng. Không phân phối các bản đó.
- Chỉ dùng trên máy bạn có quyền quản lý, thông báo cho người sử dụng khi bật thống kê.
- Công cụ chỉ kiểm soát khi chương trình đang chạy. Người có quyền sửa code, cấu hình, đọc bộ nhớ/biến môi trường hoặc dừng tiến trình có thể vượt qua. Đây không phải ranh giới bảo mật cấp Windows. Không nên dùng chung tài khoản Windows có quyền quản trị với trẻ.
- Chương trình gọi `terminate()` với **mọi tiến trình cùng tên** khi chưa được cấp giờ/hết giờ; dữ liệu chưa lưu có thể mất. Chọn đúng ứng dụng cần quản lý.

## Yêu cầu và cài đặt

Windows 10/11, Python có Tkinter, Git và kết nối HTTPS đến `api.telegram.org`. Mã tương thích Python 3.10 trở lên; nên cài Python 3.13 hoặc bản còn được hỗ trợ với các bản vá mới nhất. Mở PowerShell tại thư mục dự án:

```powershell
git clone https://github.com/levando710/pcKidControll.git
cd pcKidControll
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config.example.json config.json
```

Không cần kích hoạt venv hoặc đổi ExecutionPolicy. Mặc định chạy bằng tài khoản thông thường; tiến trình thuộc tài khoản khác hoặc quyền cao hơn có thể không dừng được.

## Cấu hình Telegram

1. Tạo bot/token mới qua BotFather. Người quản lý mở chat riêng với bot và gửi `/start`.
2. Lấy `message.chat.id` bằng phương thức [`getUpdates`](https://core.telegram.org/bots/api#getupdates), dùng token mới trên máy tin cậy. Không gửi token cho dịch vụ lấy ID không tin cậy, không chia sẻ ảnh/URL chứa token. Bot đang có webhook phải được xử lý webhook trước nếu muốn dùng `getUpdates`.
3. Đặt hai biến môi trường trong **PowerShell sẽ chạy ứng dụng**. Đoạn sau nhập token dưới dạng che ký tự, không ghi giá trị token vào lịch sử lệnh:

```powershell
$botSecret = Read-Host 'Token Telegram MỚI' -AsSecureString
$env:TELEGRAM_BOT_TOKEN = [System.Net.NetworkCredential]::new('', $botSecret).Password
$env:TELEGRAM_CHAT_ID = Read-Host 'Chat ID của người quản lý'
Remove-Variable botSecret
```

Các biến chỉ áp dụng cho phiên PowerShell và các tiến trình con. Khi mở PowerShell mới cần nhập lại. Không lưu token trong repository, file `.spec`, screenshot hoặc tham số lệnh. Không ghi log HTTP debug vì URL Telegram chứa token.

Khi không còn ứng dụng nào cần dùng thông tin này:

```powershell
Remove-Item Env:TELEGRAM_BOT_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:TELEGRAM_CHAT_ID -ErrorAction SilentlyContinue
```

Thao tác này không xóa bản sao biến môi trường trong tiến trình đã chạy. Muốn vô hiệu hóa token đã lộ phải thu hồi token tại BotFather.

## Cấu hình ứng dụng

Sửa `config.json` cạnh mã nguồn, hoặc cạnh EXE khi đóng gói. File này được Git bỏ qua. Nếu không có file, ứng dụng dùng giá trị mặc định:

| Khóa | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `game_name` | `Discord.exe` | Tên trong Task Manager → Details, không phải đường dẫn; thay bằng ứng dụng thực tế |
| `time_limit_seconds` | `1800` | Mỗi OTP cộng 30 phút |
| `otp_ttl_seconds` | `300` | Mã hết hạn sau 5 phút kể từ lúc tạo |
| `otp_max_attempts` | `5` | Số lần nhập sai trước khi hủy mã |
| `request_cooldown_seconds` | `60` | Thời gian tối thiểu giữa hai yêu cầu mã |
| `report_interval_seconds` | `1500` | Chu kỳ báo cáo 25 phút |

Thời lượng phải là số nguyên từ 1 đến 86400 giây; số lần thử từ 1 đến 10. Khóa lạ, tên tiến trình sai hoặc JSON sai khiến chương trình từ chối khởi động. Thay đổi cấu hình có hiệu lực khi khởi động lại. Token và chat ID chỉ lấy từ biến môi trường, không đặt trong JSON.

## Cấp thời gian sử dụng

```powershell
.\.venv\Scripts\python.exe WindowService.py
```

1. Kiểm tra tên ứng dụng hiển thị rồi bấm **Xin mã từ người quản lý**.
2. Người quản lý nhận mã qua Telegram và quyết định có đưa mã cho người sử dụng hay không.
3. Nhập mã rồi bấm **Xác nhận / Nạp thêm giờ**. Mã đúng cộng thời gian vào số dư hiện tại; giao diện thu nhỏ xuống taskbar.
4. Hết giờ, ứng dụng được quản lý bị dừng và cửa sổ yêu cầu mã xuất hiện lại.

Mã sinh bằng `secrets`, dùng một lần; mã mới thay mã cũ. Sai đủ lượt hoặc hết hạn thì cần xin mã mới. Khi gửi Telegram thất bại, mã bị hủy; không báo thành công giả. Gửi mạng chạy ở luồng riêng với timeout và không cập nhật Tkinter trực tiếp từ luồng đó. Bộ đếm dùng đồng hồ monotonic để tránh thay đổi khi chỉnh giờ hệ thống. Mã và số dư chỉ lưu trong RAM; khởi động lại sẽ mất thời gian còn lại. Thời gian đã cấp giảm liên tục dù ứng dụng được quản lý chưa mở; không phải bộ đếm thời gian chơi thực tế.

Nút X chỉ thu nhỏ. Muốn dừng hoàn toàn, dừng watchdog trước nếu đang bật, sau đó End task tiến trình ứng dụng trong Task Manager (với bản Python, chọn đúng tiến trình chạy `WindowService.py`).

## Báo cáo sử dụng tùy chọn

Trong PowerShell đã có biến Telegram:

```powershell
.\.venv\Scripts\python.exe RealtekHDAudioService.py --enable-reporting
```

Console hiển thị trạng thái và có thể dừng bằng **Ctrl+C**. Không truyền cờ thì chương trình không bật thống kê. Tên file Python được giữ để tương thích, đây **không phải driver Realtek hay Windows Service**.

Reporter lấy mẫu cửa sổ foreground mỗi 5 giây, đếm thời gian ước lượng và số lượt focus, bỏ qua một số tiến trình giao diện Windows. Báo cáo chỉ gồm tên tiến trình, số phút, lượt focus và khoảng giờ; chỉ liệt kê ứng dụng có ít nhất 60 giây trong phiên. Không thu thập phím gõ, tiêu đề cửa sổ, URL, nội dung tài liệu hoặc ảnh màn hình. Báo cáo được gửi đến chat ID đã cấu hình; dữ liệu đã gửi do Telegram lưu theo dịch vụ của họ.

Dữ liệu phiên chỉ ở RAM. Nếu gửi lỗi, giữ để thử lại ở chu kỳ tiếp theo; gửi nhiều phần bị lỗi giữa chừng có thể làm lặp phần đã gửi khi thử lại. Dừng chương trình bỏ dữ liệu chưa gửi. Đây là thống kê lấy mẫu, không đo chính xác thời gian hoạt động hay phát hiện idle; khoảng sleep dài được giới hạn để tránh tính toàn bộ thời gian máy ngủ.

## Đóng gói EXE và watchdog tùy chọn

```powershell
.\.venv\Scripts\python.exe -m pip install 'pyinstaller>=6.0,<7.0'
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm WindowService.spec
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm RealtekHDAudioService.spec
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm WinLANController.spec
Copy-Item config.example.json dist\config.json
```

Sửa `dist\config.json` trước khi chạy. Kết quả:

| File EXE mới | Chức năng |
| --- | --- |
| `dist\PCKidControl.exe` | Giao diện cấp thời gian |
| `dist\PCKidUsageReporter.exe` | Reporter có console; cần `--enable-reporting` |
| `dist\PCKidWatchdog.exe` | Watchdog có console; cần `--enable-watchdog` |

EXE không chứa cấu hình/token. Chạy từ PowerShell đã đặt biến môi trường:

```powershell
.\dist\PCKidControl.exe
# Hoặc bật watchdog để tự khởi chạy/khởi chạy lại ứng dụng chính:
.\dist\PCKidWatchdog.exe --enable-watchdog
# Trong PowerShell khác có cấu hình Telegram, nếu cần báo cáo:
.\dist\PCKidUsageReporter.exe --enable-reporting
```

Watchdog yêu cầu EXE chính cùng thư mục, kiểm tra đường dẫn tiến trình và chờ tối thiểu 30 giây giữa các lần khởi chạy. Dừng bằng Ctrl+C; ứng dụng chính có thể vẫn chạy. Không cài tự khởi động cùng Windows, dịch vụ, scheduled task hay cơ chế ẩn. Chỉ bật một watchdog. File `WatchDog.spec` cũ tham chiếu mã không tồn tại đã được bỏ.

`build/`, `dist/`, `.venv/`, file EXE, token môi trường và `config.json` không được đưa lên Git. Không dùng lại EXE cũ mang tên dịch vụ/driver; hãy build lại từ source này.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app_config.py otp_security.py telegram_client.py WindowService.py RealtekHDAudioService.py WinLANController.py tests
.\.venv\Scripts\python.exe -m pip install ruff pip-audit
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
```

Test không gửi Telegram thật hoặc dừng tiến trình thật. Kiểm tra Telegram end-to-end cần token mới/chat ID thật; hãy thử trên ứng dụng có thể đóng an toàn. CI Windows chạy test, kiểm tra cú pháp, Ruff và kiểm tra dependency.

## Xử lý lỗi

- **Thiếu/sai token hoặc chat ID:** đặt lại biến môi trường trong đúng PowerShell chạy ứng dụng. EXE mở bằng nhấp đúp không thừa hưởng biến của PowerShell đó.
- **Telegram không gửi được:** kiểm tra mạng, token mới, chat ID, `/start`, quyền bot gửi tin. Không chia sẻ exception HTTP nguyên gốc chứa URL token.
- **Không đủ quyền dừng ứng dụng:** kiểm tra tài khoản/quyền của tiến trình đích; không tự nâng quyền chương trình chỉ để che lỗi.
- **Không thấy game bị quản lý:** dùng đúng tên `.exe` ở tab Details, có thể game có nhiều tiến trình khác tên.
- **Không mở được GUI:** kiểm tra Python có Tkinter (`python -m tkinter`) và đang chạy trên phiên desktop Windows.

## Tài liệu tham khảo

- [Telegram Bot API](https://core.telegram.org/bots/api): kết nối HTTPS, `sendMessage`, trạng thái `ok` và `getUpdates`.
- [Python 3.10 secrets](https://docs.python.org/3.10/library/secrets.html): sinh số ngẫu nhiên cho bảo mật và so sánh mã.
