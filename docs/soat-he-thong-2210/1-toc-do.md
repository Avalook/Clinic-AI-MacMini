# Soát 22/10 · Khối 1 · TỐC ĐỘ — vì sao màn chậm, vì sao tải lại thừa

> Đang viết dần (commit theo nhóm phát hiện). Chỉ đọc code `main` @ `00bde52`.
> Không đo trên VPS; mọi "cách đo" bên dưới chạy trên Mac / DB test.

## Tóm tắt 10 dòng

(đang viết — xem cuối tệp)

## Bảng phát hiện

(đang viết — xem cuối tệp)

---

## Từ ngữ dùng trong báo cáo

- **SSR / dựng lại trang (RSC)**: máy chủ Next.js chạy lại phần "server component"
  của trang (gọi FastAPI, kiểm quyền…) rồi gửi kết quả về. `router.refresh()` ở
  trình duyệt = xin một lần dựng lại như vậy.
- **SSE**: một kết nối HTTP mở mãi, máy chủ đẩy tin "bảng X vừa đổi" xuống trình duyệt.
- **NOTIFY**: lệnh Postgres báo tin cho ai đang `LISTEN`; trigger `notify_row_change`
  bắn nó mỗi khi một dòng đổi.
- **N+1**: lấy danh sách N dòng (1 câu SQL) rồi với TỪNG dòng lại gọi thêm SQL → N+1 câu,
  đi tuần tự, mỗi câu tốn một vòng mạng.
- **Ép kiểu trên cột** (`o.id::text = x`): Postgres không dùng được chỉ mục (index) của
  cột `id` khi so sánh trên giá trị đã đổi kiểu → phải quét cả bảng của phòng khám.

---

## Nhóm A — Realtime: một lượt ghi làm mọi màn dựng lại

### A1 · CAO · Mọi tin của 41 bảng dựng lại toàn trang ở mọi màn "thường" — **đã biết** (kế hoạch G1)

- **Ở đâu:** `src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:88-147` (`LIVE_TABLES`),
  `:157` (mặc định `tables = LIVE_TABLES`), `:297-298` (`xuLy` → `nhip.nhan()` →
  `router.refresh()`); layout gắn không truyền `tables`:
  `src/dashboard/app/(dashboard)/layout.tsx:166`. Lọc bảng duy nhất:
  `src/dashboard/lib/man-tu-tai.ts:47-54` (`canDungLaiTrang`).
- **Cơ chế:** tin SSE chỉ mang tên bảng + phòng khám (`events.py:62`,
  `notify_row_change` ở `20260806000001_…sql:40-43`). Với màn KHÔNG nằm trong
  `MAN_TU_TAI` (vd `/home`, `/reception/queue`, `/customers`, `/phong`, `/reception/checkout`,
  `/truong-ca`), bất kỳ bảng nào trong 41 bảng đổi → dựng lại cả trang. Gộp nhịp chỉ
  250–600ms + lệch 0–400ms (`lib/nhip-lam-moi.ts:173`), nên một thao tác chạm 3–4 bảng
  trong vài giây vẫn ra 1–3 lần dựng.
- **Ảnh hưởng (từ số đo):** 9,8 → 6,8 lần dựng / 1 lượt ghi; `/reception/queue` 4.675
  lần / 3 giờ, `/home` 2.737, `/customers` 2.998. Tải ∝ (số màn mở) × (số lượt ghi).
- **Độ chắc:** chắc chắn (đã lần code).
- **Kế hoạch 17/10:** đúng (G1, S3, S6). Bổ sung ở A2–A4 bên dưới.

### A2 · CAO · Tự lưu không chỉ ở phiếu khám: ô tư vấn, ghi chú, đơn thuốc cũng bắn tin cho cả phòng khám — **MỚI** (kế hoạch chỉ nói `phieu_kham_luot`)

- **Ở đâu:**
  - Ô "Nội dung tư vấn" tự lưu: `src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/OTuVanTuLuu.tsx:66`
    → `/luot-kham/consultations/{id}/noi-dung-tu-van` (`routers/luot_kham.py:623`) →
    `luot_kham_service.py:1942` **INSERT `consultation_note` + UPDATE `encounter_flow`**
    (cả hai trong `LIVE_TABLES`).
  - Ghi chú lượt tự lưu: `GhiChuLuot.tsx:99` → `save_note` (cũng INSERT `consultation_note`
    + UPDATE `encounter_flow`).
  - Đơn thuốc tự lưu sau 1,5s: `PhieuKhamLuot.tsx:79,365` (`CHO_LUU_DON_MS`) → ghi
    `prescription` (trong `LIVE_TABLES`, trigger từ `20260806000001`).
  - Phiếu khám: `trg_notify_phieu_kham_luot` bắn ở MỌI UPDATE
    (`supabase/migrations/20261010100001_lich_su_don_thuoc_notify.sql:15-18`).
