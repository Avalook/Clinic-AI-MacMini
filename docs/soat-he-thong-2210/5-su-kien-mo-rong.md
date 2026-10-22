# Soát 22/10 · Khối 5 — Sự kiện + mở rộng nhiều phòng khám + vận hành

> Đang viết. Chỉ đọc code trên `main` @ `00bde52`. Không sửa code, không chạm prod.

## Tóm tắt 10 dòng

(đang soát)

## Bảng phát hiện

| # | Mức | Tệp:dòng | Phát hiện | Độ chắc | Đã biết? |
|---|---|---|---|---|---|

## (a) Sự kiện: phát, nghe, mất tin

Đã đọc đủ đường: `events/emit.py` (outbox cùng giao dịch) → `events/worker.py`
(nhận có hạn thuê, đúng thứ tự, DEAD) → `worker.py::_run_su_kien` (một vòng cho mọi
bên nhận + hẹn giờ + canh gác + agent) → trigger `notify_row_change` → `core/change_broker.py`
(một kết nối LISTEN) → `routers/events.py` (SSE) → `app/api/events/stream/route.ts`
(Next chuyển tiếp) → `RealtimeRefresher.tsx` / `dung-nghe-bang.ts`.

**Không gắn lại cờ "hàm ghi không phát sự kiện".** Báo cáo 21/10
(`docs/kiem-tra-su-kien-lego-2110/BAO-CAO.md`, nhánh `claude/repo-cleanup-process-3ce6b7`)
đã xếp từng hàm (78 hàm Python + 12 hàm SQL), và lần trước 19/20 cờ kiểu này là báo oan
vì vết nằm ở `record_event`/`_log`/`ghi_nhat_ky`/cột `…_boi`. Khối này soát phần
báo cáo ấy CHƯA soát: hạ tầng giao tin có mất tin không.

### Phần đã kiểm, ổn (đừng báo lại)

- Sự kiện ghi CÙNG giao dịch với dữ liệu (`emit.py:181-226`) → không có "ghi xong rồi
  mới phát". Mất tiến trình giữa chừng = mất cả hai, không lệch.
- Worker chết giữa chừng: dòng `IN_PROGRESS` được thu hồi sau hạn thuê 120 giây
  (`events/worker.py:283` `thu_hoi_thue`, gọi đầu mỗi vòng). Khởi động lại container
  không mất tin, chỉ trễ tối đa ~2 phút cho đúng đối tượng đang làm dở.
- Bên nhận hỏng: thử lại giãn cách, 5 lần → DEAD, không xoá; DEAD có người thật được réo
  (`worker.py:226`) và `/health/su-kien` trả 503 (`api/v1/health.py:109`) — Kuma gọi từ
  ngoài, nên su-kien chết hẳn vẫn có người biết dù canh gác nằm trong chính su-kien.
- Hẹn giờ (`events/hen_gio.py`) có thu hồi hẹn treo (`thu_hoi_hen_treo`) — cùng mẫu.
- 97 loại sự kiện khai; mọi tên bên nhận khai trong danh mục đều đã đăng ký hàm, và
  không có hàm nào đăng ký mà không khai (chạy thử import `DANH_MUC` × `_BO_XU_LY`).
- Bảng có trigger ↔ danh sách bảng ở màn: có test canh
  (`src/tests/migrations/test_realtime_trigger_matches_client.py`).
- Màn tự tải (`/ban-kham`, `/phong/[ma]`, `/hanh-trinh`, `/thu-ngan/*`) có nhịp làm mới
  riêng (`BanKham.tsx`, `PhongDichVu.tsx`, `BangHanhTrinh.tsx`, `NgayTruc.tsx`), nên
  mất tin ở dưới chỉ làm trễ, không làm màn đứng im mãi.

### A1 · VỪA · Trình duyệt TỰ nối lại SSE thì không bắt kịp quãng mù

- **Tệp:** `src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:248-259`.
- **Vì sao:** `mo(laNoiLai)` chỉ gọi `nhanTin(null)` (làm mới bắt kịp) khi
  `laNoiLai === true`, tức là khi CHÍNH mình mở lại EventSource sau lúc nó `CLOSED`.
  Nhưng đường hay gặp nhất — wifi phòng khám chớp, API/Next khởi động lại nhanh (deploy),
  Caddy cắt — là trình duyệt **tự** nối lại cùng đối tượng `e` (readyState `CONNECTING`,
  không `CLOSED`). Khi ấy sự kiện `open` bắn lại trên `e` của lần `mo(false)` đầu tiên →
  `laNoiLai` vẫn là `false` → **không bắt kịp**. Tin phát trong quãng đứt mất hẳn; SSE
  không có `id:`/`Last-Event-ID` để máy chủ gửi bù (`routers/events.py:62`).
- **Tái hiện:** mở `/reception/queue` ở máy A. Tắt wifi máy A ~10 giây; trong lúc đó máy B
  check-in một khách. Bật lại wifi: chỉ báo về "sống", nhưng hàng chờ máy A không có khách
  mới cho tới nhịp dự phòng 60 giây (`POLL_MS`, dòng 83). Với deploy API (`docker compose
  up -d api`), mọi màn đang mở cùng lúc lỡ các ghi của worker `su-kien` trong quãng đó.
