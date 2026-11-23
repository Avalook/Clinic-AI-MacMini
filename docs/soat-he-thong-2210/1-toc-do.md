# Soát 22/10 · Khối 1 · TỐC ĐỘ — vì sao màn chậm, vì sao tải lại thừa

> Bản đủ (nhóm A–E + đối chiếu kế hoạch). Chỉ đọc code `main` @ `00bde52`.
> Không đo trên VPS; mọi "cách đo" bên dưới chạy trên Mac / DB test.

## Tóm tắt 10 dòng

1. Gốc lớn nhất vẫn là kế hoạch đã nói (G1): mỗi tin của 41 bảng dựng lại toàn trang ở mọi màn "thường" (A1).
2. Phần tự lưu bắn tin rộng hơn kế hoạch tính: ô tư vấn, ghi chú, đơn thuốc cũng vậy, không chỉ phiếu khám (A2).
3. Câu `WITH dong AS (bl…` 67k lần: nghi mạnh nguồn chính là **worker sổ nợ** chạy 300 lượt × ~20 câu mỗi 10 phút, không phải màn hình (B1).
4. `/ban-kham`, `/phong/{id}` ~0,9s dù trang gần như trống: layout gọi `/phan-quyen/toi`, hàm này lặp **một câu SQL cho mỗi ngày trực** của người không đứng quầy thu — chậm dần theo ngày (D1).
5. Layout chạy 3 đợt gọi nối tiếp, không cache gì giữa hai lần dựng (D3) — "phí vào cửa" của mọi trang.
6. Quầy thu / `/reception/checkout`: N+1 tới 300 lượt × 15–25 câu, và checkout bị chạy 2 lần mỗi tin (D2, B4).
7. `/api/luot-kham` mỗi lần gọi đã gọn (~10 câu lô, có chỉ mục); 3.557 lần/30′ là do client gọi quá nhiều (C2, E4).
8. Sau thao tác màn tự refresh rồi tin SSE refresh lần nữa (C1); tin không mang cơ sở nên cơ sở này dựng lại màn cơ sở kia (E2).
9. Kế hoạch ghi S1/S2/S3a "Xong" nhưng chưa có trên `main`, và S8 thêm tiến trình sẽ vượt `max_connections` nếu giữ pool 20 (A3, E3).
10. Thứ tự sửa đề xuất (lợi/rủi ro): D1 → checkout vào `MAN_TU_TAI` (D2-1) → C1 → A2 phía client → B1 (mức 3) → D3 → B3 → S6; không cần Redis/broker (E5).

## Bảng phát hiện

