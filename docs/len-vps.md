# Chuẩn bị lên VPS

Kiểm ngày 04/08/2026 trên chính máy Mac mini đang chạy production.

**Kết luận ngắn:** phần *mã nguồn* gần như đã sẵn sàng. Vướng nằm ở *vận hành* —
và có một thứ phải sửa trước khi nghĩ đến VPS, vì nó đang làm hỏng chính việc
triển khai hôm nay.

---

## 1. PHẢI SỬA TRƯỚC — hai stack đang tranh nhau một tên

Có **hai bộ triển khai khác nhau** cùng dùng tên project `clinicai_prod`:

| Container | Được dựng từ |
|---|---|
| `clinicai_prod-api-1` | `~/clinic-server/Clinic-AI-Dr4Women` ← **thư mục cũ** |
| `clinicai_prod-dashboard-1` | `~/clinic-server/Clinic-AI-Dr4Women` ← **thư mục cũ** |
| `clinicai_prod-caddy-1` | `~/Projects/Dr4Women-MacMini` ← repo này |
| `clinicai_prod-dozzle-1` | repo này |
| `clinicai_prod-uptime-kuma-1` | repo này |

Thủ phạm: `/Library/LaunchDaemons/com.dr4women.clinic-backend.plist` chạy
`clinic-backend-boot.sh` của thư mục cũ **mỗi 300 giây**, dựng lại `api` và
`dashboard` theo `docker-compose.prod.yml` cũ.

### Ba hệ quả đo được

**a) Cổng mở ra toàn mạng LAN.** File cũ khai `"8000:8000"` và `"3000:3000"` —
tức `0.0.0.0`. Bất kỳ ai trong mạng gọi thẳng API được, **bỏ qua Caddy**. Trên
VPS công khai thì đó là mở API ra internet. Đây cũng là lý do cổng "mở lại" sau
mỗi lần sửa: 5 phút sau nó tự dựng lại.

```bash
docker compose --env-file .env.prod -p clinicai_prod up -d --dry-run
#  → Container clinicai_prod-api-1 Recreate      ← không khớp repo này
#  → Container clinicai_prod-dashboard-1 Recreate
```

**b) Đường vào công khai KHÔNG đi qua Caddy.** Script cũ dựng **Tailscale
Funnel** phơi thẳng `localhost:3000`:

```
# Funnel on:
#     - https://mac-mini-ca-quang.tailc94236.ts.net
```

Nghĩa là cấu hình TLS/ingress trong `caddy/Caddyfile` của repo này **không nằm
trên đường đi thật**. (Hiện Tailscale đang dừng nên chưa ai vào được từ ngoài —
nhưng cấu hình vẫn còn, và script tự bật lại mỗi 5 phút khi Tailscale chạy.)

**c) Deploy của repo này chỉ thắng được vài phút.** `deploy-backend.sh` build
image mới và `up -d` — nhưng lượt chạy tiếp theo của LaunchDaemon lại áp cấu
hình cũ đè lên. Code thì mới (cùng tag image `clinicai-api:prod`), *cấu hình*
thì cũ. Đó là kiểu hỏng khó tìm nhất: chạy đúng, nhưng không phải thứ mình khai.

### Cách sửa (cần mật khẩu máy — Quang tự chạy)

```bash
sudo launchctl bootout system /Library/LaunchDaemons/com.dr4women.clinic-backend.plist
sudo mv /Library/LaunchDaemons/com.dr4women.clinic-backend.plist ~/Desktop/com.dr4women.clinic-backend.plist.tat
tailscale funnel --https=443 off
```

Rồi dựng lại đúng theo repo này:

```bash
./scripts/deploy-backend.sh prod
docker inspect clinicai_prod-api-1 --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
# phải in ra .../Projects/Dr4Women-MacMini
docker compose --env-file .env.prod -p clinicai_prod ps --format "{{.Service}} {{.Ports}}"
# api và dashboard KHÔNG được có 0.0.0.0
```

Đừng xoá thư mục `~/clinic-server` cho tới khi stack mới chạy ổn vài ngày.

