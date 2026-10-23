# Rà soát tốc độ toàn hệ thống — 23/10/2026

Rà soát **chỉ đọc** trên `main` @ `00bde52`. Phạm vi: backend `src/clinicai` (211 service,
57 router, worker sự kiện) và giao diện `src/dashboard`. Không sửa code, không chạm VPS.
Số câu SQL ở đây có được bằng cách **đọc code và đếm các `await conn.*`**, đọc sâu một tầng
hàm được gọi. Dấu `~` là ước lượng. Phần nào cần số đo thật thì nằm ở mục 6, tách riêng
khỏi phần đã chắc.

Bối cảnh (phiên trước):
- Ghi tiền mất ~0,13s, nhưng tải lại bảng quầy p95 ~3,4s.
- `pg_stat_statements` 14/10: câu `WITH v AS (vi.visit_id…` của quầy thu trung bình 4,3s,
  tối đa 14s; câu `WITH dong AS (…bl…` chạy 67.381 lần.
- Đo 17/10: mỗi lần ghi kéo theo 7–10 lần dựng lại trang ở mọi tab.

Ràng buộc khi đề xuất (`docs/SO-LUAT.md` Phần 6–7, CLAUDE.md mục 7):
- Không Redis, không hàng chờ, không máy chủ cache, không thêm bản sao.
- Số tiền trên màn và số tiền lúc thu phải ra từ **cùng một hàm**.
- Thao tác nào cũng hoàn tác được và cập nhật ngay ở mọi màn liên quan.
- Không đặt luật nghiệp vụ trong TSX.

---

## 1. Tóm tắt — gốc chậm, xếp theo mức ảnh hưởng

1. **Làm mới dây chuyền nhân với số tab.** Một lần thu tiền sinh ra **~3 đợt tin SSE cách
   nhau ~1 giây**, vì worker `su-kien` nghỉ cứng 1 giây giữa các vòng (`worker.py:329-333`)
   và mỗi bên nhận sự kiện ghi trong một giao dịch riêng. Các đợt cách nhau xa hơn khung gộp
   600ms + lệch 400ms, nên mọi tab đang mở ở "màn thường" bị `router.refresh()` khoảng 3 lần.
   Mỗi lần như vậy dựng lại cả layout: 2 lời gọi GoTrue và 6–8 lời gọi FastAPI.
   Danh sách 41 bảng áp chung cho mọi trang, trong đó có các bảng ghi theo nhịp tự lưu khi
   bác sĩ gõ:
   - `phieu_kham_luot`: 1,5 giây một lần;
   - `consultation_note`: 1 giây một lần.

   Kết quả: một bác sĩ đang gõ phiếu cũng làm mọi màn thường của cả hai cơ sở dựng lại liên tục.
2. **Layout gọi `/phan-quyen/toi`, và lời gọi đó quét toàn bộ lịch sử ca trực.** Hàm
   `CashierScopeService.days()` chạy **một câu SQL cho mỗi ngày trực từ trước tới nay, nhân
   2 quầy** với người không có ca thu ngân (bác sĩ, điều dưỡng, CSKH): ~200–500 câu mỗi lần
   dựng trang. Nó chạy ở **mọi lượt dựng trang của mọi tab**, nên mục 1 nhân thẳng vào đây.
   Ngay cả màn tự tải (thu ngân, bàn khám, phòng) cũng dựng lại layout mỗi khi bảng
   `appointment` đổi.
3. **Bảng quầy thu tính từng khách nối tiếp trên một kết nối.** Với mỗi lượt:
   - hoá đơn dịch vụ 9–10 câu;
   - tính lại hoá đơn dự kiến thêm 9–10 câu nữa khi còn chỉ định chờ khách quyết;
   - mỗi chỉ định gọi `PhongQuay.cua` 3–5 câu, và bộ nhớ của hàm này không bao giờ trúng;
   - hoá đơn thuốc 2 câu.

   Tổng **~300–2.000 câu cho mỗi lần tải** (20–80 lượt). Bảng chạy lại ở mọi tab quầy sau
   mỗi tin của 8 bảng.
4. **Nút "Thu" chờ ít nhất 2 lượt tải bảng mới nhả.** `await tai()` đi qua `lib/mot-luot.ts`,
   và lời hứa trả về bao luôn lượt tải do tin SSE của chính lần thu chen vào. Với p95 ~3,4s
   mỗi lượt, người thu ngân chờ khoảng **~7s** cho một thao tác mà máy chủ chỉ ghi mất 0,13s.
5. **Màn check-out (`/reception/checkout`) bị N+1 và tải ba lần.**
   - Mỗi lượt chưa đóng trong ngày tốn ~20–25 câu (hoá đơn, nợ khi về, tiền thừa, thuốc):
     ~1.000–2.000 câu mỗi lần tải.
   - Mỗi tin làm màn tải 3 lần: bản dựng ở máy chủ (rồi bị bỏ, vì
     `useState(initial)` không nhận prop mới), lượt tải của client, và khối "lượt tồn".
6. **Câu chọn ứng viên của quầy thu (`WITH v AS`) chậm sẵn: trung bình 4,3s.** Vế "lượt cũ"
   quét mọi lượt trước hôm nay, kèm `EXISTS` lồng ba tầng và hàm `co_so_cua_luot` chạy theo
   từng dòng. Phải `EXPLAIN ANALYZE` trên staging local trước khi chọn cách sửa.
7. **Việc nền và báo cáo đọc toàn lịch sử.**
   - Vòng đối chiếu sổ nợ chạy mỗi 10 phút, xét tới 300 lượt × ~25–29 câu (≈5–9 nghìn câu).
     Đây gần như chắc là nguồn của câu `WITH dong AS` 67.381 lần.
   - Báo cáo cuối ngày (`_thua`) đọc **mọi lượt từ trước tới nay** rồi mới lọc.
   - Tồn kho thuốc tính "khả dụng" theo Σk² (k = số lô của mỗi thuốc).

**Chưa thấy logic tiền nào sai.** Cách sửa đúng cho mục 3 và 5: tách `hoa_don_con_no` thành
(a) **đọc gộp cho N lượt** và (b) **hàm dựng thuần dùng chung**. Lệnh thu vẫn gọi đúng hàm
dựng ấy, trong giao dịch có khoá, và vẫn so `revision`.

---

## 2. Bảng chính

**Cách đọc bảng:**
- **Kiểu:** A = N+1 trên đường đọc · B = nút chờ tải lại · C = làm mới dây chuyền ·
  D = trang hoặc câu nặng, tính hết rồi mới cắt, tính trùng.
- **Mức:** theo CLAUDE.md; chạm tiền, kho, quyền hay migration là mức 3.
- **Ưu tiên:** P1 làm trước · P2 · P3 · P4 để sau hoặc chỉ làm khi đo thấy đáng.
- **Màn tự tải** là các route trong `MAN_TU_TAI` (`lib/man-tu-tai.ts:23-29`). **Màn thường**
  là mọi route khác.

### 2.1 Làm mới dây chuyền (C) — hệ số nhân của mọi thứ còn lại