- **Độ chắc:** chắc về luồng code (đọc `open` handler + hành vi chuẩn EventSource); chưa bấm thật.
- **Test đề xuất:** test thuần cho `moDong` với EventSource giả: bắn `open` → `error`
  (readyState CONNECTING) → `open` lần hai ⇒ phải có đúng một `nhanTin(null)`.
- **Hướng sửa:** trong `mo()`, đếm số lần `open` của chính `e`; lần thứ hai trở đi (hoặc
  `laNoiLai`) thì `nhanTin(null)`. Một biến cục bộ, không đổi kiến trúc.

### A2 · VỪA · Bộ nghe LISTEN của API rớt rồi nối lại thì không báo màn nào bắt kịp

- **Tệp:** `src/clinicai/core/change_broker.py:91-114`.
- **Vì sao:** khi kết nối LISTEN chết (Postgres khởi động lại, `pg_terminate_backend`,
  mạng docker chớp), broker ngủ `RECONNECT_DELAY_S=3s` rồi nối lại. NOTIFY phát trong
  quãng ấy **mất hẳn** (Postgres không giữ NOTIFY cho kết nối vắng mặt). Còn các dòng
  SSE tới trình duyệt vẫn **mở nguyên** (hàng đợi trong `_subs` không bị đụng), nên trình
  duyệt không thấy đứt → không bắt kịp (khác A1: ở đây thậm chí không có `open` nào).
  Phát hiện kết nối chết cũng chỉ dựa `conn.is_closed()` mỗi giây — nửa-mở TCP thì có
  thể không bao giờ thấy.
- **Tái hiện:** staging: mở hàng chờ; `docker restart <db>` (hoặc
  `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query LIKE 'LISTEN%'`);
  ngay sau đó check-in một khách từ máy khác trong 3 giây đầu ⇒ màn không đổi tới nhịp 60s.
- **Độ chắc:** chắc (đọc code; không có nhánh nào phát tin cho `_subs` sau khi nối lại).
- **Test đề xuất:** unit `ChangeBroker`: đăng ký 1 hàng đợi, giả lập `_run` nối lại lần 2
  ⇒ hàng đợi phải nhận một tin "bắt kịp" (`{"t": null, ...}`).
- **Hướng sửa:** sau `add_listener` thành công ở lần nối thứ hai trở đi, `put_nowait` một tin
  `{"t":null,"c":<clinic>}` cho mọi hàng đợi (client đã hiểu `t=null` = làm mới một lượt,
  `RealtimeRefresher.tsx:269-276`).

### A3 · VỪA · Một vòng su-kien cõng cả gọi LLM: tóm tắt cuối ngày chặn giao tin hàng phút

- **Tệp:** `src/clinicai/worker.py:290-329` gọi `agent_tom_tat.tu_dong(pool)` NGAY TRONG
  vòng giao tin; `src/clinicai/services/agent_tom_tat.py:236-255` gọi Anthropic
  `max_tokens=8000`, thinking bật, có thử lại (`llm/anthropic_client.py::_invoke_with_retry`);
  SDK mặc định chờ tới 600 giây/lần.
- **Vì sao:** vòng su-kien làm tuần tự: mọi bên nhận → hẹn giờ → canh gác → sổ nợ → agent →
  tóm tắt. Trong lúc đợi LLM trả lời (thường chục giây tới vài phút, lâu hơn nếu API chậm),
  **không bên nhận nào chạy**: chuông, hành trình, sổ nợ, hàng chờ sau check-in đều đứng.
  Từ `AGENT_TOM_TAT_GIO` (mặc định 18h) mỗi phòng khám một lần/ngày, hỏng thì thử lại mỗi
  30 phút (`CHO_THU_LAI_GIAY`); nhiều phòng khám thì nối đuôi nhau. Quá 3 phút thì
  `/health/su-kien` còn báo "worker chết/treo" (báo động giả).
- **Tái hiện:** staging có khoá LLM, đặt `AGENT_TOM_TAT_GIO` = giờ hiện tại, có ≥1 lượt hôm
  nay; check-in khách ngay khi log có `agent_tom_tat` bắt đầu ⇒ khách vào hàng chờ trễ đúng
  bằng thời gian gọi LLM (đo `event_delivery.processed_at - created_at`).
- **Độ chắc:** chắc về luồng (tuần tự, cùng task); thời lượng gọi LLM thật cần đo.
- **Test đề xuất:** test vòng với `tu_dong` giả ngủ 5s ⇒ một sự kiện phát giữa chừng phải
  DONE trong < 2s (sẽ đỏ hiện nay).
- **Hướng sửa:** chạy `tu_dong` bằng `asyncio.create_task` riêng (giữ một task, không chạy
  chồng), hoặc đặt `timeout` ngắn cho client tóm tắt. Không cần thêm container.
  `canh_gac`/`agent_giam_sat` cũng nên tách task riêng nếu có lúc chậm, nhưng chúng chỉ
  đọc DB nên rủi ro thấp hơn.

