# KẾ HOẠCH — Hiện SĐT cạnh tên khách · Chuẩn hoá số điện thoại

> 17/10/2026 · MỨC 3 (đụng migration + nhiều màn) → **chờ Tuyền/Quang duyệt trước khi code.**
> Chưa có dòng code nào. Số liệu đo từ **bản sao lưu prod 17/10 02:15 trên Mac** (đọc cục bộ,
> không chạm VPS/staging/prod, không in số hay tên thật). Bảng kiểm kê chi tiết từng dòng:
> `docs/kiem-ke-sdt-1710/` (4 bảng A–D).

## 0. Tóm tắt một màn hình

| | Phát hiện | Nghĩa là gì |
|---|---|---|
| Trùng tên | **1.126 tên** có ≥2 hồ sơ; **4.249 / 8.787 hồ sơ (48%)** nằm trong nhóm trùng tên | Nhóm trùng tên lớn nhất có 9 hồ sơ; 191 tên có đúng 3 hồ sơ. Mã kiểu `KHACH-4821` (4.548 hồ sơ nhập Notion) không có nghĩa gì để nhìn phân biệt. |
| SĐT phân biệt được không | Trong 1.126 nhóm trùng tên, **1.066 nhóm** SĐT phân biệt hết; 23 nhóm có người **không có số**; chỉ **12 nhóm** hai hồ sơ cùng một số (nghi trùng người thật) | Hiện SĐT giải quyết gần hết. 4 số cuối đụng nhau ở 16 nhóm → nên hiện **cả số**, không chỉ 4 số cuối. |
| Dữ liệu SĐT cũ | **8.432 / 8.787 đã đúng dạng `0xxxxxxxxx`**; 306 trống; 1 viết khác dạng; **48 sai (đều từ nhập Notion, mã `KHACH-…`)**; **0 số nước ngoài, 0 số có `+`/dấu cách/dấu chấm** trong cột SĐT — vì ô nhập đang **chặn** số nước ngoài, nhân viên phải ghi số ấy vào ghi chú (Tuyền/Quang 17/10; đếm được ≥1 trong sổ ghi chú, còn lại nằm ở chỗ khác chưa quét) | Ô nhập **chặn khá chặt** nên dữ liệu sạch, nhưng **thiếu một đường cho số nước ngoài** (đã chốt: sẽ nhận). Vấn đề thật là *5 bản chuẩn hoá lệch nhau* + vài ô nhập thủng + tìm kiếm không hiểu `+84`. **Không cần chuyển đổi hàng loạt.** |
| Chỗ hiện tên | xem §1 | Phần lớn API **đã trả `phone_primary`** vì đã JOIN `patient` → hiện SĐT gần như miễn phí về tải. |

## 1. Việc 1 — Hiện SĐT cạnh tên ở mọi chỗ hiện tên

### 1.1 Kiểm kê: ≈110 chỗ, nhưng chỉ ≈20 "điểm sửa"

Bốn bảng chi tiết từng dòng (màn → `file:dòng` → API → service → đã có SĐT chưa → cần sửa gì → rủi ro) nằm ở
`docs/kiem-ke-sdt-1710/` — **A** tiếp đón/khách · **B** lâm sàng/việc/chuông · **C** tiền/thuốc/hoá đơn/in/đối tác ·
**D** backend (chuỗi ghép sẵn, sự kiện, nhật ký, tin nhắn, file xuất). Số chỗ là xấp xỉ, đếm từ 4 bảng (chưa chạy EXPLAIN, chưa bấm 375px — agent chỉ đọc).

| Tình trạng SĐT hiện nay | ≈Số chỗ | Việc cần làm |
|---|---|---|
| **Đã hiện**, nhưng ở dòng phụ chữ nhỏ (có chỗ SĐT *thay* mã BN → mất mã) | 25 | chỉ chuyển sang dạng chung `<TenKhach>` (mẫu đúng: `HangChoView.tsx`, `PharmacyBoard` chi tiết) |
| **API đã trả `phone_primary`, màn chưa vẽ** | 15 | **chỉ sửa TSX**, rẻ nhất |
| **API chưa trả**, truy vấn ĐÃ `JOIN patient` | 45 | thêm 1 cột `p.phone_primary` vào SELECT + 1 khoá `sdt` trong dict + TSX |
| **Chuỗi do máy chủ ghép sẵn** (chuông, nhật ký thao tác, cảnh báo) | 15 | sửa ở nơi ghép — xem §1.5 |
| **CẤM thêm** (cố ý, có test canh) | 4 | TV phòng chờ, Telegram, file MISA, payload sự kiện — xem §1.4 |
| **Cần chủ quyết** | 5 | cổng đối tác, cảnh báo trùng khi tạo khách, phiếu in khách cầm, file kế toán, chuông |
| Mã chết / không hiện tên khách | ~15 | bỏ qua (`sieu-am/*`, `lich_cho_check_in`, `alerts` điều phối, `ThuocTheoKhach.tsx`…) |

**Các CỤM — sửa một chỗ phủ nhiều màn** (đây là đơn vị làm việc thật):