| # | Màn (URL) | Tệp:dòng | Kiểu | SQL / lượt gọi × nhân theo gì | Khi nào chạy | Cách sửa | Mức | Ưu tiên |
|---|---|---|---|---|---|---|---|---|
| C1 | Mọi màn thường; mọi màn có `useNgheBang` | `src/clinicai/worker.py:329-333` (nghỉ 1,0s); `events/catalogue.py:2164-2179` (`payment.service_collected` có 5 bên nhận, mỗi bên một giao dịch) | C | Một lần thu → **~3 đợt NOTIFY** (t0, ≤1s, ≤2s) × mỗi tab đang hiện → ~3 lượt `router.refresh` (2 GoTrue + 6–8 API mỗi lượt) + ~3 lượt tải của mỗi khối `useNgheBang` khớp bảng | Mọi lệnh ghi có bên nhận sự kiện | Cho vòng `su-kien` **thức khi có NOTIFY `event_log`** như worker relay đã làm (`worker.py:133-144`), giữ nghỉ 1s làm dự phòng. Chuỗi bên nhận xong trong ~100–300ms, nên lớp gộp sẵn có ở client gom thành 1 đợt. Không đổi chuỗi sự kiện hay thứ tự ghi | 2 | **P1** |
| C2 | Mọi màn thường (`/home`, `/reception/queue`, `/phong`, `/pharmacy`, `/appointments`, `/customers`…) | `app/(dashboard)/RealtimeRefresher.tsx:88-147` (41 bảng); `layout.tsx:166` (không truyền `tables`); `lib/man-tu-tai.ts:46-53` | C | `phieu_kham_luot` (tự lưu 1,5s, `PhieuKham.tsx:73` → `phieu_kham_service.py:473/486`), `consultation_note` (1s, `OTuVanTuLuu.tsx:28`), `luot_dong_thoi_gian` (gần như mỗi sự kiện) → mỗi tin = 1 lượt dựng trang × mọi tab màn thường × 2 cơ sở | Liên tục trong giờ khám | **Danh sách bảng theo route** trong `man-tu-tai.ts`: route → các bảng mà phần server của nó đọc thật; route chưa khai thì giữ 41 bảng như cũ cho an toàn. Bỏ ngay 3 bảng trên khỏi tập "dựng trang" — những khối thật sự cần chúng đã tự nghe bằng `useNgheBang` (LichSuDonThuoc, HanhTrinh*). Trigger giữ nguyên, nên không có migration | 2 | **P1** |
| C3 | Mọi trang (layout) | `services/cashier_scope_service.py:243-312` `days()` ← `cashier_navigation_service.py:42-44` ← `api/v1/routers/phan_quyen.py:163-177` ← `dashboard/lib/clinic-session.ts:105` | A | 2 câu + **1 câu `_ROSTER` cho mỗi ngày trực APPROVED từ trước tới nay** + 2 câu, nhân 2 quầy. Với người không khớp quầy, vòng không bao giờ `break` (`:283` `continue`, `:312`) → ~200–500 câu, tăng ~2 câu mỗi ngày | **Mỗi lượt dựng trang** của mọi tab, kể cả mỗi `router.refresh` ở C1/C2/C4 | Một câu lấy **mọi** dòng ca của người ấy (giữ đúng nghĩa hiện tại, không thêm mốc), gom theo ngày trong Python rồi chạy `allowed_roster` từng ngày. `cashier_navigation` chỉ cần biết "có ngày khớp không", nên đọc một lần cho cả 2 quầy. Bỏ lần đọc `clinic.settings` thứ hai (`:240`, `:324`). Thêm mốc dưới (vd 400 ngày) là quyết định nghiệp vụ → hỏi Tuyền | 3 (quyền) | **P1** |
| C4 | Màn tự tải: `/thu-ngan/*`, `/ban-kham`, `/tu-van`, `/phong/[ma]`, `/hanh-trinh` | `lib/man-tu-tai.ts:33` `BANG_LAYOUT = ["appointment","work_roster"]`; `layout.tsx:105` (`DeclinedNotice`) | C | Mỗi tin `appointment` (đặt lịch, check-in, xác nhận CSKH, đồng bộ hẹn tái khám) → dựng lại layout (gồm C3) ở mọi tab thu ngân, bàn khám, phòng | Rất thường xuyên | Đổi `DeclinedNotice` thành khối client tự tải, nghe `useNgheBang(["appointment"])`. `BANG_LAYOUT` chỉ còn `work_roster` | 2 | P2 |
| C5 | `/reception/checkout`, `/truong-ca`, `/do-sinh-hieu`, `/viec-can-xu-ly` | `reception/checkout/CheckoutBoard.tsx:66` (`useState(initial)`), `:115`, `:167-168`; `truong-ca/shared.tsx:74,118`; `LiveBoardSync.tsx:48-52` (gắn ở `phong/page.tsx:63`, `reception/queue/page.tsx:67`, `reception/checkout/page.tsx:32`, `truong-ca/page.tsx:19`); `do-sinh-hieu/page.tsx:19`, `viec-can-xu-ly/page.tsx:17` | C/D | Checkout: mỗi tin = SSR (kết quả **bị bỏ**) + `reload()` + `LuotTonDong` → **×3**, mỗi lần đóng lượt ×3–4. Trưởng ca: SSR (bị bỏ) + `pull()` → đọc bảng điều phối 4 lần. Sinh hiệu, Việc cần xử lý: phần server không có dữ liệu sống mà vẫn bị refresh. LiveBoardSync: vào màn là dựng trang 2 lần | Mỗi tin, mỗi lần vào màn | Thêm 4 route vào `MAN_TU_TAI`. Bỏ `router.refresh()` ở `CheckoutBoard.tsx:168`. Thay LiveBoardSync ở checkout và trưởng ca bằng một lần client tự nạp khi vào màn. Sửa comment sai ở `man-tu-tai.ts:15-17` và test `tests/tai-lai-dong-loat-boundary.test.mts` | 2 | **P1** |
| C6 | Mọi màn (đúng đắn) | `src/clinicai/core/change_broker.py:45` (`QUEUE_SIZE = 8`), `:131-135` (đầy thì bỏ tin) | C | Từ khi client lọc theo tên bảng, bỏ một tin có thể làm một màn **không bao giờ** thấy thay đổi của bảng ấy. Trái luật "không màn nào mất cập nhật". Comment `:40-43` nay đã sai | Tab chậm, 4G, giờ cao điểm | Khi đầy: xoá hàng của client đó, đẩy một tin không có `t` để client hiểu là `null` ("không rõ bảng — hỏi lại hết"). Thêm bộ đếm tin bị bỏ vào log | 2 | P2 (làm trước C10) |
| C7 | Mọi tab | `change_broker.py:117-135`; `20260815000003…sql:16-18` (`event_log`), `20261014140000…sql:108` (`so_no`) | C | `event_log` (mỗi `emit_event`) và `so_no` (lô đầu kỳ và đối chiếu mỗi phút) được đẩy tới mọi tab dù không màn nào nghe | Liên tục | Broker không chuyển tiếp hai bảng này tới trình duyệt. Worker relay LISTEN bằng kết nối riêng nên không bị ảnh hưởng | 1 | P3 |
| C8 | Màn thường (lưới an toàn) và các nhịp hỏi riêng | `RealtimeRefresher.tsx:83,319-325` (60s, không xét SSE); `CheckoutBoard.tsx:122`, `BanKham.tsx:322`, `PhongDichVu.tsx:236`, `BangDoSinhHieu.tsx:223`, `BangHanhTrinh.tsx:85`, `BangViecCanXuLy.tsx:94` (60s); `truong-ca/shared.tsx:109`, `NgayTruc.tsx:53` (30s); `appointments/dung-giu-cho.ts:90` (5s) | C | Mỗi tab đang hiện tự dựng lại hoặc tự tải 1 lần/phút (hoặc 30s, 5s) **dù SSE khoẻ** | Liên tục | Chỉ hỏi dự phòng khi dòng SSE chết, xét `canHoiDuPhong(trangThaiDong…)` như `NotificationContext.tsx:344`. Nhịp 5s của giữ chỗ là con số đã ghi ở `SO-LUAT` Luật 6.4 ("khi 6.3 xong thì bỏ hỏi lại hẳn") → đổi phải sửa sổ luật, Tuyền gật | 1–2 | P2 |
| C9 | Mọi tab | `NotificationContext.tsx:219` (nghe `thong_bao`) | C | Mỗi thông báo cho **một** người làm mọi tab đang hiện gọi lại `/thong-bao` (2 GoTrue + 1 API) | Mỗi thông báo | Đo tần suất trước (mục 6). Nếu đáng: thêm người nhận vào tin, hoặc lọc ở broker | 3 (trigger) | P4 |
| C10 | Mọi màn khi có 2 cơ sở | `20260806000001_notify_change_for_live_screens.sql:18-48` (tin chỉ có `{t, c}`) | C | Hào Nam và Kim Ngưu làm mới lẫn nhau → tải gấp ~2 | Mọi tin | Thêm `l` (cơ sở) vào tin, broker lọc theo cơ sở người xem; tin không có `l`, hoặc người xem "mọi cơ sở", vẫn nhận. Cần migration đổi trigger | 3 | P4 (sau C6) |

### 2.2 Quầy thu — `/thu-ngan/dich-vu`, `/thu-ngan/thuoc`