### A4 · VỪA · Kiểm "sự kiện cũ hơn chưa xong" không dùng được chỉ mục, và `event_delivery` không bao giờ dọn

- **Tệp:** `src/clinicai/events/worker.py:104-112` (`truoc.status <> 'DONE'`);
  chỉ mục `ix_event_delivery_theo_aggregate` ở
  `supabase/migrations/20260923000001_domain_event.sql:196-198` là chỉ mục **một phần**
  `WHERE status IN ('PENDING','RETRY')`. Không migration nào thêm chỉ mục khác hay dọn bảng
  (`grep DELETE FROM event_delivery` chỉ ra test).
- **Vì sao:** điều kiện `status <> 'DONE'` gồm cả `IN_PROGRESS` và `DEAD`, nên Postgres
  **không được** dùng chỉ mục một phần kia (điều kiện không suy ra được vị từ của chỉ mục).
  Với mỗi ứng viên, `NOT EXISTS` phải quét theo cách khác — không có chỉ mục nào bắt đầu
  bằng `(consumer, aggregate_id)` cho mọi trạng thái → quét bảng/lọc trên toàn bộ dòng
  DONE. Bảng tăng mãi (30 ngày qua 51.683 lần giao — báo cáo 21/10 — tức ~600k dòng/năm,
  nhân số cơ sở). `/health/su-kien` + canh gác còn `count(*)` không `WHERE` trên cả bảng
  mỗi phút, hai lần (`api/v1/health.py:80-91`). Hôm nay nhanh; chậm dần đều theo tháng.
- **Tái hiện / kiểm:** trên bản sao staging:
  `EXPLAIN ANALYZE` câu `_NHAN_MOT_DONG` với `$1='dong_thoi_gian_luot'` khi có ≥1 dòng PENDING
  ⇒ xem nhánh `NOT EXISTS` có `Seq Scan on event_delivery truoc` không;
  `SELECT status, count(*) FROM event_delivery GROUP BY 1`.
- **Độ chắc:** khá (đọc truy vấn + chỉ mục; kế hoạch thật cần `EXPLAIN` trên prod).
- **Test đề xuất:** test migration: có chỉ mục khớp vị từ `status <> 'DONE'`.
- **Hướng sửa (Mức 3, migration):** chỉ mục một phần
  `(consumer, aggregate_id, aggregate_version) WHERE status <> 'DONE'`; timer dọn dòng
  `DONE` cũ hơn 30 ngày (domain_event giữ nguyên — nó là sổ); đo sức khoẻ chỉ đếm dòng
  `status <> 'DONE'`.

### A5 · VỪA (khi có ≥2 cơ sở) · Tin thời gian thực chỉ lọc theo phòng khám, không theo cơ sở

- **Tệp:** trigger `notify_row_change` gửi `{"t": bảng, "c": clinic_id}`
  (`supabase/migrations/20260806000001_notify_change_for_live_screens.sql:40-43`);
  broker chia theo `clinic_id` (`core/change_broker.py:131`); route Next có gắn
  `X-Location-ID` (`app/api/events/stream/route.ts:51`) nhưng `routers/events.py` không dùng.
- **Vì sao:** mỗi lần ghi ở Kim Ngưu đánh thức MỌI màn đang mở ở Hào Nam (và ngược lại),
  mỗi màn dựng lại trang/hỏi lại API. Tải làm mới nhân theo số cơ sở × số màn. Không lộ dữ
  liệu (tin nghèo, API lọc lại) — là chuyện **tải**, không phải quyền.
- **Tái hiện:** mở hàng chờ ở cơ sở Hào Nam; bấm thao tác ở Kim Ngưu ⇒ tab Hào Nam vẫn
  gọi lại API (xem tab Network) dù dữ liệu không đổi.
- **Độ chắc:** chắc.
- **Hướng sửa:** thêm `l` (location_id, khi bảng có cột ấy) vào tin NOTIFY, broker lọc thêm
  theo `X-Location-ID`; bảng không có cột thì vẫn gửi cho cả phòng khám. Làm khi mở cơ sở thứ hai thật sự đông.

### A6 · THẤP · 11 loại sự kiện phát ra mà không bên nhận nào nghe

`capability.granted/revoked`, `clinical_shift.exception_opened/cancelled`,
`lieu_trinh.created/prepay_set/revised/session_relinked`, `patient.contacted`,
`vat_tu.nhap_cho_duyet/nhap_da_quyet` (khai ở `src/clinicai/events/catalogue.py`,
`consumers` rỗng). Chúng vẫn nằm trong sổ `domain_event` (vết đủ) nên **không phải mất
vết**; chỉ là dòng thời gian lượt (`dong_thoi_gian_luot`) và chuông không biết. Đáng
xem: `lieu_trinh.session_relinked` (báo cáo 21/10 coi đây là đường "có phát") — có phát
nhưng không ai nghe, nên dòng thời gian lượt vẫn không ghi việc gắn lại buổi.
**Hướng:** quyết từng loại: thêm `dong_thoi_gian_luot` vào consumers, hoặc ghi chú "chỉ để sổ".