| Cụm | Sửa ở đâu | Phủ những màn nào |
|---|---|---|
| **K1 hàng chờ lâm sàng** | `luot_kham_doc.py` `hang_cho` (SQL :883, dict :1140; "sắp tới" :1038/:1223) + kiểu `DongHangCho` (`_lam-viec/api.ts:22`) | Bàn khám · Bàn tư vấn · Phòng dịch vụ (3 kiểu vẽ hàng chờ: `BanKham.Nhom`, `HangChoCot`, `HangChoKhachPhong`) · đầu khung khách `PhongDichVu:719` |
| **K2 bảng làm việc** | `luot_kham_doc.py` `bang` (:101/:356) | Đo sinh hiệu (`BangDoSinhHieu`) |
| **K3 popup Xem lượt** | `xem_luot_service.py` (:244/:283) → `XemLuot.tsx` | **11+ màn** cùng mở popup này |
| **K4 phòng** | `nhan_tai_phong.py` `_KHACH_HOM_NAY_SQL` (:383/:539), `service_routing_service.cho_nhan_vao_phong` | "Sắp đến phòng", "Đã trả tiền — chưa xếp phòng" |
| **K5 điều phối ca** | `dispatch_service.py` `_OVERVIEW_SQL` (:122) / `_overview_row` (:962) | `/truong-ca` (3 khối) |
| **K6 check-out** | `checkout_service.py` `_READINESS_SQL` (:73) — 1 SQL dùng cho 4 hàm | 3 màn check-out (danh sách, chi tiết, tồn đọng) |
| **K7 sổ thu & phiếu** | `quay_thu_service.py` `_KHACH_SQL` (:886) | Lịch sử thu · CSV/XLSX lịch sử thu · **phiếu thu/hoàn in** · phiếu hướng dẫn phòng · hoá đơn thuốc in |
| **K8 hoá đơn "việc còn tồn"** | `danh_sach_hoa_don_service.py` :138/:150/:164 + nhóm nợ | `/hoa-don` tab tồn (quên 1 nhóm = nhóm đó thiếu SĐT → test đếm) |
| **K9 trang chủ/hành trình/hàng chờ lễ tân** | `man_trang_chu_service.py` :359/:555 · `bang_hanh_trinh_service.py` :151/:313 · `routers/queue.py` `_APPT_SQL` :37 | Bảng "Trạng thái BN" · `/hanh-trinh` · `/queue` |
| **K10 thuốc/siêu âm/lẻ** | `pharmacy_service.hang_doi/cho_gan_lo` · `ultrasound_board_service` ×2 · `ban_le_service.doc` · `visit_progress` ×2 · `cho_quyet` · `doi_lich_nhanh` · `tep_ket_qua_service` ×2 · `doi_tac_service` | các màn nhỏ còn lại |
| **K11 cảnh báo trùng khi tạo khách** | `api/v1/patients.py:164-205` + `patient_service.create_patient` + `NewPatientForm.tsx` (3 khối A8–A10) | **chỗ "trùng tên" cắn nhất** — hiện CỐ Ý không trả SĐT (`schemas/patient.py` "MINIMAL") |
| **K12 chỉ-TSX** | `QueueBoard` · `WeeklyAppointmentsTable` (1 sửa = 2 màn: Trang chủ + Tiếp đón) · `CustomersView` · `ThaoTacLichTaiCho.DauLich` (1 sửa = 3 popover) · `QuayThuNgan` (4 chỗ) · `PharmacyBoard` · `ConsultBoard` · `DanhSachHoaDon` (thẻ mobile) · `lich-do-ve` · `BangViecCanXuLy` | payload đã có |
| **K13 hộp xoá khách thật** | `settings/don-du-lieu-thu` hộp xác nhận XOÁ :352 (chỉ tên+mã, dễ nhầm khi trùng tên) | dùng `che_sdt` + 1 truy vấn theo ID, không migration — **ưu tiên cao** |

### 1.2 Thiết kế: MỘT thành phần, MỘT khoá dữ liệu

Hiện **không có** thành phần "tên khách": mỗi màn tự ghép `{ten} {ma}` (≥25 chỗ ghép chuỗi ngay trong TSX, `QuayThuNgan` rải 8 chỗ); backend đặt khoá SĐT 5 kiểu (`phone_primary`, `phone`, `sdt`, `so_dien_thoai`, `dien_thoai`) và ghép `f"{full_name} ({patient_code})"` ≥10 chỗ.

```
Giao diện:  components/ui/TenKhach.tsx
            <TenKhach ten ma sdt che="day_du|che|an" bo="ngang|doc" soLuot? />
            lib/sdt.ts:  dinhDangSdt("0912345678") → "0912 345 678"   (rút từ TheKhach.sdtDoc)
Backend:    key trong payload LUÔN là `sdt` (danh sách phẳng) hoặc `patient.phone_primary` (đã lồng)
            services/ten_khach.py:  ten_kem_ma(full_name, ma, sdt, *, kem_sdt=True)   ← cho chuông/nhật ký
            core/phone.py:  che_sdt()  (chuyển từ don_du_lieu_thu_service) + dinh_dang_hien_thi()
```

**Ba kiểu hiện — chọn theo NƠI, không theo vai:**

| Kiểu | Ví dụ | Dùng ở đâu |
|---|---|---|
| `day_du` (mặc định) | Nguyễn Thị Hoa · `0912 345 678` | mọi màn nhân viên (quầy, bác sĩ, điều dưỡng, CSKH, thu ngân, nhà thuốc) |
| `che` | Nguyễn Thị Hoa · `0912 ••• 678` | **tờ khách cầm** (phiếu thu/hoàn/hướng dẫn 80mm), hộp xoá khách thật, (nếu chủ cho) cổng đối tác |
| `an` | Nguyễn Thị Hoa | TV phòng chờ, Telegram, nơi người ngoài đọc |

*Vì sao hiện CẢ SỐ chứ không chỉ 4 số cuối:* đo trên 1.126 nhóm trùng tên — 4 số cuối **đụng nhau ở 16 nhóm**, 3 số cuối ở 32 nhóm; cả số chỉ còn 12 nhóm (cùng một số thật = nghi trùng người, lại là thông tin có ích). Nhân viên vốn thấy cả số ở `/patient-list`, `/customers` — che ở màn nội bộ chỉ thêm một cú bấm mà không an toàn hơn.
*Che do máy chủ quyết:* nơi cần che (phiếu in, đối tác) API trả **sẵn `sdt_che`**, không trả số đủ rồi để TSX che — tránh "luật trong TSX" và tránh số đủ nằm trong payload.

**Bố cục (đã đọc từ code, chưa bấm):** ≥768px — tên (đậm, `truncate`) rồi SĐT cùng dòng (`tabular-nums`, `shrink-0`, mã BN **giữ lại**, không để SĐT thay mã như `WeeklyAppointmentsTable:934`). 375px — tên một dòng, dòng dưới `mã · SĐT`. Cột hẹp nhất cần bấm kiểm: `/customers` khi mở chi tiết (~220px), cột trái Phòng dịch vụ, `/truong-ca`.

**Số nào cạnh tên:** `phone_primary`; trống thì **ẩn dòng** (không in "Chưa có SĐT" ở danh sách dày). Đo prod: 306/8.787 hồ sơ trống số; chỉ **1** số trong `patient_sdt_them` toàn hệ thống → không cần JOIN `patient_sdt_them` cho danh sách (đừng in `sdt_tim_kiem` — đó là chuỗi gộp để tìm). Số lưu sai dạng (48 hồ sơ) hiện nguyên văn.