| # | Màn (URL) | Tệp:dòng | Kiểu | SQL × nhân theo gì | Khi nào chạy | Cách sửa | Mức | Ưu tiên |
|---|---|---|---|---|---|---|---|---|
| Q1 | `/thu-ngan/*` (GET `/api/v1/cashier/board`, `cashier.py:84`) | `services/cashier_board_service.py:708-737` → `bill_service.py:1126` `tinh_hoa_don` → `:853-981` `hoa_don_con_no` | A | **Dịch vụ: 9–10 câu mỗi lượt.** Gồm `THU_CU_KHONG_TRUY_DUOC` 1, `_kham` 2, `nguon_da_phu` 1, `legacy` 1, chỉ định 1, phụ thu 1, vật tư 1, liệu trình 1, đối tác ±1. **Thuốc: 2 câu mỗi lượt**, trong đó đọc lại **cả bảng giá thuốc mỗi lượt** (`bill_service.py:1155`). Nhân 20–80 lượt, chạy nối tiếp trên 1 kết nối | Mở màn; **mỗi tin** của 8 bảng (`QuayThuNgan.tsx:301-318`) × mọi tab quầy; sau mỗi lệnh | Tách hai phần. **(a) `doc_nguon_hoa_don(conn, clinic_id, visit_ids)`**: mỗi câu trên đổi `vi.visit_id = $2` thành `= ANY($2::uuid[])` và trả kèm `visit_id`, tổng ~9 câu cho **cả bảng**. **(b) `dung_hoa_don_con_no(visit_id, nguon, coi_nhu_chon)`** thuần. `hoa_don_con_no` giữ nguyên chữ ký = (a) cho 1 lượt + (b), nên lệnh thu không đổi. Chi tiết ở mục 3, PR-J | 3 | **P1** |
| Q2 | `/thu-ngan/dich-vu` | `cashier_board_service.py:754-760` → `:892-915` `_quay_thu` | A | Lượt còn chỉ định PENDING thì gọi **lại** `hoa_don_con_no(coi_nhu_chon=…)`: +9–10 câu mỗi lượt | Như Q1 | Đọc gộp lấy luôn dòng PENDING (kèm `selection_status`); hàm dựng thuần lọc theo `coi_nhu_chon` → **0 câu thêm**. Vẫn cùng luật giá, cùng `revision` | 3 | **P1** |
| Q3 | `/thu-ngan/dich-vu` | `service_selection_service.py:394-409` `cho_khach_quyet` gọi `pq.cua` theo từng chỉ định; `cashier_board_service.py:742-752` (ô xếp phòng); `quay_thu_service.py:99-159` `PhongQuay.cua` | A | 3–5 câu mỗi chỉ định × 10–30 chỉ định → ~40–180 câu. Nguyên nhân: `co_so_cua_luot` (`:121`) chạy **trước** chỗ hỏi bộ nhớ; khoá nhớ chứa `visit_id` (`:122`) nên giữa các lượt **không bao giờ trúng**; hai đối tượng `PhongQuay` (`service_selection_service.py:389` và `cashier_board_service.py:696`) không dùng chung bộ nhớ | Như Q1 | Đọc cơ sở cho mọi lượt một lần (`ANY`). Khoá nhớ chỉ còn `(node, service_code, co_so)`. Phần `tru_luot` (không đếm chính khách vào số người chờ của phòng) đổi thành trừ 1 trong Python cho phòng có khách ấy. Board truyền **một** `PhongQuay` cho cả `cho_khach_quyet`. `eligible_rooms` / `lua_chon_bac_si` chạy mỗi cặp khác nhau một lần | 3 | **P1** |
| Q4 | `/thu-ngan/*` | `cashier_board_service.py:151-387` `_SQL` (`WITH v AS`) | D | Một câu, nhưng `pg_stat_statements` 14/10 cho TB **4,3s**, tối đa 14s. Nghi phạm: (1) vế lượt cũ chưa về (`old.created_at < $2`, **không có mốc dưới**) kèm `_CU_CHI_DINH`/`_CU_DON_THUOC`/`_CU_CK_CHUA_VE` (`EXISTS` lồng service_order × payment_bill_line × payment_cycle, so `bl.source_id = so.id::text`); (2) subquery `cho_tu` cho mỗi lượt; (3) `_chua_ngung` gọi `co_so_cua_luot` theo dòng ở 4 vế; (4) 4,3s có thể gồm thời gian chờ khoá hoặc CPU do chính tải dây chuyền | Mỗi lần tải board | **Đo trước** bằng `EXPLAIN (ANALYZE, BUFFERS)` trên staging local (mục 6). Hướng sửa tuỳ kết quả: chỉ mục một phần cho lượt chưa về (`visit (clinic_id, created_at) WHERE closed_at IS NULL`); đưa `co_so_cua_luot` về JOIN `coalesce(vi.location_id, a.location_id)`; tách vế lượt cũ thành câu riêng. Có thay đổi chỉ mục thì cần migration | 3 | **P1** (đo) / P2 (sửa) |
| Q5 | `/thu-ngan/*` | `thu-ngan/QuayThuNgan.tsx:338→394→399` (`gui`); `:515→534→538` (`chotThuSau`) | B | Nút chờ **≥2 lượt `/api/cashier` nối đuôi**. Lượt 1 là `await tai()`; lượt 2 là tin SSE của chính lần thu chen vào sau 250ms + 0–400ms (xem Q6). Worker xếp phòng chạy ngay sau đó có thể thêm lượt 3. Câu "Đã thu…" và nút Check-out (`:458`, `:498`, `:563`) cũng chỉ hiện sau khi tải xong | Mỗi lần thu, mỗi lần chốt thu sau | `setDangThu(null)` và hiện câu báo **ngay khi lệnh ghi trả OK**; `void tai()` không chờ. Riêng nút "Thu" **của đúng lượt ấy** giữ khoá cho tới khi bảng mới về (`revision` đổi), để không bấm trên hoá đơn cũ. Máy chủ vẫn chặn `BILL_CHANGED` và khoá `Idempotency-Key`, nên không thể thu trùng | 3 (UI tiền) | **P1** |
| Q6 | Mọi chỗ dùng `taoMotLuot` | `dashboard/lib/mot-luot.ts:23-41` | B | Lời hứa trả về là **cả vòng `while (sau)`**, gồm mọi lượt chen vào trong lúc đang tải. Một lượt ném lỗi thì việc đang xếp hàng bị xoá (`finally { sau = null }`) và mọi người đang `await` nhận lỗi ấy | — | Nút không `await` nữa (Q5). Nếu vẫn cần chờ: trả lời hứa của **đúng lượt chạy việc của người gọi**, không phải cả vòng. Sửa comment `:16-17` cho đúng hành vi | 2 | P2 |
| Q7 | `/thu-ngan/dich-vu` | `thu-ngan/ChonDichVu.tsx:134→215` (`await onXong`), `:166-190` (`phong-du-kien` gửi **tuần tự** từng dịch vụ); `QuayThuNgan.tsx:837-841`, `:983-988` | B | ≥2 lượt cashier + N lệnh ghi phòng nối đuôi | Chốt dịch vụ, chọn phòng | Con `setDang(false)` trước `onXong`; cha bỏ `await`. Gửi phòng song song (`Promise.all`) hoặc gộp thành một lệnh | 3 | P2 |
| Q8 | `/thu-ngan/dich-vu` | `thu-ngan/VatTuQuay.tsx:79-94`; `QuayThuNgan.tsx:795` (`onDoi={tai}`); `HoaDonMot.tsx:416,425` | B | Đã áp `kq.data` mà vẫn `await onDoi()`, nên `dangGui`/`onDangLuu` khoá luôn nút Thu suốt ≥2 lượt cashier | Thêm hoặc bớt vật tư | Nhả `dangGui` ngay. Nút Thu chờ hoá đơn mới bằng cờ riêng theo `revision` (như Q5) | 3 | P2 |
| Q9 | `/thu-ngan/thuoc`, `/pharmacy` | `thu-ngan/ChinhDonQuay.tsx:152-156`; `QuayThuNgan.tsx:890-894` | B | Tải `quay-thuoc` **rồi mới** tải cashier, nối đuôi (1 + ≥2 lượt). Ô tick đứng yên, bấm lần nữa là đảo ngược | Tick mua / sửa số lượng | Vá `mua`/số lượng tại chỗ từ phản hồi `{ok, prescription_id, mua}` (`quay_thuoc_service.py:263`); hai lượt tải chạy song song, không chờ | 3 (kho) | P2 |
| Q10 | `/thu-ngan/dich-vu` | `VatTuQuay.tsx:65-69`, `LieuTrinhQuay.tsx:38-46` (`reloadToken = quay_thu.revision`) | D | Chính khối vừa ghi → board tải lại → `revision` đổi → khối **tải lại lần nữa** (+1–2 lượt mỗi lần ghi) | Mỗi lần ghi vật tư / liệu trình | Bỏ qua lần đổi `reloadToken` do chính mình vừa ghi (so với `revision` trong phản hồi) | 2 | P3 |
| Q11 | `/thu-ngan/*` tab Giao dịch | `hoan_tien_service.py:577-578` `hoan_cua_cac_lan_thu` → `_con_hoan` (`:515`), gọi từ `cashier_board_service.py:535` | A | 1 câu mỗi lần thu đã PAID: ~60–150 mỗi ngày, tới 1.000 khi chọn khoảng ngày | Mở sổ giao dịch, đổi ngày | Một câu `payment_cycle_id = ANY($2::uuid[])`, trả kèm id, gom thành dict | 3 | P3 |
| Q12 | `/thu-ngan/*` | `api/v1/routers/cashier.py:68-73` (`authorize_active` cho từng quầy) | A | 2 × ~2 câu | Mỗi lần tải board | Gộp khi làm C3 | 3 (quyền) | P4 |

### 2.3 Check-out — `/reception/checkout`

| # | Màn (URL) | Tệp:dòng | Kiểu | SQL × nhân theo gì | Khi nào chạy | Cách sửa | Mức | Ưu tiên |
|---|---|---|---|---|---|---|---|---|
| K1 | `/reception/checkout` (GET `/api/v1/reception/checkout`, `dispatch.py:383`) và lượt treo (`checkout_service.py:706`) | `services/checkout_service.py:1051-1098` `_gan_doi_tac_tu_thu`, gọi từ `pending_list` `:428` (`LIMIT 300`) | A | Mỗi lượt gồm: `hoa_don_con_no` 9–10 + `no_khi_ve` ~5–7 (`cong_no_service.py:277`) + `tien_thua_khi_ve` 2 (`tien_thua_service.py:233`) + hoá đơn thuốc 2 → **~20–25 câu mỗi lượt** × lượt hôm nay chưa đóng (~50–80) → **~1.000–2.000 câu** | Mở màn; mỗi tin (×3 do C5); sau mỗi lần đóng lượt | Dùng đọc gộp của PR-J. Thêm bản gộp cho `no_khi_ve` (nhận `hd_dich_vu` đã dựng — đã có tham số này) và cho `tien_thua_khi_ve` (`dong_tien_thua`, `giu_lai_dang_co` đã nhận mảng). Câu chính `_READINESS_SQL` đã là một câu (tốt) | 3 | **P1** |
| K2 | `/reception/checkout` | `reception/checkout/LuotTonDong.tsx:131→156→161` | B | Hộp đã đóng nhưng `dangGui` giữ đến khi tải xong | Đóng lượt tồn | `setDs(ds.filter(...))` rồi `void tai()` | 2 | P3 |

### 2.4 Sổ nợ, việc nền, báo cáo

