# ClinicAI — Sổ tay Vận hành (Ops Runbook)

> Tài liệu dành cho người quản trị hệ thống. Đọc trong 5 phút, xử lý sự cố trong 10 phút.

---

## 1. Kiểm tra nhanh trạng thái hệ thống

```bash
# Xem toàn bộ trạng thái (Docker, containers, health, link public)
./scripts/server-status.sh

# Hoặc kiểm tra nhanh từng phần:
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod ps
docker exec clinicai_prod-api-1 curl -fsS http://localhost:8000/health
docker exec clinicai_prod-api-1 curl -fsS http://localhost:8000/health/db
curl -fsS http://127.0.0.1/health
curl -sS http://127.0.0.1/enter -o /dev/null -w "%{http_code}\n"
```

---

## 2. Deploy / Cập nhật code

### Tự động (khuyến nghị)
Push code lên nhánh `main` → GitHub Actions CD pipeline tự động chạy trên Mac mini.

### Thủ công
```bash
cd ~/Projects/Dr4Women-MacMini
./scripts/deploy-backend.sh prod      # Deploy production
./scripts/deploy-backend.sh staging   # Deploy staging
```

Script sẽ tự động:
1. `git pull` code mới
2. Build Docker images
3. Khởi động containers mới
4. Health check (120s timeout)
5. **Rollback tự động** nếu health check fail

---

## 3. Rollback (quay lại phiên bản cũ)

Deploy script đã có rollback tự động. Nếu cần rollback thủ công:

```bash
# Xem các image có sẵn
docker images | grep clinicai

# Tag lại image cũ (lấy IMAGE ID từ lệnh trên)
docker tag <old-api-image-id> clinicai-api:prod
docker tag <old-dashboard-image-id> clinicai-dashboard:prod

# Khởi động lại với image cũ
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod up -d
```

---

## 4. Sao lưu & Khôi phục Database

### Backup thủ công
```bash
./scripts/backup-db.sh
# Output: .sql.gz + .sql.gz.manifest (both are required)
```

### Backup tự động
LaunchDaemon chạy hàng đêm lúc 2h sáng. Kiểm tra:
```bash
tail -20 ~/Library/Logs/clinicai-backup.log
ls -lh ~/backups/clinicai/
```

### Khôi phục từ backup
```bash
./scripts/restore-db.sh ~/backups/clinicai/<backup>.sql.gz staging
# Prod additionally requires ALLOW_PROD_RESTORE=1 and "RESTORE PROD".
# This is a public-schema application backup, not a replacement for Supabase
# PITR/auth/platform backup.
```

Restore the Supabase platform/auth backup first: `staff.auth_user_id` has a
foreign key to `auth.users`, so the public application dump correctly fails
closed if those identities are absent. Then restore the public dump into an
otherwise empty database.

Last drill: **2026-07-17**, disposable PostgreSQL 17. A fresh production public
backup passed gzip + SHA-256 manifest checks and restored transactionally after
the Auth IDs prerequisite; `patient`, `appointment`, `staff`, and `event_log`
row counts matched production exactly. This verifies the application-data
artifact only—not Supabase login/PITR recovery, which still needs a separate
platform restore drill.

---

## 5. Xem Log

### Ops Center — màn hình theo dõi chung

Tài khoản `MANAGEMENT` mở **Vận hành hệ thống** (`/ops`) trong dashboard để xem:

- health của API/database/Caddy và restart count của container;
- độ trễ database, dung lượng SSD, backup gần nhất;
- port exposure, Caddy/Funnel và trạng thái bảo vệ Dozzle;
- số lượng warning/error 15 phút gần nhất (không đọc nội dung log);
- liên kết sang Dozzle, Uptime Kuma và Sentry ở tab riêng.

Collector chạy trên host, ghi snapshot allowlist một chiều; API chỉ mount file
đó read-only và không nhận Docker socket. Chạy thủ công:

```bash
python3 scripts/collect_ops_status.py prod
# staging: python3 scripts/collect_ops_status.py staging
```

Cài collector 60 giây/lần trên Mac mini (sửa đường dẫn/UserName trong plist nếu
clone hoặc tài khoản khác):

```bash
sudo cp scripts/launchdaemons/com.dr4women.ops-status.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.dr4women.ops-status.plist
sudo launchctl bootstrap system /Library/LaunchDaemons/com.dr4women.ops-status.plist
```

`OPS_STATUS_DIR` phải là đường dẫn host tuyệt đối, dùng chung giữa collector,
backup script và bind mount Compose. Snapshot quá 3 phút chuyển cảnh báo; quá
10 phút được coi là hết hạn. Thiếu snapshot không làm hỏng luồng khám bệnh.