**Khoá chống thụt lùi (Luật 12.2 — bài kiểm phải ĐẾM):**
- `src/dashboard/tests/ten-khach-boundary.test.mts`: đếm số chỗ vẽ tên bệnh nhân thẳng (`{x.full_name}`, `{d.ten}`…) ngoài `<TenKhach>` — **con số chỉ được giảm**, cùng tinh thần "route Next chạm DB: 1".
- `src/tests/unit/test_ten_khach_drift.py`: đếm `f"{…full_name…} ({…patient_code…})"` ngoài `ten_kem_ma`; đếm khoá SĐT lạ.
- Test canh sẵn **giữ nguyên, không nới**: `test_display_board.py` (TV), `test_notification_templates.py:82` (Telegram), `nhieu-so-dien-thoai-boundary.test.mts:43` (đừng đổi biểu thức lọc `sdt_tim_kiem ?? phone_primary`).

### 1.3 Tải và hiệu năng (prod ~14 req/giây)

- **Mọi** truy vấn trong 4 bảng đều **đã `JOIN patient`** để lấy tên → thêm `p.phone_primary` là thêm một cột trên dòng đã đọc: **không thêm JOIN, không N+1, không truy vấn mới**. Chi phí thật là vài byte/dòng trong JSON (`hang_cho`, `bang`, `giao_dich` LIMIT 1.000 là lớn nhất; một khách nhiều chỉ định thì SĐT lặp theo dòng — chấp nhận, hoặc FE lấy từ dòng đầu như `HangChoKhachPhong` đã làm).
- Hai ngoại lệ cần **một truy vấn nhỏ theo ID** (không migration): nhật ký thao tác `audit_log_service.subject_label` (view `v_audit_log` không có SĐT) và hộp xoá `don-du-lieu-thu` (K13).
- **Cách kiểm trong PR (không đoán):** (1) test đếm số truy vấn mỗi endpoint không đổi; (2) `EXPLAIN (ANALYZE, BUFFERS)` `hang_cho`, `bang`, `_READINESS_SQL`, `_KHACH_SQL` trước/sau trên DB local nạp bản sao (`staging-tu-ban-sao.sh`, cấm mở đường hầm); chấp nhận thời gian ≤ +5%; (3) `hang_cho` là truy vấn nặng nhất + nạp lại theo SSE → đo riêng.
- SSE/`notify_row_change` chỉ gửi tên bảng + clinic → **không đổi**. `event_log.payload` chỉ chứa ID → **không đổi**.

### 1.4 Quyền xem SĐT — và chỗ CẤM tuyệt đối

Hiện **chưa có** cơ chế ẩn SĐT theo vai/lego, và từ 30/09 mọi nhân sự nội bộ có 19/21 lego (trừ Cài đặt, Nhân sự&phân quyền) — nên **không đề xuất thêm quyền riêng "xem SĐT"** (sẽ đảo quyết định 30/09; làm sau nếu Quang muốn, mức 3). Cửa hẹp sẵn có tự áp: thư ký bác sĩ chỉ thấy khách của bác sĩ mình; SĐT đi cùng payload nên đi cùng cửa đó.
Quyền được quyết **theo nơi hiển thị** (bảng ba kiểu ở §1.2). Tuyệt đối KHÔNG:

| Nơi | Vì sao | Canh bằng |
|---|---|---|
| TV phòng chờ `/display`, `/dispatch/tv` | màn công cộng; phòng khám phụ khoa/hiếm muộn — "không một định danh nào khác ngoài tên" | `test_display_board.py` (cấm `phone_primary`) |
| Tin Telegram (nhóm vận hành) | bên thứ ba | `test_notification_templates.py:82` |
| File MISA/GTGT | mẫu 17 cột cố định, test ghim; hoá đơn công ty cố ý không SĐT (Tuyền 16/10) | `test_xuat_hoa_don.py:17` |
| `event_log.payload`, URL, tên tệp PDF, log | sống lâu hơn mọi màn; nay chỉ ghi 4 số cuối | thêm `sdt`, `so_dien_thoai`, `dien_thoai` vào `core/logging._SENSITIVE_KEYS` |

### 1.5 Chỗ đặc biệt (không phải "thêm một cột")

| Chỗ | Vấn đề | Phương án |
|---|---|---|
| **Chuông** (`thong_bao`, ~11 nơi ghép) | tên khách bị **ghi cứng** vào `tieu_de/noi_dung`; bảng không có `clinic_patient_id`; thông báo cũ không đổi; SĐT sẽ nằm trong DB | **P1** (đề xuất, mức 2): chỉ 5 loại chuông mà việc là "gọi khách" (nhắc tái khám, lộ trình sắp hết, kết quả về, lịch có bác sĩ, lịch mất bác sĩ) nhét SĐT qua `ten_kem_ma`; các chuông khác để nguyên. **P2** (mức 3): thêm `thong_bao.clinic_patient_id` + JOIN lúc đọc. |
| **Nhật ký thao tác** `/audit-log` | `subject_label()` ghép "Tên (Mã)" ở backend; view không có SĐT | chọn thêm `subject_patient_id`, 1 truy vấn theo ID cho trang, ghép tiếp — không migration; cẩn thận ô tìm `AuditLogBoard.tsx:143` |
| **Lịch sử điều phối** `/truong-ca/lich-su` | đọc view `v_dispatch_history` | **bỏ qua** (không cần SĐT ở nhật ký) |
| **File xuất** (Excel/CSV gửi kế toán) | PII rời hệ thống; test ghim vị trí cột | nếu làm: thêm cột "Điện thoại" **ở CUỐI** (Lịch sử thu, các sheet hoá đơn còn thiếu); báo cáo cuối ngày để sau (nhiều SQL, giá trị thấp) |
| **Tên tệp PDF** `ho-so-kham_<tên>_<ngày>.pdf` | — | **không** đưa SĐT vào tên tệp |
| **Ô tìm** ở màn lọc phía trình duyệt | `khopTimKhach`, `BanKham:338`, `QuayThuNgan` chưa tìm theo SĐT | tuỳ chọn, gộp ở PR S2 (tìm) |

### 1.6 PR — Việc 1 (<400 dòng mỗi PR, không tính test)