| # | Màn (URL) | Tệp:dòng | Kiểu | SQL × nhân theo gì | Khi nào chạy | Cách sửa | Mức | Ưu tiên |
|---|---|---|---|---|---|---|---|---|
| N1 | (nền, worker `su-kien`) | `services/so_no_service.py:595-613` `_doi_chieu` → `ghi_chenh_lech` `:270` → `so_du_hien_tai` `:215`; nhịp `NHIP_GIAY = 600` (`:79`), `DOI_CHIEU_MOI_VONG = 300` (`:83`); `worker.py:318-320` | A | ~25–29 câu mỗi lượt: khoá, `_LUOT_SQL`, `no_khi_ve` (gồm `hoa_don_con_no`), `_CK_CHO`, `dong_tien_thua`, `_CHUA_LAM`, `tien_da_thu_cua_chi_dinh`, `_THUOC_PHAI_TRA`, 2 × `_CUOI`, `SELECT now()`. Nhân ≤300 lượt mỗi 10 phút → **~5–9 nghìn câu**. `_CAN_XET_SQL` (`:528`) gồm mọi lượt còn số dư ≠ 0, **xét lại mãi** dù không gì đổi. `_THUOC_PHAI_TRA_SQL` (`:128`, mở đầu `WITH dong AS ( SELECT bl.source_id…`) và `tien_da_thu_cua_chi_dinh` (`hoan_tac_service.py:282`, cũng `WITH dong AS`) chạy mỗi lượt một lần → khớp con số 67.381 | Mỗi 10 phút, cả giờ cao điểm | Chỉ xét lượt **có sự kiện tiền mới** kể từ vòng trước (con trỏ theo `domain_event`) cộng lượt vừa về trong 48h. Lượt số dư ≠ 0 mà nguồn không đổi thì bỏ qua. Khi PR-J xong, dùng đọc gộp cho cả lô. Không đổi luật tính số dư | 3 | P2 |
| N2 | (nền, consumer `so_no`) | `events/consumers/so_no.py:93-120` `ghi_so` | A | ~29 câu mỗi lượt × 1–3 lượt | Mỗi sự kiện tiền | Chấp nhận được; gom theo N1 nếu đo thấy chậm | 3 | P4 |
| R1 | `/reports?tab=cuoi-ngay` (+ `.csv`, `.xlsx`, `reports.py:150,256,308`); POST chốt ca (`chot_so_ca_service.py:183`) | `services/bao_cao_viec_tien_service.py:78-122` `_thua` | D | Câu `:84-101` lấy **mọi lượt từ trước tới nay** (chỉ lọc cơ sở), rồi truyền mảng hàng chục nghìn uuid cho `dong_tien_thua` + `giu_lai_dang_co`, lọc `so > 0`, cắt 100 dòng (`_gom`) | Mỗi lần mở báo cáo, xuất tệp, chốt ca | Đi ngược: từ dòng hoá đơn **đã thu** của chỉ định huỷ / không làm / khám bỏ tick (đúng nguồn của `dong_tien_thua`) suy ra tập lượt, rồi mới gọi `dong_tien_thua`. Không đổi công thức tiền thừa | 3 | P2 |
| R2 | `/reports?tab=cuoi-ngay` | `services/tien_thua_service.py:293-335` `bao_cao_tien_thua` (`bao_cao_cuoi_ngay_service.py:1285`) | D | Lọc ngày bằng `(coalesce(checked_in_at, created_at) AT TIME ZONE …)::date`, không dùng được chỉ mục → quét lượt cả phòng khám; `co_so_cua_luot` ×2 mỗi dòng (`:309-311`) | Mở báo cáo | Lọc theo khoảng `timestamptz`; JOIN appointment thay cho gọi hàm | 3 | P3 |
| R3 | `/reports?tab=cuoi-ngay`; `/home` của quản lý (`man_trang_chu_service.py:437`) | `so_no_service.py:336-342` `_SO_DU_TOI_SQL` (chạy ×2), `:452-518` `_SO_DU_MO_SQL` | D | `DISTINCT ON (visit_id, chieu)` trên **toàn bộ** `so_no` trước mốc; khi lọc cơ sở thì `co_so_cua_luot` mỗi dòng. Trang chủ chỉ cần đếm và tổng mà tải hết danh sách | Mở báo cáo; mở hoặc làm mới `/home` (× C1/C2) | EXPLAIN trước. Đã có chỉ mục `(clinic_id, visit_id, chieu, seq DESC)` (`20261014140000:64`). Hướng: đọc dòng cuối bằng LATERAL/`DISTINCT ON` có lọc sớm; tổng và đếm bằng SQL khi `kem_ds=False` | 3 | P2 |
| R4 | `/reports` (tab Vận hành) | `app/(dashboard)/reports/page.tsx:70→104→157→165` | D | access → tq → chan → kpi **nối đuôi** (4 vòng) | Mở báo cáo | `Promise.all([tq, chan, kpi])` sau access → 2 vòng | 2 | P3 |
| R5 | `/audit-log` | `app/(dashboard)/audit-log/page.tsx:43` | D | Lấy toàn bộ nhật ký từ đầu ngày, không phân trang | Mở màn | Phân trang theo con trỏ | 2 | P4 |

### 2.5 Kho thuốc, bán lẻ, vật tư

| # | Màn (URL) | Tệp:dòng | Kiểu | SQL × nhân theo gì | Khi nào chạy | Cách sửa | Mức | Ưu tiên |
|---|---|---|---|---|---|---|---|---|
| W1 | `/pharmacy/inventory` (GET `/api/v1/pharmacy/inventory`, `pharmacy.py:297`) | `services/pharmacy_service.py:269-340` `ton_kho` | D | 1 câu nhưng mỗi lô cộng `drug_batch_kha_dung` của **mọi lô anh em** (`:305-314`) → Σk² lần gọi hàm (mỗi lần 3 subquery). Thêm `co_so_cua_luot` cho mỗi dòng giao chưa gán lô (`:302`). Không LIMIT, gồm cả lô đã hết | Mở màn; mỗi lệnh kho (`router.refresh` chạy lại 7 lời gọi + layout, `inventory/page.tsx:50-62`) | CTE tính `kha_dung` **một lần mỗi lô**, rồi `sum() OVER (PARTITION BY drug_catalog_id, lower(trim(unit)))`. Gộp sẵn phần "giao chưa gán lô" theo (thuốc, đơn vị, cơ sở). Kết quả phải trùng từng số với bản cũ | 3 (kho) | P2 |
| W2 | `/pharmacy/lich-su` (`pharmacy.py:420`) | `pharmacy_service.py:194-236` `lich_su_giao` | D | **Mọi** dòng đơn đã giao từ trước tới nay; `co_so_cua_luot` ×2 mỗi dòng trong WHERE; ORDER BY `dispensed_at` không có chỉ mục → tính hết rồi LIMIT 200 | Mở màn | JOIN thẳng visit/appointment, viết `coalesce(v.location_id, a.location_id)` một lần. Chỉ mục `(clinic_id, dispensed_at DESC) WHERE dispensed_qty > 0` (migration) | 3 (kho) | P3 |
| W3 | `/pharmacy` (hàng đợi, chờ tư vấn, chờ gán lô) | `pharmacy_service.py:143-192` `hang_doi`, `:238-267` `cho_tu_van`, `:1008-1060` `cho_gan_lo` | D | `co_so_cua_luot` 2–3 lần mỗi dòng | Mở màn; tin `prescription` | Như W2: JOIN thay cho gọi hàm | 3 (kho) | P3 |
| W4 | `/pharmacy` (bán lẻ) | `pharmacy/BanLeThu.tsx:88,145-146,215-216,231-232`; `LichSuDonThuoc.tsx:320-323,346-349` | C/D | Một lần thu ở quầy bán lẻ: `await tai()` + `router.refresh()` tay + SSE (BanLeThu `tai` + LichSuDonThuoc + RealtimeRefresher, vì `/pharmacy` không phải màn tự tải) → ban-le ×2, lich-su-don ×2, dựng trang ×2. Nút đã nhả trước khi tải (tốt) | Mỗi lần thu bán lẻ | Bỏ `router.refresh()` tay và lượt `taiTrang` gọi tay; để SSE làm tươi. Không đổi lệnh ghi | 2 | P3 |
| W5 | `/pharmacy` (lịch sử đơn của khách, `pharmacy.py:232`) | `services/ban_theo_don_service.py:349-351` `lich_su_don` → `_doc_goc` `:287-308` | A | 4 câu mỗi đơn (`_DAU_DON`, `_DONG_KE`, `_DA_MUA`, `doc_hen_luot`) × 10 đơn/trang = 40 | Chọn khách, lật trang | 4 câu `visit_id = ANY($2::uuid[])`; `_DA_MUA` gom theo `coalesce(k.don_goc_visit_id, bl.visit_id)` → 4 câu | 3 (đọc bill_line/refund) | P3 |
| W6 | `/kho-vat-tu` | `kho-vat-tu/KhoVatTu.tsx:70-72` (`taiLaiKho` = `router.refresh()`), `ChoDuyetVatTu.tsx:86` | C | `vat_tu_txn` vừa được RealtimeRefresher refresh vừa được KhoVatTu refresh, hai nhịp gộp riêng → dựng trang 2 lần | Mỗi lệnh vật tư | Bỏ `useNgheBang` tự refresh (RealtimeRefresher đã lo), hoặc đưa `/kho-vat-tu` vào danh sách bảng theo route (C2) | 2 | P3 |
| W7 | `/pharmacy/inventory` (kiểm kê ca) | `pharmacy/inventory/KiemKeCa.tsx:215→326/339` | B | `await docLai(phieu.id)` | Ghi kiểm kê | Nhả cờ trước, `void docLai()` | 2 | P4 |

### 2.6 Khám, tiếp đón, CSKH, đặt lịch