- **Cơ chế:** bác sĩ / thư ký gõ → mỗi lần tự lưu là một giao dịch ghi bảng "nóng"
  → NOTIFY → mọi màn thường của cả phòng khám dựng lại, dù màn đó không vẽ ô chữ ấy.
- **Kế hoạch sai chỗ nào:** mục 3b ghi lợi ích S2 "chỉ ~10–15% lượt ghi" vì chỉ đếm
  `/api/phieu-kham`. Ô tư vấn và ghi chú đi qua `/api/luot-kham` (POST), đơn thuốc qua
  đường đơn — nên phần "tự lưu" thật lớn hơn con số kế hoạch dùng để hạ ưu tiên S2.
- **Kịch bản tái hiện:** mở `/reception/queue` ở tab A; ở tab B mở Bàn khám một lượt đang
  tư vấn, gõ 3 câu vào ô Nội dung tư vấn (dừng >1,5s giữa câu) → tab A dựng lại 3 lần
  (đếm request `?_rsc=` trong DevTools).
- **Độ chắc:** chắc chắn về đường ghi → bảng → tin. Tỉ lệ trong tổng lượt ghi: **nghi**
  (cần đếm theo `thao_tac` trong log).
- **Cách đo trên Mac:** stack dev, mở 2 tab như trên, đếm `_rsc` trong DevTools; hoặc
  `LISTEN clinicai_changes;` trong `psql` vào DB thử rồi gõ — đếm tin theo bảng.
- **Đề xuất test:** test DB: UPDATE `consultation_note`/`encounter_flow` chỉ đổi nội dung
  → không có NOTIFY (sau khi sửa); test TS: `canDungLaiTrang` trả `false` cho bảng
  "nội dung" ở màn thường.
- **Hướng sửa:** (1) trigger có điều kiện như `form_instance` cho `phieu_kham_luot`,
  `consultation_note`, `encounter_flow` khi chỉ đổi nội dung/`content_revision`;
  (2) hoặc tách nhóm "bảng nội dung" khỏi tập bảng dựng lại trang ở client (rẻ, không
  migration). **Rủi ro:** màn nào thật sự vẽ nội dung (Bàn khám, Hành trình) phải tự
  nghe qua `useNgheBang` — các màn ấy đã ở `MAN_TU_TAI` nên rủi ro thấp; kiểm `/truong-ca`.

### A3 · VỪA · Kế hoạch ghi S1/S2/S3a "Xong" nhưng **chưa có trên `main`** — **kế hoạch sai trạng thái**

- **Ở đâu:** `src/dashboard/app/(auth)/login/actions.ts:50,61,70,97` vẫn
  `supabase.auth.signOut()` (không `scope: "local"`) — S1/#490 chưa vào `main`.
  `src/dashboard/lib/man-tu-tai.ts:23-29` chưa có `/patients/new` — S3a/#491 chưa vào.
  Không có migration nào sau `20261010100001` sửa `trg_notify_phieu_kham_luot`
  (`20261017100000` trên `main` là `thuoc_quy_doi`, không phải S2) — S2/#492 chưa vào.
- **Vì sao quan trọng:** đội đọc kế hoạch sẽ tưởng gốc G2/G5 đã xử lý; thật ra prod
  (gần `main`) vẫn chạy bản cũ. Tên migration S2 còn **đụng giờ** `20261017100000` đã dùng
  cho `thuoc_quy_doi` trên `main` → khi merge #492 phải đổi tên, nếu không
  `apply-pending-migrations.sh` sẽ coi là đã áp / trùng khoá.
- **Độ chắc:** chắc chắn về `main`; trạng thái các PR #490–492 (mở/đóng) chưa tra.
- **Hướng sửa:** cập nhật bảng 3b ("đã code, chưa merge"); đổi giờ migration S2 trước khi merge.

### A4 · VỪA · SSE đóng mỗi lần tab ẩn, mở lại = `getUser()` + một lượt bắt kịp ở mọi widget — **đã biết** (G3), kế hoạch đã đo và BỎ S4

