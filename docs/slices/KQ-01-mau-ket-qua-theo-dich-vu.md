# KQ-01 — Mẫu kết quả gắn với dịch vụ

| | |
|---|---|
| **Mã** | KQ-01 |
| **Module chủ** | `catalogue` |
| **Trạng thái** | ĐÃ CODE 23/09 — backend + test; chưa gắn mẫu nào trên bản thật; màn hình chưa dựng |
| **Nguồn** | Phiếu chỉ định giấy Dr4Women bản 17/08/2026 (`chi-dinh.html` Tuyền gửi) |

## 0. Vì sao có lát này

Trên tờ giấy, cạnh mỗi dịch vụ có nút "📄 Xem mẫu" — người làm biết siêu âm
tuyến vú thì điền vào mẫu nào. Hệ thống thì **không biết**: quan hệ ấy chỉ nằm
trong tờ giấy và trong đầu người làm.

Tách làm hai bảng, vì là hai thứ khác nhau:

| Bảng | Giữ cái gì | Đổi cái này không làm hỏng cái kia |
|---|---|---|
| `ket_qua_mau` | 18 mẫu kết quả | đổi tên mẫu không đụng dịch vụ nào |
| `dich_vu_mau_ket_qua` | dịch vụ nào dùng mẫu nào | KiotViet đồng bộ đè bảng giá cũng không mất liên kết |

Nhét một cột `mau_ket_qua` vào `service_price` là cách chắc chắn để mai kia đồng
bộ bảng giá là mất sạch liên kết.

## 1. Trigger
Màn "Danh mục & biểu mẫu" của quản lý (chưa dựng) · vai: ai có quyền
`catalogue.result_template.manage` (mặc định quản lý).

## 2. Command
```text
BindResultTemplate    POST /api/v1/mau-ket-qua/gan   {service_code, mau}
UnbindResultTemplate  POST /api/v1/mau-ket-qua/go    {service_code, mau}
```
Đọc: `GET /mau-ket-qua` (danh mục) · `GET /mau-ket-qua/dich-vu/{ma}` (bác sĩ hỏi
"dịch vụ này điền mẫu nào") · `GET /mau-ket-qua/de-xuat` (máy gợi ý).

## 3. Events
Chưa có. Gắn mẫu là **cấu hình**, không phải chuyện xảy ra với bệnh nhân. Dòng
gắn tự mang `gan_boi` + `gan_luc` nên vẫn truy được ai gắn.
Khi nào việc gắn mẫu ảnh hưởng hồ sơ đã trả thì mới nâng thành sự kiện.

## 4. Views
- Bác sĩ trả kết quả: hỏi mẫu theo mã dịch vụ.
- Màn quản lý: mẫu nào đang dùng cho những dịch vụ nào.

## 5. Constraint — ép ở đâu

| Luật | Ép ở đâu |
|---|---|
| Không gắn mẫu không tồn tại | **Postgres** (khoá ngoại `(clinic_id, mau)`) |
| Một dịch vụ + một mẫu chỉ một dòng | **Postgres** (khoá chính) |
| Không xoá mẫu đang được dịch vụ dùng | **Postgres** (`ON DELETE RESTRICT`) |
| Không gắn cho dịch vụ không có trong bảng giá | **Lệnh** |
| Gắn/gỡ cần quyền | **Lệnh** (`doi_quyen`, trong cùng giao dịch) |

## 6. Hotspot — chưa chốt

1. **Máy KHÔNG tự gắn mẫu.** Tờ giấy chỉ có tên ("SÂ tuyến vú"), bảng giá dùng mã
   KiotViet. Đoán mã từ tên là gắn nhầm mẫu kết quả cho bệnh nhân. `/de-xuat` chỉ
   gợi ý, người xác nhận từng dòng. **Ai ngồi xác nhận 28 liên kết ấy?**
2. **Nội dung từng mẫu chưa số hoá.** Mới có tên và nhóm. Trường nào trong mẫu
   siêu âm tuyến vú là việc của Form Engine, một lát riêng.
3. **Một dịch vụ nhiều mẫu** (siêu âm thai theo quý) — hiện trả danh sách để bác
   sĩ chọn. Có nên chọn sẵn theo tuổi thai không?

## 7. Time source
Không có.

## 8. Given / When / Then

```text
G1  18 mẫu của phòng khám có sẵn sau migration
G2  Migration KHÔNG tự gắn mẫu cho dịch vụ nào
G3  Quản lý gắn được, bác sĩ đọc được ngay
G4  Gắn lại lần hai không nhân đôi dòng
G5  Bác sĩ KHÔNG gắn được (đọc thì được)
G6  Gắn cho mã dịch vụ không có thật → bị chặn
G7  Gắn mẫu không có thật → Postgres chặn
G8  Gọi /de-xuat KHÔNG tạo dòng gắn nào
```

## Phụ lục — đã làm gì

| Thứ | Ở đâu |
|---|---|
| Hai bảng + seed 18 mẫu + quyền mới | `supabase/migrations/20260923000004_mau_ket_qua.sql` |
| Lệnh + đề xuất | `src/clinicai/services/mau_ket_qua_service.py` |
| Endpoint | `src/clinicai/api/v1/routers/mau_ket_qua.py` |
| Quyền `catalogue.result_template.manage`, khối "Danh mục & biểu mẫu" | `src/clinicai/permissions/catalogue.py` |
| Test | `src/tests/services/test_mau_ket_qua_db.py` |

**18 mẫu:** SA ổ bụng · SA tuyến vú · SA tuyến giáp · SA ĐM cảnh · SA ĐM thận ·
SA Doppler âm vật · SA tinh hoàn · SA tử cung-buồng trứng · SA tử cung-phần phụ ·
SA thai sớm · SA thai quý I · SA thai quý II-III · SA song thai quý I ·
SA song thai quý II-III · Soi âm hộ · XN HPV Genotype · XN PCR 13 tác nhân ·
XN tổng quát (TrueMedicine).
