# Kế hoạch (MỨC 3 — chờ Tuyền duyệt): tính sức chứa MỘT lần cho mỗi cặp (bác sĩ, giờ)

16/10/2026 · gốc: PR #481 (`claude/giam-cham-trang-chu-quan-ly-khach`) đo được đây là nút cổ chai chung của
Quản lý khách hàng, Trang chủ và Tiếp đón.

## Vấn đề
`public.lich_vuot_suc_chua()` (migration `20260915000014_suc_chua_online_truc_tiep.sql`) không nhận tham số. Nó đi qua
**mọi lịch tương lai** có bác sĩ và gọi `resolve_effective_cap(clinic, bác sĩ, giờ)` cho TỪNG lịch.
Trên DB thử: 1.730 lịch → ~210 ms mỗi lần gọi, trong khi chỉ có **154 cặp (bác sĩ, giờ) khác nhau**.
Hàm nằm trong view `v_viec_cskh` nên mỗi lần mở Quản lý khách / Trang chủ / Tiếp đón là 1–3 lần gọi.

## Cách sửa (một migration, không đổi dữ liệu, không đổi chữ ký)
- `CREATE OR REPLACE FUNCTION public.lich_vuot_suc_chua()`: GIỮ NGUYÊN chữ ký, cột trả về, `STABLE`, `SECURITY INVOKER`,
  `search_path`. Chỉ đổi thân: tính cap một lần cho mỗi cặp bằng CTE `MATERIALIZED` (không có `MATERIALIZED` thì planner nhúng
  CTE và vẫn gọi 1.730 lần), rồi nối lại vào từng lịch.
- Không đụng view `v_viec_cskh`, bảng, quyền, dữ liệu.

## Kết quả mong đợi (đo local, 9.000 khách / 36.000 lịch)
| Điểm | Hiện tại | Sau |
|---|---|---|
| `GET /cskh/man-khach-hang` | 235 ms | ~45 ms |
| Trang chủ (`bang-dieu-khien`) | 600 ms | ~205 ms |
| Tiếp đón (phần backend) | 273 ms | ~68 ms |

## Kiểm chứng trước khi lên
1. Test DB so kết quả hàm mới với hàm cũ (đổi tên bản cũ trong DB thử) bằng `EXCEPT` hai chiều = 0 trên dữ liệu có nhiều cặp,
   gồm lịch cùng giờ nhiều khách, nhiều bác sĩ, lịch ngày lễ/nghỉ, `WALK_IN`, trạng thái đã huỷ/check-in.
2. Test unit cho đầu vào rác (lịch không bác sĩ, `slot_start` NULL).
3. `ci-may` một lần; staging áp migration và đo lại bằng log API (`top_route_cham`).

## Rủi ro và hoàn tác
- Rủi ro: nếu thân hàm mới lệch ý nghĩa thì việc CSKH "Lịch vượt sức chứa" và lịch tuần hiện sai. Giảm bằng test so sánh ở trên.
- Hoàn tác: migration đảo (`CREATE OR REPLACE` lại thân cũ), không mất dữ liệu, áp tức thì.
- Áp lên prod: một câu `CREATE OR REPLACE FUNCTION`, không khoá bảng, không cần dừng dịch vụ; vẫn theo quy trình sao lưu →
  diễn tập → áp (skill `len-prod`).

## Không làm trong kế hoạch này
- `danh_sach_khach` (tính "hoạt động gần nhất" cho mọi khách trước khi sắp xếp, ~84 ms ở 9.000 khách và tăng theo số khách):
  cần thêm cột/keyset — kế hoạch riêng sau.
- Gom N+1 quầy thu: mức 3 riêng, chờ duyệt.

## Cần Tuyền quyết
1. Duyệt làm (có/không).
2. Lên cùng đợt prod này hay đợt sau (đề xuất: cùng đợt, vì giảm tải lúc đông người và đo được ngay).