---

## 2. Mã nguồn — đã sẵn sàng

Đã soi và **không** thấy thứ chặn đường:

| Kiểm | Kết quả |
|---|---|
| Đường dẫn `/Users/...` trong compose | không có |
| Mount thư mục máy trong volume | không có (đều là named volume) |
| Ghim kiến trúc CPU (`platform:`) | không có — build được cả arm64 lẫn amd64 |
| Cấu hình qua biến môi trường | có, toàn bộ |
| Schema trong git | có, `supabase/migrations/*.sql` |

Chỗ duy nhất mang dấu vết macOS là các script prepend đường Homebrew
(`/opt/homebrew/...`). Trên Linux, một mục PATH không tồn tại bị bỏ qua nên
không hỏng; `deploy-backend.sh` đã có sẵn `CLINIC_PATH_PREFIX` để đè.

---

## 3. Việc phải làm khi lên VPS

Theo thứ tự.

### 3.1 Trước khi chuyển
1. Sửa mục 1 ở trên, chạy 2–3 ngày để chắc stack repo này đứng vững một mình.
2. **Chép bản sao lưu ra khỏi máy Mac.** Hiện bản lưu chỉ nằm trên đúng ổ đĩa
   của máy — Mac hỏng là mất cả hệ thống lẫn bản lưu. Xem
   [khoi-phuc-du-lieu.md](khoi-phuc-du-lieu.md).
3. Diễn tập khôi phục một lần vào project Supabase mới (phần `auth` là phần
   duy nhất chưa được kiểm đầu-cuối).

### 3.2 Chọn máy
- 2 vCPU / 4GB RAM là dư cho tải hiện tại (Mac mini đang dùng CPU 5%).
- **Đặt ở Singapore.** Không phải vì VPS, mà vì database: Seoul → Việt Nam đo
  được 74,5ms mỗi vòng, Singapore 55,6ms. Nếu chuyển Supabase sang Singapore
  thì VPS cũng nên ở đó — hai đầu cùng vùng thì độ trễ giữa app và DB gần như
  bằng 0, và đó mới là con số đáng kể chứ không phải 19ms kia.

### 3.3 Trên VPS
1. Cài Docker + compose plugin. **Không cần Colima** (đó là thứ của macOS).
2. `git clone` repo, tạo `.env.prod` (không bao giờ commit).
3. Trỏ tên miền thật vào VPS, đặt `SITE_ADDRESS` — Caddy tự xin chứng chỉ
   Let's Encrypt. Đây là lúc `caddy/Caddyfile` bắt đầu thật sự làm việc của nó.
4. `./scripts/deploy-backend.sh prod`
5. Dựng lại lịch sao lưu (LaunchDaemon là của macOS; trên Linux dùng systemd
   timer hoặc cron).
6. Bật tường lửa: chỉ mở 80/443 và cổng SSH. `ufw default deny incoming`.

### 3.4 Đừng mang theo
- `com.dr4women.clinic-backend.plist` và `clinic-backend-boot.sh` — vòng tự
  chữa 5 phút đó sinh ra để vá một máy để bàn hay ngủ. VPS không ngủ, và
  `restart: unless-stopped` của Docker đã làm đúng việc đó.
- Tailscale Funnel — trên VPS có IP công khai và tên miền thật, Caddy vào thẳng.

---

## 4. Còn hở, không phải việc của mã nguồn

| Việc | Vì sao gấp |
|---|---|
| **FileVault đang Tắt** | Ổ không mã hoá, trong đó có bệnh án thật. Chỉ Quang bật được. |
| Bản lưu chỉ nằm trên máy Mac | Mất máy là mất cả hai |
| Secret nằm ở `.env.prod` trên đĩa | Trên VPS nên dùng kho secret, hoặc ít nhất chmod 600 + ổ mã hoá |
| Supabase gói Free | Không PITR, không backup tự động, compute NANO |
| `uptime-kuma` báo unhealthy | Đang không giám sát được gì |
