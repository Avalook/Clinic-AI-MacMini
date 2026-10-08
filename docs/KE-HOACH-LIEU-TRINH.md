# Kế hoạch: Liệu trình điều trị nhiều buổi + sắp lại khối 3/4 hồ sơ khám (BẢN NHÁP chờ Tuyền duyệt, 08/10/2026)

Nhánh nền `origin/dot/0710-nhan-tai-phong` (đụng hồ sơ khám + phòng dịch vụ). Đợt 0710 CHƯA
lên prod (PM chưa cho) → việc này dựng trên nhánh đợt, lên staging cùng/sau đợt.
Nguyên tắc chung (giữ như mọi đợt): **không khoá cứng** · **hoàn tác được mọi thao tác** ·
**không cái gì sau đè cái trước** (lịch sử chỉ-thêm) · **làm mới không mất cũ** ·
**bất biến tiền ép ở Postgres**.

---

## Phần A — Sắp lại khối 3/4 hồ sơ khám (mức 2, KHÔNG migration, làm trước)

Hiện tại (`lib/phieu-kham.ts:855` `KHOI_PHIEU`, `phieu-kham/PhieuKham.tsx`):
khối 3 "Chỉ định điều trị" = D Chẩn đoán và xử lý · E Đơn thuốc · F Dịch vụ khác (lưới chọn
→ thẻ chỉ định NẰM DƯỚI lưới) · G Hẹn khám; khối 4 "Điều trị" = thẻ chỉ định điều trị +
phiếu 2 ô (`KhoiDieuTri.tsx` + `PhieuDieuTri.tsx`).

Lỗi gốc phải sửa cùng: **một chỉ định Ghế điện hiện HAI thẻ** (thẻ `KetQuaChiDinh` ở khối 3
vì mã nằm trong `tc.thu_thuat`, và thẻ khối 4 vì `service_type.nhom='DIEU_TRI'`) — hai định
nghĩa "điều trị" lệch nhau; Laser tiền đình lại rơi vào khối 2. Gom về **một định nghĩa**: cờ
`dieu_tri` máy chủ đã trả (`ChiDinhVaKetQua.dieu_tri`, gốc `MA_DIEU_TRI_SQL`), bỏ dò bằng
`maThuThuat` cho việc phân khối.

Đích (Tuyền chốt Q1 = BỎ ô Chẩn đoán và xử lý, lượt cũ có dữ liệu hiện chỉ đọc):
```
3 Chỉ định điều trị
  THẺ CHỈ ĐỊNH ĐIỀU TRỊ (lên đầu) — MỘT thẻ mỗi chỉ định, gộp thẻ khối 3 + khối 4:
    tên · trạng thái · tiền · [Làm tại bàn khám] · Hoàn tác chỉ định · In · Ảnh-tệp
    phiếu 2 ô Cảm nhận / Vấn đề sau điều trị (CHÍNH form_instance cũ — không chép dữ liệu)
    (Phần B) dải liệu trình: Buổi 3/10 · đã trả 5 · còn nợ 5 buổi · [Điều chỉnh]
  Thủ thuật đã chỉ định (Đặt vòng…) — thẻ KetQuaChiDinh như cũ, cũng LÊN TRÊN lưới
  Dịch vụ khác — ô tìm + lưới chọn (giữ)
  Hẹn khám (giữ nguyên chỗ cuối khối 3)
4 Đơn thuốc   (mục E dời nguyên — cả ô "điều trị khác/ghi chú" đi kèm mục E)
```
"Di dời thật" = component + nguồn dữ liệu dời theo (`KhoiDieuTri` render trong khối 3, nghe
realtime y cũ); dữ liệu DB không đổi chỗ (phiếu điều trị vốn đã là `form_instance` theo chỉ
định) → không migration, dữ liệu cũ hiện đủ.