### A7 · THẤP · Bên nhận làm sập tiến trình (hết RAM, segfault) sẽ bị nhận lại mãi, không bao giờ DEAD

- **Tệp:** `src/clinicai/events/worker.py:183` — chỉ nhánh `except` mới xét
  `attempts >= 5` để chuyển DEAD; `thu_hoi_thue` (dòng 283) trả về `RETRY` không xét số lần.
- **Vì sao:** tiến trình chết thì không vào `except` → dòng treo → 120s sau thu hồi →
  nhận lại (attempts 6, 7, …) → chết lại. Vòng lặp mãi, cứ 2 phút container sập một lần.
- **Độ chắc:** chắc về code; chưa từng thấy trên prod (51.683 lần giao, 0 kẹt — báo cáo 21/10).
- **Hướng sửa:** trong `thu_hoi_thue`, `status = CASE WHEN attempts >= 5 THEN 'DEAD' ELSE 'RETRY' END`.

## (c) Ổn định vận hành: sao lưu, timer, healthcheck, tự bật lại

Đã đọc: `docker-compose.yml`, `docker-compose.supabase*.yml`, `docker-compose.staging.yml`,
`scripts/systemd/*`, `scripts/backup-db.sh`, `scripts/day-sao-luu-len-viettel-storage.sh`,
`scripts/collect_ops_status.py`, `src/clinicai/services/ops_status.py`, `deploy-backend.sh`.

### Phần đã kiểm, ổn

- **Mọi container dài hạn đã có `restart: unless-stopped`** (prod, supabase qua anchor,
  staging, theo dõi). Riêng `media-quyen` là `"no"` — đúng, nó chạy một lần. Vậy sự cố
  14/10 **không** do thiếu `restart:`; repo không có tài liệu ghi nguyên nhân 14/10
  (grep `docs/` theo "14/10" chỉ ra chuyện bể kết nối). Ứng viên mạnh nhất: C1.
- `depends_on: condition: service_healthy` cho caddy → dashboard → api → db; healthcheck
  api đo `/health/db`; su-kien đo tệp nhịp tim (vòng có quay, không chỉ PID).
- Deploy chờ healthy rồi mới coi là xong, hỏng thì lùi bản (`deploy-backend.sh:372-441`).
- Timer bản đêm + nạp staging `Persistent=true`; bản 15 phút `Persistent=false` có chủ ý.
- Sao lưu: kiểm gzip, cỡ tối thiểu, dấu đủ bảng, kèm auth, đẩy CFS so sha256; chỉ dọn bản
  cũ khi lần này thành công; có `restore-drill.sh`, staging nạp lại bản sao mỗi đêm = một
  lần thử khôi phục thật.

### C1 · CAO · Máy/Docker khởi động lại trước khi ổ CFS gắn xong ⇒ api, day-tep nằm im

- **Tệp:** `docker-compose.yml:216-222` (api), `:164-169` (media-quyen), day-tep cùng kiểu:
  gắn `type: bind` cú pháp dài, nguồn `${MEDIA_DIR}/production` =
  `/mnt/viettel-cfs/clinicai-media/production` (`docs/DANG-LAM.md:1480`).
  Repo không có drop-in nào cho `docker.service` chờ ổ mạng (`After=remote-fs.target`).
- **Vì sao:** Docker bật lại container theo `restart:` ngay khi daemon lên. Nếu CIFS chưa
  gắn, `/mnt/viettel-cfs` là thư mục rỗng → thư mục con không tồn tại → container báo
  "bind source path does not exist" và **dừng hẳn** (chính sách restart không thử lại
  khi tạo container thất bại). Nếu thư mục có sẵn trên ổ VPS thì tệ kiểu khác: api gắn vào
  ổ VPS, ghi ảnh vào chỗ sai cho tới khi restart tay (DANG-LAM.md:1481 đã gặp).
- **Tái hiện (staging/máy thử, KHÔNG prod):** `sudo umount /mnt/viettel-cfs && sudo systemctl
  restart docker; docker ps -a` ⇒ api/day-tep `Exited`.
- **Kiểm trên VPS (chỉ đọc):** `journalctl -u docker --since 2026-10-14 --until 2026-10-15 | grep -iE "bind source|mount"`.
- **Độ chắc:** khá (cơ chế chắc; chưa có log 14/10 để khẳng định đây đúng là nguyên nhân).
- **Hướng sửa (Mức 3, hạ tầng):** drop-in `docker.service.d/cho-o-mang.conf`:
  `After=remote-fs.target` + `Wants=remote-fs.target` (không `Requires` — CFS chết thì prod vẫn
  phải lên), fstab có `_netdev`; thêm một kiểm sau khởi động "mọi container `running`" vào
  nhật ký vận hành.

### C2 · CAO · Khoá sao lưu là thư mục trên đĩa: bị giết giữa chừng thì sao lưu dừng vĩnh viễn, im lặng

- **Tệp:** `scripts/backup-db.sh:127-134` (`mkdir "$LOCK_DIR"` trong `BACKUP_DIR`) và
  `:89-93` (`BACKUP_DECLINED=1` thì cố ý **không** ghi trạng thái lỗi).