| # | Mức | Phát hiện | Ở đâu (chính) | Độ chắc | So kế hoạch | Ưu tiên |
|---|---|---|---|---|---|---|
| A1 | CAO | Mọi tin 41 bảng → dựng lại toàn trang | `RealtimeRefresher.tsx:88-147,297` | chắc | đã biết (G1) | S6 |
| A2 | CAO | Ô tư vấn / ghi chú / đơn thuốc tự lưu bắn tin cả phòng khám | `OTuVanTuLuu.tsx:66`, `luot_kham_service.py:1942`, `PhieuKhamLuot.tsx:79` | chắc (tỉ lệ: nghi) | MỚI, kế hoạch hẹp | 4 |
| A3 | VỪA | S1/S2/S3a ghi "Xong" nhưng chưa vào `main`; giờ migration S2 trùng | `login/actions.ts:50`, `man-tu-tai.ts:23` | chắc | kế hoạch sai | sửa tài liệu |
| A4 | VỪA | Mở lại SSE → `null` → mọi widget tải lại | `RealtimeRefresher.tsx:203-218` | chắc (tỉ trọng: nghi) | đã biết (G3), thiếu phần widget | 7 |
| B1 | CAO | Worker sổ nợ 300 lượt × ~20 câu / 10′; `LIMIT 300` không `ORDER BY` | `so_no_service.py:79-83,528-614` | chắc (nguồn 67k: nghi) | MỚI | 5 (mức 3) |
| B2 | VỪA | `id::text = …` bỏ chỉ mục khoá chính (~41 chỗ) | `hoan_tac_service.py:297`, `so_no_service.py:162`, `consumers/so_no.py:47-71` | chắc (thời gian: nghi) | MỚI | 8 |
| B3 | CAO | `lich_vuot_suc_chua()` quét mọi phòng khám | `20260915000014_…sql:65-115` | chắc | đã biết + MỚI (lọc phòng khám) | 6 (mức 3) |
| B4 | VỪA | Bảng thu ngân N+1; vế lượt cũ không mốc ngày | `cashier_board_service.py:247-262,708-772` | chắc | đã biết một phần | 8 (mức 3) |
| B5 | THẤP | JIT chỉ tắt ở bể FastAPI | `core/database.py:41` | chắc | MỚI | thấp |
| C1 | VỪA | Refresh chủ động + refresh do SSE; vào màn = 2 lần dựng | `QueueBoard.tsx:113`, `CheckoutBoard.tsx:167`, `LiveBoardSync.tsx:50` | chắc | MỚI | 3 |
| C2 | VỪA | Bàn khám 3 lời gọi/tin của 8 bảng; `null` ~15 lời gọi | `BanKham.tsx:330,566` | đường: chắc; số: nghi | MỚI (định lượng) | S6 |
| C3 | THẤP | Poll cứng 4s/5s/30s còn sót | `ServiceFormEngine.tsx:144`, `dung-giu-cho.ts:90`, `DisplayBoard.tsx:103` | chắc | MỚI | thấp |
| C4 | THẤP | `ClinicalRecordForm` tự nghe bảng mình ghi | `ClinicalRecordForm.tsx:536,637` | chắc | MỚI | thấp |
| D1 | CAO | `/phan-quyen/toi` một câu SQL mỗi ngày trực | `cashier_scope_service.py:243-309` | chắc (ms: nghi) | MỚI | **1** |
| D2 | CAO | `/reception/checkout` N+1 300 lượt, chạy 2 lần/tin | `checkout_service.py:401-428,1051-1095` | chắc | MỚI | **2** |
| D3 | VỪA | Layout 3 đợt gọi nối tiếp, `no-store` | `layout.tsx:46,96-121`, `proxy.ts:139` | chắc (ms: nghi) | MỚI | 6 |
| D4 | VỪA | `/customers` ghi `nhac_tai_kham` khi dựng | `customers/page.tsx:296` | chắc | đã biết | theo kế hoạch |
| D5 | THẤP | `MAN_TU_TAI` vẫn dựng lại theo `appointment` | `man-tu-tai.ts:33,53` | chắc | MỚI | thấp |
| E1 | THẤP | Cache tĩnh đã sửa; số đo 7.000 là số cũ | `caddy/Caddyfile:50-87,198` | chắc | đã sửa | — |
| E2 | VỪA | Tin realtime không mang cơ sở | `20260806000001_…sql:29-43`, `change_broker.py:117-140` | chắc (ảnh hưởng: nghi) | MỚI | gộp S6 |
| E3 | VỪA | 1 tiến trình, pool 20; S8 sẽ vượt `max_connections` | `Dockerfile.api:41`, `database.py:17-28` | chắc (bể cạn: nghi) | kế hoạch thiếu | sau D1/D2/B1 |
| E4 | THẤP | `/api/luot-kham` mỗi lần gọi đã gọn | `luot_kham_doc.py:75-360` | chắc | xác nhận | — |
| E5 | THẤP | SSE phía máy chủ ổn | `change_broker.py`, `events.py` | chắc | xác nhận | — |
| E6 | THẤP | Chỉ mục đủ; 2 điểm nhỏ | `cashier_board_service.py:137-145` | nghi | MỚI (nhỏ) | thấp |

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


---

## Nhóm C — Widget phía trình duyệt (client) tự tải lại

Nền: `useNgheBang` (`src/dashboard/app/(dashboard)/dung-nghe-bang.ts:45-83`) gộp nhịp
250–600ms và **luôn** phản ứng với tin `null` (`:75`). `gopDoc` (`lib/doc-gop.ts`) chỉ gộp
hai lời gọi giống nhau trong 50ms **trên cùng một máy**. Không có `AbortController`.

### C1 · VỪA · Màn vừa tự gọi `router.refresh()` sau thao tác, vừa bị tin SSE dựng lại lần nữa — **MỚI** (kế hoạch không nêu)

- **Ở đâu:** `reception/queue/QueueBoard.tsx:113,177,187,206`;
  `reception/checkout/CheckoutBoard.tsx:167-168` (`reload()` rồi `router.refresh()`);
  `truong-ca/shared.tsx:159`. Cả ba màn KHÔNG ở `MAN_TU_TAI` → tin `visit`/`queue_entry`/…
  do chính thao tác ấy sinh ra 250–1000ms sau lại `router.refresh()` lần nữa.
- **Thêm — đọc đôi mỗi tin:** `/reception/checkout` và `/truong-ca` có CẢ phần server
  (dựng lại bởi `RealtimeRefresher`) LẪN phần client tự tải (`CheckoutBoard.tsx:115`,
  `truong-ca/shared.tsx:118` — overview + alerts) → một tin = dựng trang + 1–2 lời gọi
  client cho cùng dữ liệu.