| # | Màn (URL) | Tệp:dòng | Kiểu | SQL × nhân theo gì | Khi nào chạy | Cách sửa | Mức | Ưu tiên |
|---|---|---|---|---|---|---|---|---|
| L1 | `/nhac-tai-kham`, `/customers` (GET `/api/v1/cskh/recall-jobs`, `cskh.py:317`) | `services/recall_job_service.py:141-148` → `hen_tai_kham_service.py:196-236` `chi_tiet_viec` | A | 4 câu mỗi việc (visit, `phieu_kham_luot` qua `doc_hen_luot`, **`phieu_kham_luot` lần nữa** qua `doc_chan_doan`, appointment) × 10–60 việc (trần 500). GET này còn chạy `sinh()` (một lệnh ghi) mỗi lần | Mở màn | Viết `chi_tiet_cac_viec(conn, cid, visit_ids)`: 3 câu `ANY` (đọc `phieu_kham_luot` một lần, lấy cả `tao_luc` và `sua_luc`). Có thể dùng lại ở `ghi_chu_khach_service.py:346` | 2 | P3 |
| L2 | `/ban-kham`, `/tu-van` (hồ sơ; GET `/clinical-records/doc`, `clinical_records.py:69`) | `services/clinical_record_service.py:972-982` `lich_su_cho_ho_so` → `phieu_kham/mang_sang.py:229` `doc_chan_doan` | A | 1 câu mỗi lượt trước của khách (khách quen 20+, trần 200) | Mỗi lần mở hồ sơ | Một câu `phieu_kham_luot WHERE visit_id = ANY($ids)`, chạy `chan_doan_tu_phieu` trong Python | 2 | P3 |
| L3 | `/appointments` (popover đổi dịch vụ; `booking.py:814`) | `services/doi_dich_vu_kham.py:240-250` → `booking_service.py:2148` | A | 1 câu mỗi `service_type` (~30–80) | Mở popover | Một câu `luat_bac_si_bat_buoc WHERE service_type_id = ANY(...)` | 2 | P4 |
| L4 | `/appointments` (`/appointments/cho-trong-tuan`, `/luoi-ngay`; `booking.py:510,539`) | `services/capacity_service.py:641-652` `bang_tuan`, `:730-743` `luoi_ngay` | A | 126 câu `quote` nặng (18 bác sĩ × 7 ngày; `DANG-LAM.md` đo prod TB **22,56ms** mỗi câu), `gather` + Semaphore 6 → chiếm 6 kết nối pool | Mở màn, đổi tuần | `quote` nhận mảng bác sĩ (`unnest`) → 7 câu (mỗi ngày một câu). `DANG-LAM.md` đã chỉ hướng này, và bộ đối chiếu ô-với-ô có sẵn | 2 | P3 |
| L5 | `/reception/queue`, `/do-sinh-hieu` (GET `/lam-them/nut`, `lam_them_tai_quay.py:88`) | `services/lam_them_tai_quay_service.py:432-444` `_ket_qua_cac_don` → `lam_them_dong_dich_vu.py:92` | A | ~4 câu × chỉ định READY còn PENDING (0–vài), trong đó **2× `can_o_phong_nao_do` không nhớ** lặp mỗi vòng | Mở màn; tin bảng | Kiểm 2 quyền **một lần** ngoài vòng; `states_for_orders` một lần cho mọi id | 3 (cửa tiền `finance_gate`) | P4 |
| L6 | Khung khách (CSKH, `/customers`, `/ban-kham`…; GET `cskh.py:111`) | `services/ghi_chu_khach_service.py:290-320` `tom_tat` | A | `tinh_hoa_don` dịch vụ (~10) + kiểm phiếu thuốc (1) + hoá đơn thuốc (2) ≈ 13 câu × ≤5 lượt gần đây ≈ 65 | Mở khung khách | Dùng đọc gộp PR-J cho 5 lượt | 3 | P3 |
| L7 | `/ban-kham`, `/tu-van`, `/ban-kham/[phong]` | `ban-kham/BanKham.tsx:266-268→288→291` | D | `phong-hom-nay` xong mới tới (hang-cho + bang), kể cả khi không cần phòng (2 vòng) | Mở màn, mỗi tin | Không chờ `phongs` khi `phongMa` rỗng hoặc đang ở tư vấn | 2 | P3 |
| L8 | `/ban-kham` | `DoiPhong.tsx:103-105` (gắn trong vòng chỉ định, `BanKham.tsx:1639,1678`) | D | Mỗi `DoiPhong` đọc lại `phong-hom-nay` (`gopDoc` chỉ gộp lời gọi cách nhau ≤50ms); `goi-y-phong` gọi **N lần** cho N chỉ định | Mở một khách | Truyền `phongs` của cha xuống làm prop; gộp gợi ý phòng theo lượt | 2 | P3 |
| L9 | `/reception/queue` | `reception/queue/QueueBoard.tsx:113,177,187,206`; `:121` (`ban = gui \|\| dang`) | B | `startTransition(() => router.refresh())`: `isPending` giữ nút tới khi dựng lại cả trang (~7–9 lời gọi backend) | Check-in, chuyển trạng thái | Gọi `router.refresh()` ngoài transition, hoặc không gộp `dang` vào `ban` | 2 | P2 |
| L10 | `/do-sinh-hieu` | `do-sinh-hieu/BangDoSinhHieu.tsx:322→346` (`batDau`, gọi ở phím đầu tiên `:723`); `:353-423` (`luu` = ghi bắt đầu + **tải cả ngày** + ghi sinh hiệu + **tải cả ngày**); `:434-461` (`doiTuVan`) | B | 1–2 lượt `/api/luot-kham?ngay=` (cả ngày) nối đuôi mỗi thao tác | Mỗi lần đo | Vá trạng thái tại chỗ; tìm khách kế (`keTiep`) từ danh sách đang có (bỏ khách vừa lưu); tải lại không chờ | 2 | P2 |
| L11 | Mọi trang (layout) | `app/(dashboard)/layout.tsx:44→103-125`; `lib/clinic-session.ts:34-68` | D | `/me` → `/me/vi-tri-hom-nay` → Promise.all 4–6 lời gọi = 3 vòng; `phan-quyen/toi` và `reports/access` không phụ thuộc mà vẫn chờ | Mỗi lượt dựng trang (× C1/C2/C4) | Bắt đầu các lời gọi không phụ thuộc ngay đầu hàm → 2 vòng | 2 | P2 |
| L12 | `/settings` | `app/(dashboard)/settings/page.tsx:26→31` | D | `reportSettings` chạy trước một Promise.all riêng | Mở màn | Gộp vào một Promise.all | 2 | P4 |
| L13 | `/customers` | `customers/page.tsx:166→226; 296` | D | `recall-jobs` không phụ thuộc mà chỉ bắt đầu ở vòng 2 | Mở màn | Cho vào Promise.all ở `:166` | 2 | P4 |

### 2.7 Nút chờ tải lại (B) ở các màn còn lại — một dòng một chỗ

Cách sửa chung cho cả mục này:
- Nhả cờ bận và đóng hộp **ngay khi lệnh ghi trả OK**.
- Vá tại chỗ từ phản hồi nếu có (vd `NgoaiLeCaTruc` nhận lại nguyên dòng, `TuNhac` nhận `{id, nhac_luc}`).
- Gọi `void tai()` không chờ, và **tách lượt tải lại ra khỏi `try` của lệnh ghi**. Hiện `DayNoiBoard` `doc` `:86`, `TuNhac` `doc` `:45`, `QuyenTheoMan` `doc` `:38` báo "CHƯA lưu" khi lượt tải lỗi mạng dù lệnh đã ghi xong, làm người dùng dễ bấm lại.
- Mỗi dòng chỉ chờ 1 lượt tải.

| # | Màn (URL) | Tệp:dòng | Kiểu | Chờ gì | Mức | Ưu tiên |
|---|---|---|---|---|---|---|
| B1 | `/ban-kham`, `/ban-kham/[phong]`, `/tu-van`, `/patient-list` | `tasks/HoSoHoanTatPanel.tsx:126→151→154` | B | `await load()` | 2 | P2 |
| B2 | `/ban-kham`, `/customers`, `/nhac-tai-kham`, `/patient-list`, `/tu-van` | `CongTyKhach.tsx:42→51→53` (`luu`); `:55-61` (`an`: không cờ, không phản hồi tới khi tải xong) | B | `await tai()` | 2 | P3 |
| B3 | `/customers`, `/nhac-tai-kham` | `_lam-viec/KhungKhach.tsx:230→240→247` | B | `await docGhiChu()` | 2 | P3 |
| B4 | Khung khách (`/ban-kham`, `/customers`, `/thu-ngan/*`, `/pharmacy`, `/phong/[ma]`…) | `_lam-viec/TuNhac.tsx:61→71→78` | B | `await doc()`; phản hồi đã có `{ok, id, nhac_luc}` (`nhac_viec_service.py:86`) | 2 | P3 |
| B5 | `/hoa-don` | `hoa-don/CongTyHoaDon.tsx:66→77→80` | B | Hộp đã đóng nhưng nút khoá tới khi `tai()` xong | 2 | P3 |
| B6 | `/schedule` | `schedule/NgoaiLeCaTruc.tsx:65→82`, `:87→96` (`await tai()` trong `useTransition`) | B | Phản hồi đã trả nguyên dòng (`ngoai_le_ca_truc_service.py:100,132`) | 2 | P3 |
| B7 | `/doi-tac` | `doi-tac/BangDoiTac.tsx:222→234→235` | B | `await tai()` | 2 | P3 |
| B8 | `/cashier/dich-vu` (bảng giá) | `cashier/DanhMucDichVuPhong.tsx:139→153→160`; `VatTuThuocTinh.tsx:58`, `VatTuBangGia.tsx:127`, `ThemDichVu :616` | B/D | `await taiLai()` tải **cả danh mục**; `ban` khoá mọi ô. PATCH chỉ trả `{"ok": True}` (`config.py:576`) | 2 | P3 |
| B9 | `/settings/day-noi` | `settings/day-noi/DayNoiBoard.tsx:113→125→129` | B | `await tai()` | 2 | P4 |
| B10 | `/phan-quyen` | `phan-quyen/QuyenTheoMan.tsx:60→72→77` | B | `await doc()` | 2 | P4 |
| B11 | `/phan-quyen` | `phan-quyen/NhomQuyenMau.tsx:80→89→104` | B | Hộp chỉ đóng sau `napLai()` | 2 | P4 |
| B12 | `/ke-toan` | `ke-toan/ThueSuat.tsx:75→80/85` | B | Phản hồi đã có `{ok, nhom\|id, thue_suat}` (`thue_suat_service.py:140,173`) | 2 | P4 |
| B13 | `/settings/clinic-config` | `settings/clinic-config/CoSoPhong.tsx:144→148→149→150→154` | B | `await onDocLai()` rồi `taiNhanSu()` (kéo theo lich-phong + day-noi); hộp chỉ đóng sau đó | 2 | P4 |
| B14 | `/settings/don-du-lieu-thu` | `settings/don-du-lieu-thu/DonDuLieuThu.tsx:166→180→184` | B | `await taiNgay` | 2 | P4 |
| B15 | `/settings` | `settings/FeatureModeCard.tsx:43-54,76` | B | `router.refresh()` trong transition | 2 | P4 |

---

## 3. Chia đợt PR

Luật chung:
- Mỗi PR một nhánh, một worktree, một agent.
- PR không quá ~400 dòng, không tính test, migration và tệp sinh.
- PR có migration dùng dải giờ riêng (gợi ý `2026102xyy…` theo chữ cái PR), cổng web/API riêng 32xx/82xx.
- PR nào đổi router/service thì chạy lại `python3 scripts/ban-do-code.py`.
- Mức 3 = **kế hoạch ngắn cho Tuyền duyệt TRƯỚC** (viết trong thân PR draft), xong mới code.

### Đợt 1 — mức 1–2, làm song song ngay; cắt hệ số nhân (C) và việc không đụng tiền

