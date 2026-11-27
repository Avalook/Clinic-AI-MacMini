# Kế hoạch (mức 3, chờ Tuyền duyệt): quy đổi hộp ↔ gói lúc nhập + xử lý thuốc khách trả

Soạn 17/10/2026 sau buổi mổ xẻ Kho thuốc (`docs/MO-XE-KHO-THUOC-VAT-TU.md`). Quang đã đồng ý hướng này
(**ít bước nhất, không rò tiền, không quá cứng**); Tuyền duyệt trước khi viết code. Hai việc, **hai PR riêng**.

## Việc A — Quy đổi hộp ↔ gói LÚC NHẬP

**Vấn đề (đã dựng lại trên bản local):** Androgel nhập 6 hộp, bán theo gói. Giao thuốc ghi tiền nhưng kho vẫn 6 hộp,
dòng "Đã giao, chưa trừ kho" không có lô nào gắn được (luật đúng: `không tự quy đổi hộp, vỉ, viên`).
Prod lúc đo 16/10 có 110/160 lô lệch đơn vị (đều là lô mẫu `DEMO1709-*`).

**Cách làm:** kho chỉ giữ **một đơn vị = đơn vị bán** (`drug_catalog.don_vi_ban`). Nhập khác đơn vị thì đổi ngay ở cửa nhập.

Ví dụ: nhập 6 hộp, 1 hộp = 10 gói, giá 450.000đ/hộp → kho ghi **60 gói**, giá vốn **45.000đ/gói**. Bán 2 gói → kho 58.

| Chỗ | Việc | Ghi chú |
|---|---|---|
| Cửa nhập duy nhất `pharmacy_service.nhap_vao_lo` (cả `receive` lẫn `kho_thuoc_service.tao_phieu_nhap` đều qua đây) | thêm hàm thuần `quy_doi_dong_nhap` đứng TRƯỚC: đơn vị → đơn vị bán, số lượng × hệ số, giá ÷ hệ số | giá vốn `drug_batch.cost_price` là numeric(12,0): làm tròn đồng, ghi số gốc để đối chiếu |
| API `POST /pharmacy/receive`, `/pharmacy/phieu-nhap` | nhận thêm `he_so` (tuỳ chọn) | khác đơn vị bán mà chưa có hệ số nào → 422 "Nhập hệ số: 1 hộp = ? gói" (không đoán) |
| Migration (chỉ THÊM) | bảng `thuoc_quy_doi (clinic_id, drug_catalog_id, don_vi, he_so)`; 3 cột nullable trên `phieu_kho_dong`: `so_luong_goc`, `don_vi_goc`, `he_so` | `CHECK he_so > 0 AND he_so <= 10000`; sổ kho vẫn chỉ-thêm |
| Màn Nhập lô / Phiếu nhập | dòng xem trước "= 60 gói"; ô hệ số chỉ hiện **lần đầu** của thuốc ấy | đã nhớ hệ số thì 0 bước thêm |
| Màn Danh mục & giá | cột "Quy đổi": mỗi thuốc một ô cho từng đơn vị lô, điền một lượt | sau đó nhân viên nhập không bao giờ gõ hệ số |

**Không đổi:** giao thuốc, gán lô, chuyển kho/quầy, kiểm kê ca, xuất–nhập–tồn, báo cáo (cùng một đơn vị nên không phải sửa).
Giao khác đơn vị vẫn bị chặn (đúng). Lô cũ đang theo đơn vị khác **không** tự đổi (lô prod là lô mẫu, sẽ nạp lại tồn thật).

**Chống gõ sai hệ số:** hệ số khác hẳn lần trước (> 10 lần) → hỏi lại một lần; kiểm đếm kho/ca sẽ bắt lệch nếu vẫn sai.

**Test (độc lập với code):** nhập 6 hộp × 10 → tồn 60 và giá vốn 45.000; hệ số rác (0, âm, chữ, 1e12) → câu tiếng Việt, không 500;
phiếu nhiều dòng; hệ số đã nhớ không hỏi lại; cộng thêm vào bộ mô phỏng ngẫu nhiên (`test_mo_phong_kho_day_du_db`)
một thao tác "nhập theo hộp"; làm sai code cố ý (không nhân hệ số, không chia giá) → test phải đỏ.