- **Thêm — vào màn = 2 lần dựng:** `LiveBoardSync.tsx:50` `router.refresh()` ngay khi
  mount, sau khi trang vừa dựng xong (chủ ý né `staleTimes.dynamic: 10`,
  `next.config.ts:29`). Gắn ở `/truong-ca`, `/reception/queue`, `/reception/checkout`, `/phong`.
- **Kịch bản:** lễ tân bấm "Gọi vào" ở `/reception/queue` → DevTools thấy 2 request
  `?_rsc=` cho `/reception/queue` trong ~1 giây.
- **Độ chắc:** chắc chắn (đã đọc các dòng trên).
- **Ảnh hưởng ước:** với người BẤM, mỗi thao tác ×2 lần dựng trang của chính họ
  (`/reception/queue` ~338ms mỗi lần). Không nhân theo số máy như A1, nhưng là phần
  dễ cắt nhất.
- **Hướng sửa:** bỏ `router.refresh()` sau thao tác ở màn đã nghe đúng bảng (để tin SSE
  làm), hoặc giữ cái chủ động và cho `RealtimeRefresher` bỏ qua tin trong ~1,5s sau một
  lần refresh chủ động (một mốc `lanLamMoiCuoi` dùng chung). **Rủi ro:** SSE rớt thì
  người bấm phải chờ nhịp 60s — giữ refresh chủ động khi `trangThaiDong !== "song"`.

### C2 · VỪA · Bàn khám: 3 lời gọi cho mỗi tin của 8 bảng nóng; tin `null` bắn ~15 lời gọi cùng lúc — **MỚI** (định lượng)

- **Ở đâu:** `ban-kham/BanKham.tsx:330` nghe `queue_entry, consultation, visit,
  encounter_flow, service_order, form_instance, tep_ket_qua, vital_measurement` → tải
  `luot-kham?xem=hang-cho` + `luot-kham` (bảng) + `cho-quyet` (qua `lanNap`, `:566`).
  Khi đang mở phiếu: thêm `OLamTruocThuSau.tsx:113` (nghe `visit`, fetch thẳng không qua
  `gopDoc`), `DauDoChiDinh.tsx:54`, `HanhTrinhKhach.tsx:410`, `PhieuKhamLuot.tsx:257,268`…
- **Ảnh hưởng:** khớp số "~15 lời gọi API / 1 lượt ghi" và `/api/luot-kham` 3.557 lần /
  30 phút (≈2/giây): ~6 máy ở Bàn khám/Phòng/Sinh hiệu × 1–3 lời gọi × một tin "nóng" mỗi
  3–5 giây, cộng các đợt `null` khi đổi tab. Đây là **ước lượng**, chưa đo.
- **Độ chắc:** đường gọi chắc chắn; con số **nghi**.
- **Cách đo trên Mac:** một máy mở Bàn khám, máy khác check-in/đo sinh hiệu 10 lần; đếm
  request theo `?xem=` trong DevTools (hoặc access log Caddy local).
- **Hướng sửa:** (1) `cho-quyet` chỉ nghe bảng của nó (`service_order_draft`/`service_order`)
  thay vì theo `lanNap`; (2) gộp `hang-cho` + `bang` thành một endpoint cho Bàn khám;
  (3) tin SSE mang thêm `visit_id` (S6 của kế hoạch) để phiếu đang mở chỉ tải khi đúng lượt.

### C3 · THẤP · Poll cứng ngắn còn sót

- `tasks/ServiceFormEngine.tsx:144` đọc lại `/api/clinical-form` mỗi **4 giây** (dùng ở
  `BanKham.tsx:1399,1466` — đường phiếu cũ, `PHIEU_V5 = true` nên chỉ khi xem lượt cũ).
- `appointments/dung-giu-cho.ts:90` poll **5 giây** khi mở lưới đặt lịch (có cả nghe
  `slot_hold`).
- `display/DisplayBoard.tsx:103` `router.refresh()` mỗi 30 giây mỗi TV (poll thuần).
- **Độ chắc:** chắc chắn; ảnh hưởng thấp (theo số màn đang mở).
- **Hướng sửa:** đổi sang `useNgheBang` + nhịp 60s như các màn khác.

### C4 · THẤP · `ClinicalRecordForm` tự lưu rồi tự nghe chính bảng mình ghi

- `tasks/ClinicalRecordForm.tsx:637` (tự lưu `clinical_record`) và `:536-542` (nghe
  `clinical_record` → nạp lại chính nó). Đường cũ (sau `PHIEU_V5`), ảnh hưởng thấp.
  Độ chắc: chắc chắn về đường; **nghi** về tần suất trên prod.

---

## Nhóm D — Trang SSR nặng: vì sao màn này chậm, màn kia nhanh

