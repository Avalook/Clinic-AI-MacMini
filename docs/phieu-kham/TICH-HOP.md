# Bảy phiếu khám — gói song song, và các điểm tích hợp

> Viết 23/09/2026. Nhánh `claude/7-phieu-kh-m-forms-0dc921`, dựng trên
> `db7377af` (đỉnh đã push của `claude/clinicai-lifecycle-v1`, nơi có Form
> Template Engine). **Không merge, không deploy.** Không đụng `BanKham.tsx`,
> clinical shell / logic chốt hồ sơ, quyền, phòng/roster, thanh bên, danh mục
> V5-A, migration dùng chung. Tệp dùng chung duy nhất bị chạm: `main.py` (mount
> router — CI đòi mọi router phải mount; quyền mặc định chặn tất).

## 1. Gói này có gì

| Phần | Tệp | Ghi chú |
|---|---|---|
| 7 định nghĩa phiếu (dữ liệu) | `src/clinicai/phieu_kham/dinh_nghia/{NT,HMVS,PK,SK,NK,THU_THUAT,SAN_CHAU}.json` | Trích BẰNG MÁY từ nguồn |
| Tham chiếu nguồn (C / F / thuốc) | `…/dinh_nghia/tham_chieu_nguon.json` | Nhãn chờ ánh xạ — `service_code` / `drug_catalog_id` đều `null` |
| Bộ trích | `scripts/phieu-kham/trich-tu-html.py` | Chạy lại khi nguồn đổi |
| Khung + kiểm dữ liệu | `src/clinicai/phieu_kham/khung.py` | Khoá lạ / chữ thay mã → chặn; số, ngày rác → rỗng + cảnh báo |
| Chế độ phiếu | `src/clinicai/phieu_kham/che_do.py` | `editable / finalized_locked / amendment_mode` — NHẬN từ shell |
| Mang sang | `src/clinicai/phieu_kham/mang_sang.py` | Hành chính, sinh hiệu mới nhất, ghi chú tư vấn — chỉ đọc |
| Kết quả CLS | `src/clinicai/phieu_kham/ket_qua_chi_dinh.py` | Nối bằng `service_order_id`, không theo tên |
| Nạp v1 | `src/clinicai/phieu_kham/nap.py` | Chỉ test gọi — xem IP-3 |
| Dịch vụ | `src/clinicai/services/phieu_kham_service.py` | Khung theo bản · cổng `kiem_luu` · đọc kèm; quyền cắm từ ngoài |
| API đọc | `src/clinicai/api/v1/routers/phieu_kham.py` + mount ở `main.py` | Quyền mặc định chặn tất |
| Proxy Next (chỉ GET) | `src/dashboard/app/api/phieu-kham/route.ts` | |
| Hàm thuần giao diện | `src/dashboard/lib/phieu-kham.ts` | Gom nhóm/bảng, giữ nguồn khi tự lưu, `ghiDuoc` |
| Component | `src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/*.tsx` | Điều khiển từ ngoài, CHƯA gắn vào màn nào |

Không có engine thứ hai: khung dùng đúng hình `form_definition.khung`, bản mới
xuất bản qua `PublishFormVersion` của engine.

## 2. Nguồn và BA CON SỐ (đừng lẫn)

Nguồn: `ClinicAI-7-phieu-v5-final-review.html` (sha256 ghi trong mỗi JSON).
`chi-dinh.html` dùng đối chiếu phiếu Sàn chậu: Oxford / Valsalva ở đó là câu tự
do, nên giữ `doan_van`, không tự chế thang điểm.

| Phiếu | Khoá ổn định | trong đó từ `data-field-key` | từ `name` | Ô trên khung |
|---|---|---|---|---|
| NT | 86 | 84 | 2 | 57 |
| HMVS | 183 | 163 | 20 | 122 |
| PK | 73 | 71 | 2 | 69 |
| SK | 54 | 52 | 2 | 41 |
| NK | 25 | 23 | 2 | 25 |
| THU_THUAT | 15 | 13 | 2 | 15 |
| SAN_CHAU | 14 | 12 | 2 | 14 |
| **Tổng** | **450** | **418** | **32** | **343** |