- **Vì sao:** SIGKILL (OOM, systemd giết lúc dừng, mất điện) không chạy `trap ... EXIT` →
  `.backup.lock` ở lại trên đĩa bền. Mọi lần sau in "DECLINED" và thoát, không ghi
  `backup-status.json`. Chỉ phép đo "bản cuối quá 26 giờ" còn bắt được — mà Kuma vẫn
  "CHỜ TUYỀN dựng" (`docs/DANG-LAM.md:140`), và canh gác không có phép kiểm sao lưu (C3).
- **Tái hiện:** `mkdir ~/backups/clinicai-15p/.backup.lock`; chờ một nhịp ⇒ log chỉ "DECLINED",
  status không đổi, /ops không đỏ.
- **Độ chắc:** chắc.
- **Test:** `scripts/tests/test-infra-safety.sh` thêm ca "khoá cũ, PID chết ⇒ vẫn sao lưu".
- **Hướng sửa:** `flock` trên tệp ở `/run` (hệ điều hành tự nhả khi tiến trình chết), hoặc ghi
  PID vào khoá và coi là cũ khi PID không sống.

### C3 · VỪA · Sao lưu hỏng hiện "không rõ" chứ không đỏ; canh gác không kiểm sao lưu

- **Tệp:** `scripts/collect_ops_status.py:195-216` đòi `completed_at` + `verified is True`,
  thiếu thì trả `None` ⇒ `/ops` hiện "unknown"; `src/clinicai/services/canh_gac.py:60-143`
  không có mã nào về sao lưu.
- **Vì sao:** `backup-db.sh` đã chịu ghi `succeeded:false`, nhưng tín hiệu ấy bị nuốt ở bộ thu.
- **Độ chắc:** chắc. **Test:** unit `collect_ops_status.backup()` với `{"succeeded": false}`
  ⇒ phải ra "failed".
- **Hướng sửa:** collector trả `failed`, ops_status coi là critical, canh gác thêm mã
  `SAO_LUU` (status quá 26 giờ hoặc failed) → có `canh_bao` + Telegram ops.

### C4 · VỪA · Unit sao lưu không giới hạn giờ, không `OnFailure=`

- **Tệp:** `scripts/systemd/clinicai-backup.service`, `clinicai-backup-15p.service`
  (`Type=oneshot`, không `TimeoutStartSec`, không `OnFailure`); bước `cp` lên ổ SMB
  (`scripts/day-sao-luu-len-viettel-storage.sh:78`) không có `timeout`.
- **Vì sao:** ổ CFS treo (SMB hay treo kiểu "D state") thì unit đứng `activating` mãi; timer
  không chạy chồng nên **mọi** lần sau bỏ lượt, và không có log lỗi nào.
- **Độ chắc:** chắc về cấu hình. **Hướng sửa:** `TimeoutStartSec=20min` (15p: `10min`),
  `timeout 600 cp …`, `OnFailure=` gọi một unit báo Telegram ops / ghi nhật ký vận hành.

### C5 · VỪA · Dọn bản sao trên CFS đếm theo NGÀY nhưng chung thư mục với bản 15 phút

- **Tệp:** `scripts/day-sao-luu-len-viettel-storage.sh:23-25` (`DICH=.../db-backups`,
  `GIU_LAI=30` "số ĐÊM") và vòng dọn `:108-118` (giữ mọi tệp của 30 ngày gần nhất).
- **Vì sao:** bản 15 phút cũng đẩy vào cùng thư mục, nên CFS giữ 30 ngày × mọi bản trong
  ngày (dump + auth + manifest) thay vì 30 bản đêm. CFS cũng là kho ảnh/video gốc: đầy ổ
  thì `day-tep` hỏng, tệp kết quả kẹt ở ổ VPS (bản duy nhất).