| PR | Nội dung | Mức | ~Giờ |
|---|---|---|---|
| **H0 nền** | `TenKhach.tsx` + `lib/sdt.ts` + `ten_khach.py` + chuyển `che_sdt` + 2 bài kiểm đếm + trang mẫu trong `/design-system` | 2 | 3 |
| **H1 chỉ-TSX** | K12 (10 file, payload sẵn) — **cho thấy giá trị sớm nhất, không đụng backend** | 2 | 4 |
| **H5 trùng tên khi tạo khách** | K11 + K13 (sau khi chốt H-Q3) | 2 | 2 |
| **H2a** | K1 (hàng chờ lâm sàng) + `DongHangCho` | 2 | 5 |
| **H2b** | K2 + K3 + K4 | 2 | 4 |
| **H3 tiền** | K6 + K7 + K8 (phiếu in dùng `che`) + `giao_dich` | 2 | 5 |
| **H4 còn lại** | K5 + K9 + K10 | 2 | 5 |
| **H6 file xuất** *(tuỳ chọn)* | cột cuối ở Lịch sử thu + sheet hoá đơn | 2 | 3 |
| **H7 chuông + nhật ký** *(tuỳ chọn)* | P1 + audit-log | 2 | 4 |

Cách kiểm mỗi PR: `scripts/test-nhanh.sh` đúng tệp test chạm; bài kiểm đếm; **bấm thật 375 và 1280** trên stack local riêng cổng (dev-up.sh; thêm 2 khách `DEMO-*` trùng tên, khác số) đúng danh sách màn của PR; thân PR có "kịch bản bấm thử" + bảng "nút/link đã đụng" (`.claude/rules/giao-dien.md` mục 5). Sửa `docs/SITEMAP.md` chỉ khi đổi route (không đổi).

## 2. Việc 2 — Chuẩn hoá số điện thoại

### 2.1 Hiện trạng: 5 bản "chuẩn hoá" lệch nhau

| # | Ở đâu | Luật | Lệch ở đâu |
|---|---|---|---|
| 1 | `src/clinicai/core/phone.py` `normalize_vn_phone` (nguồn chính: MPI, tạo/sửa khách, thêm số) | nhận `090…`, `8490…`, `+8490…`, `0084…`, 9 số thiếu 0, bỏ `. - ( )`; đầu số 03/05/07/08/09; **không nhận 02** | schema `PatientCreate/Update` tự thêm ngoại lệ `^02\d{8}$` (số bàn) bằng regex riêng |
| 2 | `src/dashboard/lib/validation.ts` `normalizePhoneVi` / `PHONE_RE` / `phoneError` | `^0[235789]\d{8}$`, **cắt cứng 10 số** | dán `+84 912 345 678` ở ô dùng `digitsOnly().slice(0,10)` (PatientAdminEditor, ô thêm số `NewPatientForm.tsx:278`) → thành `8491234567` → bị từ chối khó hiểu |
| 3 | `src/clinicai/services/providers/zalo.py` `chuan_hoa_sdt` | ra `84xxxxxxxxx` cho ZNS | không kiểm đầu số (nhận `0100000000`) |
| 4 | `src/clinicai/schemas/staff.py` `sdt_hop_le` (SĐT nhân sự) | 9–11 chữ số bất kỳ | nhận số vô nghĩa; `NhanSuBoard.tsx:460` gõ thẳng |
| 5 | `src/clinicai/services/nhap_lich_su_notion.py` (SQL `length(sdt)=9`) | ghi thẳng `phone_primary` không qua hàm nào | **nguồn của 48 số sai trên prod** |
| + | Next `app/api/patients/route.ts` (POST/PATCH), `check-phone/route.ts` | `PHONE_RE` riêng; check-phone lấy "10 số cuối" | luật nghiệp vụ nằm trong route Next (trái SO-LUAT Phần 3) |

Chưa có **ràng buộc nào ở Postgres** trên `patient.phone_primary/phone_secondary` (chỉ `patient_sdt_them` có `CHECK ^0[0-9]{9}$`).

### 2.2 Kiểm kê ô nhập & chỗ so khớp SĐT

**Ô NHẬP (ghi)**