- **418** = số ô trong HTML mang thuộc tính `data-field-key` (con số "418
  controls" đếm thẳng trên nguồn).
- **450** = số KHOÁ ỔN ĐỊNH (ô + từng checkbox) = 418 + **32** ô nguồn không gắn
  `data-field-key` mà chỉ có `name`: 18 ô bảng tinh dịch đồ
  `hmvs_semen_<hàng>_<lần>` và 14 ô mục E (`<phiếu>_treatment_other` /
  `_treatment_note`, 2 ô × 7 phiếu). Khoá của 32 ô này lấy từ `name`, và mang cờ
  `khoa_tu: "name"` trong JSON.
- **343** = ô trên khung sau khi gom mỗi nhóm checkbox thành một ô `nhieu_chon`.

Test `test_moi_phieu_dem_dung_tung_con_so` canh cả bốn cột từng phiếu;
`test_450_khoa_bang_418_data_field_cong_32_chi_name` canh tổng;
`test_32_khoa_chi_name_la_dung_hai_loai_da_biet` canh rằng không có ô thứ 33
nào lọt khỏi `data-field-key` mà không ai giải thích.

Chạy lại bộ trích khi nguồn đổi — không sửa tay JSON:

```bash
python3 scripts/phieu-kham/trich-tu-html.py ~/Downloads/ClinicAI-7-phieu-v5-final-review.html
```

## 3. Contract

**Khung** — hình của engine, thêm vài khoá engine bỏ qua được:

```
[{ma: "HANH_CHINH"|"A".."G", ten, lien_ket?: {loai, truong?, rang_buoc?},
  block: [{ma, ten, kieu, nhom?, goi_y?, lua_chon?: [{ma, ten}],
           bang?: {ma, ten, cot[]}, hang?, cot?, ten_tu_dat?, khoa_tu?}]}]
```

- `ma` của ô = khoá nguồn; `lua_chon[].ma` = khoá từng checkbox nguồn. **Không
  khoá nào suy từ nhãn.**
- Mục liên kết: HANH_CHINH, A (`mang_sang`) · C (`chi_dinh_cls`) · E
  (`don_thuoc`) · F (`chi_dinh_thu_thuat`). C và F **không có ô** — danh sách
  chỉ định thuộc `service_order`.
- Định nghĩa **không mang khoá nào về cách chốt** — chốt là của shell.

**Dữ liệu một lần lưu:** `{khoá_ô: {gia_tri, nguon}}`; `nhieu_chon` → mảng mã
lựa chọn theo thứ tự khung. Giao diện giữ nguyên `nguon` của ô không ai đụng.

**Chế độ** (shell truyền, gói không tự suy): `editable` và `amendment_mode` ghi
được; `finalized_locked` chỉ đọc; giá trị lạ/thiếu → **chặn**.

**Cổng lưu** `PhieuKhamService.kiem_luu(form_id, version, du_lieu, che_do,
identity)` — chỗ lưu (khi có) gọi TRƯỚC khi ghi. Thứ tự: chế độ → quyền → khung
ĐÚNG phiên bản → từng ô. Trả `(sach, canh_bao)`.

**Quyền:** `PhieuKhamService(pool, kiem_quyen=…)`. `kiem_quyen(conn, identity,
hanh_dong)` với `hanh_dong ∈ {doc_phieu, ghi_phieu, doc_ket_qua_cls}` — nhãn của
lời hỏi, KHÔNG phải capability. Mặc định `chua_noi_quyen` = chặn tất.

**API đọc** (đã mount; bị chặn cho tới khi nối quyền):

| Đường | Việc |
|---|---|
| `GET /phieu-kham/dinh-nghia` | bảy phiếu (tên) |
| `GET /phieu-kham/dinh-nghia/{form_id}?version=` | khung một phiên bản |
| `GET /phieu-kham/tham-chieu` | danh mục C / F / thuốc của nguồn |
| `GET /phieu-kham/luot/{visit_id}/dau-phieu` | hành chính + sinh hiệu + tư vấn |
| `GET /phieu-kham/luot/{visit_id}/ket-qua-chi-dinh` | kết quả CLS theo từng chỉ định |

**Component** `PhieuKham`: nhận `dinhNghia, duLieu, cheDo, dauPhieu,
ketQuaChiDinh, onLuu` (+ `donThuoc`, `thuThuat`, `oChiDinhCls`). Không tự lưu
xuống đâu, không có nút chốt.

## 4. INTEGRATION_BLOCKER — phiếu khám chưa có chỗ lưu

**Bảy phiếu khám (5 chuyên khoa + Thủ thuật + Sàn chậu) gắn vào
consultation/visit. Chỉ phiếu kết quả DỊCH VỤ mới gắn `service_order`.**

`form_instance` hiện có `service_order_id` NOT NULL + FK thật. Nên gói này
**không mở, không ghi `form_instance` nào cho phiếu khám**, và KHÔNG giả khám
thành một `service_order` để lọt ràng buộc. Chưa gỡ được thì chưa có
save/load/edit thật cho phiếu khám — chỉ có cổng `kiem_luu` và component điều
khiển từ ngoài.

Cần (không làm trong nhánh này — migration dùng chung):
- `form_instance` gắn được consultation/visit (ví dụ cột `consultation_id`,
  `service_order_id` cho NULL, CHECK "đúng một chủ thể"), unique theo chủ thể
  + `form_id`;
- `FormEngineService` mở/lưu theo chủ thể ấy, và KHÔNG tự đóng dịch vụ khi phiếu
  của consultation được chốt;
- quyết của CORE: chỗ lưu dùng chung `form_instance` hay bảng riêng.

## 5. INTEGRATION_POINT

### IP-1 · Clinical shell (Bàn khám) — gắn component, truyền chế độ
- Gắn `<PhieuKham …/>`, truyền `cheDo` từ luật chốt hồ sơ của shell, và
  `onLuu` ghi xuống chỗ lưu (sau khi có chỗ lưu — mục 4) qua cổng `kiem_luu`.
- `form_id` là form profile chọn theo MÃ, không suy từ tên dịch vụ như
  `resolveServiceCode` cũ.
- Tra `docs/SITEMAP.md` mục B để sửa đủ mọi lối vào phiếu khám.

### IP-2 · Hệ phân quyền của CORE
- Cung cấp `KiemQuyen` cho ba hành động `doc_phieu`, `ghi_phieu`,
  `doc_ket_qua_cls` — thay `lay_kiem_quyen` ở router (sửa hàm hoặc
  `app.dependency_overrides`). Router đã mount nhưng tới lúc ấy mọi đường có
  dữ liệu bệnh nhân đều bị chặn.
- Gói này không thêm capability, không mượn `result.form.fill`. Luật thư ký
  chỉ ghi cho bác sĩ được phân (nếu áp) là của hệ phân quyền.

### IP-3 · Migration dữ liệu — nạp bảy khung v1
- Bảy dòng `form_definition` v1 PUBLISHED, `nhom='PHIEU_KHAM'`, `xuat_ban_boi`
  NULL — đúng logic `clinicai/phieu_kham/nap.py` (không đè nếu đã có bản nào).
- Xếp số SAU các migration của CORE lúc tích hợp.

### IP-4 · Danh mục V5-A — ánh xạ nhãn nguồn sang mã thật
- `tham_chieu_nguon.json`: `chi_dinh_cls[].muc[]` (8 nhóm, 32 nhãn) và
  `thu_thuat[]` (`procedure_1..15`) → `service_code`; riêng "XN máu", "XN dịch
  âm đạo" → mã dịch vụ ĐỐI TÁC (không mã giả, không fuzzy-match).
  `mau_thuoc[]` (`rx_001..073`) → `drug_catalog_id`.
- Chưa ánh xạ: mục F khoá chọn; dòng thuốc từ mẫu mang chip "Chưa gắn thuốc kho".
- Đã nối mã → mã (không qua nhãn): `modal_sa_obung` → `KQ_SA_OBUNG` (test canh
  cả 18 mẫu).

### IP-5 · Đơn thuốc (E) và thủ thuật (F) — điều khiển từ ngoài
- E: shell truyền `donThuoc={{dong, onDoi}}`, ghi qua đường `prescription` sẵn
  có. Ánh xạ cột đề xuất: `ten_thuoc→drug_name_raw` · `drug_catalog_id` ·
  `so_luong→quantity_num/quantity` · `don_vi→unit` ·
  `cach_dung→dosage_instructions` · `luu_y→caution`. **`prescription` không có
  cột đường dùng** — cần chốt.
- F: shell truyền `thuThuat={{daChon, onChon}}`; chọn = tạo `service_order` qua
  lệnh của module Chỉ định.

### IP-6 · Dữ liệu cũ `clinical_form_response`
- Khoá cũ (`ly_do`, `dtd`…) ≠ khoá v5 (`nt_ly_do`, `nt_endo_hist_1`…). Không đối
  tự động (đối qua nhãn = dò theo tên). Hồ sơ cũ vẫn đọc qua `lib/form-schemas`;
  `HoSoKham.tsx` cần đọc thêm chỗ lưu mới sau khi chuyển.

## 6. Nút / link đã đụng

Chưa gắn vào màn nào, nên chưa vai nào thấy.

| Component | Nút | Gọi | Ai |
|---|---|---|---|
| `PhieuKham` | (gõ ô) | `onLuu` của shell — component không gọi API ghi | theo IP-1/IP-2 |
| `PhieuKham` | (mở) | `GET /api/phieu-kham?xem=tham-chieu` | — |
| `KetQuaChiDinh` | [Xem kết quả] | không gọi API | — |
| `DonThuocPhieu` | [Danh mục thuốc] · chọn · [Bỏ] | `onDoi` của shell | theo IP-5 |
| `ChiDinhThuThuat` | ô chọn | `onChon` của shell; khoá khi chưa có mã | theo IP-4 |

## 7. Đã kiểm ở lớp nào

- **Test:** 76 bài Python thuần · 9 bài trên Postgres thật · 9 bài giao diện
  chạy trên chính 7 khung JSON. ruff, format, mypy, tsc, eslint sạch; bộ
  boundary dashboard xanh.
- **API qua HTTP:** chưa gọi thật (quyền chưa nối → chặn tất); CI kiểm router đã
  mount và mọi đường dashboard gọi đều tồn tại.
- **Trình duyệt:** **CHƯA BẤM** — không màn nào gắn component.

## 8. Nợ / câu hỏi mở

- 4 nhãn nhóm nguồn không ghi, người trích đặt tạm (`ten_tu_dat`, màn in
  "(nhãn tạm)"): `nt_mht_type`, `nt_follow_tests`, `hmvs_follow_tests`,
  `pk_follow_tests`.
- NK, THU_THUAT, SAN_CHAU: nguồn tự ghi chưa có phiếu chuẩn → phần lớn ô tự do;
  có ruột thật thì xuất bản v2.
- SK "Ổn định" là ô chữ theo nguồn.