### Dozzle (giao diện web)
Truy cập qua Tailscale: `http://localhost:8888`

### Terminal
```bash
# Tất cả container
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod logs -f --tail=100

# Chỉ API backend
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod logs -f api

# Chỉ Dashboard
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod logs -f dashboard

# Tìm lỗi
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod logs api | grep '"level": "error"'

# Tìm theo request-id
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod logs api | grep "abc12345-request-id"

# Log tự khởi động
tail -50 ~/Library/Logs/clinic-backend-boot.log
```

---

## 6. Sự cố thường gặp

### 🔴 Mất điện / Mac mini tắt đột ngột
**Không cần làm gì.** Hệ thống tự phục hồi:
1. macOS tự bật lại (Energy Saver → "Start up after power failure")
2. LaunchDaemon tự khởi Colima + Docker containers
3. Health check chạy mỗi 5 phút để đảm bảo

Kiểm tra sau khi bật lại:
```bash
./scripts/server-status.sh
```

### 🔴 API trả 503 (Database tạm mất)
**Nguyên nhân:** Supabase Cloud tạm thời không kết nối được (mạng hoặc maintenance).
**Xử lý:** Đợi 2-5 phút. API có retry tự động (3 lần) và sẽ tự phục hồi khi Supabase khả dụng trở lại.

Kiểm tra:
```bash
docker exec clinicai_prod-api-1 curl -fsS http://localhost:8000/health/db | python3 -m json.tool
```

### 🔴 Ổ cứng SSD đầy
```bash
# Kiểm tra dung lượng
df -h /

# Dọn Docker (chạy ngay)
./scripts/docker-cleanup.sh

# Kiểm tra backup chiếm bao nhiêu
du -sh ~/backups/clinicai/
```

### 🔴 Container bị restart loop
```bash
# Xem lý do
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod logs --tail=50 <service-name>

# Reconcile/restart an toàn; không hạ toàn bộ stack trước
./scripts/deploy-backend.sh prod
```

### 🟡 Sentry báo lỗi nhiều
Truy cập [sentry.io](https://sentry.io) → xem stack trace, request_id → tìm trong log.

---

## 7. Bảo dưỡng định kỳ

| Tần suất | Việc | Tự động? |
|---|---|---|
| **Hàng đêm** (2h sáng) | Backup DB | ✅ LaunchDaemon |
| **Hàng tuần** (CN 3h sáng) | Dọn Docker cache | ✅ LaunchDaemon |
| **Mỗi 5 phút** | Kiểm tra containers + self-heal | ✅ LaunchDaemon |
| **Hàng tháng** | Cập nhật macOS + Docker | ❌ Thủ công |
| **Hàng tháng** | Review Sentry errors | ❌ Thủ công |
| **Hàng quý** | Kiểm tra SSD health + UPS | ❌ Thủ công |

---

## 8. Cài đặt LaunchDaemon (lần đầu)

```bash
# Backend tự khởi động (đã cài rồi)
sudo cp scripts/launchdaemons/com.dr4women.clinic-backend.plist /Library/LaunchDaemons/ 2>/dev/null

# Backup DB hàng đêm
sudo cp scripts/launchdaemons/com.dr4women.db-backup.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/com.dr4women.db-backup.plist

# Docker cleanup hàng tuần
sudo cp scripts/launchdaemons/com.dr4women.docker-cleanup.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/com.dr4women.docker-cleanup.plist

# Kiểm tra đã cài
sudo launchctl list | grep dr4women
```

---

## 9. Liên hệ khẩn cấp

| Vai trò | Liên hệ |
|---|---|
| Quản trị hệ thống | (Điền tên + SĐT) |
| Supabase Support | [supabase.com/dashboard](https://supabase.com/dashboard) |
| Sentry Dashboard | [sentry.io](https://sentry.io) |
| Uptime Kuma | `http://localhost:3001` (qua Tailscale) |

---

## 10. Kiến trúc tham chiếu nhanh

```
Internet → Cloudflare Tunnel → Caddy (:80) → Dashboard (:3000)
                                                 ↓ (internal)
                                              API (:8000) → Supabase Cloud (DB)
                                                 ↓
                                         Worker (--relay) → Telegram Bot
```

| Port | Service | Truy cập |
|---|---|---|
| 80/443 | Caddy (ingress) | Public (qua tunnel) |
| 3000 | Next.js Dashboard | Internal only |
| 8000 | FastAPI API | Internal only |
| 3001 | Uptime Kuma | Tailscale (127.0.0.1) |
| 8888 | Dozzle (logs) | Tailscale (127.0.0.1) |