- **Ở đâu:** `RealtimeRefresher.tsx:203-218,314` (`batKip` phát `SU_KIEN_BANG` với
  `detail: null` → MỌI widget dùng `useNgheBang` tải lại); `app/api/events/stream/route.ts:35-43`
  (mỗi lần mở dòng: `getUser()` + `getSession()`, rồi một kết nối mới tới FastAPI).
- **Nhận xét:** kế hoạch đo "3–5% lần dựng lại trang đi sau lần mở lại SSE" — đúng cho
  **dựng trang**, nhưng lần mở lại còn kéo **mọi widget client** (`detail: null`) tải lại —
  phần này không nằm trong số RSC đã đếm. ">500 lần mở SSE / 30 phút" với ~16 máy ≈ mỗi
  máy 1 lần/phút: khớp với thói quen đổi tab/cửa sổ của lễ tân, không phải lỗi rớt kết nối.
- **Độ chắc:** chắc chắn về cơ chế; tỉ trọng **nghi** — xem thêm nhóm C (widget).
- **Hướng sửa (rẻ):** khi quãng ẩn ngắn (< 30–60s) và SSE vừa sống, không phát `null`;
  hoặc giữ SSE khi ẩn (HTTP/2 đã có, 99,99% request) và chỉ bắt kịp khi thật sự rớt.

---

## Nhóm B — SQL nặng, worker nền, chỉ mục

### B1 · CAO · Worker đối chiếu sổ nợ tính lại "số dư" của tới 300 lượt mỗi 10 phút, suốt giờ khám — **MỚI**

- **Ở đâu:** `src/clinicai/worker.py:318-320` gọi `so_no_service.doi_chieu_mot_vong` mỗi
  `NHIP_GIAY = 600` (`so_no_service.py:79`), mỗi vòng tới `DOI_CHIEU_MOI_VONG = 300` lượt
  (`:83`); `_doi_chieu` (`:597-614`) với TỪNG lượt mở giao dịch, khoá lượt, gọi
  `ghi_chenh_lech` → `so_du_hien_tai` (`:215-260`) = `no_khi_ve` (hoá đơn đầy đủ, ~10 câu,
  `cong_no_service.py:277` → `bill_service.hoa_don_con_no:853`) + `dong_tien_thua` +
  `_CHUA_LAM_SQL` + `tien_da_thu_cua_chi_dinh` + `_THUOC_PHAI_TRA_SQL` + 2× `_CUOI_SQL`.
  Thêm `dau_ky_mot_vong` 300 lượt / 60 giây cho tới khi xong ~14k lượt cũ (`:81,85`).
- **Cơ chế:** ~20 câu SQL × 300 lượt = ~6.000 câu mỗi vòng, chạy dồn trong một tiến trình,
  cạnh tranh DB với giờ cao điểm. Mỗi lượt còn giữ khoá `pg_advisory_xact_lock('so_no:…')` (`_khoa`, `:206-212`) — bên
  nhận sự kiện tiền của cùng lượt (thu ngân vừa thu) phải chờ vòng đối chiếu nhả khoá.
- **Liên hệ số đo:** comment ở `tien_thua_service.py:39-46` ghi chính câu tiền thừa cũ chạy
  "171 ms × 67k lần ở prod". Trang/quầy không gọi được 67k lần; vòng đối chiếu (300 lượt
  × 6 vòng/giờ × 24h ≈ 43k/ngày) + lô đầu kỳ (14k) **khớp cỡ số** → nghi mạnh đây là nguồn
  chính của con số 67k, không phải màn hình.
- **Lỗi kèm (đúng/sai, không chỉ chậm):** `_CAN_XET_SQL` (`:528-543`) là `UNION … LIMIT 300`
  **không `ORDER BY`**: khi số lượt còn số dư ≠ 0 (khách nợ lâu, tiền thừa "giữ lại")
  vượt 300, tập 300 lượt mỗi vòng là tuỳ planner — lượt vừa về có thể không bao giờ được
  đối chiếu, còn cùng 300 lượt nợ cũ bị tính lại mãi.
- **Độ chắc:** chắc chắn về vòng lặp và số câu; "nguồn của 67k" là **nghi** (cần
  `pg_stat_statements` trên DB thử sau khi chạy worker 1 giờ).