## Việc B — Màn "Thuốc khách trả chờ kiểm"

**Hiện trạng (đã đọc code):** khách trả thuốc → sổ kho ghi `RETURN_RECEIVED` (+ tồn vật lý) và `drug_return.disposition = NULL`
("đã nhận lại, CHƯA quyết xử lý"). Phần ấy **bị trừ khỏi lượng bán được** (`drug_batch_kha_dung()`), tức là không tự bán lại.
**Thiếu:** lệnh quyết định. Trigger `drug_return_guard` đang chặn mọi sửa ("HOLD J1/J2").

Ví dụ: khách trả 1 hộp Eulac (85.000đ): tiền hoàn như hiện nay; hộp nằm ở "chờ kiểm".
**Nhập lại bán được** → lượng bán được +1. **Huỷ** → tồn vật lý −1, giá vốn 60.000đ vào hao hụt.

| Chỗ | Việc |
|---|---|
| Migration (nới guard, chỉ THÊM) | cho `UPDATE` **đúng một lần** `NULL → BAN_LAI \| HUY` (+ người, giờ, lý do); `CHECK` giá trị hợp lệ; mọi sửa khác vẫn bị chặn |
| Service `xu_ly_thuoc_tra` | `BAN_LAI`: chỉ đặt quyết định (hàm khả dụng tự thôi trừ). `HUY`: đặt quyết định + một dòng `DISCARD` (`ref_type = drug_return`) **cùng giao dịch** |
| Màn | Kho thuốc → QUẦY → tab mới "Thuốc trả chờ kiểm (N)" có chấm báo như "Đã giao, chưa trừ kho"; mỗi dòng: thuốc, lô, số lượng, khách, lý do trả, hai nút; xác nhận tại chỗ (không `window.confirm`) |
| Không làm | không chặn lúc khách trả / hoàn tiền; không bắt xử lý ngay (để đó không kẹt gì); không thêm nhánh "cách ly" |

**Test:** trả → khả dụng giảm đúng số trả; `BAN_LAI` → khả dụng tăng lại; `HUY` → tồn vật lý giảm + giá vốn; xử lý lần hai bị chặn ở Postgres;
thiếu quyền bị từ chối; thêm vào mô phỏng ngẫu nhiên; làm sai code cố ý (HUY không ghi DISCARD) → test đỏ.

## Thứ tự, thời gian, rủi ro

- **A trước** (nó sửa gốc "tiền vào mà kho không trừ"), **B sau**. Ước: A ~3 giờ làm + CI, B ~2 giờ (chưa tính duyệt).
- Mỗi PR: migration chỉ **thêm** (bảng/cột nullable, nới trigger), rollback SQL ghi trong đầu file, không đụng dữ liệu cũ.
  Diễn tập migration trên bản sao trước (skill `len-prod`), lên staging bấm theo kịch bản, rồi mới prod; **không áp migration lúc deploy**.
- Rủi ro chính: gõ sai hệ số (đã nêu cách giảm); làm tròn giá vốn theo đồng; thuốc chưa khai đơn vị bán thì không đổi được
  (phải khai ở Danh mục & giá trước — màn sẽ nói rõ).

## Cần Tuyền quyết / duyệt

1. Hệ số lưu ở **bảng riêng** (đề xuất, nhiều đơn vị lô cho một thuốc) hay một cột JSON trên thuốc?
2. Ngưỡng hỏi lại khi hệ số lạ: **10 lần** so với lần trước, đúng không?
3. Ai bấm "Nhập lại bán được / Huỷ": quyền `pharmacy.dispense` (lễ tân kiêm kho thuốc cũng làm được) hay chỉ dược sĩ/quản lý?
4. Lô mẫu trên prod: **xoá rồi nạp tồn thật** theo đơn vị bán (đề xuất) hay đổi từng lô?
