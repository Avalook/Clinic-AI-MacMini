# STAGING ONLINE — https://staging.dr4women.io.vn

Dựng 01/10/2026 (Tuyền chốt). Bản thử giống prod để mọi người vào kiểm, bấm
"nghịch" thoải mái cho ra lỗi — trước khi một thay đổi lên prod.

## Ai vào, đăng nhập thế nào

- Ai có **tài khoản prod** là vào được, bằng **đúng email + mật khẩu prod**
  (tài khoản nạp nguyên từ bản sao lưu, không đổi mật khẩu). Không có đăng ký mới.
- Đầu mọi trang có dải vàng **"STAGING — bản thử, dữ liệu khách đã che"**.
  Không thấy dải → bạn đang ở PROD.
- Đổi mật khẩu trên staging **không** đổi ở prod, và bị ghi đè lại đêm đó.

## Dữ liệu

- Mỗi đêm **03:30** nạp lại từ bản sao lưu prod 02:15 (`staging-nap-ban-sao.sh`,
  hẹn giờ `clinicai-staging-nap.timer`). Mọi thứ bấm trên staging **mất** sau đêm đó.
- **Giữ nguyên:** nhân sự, tài khoản, phòng, lịch trực, dịch vụ, giá, kho, mã khách
  (BN-…), giới tính, tỉnh/phường, nội dung khám.
- **Đã che (dữ liệu khách):** tên → "Khách 0001" (số ổn định qua các đêm), SĐT →
  09/08/07…xxxxxxxx giả, CCCD giả, ngày sinh lệch ±14 ngày, địa chỉ → "Số n đường
  Thử", người thân, kênh liên lạc, người giới thiệu, ghi chú tự do về khách, nội
  dung CSKH, phản hồi, tin nhắn → "(đã che)". Tên khách nằm trong thông báo / văn
  bản khám / JSON sự kiện được thay bằng tên giả; mọi SĐT, email trong văn bản →
  giả. Danh sách cột đầy đủ: bảng `_che_cot` trong `scripts/staging-che-du-lieu.sql`.
  Nạp + che là **một giao dịch** — dữ liệu chưa che không bao giờ nằm lại staging.
- **Phiên đăng nhập được giữ qua đêm nạp lại (02/10):** `TRUNCATE auth.users CASCADE`
  xoá cả `auth.sessions` / `refresh_tokens`, nên script chép chúng ra bảng tạm trước
  và trả lại (chỉ phiên của tài khoản còn tồn tại) trong cùng giao dịch — sáng ra
  không ai phải đăng nhập lại. Trả lại hỏng thì chỉ in cảnh báo, nạp lại vẫn chạy
  (không giữ được phiên ≠ không có staging). Nếu phiên vẫn mất (đổi mật khẩu, GoTrue
  mất dữ liệu…), ứng dụng tự đưa người dùng về `/login` kèm câu "Phiên đăng nhập đã
  hết — vui lòng đăng nhập lại" thay vì để họ kẹt ở màn cũ (`lib/het-phien.ts`).
- **Không có** ảnh / video / PDF kết quả (không chép kho Viettel) — màn hiện
  "không có tệp" là đúng. Tệp tải lên staging nằm ở `~/clinicai-staging-data`.
- **Không gửi gì ra ngoài:** không khoá Telegram / Zalo / SMS / POS / AI thật
  (`scripts/lib/staging-chung.sh` từ chối chạy nếu thấy).

## Kiến trúc (kiểu `chung` — mặc định, chung VPS `clinic-vps-moi`)

```
khách ─► Caddy PROD (TLS cho cả hai tên miền)
           ├─ dr4women.io.vn          ─► prod (như cũ)
           └─ staging.dr4women.io.vn  ─► [mạng cầu clinicai_staging_edge]
                                           ─► Caddy STAGING (clinicai-staging-cong)
                                                ├─ /auth/v1 /rest/v1 ─► Supabase staging
                                                └─ còn lại ─► dashboard ─► api ─► Postgres staging
```

| | prod | staging |
|---|---|---|
| Thư mục code | `~/clinicai` (nhánh main) | `~/clinicai-staging` (clone riêng, đứng tách rời) |
| Compose project | `clinicai_prod`, `clinicai_db` | `clinicai_staging`, `clinicai_stg_db` |
| Database | `clinicai_db` | `clinicai_stg_db` (volume riêng) |
| Env | `.env.prod` | `.env.staging` (khoá JWT/DB/API riêng) |
| Ảnh | `:prod` | `:staging` |
| Khoá deploy | `/tmp/clinicai-deploy.lock` | `/tmp/clinicai-staging-deploy.lock` |

