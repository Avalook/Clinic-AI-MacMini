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