| PR | Nhánh | Gồm | Ước dòng | Mức | Phụ thuộc |
|---|---|---|---|---|---|
| A | `toc-do-su-kien-thuc-ngay` | C1 (`su-kien` thức theo NOTIFY `event_log`) | ~80–120 | 2 | — |
| B | `toc-do-bang-theo-man` | C2 (bảng theo route; bỏ `phieu_kham_luot`, `consultation_note`, `luot_dong_thoi_gian` khỏi tập dựng trang), C4 (`DeclinedNotice` tự tải, `BANG_LAYOUT` chỉ còn `work_roster`), C5 (4 màn vào `MAN_TU_TAI`, bỏ refresh thừa ở checkout, LiveBoardSync) + sửa test boundary | ~250–350 | 2 | Trước khi bỏ một bảng khỏi route nào, kiểm SSR của route ấy không đọc bảng đó (mục 6) |
| C | `toc-do-hang-doi-sse` | C6 (tràn → tin `null`) + C7 (không chuyển tiếp `event_log`, `so_no`) | ~60 | 2 | — |
| D | `toc-do-hoi-du-phong` | C8 (nhịp dự phòng chỉ chạy khi SSE chết) | ~80 | 1–2 | Riêng nhịp 5s giữ chỗ: chờ Tuyền gật vì đổi một con số đã ghi ở `SO-LUAT` 6.4 |
| E | `toc-do-nut-nha-som-kham-le-tan` | L9, L10, K2, B1–B4 | ~250 | 2 | — |
| F | `toc-do-nut-nha-som-cai-dat` | B5–B15, W4, W6, W7 | ~300 | 2 | — |
| G | `toc-do-ssr-song-song` | L11, R4, L7, L8, L12, L13 | ~150 | 2 | — |
| H | `toc-do-doc-gop-khong-tien` | L1, L2, L3 | ~200 (+test) | 2 | — |

### Đợt 2 — mức 3, chờ Tuyền duyệt kế hoạch; lõi tiền của quầy thu

| PR | Nhánh | Gồm | Ước dòng | Mức | Phụ thuộc |
|---|---|---|---|---|---|
| I | `toc-do-ngay-truc-mot-cau` | C3 + Q12 (`days()` một câu, giữ nguyên nghĩa) | ~80 (+test) | 3 (quyền) | — Kế hoạch rất ngắn, duyệt nhanh được. **Làm sớm nhất trong đợt 2**, có thể gom chung đợt staging với đợt 1 |
| J | `toc-do-hoa-don-doc-gop` | Tách `bill_service`: `doc_nguon_hoa_don` (gộp N lượt, gồm cả thuốc với bảng giá đọc 1 lần) + `dung_hoa_don_con_no` / `dung_hoa_don_thuoc` thuần; `hoa_don_con_no` / `tinh_hoa_don` giữ chữ ký. **Chưa đổi nơi gọi nào** | ~300–400 (+test lớn) | 3 | — Nền của K, N, O, R |
| K | `toc-do-quay-thu-doc-gop` | Q1, Q2: board dùng PR-J, bỏ lần tính `_quay_thu` thứ hai | ~150 | 3 | J |
| L | `toc-do-phong-quay-chung` | Q3: `PhongQuay` dùng chung, khoá nhớ không có `visit_id`, cơ sở đọc gộp | ~150 | 3 | — (song song với J) |
| M | `toc-do-quay-thu-nut` | Q5–Q10: nút nhả sớm, nút Thu khoá theo `revision`, `mot-luot` | ~250 | 3 | — (song song với J; hiệu quả thấy rõ nhất khi K đã vào) |

### Đợt 3 — mức 3, sau khi đợt 2 qua staging

| PR | Nhánh | Gồm | Ước dòng | Mức | Phụ thuộc |
|---|---|---|---|---|---|
| N | `toc-do-checkout-doc-gop` | K1 (+ bản gộp `no_khi_ve`, `tien_thua_khi_ve`) | ~300 | 3 | J |
| O | `toc-do-so-no-doi-chieu` | N1 (chỉ xét lượt có sự kiện mới; đọc gộp) | ~150 | 3 | J (phần đọc gộp) |
| P | `toc-do-bao-cao-tien-thua` | R1, R2, R3 (+ migration chỉ mục nếu EXPLAIN cần) | ~250 | 3 | EXPLAIN trước |
| Q | `toc-do-kho-ton` | W1, W2, W3 (+ migration chỉ mục) | ~250 | 3 (kho) | EXPLAIN trước |
| R | `toc-do-gop-le-tien` | Q11, W5, L5, L6 | ~200 | 3 | J (cho L6) |
| S | `toc-do-cau-ung-vien-quay` | Q4 — **chỉ sau khi có EXPLAIN**; có thể kèm migration chỉ mục | ? | 3 | Đo trên staging local |

### Để sau, chỉ làm khi đo thấy đáng
- L4: gộp `quote` sức chứa (mức 2).
- C9: lọc `thong_bao` theo người nhận.
- C10: tin mang cơ sở (mức 3, migration trigger, sau C6).
- N2: gom consumer `so_no`.

### Thứ tự và nhịp lên staging
1. **Đợt staging 1:** A, B, C, D, E, F, G, H, cộng I nếu Tuyền duyệt kịp. Cắt dây chuyền trước: đây là hệ số nhân của mọi thứ còn lại, và không đụng tiền. Đo lại xong rồi mới quyết mức đầu tư cho đợt 2.
2. **Đợt staging 2:** J, K, L, M. Song song được: J, L, M (khác tệp; M chỉ đụng TSX). K phải chờ J.
3. **Đợt staging 3:** N, O, P, Q, R, S. N, O, R chờ J đã lên prod; P, Q, S chờ số EXPLAIN.

Đụng chung tệp, phải sửa tối thiểu:
- B và D cùng sửa `RealtimeRefresher.tsx`: làm B trước, D rebase sau.
- K và L cùng sửa `cashier_board_service.py`: hai vùng khác nhau (`:708-769` và `:742-752`), merge cẩn thận.
- I và Q12 cùng sửa `cashier_scope_service.py`: đã gom chung vào PR-I.

---

## 4. Test cần thêm và cách đo trước/sau (PR mức 2–3)

### 4.0 Công cụ đếm câu SQL trong test (thêm một lần, ở PR đầu tiên cần nó)

asyncpg đang dùng bản `0.30.0` (`pyproject.toml:16`), có `Connection.add_query_logger`. Đề xuất
thêm fixture `dem_sql` vào `src/tests/` (chưa có công cụ nào như vậy):
- Mỗi lần `pool.acquire()` thì gắn logger vào kết nối, đếm số câu.
- Trả về `(so_cau, danh_sach_cau)`.

Mẫu kiểm cho mọi PR kiểu A: **số câu không tăng theo N**. Chạy cùng endpoint với 5 lượt rồi
30 lượt, assert `dem(30) - dem(5) <= 2`. Bản trước khi sửa sẽ fail rõ ràng (khoảng +250 câu).
Ghi số trước/sau vào thân PR. Chạy bằng `scripts/test-nhanh.sh <tệp>`, không đo trên VPS.

Giao diện (kiểu B/C) đo bằng Playwright trên stack local, ở cỡ 375 và 1280:
- đếm số request `/api/cashier` (hoặc endpoint của màn) cho mỗi thao tác;
- đếm số request RSC (`?_rsc=`) ở **một tab thứ hai** đang mở màn thường sau một lần thu;
- đo thời gian từ lúc bấm tới lúc nút nhả.

| PR | Đo trước → mục tiêu sau |
|---|---|
| A | Số đợt NOTIFY mỗi lần thu: ~3 → 1–2. Đếm bằng cách nghe kênh `clinicai_changes` trong test, nhóm theo khoảng 600ms |
| B, C | RSC ở tab thứ hai: ~3 mỗi lần thu → ≤1; ~1 mỗi 1,5s khi có người gõ phiếu → 0 |
| I | `/phan-quyen/toi` với bác sĩ có 200 ngày trực: ~400 câu → ≤6 |
| K, L | `/cashier/board` 30 lượt: ~300–2.000 câu → ~25–35, và không tăng theo N |
| M | Bấm "Thu" → nút nhả: ≥2 lượt tải (~7s p95) → ngay khi lệnh ghi trả OK |
| N | `/reception/checkout` 50 lượt: ~1.000+ câu → hằng số |
| O | Một vòng đối chiếu: số lượt xét giảm về số lượt có sự kiện mới |

### 4.1 Test cho từng PR

**PR-A (`su-kien` thức theo NOTIFY):**
- Một sự kiện được giao trong < 1s mà không chờ nhịp nghỉ.
- Mất kết nối LISTEN thì vòng vẫn chạy bằng nhịp 1s (dự phòng).
- Thứ tự giao trong một consumer không đổi.
- Không giao trùng: thuê dòng (`thu_hoi_thue`) vẫn đúng khi hai lần thức chồng nhau.

**PR-B (bảng theo route):**
- Unit test `canDungLaiTrang`: mỗi route khai báo → đúng tập bảng; route chưa khai → 41 bảng; tin `null` → dựng lại.
- Test boundary mới: mỗi route trong `MAN_TU_TAI` có `useNgheBang` phủ đủ bảng mà màn ấy hiện.
- **Kịch bản người thật (hoàn tác vẫn cập nhật mọi màn):** thu ở quầy rồi hoàn tác → check-out, trưởng ca, sinh hiệu đổi trong ≤2s; bác sĩ gõ phiếu → `/home` không dựng lại; CSKH đặt lịch → quầy thu không dựng layout.

**PR-C (hàng đợi SSE):**
- Đẩy 9 tin vào hàng 8 chỗ → client nhận một tin không có `t` và màn hỏi lại hết.
- `event_log` và `so_no` không tới trình duyệt.
- Worker relay vẫn nhận `event_log`.

**PR-D (nhịp dự phòng):**
- SSE sống → không hỏi 60s.
- Ngắt SSE → nhịp dự phòng chạy lại.
- Tab ẩn → không hỏi.

**PR-E, PR-F (nút nhả sớm, không tiền):**
- Mỗi màn: lệnh ghi OK mà lượt tải lại lỗi mạng → **không** báo "CHƯA lưu".
- Lệnh ghi lỗi → nút nhả, báo lỗi, dữ liệu không đổi.
- Bấm thật 375/1280; bảng "nút/link đã đụng" trong PR.