Thứ duy nhất dùng chung là **Caddy prod**: nó đọc thêm `caddy/them/staging.caddy`
(tệp không theo git, script viết) và được nối vào mạng cầu. Mạng cầu chỉ có hai
Caddy — không database, không api nào của hai bên.

### Chốt bảo vệ prod (chung máy)

- `mem_limit` từng container: ứng dụng 896m + Supabase 624m = 1520m (Realtime tắt).
  Đo local lúc rảnh: ~370MiB + ~185MiB.
- `oom_score_adj` 800–900: máy hết RAM thì kernel giết staging trước (prod = 0).
- `cpu_shares` 256 (prod 1024). Hẹn giờ nạp chạy `Nice=19`, `IOSchedulingClass=idle`.
- Dựng ảnh bằng builder buildx **riêng** có trần RAM (`STG_BUILDER_RAM`, mặc định
  3g — `next build` đo đỉnh 2,6GiB; trần 1,4G bị giết sau 10 giây) + `cpu-shares`
  128, dựng từng ảnh một; client chạy `nice -n 19 ionice -c3`. (`nice` một mình
  KHÔNG đủ: `docker build` chỉ gửi lệnh, việc dựng chạy trong buildkitd.)
  Trong lúc dựng, ứng dụng staging TẠM TẮT (trả RAM); cần RAM khả dụng ≥ trần
  builder + 768MB chừa cho prod, thiếu thì bật lại bản cũ và dừng.
- Từ chối dựng/deploy khi: RAM khả dụng < 2,5G · đĩa trống < 8G · prod đang
  deploy. Sau mỗi deploy dọn ảnh staging treo + bộ nhớ tạm builder staging.
- Postgres staging nhỏ (`shared_buffers=64MB`, `max_connections=60`) nhưng
  `max_locks_per_transaction=256` — xem sự cố 08/10 dưới đây. Mọi tham số nằm
  ở `command:` của `db` trong `docker-compose.supabase.staging.yml`, **không**
  `ALTER SYSTEM` (nằm trong volume, dựng lại là mất; tham số dòng lệnh cũng
  thắng `postgresql.auto.conf`).

### Sự cố 08/10/2026 — nạp lại hỏng "out of shared memory"

`staging-nap-ban-sao.sh` bước 4 nạp + che trong MỘT giao dịch: DROP schema
public (khoá mọi bảng/chỉ mục/toast CŨ) rồi tạo lại ~300 bảng (khoá mọi đối
tượng MỚI), giữ hết tới COMMIT. Đếm 08/10 trên khuôn test 150 bảng: ~840 quan
hệ (533 chỉ mục, 140 toast) → lược đồ prod ~300 bảng cỡ 2.000–2.500 quan hệ,
cũ + mới ≈ 5.000 khoá. Bảng khoá chung chỉ có `max_locks_per_transaction ×
max_connections` = 64 × 60 = 3.840 chỗ → hỏng "out of shared memory … increase
max_locks_per_transaction" (giao dịch rollback, staging giữ dữ liệu đêm trước).
Vá tạm bằng `ALTER SYSTEM` + restart, rồi đưa vào compose: 256 → 15.360 chỗ
(dư ~3 lần, tốn thêm vài MB). Lỗi quay lại thì tăng tiếp ở compose, đừng tách
giao dịch (tách là mất "che xong mới commit"). CI không cần: job database và
`test-nhanh.sh` áp migration từng tệp, mỗi tệp một giao dịch nhỏ.

## Lệnh (gõ từ Mac)

Dựng lần đầu / dựng lại (chạy lại được; đòi prod đã deploy bản có `caddy/them`):

```bash
ssh clinic-vps-moi "git -C ~/clinicai fetch -q origin && git -C ~/clinicai show origin/main:scripts/staging-dung-lan-dau.sh > /tmp/stg-dung.sh && bash /tmp/stg-dung.sh"
```

Đưa một PR / nhánh lên staging (mặc định main):

