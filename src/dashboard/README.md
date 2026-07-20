This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

---

# Quản lý tài khoản đăng nhập (Account Management)

Dashboard tự quản lý đăng nhập/đăng ký tài khoản **ngay trong app**, dựa trên
**Supabase Auth** (KHÔNG thay thế bằng auth tự viết — RLS các bảng PII đang dựa
trên `auth.uid()` của Supabase). Mỗi tài khoản login = 1 Supabase Auth user, link
1-1 với 1 dòng `staff` qua cột `staff.auth_user_id`.

## Phân quyền

| Vai trò (`staff.primary_department`) | Thấy gì |
|---|---|
| `MANAGEMENT` (Quản lý) | Toàn bộ + **Cài đặt** + **Báo cáo**. Chỉ vai trò này tạo/sửa tài khoản. |
| `DOCTOR` / `ULTRASOUND_DOCTOR` | Landing `/appointments?scope=me` (lịch của mình) |
| `CSKH` | Landing `/tasks` |
| Khác | Landing `/home` |

Cổng auth ở `proxy.ts` (Next 16 — **không** có `middleware.ts`). Vào `(dashboard)/*`
mà chưa đăng nhập → redirect `/login`. Đăng nhập rồi → `proxy.ts` điều hướng theo
vai trò. Map user → staff → vai trò ở `lib/current-staff.ts`.

## Cấu hình bắt buộc (1 lần)

### 1. Biến môi trường

`src/dashboard/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
# Bắt buộc để tạo/sửa tài khoản trong app (F3). KHÔNG có prefix NEXT_PUBLIC_
# (server-only — KHÔNG bao giờ lọt ra client). Lấy từ:
# Supabase console → Settings → API → Project API keys → service_role (secret).
SUPABASE_SERVICE_ROLE_KEY=<service_role key>
```

> ⚠️ `SUPABASE_SERVICE_ROLE_KEY` đặt ở **đây** (env của dashboard), KHÔNG phải `.env`
> gốc (đó là env của backend Python). Thiếu key → `/api/admin/users` trả 503 và
> trang `/settings/new-user` hiện cảnh báo vàng.
> Đổi `.env.local` phải **restart `npm run dev`** mới nạp.

### 2. Bootstrap admin đầu tiên (con-gà-quả-trứng)

Seed staff từ Notion sinh **0 dòng `MANAGEMENT`** → ban đầu chưa ai vào được khu
admin. Admin **đầu tiên** phải tạo qua console + CLI; sau đó mọi tài khoản khác
tạo được ngay trong dashboard.

```bash
# (a) Tạo dòng staff MANAGEMENT "Quản trị hệ thống" (idempotent):
#     apply seed src/migrations/seed/008_management_admin.sql
#     (giống cách apply các seed 005/006/007)

# (b) Supabase console → Authentication → Users → Add user
#     → nhập email + mật khẩu, tick "Auto-confirm" → copy UUID.

# (c) Link UUID vào dòng staff vừa tạo (chạy ở repo root):
poetry run python scripts/seed/link_staff_to_auth.py --map "Quản trị hệ thống=<uuid>"
```

> Muốn dùng chính bạn làm admin thay vì dòng generic, bỏ qua (a) và promote 1
> staff sẵn có: `UPDATE staff SET primary_department='MANAGEMENT' WHERE full_name='<tên>';`
> rồi link UUID vào dòng đó.

Restart dashboard → login bằng admin đó → menu **Cài đặt** xuất hiện.

## Dùng hằng ngày (admin) — tại `/settings`

- **Bảng nhân viên**: vai trò, hợp đồng, active, trạng thái login (🟢 đã link / 🟡 chưa).
- **+ Thêm tài khoản** (`/settings/new-user`): chọn NV chưa link → nhập email +
  mật khẩu tạm → tạo Auth user (auto-confirm) + link. NV tự đổi mật khẩu sau
  (link "Quên mật khẩu?" ở trang login).
- **Mỗi dòng đã link** có nút:
  - **Đặt lại mật khẩu** — đặt mật khẩu mới (≥ 8 ký tự) cho NV.
  - **Gỡ tài khoản** — xoá hẳn Auth user (thu hồi đăng nhập), **giữ** dòng staff
    → tạo lại login sau được. Cần xác nhận 2 bước.

NV tự phục vụ: **Quên mật khẩu** (`/forgot-password` → email → `/reset-password`).
Phòng khám **không** mở đăng ký công khai — tài khoản chỉ do admin tạo.

## API nội bộ — `POST|PATCH /api/admin/users`

Mọi method đều kiểm tra caller là `MANAGEMENT`, dùng service-role client server-side.

| Method | Body | Tác dụng |
|---|---|---|
| `POST` | `{ email, password, staffId }` | Tạo Auth user + link staff (báo lỗi nếu staff đã link) |
| `PATCH` | `{ staffId, action: "reset_password", password }` | Đặt lại mật khẩu |
| `PATCH` | `{ staffId, action: "unlink" }` | Null FK + xoá Auth user (giữ staff) |

Lỗi: `401` chưa đăng nhập · `403` không phải MANAGEMENT · `503` thiếu service key.
