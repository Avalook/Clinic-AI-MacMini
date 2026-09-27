# Kế hoạch theo dõi lỗi & sức khoẻ hệ thống (27/09/2026)

Tuyền 27/09: *"check kĩ toàn bộ logic, luồng, sức khoẻ của hệ thống, plan xem hệ thống
chuyên nghiệp để theo dõi và biết lỗi phát sinh là gì mà thu thập lỗi còn sửa"*.

**Khuôn:** `docs/SO-LUAT.md` Phần 7 — Postgres là hạ tầng có trạng thái DUY NHẤT; không
Redis / Loki / ES / Grafana / GlitchTip ở quy mô ~1 lượt gọi/giây, một người vận hành.
Bộ canh gác chạy ghép trong worker `su-kien` (vốn bắt buộc chạy); Kuma canh độc lập
(API canh worker, Kuma canh API).

**Quyết định 27/09 (Tuyền):** thu lỗi TỰ DỰNG trong Postgres (không Sentry — dữ liệu y
tế, NĐ 13/2023); đổi log driver sang **journald**; **lọc SĐT/tên khỏi log Caddy**; **kênh
Telegram riêng** `TELEGRAM_OPS_CHAT_ID` (Tuyền/Quang tạo nhóm và đặt biến trên VPS).

## Đo prod 27/09 (chỉ đọc)

| Mục | Kết quả |
|---|---|
| Máy | tải 0.17, đĩa 35%, RAM trống 5.4 GB, mọi container healthy, TLS tới 15/12/2026 |
| Đường sự kiện | 0 chờ / 0 chết; p95 giao ~1s; không hẹn giờ chết |
| Tiền / kho | 0 phiếu CK chờ quá 30 phút; 0 tồn kho âm |
| **Hàng chờ ma** | 4 chỗ chờ của khách đã về — LỖI THẬT, đã sửa (PR #207, migration 20260927000001) |
| Lượt treo | 35 lượt mở quá 24h (FINALIZED chưa check-out, IN_PROGRESS 17–25/09) — không gì nhắc chốt ngày |
| Log | log API mất mỗi lần deploy (còn 35 dòng) |
| Sentry | tắt (đúng quyết định) |
| **Kuma** | **RỖNG HOÀN TOÀN** (đo lại 27/09 bằng sqlite3 trong container): 0 monitor, 0 tài khoản, 0 kênh báo — từ ngày chuyển VPS mới (16/09) **không có gì canh hệ thống**. `monitors.json` chỉ nằm trên giấy. Dựng lại cần tạo tài khoản quản trị → **Tuyền làm** (Claude không tạo tài khoản) |
| Collector `/ops` | không có lịch trên VPS mới → tab Hệ thống cũ mãi |
| Tài khoản thử | 3 tài khoản `@dr4women.local` còn trên prod (mật khẩu trong git) — dọn khi bàn giao |
| **Hạn hợp đồng** | **Viettel CFS 16/10/2026** (nơi lưu ảnh/video kết quả) · DBaaS 07/11/2026 · tên miền 16/09/2027 |

## Những gì hiện trôi qua không ai biết

500 ở endpoint ít dùng (mất khi deploy, người dùng không có mã lỗi) · React crash trong
trình duyệt · worker su-kien chết/treo (Kuma không canh, deploy không kiểm, unhealthy
không tự restart) · DEAD của sự kiện SYSTEM · bất biến tiền/lâm sàng trên prod · ổ CFS
rớt (chỉ lộ khi tải lên) · WAL bị slot giữ · query chậm · hợp đồng hết hạn.

## Pha 0 — một ngày  (✅ xong · ☐ chưa)

- ✅ `GET /health/su-kien` — 503 khi tin TỚI HẠN quá 3' chưa ai giao (đo theo tới hạn,
  không theo "lần giao cuối": giờ vắng worker im cả tiếng là bình thường), tin tồn >15',
  DEAD / hẹn giờ chết 24h, hẹn giờ trễ. Chỉ số đếm. + monitor trong `monitors.json` +
  `su-kien` vào `health_ok` của deploy + collector / schema / màn /ops +
  `test_theo_doi_du_moi_service.py` (thêm service có healthcheck mà thiếu một chỗ → đỏ).
- ✅ Mã lỗi: 500 trả "… (mã lỗi abcd1234) …" + `request_id` + header `X-Request-ID`
  (handler 500 nằm NGOÀI RequestIdMiddleware — lấy mã từ structlog contextvars); proxy
  Next đặt mã từ phía nó (502 "không kết nối được" cũng có mã); mã từ ngoài chỉ nhận khi
  đúng dạng `[A-Za-z0-9-]{8,64}` (chống chèn rác vào log).
- ✅ Lọc log: Caddy cắt NGUYÊN `?…` khỏi `request>uri` và `Referer` ở CẢ access log lẫn
  log lỗi (`log default` — dòng "dial dashboard hỏng" in nguyên uri, đo thật bằng
  container); uvicorn access cũng cắt `?…` (bộ che cũ bắt SĐT, không bắt TÊN).
  **Không đổi `check-phone` / `check-duplicate` sang POST**: lọc ở hai tầng log là đủ —
  Next không ghi log request, `fetch()` không vào lịch sử trình duyệt.