**PR-H (đọc gộp, không tiền):**
- `chi_tiet_cac_viec` cho N việc == N lần `chi_tiet_viec`, so từng trường (dữ liệu gồm việc có/không hẹn, có/không chẩn đoán).
- `lich_su_cho_ho_so` với khách 0, 1, 25 lượt.
- Test `dem_sql` không tăng theo N.

**PR-I (`days()` một câu):**
- **Đối chiếu kết quả**: với cùng dữ liệu, bản mới == bản cũ trên các ca sau:
  - quản lý;
  - thu ngân dịch vụ / thuốc / cả hai;
  - người không có ca thu ngân;
  - ca hôm nay chưa tới giờ;
  - trưởng điều phối (`DIEU_PHOI`);
  - có `cursor`;
  - `limit` 1 và 30.
- Ngày rác (`cursor="abc"`) vẫn trả `SafetyGateError` như cũ (luật "nhận ngày từ người dùng").

**PR-J (đọc gộp hoá đơn — lõi tiền, test kỹ nhất):**
- **Hàm tham chiếu:** giữ bản cũ tạm thời trong test (`_hoa_don_con_no_cu`, chép nguyên) trong một chu kỳ phát hành.
- Với **mỗi kịch bản** dưới đây, assert cả ba điều:
  - `dung(doc([v]))` == bản cũ: so `cho_api()` đầy đủ **và `revision`**;
  - dựng gộp nhiều lượt lẫn lộn == dựng từng lượt (kiểm không rò dữ liệu giữa các lượt);
  - với `coi_nhu_chon`, kết quả == bản cũ gọi với cùng `coi_nhu_chon`.
- Kịch bản:
  1. Lượt chỉ có phí khám (tick dịch vụ khám); lượt Điều trị / Thủ thuật không tự cộng phí khám; lượt "đi thẳng phòng".
  2. **Thu một phần:** thu lần 1, bác sĩ chỉ định thêm → hoá đơn chỉ còn khoản mới.
  3. **Thêm hoặc bỏ dịch vụ sau khi thu:** bỏ chỉ định đã thu → rời hoá đơn và hiện ở tiền thừa; tick lại sau khi hoàn hết → thành nợ mới (luật `payment_bill_line_mot_lan_phu`).
  4. **Giảm giá** theo AMOUNT và PERCENT: `revision` **không đổi** vì giảm giá; liệu trình trả trước không bị giảm.
  5. **CK chờ xác minh:** dòng đang được một lần `PENDING_VERIFICATION` phủ thì không vào hoá đơn; huỷ lần chờ → dòng hiện lại.
  6. **Hoàn tiền:** hoàn một phần (vẫn phủ) và hoàn hết (hết phủ).
  7. Đối tác tự thu (`dong_doi_tac`, `doi_tac_da_thu`); phụ thu; vật tư theo chỉ định; liệu trình trả trước.
  8. Dữ liệu cũ: dòng khám gộp `exam-{visit}` (legacy), lượt `THU_CU_KHONG_TRUY_DUOC`.
  9. Chỉ định giá mâu thuẫn hoặc thiếu giá (`van_de`).
  10. Thuốc: dòng từ chối, `purchased_qty`, giá danh mục cùng giá bảng giá trùng tên, đơn đã gỡ (`removed_at`).
- **Hai người thao tác cùng lúc** (test có hai kết nối):
  - hai lệnh thu cùng `revision` → một PAID, một nhận lại đúng lần thu ấy (`Idempotency-Key`) hoặc `ConflictError`;
  - người A thêm chỉ định giữa lúc B đọc bảng và bấm thu → B nhận `BILL_CHANGED`.

  Hai test này đã có ở đường ghi; chạy lại để chứng minh PR-J không đổi gì ở đó.
- Bộ test cũ phải xanh nguyên: `test_quay_thu_mot_hoa_don_db.py`, `test_cashier_board*.py`, `test_tien_thua_*`, `test_so_no_hai_chieu_db.py`, `test_checkout_blockers.py`, `test_doi_chieu_hoa_don_db.py`, `test_rx_catalog_and_payment_simple_db.py`.

**PR-K (board dùng đọc gộp):**
- Toàn bộ test PR-J, cộng: JSON `/cashier/board` trước và sau giống hệt nhau trên một bộ dữ liệu 30 lượt trộn đủ kịch bản trên. So bằng snapshot, bỏ trường thời gian `cho_phut`.
- Các trường phải giữ: `ds_cho_thu` và thứ tự, `da_chot_0d`, `tick_lai`, `lam_truoc.nhom`, `quay_thu.revision`.
- `dem_sql` không tăng theo N.

**PR-L (`PhongQuay` dùng chung):**
- `phong_chon_duoc` bản mới == bản cũ cho:
  - nhiều lượt cùng node;
  - khách đang ở trong phòng (`tru_luot`);
  - phòng nhiều bác sĩ;
  - dịch vụ gắn phòng riêng;
  - phòng đối tác;
  - hai cơ sở.
- Thứ tự "vắng nhất lên đầu" giữ nguyên.

**PR-M (nút quầy thu):**
- Playwright:
  - thu tiền mặt → nút nhả ngay, câu "Đã thu…" hiện ngay, nút Thu của lượt ấy khoá tới khi `revision` mới về;
  - thu lại khi bảng chưa về → máy chủ trả `BILL_CHANGED` hoặc lần thu cũ, không tạo lần thu thứ hai;
  - mất mạng giữa chừng → báo đúng;
  - hoàn tác lần thu ngay sau đó vẫn chạy.
- Hai tab quầy: tab B thấy lượt rời "chờ thu" trong ≤2s.

**PR-N (check-out gộp):**
- `no_khi_ve`, `tien_thua_khi_ve`, `con_no_*`, `chan` bản gộp == từng lượt, trên các ca:
  - nợ khi về có / không ghi nợ phủ;
  - tiền thừa có / không "giữ lại";
  - CK chờ xác minh;
  - lượt chỉ đối tác thu;
  - lượt có thuốc chưa thu.
- Đóng lượt bị chặn đúng như cũ.

**PR-O (đối chiếu sổ nợ):**
- Lượt không có sự kiện mới không bị ghi dòng `DOI_CHIEU`.
- Hoàn tiền xong hoặc thất bại (không phát sự kiện số dư) vẫn được bắt trong 48h.
- Số dư cuối của mọi lượt sau N vòng == bản cũ trên cùng dữ liệu.

**PR-P (báo cáo tiền thừa):**
- `_thua` bản mới == bản cũ trên dữ liệu có lượt cũ hơn 30 ngày.
- Kiểm ở biên ngày giờ VN.
- Cơ sở đã ngừng vẫn ẩn / hiện đúng `sql_loc_ton`.

**PR-Q (kho):**
- `ton_kho` mới == cũ cho từng `(lô, kha_dung, tong_kha_dung)`, trên các ca: thuốc 1 lô, thuốc 5 lô, lô hết, dòng giao chưa gán lô, hai cơ sở.
- `lich_su_giao` cùng 200 dòng, cùng thứ tự.

**PR-R:** mỗi hàm gộp == từng phần tử. `hoan_cua_cac_lan_thu` gồm lần thu đã huỷ phiếu và lần hoàn một phần.

**PR-S:** chỉ viết sau khi có EXPLAIN. Bắt buộc có: tập `visits` của `_SQL` trước và sau giống hệt nhau trên bản sao prod (staging local).

---

## 5. Đã kiểm và ổn (độ phủ)

Mỗi dòng là một chỗ đã đọc và thấy gộp truy vấn đúng, hoặc có N nhỏ và cố định.

**Quầy thu và tiền**
- `cashier_board_service.board` phần phụ: `doc_chot_0d`, `doc_no_dang_mo`, `cho_khach_quyet` (câu chính), `da_tra_cho_vao_phong`, `tien_thua_cua_luot`, `da_bo_cua_cac_luot`, `cong_ty_cua_khach`, `trang_thai_lam_truoc`, `dich_vu_lam_truoc`, `anh_cua_cac_lan_thu` — đều nhận mảng `visit_ids`.
- `cashier_board_service._SQL`: một câu, một vòng mạng cho sáu tập dữ liệu (chậm là ở bên trong câu, xem Q4).
- `cashier_board_service.giao_dich`: `trang_thai_doi`, `anh_cua_cac_lan_thu`, phần khoản hoàn gom đúng (chỉ `_con_hoan` lặp, xem Q11).
- `payment_service`: lệnh thu tính lại hoá đơn **một lượt** trong giao dịch có `FOR UPDATE`, so `revision`, có `Idempotency-Key`. Đúng thiết kế, giữ nguyên.
- `checkout_service.pending_list`: câu chính `_READINESS_SQL` đã là một câu cho cả danh sách (chỉ phần gắn hoá đơn bị N+1).
- `quay_thu.lich_su` (nhánh giao diện, không `chi_tiet`): khách, dòng, đổi hình thức, ảnh, hoàn đều gom `ANY`. `phieu()` ~7 câu cố định.
- `tien_thua.dong_tien_thua`: một CTE đi từ chỉ mục lượt (đã tối ưu 14/10).
- `danh_sach_hoa_don_service.xem` và `_viec_ton` (`/hoa-don`): mọi câu phụ gom `ANY`.
- `hoa_don_projection`, `xuat_hoa_don.doc_goc`: gom.
- `lieu_trinh_service.theo_luot`/`chip`/`cskh`, `lieu_trinh_tien._so_lieu`/`quay`, `lam_truoc_thu_sau`: gom.
- `cong_no_service` đọc nợ nhiều lượt (`ANY`).
- `bao_cao_cuoi_ngay.bao_cao`: ~15–17 câu cố định; `con_no` đọc một lần rồi dùng lại ở `doc_viec_tien`.
- `bao_cao_thuoc_service.doc_thuoc_theo_khach`: 4 câu gom.

**Kho và vật tư**
- `vat_tu_kho.doc_ton`, `vat_tu_nhap_duyet.doc_cho_duyet`, `phan_lo.can_theo_hoa_don`: gom.