**Câu trả lời ngắn:** mọi trang trong `(dashboard)` trả chung một "phí vào cửa" ở layout
(D1, D3) — kể cả `/ban-kham`, `/phong/[id]`, `/thu-ngan/*` là những trang phần server
gần như không có gì riêng. Màn nào thêm một endpoint N+1 của riêng nó (D2, B4) hoặc đọc
`v_viec_cskh` (B3) thì chậm hẳn. `/display` nhanh (59ms) vì không đi qua layout này.

### D1 · CAO · `/phan-quyen/toi` (layout gọi ở MỖI lần dựng trang) lặp một câu SQL cho TỪNG ngày trực trong lịch sử — **MỚI**

- **Ở đâu:** `src/dashboard/lib/clinic-session.ts:106` (layout → `getQuyenCuaToi`; mọi
  `requireNavAccess` chờ nó) → `routers/phan_quyen.py:164-177` →
  `cashier_navigation_service.py:38-46` gọi `CashierScopeService.days(kind, limit=1)` cho
  **2 quầy** → `cashier_scope_service.py:243-253` lấy **mọi** `work_date` đã duyệt của người
  ấy (không mốc dưới) rồi `:254-262` **một câu SQL mỗi ngày**; chỉ dừng khi gom được
  `> limit` = **2 ngày có quầy thu** (`:309`).
- **Cơ chế:** người KHÔNG đứng quầy thu (bác sĩ, điều dưỡng, phòng dịch vụ, CSKH, lễ tân
  không thu) không bao giờ gom đủ 2 ngày → đi hết lịch sử, ×2 quầy. Ví dụ bác sĩ đã có
  60 ngày ca: ~2 × (1 + 60 + 3) ≈ 130 câu SQL tuần tự, mỗi câu mượn/trả bể kết nối riêng
  (`self.pool.fetch`). Con số **tăng mỗi ngày** người ấy đi làm — trang chậm dần theo
  thời gian mà không ai đổi code.
- **Vì sao giải thích được số đo:** `/ban-kham` và `/phong/{id}` đã ở `MAN_TU_TAI`, phần
  page không gọi gì riêng, mà SSR vẫn ~0,9s — người dùng hai màn này đúng là nhóm "không
  đứng quầy thu". Kèm theo: `report_access_service.py:143-157` (`/reports/access`, cũng
  trong layout) đọc toàn bộ `work_roster` của người đó, không giới hạn.
- **Kịch bản tái hiện:** DB thử có 1 bác sĩ với 90 ngày `work_roster` APPROVED ở trạm
  `LICH_KHAM` → `GET /api/v1/phan-quyen/toi` bằng token bác sĩ → đếm câu SQL
  (`log_min_duration_statement=0`) ≈ 2×90+; cùng gọi với thu ngân có 2 ngày `THU_NGAN` gần
  nhất → chỉ ~10 câu.
- **Độ chắc:** chắc chắn (đã đọc vòng lặp và điều kiện dừng). Thời gian thật trên prod: nghi.
- **Ảnh hưởng ước:** ×2.000–5.000 lần dựng trang mỗi 3 giờ cao điểm (số RSC đo được) ×
  ~100+ câu = vài trăm nghìn câu SQL nhỏ mỗi buổi tối chỉ để vẽ thanh bên.
- **Đề xuất test:** test DB `cashier_navigation` cho nhân viên 100 ngày ca không có quầy thu:
  số câu SQL ≤ hằng số (đếm qua wrapper conn) và kết quả bằng bản cũ.
- **Hướng sửa:** một câu SQL gom lô (lấy các ngày có trạm quầy thu bằng `WHERE station IN …`
  ngay trong câu `DISTINCT work_date`, `LIMIT limit+1`), hoặc giới hạn mốc dưới (vd 60 ngày)
  cho đường thanh bên. **Rủi ro:** thấp–vừa (quyền hiển thị menu, không phải quyền thật —
  backend vẫn kiểm từng lệnh); cần test tương đương.

### D2 · CAO · `/reception/checkout`: N+1 tới 300 lượt, và mỗi tin chạy nó HAI lần — **MỚI**

- **Ở đâu:** `checkout_service.py:401-428` (`pending_list`, `LIMIT 300` ở `:421`) và
  `:700-706` (danh sách tồn) → `_gan_doi_tac_tu_thu` (`:1051-1095`): với **từng lượt**,
  `hoa_don_con_no` (~10 câu), `no_khi_ve`, `tien_thua_khi_ve` (~3), có thể thêm
  `tinh_hoa_don(thuoc)` → ~15–25 câu / lượt, tuần tự trên một kết nối.
