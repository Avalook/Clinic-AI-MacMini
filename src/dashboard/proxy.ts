// Next 16 proxy (renamed from `middleware`). MỘT cổng duy nhất:
//   không có phiên, hoặc phiên chưa gắn nhân viên đang làm việc → /login.
// clinic_role is a legacy compatibility cookie; it is never read here.
// API routes enforce their own auth and are never redirected to HTML pages.

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { laRouteDaTat } from "./lib/route-da-tat";
import { SUPABASE_COOKIE_NAME } from "./lib/supabase-cookie";

const PUBLIC_PATHS = ["/login", "/auth", "/forgot-password", "/reset-password"];

// The living style guide holds no patient data and must not look like it needs
// a clinical session. The page itself 404s outside development, so this entry
// opens nothing in production.
if (process.env.NODE_ENV === "development") PUBLIC_PATHS.push("/design-system");

export async function proxy(request: NextRequest) {
  // Route cũ đã tắt (lib/route-da-tat.ts) — trả 410, không đụng tới phiên.
  if (laRouteDaTat(request.nextUrl.pathname)) {
    return NextResponse.json(
      { error: "ENDPOINT_RETIRED", message: "Đường cũ đã tắt — màn hiện tại không dùng nữa." },
      { status: 410 },
    );
  }

  let response = NextResponse.next({ request });

  // ĐỊA CHỈ NỘI BỘ TRƯỚC. Proxy này chạy TRONG container và gọi Supabase cho
  // MỌI request. `NEXT_PUBLIC_SUPABASE_URL` là địa chỉ dành cho TRÌNH DUYỆT —
  // từ trong container nó phải đi vòng ra IP công cộng rồi quay lại.
  //
  // Prod sống sót vì địa chỉ công cộng của nó ở cổng 80, và cổng 80 đi vòng
  // được. Staging ở cổng 8080 thì KHÔNG: đo ngày 07/08/2026, từ trong container
  // gọi IP:80 OK còn IP:8080 hết giờ chờ. Hậu quả là mọi request trên staging
  // đều không kiểm được phiên → đá về /login → không ai đăng nhập được, mà
  // trang đăng nhập vẫn hiện ra bình thường nên trông như gõ sai mật khẩu.
  //
  // Cùng thứ tự với `lib/supabase-server.ts`. Prod đang đúng nhờ may, không
  // nhờ thiết kế — một luật tường lửa là nó hỏng y như staging.
  const supabase = createServerClient(
    process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL!,
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
  const { data: staff, error: loiTra } = await supabase
    .from("staff")
    .select("id")
    .eq("auth_user_id", user.id)
    .eq("is_active", true)
    .maybeSingle();
  // TRA HỎNG ≠ KHÔNG PHẢI NHÂN VIÊN (kiểm toán 27/09/2026): DB / PostgREST
  // chậm một nhịp (lúc deploy, lúc DB treo) thì `data` rỗng kèm `error` — trước
  // đây cũng bị đá về /login giữa ca dù phiên vẫn còn. Tra hỏng thì cho đi tiếp:
  // layout và mọi API vẫn tự kiểm danh tính, không có gì mở thêm.
  if (!staff && !loiTra) return redirectTo("/login");

  return response;
}

export const config = {
  // Skip Next internals + static assets. Everything else passes through.
  matcher: [
    // HAI ĐƯỜNG TẢI TỆP ĐI THẲNG, KHÔNG QUA proxy (tự kiểm 16/09/2026).
    // Proxy chép thân yêu cầu vào RAM và CẮT ở 10MB — mọi video siêu âm, phiếu
    // PDF lớn tải lên đều hỏng với câu "không kết nối được máy chủ". Nâng trần
    // `proxyClientMaxBodySize` thì vài video 80MB cùng lúc là tràn bộ nhớ
    // dashboard. Hai route này tự xác thực người gọi (getCallerAuthHeaders);
    // với /api proxy chỉ làm mới cookie, không gác cửa.
    // `manifest.webmanifest` (PWA, 27/09/2026): điện thoại đọc nó TRƯỚC khi
    // đăng nhập để cài app — qua proxy thì bị đẩy về /login, cài không được.
    "/((?!_next/static|_next/image|favicon.ico|manifest.webmanifest|api/cskh/ket-qua$|api/doi-tac$|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