- **Cách đo trên Mac:** DB staging-local (bản sao lưu), `pg_stat_statements_reset()`, chạy
  worker `su-kien` 30 phút không ai bấm → xem `calls`, `total_exec_time` của
  `_DONG_THUA_SQL`/`_THUOC_PHAI_TRA_SQL`. Nếu 0 người bấm mà vẫn hàng nghìn lần → xác nhận.
- **Đề xuất test:** unit: `_CAN_XET_SQL` với 301 lượt nợ cũ + 1 lượt vừa về → lượt vừa về
  phải nằm trong kết quả (ưu tiên lượt mới; `ORDER BY` rõ).
- **Hướng sửa:** (1) chỉ đối chiếu lượt có **thay đổi** từ vòng trước (so `updated_at`/
  `so_no.seq` với mốc vòng trước) thay vì mọi lượt còn số dư; (2) `ORDER BY` ưu tiên lượt
  vừa về; (3) giãn nhịp / chuyển vòng lớn ra ngoài 18–21h. **Rủi ro:** đây là sổ tiền
  (mức 3) — đổi tập lượt xét phải có test so số dư trước/sau.

### B2 · VỪA · So khoá uuid bằng chuỗi (`id::text = …`) — Postgres không dùng chỉ mục khoá chính — **MỚI** (một phần đã sửa riêng ở `_DONG_THUA_SQL`)

- **Ở đâu (đi ngược chiều chỉ mục):**
  - `hoan_tac_service.py:297` `o.id::text = ANY($2::text[])` trong `tien_da_thu_cua_chi_dinh`
    — gọi ở `so_no_service.py:249` (mỗi lượt của B1), `danh_sach_hoa_don_service.py:194`,
    `hoan_tac_service.py:382,760`, `so_sua_chi_dinh_service.py:779`.
  - `so_no_service.py:162` `p.id::text = d.rx_id` (`_THUOC_PHAI_TRA_SQL`, mỗi lượt của B1).
  - `events/consumers/so_no.py:47` `bl.payment_cycle_id::text = $2::text` (OR với nhánh hoàn
    → không dùng chỉ mục `payment_cycle_id`), `:58,:63,:71` `o.id::text = d.source_id`,
    `p.id::text`, `rx.id::text`.
  - `tien_thua_service.py:183` `g.visit_id::text = ANY($2::text[])` (bảng nhỏ, ảnh hưởng thấp).
  - Toàn `src/clinicai/services/*.py` có ~41 chỗ dạng `cột::text = …`; không migration nào có
    chỉ mục biểu thức `((id::text))`.
- **Cơ chế:** `payment_bill_line.source_id` là `text` nên mọi nối sang uuid phải ép kiểu.
  Khi ép ở phía **cột cần tìm**, chỉ mục bị bỏ → quét toàn bộ dòng của phòng khám
  (`service_order` ~35k, `prescription`…) cho mỗi lần gọi. Ở quy mô nhiều phòng khám, chi
  phí tăng theo tổng dữ liệu, không theo số dòng cần.
- **Độ chắc:** chắc chắn về câu chữ; thời gian thật **nghi** — chưa có `EXPLAIN` trên dữ liệu thật.
- **Cách đo:** `EXPLAIN (ANALYZE, BUFFERS)` các câu trên ở staging-local với một `visit_id`
  thật; tìm `Seq Scan on service_order`/`prescription`.
- **Hướng sửa:** đổi chiều ép (`o.id = ANY($2::uuid[])` sau khi lọc chuỗi hợp lệ ở Python như
  `_uuid_chuan`; `p.id = d.rx_id::uuid` chỉ trong nhánh `source_type='prescription'`), hoặc
  thêm chỉ mục biểu thức. **Rủi ro:** `source_id` có thể chứa chuỗi không phải uuid (vd
  `exam-…-selected-…`) → ép `::uuid` sẽ ném; phải lọc `source_type` trước. Test tương đương
  như `test_tien_thua_dong_tuong_duong_db`.

### B3 · CAO · `lich_vuot_suc_chua()` quét mọi lịch tương lai của **mọi phòng khám** cho mỗi lần đọc `v_viec_cskh` — **đã biết** (`docs/KE-HOACH-HAM-SUC-CHUA.md`), có điểm MỚI

- **Ở đâu:** hàm `supabase/migrations/20260915000014_suc_chua_online_truc_tiep.sql:65-115`
  (vẫn là bản hiện hành trên `main`); dùng qua `v_viec_cskh` ở
  `week_appointments_service.py:61` (CTE `vuot`, câu `WITH tuan AS` 10k × 277ms),
  `man_trang_chu_service.py:119` (câu `count(DISTINCT x.pid)` 10k × 165ms), màn Quản lý khách.
