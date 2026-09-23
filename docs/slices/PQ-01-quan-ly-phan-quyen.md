# PQ-01 — Quản lý phân quyền cho nhân sự

> Lát theo khuôn 8 mục. Ví dụ: **quản lý cho điều dưỡng Hương được chỉ định dịch vụ**,
> hoặc cho chị ấy thu tiền hộ đúng ca chiều.

| | |
|---|---|
| **Mã** | PQ-01 |
| **Module chủ** | `permission` |
| **Trạng thái** | ĐÃ CODE 23/09 — backend + test; màn hình chưa làm |
| **Ngày** | 23/09/2026 |

---

## 0. Mô hình — vì sao không phải "vai"

Năm lớp, chốt trong chat (#124, #132, #133, #134):

```
TÀI KHOẢN            Hương là Hương. Tài khoản KHÔNG mang quyền.
  └ THUỘC PHÒNG KHÁM làm ở phòng khám nào
      └ PRESET (vai)  gói mẫu để cấp cho nhanh — KHÔNG phải hàng rào
          └ CA/VỊ TRÍ đứng phòng SA hôm nay ≠ có mọi quyền siêu âm
              └ CAPABILITY + PHẠM VI ← quyền THẬT nằm ở đây
```

Lệnh hỏi `can(identity, "clinical.order.place")`, **không bao giờ** hỏi
`if role in {DOCTOR, TKYK}`. Đó là lý do "cho điều dưỡng điều phối khách" từ
chỗ phải sửa năm cửa code thành một ô tick của quản lý.

**Quản lý chỉnh được cao nhất:** ai có `permission.manage` cấp và thu được **mọi
khối** cho bất kỳ ai trong phòng khám, kể cả khối không nằm trong preset vai họ.

---

## 1. Trigger

| | |
|---|---|
| **Màn** | `/phan-quyen` — danh sách người bên trái, khối công việc bên phải |
| **Vai** | bất kỳ ai có `permission.manage` — mặc định quản lý, nhưng cấp cho người khác được |
| **Nút** | công tắc từng **khối**: Tiếp đón · Sinh hiệu · Chỉ định dịch vụ · Khách chọn dịch vụ · Điều phối khách · Thu tiền dịch vụ · Phân quyền. `[+ Thêm preset Điều dưỡng]` để cấp nhanh một nhóm |

Quản lý **không** tick từng quyền lắt nhắt (Tuyền #133). "▾ Chi tiết" mới bung quyền con.

## 2. Command

```text
GrantWorkPack    POST /phan-quyen/nhan-su/{staff_id}/cap
RevokeWorkPack   POST /phan-quyen/nhan-su/{staff_id}/thu
ApplyRolePreset  POST /phan-quyen/nhan-su/{staff_id}/them-preset
```

`cap` nhận `khoi`, `scope_type` (CLINIC · ROOM · SHIFT), `scope_id`, `valid_until`, `ly_do`.

**Từ chối khi:** người bấm không có `permission.manage` · người nhận không thuộc
phòng khám ấy · phạm vi hẹp mà không nói rõ hẹp ở đâu · khối chứa quyền cần
chứng chỉ hành nghề mà người nhận không có vai lâm sàng.

## 3. Events

| Sự kiện | Khi nào | Công khai? |
|---|---|---|
| `capability.granted` | có ít nhất một quyền THẬT SỰ được thêm | không |
| `capability.revoked` | có ít nhất một quyền bị đóng | không |

Cấp lại đúng thứ đã có thì **không phát sự kiện** — không có gì xảy ra thì không có gì để kể.

## 4. Views

| Bên đọc | Dùng để |
|---|---|
| `GET /phan-quyen/toi` | màn hình vẽ thanh bên, ẩn nút |
| `GET /phan-quyen/nhan-su/{id}` | màn quản lý hiện người này đang có khối nào |
| view `v_quyen_hieu_luc` | nguồn duy nhất trả lời "ai làm được gì, lúc này" |

**Ẩn nút không phải bảo mật.** Lệnh luôn kiểm lại bằng `doi_quyen`.

## 5. Constraint — ép ở đâu

| Luật | Ép ở đâu |
|---|---|
| Một người + một quyền + một phạm vi chỉ có một dòng còn sống | **Postgres** (chỉ mục duy nhất một phần) |
| Cấp một quyền không tồn tại là hỏng ngay lúc ghi | **Postgres** (khoá ngoại tới `capability`) |
| Phạm vi hẹp phải có `scope_id`, toàn phòng khám thì không | **Postgres** (CHECK) |
| Thu quyền không xoá dòng cũ | **Postgres** (CHECK `revoked_at`/`revoked_by` đi cặp) |
| Danh mục trong code = danh mục trong DB | **CI** (`test_danh_muc_quyen_db.py`) |
| Người bấm phải có `permission.manage` | **Lệnh**, trong cùng giao dịch |

## 6. Hotspot — chưa chốt

1. **Chứng chỉ hành nghề lấy gì làm bằng chứng?** Hiện tạm dùng vai
   DOCTOR/ULTRASOUND_DOCTOR. Phòng khám phải chốt (số chứng chỉ? phạm vi hành nghề?).
2. **Ai được giữ `permission.manage`?** Hiện chỉ preset MANAGEMENT có. Có cho
   trưởng ca không?
3. **Quyền theo ca** (`SHIFT`) đã có cột nhưng chưa nối với lịch trực thật.

## 7. Time source

Có: `valid_until`. Quyền cấp tạm hết hạn tự mất hiệu lực — view lọc theo thời
gian, không cần ai đi tắt.

## 8. Given / When / Then

```text
G1  Given điều dưỡng mới, chưa ai cấp khối Chỉ định
    When  gọi lệnh chỉ định
    Then  bị chặn — vai "nghe có vẻ đúng" không đủ

G2  Given quản lý bật khối "Chỉ định dịch vụ" cho điều dưỡng ấy
    When  điều dưỡng chỉ định
    Then  thành công, KHÔNG sửa một dòng code nào

G3  Given thu ngân (preset không có Sinh hiệu)
    When  quản lý bật khối Sinh hiệu cho họ
    Then  thành công — preset chỉ là gợi ý, không phải trần

G4  Given đã cấp rồi
    When  quản lý thu khối
    Then  mất quyền, nhưng dòng cũ còn nguyên (ai cấp, ai thu, lúc nào, vì sao)

G5  Given bác sĩ không có permission.manage
    When  bác sĩ cấp quyền cho người khác
    Then  bị chặn

G6  Given người thuộc phòng khám khác
    When  quản lý cấp quyền cho họ
    Then  bị chặn

G7  Given cấp hai lần cùng một khối
    Then  chỉ một dòng, và lần hai KHÔNG phát sự kiện
```

## Màn hình (23/09)

Chọn người → mỗi khối một dòng, một nút **"Bật khối này" / "Đang bật — tắt"**.
`[+ Thêm preset <vai>]` cấp nhanh cả nhóm khối theo vai. `▾ Chi tiết` bung quyền
con, kèm mức rủi ro (vận hành · đụng tiền · lâm sàng · quản trị) và dấu "cần
chứng chỉ hành nghề".

Màn nói rõ **"Vai chỉ là gợi ý, không phải giới hạn"** — vì đó chính là chỗ người
dùng dễ hiểu nhầm nhất khi nhìn thấy chữ "vai" cạnh tên người.

Vào được màn (chỉ Quản lý thấy trong thanh bên) **không có nghĩa là cấp được**:
backend đòi capability `permission.manage` ở từng lệnh. Ẩn nút không phải bảo mật.

## Phụ lục — đã làm gì

| Thứ | Ở đâu |
|---|---|
| Danh mục khối/quyền/preset | `src/clinicai/permissions/catalogue.py` |
| `can` / `doi_quyen` / `quyen_hieu_luc` | `src/clinicai/permissions/can.py` |
| Lệnh cấp, thu, thêm preset | `src/clinicai/services/permission_service.py` |
| Cấp preset khi thêm nhân sự (cùng giao dịch) | `services/staff_service.py` |
| Endpoint | `src/clinicai/api/v1/routers/phan_quyen.py` |
| Bảng + view + chép quyền cho người đang làm | `supabase/migrations/20260923000003_capability.sql` |
| Test | `src/tests/services/test_permission_db.py`, `test_danh_muc_quyen_db.py` |
| Màn hình | `app/(dashboard)/phan-quyen/page.tsx` + `BangPhanQuyen.tsx`, proxy `app/api/phan-quyen/route.ts` |

**Đã chuyển:** lệnh CD-01 (chỉ định dịch vụ) không còn kiểm vai, chuyển sang
`clinical.order.place`.

**Chưa chuyển:** các cửa còn lại vẫn kiểm theo vai. Chuyển dần theo từng lát;
mỗi lát chuyển một khối, không chuyển ồ ạt.

## Nhóm quyền mẫu — quản lý tự thêm, sửa, xoá (23/09 chiều)

Tuyền: *"quản lý quyền cao nhất, thay đổi các nút và vai trò, mặc định các nút ở
đó có thể thêm sửa xoá được"*.

Trước hôm nay, "preset của vai" là hằng số trong `permissions/catalogue.py`:
phòng khám muốn thêm nhóm "Điều dưỡng ca tối" thì phải chờ lập trình viên. Giờ
nó là **dữ liệu** (`quyen_preset`), và tab "Nhóm quyền mẫu" trong `/phan-quyen`
là chỗ sửa.

Ba lằn ranh, mỗi cái có một bài kiểm giữ:

1. **Nhóm KHÔNG phải quyền.** Quyền thật vẫn ở từng dòng `capability_grant` của
   từng người. Nhóm chỉ là "bấm một cái cấp cả loạt".
2. **Sửa nhóm không đổi quyền người đã cấp.** Nếu nó đổi được, một lần sửa nhóm
   là một lần âm thầm đổi quyền của mười người — mà không ai bấm nút nào.
3. **Nhóm dựng sẵn tắt chứ không xoá cứng.** Người cũ còn phải tra được "hồi ấy
   cấp theo nhóm nào".

Hằng số `PRESET` trong mã còn lại làm **lưới an toàn** cho phòng khám chưa chạy
migration, và có một bài kiểm giữ cho hai bên không lệch.