- **Đọc đôi:** trang gắn cả `LiveBoardSync` (`reception/checkout/page.tsx:32`) và
  `CheckoutBoard` client tự tải `/api/reception/checkout` (`CheckoutBoard.tsx:115`, nghe
  `visit, work_item, payment, service_order, consultation, cong_no`) — trong khi trang không
  thuộc `MAN_TU_TAI` nên `RealtimeRefresher` cũng dựng lại phần server
  (`checkout/page.tsx:27` gọi cùng endpoint). Một tin `visit` = `pending_list` chạy 2 lần
  trên mỗi máy đang mở màn này.
- **Độ chắc:** chắc chắn. Số lượt/ngày thật: nghi (40–80 lượt → 600–2.000 câu mỗi lần).
- **Cách đo:** staging-local, 1 ngày dữ liệu thật, gọi `GET /api/v1/reception/checkout`
  với `log_min_duration_statement=0` → đếm câu + tổng ms.
- **Hướng sửa:** (1) đưa `/reception/checkout` vào `MAN_TU_TAI` (phần client đã tự tải) —
  rẻ, cắt một nửa ngay; (2) gom lô `hoa_don_con_no`/`no_khi_ve`/`tien_thua` theo danh sách
  lượt (mức 3 — tiền). **Rủi ro (1):** kiểm phần server còn vẽ gì sống (ô đếm?) trước khi
  đưa vào; test `tai-lai-dong-loat-boundary.test.mts` cấm trang `MAN_TU_TAI` có
  `LiveBoardSync` → phải gỡ `LiveBoardSync` cùng lúc.

### D3 · VỪA · Layout chạy 3 đợt lời gọi nối tiếp trước khi trang được tải dữ liệu riêng — **MỚI** (định lượng)

- **Ở đâu:** `app/(dashboard)/layout.tsx:46` (`getVaiHienThi` → `/api/v1/me`) → đợt 2
  `getViTriHomNay` (`/me/vi-tri-hom-nay`, `lib/clinic-session.ts:59-74`) → đợt 3
  `Promise.all` 6–7 lời gọi (`layout.tsx:96-121`: `/appointments/policy`, `/feature-mode`,
  `/phan-quyen/toi`, `/reports/access`, …). Cộng 1 lời gọi PostgREST `staff` ở
  `proxy.ts:139-144` cho MỌI request trang (kể cả RSC refresh).
- **Cơ chế:** tất cả `cache: "no-store"` (`lib/backend-proxy.ts:262`) — `cache()` của React chỉ
  khử trùng TRONG một lần dựng; giữa hai lần dựng cách nhau 1 giây vẫn hỏi lại hết, dù
  vai, vị trí, chính sách đặt lịch, feature-mode gần như không đổi trong ngày.
  Xác thực thì đã rẻ: `getUser()` kiểm JWT tại chỗ (`lib/kiem-phien-tai-cho.ts`), FastAPI cache
  danh tính 30s (`api/identity.py:386`).
- **Độ chắc:** chắc chắn về thứ tự gọi; thời gian mỗi đợt: nghi (đo được).
- **Cách đo:** dev local, bật log thời gian ở `fetchFromBackend`, dựng `/ban-kham` 20 lần.
- **Hướng sửa:** cache ngắn hạn phía Next (30–60s theo `staff_id`) cho `/me`, `/feature-mode`,
  `/appointments/policy`, `/reports/access`, `/phan-quyen/toi` — làm mới khi đổi quyền
  (`lam_moi_luc` đã có sẵn); bỏ / cache lời gọi `staff` ở proxy (layout đã kiểm `/me`).
  **Rủi ro:** đổi quyền / đổi ca có trễ tới hết hạn cache — dùng `lam_moi_luc` làm hạn.

### D4 · VỪA · `/customers` ghi `nhac_tai_kham` trong lúc dựng trang — **đã biết** (kế hoạch 3b)

- **Xác nhận:** `customers/page.tsx:296-299` → `routers/cskh.py:317` →
  `recall_job_service.py:84-94` (`sinh_truoc=True`) → hàm SQL `sinh_viec_nhac_tai_kham`
  (`20260926000002_nhac_tai_kham_tu_phieu_v5.sql`): 2 câu `INSERT … ON CONFLICT DO NOTHING`,
  câu 1 quét `visit` 183 ngày kèm `jsonb_each(phieu_kham_luot.du_lieu)` từng lượt. Lời gọi
  khởi chạy sau đợt 2 của trang (`:226,296`) nên nằm trên đường chờ. Không tạo vòng tin
  (`nhac_tai_kham` không trong `LIVE_TABLES`). Câu "danh sách khách"
  (`danh_sach_khach_cskh.py:224`) sắp xếp theo `greatest(…)` của 3 truy vấn con cho MỌI
  khách — **đã biết** (KE-HOACH-HAM-SUC-CHUA, mục "không làm").