- ✅ journald: `docker-compose.journald.yml`, deploy chỉ gắn khi máy chủ có
  `/var/log/journal` (Docker Desktop không có journald). ☐ **Bước máy chủ** (sudo):
  bật journal lưu bền + `SystemMaxUse=2G` + `RateLimitBurst` rộng — chạy riêng, có xem.
- ✅ Dọn công cụ nói sai: `suc-khoe.sh` trỏ VPS mới + HTTPS (cũ in "308 ✗" cho hệ thống
  khoẻ), bỏ dòng staging (máy mới không có), nói thẳng "Kuma KHÔNG có monitor nào",
  đọc đúng thư mục sao lưu, thêm dòng `/health/su-kien`; sửa câu Sentry ở SO-LUAT 8.3 /
  GIAI-THICH-CODE / error.tsx. ☐ Monitor TLS: đi cùng lúc Tuyền dựng lại Kuma.
- ✅ Kiểm sau deploy: `deploy-status.sha` == HEAD, container vừa tạo lại (bẫy 27/09).
- ☐ Lịch cho collector `/ops` trên VPS (systemd timer) — cùng bước máy chủ ở trên.
- ☐ Relay thông báo: đổi monitor docker (cần mount docker.sock — KHÔNG) sang điểm đo
  HTTP đọc hàng `event_log` chưa giao.

## Pha 1 — một tuần

- ☐ Bảng `loi_nhom` (fingerprint, nguồn api/worker/next/trình duyệt, vị trí = route
  TEMPLATE / consumer / component, thông điệp đã khuôn, lần đầu/cuối, số lần, bản
  đầu/cuối, trạng thái MOI/DA_BIET/DA_SUA/BO_QUA) + `loi_mau` (≤20 mẫu/nhóm: request_id,
  vai, method, status, ≤10 khung stack — KHÔNG biến, KHÔNG body). Gắn ở handler 500,
  worker, hen_gio. Ghi bằng connection riêng, timeout 200ms, gộp 10s/fingerprint.
- ☐ Lỗi trình duyệt + server Next: `instrumentation-client.ts` (error,
  unhandledrejection), `app/global-error.tsx`, `instrumentation.ts` (`onRequestError`) →
  `/api/loi` → `POST /api/v1/loi-trinh-duyet` (≤4KB, chống lặp 60s/tab).
- ☐ Bộ canh gác `services/canh_gac.py` mỗi 60s trong vòng su-kien, bảng `canh_bao`
  (chỉ gửi khi ĐỔI trạng thái, đúng 2 vòng liên tiếp, nhắc ≤2h/lần mức KHẨN, trần 20
  tin/giờ, 22:00–06:30 chỉ KHẨN, tin không có PII). Luật: fingerprint mới/tái phát ·
  ≥5 lần/10' · 5xx >2%/15' · DEAD / chờ >5' · hen_gio CHET · chuông KHẨN >30' · bất
  biến · WAL >2GB · đĩa >80% · ổ CFS mất tệp đánh dấu · hợp đồng <21 ngày · tổng hợp
  pg_stat_statements hằng tuần.
- ☐ `services/bat_bien.py` — MỘT nguồn bất biến (hàng chờ ma, đã trả chưa phòng, giao
  thuốc vượt mua, xếp khác cơ sở, lượt treo qua đêm, tồn kho âm); mô phỏng import lại;
  canh gác chạy 5'/lần; CI đòi 0 sau luồng chuẩn.
- ☐ Tab "Sức khoẻ hệ thống" ở `/ops` (người đưa tin, nhóm lỗi đổi trạng thái được, bất
  biến, cảnh báo đang mở) — SITEMAP cùng commit.
- ☐ Collector systemd timer 1' trên VPS (+ su-kien, đĩa `/` và CFS, tệp đánh dấu CFS,
  ngày còn của chứng chỉ).
- ☐ Query chậm: `log_min_duration_statement=500` (log chỉ ở máy), `telemetry_5p`.
- ☐ Chốt ngày: danh sách lượt còn mở cuối ngày cho lễ tân/trưởng ca (35 lượt treo).
- ☐ Kiểm hành trình tổng hợp CHỈ ĐỌC bằng tài khoản robot (cần Tuyền duyệt tài khoản).

## Pha 2 — sau

Tra ngược source map tại máy · SLO (API 99,5% giờ mở cửa, sự kiện p95 <10s). Không
làm (có ngưỡng mở lại): GlitchTip (khi có người vận hành thứ hai hoặc >200 nhóm lỗi
mở), Loki/ES/Grafana/OTel (log >50 triệu dòng hoặc ≥2 máy phục vụ).

## Truy vấn kiểm nhanh (chỉ đọc) — xem lịch sử phiên 27/09 hoặc `services/bat_bien.py` khi xong
