// Server-side Supabase client (server components, route handlers, middleware).
// Uses ANON key + the request/response cookies for session refresh.

import { cache } from "react";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { SUPABASE_COOKIE_NAME } from "./supabase-cookie";

// Địa chỉ Supabase cho phía SERVER. Khác địa chỉ trình duyệt dùng.
//
// Cùng một biến NEXT_PUBLIC_SUPABASE_URL không phục vụ được cả hai vị trí mạng:
// trong container, 127.0.0.1 là chính container đó, nên server action đăng nhập
// chết với ECONNREFUSED; còn host.docker.internal thì trình duyệt không phân
// giải nổi. Sửa một đầu là hỏng đầu kia — đã xảy ra đúng như vậy.
//
// SUPABASE_URL là địa chỉ container tới được; NEXT_PUBLIC_SUPABASE_URL là địa
// chỉ trình duyệt tới được. Chạy ngoài container thì hai cái trùng nhau nên
// fallback vẫn đúng.
const SERVER_SUPABASE_URL =
  process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL!;

// `cache()` = MỘT client cho cả lượt dựng trang. Layout, page và các server
// component con đều gọi hàm này; không gói thì mỗi nơi tự dựng một client và
// tự xác minh phiên riêng — đo trên staging 21/08/2026: một lần mở /home chạy
// lại chuỗi users/sessions/mfa của gotrue nhiều lần cho CÙNG một người. Trong
// route handler không có kho theo-request thì cache() tự thành gọi thẳng, mỗi
// request vẫn xác minh riêng — đúng như phải thế. Cùng mẫu getBookingPolicy
// và getFeatureMode đã dùng.
export const getSupabaseServer = cache(async () => {
  const cookieStore = await cookies();
  return createServerClient(
    SERVER_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      // Máy chủ và trình duyệt dùng hai URL khác nhau; không ghim tên thì mỗi
      // bên đọc một cookie khác. Xem `lib/supabase-cookie.ts`.
      cookieOptions: { name: SUPABASE_COOKIE_NAME },
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Called from a Server Component — cookies can't be set here, ignore.
            // Middleware handles the refresh write path.
          }
        },
      },
    },
  );
});
