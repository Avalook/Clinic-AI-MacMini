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