- **Độ chắc:** chắc chắn.
- **Hướng sửa:** như kế hoạch (chạy theo lịch trong worker, mỗi phòng khám ≤ 1 lần / 10 phút).

### D5 · THẤP · `MAN_TU_TAI` vẫn dựng lại cho `appointment` và khi tới giờ đổi quyền

- `lib/man-tu-tai.ts:33,53` giữ `appointment`, `work_roster` cho phần layout (chuông bác sĩ từ
  chối, vị trí hôm nay) — `appointment` là bảng đổi liên tục (lễ tân đặt/sửa lịch) → Bàn khám,
  Phòng vẫn dựng lại toàn trang (gánh cả D1, D3) mỗi lần có lịch đổi. Timer `lamMoiQuyenLuc`
  (`RealtimeRefresher.tsx:338-347`) gọi `nhip.nhan()` không xét `MAN_TU_TAI` (hiếm, đúng ý).
- **Hướng sửa:** chuông "bác sĩ từ chối" tự tải ở client qua `useNgheBang(["appointment"])`
  → bỏ `appointment` khỏi `BANG_LAYOUT`.

---

## Nhóm E — Hạ tầng: cache tĩnh, pool, SSE phía máy chủ, chỉ mục

### E1 · THẤP · Cache tĩnh (manifest/icon `max-age=0`) — **đã sửa trên `main`**, số đo dùng là số cũ

- **Ở đâu:** `caddy/Caddyfile:50-87` (snippet `tai_nguyen_tinh`: `/manifest.webmanifest`,
  `/favicon.ico`, `/icon.png`, `/apple-icon.png`, `/pwa/*`, logo → `public, max-age=86400,
  stale-while-revalidate=604800`, chỉ khi upstream 2xx), gắn ở `:198` trước khối
  `reverse_proxy dashboard`; bản staging chép nguyên văn, `src/tests/test_caddy_cache_tinh.py`
  canh hai bản khớp.
- **Nhận xét:** con số "~7.000 req/30 phút do `max-age=0`" là của 14/10 **trước** khi sửa
  (comment ghi 3.140 + 3.136 + 720). Kế hoạch 17/10 đã ghi "16/10 nhẹ hơn ~3 lần sau đợt sửa
  cache tĩnh". Không còn gốc mới ở đây.
- **Cách đo trên Mac:** stack dev có Caddy → `curl -sI https://localhost/manifest.webmanifest`
  phải ra đúng một dòng `Cache-Control: public, max-age=86400…`. Trên log prod lần sau: đếm
  lại `manifest.webmanifest` / 30 phút — phải về cỡ vài chục (mỗi máy ~1 lần/ngày).
- **Độ chắc:** chắc chắn (đã đọc cấu hình).

### E2 · VỪA · Tin realtime không mang **cơ sở** — ghi ở cơ sở B dựng lại màn ở cơ sở A — **MỚI** (kế hoạch S6 chỉ nói bảng + lượt/phòng)

- **Ở đâu:** `notify_row_change` (`supabase/migrations/20260806000001_notify_change_for_live_screens.sql:29-43`)
  chỉ gửi `{t: bảng, c: clinic_id}`; `ChangeBroker._on_notify` / `subscribe`
  (`src/clinicai/core/change_broker.py:117-140`) chia tin theo `clinic_id`; route SSE Next
  có gắn cơ sở (`app/api/events/stream/route.ts:51`, `ganCoSo`) nhưng phía FastAPI
  (`api/v1/routers/events.py:52`) không dùng nó để lọc.
- **Cơ chế:** từ 08/10 có hai cơ sở; mọi màn lọc dữ liệu theo cơ sở (`luot_kham_doc.py:131-137`)
  nhưng tin đổi thì không — mỗi lượt ghi ở cơ sở này nhân A1 lên cả số màn của cơ sở kia.
- **Ảnh hưởng:** tỉ lệ thuận với phần lượt ghi của cơ sở kia. Nếu cơ sở thứ hai đang ngừng
  hoặc ít khách thì hiện gần 0 — **nghi** (chưa biết số lượt ghi theo cơ sở). Khi cơ sở thứ
  hai chạy đủ, tải A1 tăng gần ×2.
- **Cách đo trên Mac:** stack dev với 2 cơ sở; tab A đứng cơ sở 1 mở `/reception/queue`; tab B
  đứng cơ sở 2 check-in một khách → tab A vẫn có request `?_rsc=`.
- **Đề xuất test:** test broker: tin có `l` (cơ sở) chỉ tới hàng đợi của người đứng đúng cơ
  sở hoặc người không chọn cơ sở; tin không có `l` vẫn tới mọi người (giữ đúng như cũ).