| Ô | File | Đường ghi | Qua `normalize_vn_phone`? | Sửa |
|---|---|---|---|---|
| SĐT chính + người nhà, tạo khách | `patients/new/NewPatientForm.tsx` (:1226, :1317) | POST `/api/patients` → `PatientCreateDTO` | có (FE `normalizePhoneVi` + BE validator) | thay bằng `<OSdt>` |
| Thêm số cho khách trùng | `NewPatientForm.tsx:211-278` (`ThemSdtChoKhach`) | POST `/api/patients/sdt-them` | có (BE) | cắt cứng 10 số → thay `<OSdt>` |
| Sửa hồ sơ khách | `PatientAdminEditor.tsx:363,376` | PATCH `/api/patients` → `PatientUpdateDTO` | có (BE) | cắt cứng 10 số → thay `<OSdt>` |
| Khách mua lẻ ở nhà thuốc | `pharmacy/KhachMuaThuoc.tsx:273` | `/pharmacy/ban-le` → `ban_le_service._tao_khach` → `PatientCreateDTO` | có (BE); FE **không nắn gì** | thay `<OSdt>` |
| SĐT nhân sự | `nhan-su/NhanSuBoard.tsx:460` | `schemas/staff.py` | **không** (luật #4) | dùng hàm chung (cho phép số bàn) |
| SĐT cơ sở | `settings/clinic-config` → `clinic_location.phone` | cấu hình | **không** (1 bản ghi viết `9999 999 999`) | dùng hàm chung |
| Nhập Notion (đã chạy xong, code còn) | `nhap_lich_su_notion.py:161-173` | INSERT thẳng SQL | **không** | không chạy lại; thêm trigger chặn (§2.5) |
| *(sắp có)* khách tự khai QR | `docs/KE-HOACH-QUET-QR.md` PR E (nhánh khác, chưa vào main) | — | — | **bắt buộc đi qua hàm chung** — ghi vào mẫu giao việc |

**CHỖ SO KHỚP / TÌM THEO SĐT (đọc)**

| Chỗ | File | Cách khớp | Hiểu `+84…` / `84…`? |
|---|---|---|---|
| Kiểm trùng lúc tạo, MPI, khoá tạo đồng thời | `patient_service.py:182-196`, `mpi_service.py:110` | `= ANY(phone_variants)` (3 cách viết) | có |
| Tra theo số / cảnh báo "số dùng chung" | `patient_service.get_by_phone`, `find_phone_duplicates`; `GET /patients/check-phone`, `GET /patients` | `phone_variants` | có |
| Danh sách bệnh nhân, Đặt lịch (tìm khách) | `danh_sach_benh_nhan_service.mau_so`, `man_dat_lich_doc._TIM_SQL` | `sdt_tim_kiem LIKE %chữ số%` | **không** (`+84912…` → `%84912…%` không khớp `0912…`) |
| CSKH danh sách | `danh_sach_khach_cskh.py:240` | `sdt_tim_kiem ILIKE` thô | không (không bỏ dấu cách) |
| Nhà thuốc tìm khách | `ban_le_service.tim_khach` | `phone_primary/secondary LIKE %số%` | không; **không tìm số thêm** (`patient_sdt_them`) |
| Lễ tân / Đặt lịch (lọc phía trình duyệt) | `lib/tiep-don.ts:101`, `BookingHub.tsx:620`, `CustomersView.tsx:837` | `includes(q)` thô | không (lọc tạm trong lúc chờ máy chủ; gõ có dấu cách thì hụt) |
| Cảnh báo trùng ở màn tạo (Next) | `app/api/patients/check-phone/route.ts:42-57` | "10 số cuối" + `ilike` (đọc DB trực tiếp — route duy nhất còn chạm DB, **đã tắt**) | có |
| Hàm SQL cũ | `doctor_patient_list` (baseline) | `phone_primary ILIKE %q%` | không |
| Gửi Zalo/nhắc | `tuong_tac_cskh_service.py:865-892`, `recall_job_service`, `providers/zalo.py` | `chuan_hoa_sdt` (#3) | có, nhưng bản riêng |

### 2.3 Thiết kế: MỘT hàm, một dạng lưu

**Hàm duy nhất** `src/clinicai/core/phone.py`, Python thuần, **không ném**, rác → `None`:

```
chuan_hoa_sdt(raw: object) -> SoDienThoai | None     # SoDienThoai(so="0912345678", loai="DI_DONG"|"CO_DINH")
mau_tim_sdt(q: object) -> str | None                 # ô tìm: hiểu +84/84/0084/thiếu 0 → mẫu LIKE trên dạng chuẩn
sang_e164(so: str) -> str | None                     # "+84912345678" — CHỈ dùng khi gửi Zalo/SMS
dinh_dang_hien_thi(so: str) -> str                   # "0912 345 678"
che_sdt(so: str) -> str                              # "0912 ••• 678"
```
`normalize_vn_phone` / `phone_variants` giữ làm vỏ mỏng gọi hàm mới (không vỡ test cũ). `zalo.chuan_hoa_sdt`, `schemas/staff`, schema khách, route Next đều gọi/chuyển tiếp hàm này — **bỏ 4 bản kia**. FE chỉ giữ nắn nhẹ lúc gõ (bỏ ký tự lạ, đổi `+84`→`0`, **không cắt cứng**) và gọi lại máy chủ để quyết.

**Bảng ví dụ (đây cũng là bộ test phải đếm đúng):**

| Người gõ | Kết quả | Ghi chú |
|---|---|---|
| `0912 345 678` · `0912.345.678` · `0912-345-678` | `0912345678` | |
| `+84 912 345 678` · `(+84) 912345678` · `84912345678` · `0084912345678` | `0912345678` | |
| `912345678` (thiếu 0) | `0912345678` | giữ như nay |
| `0281234567` (số bàn Hà Nội/HCM) | `0281234567`, loại `CO_DINH` | giữ như nay; không gửi Zalo |
| `+1 415 555 2671` · `+82 10 1234 5678` · `001 415 555 2671` | **nhận**, lưu `+14155552671` (loại `QUOC_TE`, chỉ kiểm độ dài 8–15 số) | **Tuyền/Quang chốt 17/10: có nhận** — hiện phải gõ vào ghi chú |
| `091234567` (thiếu 1 số) · `0912345678 9` · `0123456789` (đầu số lạ) | từ chối | |
| `0912345678 gặp chị Hoa` · `abc` · `''` · `None` · `12345` · chuỗi 5.000 ký tự | `None` (không ném, không 500) | luật repo |
| số full-width `０９１２…`, có ký tự vô hình/NBSP | chuẩn hoá được hoặc `None`, không ném | thêm vào test rác |

**Nơi lưu dạng chuẩn — số VN giữ `0xxxxxxxxx` (national 10 số), KHÔNG chuyển cả hệ thống sang E.164 (số quốc tế mới lưu `+…`, xem §2.3b):**

| | `0xxxxxxxxx` (đề xuất, = hiện nay) | E.164 `+84…` |
|---|---|---|
| Dữ liệu prod | 8.432/8.434 số dùng được **đã đúng dạng** | phải đổi ~8.4k dòng + `patient_sdt_them` + `sdt_tim_kiem` + staging mask |
| Sửa code | thêm hàm, bỏ bản trùng | đổi 4 truy vấn, `phone_variants`, CHECK, mọi chỗ hiển thị |
| Số nước ngoài | lưu thêm dạng `+<mã nước><số>` cùng cột (hai dạng không lẫn nhau) → **chọn cách này**, không cần chuyển 8,4k dòng | chứa được nhưng phải chuyển hết |
| Gửi Zalo/SMS | `sang_e164()` lúc gửi | sẵn |
| Rủi ro | thấp | **cao** (đổi hành vi tìm kiếm đột ngột, đúng điều cần tránh) |

### 2.3b Số nước ngoài — ĐÃ CHỐT NHẬN (17/10)

Hiện khách nước ngoài không nhập được nên nhân viên ghi số vào ghi chú → không tìm được, không gọi nhanh, không thấy cạnh tên. Thiết kế (add-only, không đổi dữ liệu cũ):

| | |
|---|---|
| **Lưu cùng cột `phone_primary` / `phone_secondary` / `patient_sdt_them`**, hai dạng không lẫn nhau | VN: `0912345678` · quốc tế: `+14155552671` (E.164: `+`, mã nước 1–3 số, tổng 8–15 số) |
| Nhận vào | `+1 415 555 2671`, `+82 10-1234-5678`, `(+1) 415.555.2671`, `001 415 555 2671` → đều ra `+14155552671` / `+821012345678`. `+84…` luôn quy về `0…` (không bao giờ lưu `+84`). |
| Ô chọn nước (như app chuẩn) | `<OSdt>` có ô chọn nước **mặc định 🇻🇳 +84**. Gõ `0912…` → hiểu là VN. Gõ `+…` hoặc `00…` → tự nhận nước theo mã, ô chọn nước tự nhảy. Muốn nhập số nước ngoài không gõ `+` → chọn nước ở ô bên cạnh rồi gõ số nội địa (`415 555 2671` + chọn 🇺🇸 → `+14155552671`). Backend nhận thêm tham số `quoc_gia` (mặc định `VN`). |
| Từ chối | số không hợp lệ theo nước đã chọn; số ngắn hơn 8 hoặc dài hơn 15 số; có chữ. Thông báo nói rõ "số này không phải số VN — chọn nước khác hoặc bắt đầu bằng +" |
| Kiểm tới đâu | **VN: luật tự viết như nay** (đầu số 03/05/07/08/09, 10 số). **Nước khác: dùng thư viện `phonenumbers` (bản Python của libphonenumber, chuẩn mà Google/Zalo-các-app dùng)** — kiểm đúng độ dài/đầu số từng nước, chỉ gọi khi số KHÔNG phải VN. Thêm 1 phụ thuộc (thuần Python); quyết kỹ thuật tự chọn, không cần hỏi chủ |
| Hiện | `+1 415 555 2671` (cách nhóm theo mã nước thô); che: `+1 415 ••• 2671` |
| Tìm | ô tìm hiểu `+`/`00` + số; so khớp theo chuỗi số (đã có `sdt_tim_kiem`); nhận thêm dạng ngắn (gõ `415555`) |
| Kiểm trùng / khoá tạo đồng thời | số quốc tế khớp **nguyên chuỗi chuẩn** (không có "3 cách viết" như số VN) |
| Gửi Zalo/SMS | số quốc tế **không gửi ZNS** (ZNS chỉ số VN) — đánh dấu "không gửi được", CSKH gọi tay |
| Gõ nhầm | vẫn cảnh báo "số này đã thuộc hồ sơ khác" như nay |
| Trigger Postgres | regex nhận **hai dạng**: `^(0[0-9]{9}|\+[1-9][0-9]{7,14})$` |
| Số đang nằm trong ghi chú | **không tự tách** (máy không biết số nào là số khách). Đo thử: `ghi_chu_khach` 1 dòng; nơi khác (Notion, ô chữ) chưa quét hết → PR S5 xuất danh sách cho CSKH chuyển sang ô SĐT |

Tác động lên bảng §2.1: `normalize_vn_phone` giữ nguyên nghĩa "chỉ VN"; hàm mới `chuan_hoa_sdt` trả `loai ∈ {DI_DONG, CO_DINH, QUOC_TE}`. FE: ô `<OSdt>` bỏ cắt cứng 10 số; ô báo lỗi nói rõ "số nước ngoài cần bắt đầu bằng +".

**Dạng gốc người gõ:** *không lưu.* Dạng gốc không có giá trị nghiệp vụ, chỉ gây hai cách viết cho một số. Vết "ai gõ gì" nằm ở nhật ký thao tác (đang chỉ ghi 4 số cuối — giữ nguyên).

### 2.4 Quyết định cần Tuyền / Quang (kèm đề xuất mặc định)

| # | Câu hỏi | Ví dụ số | Đề xuất mặc định |
|---|---|---|---|
| **S-Q1** | ~~Có nhận số nước ngoài không?~~ **ĐÃ CHỐT 17/10 (Tuyền/Quang): CÓ** — đã có khách nước ngoài, hiện không nhập được nên phải ghi vào ghi chú | `+1 415 555 2671`, `+82 10 1234 5678` | Xem §2.3b. Không còn câu hỏi nào (cách nhập + thư viện kiểm: tự chọn theo chuẩn app phổ biến) |
| **S-Q2** | Số bàn `02…` có nhận không? | `028 1234 567` (bàn) | **Giữ nhận** như hiện nay (đã cho phép ở FE+BE), đánh loại `CO_DINH`, không gửi Zalo. Hiện **0** hồ sơ prod dùng số bàn. |
| **S-Q3** | **48 hồ sơ số sai** (nhập Notion: 9 số mà thiếu 1 số, hoặc 10 số đầu lạ) xử lý thế nào? | ví dụ dạng `09` + 7 số (thiếu 1), `65xxxxxxxx` | **Không tự sửa.** Xuất danh sách (mã khách, không in số) cho CSKH gọi hỏi lại; sửa trên màn hồ sơ. 1 hồ sơ "viết khác dạng" sửa tay luôn. |
| **S-Q4** | Ô SĐT nhân sự / cơ sở dùng cùng luật? | nhân sự gõ `0912345678` hay `024 3xxx xxxx` | **Cùng hàm**, nhận cả số bàn. Hiện nhân sự có 18/97 số, cơ sở 1 số viết `9999 999 999`. |
| **S-Q5** | Khi nhập số trùng với khách khác | `0912345678` đã thuộc 2 hồ sơ | **Giữ nguyên**: cảnh báo, không chặn (mẹ-con dùng chung số hợp lệ; 333 số đang dùng chung 691 hồ sơ). Không thêm UNIQUE. |

### 2.5 Dữ liệu cũ & Postgres

**Cách đo (chỉ đọc, lặp lại được):** đọc bản sao lưu đêm đã kéo về Mac (`~/Projects/ClinicAI-Backups/ban-sao/*.sql.gz`), tách khối `COPY public.patient…`, chạy hàm chuẩn hoá thật của repo, **chỉ in số đếm và "dạng"** (`9` thay chữ số). Không ssh vào VPS. Sẽ đưa script vào `scripts/do-sdt-ban-sao.py` (PR S5) để đo lại đúng ngày deploy.

| Bảng.cột | Dòng | Đúng dạng | Viết khác dạng | Sai/rác | Trống | `+`, nước ngoài |
|---|---|---|---|---|---|---|
| `patient.phone_primary` | 8.787 | 8.432 | 1 | 48 | 306 | 0 |
| `patient.phone_secondary` | 4 | 4 | 0 | 0 | — | 0 |
| `patient_sdt_them` | 1 | 1 | 0 | 0 | — | 0 |
| `staff.phone` | 97 | 18 | 0 | 0 | 79 | 0 |
| `clinic_location.phone` | 2 | 0 | 1 (`9999 999 999`) | 0 | 1 | 0 |
| `patient_next_of_kin`, `cskh_log` | 0 / 126 | — | — | — | 0 / 126 | 0 |

48 số sai: tất cả mã `KHACH-…`, tạo chủ yếu 11/2025 (đợt nhập Notion). Mọi hồ sơ trong sổ đều `is_active`.

**Kế hoạch chuyển đổi (add-only, không đổi hành vi tìm đột ngột):**
1. **Không chạy migration đổi dữ liệu hàng loạt** — chỉ 1 hồ sơ + 1 cơ sở cần sửa, làm trên màn. 48 số sai chờ người xác minh (S-Q3).
2. Hàm mới **chỉ mở rộng** điều được nhận (hiểu `+84` ở ô tìm), không thu hẹp: số cũ vẫn tìm ra như cũ (`sdt_tim_kiem` giữ).
3. **Migration mức 3, add-only:** trigger `BEFORE INSERT OR UPDATE OF phone_primary, phone_secondary` — **chỉ nổ khi giá trị số THAY ĐỔI** và không khớp `^(0[0-9]{9}|\+[1-9][0-9]{7,14})$`. *Vì sao không dùng `CHECK … NOT VALID` thuần:* Postgres vẫn kiểm CHECK trên **mọi** UPDATE hàng đó, nên 48 hồ sơ sai sẽ không check-in/sửa được (lỗi khó hiểu giữa giờ khám). Khi 48 hồ sơ đã sạch mới nâng lên `CHECK` + `VALIDATE`.
4. Kẽ hở tranh chấp (SO-LUAT Phần 6): tạo khách đồng thời đã có khoá `pg_advisory_xact_lock(phone)` — sau chuẩn hoá khoá luôn theo dạng chuẩn (bỏ `sorted(variants)[0]` khi dữ liệu sạch). Không thêm UNIQUE (S-Q5).
5. **Staging mask** (`scripts/staging-che-du-lieu.sql`) phải sinh số hợp lệ — test `test_staging_che_du_lieu.py` thêm ca "số đã che qua được trigger".

### 2.6 PR (<400 dòng mỗi PR) và ước giờ — Việc 2

| PR | Nội dung | Mức | ~Dòng | ~Giờ |
|---|---|---|---|---|
| **S1** | `core/phone.py` hàm mới (VN + quốc tế) + vỏ cũ; thay bản Zalo/staff/schema; test rác (bảng §2.3, hơn 50 ca, **thử ngược**) | 2 | 300 | 4 |
| **S2** | Tìm theo SĐT: `mau_tim_sdt` dùng ở `mau_so`, `man_dat_lich_doc`, `ban_le_service` (thêm số thêm), CSKH; bỏ lọc `includes()` thô ở 3 file TS bằng API/hàm chung | 2 | 250 | 3 |
| **S3** | `<OSdt>` (components/ui, có ô chọn nước mặc định 🇻🇳) thay 6 ô nhập; `validation.ts` chỉ còn nắn nhẹ; route Next bỏ `PHONE_RE`, chuyển tiếp; bài kiểm "đếm" ô SĐT phải dùng `<OSdt>` (Luật 12.2) | 2 | 350 | 4 |
| **S4** | Trigger migration + test + staging-mask (mức 3, diễn tập migration) | 3 | 120 | 2 |
| **S5** | `scripts/do-sdt-ban-sao.py` + danh sách 48 + hướng dẫn CSKH | 1 | 150 | 1,5 |

Cách kiểm: pytest `scripts/test-nhanh.sh` (test rác + DB), bấm thật 375/1280 trên stack local (`dev-up.sh`, cổng riêng) với các số trong bảng §2.3; CI máy 1 lần cuối mỗi PR; **không** staging/prod cho tới khi duyệt.

## 3. Thứ tự làm, rủi ro, tổng giờ

### 3.1 Thứ tự (giá trị sớm nhất trước, mỗi bước độc lập, mỗi PR một nhánh từ `origin/main`)

```
 S1 hàm chung ──► H0 thành phần ──► H1 chỉ-TSX ──► H5 trùng tên khi tạo khách   ← Tuyền thấy ngay
        │                                  │
        │                                  └─► H2a ─► H2b ─► H3 ─► H4            ← backend + màn còn lại
        ├─► S2 tìm theo SĐT ─► S3 ô nhập <OSdt>
        └─► S4 trigger (mức 3, SAU khi S1–S3 lên) ─► S5 script đo + 48 hồ sơ
                                     H6 file xuất · H7 chuông+nhật ký: tuỳ chọn, sau cùng
```
Có thể chạy song song 2 nhánh (H* và S*) vì không chung file, trừ `core/phone.py` (S1 làm trước, rồi H0 chỉ import). Mỗi việc một dải giờ migration riêng (chỉ S4 có migration) và cổng web/API riêng (CLAUDE.md mục 2).

**Tổng ước: Việc 1 ≈ 31 giờ (gồm tuỳ chọn 7 giờ) · Việc 2 ≈ 16 giờ · cộng ≈ 47 giờ ≈ 6 ngày làm**, chưa kể chờ duyệt, CI, staging.

### 3.2 Rủi ro

| Rủi ro | Mức | Cách giảm |
|---|---|---|
| Đụng logic cũ khi nhận số quốc tế (phải sửa cùng S1/S4) | `patient_sdt_them.so_dien_thoai` có `CHECK ^0[0-9]{9}$` → **nới CHECK** (migration add-only, S4) mới lưu được `+…`; `phone_variants()` trả `[]` cho số quốc tế → kiểm trùng/khoá tạo đồng thời/MPI im lặng bỏ qua → phải trả `[canonical]`; `mpi_service.score` so `normalize_vn_phone` → quốc tế luôn `None` → phải so chuẩn mới |
| Thêm SĐT vào chuông/nhật ký → SĐT nằm trong DB/log | cao | chỉ P1 hẹp 5 loại; `_SENSITIVE_KEYS`; hỏi H-Q4 |
| Lộ SĐT ra TV/Telegram/đối tác do dùng chung payload | cao | bài kiểm sẵn có giữ nguyên; `sdt_che` do máy chủ quyết; bài kiểm "đếm" |
| Test Python ghim cột/dict (`test_danh_sach_hoa_don.py:566,634`, `test_quay_thu.py:406`, `test_xuat_hoa_don.py:17`, các test `==` cả dict `hang_cho/bang/overview` — **chưa kiểm hết**) | trung bình | thêm cột ở CUỐI; chạy đúng tệp bằng `test-nhanh.sh` trước khi sửa để biết nền |
| Cột chật ở 375px (`/customers` có chi tiết, cột trái phòng, `/truong-ca`) | trung bình | dòng phụ; bấm thật 375/768/1280 |
| Quên 1 nhóm trong "việc còn tồn" hoá đơn (đường từng chậm, nhiều SQL) | trung bình | test đếm nhóm; không thêm JOIN; đo EXPLAIN |
| Trigger chuẩn hoá chặn nhầm 48 hồ sơ cũ (check-in/sửa giữa giờ) | trung bình | trigger chỉ nổ khi **số thay đổi**; xem §2.5 |
| Ba nhóm tên trường (`ten` = tên dịch vụ ở `ChuaXepPhong`, `khach` = tên khách) dễ vẽ nhầm | thấp | `<TenKhach>` nhận đúng `ten`/`ma`/`sdt`, bài kiểm đếm |
| Không bấm được 375px trong lúc lập kế hoạch | thấp | kiểm khi code; tờ này chỉ kết luận từ mã nguồn |

### 3.3 Cái GÌ KHÔNG đổi (để khỏi lo)
Tìm kiếm cũ vẫn tìm ra như cũ; mã BN vẫn hiện; không đổi route/sidebar (không cần `SITEMAP`/`BAN-DO-CODE` — nếu có thêm router thì chạy `ban-do-code.py`); không migration đổi dữ liệu; không chạm prod/staging trong lúc lập kế hoạch.

## 4. Câu hỏi cho Tuyền / Quang — mỗi câu có ví dụ và đề xuất mặc định

Ví dụ chung: hai khách **Nguyễn Thị Hoa** — `KHACH-2301`, SĐT `0912 345 678` và `KHACH-2455`, SĐT `0987 654 321`.

| # | Câu hỏi | Chọn A / B | Đề xuất |
|---|---|---|---|
| **H-Q1** | ✅ **ĐÃ CHỐT 17/10 (Tuyền/Quang): B — che giữa.** Phiếu thu / phiếu hướng dẫn in 80mm (tờ khách cầm đi giữa các phòng)** in SĐT thế nào? | A: `0912 345 678` · B: `0912 ••• 678` · C: không in | **B** — khách phân biệt được số của mình, người ngồi cạnh không đọc được cả số |
| **H-Q2** | **Cổng đối tác** (phòng xét nghiệm ngoài) thấy gì cạnh tên? Họ hiện thấy tên + mã. | A: không thêm · B: 4 số cuối `…5678` · C: cả số | **A** (an toàn; đối tác làm việc theo mã BN). Nếu đối tác phàn nàn trùng tên → B |
| **H-Q3** | **Cảnh báo trùng khi tạo khách** ("đã có 3 hồ sơ trùng họ tên") hiện cố ý không trả SĐT. Có đảo lại không? | A: hiện cả số · B: hiện `0912 ••• 678` · C: giữ nguyên | **A** — nhân viên đã thấy cả số ở danh sách bệnh nhân; đây đúng là chỗ trùng tên cắn nhất |
| **H-Q4** | **Chuông** "Hẹn tái khám — cần gọi chốt giờ: Nguyễn Thị Hoa (KHACH-2301)" có thêm SĐT không? (SĐT sẽ được **lưu** trong bảng thông báo, chuông cũ không đổi) | A: thêm cho 5 loại chuông "gọi khách" · B: thêm cột để đọc luôn mới (mức 3) · C: không | **A**, làm sau cùng (H7) |
| **H-Q5** | **File Excel/CSV gửi kế toán** (Lịch sử thu, hoá đơn): thêm cột "Điện thoại" ở cuối? File MISA thì **không đổi**. | A: có · B: không | **A cho 2 file này**, báo cáo cuối ngày để sau |
| **H-Q6** | Khách có 2 số (`0912…` và số người nhà), hoặc chưa có số: hiện gì? | A: chỉ số chính, trống thì ẩn · B: hiện cả hai | **A** (prod: 306/8.787 hồ sơ trống số; chỉ 1 số thêm toàn hệ thống) |
| **S-Q2** | Số bàn `028 1234 567` có nhận không? | A: có (như nay) · B: không | **A** (0 hồ sơ prod dùng; không gửi Zalo) |
| **S-Q3** | **48 hồ sơ số sai** (nhập Notion, vd `09` + 7 số, thiếu 1 chữ số) xử lý ai? | A: xuất danh sách cho CSKH gọi hỏi lại · B: máy tự sửa | **A** — máy không đoán được số nào đúng |
| **S-Q4** | SĐT nhân sự / cơ sở dùng cùng luật? (nhân sự hiện nhận 9–11 số bất kỳ) | A: cùng luật · B: để lỏng | **A** |
| **S-Q5** | Hai hồ sơ cùng một số (mẹ-con `0912 345 678`) khi nhập: | A: cảnh báo, vẫn cho (như nay) · B: chặn | **A** (333 số đang dùng chung 691 hồ sơ) |

**Chưa cần hỏi** (đã chốt mặc định, báo lý do): không thêm quyền riêng "xem SĐT" (đảo quyết định mở full lego 30/09); TV phòng chờ và Telegram **không bao giờ** có SĐT; mã BN giữ nguyên.

## 5. Điều chưa kiểm được (nói thẳng)

- Chưa bấm 375/768/1280 — mọi nhận xét "chật/cắt chữ" đọc từ class Tailwind.
- Chưa chạy `EXPLAIN` và chưa đo thời gian truy vấn; "≈0 chi phí" dựa trên việc đọc từng SQL thấy đã `JOIN patient`.
- Chưa mở hết ~100 bài `*.test.mts` và các test Python ghim dict/cột; chưa biết sửa chuỗi chuông làm đỏ test nào.
- Số đo dữ liệu lấy từ **bản sao lưu 17/10 02:15**, không phải prod trực tiếp; lệch tối đa vài trăm hồ sơ mới trong ngày.
- Còn thiếu: nguồn backend `/nhac-tai-kham`, `cong_no_service.doc_khach_con_no`, `matches` khi trùng SĐT ở bán lẻ, `ops/LoiCanhBao` (thông điệp lỗi có thể chứa tên), `lich_su_notion`, `luot_dong_thoi_gian.nhan`; email/SMS (không thấy mã gửi).
- File MISA thật có chịu thêm cột hay không: không kiểm — nên mặc định không đổi.
