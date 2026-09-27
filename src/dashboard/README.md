# Dashboard ClinicAI (Next.js)

Giao diện của ClinicAI. **Chỉ là giao diện**: mọi luật nghiệp vụ nằm ở FastAPI
(`src/clinicai`) hoặc SQL. Route trong `app/api/*` chỉ chuyển tiếp sang FastAPI;
dashboard chỉ nói chuyện thẳng với Supabase (bộ **tự dựng**, không phải cloud) cho
đăng nhập và tin thời gian thực. Luật chung: `CLAUDE.md` và `DESIGN.md` ở gốc repo.

Next.js ở đây là bản mới có thay đổi phá vỡ — đọc `AGENTS.md` trong thư mục này
trước khi viết code. Không có `middleware.ts`: cổng đăng nhập ở `proxy.ts`.

## Chạy trên máy dev

Cách chuẩn là dựng cả stack từ gốc repo: `scripts/dev-up.sh` (Supabase tự dựng +
api + dashboard, tự kiểm, in tài khoản thử). Chỉ sửa giao diện thì:

```bash
npm run dev                                   # http://localhost:3000
./node_modules/.bin/tsc --noEmit
npm run lint -- --max-warnings=0
npm run test:boundary                         # các bài kiểm ranh giới (tests/*boundary.test.mts)
```

Dùng công cụ trong `node_modules/.bin`, **không** `npx` gói ngoài dự án.
Build image prod: `Dockerfile.dashboard`, gọi qua `docker compose` trong
`scripts/deploy-backend.sh` trên VPS — không có Vercel.

## Biến môi trường

`src/dashboard/.env.local` (máy dev; `scripts/dev-up.sh` tự điền):

```
NEXT_PUBLIC_SUPABASE_URL=<địa chỉ gateway Supabase tự dựng mà TRÌNH DUYỆT gọi>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
# Chỉ phía máy chủ, KHÔNG có prefix NEXT_PUBLIC_. Cần cho /api/admin/users.
SUPABASE_SERVICE_ROLE_KEY=<service_role key>
```

Khoá do `scripts/sinh-khoa-supabase.py` sinh. Trên prod, giá trị nằm trong
`.env.prod` ở VPS và được truyền lúc build (xem `docker-compose.yml`, service
`dashboard`). Thiếu `SUPABASE_SERVICE_ROLE_KEY` → `/api/admin/users` trả 503.

## Quyền và điều hướng

Quyền theo **lego** (21 khối theo node thanh bên, gán theo tài khoản) — danh mục ở
`src/clinicai/permissions/catalogue.py`, màn `/phan-quyen`. Route nào là màn chuẩn,
mọi lối vào của một chức năng: `docs/SITEMAP.md`. Map user → staff ở
`lib/current-staff.ts`.

## Tài khoản đăng nhập

Mỗi tài khoản = 1 user GoTrue (Supabase tự dựng), gắn 1-1 với một dòng `staff`
qua `staff.auth_user_id`. Không có đăng ký công khai.

- **Cấp hàng loạt cho nhân sự:** `scripts/provision-staff-logins.sh` (mời qua
  email, người dùng tự đặt mật khẩu) hoặc `scripts/tao-tai-khoan-nhan-su.py`.
- **Trong app** (`/settings`, `/settings/new-user`): tạo tài khoản, đặt lại mật
  khẩu, gỡ tài khoản (giữ dòng staff).
- **Tự phục vụ:** `/forgot-password` → email → `/reset-password`.

### API nội bộ — `POST|PATCH /api/admin/users`

Kiểm quyền `account.manage` (lego), dùng service-role client phía máy chủ — đây
là một trong 2 file được phép giữ khoá service-role (`tests/service-role-boundary.test.mts`).

| Method | Body | Tác dụng |
|---|---|---|
| `GET` | — | `{ emails: { staffId: email } }` |
| `POST` | `{ email, password, staffId }` | Tạo user + gắn staff (báo lỗi nếu staff đã gắn) |
| `PATCH` | `{ staffId, action: "reset_password", password }` | Đặt lại mật khẩu |
| `PATCH` | `{ staffId, action: "change_email", email }` | Đổi tên đăng nhập |
| `PATCH` | `{ staffId, action: "unlink" }` | Bỏ gắn + xoá user (giữ staff) |

Nguồn sự thật là chú thích đầu `app/api/admin/users/route.ts`.

Lỗi: `401` chưa đăng nhập · `403` không có quyền · `503` thiếu service key.