- **Độ chắc:** khá (đọc script; số tệp thật cần đếm).
- **Kiểm:** `ls /mnt/viettel-cfs/db-backups | wc -l; du -sh /mnt/viettel-cfs/db-backups; df -h /mnt/viettel-cfs`.
- **Hướng sửa:** bản 15 phút vào `db-backups-15p/`, giữ 2 ngày; bản đêm giữ nguyên 30.
- Gần với mục "đẩy sao lưu Viettel chọn nhầm tệp notion" trong `phat-hien.json`
  (`day-sao-luu-len-viettel-storage.sh:45`, đã sửa ở #523) nhưng **khác lỗi**.

### C6 · CAO (nghiệp vụ) · Ảnh/video kết quả trên CFS không có bản thứ hai

- **Tệp:** `scripts/backup-db.sh:349-357` — kho có `MEDIA_MARKER` thì cố ý không đóng tar.
  `docs/DANG-LAM.md:1484` đã ghi "còn hở" → **đã biết**, nhắc lại vì
  `docs/VAN-HANH-MAY-CHU.md:92` ghi hợp đồng CFS hết hạn 16/10/2026 và repo không có
  dòng nào xác nhận đã gia hạn.
- **Việc Tuyền:** xác nhận đã gia hạn CFS; chốt chỗ đặt bản thứ hai của media (rẻ nhất:
  kéo về ổ Mac cùng lúc kéo bản sao DB).

### C7 · VỪA · su-kien treo thì Docker không tự bật lại, và canh gác nằm trong chính nó

- **Tệp:** `docker-compose.yml:307-313` (healthcheck su-kien) · `src/clinicai/worker.py:290-329`.
- **Vì sao:** Docker **không** restart container `unhealthy` (chỉ restart khi tiến trình
  thoát). Canh gác chạy trong su-kien nên su-kien treo thì không tự báo. Lớp còn lại là Kuma
  gọi `/health/su-kien` — chưa dựng. Ghép với A3: gọi LLM > 120s làm healthcheck đỏ giả.
- **Độ chắc:** chắc. **Hướng sửa:** một timer systemd 1 phút: container `unhealthy` quá 3
  lần liên tiếp ⇒ `docker restart` + ghi nhật ký vận hành (một unit, không phải hạ tầng mới).
  Và dựng Kuma (đã có trong danh sách chờ).

### C8 · THẤP · Supabase tự dựng: rest/realtime/gateway không có healthcheck; /ops không thấy auth/gateway

- **Tệp:** `docker-compose.supabase.yml:153-245`; `scripts/collect_ops_status.py:16` (`SERVICE_IDS`
  không gồm db, auth, gateway). Auth/gateway chết = không ai đăng nhập được mà /ops vẫn xanh.
- **Hướng sửa:** thêm healthcheck HTTP đơn giản và đưa vào `SERVICE_IDS`.

## (b) Sẵn sàng nhiều cơ sở / nhiều phòng khám, và chỗ chậm theo số dòng

**Hai tầng khoá trong repo:** tenant = `clinic_id` (mọi bảng nghiệp vụ, NOT NULL, đã gỡ
DEFAULT ở `20260730000014`); cơ sở = `location_id`. Cơ sở người xem = `identity.location_id`
từ header `X-Location-ID`, máy chủ kiểm thuộc phòng khám + đang bật
(`api/identity.py:531-548`). Cơ sở của lượt = `co_so_cua_luot()` =
`coalesce(visit.location_id, appointment.location_id)`.

| Bảng | `clinic_id` | `location_id` |
|---|---|---|
| visit, appointment, patient, staff_task, pregnancy | có | có (không chỉ mục riêng) |
| clinic_room, drug_batch, phieu_kho, chot_so_ca, kiem_ke_ca, vat_tu_*, staff_node | có | có |
| queue_entry, work_item, payment, prescription | có | không — suy qua visit (đúng thiết kế) |
| **thong_bao** | có | **không, và không suy được** (xem B3) |
| work_roster, vi_tri_lam_viec | có | không — suy qua `station → vi_tri.room_id → clinic_room` |
| service_price, service_type, `clinic.settings` | có | không — giá/ca/chính sách chung cả phòng khám (B7) |

### Phần đã kiểm, ổn

- Lọc cơ sở có test sẵn (`test_loc_co_so_nhom_a/b/c_db.py`, `test_an_ton_co_so_ngung_db.py`):
  hàng chờ, bảng lượt, siêu âm, quầy thu, check-out, nhà thuốc, trang chủ, TV
  (`display_board_service.py:126`), điều phối (`dispatch_service.py:293`).
- Phòng khác cơ sở với lượt bị chặn ở Postgres (`chan_phong_khac_co_so`, `20261008700000`);
  lô thuốc theo cơ sở (`lo_dung_co_so_luot`).
- Không UUID cơ sở/phòng viết cứng trong code chạy thật; "Hào Nam/Kim Ngưu" trong `src/`
  chỉ còn ở comment; `'KN'` trong migration là backfill một lần.
- **SĐT in phiếu đọc từ DB** (`quay_thu_service.py:983-1003`, `mang_sang.py:267-273`) —
  không viết cứng trong code chạy (xem B8 về chỗ SỬA nó).
- Giá trong `phieu_kham/anh_xa_danh_muc.py` không dùng lúc chạy (giá đọc từ DB).
- Quầy thu 7.539 lượt cũ: đã sửa (`cashier_board_service.py:95-134`: 30 ngày / 7 ngày / trần 400).

### B1 · VỪA (nhiều cơ sở) · Vai theo lịch trực không xét cơ sở đang đứng

- **Tệp:** `src/clinicai/api/identity.py:1011-1028` (`doc_vi_tri_hien_hanh` chỉ lọc
  `clinic_id + staff_id + ngày`) → `vai_theo_vi_tri` (`:580`).
- **Tái hiện:** điều dưỡng Y có ca `HN__T1_THUNGAN` hôm nay → chọn cơ sở Kim Ngưu → vẫn có vai
  thu ngân, check-in/thu tiền được ở KN dù không có ca ở đó.
- **Độ chắc:** chắc. **Test:** `test_vai_theo_lich_chi_o_co_so_co_ca`.
- **Hướng sửa:** thêm điều kiện ca thuộc `identity.location_id`. **Cần Tuyền chốt** vai có đi
  theo người sang cơ sở khác không.

### B2 · VỪA (nhiều cơ sở) · Lượt bán lẻ đang mở dùng chung giữa hai cơ sở

- **Tệp:** `supabase/migrations/20260930600000_*.sql:24` (`uq_visit_ban_le_dang_mo (clinic_id,
  clinic_patient_id)`), `src/clinicai/services/ban_le_service.py:294-330` (ON CONFLICT rồi
  UPDATE lấy lại theo khách, **không theo cơ sở**).
- **Tái hiện:** khách mua lẻ ở HN, lượt chưa đóng → hôm khác mua ở KN → nhận lại lượt HN
  (`location_id` = HN) ⇒ đơn không hiện ở Nhà thuốc KN, lô KN bị `lo_dung_co_so_luot` chặn.
- **Độ chắc:** khá (cần xác nhận lượt bán lẻ có tự đóng cuối ngày không).
- **Test:** `test_ban_le_moi_co_so_mot_luot_rieng`. **Hướng sửa (Mức 3):** thêm `location_id`
  vào chỉ mục duy nhất và câu UPDATE.

### B3 · VỪA (nhiều cơ sở) · Chuông gọi bộ phận không có cơ sở

- **Tệp:** bảng `thong_bao` (`20260807000006`, không migration nào thêm `location_id`);
  `services/thong_bao_service.py:186-207` (`goi`), `:340-349` (`cua_toi` chỉ lọc
  `clinic_id` + vai/người nhận); `events/consumers/chuong.py:153-180`.
- **Tái hiện:** trưởng ca HN "gọi Lễ tân" → lễ tân KN cũng thấy, bấm Xong được → việc ở HN
  bị đóng mà không ai ở HN làm. Chuông hạn lô/kiểm kê lệch gộp mọi cơ sở, không ghi tên cơ sở.
- **Độ chắc:** chắc. Gần với mục đã biết "Bấm 'Xong' thông báo không kiểm người bấm"
  (`thong_bao_service.py:458`, `phat-hien.json`) nhưng là lỗi khác (phạm vi cơ sở).
- **Hướng sửa (Mức 3):** cột `thong_bao.location_id` (NULL = mọi cơ sở), lọc trong `cua_toi`.
  **Cần Tuyền chốt** chuông có chỉ tới cơ sở người gọi không.

### B4 · VỪA · Vai và ca bác sĩ suy từ mã vị trí viết cứng; Python và SQL lệch nhau

- **Tệp:** `api/identity.py:825-847` (`VAI_THEO_VI_TRI`), `services/config_service.py:66-79`
  (`MA_CA_KHAM_BAC_SI`), `cashier_scope_service.py:266/329/387` + `report_access_service.py:51`
  (`"DIEU_PHOI"`), `api/v1/routers/hang_cho.py:292,296` (`'LUOTKHAM-15'`, `'LUOTKHAM-01'`);
  bản SQL `la_ca_kham_bac_si` (`20260917000004`) lại đọc dữ liệu `nhom_nghe='BAC_SI'`.
- **Tái hiện:** tạo vị trí `T3_BS_MOI` (nhóm nghề BAC_SI) trên màn → lịch tuần (SQL) coi là ca
  khám, nhưng Python (`config_service.py:260/993`) không báo CSKH "lịch chờ xếp". Phòng khám
  thứ hai dùng bộ mã khác là hỏng hết.
- **Độ chắc:** chắc. **Đã biết một phần:** `lib/ca-kham-bac-si.ts:6` (mã chép tay ở giao diện)
  có trong `phat-hien.json`; phía Python/SQL lệch là mới.
- **Test:** `test_vi_tri_bac_si_moi_khop_python_va_sql`. **Hướng sửa:** cột `vi_tri_lam_viec.vai`
  đọc từ bảng thay dict; một hàm Python gọi chung luật SQL.

### B5 · CAO (khi có tenant thứ hai) · Giao diện không bao giờ gửi `X-Clinic-ID`

- **Tệp:** `api/identity.py:494-509` trả 403 khi tài khoản có ≥2 membership mà thiếu header;
  `src/dashboard` không có chỗ nào gửi `X-Clinic-ID` (grep 0 kết quả), `lib/backend-proxy.ts`
  chỉ gắn `X-Location-ID`.
- **Tái hiện:** thêm `clinic_membership` thứ hai cho bác sĩ X ⇒ X đăng nhập, mọi API 403.
- **Độ chắc:** chắc. Đúng hướng "đóng khi mơ hồ" (an toàn), chỉ là chưa có lối chọn.
- **Hướng sửa:** cookie/màn chọn phòng khám giống `co-so.ts`, gắn header trong backend-proxy. Làm khi thật có tenant thứ hai.

### B6 · VỪA · Cấu hình nghiệp vụ của Dr4Women nằm trong code

- `phieu_kham/anh_xa_danh_muc.py` (nhãn → `service_code`/node), dùng ở
  `phieu_kham_service.py:680-682`, `mau_goi_y.py:41-45`: tenant khác không đổi được nếu không sửa code.
- Thương hiệu trong prompt LLM (`orchestrator/llm_nodes.py:36,164`, `agent_tom_tat.py:78`),
  `manifest.ts:21-23`; `Asia/Ho_Chi_Minh` viết cứng trong SQL/`CLINIC_TZ` dù có `clinic.timezone`;
  Telegram một kênh cho mọi cơ sở (`worker.py:114`, `providers/telegram.py:38`).
- **Độ chắc:** chắc. **Hướng:** bảng `phieu_anh_xa(clinic_id, nhan, service_code)`; tên thương hiệu
  lấy từ `clinic.name`. Không gấp khi chỉ có một tenant.

### B7 · VỪA (nhiều cơ sở) · Giờ ca, chính sách đặt lịch, cấu hình TV là của cả phòng khám

- **Tệp:** `core/shifts.py:58-63` + `ca_tu_settings(clinic.settings)` (11 chỗ gọi);
  `services/clinic_policy.py:28-31`; `api/v1/routers/display.py:46-63`.
- **Tái hiện:** KN mở 7:30, HN 8:00 → không khai được; TV hai cơ sở chung chân trang.
- **Hướng sửa (Mức 3):** `clinic_location.settings` ghi đè `clinic.settings`.

### B8 · THẤP · SĐT / tên in / địa chỉ cơ sở không sửa được trên màn

- **Tệp:** `services/clinic_config_service.py:799-855` (`update_location` chỉ sửa
  name/address/is_active). Đổi SĐT phải viết migration (`20261020100000`, viết cứng
  `WHERE code IN ('HN','KN')` — chính là commit "Kim Ngưu cũng in SĐT 0899 973 555") hoặc chạy
  `scripts/nhan-ban-co-so.py` (viết cứng `MA_HN="HN"`). Trái luật "việc dữ liệu làm trên màn".
- **Test:** `test_sua_sdt_ten_in_co_so`. **Hướng sửa:** thêm `phone`, `ten_in` vào
  `update_location` + màn Cấu trúc phòng khám.

### B9 · THẤP · Các lọt nhỏ khác

- `/appointments/lich-ngay` (`lich_hen_doc.py:52-61`) không lọc cơ sở; `NewPatientForm.tsx:620-633`
  gợi ý số khám max+1 trên cả hai cơ sở (chỉ hiển thị — máy chủ đánh lại, `booking_service.py:685-689`).
- Trigger `assign_appointment_queue_number` (`20260812000001`) đánh số theo bác sĩ trên mọi cơ sở.
- Tin SSE theo tenant chứ không theo cơ sở: xem A5.
- **Nghi, chưa xác minh:** CSKH/recall, `lich_bac_si_tu_choi` (`lich_hen_doc.py:135`) không lọc cơ
  sở — có thể chủ ý (CSKH làm cho cả phòng khám).

### Chậm dần theo số dòng

**S1 · VỪA · chắc** — `src/clinicai/services/bao_cao_viec_tien_service.py:85-104` (`_thua`):
lấy **mọi lượt từ trước tới nay** của cơ sở (không giới hạn ngày, không LIMIT), đẩy cả mảng id vào
`dong_tien_thua` (`= ANY($2)`) rồi lọc bằng Python. Gọi mỗi lần mở báo cáo Cuối ngày
(`bao_cao_cuoi_ngay_service.py:1258`). Cùng kiểu "lượt cũ" đã làm quầy thu 40 giây.
*Kiểm:* `EXPLAIN ANALYZE` + đếm `len(vids)` trên staging. *Sửa:* tập ứng viên lấy từ
`payment_bill_line` của chỉ định huỷ/không làm (đã có chỉ mục), không từ visit.

**S2 · VỪA** — `event_delivery` không dọn + đếm toàn bảng mỗi phút: đã gộp vào **A4**.
`hen_gio` cũng bị đếm toàn bảng (`api/v1/health.py:93-104`).

**S3 · THẤP · chắc** — `canh_gac.py:187-190` gọi `bat_bien_lieu_trinh(c.id)` mỗi phút cho mọi liệu
trình từ trước tới nay (3 subquery/liệu trình). *Sửa:* chỉ xét liệu trình có thay đổi 24 giờ qua,
như `bat_bien_tien_chi_dinh`.

**S4 · THẤP · chắc** — `agent_tom_tat.py:333-343`: từ 18h, mỗi phút, với mỗi phòng khám chưa có
tóm tắt, `EXISTS (... (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $1)` — biểu thức
không dùng được chỉ mục; ngày vắng (không có lượt) thì không bao giờ tạo tóm tắt nên câu này quét
`visit` mỗi phút tới nửa đêm. *Sửa:* điều kiện khoảng `checked_in_at >= đầu ngày VN AND < cuối ngày`.

**Ngờ:** `pharmacy_service.py:147-188` (`hang_doi`) lấy đơn `closed_at IS NULL` không giới hạn ngày;
có chỉ mục + `LIMIT 300` nên rủi ro là hàng đầy đơn cũ hơn là chậm.
*Kiểm:* `SELECT count(*) FROM prescription WHERE closed_at IS NULL AND removed_at IS NULL AND created_at < now()-interval '7 days'`.