```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && ./scripts/deploy-staging.sh 301"
ssh clinic-vps-moi "cd ~/clinicai-staging && ./scripts/deploy-staging.sh claude/ten-nhanh"
```

Nhánh có migration mới: deploy xong chạy thêm (database STAGING):

```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && CLINIC_DB_CONTAINER=clinicai_stg_db ./scripts/apply-pending-migrations.sh --apply"
```

Nạp lại dữ liệu ngay (không chờ đêm):

```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && ./scripts/staging-nap-ban-sao.sh"
```

Xem lần nạp / deploy gần nhất:

```bash
ssh clinic-vps-moi "tail -5 ~/.local/state/clinicai-staging-nap.log ~/.local/state/clinicai-staging-deploy.log; systemctl list-timers clinicai-staging-nap.timer --no-pager"
```

### Tắt staging

Tạm dừng (giữ dữ liệu, bật lại bằng `up -d` hoặc `deploy-staging.sh`):

```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && sudo systemctl disable --now clinicai-staging-nap.timer && CLINIC_ENV_FILE=.env.staging docker compose --env-file .env.staging -f docker-compose.yml -f docker-compose.staging.yml -p clinicai_staging stop && docker compose --env-file .env.staging -f docker-compose.supabase.yml -f docker-compose.supabase.staging.yml -p clinicai_stg_db stop"
```

Gỡ hẳn site khỏi Caddy prod (khởi động lại Caddy prod ~1–2 giây):

```bash
ssh clinic-vps-moi "rm ~/clinicai/caddy/them/staging.caddy && docker exec clinicai_prod-caddy-1 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && docker restart clinicai_prod-caddy-1"
```

### Hẹn giờ (khi không có sudo không mật khẩu)

`staging-dung-lan-dau.sh` tự cài nếu `sudo -n` được. Không thì chép tay
`scripts/systemd/clinicai-staging-nap.{service,timer}` vào `/etc/systemd/system/`
(thay `@STAGING_DIR@`, `@USER@`, `@STAGING_KIEU@`), rồi
`sudo systemctl daemon-reload && sudo systemctl enable --now clinicai-staging-nap.timer`.

## Kiểu `rieng` (VPS riêng cho staging)

`STAGING_KIEU=rieng STAGING_REPO_URL=… BAN_SAO_SSH=clinicai@222.255.214.133 bash staging-dung-lan-dau.sh`
— Caddy staging tự nghe 80/443 và xin TLS; bản sao lưu kéo bằng `rsync` CHỈ ĐỌC
từ prod (nên khoá ssh hạn chế bằng `rrsync -ro` trên prod). Sổ migration lấy
theo git (`SO_MIGRATION=theo-git`, gần đúng) vì không đọc được database prod.
Viettel CFS gắn được thì đặt `BAN_SAO_DIR` trỏ thư mục sao lưu trên CFS.

## Rủi ro — đọc trước khi mở cho nhiều người

1. **Chung máy với prod.** Đã có trần RAM/CPU + giết-trước; vẫn là cùng đĩa,
   cùng mạng ra ngoài. Deploy staging lúc đông khách: tránh (dựng ảnh ăn CPU vài
   phút dù đã hạ ưu tiên).
2. **Lộ staging = lộ BĂM mật khẩu prod** (bcrypt, `auth.users`). Bcrypt chậm bẻ
   nhưng mật khẩu yếu vẫn rơi. Vì vậy: không đăng ký công khai (GoTrue tắt
   signup), chỉ người có tài khoản prod; giới hạn dò mật khẩu `auth-guard` như
   prod; khoá JWT riêng (token staging không dùng được ở prod và ngược lại).
3. **Che dữ liệu không tuyệt đối:** tên khách viết kiểu khác (chỉ tên gọi, viết
   tắt) trong văn bản khám có thể sót — ghi chú tự do vì vậy bị thay hẳn. Cột
   định danh mới ở migration sau → test `test_staging_che_du_lieu.py` đỏ cho tới
   khi được xếp loại.
4. **Sổ migration:** lấy từ database prod (SELECT). Migration áp lên prod SAU
   02:15 thì staging thiếu nó tới đêm sau.
5. **Rollback deploy prod** chạy compose từ bản sao `git archive` (không có
   `caddy/them/staging.caddy`) → site staging mất tới lần deploy prod sau, hoặc
   chạy lại lệnh dựng lần đầu.