- **Điểm MỚI:** hàm **không có tham số `clinic_id`** và CTE `lich` không lọc phòng khám
  (`:84-100`) → khi có phòng khám thứ hai, mỗi lần mở trang chủ của phòng khám A cũng gọi
  `resolve_effective_cap` cho mọi lịch tương lai của phòng khám B rồi mới lọc. Kế hoạch sức
  chứa chỉ gom theo cặp (bác sĩ, giờ), chưa thêm lọc phòng khám.
- **Vì sao 10k lần:** cả hai câu nằm trong SSR `/home` (và lịch tuần) — bị A1 kéo chạy lại
  sau mỗi tin. Sửa A1 giảm số lần, sửa B3 giảm giá mỗi lần — hai việc nhân nhau.
- **Độ chắc:** chắc chắn (đã đọc thân hàm).
- **Hướng sửa:** theo `KE-HOACH-HAM-SUC-CHUA.md` + thêm tham số / điều kiện phòng khám
  (hàm mới `lich_vuot_suc_chua(p_clinic uuid)`, view truyền `clinic_id`). Mức 3.

### B4 · VỪA · Bảng thu ngân: N+1 tuần tự trên mỗi khách + vế "lượt cũ chưa về" không có mốc ngày — **đã biết một phần** (DANG-LAM 16/10 mục 3 "gom N+1 quầy thu")

- **Ở đâu:** `cashier_board_service.py:708-772`: với MỖI lượt trong `out["items"]`, tuần tự
  `tinh_hoa_don` cho từng loại (`:715`, dịch vụ → `hoa_don_con_no` ~10–12 câu
  `bill_service.py:853-1000`), `_quay_thu` (`:756`, có thể gọi `hoa_don_con_no` lần nữa
  `:913`), và `pq.cua(...)` cho từng phòng (`:745`).
  Vế ứng viên `old.created_at < $2 AND NOT da_ve` (`:247-262`) **không có mốc ngày dưới** —
  mọi lượt cũ chưa đóng từ trước tới nay đều được xét EXISTS × 3 mỗi lần tải.
- **Ảnh hưởng:** 40–60 khách × ~15–25 câu ≈ 600–1.500 câu tuần tự mỗi lần tải bảng; khớp
  "quầy thu max 14s" khi DB đang bận (B1, A1). (Lưu ý: `max` của `pg_stat_statements` cộng
  dồn từ lần reset — có thể còn là lần chạy trước khi tắt JIT 09/10, `core/database.py:34-41`.)
- **Độ chắc:** N+1 chắc chắn; số lượt cũ chưa đóng trên prod **chưa biết** (nghi tăng dần).
- **Cách đo:** staging-local: bật `log_min_duration_statement=0` cho DB thử, mở
  `/thu-ngan/dich-vu` một lần, đếm số câu; `SELECT count(*) FROM visit WHERE closed_at IS
  NULL AND status NOT IN ('FINALIZED','AMENDED','INCOMPLETE') AND created_at < current_date`.
- **Hướng sửa:** gom theo lô (một câu cho mọi `visit_id` như `dong_tien_thua` đã làm); thêm
  mốc dưới (vd 90 ngày) cho vế "chưa về" kèm cảnh báo khi cắt. Mức 3 (tiền).

### B5 · THẤP · JIT chỉ tắt cho bể kết nối của FastAPI

- **Ở đâu:** `src/clinicai/core/database.py:41` (`SERVER_SETTINGS = {"jit": "off"}`); không có
  `jit` trong cấu hình Postgres / compose. PostgREST (trình duyệt + `lib/doctors-server.ts`,
  `lib/roster-names.ts`, `lib/event-log.ts`), GoTrue và kết nối LISTEN của `change_broker`
  (`core/change_broker.py:95` — `asyncpg.connect` không truyền `server_settings`, nhưng kết
  nối này không chạy truy vấn) vẫn để JIT bật.
- **Ảnh hưởng:** thấp (câu PostgREST nhỏ). Ghi lại vì comment nói "prod, staging, CI và máy
  dev cùng một hành vi" — đúng cho API, không đúng cho cả DB.
- **Hướng sửa:** `ALTER DATABASE … SET jit = off` một lần (mức 3, hạ tầng), hoặc giữ như cũ.