- **Hướng sửa:** trigger thêm `l` khi dòng có sẵn `location_id` (đọc `to_jsonb(NEW)->>'location_id'`,
  không tra thêm bảng); broker/SSE lọc theo cơ sở của người xem, tin không có `l` thì phát
  hết. Gộp vào S6. **Rủi ro:** bảng không có `location_id` (đa số) sẽ vẫn phát hết — đúng,
  chỉ không lợi; tuyệt đối không tra bảng khác trong trigger (thêm chi phí cho mọi lượt ghi). Mức 3.

### E3 · VỪA · Pool kết nối và số tiến trình API: kế hoạch S8 thiếu ngân sách kết nối — **kế hoạch thiếu**

- **Ở đâu:** `Dockerfile.api:41` — `uvicorn` **một** tiến trình, không `--workers`.
  `src/clinicai/core/database.py:24` `POOL_MAX_SIZE = 20`, comment `:17-23` ghi ngân sách
  `max_connections=100` (API 20 + checkpointer 10 + broker 1 + GoTrue 10 + PostgREST 10 +
  Realtime ~10 + worker). Worker `su-kien` có bể riêng `WORKER_POOL_MAX_SIZE = 10` (`:28`).
- **Cơ chế:** các chuỗi N+1 (D2 checkout, B4 thu ngân) giữ **một** kết nối hàng giây; D1 mượn/trả
  bể từng câu (hàng trăm lượt mượn mỗi lần dựng trang). Lúc cao điểm, khi DB chậm vì B1 chạy
  cùng giờ, 20 kết nối có thể bị giữ hết → request khác xếp hàng trong bể chứ không phải ở SQL
  (khớp kiểu "p95 1,5s nhưng câu SQL đơn lẻ nhanh").
- **Kế hoạch S8 ("2–4 tiến trình uvicorn + chỉnh pool"):** nếu giữ `POOL_MAX_SIZE=20` thì 4 tiến
  trình × 20 = 80, cộng phần còn lại (~45) **vượt 100** → lỗi `too many connections` đúng lúc cao
  điểm. Phải hạ trần mỗi tiến trình (vd 4 × 10) và ghi lại ngân sách trong cùng PR. Thêm tiến
  trình cũng **không** giảm số câu SQL — sửa D1/D2/B1 trước rồi mới đo xem có cần S8.
- **Độ chắc:** cấu hình chắc chắn; "bể cạn là nguyên nhân p95": **nghi** (comment `:17-19` cũng ghi
  "nghi cạn bể" 12/10).
- **Cách đo trên Mac:** stack dev + `scripts/do-tai` (khi có) hoặc 20 tab tự refresh;
  trong lúc chạy: `SELECT state, count(*) FROM pg_stat_activity WHERE application_name LIKE
  '%' GROUP BY 1` và log thời gian chờ `pool.acquire()` (bọc tạm trong `get_db_pool`).
- **Hướng sửa:** trước hết giảm việc (D1, D2, B1); sau đó nếu cần thêm tiến trình thì chia lại
  ngân sách (mức 3, hạ tầng).

### E4 · THẤP · `/api/luot-kham` — đắt vì SỐ LẦN gọi, không phải vì mỗi lần gọi — **xác nhận** (bổ sung C2)

- **Ở đâu:** proxy `app/api/luot-kham/route.ts:211-231` → `GET /api/v1/luot-kham/bang`
  (`api/v1/routers/luot_kham.py:171`) → `BangLuotKham.bang` (`services/luot_kham_doc.py:75-360`):
  ~10 câu theo **lô** (`= ANY($2::uuid[])`), không N+1; câu chính dùng chỉ mục biểu thức
  `idx_visit_ngay_check_in` (`20261014220000_chi_muc_visit_ngay_check_in.sql:17-18`) khớp từng chữ
  với điều kiện ngày ở `:124-125`.
- **Kết luận:** 3.557 lần / 30 phút đến từ phía trình duyệt (C2: Bàn khám 3 lời gọi mỗi tin, `null`
  khi mở lại SSE). Chỗ sửa là client (C2, A4), không phải SQL.
- Lặt vặt: mỗi lời gọi Next kiểm phiên 2 lần (`coPhien` `route.ts:211-216` rồi `proxyJsonToBackend`
  gọi lại `getUser()`+`getSession()`, `lib/backend-proxy.ts:53,109`) — kiểm JWT tại chỗ nên rẻ, bỏ
  được nhưng lợi nhỏ.
- **Độ chắc:** chắc chắn.

### E5 · THẤP · SSE phía máy chủ ổn; không cần broker/Redis — **xác nhận** (đúng `SO-LUAT` Phần 7)

