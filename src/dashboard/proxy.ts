// Next 16 proxy (renamed from `middleware`). One gate:
//   No Supabase session, or a session with no active linked staff → /login.
//
// There used to be a stage in front of that: /enter, a single shared Supabase
// account per deployment (CLINIC_SHARED_EMAIL). It was removed because one env
// var meant one clinic — the opposite of a pooled multi-tenant product — and
// because it had already stopped protecting anything: ADR-0004 gave that
// account no staff row, so tenant-scoped RLS let it read zero rows. What was
// left was a password every person in the building shared, in front of the
// login that actually decides who they are.
//
// clinic_role is a legacy compatibility cookie; it is never read here.
// API routes enforce their own auth and are never redirected to HTML pages.

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

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

  // Luồng: /login (đăng nhập cá nhân) → phần việc.

  // 1. Chưa đăng nhập.
  if (!user) {
    return isPublic ? response : redirectTo("/login");
  }

  // 2. Có phiên nhưng CHƯA gắn với nhân viên nào → /login nói lý do.
  if (!hasStaffIdentity && !isPublic) {
    return redirectTo("/login");
  }

  // 3. Đã đăng nhập mà còn ở /login → vào việc. /home đi qua layout, nên ai làm
  // nhiều phòng khám sẽ được hỏi nơi trực ở đó chứ không phải ở đây.
  if (hasStaffIdentity && pathname === "/login") {
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