Phải sửa đủ mọi lối:
- `KHOI_PHIEU` + `PhieuKham.tsx` (thứ tự `theMuc` mục F: thẻ trước lưới; bỏ `khoi===4 ? oDieuTri`;
  thanh bước bên phải: "3 Chỉ định điều trị · N điều trị · M thủ thuật · có hẹn", "4 Đơn thuốc ·
  N thuốc"; nút "Sang: …").
- Nhánh hồ sơ tối giản (lượt Điều trị/Khác, `PhieuKhamLuot.tsx:501-562`) — xếp cùng thứ tự.
- Màn dùng chung `PhieuKhamLuot`: Bàn khám, popup Lịch sử khám, `/patient-list` (chỉ đọc),
  `tasks/ClinicalRecordForm` — đổi một chỗ ăn hết, kiểm cả bốn.
- Bản in `/print/phieu-kham` KHÔNG theo khối (Khám → Đơn thuốc → CLS → Điều trị) — giữ.
- Test khoá cứng phải sửa: `khoi-dieu-tri-boundary.test.mts` (khối 4 "Điều trị"),
  `phieu-kham-boundary`, `ho-so-dich-vu-boundary`, `lich-su-kham-boundary`.
- Docs: `BAN-DO-SUA.md` §5, `SITEMAP.md` /ban-kham.

Ước ~1–1,5h AI, một PR (~300 dòng).

---

## Phần B — Liệu trình điều trị nhiều buổi (mức 3: migration + tiền)

### Hiện trạng đã soi (vì sao không "gắn đại" được)
- Không có gói / số buổi / tạm ứng / ví / số dư ở đâu cả.
- `service_order` = MỘT lần làm: một trạng thái "xong", không cột giá (giá đọc sống
  `service_price`, chốt khi thu vào `payment_bill_line`), **chỉ thu đúng một lần, số lượng 1**
  (trigger `payment_bill_line_mot_lan_phu`, bất biến `THU_TRUNG`).
- Tiền lệ gần nhất: `mang_sang_luot_moi` (chỉ định ĐÃ TRẢ chưa làm dời sang lượt sau) — nhưng
  dời HẾT chỉ định treo sang lượt mới.
- `care_episode` (đợt chăm sóc) không nối `service_order`, không tiền; đặt lịch NEW tự đóng
  đợt → bẫy. **Không dùng.**
- Đặt lịch Điều trị → check-in → consumer sinh MỘT chỉ định (`ho_so_dich_vu.sinh_chi_dinh_dieu_tri`).
- KiotViet: adapter chưa chạy (`POS_ADAPTER=none`), payload chỉ tổng tiền → không vướng.

### Mô hình đề xuất: liệu trình = sổ kế hoạch + sổ tiền; MỖI BUỔI = MỘT `service_order` thường

Loại bỏ: (x) tạo trước N chỉ định cho N buổi — 10 chỉ định "ma" sẽ hiện ở Sắp đến mọi phòng,
hàng chờ, quầy (đúng cái bẫy "phòng nào cũng hiện" hôm qua) và `mang_sang_luot_moi` sẽ bê cả
10 sang lượt sau; (y) ví/số dư tiền chung — không trả lời được "còn mấy buổi".

**Bảng mới** (dải migration riêng, RLS 106 → 109, trigger `notify_row_change` + `LIVE_TABLES`):
1. `lieu_trinh` — khách, `service_code` (dịch vụ nhóm DIEU_TRI), `so_buoi` (kế hoạch, sửa
   được), `don_gia` (CHỐT lúc tạo = giá bảng giá — Q2), `ghi_chu_lo_trinh` (tần suất…),
   `trang_thai` DE_XUAT / DANG_LAM / XONG / DUNG, nguồn (lượt + bác sĩ đề xuất | CSKH),
   người/lúc. Sửa bằng lệnh có `revision` (409 khi màn cầm bản cũ).
2. `lieu_trinh_lich_su` — chỉ-thêm, trigger BEFORE UPDATE ghi bản cũ (như
   `form_instance_lich_su`) → "Lịch sử sửa" trên thẻ.
3. `lieu_trinh_buoi` — nối `service_order` ↔ liệu trình: `service_order_id` UNIQUE, `buoi_so`,
   `tra_truoc` (buổi này trừ vào tiền đã trả trước?), `go_luc` (gỡ — không xoá).

**Tiền trả trước:** dòng hoá đơn loại mới `payment_bill_line.source_type='lieu_trinh'`,
`quantity = k buổi`, `unit_price = don_gia` — thu qua đúng `payment_cycle` dịch vụ của lượt
đang có mặt (quầy thu như cũ: cùng hình thức, chia hình thức, huỷ, hoàn tác, phiếu thu).
- Số buổi đã trả = Σ quantity các dòng `lieu_trinh` của lần thu PAID − Σ đã hoàn.
- Buổi được **phủ** (không vào hoá đơn, cổng tiền coi như đã thu, không thành nợ khi về):
  chỉ định gắn liệu trình + `tra_truoc` + còn buổi đã trả chưa dùng.
- Buổi không phủ (trả từng buổi): vào hoá đơn như chỉ định thường, giá = `don_gia` của
  liệu trình (không lấy giá bảng giá mới).

**Bất biến ép ở Postgres** (khoá dòng `lieu_trinh` FOR UPDATE trong trigger):
- buổi phủ còn sống ≤ buổi đã trả (net hoàn) — hai phòng cùng bấm không trừ âm;
- một chỉ định thuộc ≤ 1 liệu trình; `buoi_so` không trùng trong buổi còn sống;
- `don_gia` không đổi sau lần thu đầu;
- hoàn tiền liệu trình ≤ số buổi đã trả chưa dùng;
- mở rộng `bat_bien_tien_chi_dinh()` (+ `canh_gac`): kiểm thêm LIEU_TRINH_AM / PHU_VUOT.

**Gắn buổi tự động — một chỗ cho cả 6 đường tạo chỉ định:** trigger AFTER INSERT trên
`service_order`: khách có ĐÚNG MỘT liệu trình DANG_LAM cùng `service_code` → gắn buổi kế
(`tra_truoc` nếu còn buổi đã trả). Có 2 liệu trình cùng dịch vụ → không gắn, thẻ hiện
"chọn liệu trình". Chỉ định bị huỷ / bỏ / NOT_SELECTED / không làm → buổi tự gỡ (trả buổi về
liệu trình); hoàn tác bỏ → gắn lại. Không sửa 6 đường tạo, không sửa `so_sua_chi_dinh`.

### Luồng theo vai

| Ai | Ở đâu | Làm gì |
|---|---|---|
| Bác sĩ / ĐD / TKYK | khối 3, thẻ chỉ định điều trị | ô "Lộ trình [N] buổi · ghi chú tần suất" → tạo liệu trình DE_XUAT gắn chỉ định hôm nay là buổi 1. Nút "Chỉ đề xuất, không làm hôm nay" (không tạo chỉ định). Điều chỉnh: đổi số buổi, ghi chú, dừng, mở lại — mọi lệnh có Hoàn tác + lịch sử |
| Lễ tân / thu ngân | quầy dịch vụ, hoá đơn của khách | khối "Liệu trình" của khách đang thu: Buổi đã làm/đã trả/còn lại + tiền còn lại; [Trả trước … buổi] (1…còn lại, nút "Trả hết") → thêm dòng vào hoá đơn đang thu |
| CSKH | `/nhac-tai-kham` (Q4) + khung khách `/customers` | danh sách "Đề xuất liệu trình chưa đăng ký" và "Liệu trình đang dở, quá X ngày chưa quay lại"; [Đăng ký] (1 buổi / N buổi, sửa số buổi) → DANG_LAM; đặt lịch buổi kế (dịch vụ Điều trị) |
| Phòng điều trị | `/phong/[ma]` | KHÔNG thêm danh sách mới. Dòng chỉ định hôm nay có chip "Buổi 3/10 · đã trả trước" |
| Lễ tân check-in | đặt lịch / tiếp đón | chip "Liệu trình Ghế điện: còn 3 buổi đã trả" cạnh khách |

### Phạm vi hiển thị — soi trước (bài học "phòng nào cũng hiện")
- Liệu trình **không** tự sinh dòng ở bất kỳ danh sách vận hành nào (phòng, hàng chờ bàn khám,
  Hành trình, TV). Chỉ chỉ định của HÔM NAY (thứ đã có) mang thêm chip.
- Quầy: chỉ trong hoá đơn của khách đang chọn — không thêm dòng ở bảng quầy.
- CSKH: chỉ ở màn CSKH + khung khách.
- Hồ sơ khám: thẻ liệu trình ở MỌI lượt của khách khi có chỉ định gắn liệu trình; lượt không
  liên quan không hiện. Popup Lịch sử khám / `/patient-list`: chỉ đọc.
- Ghi chú: "Sắp đến mọi khách ở mọi phòng" là luật Tuyền chốt 07/10 cho dây `nhan_tai_phong`,
  liệu trình không làm tệ hơn; muốn thu hẹp thì là việc riêng (đề xuất: gắn `clinic_room_service`
  cho mã điều trị — việc dữ liệu trên màn).

### Soi tình huống (mỗi dòng = một test DB)
| # | Tình huống | Kết quả mong muốn |
|---|---|---|
| 1 | BS đề xuất 10 buổi, khách làm buổi 1 trả lẻ | LT DANG_LAM, buổi 1 thu 1×đơn giá, còn 9 |
| 2 | Đề xuất 10, khách trả trước hết hôm nay | dòng `lieu_trinh` ×10 (hoặc ×9 + buổi 1 phủ) — không thu trùng buổi 1 |
| 3 | Trả trước 5/10, đến buổi 6 | buổi 6 vào hoá đơn đơn giá chốt; quầy gợi ý trả thêm |
| 4 | Khách từ chối hôm nay (NOT_SELECTED) | buổi gỡ, LT ở DE_XUAT → hiện ở CSKH |
| 5 | Về nhà gọi CSKH đăng ký 1 buổi / cả lộ trình | CSKH [Đăng ký] → DANG_LAM; tiền thu khi đến (Q3) |
| 6 | Đặt lịch Điều trị → check-in | consumer sinh chỉ định → trigger gắn buổi kế, phủ nếu đã trả → quầy 0đ, phòng làm ngay không cần tick |
| 7 | Buổi phủ mà khách về không làm | chỉ định huỷ → buổi trả về, số đã trả giữ |
| 8 | Hoàn tác "Xong" buổi | đếm đã làm giảm; tiền không đổi |
| 9 | Hai phòng cùng nhận hai chỉ định cùng LT khi chỉ còn 1 buổi trả | Postgres cho một bên phủ, bên kia vào hoá đơn — không âm |
| 10 | Đổi giá bảng giá giữa liệu trình | LT giữ đơn giá chốt; LT mới dùng giá mới |
| 11 | Giảm số buổi dưới số đã trả | chặn bằng câu báo "đã trả 5 buổi — hoàn tiền trước" (không khoá: hoàn xong làm tiếp) |
| 12 | Dừng LT còn buổi đã trả | buổi dư → tiền thừa / hoàn tiền (luật E hiện có) — Q5 |
| 13 | Làm quá số buổi kế hoạch | tự thêm buổi (so_buoi +1 có lịch sử), không chặn |
| 14 | BS kê lại cùng dịch vụ khi LT đang chạy | gắn vào LT cũ, không đẻ LT mới; muốn LT mới thì bấm rõ |
| 15 | 2 LT cùng dịch vụ (cũ chưa xong + mới) | không tự gắn; thẻ bắt chọn LT |
| 16 | Hoàn tác lần thu trả trước sau khi đã dùng buổi | chặn như hoàn tác thu thường đã có dịch vụ đã làm (luật E5) |
| 17 | Hoàn tác bỏ chỉ định đã phủ | gắn lại nếu còn buổi trả, không thì vào hoá đơn |
| 18 | Check-out lượt có buổi phủ đã làm | không nợ, không chặn |
| 19 | Lượt Điều trị không qua bàn khám | y như #6; bước bác sĩ vẫn tuỳ chọn |
| 20 | Làm tại bàn khám buổi phủ | cổng tiền mở như đã thu |
| 21 | Báo cáo doanh thu ngày | tiền trả trước tính ngày thu (dòng "Ghế điện — trả trước 5 buổi") |
| 22 | Bản sao staging che dữ liệu | thêm cột chữ tự do của LT vào `staging-che-du-lieu.sql` (bẫy đêm 08/10) |

### Tuyền đã chốt (08/10)
- **Q1 — BỎ ô "Chẩn đoán và xử lý"** ở khối 3: phiếu 2 ô của thẻ điều trị thay chỗ đó. Lượt
  MỚI không hiện ô; lượt CŨ có dữ liệu `pk_dx`/`pk_treatment` hiện CHỈ ĐỌC (làm mới không mất
  cũ), bản in vẫn in nếu có. Rủi ro ghi lại: phiếu khám không còn ô chẩn đoán riêng — nếu bác
  sĩ cần thì mở lại là một dòng `KHOI_PHIEU`.
  **ĐỔI (Tuyền, 08/10 sau PR #360):** KHÔNG bỏ — mục D DỜI xuống CUỐI khối 2 "Chỉ định cận lâm
  sàng", sửa được, cả bảy phiếu (HMVS 16 ô / NT 9 ô không được mất; luồng CLS → kết quả →
  chẩn đoán → điều trị). `KHOI_PHIEU`: 2 = C · D, 3 = F · G (+ thẻ điều trị), 4 = E.
- **Q2 — Giá = đơn giá × số buổi, chốt lúc tạo.** Giá gói ưu đãi: làm sau nếu cần.
- **Q3 — Tiền luôn thu ở quầy khi khách có mặt.** CSKH chỉ ghi đăng ký + đặt lịch.
- **Q5 — Dừng giữa chừng: hoàn tiền buổi dư theo luồng tiền thừa/hoàn hiện có, không hạn dùng,
  mở lại được.**

### Mặc định Claude chọn (Tuyền chưa nói khác)
- CSKH xem đề xuất treo ở `/nhac-tai-kham` (màn gọi khách hằng ngày) + tab "Liệu trình" trong
  khung khách `/customers`.
- Trả trước theo **số buổi nguyên** (không đặt cọc tiền lẻ).

### Tách PR (≲400 dòng/PR, không tính test/migration)
| PR | Nội dung | Mức |
|---|---|---|
| A | Sắp lại khối 3/4 + gộp thẻ trùng | 2 |
| B1 | Migration 3 bảng + bất biến + trigger gắn buổi + `lieu_trinh_service` + API + sự kiện | 3 |
| B2 | Tiền: dòng trả trước, phủ buổi (hoá đơn, `finance_gate`, `cong_no`), hoàn, `bat_bien` | 3 |
| B3 | Giao diện thẻ liệu trình (khối 3) + quầy | 2 |
| B4 | CSKH + khung khách + chip phòng/tiếp đón + bản in | 2 |

Kiểm: mỗi PR `scripts/test-nhanh.sh <tệp test mới + 1–2 tệp trực tiếp>` → `ci-may.sh` một lần.
Không chạy tay loạt test cũ, không diễn tập migration tay (diễn tập trên bản sao prod lúc lên
staging/prod theo `len-prod`). Ước: A ~1,5h; B1–B4 ~7–9h AI.
