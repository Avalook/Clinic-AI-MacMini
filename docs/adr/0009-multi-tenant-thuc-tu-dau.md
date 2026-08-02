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
2. **`clinic_id NOT NULL`** trên **27 bảng**: mọi bảng nghiệp vụ (patient, appointment,
   visit, clinical_record, payment, work_roster, …) **và** mọi bảng danh mục/cấu hình
   riêng của phòng khám (`service_type`, `drug_catalog`, `service_price`,
   `block_budget`, `booking_channel`, `clinic_location`).
   **Không** mang `clinic_id`:
   - `province`, `ward` — danh mục hành chính quốc gia, dùng chung thật;
   - `staff`, `staff_capability` — một bác sĩ có thể làm ở nhiều phòng khám, nên tenant
     nằm ở `clinic_membership` chứ không phải một cột trên `staff`;
   - `idempotency_key`, `schema_migrations` — hạ tầng.

   *(Sửa so với bản nháp đầu: `service_type` và `drug_catalog` từng bị xếp nhầm vào nhóm
   dùng chung. Danh mục dịch vụ và danh mục thuốc là của từng phòng khám, không phải
   chuẩn quốc gia — nếu dùng chung thì tenant thứ 2 sẽ thấy bảng giá của tenant thứ 1.)*
3. **Tenant lấy từ JWT, không từ client**: backend suy `clinic_id` từ
   `auth.uid() → staff.auth_user_id → clinic_membership`. Không nhận `clinic_id` trong
   body/query của request người dùng.
   *(Làm rõ, 2026-08-02:* header `X-Clinic-ID` **không** phải ngoại lệ. Nó là **bộ
   chọn**, không phải thẩm quyền: `identity.py` giao nó với chính membership của
   `auth.uid()`, nên giá trị giả mạo chỉ có hai kết cục — trỏ vào phòng khám người
   đó vốn đã thuộc về, hoặc 403. Nó tồn tại vì người làm ở nhiều nơi cần *nói* họ
   đang trực ở đâu; suy ngầm chỉ đúng khi mỗi người có đúng một phòng khám, và bác
   sĩ chạy sô đầu tiên biến suy ngầm thành khoá tài khoản im lặng.*)*
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

## Trạng thái thực hiện
- **Xong (W2)** — `supabase/migrations/20260730000003_multi_tenant_foundation.sql`:
  `clinic` + `clinic_membership`, `clinic_id` trên 27 bảng, khoá duy nhất mang tenant,
  helper `current_staff_id()` / `current_clinic_ids()` / `current_clinic_roles()`.
  Kiểm bằng `supabase/tests/multi_tenant_foundation.sql` (chạy trong CI, job `database`).
- **Xong (W3)** — `20260730000004_tenant_scoped_rls.sql`: 26 policy `USING (true)`
  thay bằng `clinic_id IN (SELECT public.current_clinic_ids())`.
  Kiểm bằng `supabase/tests/tenant_scoped_rls.sql`.
- **Xong (W8) — quan trọng nhất:** RLS **không** bảo vệ được backend. Tiến trình
  FastAPI nối DB bằng chủ sở hữu database, nên policy ở trên không áp cho nó: một câu
  lệnh đọc rộng đúng bằng mệnh đề `WHERE` của chính nó. Vì vậy mọi câu lệnh trong
  `src/clinicai` chạm bảng có tenant đều phải tự lọc `clinic_id`. Đã đưa từ **71 → 0**;
  `scripts/tests/tenant-scope-audit.py --check` chạy trong CI với **ceiling = 0**, nên
  PR nào thêm một câu lệnh không lọc là CI đỏ. Ba relay quét mọi tenant *có chủ đích*
  (`pos_relay`, `notification_relay`, `event_service`) được liệt kê tường minh trong
  audit chứ không im lặng bỏ qua.
- **Kiểm lúc chạy:** `scripts/tests/tenant-scope-runtime-check.py` (cần
  `npx supabase start`) chạy thật từng câu lệnh đó và khẳng định phòng khám này không
  đọc được dữ liệu phòng khám kia. Audit chỉ đọc chữ; unit test thì mock pool — cả hai
  đều xanh với SQL mà Postgres sẽ từ chối.
- **✅ Đã gỡ default (migration `20260730000014`, 2026-07-30).** `DEFAULT
  public.default_clinic_id()` bị xoá khỏi **36 bảng**, và 45 chỗ
  `COALESCE($n, public.default_clinic_id())` trong query cũng biến mất. Cái mở đường
  cho việc này là sửa **kiểu dữ liệu**: `StaffIdentity.clinic_id` từ `str | None` thành
  `str`. `get_current_identity` vốn đã 403 khi không có membership, nên `None` là trường
  hợp **không thể xảy ra** — vậy mà mỗi query phía dưới vẫn phải mang một fallback cho
  nó. Khai báo đúng sự thật thì mypy chỉ thẳng ra 12 lối gọi nền chưa có tenant (graph,
  tool, orchestrator), sửa xong là fallback thành thừa.
- **Giờ quên tenant là hỏng ngay và hỏng giống nhau** dù có 1 hay 50 phòng khám. Trước
  đây trường hợp 1 phòng khám là ngoại lệ che lỗi cho tới ngày có phòng khám thứ 2 —
  đúng lúc lỗi đắt nhất.
- **Hàng con thừa kế tenant từ hàng cha:** `work_item_dependency` và `work_item_event`
  không có tenant riêng — cạnh thuộc về phòng khám sở hữu hai đầu, sự kiện thuộc về
  work item sinh ra nó. Trước đây chúng lấy từ column DEFAULT (nên bài test "event phải
  thừa kế tenant" thực chất chỉ đang kiểm tra default hoạt động). Nay có trigger **tra
  từ cha** — không phải đoán — và **từ chối** cạnh nối hai phòng khám khác nhau, thứ mà
  trước đây được nhận rồi âm thầm dán nhãn default.
- **Hàm `default_clinic_id()` vẫn còn**, chỉ còn `staff_ensure_default_membership` dùng,
  và hàm đó đã tự no-op khi có từ 2 phòng khám. Bỏ hẳn hàm sẽ phải viết lại trigger
  onboarding — việc khác, quyết định khác.