**Trang chủ, báo cáo, điều phối**
- `man_trang_chu_service.goi_du_lieu`: ~15 câu cố định; `doc_hanh_trinh_khach` gom theo mảng lượt.
- `reports_service` (`tong_quan`, `toan_canh`, `kpi`, `booking_channels`): 2–5 câu cố định, đếm bằng FILTER.
- `week_appointments_service.week`: CTE `caps` MATERIALIZED, mỗi cặp (bác sĩ, giờ) gọi `resolve_effective_cap` một lần.
- `visit_progress_service.for_range`, `bang_hanh_trinh_service.hom_nay`, `hanh_trinh_khach_service.doc_hanh_trinh_khach`: set-based hoặc gom `ANY`.
- `nhan_luot.doc_nhan_luot`, `nhan_tai_phong.*`, `service_routing.cho_nhan_vao_phong`/`doi_tac_lam_tron`: mỗi hàm một câu gom.
- `xem_luot_service.doc`: ~20 câu cố định mỗi lượt.
- `luot_kham_doc` (cả tệp), `booking_service`, `dispatch_service`, `display_board_service`, `doctor_board_service`, `danh_sach_benh_nhan_service`, `cskh_service`, `lich_hen_doc`, `hang_cho`, `ho_so_khach_doc`: không có `await` trong vòng.
- `ops_status`, `traffic_service`: không đụng DB (chỉ đọc tệp hoặc `SELECT 1`).

**Vòng có N nhỏ, chấp nhận được**
- `can()` qua 2–4 mã quyền (câu "có" được nhớ 5 giây).
- `bac_si_ky`, `bac_si_phu_trach`: tối đa 2 vòng.
- `form_engine_service`: 1–3 phiếu mỗi chỉ định.
- Việc nền mỗi cơ sở / mỗi clinic: `canh_gac`, `agent_giam_sat`.

**Thời gian thực**
- Mỗi tab chỉ có một EventSource; tab ẩn đóng dòng, không dựng trang, không gọi `useNgheBang`.
- Có gộp nhịp 250/600ms + lệch 0–400ms; `useNgheBang` có "một lượt một lúc".
- Máy chủ SSE không đọc DB cho mỗi tin; một kết nối LISTEN mỗi tiến trình API.
- Postgres tự gộp NOTIFY giống nhau trong một giao dịch, nên số dòng ghi không nhân số tin.
- Trigger có lọc theo cột hoặc WHEN: `form_instance` (lượt tự lưu không báo), `tep_ket_qua`, `anh_chuyen_khoan`.
- `canh_bao`, `loi_nhom`, `luot_ghi_chu`, nhịp sống worker không có trigger.

**Giao diện làm đúng (mẫu để theo)**
- `ChonDichVuKham`: đổi ô tick lạc quan, áp `kq.data`, chỉ tải lại khi lỗi.
- `NhanSuBoard`, `RosterRegisterTable`, `PhieuKhamLuot.dat`/`doiBatBuoc`, `ClinicConfigBoard`, `NotificationContext.danhDauDaXuLy`: vá tại chỗ hoặc tải lại không chờ.
- `PhieuKham`: nhận tham chiếu từ cha, không đọc lần hai.
- Nhả cờ bận trước khi tải lại: `BanLeThu.gui`, `CheckoutBoard`, `ChinhDonQuay` (nút), `LichSuDonThuoc`, `HoaDonMot`, `AnhChuyenKhoan`, `HoanTien`, `NutHoanTac`, `LieuTrinhKhach`.
- Trang SSR đã song song: `/home`, `/schedule`, `/appointments`, `/patients/new`, `/pharmacy/inventory`, `/kho-vat-tu`, `/nhan-su`, `truong-ca/load.ts`.

---

## 6. Chưa chắc / cần đo thật

Các mục dưới đây **chưa** được coi là đã chắc trong bảng chính. Đo trên **staging local**
(`scripts/staging-tu-ban-sao.sh`, bản sao prod) hoặc trong test; không đo trên VPS.

1. **Q4 — vì sao `WITH v AS` mất 4,3s.** Chạy `EXPLAIN (ANALYZE, BUFFERS)` với tham số thật
   (hôm nay, có / không cơ sở). Đếm số lượt chưa về cũ hơn hôm nay (`closed_at IS NULL AND
   status NOT IN ('FINALIZED','AMENDED','INCOMPLETE')`). Xem 4,3s là chi phí của chính câu
   hay do chờ khi DB bị tải dây chuyền đè: chạy riêng lúc vắng để so.
2. **Nguồn chính xác của `WITH dong AS` 67.381 lần.** Khả năng cao là `_THUOC_PHAI_TRA_SQL` /
   `tien_da_thu_cua_chi_dinh` trong vòng đối chiếu N1. Ứng viên khác cùng mở đầu `WITH dong
   AS`: `vat_tu_tieu_hao_service.py:38`, `events/consumers/so_no.py:43`, hàm SQL trong
   migration `20261006200000` / `20260929950000` / `20261003720000`. Xác nhận bằng
   `queryid` + nội dung đầy đủ trong `pg_stat_statements` (Tuyền đọc, AI không chạm VPS).
3. **Số ngày trực thật của mỗi người** (C3) và số lần `/phan-quyen/toi` được gọi mỗi phút
   lúc cao điểm.
4. **Số đợt NOTIFY và khoảng cách thật** cho một lần thu (C1): log thời điểm `pg_notify`
   theo bảng ở broker.
5. **Trước khi bỏ bảng khỏi route (PR-B):** kiểm `/luot-kham/phong-hom-nay`, gói trang chủ và
   `/reception/danh-sach` có đọc `phieu_kham_luot` / `luot_dong_thoi_gian` /
   `consultation_note` không (grep chưa thấy, nhưng `luot_kham_service.py` rất lớn).
6. **`consultation_note` không có người nghe trên màn bàn khám.** Bác sĩ chính có thể không
   thấy ghi chú tư vấn mới tới khi tải lại — có thể là một lỗ cập nhật sẵn có, không phải tốc
   độ. Cần Tuyền xác nhận nghiệp vụ.
7. **Chi phí GoTrue `getUser`:** 2 lần mỗi `router.refresh` (`proxy.ts:90` +
   `backend-proxy.ts:48-59`) và 2 lần mỗi lời gọi `/api/*` (54/61 route). Nếu đáng kể thì nó
   là một hệ số nhân riêng.
8. **Tần suất `thong_bao`** mỗi phút lúc cao điểm (C9); tần suất các việc hẹn giờ ghi
   `work_item` / `staff_task`.
9. **Hàng đợi SSE 8 tin có thật sự đầy không** (C6): thêm bộ đếm tin bị bỏ (đã nằm trong PR-C).
10. **Kích thước và thời gian câu** của `so_no` (`_SO_DU_TOI_SQL`, `_SO_DU_MO_SQL`,
    `_CAN_XET_SQL`), `ton_kho` (số lô trên mỗi thuốc), `lich_su_giao` (số dòng đã giao).
11. **Ép kiểu làm mất chỉ mục:** `bl.source_id = so.id::text` (chỉ mục
    `idx_payment_bill_line_nguon` là `(clinic_id, source_type, source_id)`, nên phía
    `so.id::text` không cản chỉ mục, nhưng cần xem kế hoạch); `giu_lai_dang_co`
    (`g.visit_id::text = ANY`), `_HOAN_TIEN_THUA_SQL` (`bl.visit_id::text = ANY`).
12. **Hàm SQL theo dòng có được Postgres gộp vào câu ngoài không:** `co_so_cua_luot`,
    `phong_lam_duoc`, `phan_thu_hieu_luc`, `hinh_thuc_hieu_luc`, `drug_batch_kha_dung`. Kiểm
    bằng `EXPLAIN VERBOSE`; nhiều khả năng là không, vì chúng có FROM hoặc subquery.
13. **`work_item_gate_blockers`** theo từng dòng việc (`work_item_service.py:389-391,
    538-540`) và `resolve_effective_cap` theo từng lịch ở `tiep_don_service.py:254`: chưa đọc
    đủ để kết luận N.
14. **Thời gian hiện tại của `/appointments/cho-trong-tuan`** sau lần tối ưu `boi_canh_tuan`
    (L4) — đo trước khi viết lại `quote`.
15. **Số lượt gọi khi mở một khách ở `/ban-kham`:** mới ước 10–20 từ danh sách component tự
    tải, chưa đếm cây render thật.
16. **`recall-jobs` và `/api/v1/staff`** trả cả danh sách: chưa kiểm có trần kích thước không.
17. **`/lam-them/nut`** được tải lại theo SSE hay chỉ khi mở màn (L5).

---

## Việc Tuyền quyết

| Quyết định | Vì sao cần Tuyền |
|---|---|
| Duyệt kế hoạch PR-I (`days()` một câu, giữ nguyên nghĩa) | Mức 3 (quyền). Ảnh hưởng lớn và nhỏ gọn — nên duyệt đầu tiên |
| Có thêm mốc dưới cho lịch sử ca khi tính quyền không (vd 400 ngày) | Nghiệp vụ: người từng là thu ngân lâu rồi còn thấy "lịch sử thu" không |
| Duyệt thiết kế PR-J (mục 2.2 Q1, mục 4.1 PR-J) | Lõi tiền |
| PR-M: nút "Thu" của **đúng lượt vừa thu** khoá tới khi hoá đơn mới về, các nút khác nhả ngay | UX quầy thu |
| Nhịp 5s ở màn giữ chỗ (C8) | Con số đã ghi ở `SO-LUAT` 6.4 |
| `consultation_note` có cần hiện tức thời trên bàn khám không (mục 6.6) | Nghiệp vụ |
| Chạy `EXPLAIN (ANALYZE, BUFFERS)` cho Q4, R1, R3, W1, W2 trên staging local; đọc `pg_stat_statements` (`queryid` của `WITH dong AS`) | Tuyền chạy lệnh trên máy có dữ liệu. AI soạn sẵn câu khi bắt đầu PR-S/P/Q |
