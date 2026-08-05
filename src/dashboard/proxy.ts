// Next 16 proxy (renamed from `middleware`). MỘT cổng duy nhất:
//   không có phiên, hoặc phiên chưa gắn nhân viên đang làm việc → /login.
// clinic_role is a legacy compatibility cookie; it is never read here.
// API routes enforce their own auth and are never redirected to HTML pages.

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { SUPABASE_COOKIE_NAME } from "./lib/supabase-cookie";

const PUBLIC_PATHS = ["/login", "/auth", "/forgot-password", "/reset-password"];

// The living style guide holds no patient data and must not look like it needs
// a clinical session. The page itself 404s outside development, so this entry
// opens nothing in production.
if (process.env.NODE_ENV === "development") PUBLIC_PATHS.push("/design-system");

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookieOptions: { name: SUPABASE_COOKIE_NAME },
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;

  // API routes do their own authorization; just refresh the session cookie.
  if (pathname.startsWith("/api")) return response;

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  const redirectTo = (path: string) => {
    const url = request.nextUrl.clone();
    url.pathname = path;
    url.search = "";
    return NextResponse.redirect(url);
  };

  // Trang công khai (kể cả /login) đi thẳng — nếu chặn ở đây thì người chưa
  // đăng nhập bị đá vòng tròn về chính nó.
  if (isPublic) return response;

  // Cổng duy nhất: phải có phiên...
  if (!user) return redirectTo("/login");

  // ...VÀ phiên ấy phải gắn với một nhân viên đang làm việc. Trước đây truy vấn
  // này chạy rồi vứt kết quả đi, vì cổng phòng khám dùng chung mới là thứ chặn
  // ở vòng ngoài. Bỏ cổng ấy (05/08/2026) thì đây là chốt duy nhất còn lại, nên
  // nó phải thật sự chặn: một tài khoản Supabase không có dòng `staff` — tài
  // khoản dùng chung cũ, hay một tài khoản tự đăng ký — nay dừng ở /login thay
  // vì đi tiếp vào giao diện rồi mới rỗng dữ liệu ở từng màn.
  const { data: staff } = await supabase
    .from("staff")
    .select("id")
    .eq("auth_user_id", user.id)
    .eq("is_active", true)
    .maybeSingle();
  if (!staff) return redirectTo("/login");

  return response;
}

export const config = {
  // Skip Next internals + static assets. Everything else passes through.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
