# Vận hành hằng ngày

Mọi lệnh chạy trong thư mục `~/Projects/Dr4Women-MacMini`.

```bash
cd ~/Projects/Dr4Women-MacMini
```

---

## Đường vào hệ thống

| Vào từ đâu | Địa chỉ |
|---|---|
| **Chính máy Mac mini** | http://localhost |
| **Máy khác trong phòng khám** (cùng wifi) | http://192.168.1.239 |
| Từ ngoài internet | *chưa có* — xem ghi chú cuối trang |

Địa chỉ LAN đổi theo router. Xem lại bằng:

```bash
ipconfig getifaddr en0
```

### Hai màn kỹ thuật (chỉ mở được TRÊN máy Mac)

| | Địa chỉ | Dùng để |
|---|---|---|
| Xem log | http://localhost:8888 | Đọc log thời gian thực của từng container |
| Giám sát | http://localhost:3001 | Uptime Kuma — báo khi dịch vụ chết |

Hai cái này buộc vào `127.0.0.1` nên máy khác **không** vào được. Cố ý.

### Các màn chính của phần mềm

Thêm vào sau địa chỉ ở trên, ví dụ `http://192.168.1.239/home`

| Vai | Đường dẫn |
|---|---|
| Trang chủ | `/home` |
| Lễ tân — hàng đợi / check-out | `/reception/queue` · `/reception/checkout` |
| Bác sĩ | `/doctor/board` |
| Trưởng ca | `/truong-ca` · `/truong-ca/hang-doi` · `/truong-ca/canh-bao` · `/truong-ca/lich-su` |
| Màn hình TV phòng chờ | `/truong-ca/tv` |
| CSKH — đặt lịch / nhắc lịch / khách hàng | `/appointments` · `/cskh-tasks` · `/customers` |
| Thu ngân | `/cashier/thuoc` · `/cashier/dich-vu` |
| Nhà thuốc | `/pharmacy` · `/pharmacy/inventory` |
| Xét nghiệm / siêu âm | `/lab-queue` · `/sono` |
| Báo cáo · Nhật ký thao tác | `/reports` · `/audit-log` |
| Cấu hình · Luật đặt lịch | `/settings` · `/settings/booking-policy` |

---

## Bật / tắt / xem trạng thái

```bash
# Xem đang chạy gì
docker compose --env-file .env.prod -p clinicai_prod ps

# TẮT toàn bộ (bệnh nhân không vào được)
docker compose --env-file .env.prod -p clinicai_prod stop

# BẬT lại
CLINIC_ENV_FILE=.env.prod docker compose --env-file .env.prod -p clinicai_prod up -d

# Khởi động lại một dịch vụ (khi nó treo)
docker compose --env-file .env.prod -p clinicai_prod restart api
```

`CLINIC_ENV_FILE` chỉ cần khi **bật**. Thiếu nó thì compose báo
`required variable CLINIC_ENV_FILE is missing a value` và không chạy — đó là
chốt chặn cố ý, để không ai vô tình bật prod bằng file cấu hình của staging.

**Cách gọn hơn**, làm đúng cả hai việc trên và tự bật Colima nếu cần:

```bash
./scripts/clinic-boot.sh
```

Chạy bao nhiêu lần cũng được — mọi thứ đã đúng thì nó không đụng gì.

---

## Xem log khi có sự cố

```bash
# Log trực tiếp, thoát bằng Ctrl-C
docker compose --env-file .env.prod -p clinicai_prod logs -f api

# 100 dòng cuối của mọi dịch vụ
docker compose --env-file .env.prod -p clinicai_prod logs --tail=100

# Chỉ lỗi
docker compose --env-file .env.prod -p clinicai_prod logs --tail=500 | grep -i error
```

Hoặc mở http://localhost:8888 cho dễ đọc.

---

## Cập nhật phần mềm sau khi có code mới

```bash
git pull
./scripts/deploy-backend.sh prod
```

Script tự làm đủ: build → bật → kiểm sức khoẻ → **tự quay về bản cũ nếu bản mới
không sống**. Nó cũng từ chối chạy khi thư mục còn thay đổi chưa commit — để
bản đang chạy trên prod luôn khớp đúng một commit trong git.

Khi có thay đổi cấu trúc database (hiếm, và tách riêng có chủ ý):

```bash
npx supabase db push
```

---

## Sao lưu

Chạy tự động **02:00 mỗi ngày**. Kiểm bản gần nhất:

```bash
ls -lh ~/backups/clinicai/ | tail -5
```

Chạy tay khi cần (trước khi làm gì đó lớn):

```bash
./scripts/backup-db.sh
```

Cách khôi phục: [khoi-phuc-du-lieu.md](khoi-phuc-du-lieu.md). **Đọc trước khi
cần đến nó**, đừng đọc lúc đang hỏng.

---

## Ba câu kiểm nhanh khi "web không vào được"

```bash
# 1. Docker còn sống không? (hay gặp nhất sau khi mất điện)
colima status

# 2. Container còn chạy không?
docker compose --env-file .env.prod -p clinicai_prod ps

# 3. Web trả lời không?
curl -I http://localhost
```

Thứ tự đó không ngẫu nhiên: Colima chết thì mọi thứ bên dưới đều chết theo, mà
nhìn vào container sẽ không hiểu vì sao.

Cả ba đều ổn mà vẫn không vào được từ máy khác → kiểm địa chỉ LAN
(`ipconfig getifaddr en0`) xem router có đổi IP của Mac không.

---

## Chưa có: đường vào từ ngoài internet

Hôm nay hệ thống **chỉ chạy trong mạng phòng khám**. Trước đây có một script bật
`tailscale funnel` phơi thẳng cổng 3000 ra internet — nó đi vòng qua Caddy nên
mất hết lớp bảo vệ ở đó, và đã được bỏ (xem [len-vps.md](len-vps.md)).

Muốn vào từ xa, hai đường:
- **Tailscale** cho nhân viên: máy nào cài Tailscale và cùng tài khoản thì vào
  được, không phơi gì ra internet.
- **Tên miền thật + Caddy**: đặt `SITE_ADDRESS=phongkham.example.com` trong
  `.env.prod`, trỏ tên miền về, Caddy tự xin chứng chỉ HTTPS. Đây là đường đúng
  khi lên VPS.
