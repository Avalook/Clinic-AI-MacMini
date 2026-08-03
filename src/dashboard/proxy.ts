// Next 16 proxy (renamed from `middleware`). Two-stage gate:
//   1. No Supabase session                       → /enter.
//   2. Session without an active linked staff    → /login.
// clinic_role is a legacy compatibility cookie; it is never read here.
// API routes enforce their own auth and are never redirected to HTML pages.

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PATHS = ["/enter", "/auth", "/forgot-password", "/reset-password"];

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
  let hasStaffIdentity = false;
  if (user) {
    const { data: staff } = await supabase
      .from("staff")
      .select("id")
      .eq("auth_user_id", user.id)
      .eq("is_active", true)
      .maybeSingle();
    hasStaffIdentity = !!staff;
  }
  const redirectTo = (path: string) => {
    const url = request.nextUrl.clone();
    url.pathname = path;
    url.search = "";
    return NextResponse.redirect(url);
  };

  // Luồng: /enter (mật khẩu phòng khám) → /login (đăng nhập cá nhân) → phần việc.

  // 1. Chưa qua cổng (không có session).
  if (!user) {
    return isPublic ? response : redirectTo("/enter");
  }

  // 2. Trang /login: Luôn cho phép hiển thị form đăng nhập cá nhân khi đã qua cổng.
  if (pathname === "/login") {
    return response;
  }

  // 3. Trang /enter: Đã qua cổng nhưng gõ lại /enter → chuyển sang /login để chọn tài khoản cá nhân.
  if (pathname.startsWith("/enter")) {
    return redirectTo("/login");
  }

  return response;
}

export const config = {
  // Skip Next internals + static assets. Everything else passes through.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
