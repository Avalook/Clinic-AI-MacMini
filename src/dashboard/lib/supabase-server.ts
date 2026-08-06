// Server-side Supabase client (server components, route handlers, middleware).
// Uses ANON key + the request/response cookies for session refresh.

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

export async function getSupabaseServer() {
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
}
