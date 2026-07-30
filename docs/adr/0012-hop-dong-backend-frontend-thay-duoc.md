# ADR-0012 — Backend sở hữu hợp đồng: đổi/vứt frontend không ảnh hưởng backend

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-30 |
| **Deciders** | Quang — "code hoàn thiện backend đi để nếu đổi frontend như nào cũng không ảnh hưởng backend, hỏng hệ thống" |
| **Liên quan** | CLAUDE.md ("Frontend = UI only"), ADR-0004, ADR-0009, Phase 4 |

## Context
Mục tiêu: frontend là thứ thay được (đổi Next.js sang cái khác, thêm app mobile, thêm
màn cho phòng khám khác) mà backend không phải sửa và không thể bị làm hỏng.

Hiện trạng vi phạm mục tiêu này ở 2 chỗ:
1. **Dashboard đọc/ghi Supabase trực tiếp.** Ví dụ `/reports` đọc `booking_channel`,
   `/episodes` đọc `care_episode`, `app/api/*` dùng `getSupabaseService()` (service_role)
   — tức là frontend đang cầm quyền bỏ qua RLS. Bất kỳ frontend nào cũng có thể ghi sai
   dữ liệu mà backend không biết.
2. **Logic nghiệp vụ còn nằm trong `src/dashboard`** (Phase 4 chưa xong).

## Decision
1. **Hợp đồng = OpenAPI của FastAPI, có version (`/api/v1`).** Đây là mặt tiếp xúc duy
   nhất. Thay đổi phá vỡ hợp đồng ⇒ `/api/v2`, không sửa ngầm `v1`.
2. **Frontend chỉ được dùng Supabase trực tiếp cho `auth` và `realtime`** (đúng
   CLAUDE.md). Mọi đọc/ghi dữ liệu nghiệp vụ đi qua FastAPI.
3. **Service-role key rời khỏi frontend.** `getSupabaseService()` bị gỡ khỏi
   `src/dashboard`; `SUPABASE_SERVICE_ROLE_KEY` chỉ tồn tại trong env của `api`/`worker`.
4. **RLS siết đủ chặt để frontend không cần được tin.** Sau ADR-0009 + ADR-0004, một
   client cầm anon key + JWT hợp lệ chỉ đọc được đúng tenant của mình, và **không ghi
   được gì**. Đây là điều khiến "đổi frontend không hỏng hệ thống" thành đúng ở tầng DB
   chứ không phải lời hứa.
5. **Bất biến nghiệp vụ nằm ở DB + service layer**, không ở TSX: chống trùng slot, sức
   chứa, thứ tự gọi hàng đợi, gate của work item (ADR-0003, ADR-0011).
6. **Sinh client từ OpenAPI**, không viết tay type: frontend dùng type sinh tự động; CI
   fail nếu client lệch hợp đồng.
7. **Test hợp đồng chạy không cần frontend**: pytest gọi thẳng API; một frontend rỗng
   vẫn phải pass toàn bộ.

## Alternatives
| | Ưu | Nhược |
|---|---|---|
| **A. Backend sở hữu hợp đồng, FE thuần UI (chọn)** | FE thay được; bảo mật không phụ thuộc FE; test được không cần trình duyệt | phải gỡ toàn bộ đường đọc thẳng Supabase trong dashboard |
| B. Giữ Next.js BFF làm nơi chứa logic | ít việc trước mắt | đổi FE = mất logic; service_role nằm trong FE = FE bug là rò dữ liệu |
| C. Chỉ dùng Supabase (PostgREST) làm API | không phải viết backend | logic nghiệp vụ phức tạp (workflow, thanh toán) không diễn đạt được bằng RLS |

## Consequences
**Tích cực:** thêm app mobile / đổi framework = chỉ viết UI; kiểm thử và bảo mật không
phụ thuộc frontend; audit "ai làm gì" đầy đủ vì mọi ghi đều qua backend.
**Tiêu cực:** thêm một chặng mạng cho các màn đang đọc thẳng Supabase (chấp nhận được ở
tải hiện tại); phải viết endpoint cho mọi thứ frontend đang tự truy vấn.
**Kiểm chứng:** CI có test khẳng định `src/dashboard` không còn tham chiếu
`SUPABASE_SERVICE_ROLE_KEY`, và không `from("<bảng nghiệp vụ>")` ngoài auth/realtime.

## Trạng thái thực hiện (cập nhật 2026-07-30, W5 đợt 1)

**Đã gỡ service-role khỏi 3 chỗ** — nhờ policy thêm ở W1b/W3, không cần bypass RLS nữa:
`app/api/wards`, `app/api/patients/check-phone`, `app/(dashboard)/patients/new`.
Đọc `province`/`ward`/`patient` giờ đi bằng session của chính người gọi, nên còn được
lọc theo phòng khám thay vì thấy toàn hệ thống.

**Ranh giới đã có hàng rào, không còn là lời hứa.**
`src/dashboard/tests/service-role-boundary.test.mts` (chạy trong CI qua
`npm run test:boundary`) giữ một **danh sách trắng chỉ được ngắn đi**:
- thêm file mới đụng tới service-role ⇒ **CI đỏ**;
- để lại file đã hết dùng service-role trong danh sách ⇒ **CI cũng đỏ** (chống mục);
- trần cứng **19 file**, chỉ được hạ. W5 xong khi còn **2** (factory + route Auth-admin).

Test này còn tìm ra 3 chỗ mà `grep getSupabaseService` bỏ sót vì chúng tự tạo client
inline từ `SUPABASE_SERVICE_ROLE_KEY`: `api/roster`, `api/service-price`,
`settings/new-user`.

**Một vertical đã dời trọn sang FastAPI làm mẫu:** vòng đời `care_episode`.
`EpisodeService` + router `PATCH /api/v1/episodes/{id}`, gate vai trò bằng
`require_role(CSKH, MANAGEMENT, TRUONG_CA)` — khớp `canManageAppt` trong `roles.ts`, và
`require_role` nay trả về `RoleGuard` có `allowed_roles` đọc lại được nên test khẳng định
được cổng vai trò mà không cần dựng HTTP. Bản backend **chặt hơn** bản Next: đổi trạng
thái và ghi audit event nằm trong **cùng một transaction**, nên không thể có chuyện đóng
đợt khám mà thiếu event. Bật bằng `EPISODE_VIA_BACKEND=1`, mặc định tắt.

**Còn lại:** 14 route nghiệp vụ (đặt lịch/check-in, bệnh án, siêu âm, xét nghiệm, thu
tiền, service-log, sono, CSKH, roster, bảng giá). Mỗi entry trong danh sách trắng ghi rõ
nó phải về router nào.