- `change_broker.py`: một kết nối LISTEN riêng (không lấy từ bể), mỗi màn một hàng đợi 8 tin, đầy
  thì bỏ (`:41-45,130-135`) — màn chậm không chặn ai. `events.py:30,52-62`: nhịp giữ 20s, kiểm
  ngắt kết nối mỗi vòng. NOTIFY trùng nội dung trong **cùng** giao dịch được Postgres gộp làm một,
  nên một lệnh sửa nhiều dòng một bảng chỉ ra một tin.
- Chi phí mỗi lần mở lại dòng: kiểm JWT ở Next + `get_current_identity` (cache 30s,
  `api/identity.py:386`, JWT vẫn kiểm mỗi lần) — nhỏ. Vấn đề của SSE nằm ở **phía nhận** (A1, A4), không phải đường truyền.

### E6 · THẤP · Chỉ mục: các bảng nóng đã đủ cho những câu đã soát; hai điểm nhỏ

- **Đã có** (soát toàn bộ `supabase/migrations`): `payment_bill_line (clinic_id, source_type,
  source_id)`, `(clinic_id, payment_cycle_id)`, `(clinic_id, visit_id)`; `service_order (clinic_id,
  visit_id, created_at)`; `so_no (clinic_id, visit_id, chieu, seq DESC)`; `cong_no` một phần theo
  `CHUA_THU`; `payment_cycle` một phần theo trạng thái; `queue_entry` một phần theo hàng sống;
  `visit` theo ngày check-in, `created_at`, lượt đang mở. → Chậm ở nhóm B/D là do **số câu**
  và **ép kiểu trên cột** (B2), không phải thiếu chỉ mục.
- **Nhỏ 1:** `work_roster` chỉ có chỉ mục đơn (`staff_id`, `work_date`), không có ghép
  `(staff_id, work_date)` — vòng D1 đi `idx_work_roster_staff` rồi lọc. Sửa D1 (gom một câu) thì
  không cần chỉ mục mới.
- **Nhỏ 2:** `_chua_ngung` (`cashier_board_service.py:137-145`) gọi `co_so_cua_luot(uuid, uuid)`
  (`20261008710000_kho_theo_co_so.sql:119-128`) cho từng dòng ứng viên của bảng thu ngân. Hàm SQL có
  `FROM` nên Postgres **không nhúng** (inline) được → mỗi dòng một lần gọi, chỉ khi phòng khám có
  cơ sở đã ngừng. **Nghi** nhỏ (điều kiện rẻ `_LUOT_CU_DA_VE` lọc trước); đo bằng `EXPLAIN ANALYZE`
  bảng thu ngân trên staging-local, tìm `SubPlan` gọi hàm. Hướng sửa nếu đáng: nối thẳng
  `coalesce(v.location_id, a.location_id)` trong câu.

---

## Đối chiếu `docs/KE-HOACH-ON-DINH-VA-HOP-NHAT.md` (nhánh `claude/ke-hoach-on-dinh`)

| Điểm kế hoạch | Nhận định | Phát hiện |
|---|---|---|
| G1 — mọi tin dựng lại toàn trang | **Đúng** | A1 |
| G2 / S2 — tự lưu phiếu khám | **Đúng nhưng hẹp:** ô tư vấn, ghi chú, đơn thuốc cũng tự lưu và bắn tin; "S2 chỉ ~10–15%" đánh giá thấp phần tự lưu | A2 |
| G3 / S4 bỏ | Bỏ S4 hợp lý cho **dựng trang**, nhưng chưa tính các widget client tải lại theo tin `null` | A4, C2 |
| 3b "S1/S2/S3a Xong" | **Sai trạng thái** với `main` @ `00bde52`; tên migration S2 đụng giờ đã dùng | A3 |
| S5 staging đã có giới hạn | Đúng (đã được kế hoạch tự sửa) | — |
| G4 / S8 thêm tiến trình + pool | **Thiếu** ngân sách `max_connections`; thêm tiến trình không giảm số câu SQL | E3 |
| Cache tĩnh (ghi là đã sửa trước 16/10) | Đúng — đã có trên `main` | E1 |
| `/customers` ghi `nhac_tai_kham` khi dựng | Đúng | D4 |
| "Không cần Redis/broker" | Đúng | E5 |
| **Không nói tới** | Worker sổ nợ — nghi là nguồn chính của câu 67k lần; `/phan-quyen/toi` lặp theo ngày; N+1 checkout/thu ngân; ép kiểu uuid; `lich_vuot_suc_chua` không lọc phòng khám; refresh đôi sau thao tác; layout 3 đợt gọi không cache; tin không mang cơ sở | B1, D1, D2, B4, B2, B3, C1, D3, E2 |
