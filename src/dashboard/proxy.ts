// Next 16 proxy (renamed from `middleware`). Two-stage gate:
//   1. No shared Supabase session  → /enter (clinic password).
//   2. Session but no role cookie   → /role-picker.
// API routes enforce their own auth and are never redirected to HTML pages.

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PATHS = ["/enter", "/auth", "/forgot-password", "/reset-password"];

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
  const hasRole = !!request.cookies.get("clinic_role")?.value;
  const redirectTo = (path: string) => {
    const url = request.nextUrl.clone();
    url.pathname = path;
    url.search = "";
    return NextResponse.redirect(url);
  };

  // Luồng: /enter (mật khẩu phòng khám) → /login (đăng nhập cá nhân) → phần việc.

  // 1. Chưa qua cổng (không có session). /login KHÔNG public → cũng đẩy về /enter.
  if (!user) {
    return isPublic ? response : redirectTo("/enter");
  }

  // 2. Đã qua cổng, đang ở trang /enter → đi tiếp.
  if (pathname.startsWith("/enter")) {
    return redirectTo(hasRole ? "/home" : "/login");
  }

  // 3. Đã qua cổng nhưng CHƯA đăng nhập cá nhân (chưa có role) → /login.
  if (!hasRole && pathname !== "/login" && !isPublic) {
    return redirectTo("/login");
  }

  // 4. Đã đăng nhập cá nhân mà còn ở /login → vào việc.
  if (hasRole && pathname === "/login") {
    return redirectTo("/home");
  }

  return response;
}

export const config = {
  // Skip Next internals + static assets. Everything else passes through.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
