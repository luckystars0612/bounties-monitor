# Hướng dẫn deploy Bounty Scope Monitor làm Service trên VPS Linux

Tài liệu này hướng dẫn cách cấu hình dự án chạy nền như một **Systemd Service** trên VPS Linux (Ubuntu/Debian, CentOS, v.v.), đảm bảo bot tự động chạy lại khi server reboot hoặc khi bị crash đột ngột.

---

## Bước 1: Chuẩn bị trên VPS

1. Clone mã nguồn của bạn về VPS:
   ```bash
   git clone https://github.com/luckystars0612/bounties-monitor.git /opt/bounties-monitor
   cd /opt/bounties-monitor
   ```
2. Cài đặt **uv** (nếu chưa cài):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source $HOME/.local/bin/env
   ```
3. Tạo môi trường ảo và cài đặt thư viện tự động thông qua `uv`:
   ```bash
   uv sync
   ```
4. Copy file cấu hình mẫu và điền thông tin của bạn (token telegram bot, chat id group/channel, v.v.):
   ```bash
   cp .env.example .env
   nano .env
   ```

---

## Bước 2: Thiết lập Systemd Service

1. Copy file service mẫu vào thư mục cấu hình hệ thống:
   ```bash
   sudo cp deploy/bounties-monitor.service /etc/systemd/system/bounties-monitor.service
   ```
2. Mở file service ra cấu hình lại thông số cho khớp với VPS của bạn:
   ```bash
   sudo nano /etc/systemd/system/bounties-monitor.service
   ```
   * Lưu ý sửa lại giá trị `User=YOUR_USERNAME` thành username Linux hiện tại của bạn trên VPS (ví dụ: `User=ubuntu` hoặc `User=root`).
   * Kiểm tra xem thư mục cài đặt `WorkingDirectory` và đường dẫn Python `ExecStart` đã chính xác chưa.

3. Tải lại cấu hình systemd để hệ thống nhận diện service mới:
   ```bash
   sudo systemctl daemon-reload
   ```

---

## Bước 3: Quản lý Service

* **Kích hoạt tự động chạy khi khởi động VPS**:
  ```bash
  sudo systemctl enable bounties-monitor
  ```
* **Khởi động service**:
  ```bash
  sudo systemctl start bounties-monitor
  ```
* **Dừng service**:
  ```bash
  sudo systemctl stop bounties-monitor
  ```
* **Khởi động lại service** (Sau khi bạn cập nhật code mới hoặc sửa file `.env`):
  ```bash
  sudo systemctl restart bounties-monitor
  ```
* **Kiểm tra trạng thái đang chạy**:
  ```bash
  sudo systemctl status bounties-monitor
  ```

---

## Bước 4: Xem log hoạt động

Bạn có thể theo dõi trực tiếp log hoạt động của bot (các đợt quét dữ liệu, lệnh telegram nhận được, thông báo gửi đi, v.v.) bằng lệnh sau:
```bash
journalctl -u bounties-monitor -f
```
