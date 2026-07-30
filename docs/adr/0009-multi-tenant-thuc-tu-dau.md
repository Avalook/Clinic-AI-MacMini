# ADR-0009 — Multi-tenant thật ngay từ bây giờ: `clinic` + `clinic_membership` + `clinic_id` mọi bảng nghiệp vụ

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-30 |
| **Deciders** | Quang — "multi-tenant là thật luôn, làm sản phẩm cuối từ giờ luôn chứ không giai đoạn dài dòng" |
| **Liên quan** | ADR-0004 (auth/RLS), ADR-0012 (hợp đồng backend), Design doc v5, `docs/ClinicAI-Tong-Quan-He-Thong.md` §3 |

## Context
Tài liệu §3 mô tả ClinicAI là sản phẩm nhiều phòng khám, Dr4Women là tenant #1. Nhưng
schema hiện tại **không có một cột `clinic_id` nào** (`grep -c clinic_id` trên baseline
= 0). `clinic_location` chỉ là *cơ sở/chi nhánh*, không phải *tenant*. Toàn bộ RLS đang
là `USING (true)` cho `authenticated`, nghĩa là nếu onboard phòng khám thứ 2 vào cùng
project thì mọi user đọc được dữ liệu của nhau.

Thêm tenant sau khi đã có dữ liệu thật = backfill 30+ bảng + viết lại toàn bộ policy +
sửa mọi query. Chi phí đó chỉ tăng theo thời gian.

## Decision
1. **Bảng gốc**: `clinic` (tenant) và `clinic_membership` (`staff_id × clinic_id × role`).
   `clinic_location` trở thành con của `clinic`.
2. **`clinic_id NOT NULL`** trên mọi bảng nghiệp vụ (patient, appointment, visit,
   clinical_record, payment, work_roster, …). Bảng tham chiếu dùng chung
   (`province`, `ward`, `service_type`, `drug_catalog`) **không** mang `clinic_id`;
   bảng cấu hình theo phòng khám (`service_price`, `block_budget`, `booking_channel`)
   **có** `clinic_id`.
3. **Tenant lấy từ JWT, không từ client**: backend suy `clinic_id` từ
   `auth.uid() → staff.auth_user_id → clinic_membership`. Không nhận `clinic_id` trong
   body/query của request người dùng.
4. **RLS theo tenant** thay cho `USING (true)`: mọi policy đọc đều kèm điều kiện
   `clinic_id IN (SELECT clinic_id FROM clinic_membership WHERE staff_id = current_staff())`.
   Ghi vẫn service_role-only (ADR-0004).
5. **Unique key mang tenant**: mọi ràng buộc duy nhất hiện có (mã bệnh nhân, mã dịch vụ,
   số thứ tự hàng đợi…) đổi thành `(clinic_id, …)`.
6. Dr4Women = một row `clinic` được seed; migration backfill toàn bộ dữ liệu hiện có về
   tenant đó trước khi đặt `NOT NULL`.

## Alternatives
| | Ưu | Nhược |
|---|---|---|
| **A. Tenant từ đầu (chọn)** | không phải backfill dữ liệu thật lần 2; RLS đúng ngay; bán được ngay | phải sửa 30+ bảng + mọi query ngay bây giờ |
| B. Sau pilot Dr4Women | ship pilot nhanh hơn vài tuần | backfill trên dữ liệu bệnh nhân thật + viết lại toàn bộ policy = rủi ro rò dữ liệu chéo |
| C. Mỗi phòng khám 1 Supabase project | cách ly tuyệt đối | chi phí × N, vận hành/migration × N, không báo cáo chéo được |

## Consequences
**Tích cực:** onboard phòng khám thứ 2 = insert 1 row + cấu hình, không sửa code; rò
dữ liệu chéo bị chặn ở tầng DB chứ không phụ thuộc code ứng dụng.
**Tiêu cực:** đợt migration lớn (backfill + đổi unique key + viết lại policy) phải làm
một lần, có downtime ngắn; mọi service function phải nhận `clinic_id` — cần sửa cả test.
**Rủi ro:** quên `clinic_id` ở một bảng = lỗ rò. Bù bằng test khẳng định: không bảng
nghiệp vụ nào thiếu `clinic_id`, và không policy nào còn `USING (true)`.
