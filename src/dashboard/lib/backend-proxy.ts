// backend-proxy — server→server forwarding from Next route handlers to FastAPI.
// backend-proxy — chuyển tiếp server→server từ Next route handlers đến FastAPI.
//
// Phase 4 (Cụm B/C): as business logic moves into FastAPI, a Next route becomes a
// thin proxy. Unlike the older brief/patients proxies, this forwards the caller's
// Supabase access token (Authorization: Bearer …) so the backend can verify
// identity → staff → role (server-authoritative, identity.py), in addition to the
// shared X-API-Key.
// Phase 4 (Cụm B/C): khi logic nghiệp vụ chuyển vào FastAPI, một route của Next trở thành
// proxy mỏng. Khác với các proxy brief/patients cũ, file này chuyển tiếp
// access token của Supabase (Authorization: Bearer …) để backend có thể xác minh
// danh tính → nhân viên → vai trò (server-authoritative, identity.py), ngoài
// X-API-Key dùng chung.
//
// The cutover is finished: every business route proxies unconditionally, the
// per-route *_VIA_BACKEND flags are gone, and no route holds a legacy
// direct-Supabase branch to fall back to. CLINIC_API_URL not being set is now a
// broken deployment rather than a supported mode, so it fails loudly.
// Việc chuyển đổi đã hoàn tất: mọi route nghiệp vụ đều proxy vô điều kiện,
// các cờ *_VIA_BACKEND theo từng route đã bị xóa, và không route nào còn giữ
// nhánh trực tiếp-Supabase cũ để fallback. CLINIC_API_URL không được đặt giờ là
// một triển khai hỏng thay vì một chế độ được hỗ trợ, nên nó sẽ báo lỗi rõ ràng.

// Nhập NextResponse từ next/server để tạo phản hồi HTTP cho Next.js
import { NextResponse } from "next/server";
// Nhập hàm getSupabaseServer từ file supabase-server để lấy client Supabase phía server
import { getSupabaseServer } from "./supabase-server";

// Lấy URL API backend từ biến môi trường CLINIC_API_URL, loại bỏ khoảng trắng thừa và dấu / ở cuối
const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

/**
 * Forward a JSON body to a FastAPI endpoint, attaching the caller's Supabase
 * access token (Bearer) + the shared X-API-Key, and mirror the backend's
 * status/body back to the browser as the { ok } / { error } shape the UI expects.
 * Chuyển tiếp một body JSON đến endpoint FastAPI, gắn kèm access token của
 * Supabase (Bearer) + X-API-Key dùng chung, và phản chiếu status/body của backend
 * về trình duyệt dưới dạng { ok } / { error } mà UI mong đợi.
 */
export async function proxyJsonToBackend(
  // Phương thức HTTP được phép: POST, PUT, PATCH, DELETE
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  // Đường dẫn API phía backend (ví dụ: /api/v1/bookings)
  path: string,
  // Dữ liệu body cần gửi đi
  body: unknown,
): Promise<NextResponse> {
  // Kiểm tra nếu API_BASE chưa được cấu hình
  if (!API_BASE) {
    // Trước đây cờ này trả false và route âm thầm dùng nhánh cũ.
    // Giờ không còn nhánh cũ, nên CLINIC_API_URL chưa đặt phải báo lỗi
    // thay vì fail với lỗi 502 khó hiểu mỗi request.
    return NextResponse.json(
      // Trả về lỗi 503 Service Unavailable với thông báo tiếng Việt
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }
  // Lấy client Supabase phía server (dùng cookie của phiên đăng nhập)
  const supabase = await getSupabaseServer();
  // getSession() chỉ đọc cookie cục bộ — không refresh. Khi access token hết
  // hạn, nó trả null dù người dùng vẫn còn phiên hợp lệ. getUser() đổi refresh
  // token lấy access token mới trong bộ nhớ client; gọi trước getSession() để
  // có token dùng được, kể cả trong server component nơi setAll() là no-op.
  // Gọi getUser() trước để refresh token nếu cần, đảm bảo có access token hợp lệ
  await supabase.auth.getUser();
  // Lấy session hiện tại từ Supabase (chứa access_token)
  const {
    data: { session },
  } = await supabase.auth.getSession();
  // Trích xuất access_token từ session
  const token = session?.access_token;
  // Nếu không có token nghĩa là người dùng chưa đăng nhập
  if (!token) {
    // Trả về lỗi 401 Unauthorized với thông báo tiếng Việt
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }

  // Tạo object headers cho request HTTP
  const headers: Record<string, string> = {
    // Định dạng nội dung gửi đi là JSON
    "Content-Type": "application/json",
    // Gắn access token của người dùng vào header Authorization dạng Bearer
    Authorization: `Bearer ${token}`,
  };
  // Lấy API key dùng chung từ biến môi trường BACKEND_API_KEY
  const apiKey = process.env.BACKEND_API_KEY;
  // Nếu có API key thì thêm vào header X-API-Key để xác thực giữa các service
  if (apiKey) headers["X-API-Key"] = apiKey;

  // Khai báo biến để lưu kết quả response từ backend
  let res: Response;
  try {
    // Gửi request fetch đến backend FastAPI với method, headers và body JSON
    res = await fetch(`${API_BASE}${path}`, {
      method, // Phương thức HTTP (POST/PUT/PATCH/DELETE)
      headers, // Headers đã chuẩn bị ở trên
      body: JSON.stringify(body), // Chuyển body thành chuỗi JSON
      cache: "no-store", // Không cache để luôn lấy dữ liệu mới nhất
    });
  } catch {
    // Nếu fetch thất bại (mất kết nối, backend down...)
    return NextResponse.json(
      // Trả về lỗi 502 Bad Gateway với thông báo tiếng Việt
      { error: "Không kết nối được máy chủ xử lý" },
      { status: 502 },
    );
  }

  // Đọc nội dung response dưới dạng text
  const text = await res.text();
  // Khởi tạo payload mặc định là object rỗng
  let payload: unknown = {};
  try {
    // Thử parse text thành JSON
    payload = text ? JSON.parse(text) : {};
  } catch {
    // Nếu parse thất bại, dùng text gốc làm thông báo lỗi
    payload = { error: text || "Lỗi máy chủ" };
  }
  // FastAPI domain errors come back as { error, message }; surface `message` to the UI.
  // Lỗi domain của FastAPI trả về dạng { error, message }; hiển thị `message` cho UI.
  // Kiểm tra nếu response không thành công và payload có trường message
  if (
    !res.ok && // Response không thành công (status >= 400)
    payload && // Payload tồn tại
    typeof payload === "object" && // Payload là object
    "message" in payload // Payload có trường message
  ) {
    // Lấy thông báo lỗi từ trường message
    const msg = (payload as { message?: string }).message;
    // Trả về lỗi với message và status từ backend
    return NextResponse.json({ error: msg ?? "Lỗi xử lý" }, { status: res.status });
  }
  // Trả về payload và status nguyên vẹn từ backend cho trình duyệt
  return NextResponse.json(payload, { status: res.status });
}

/** Server-side GET from FastAPI, with the caller's own token.
 * GET phía server từ FastAPI, với token của chính người gọi.
 *
 * proxyJsonToBackend is for route handlers, which return a NextResponse. A
 * server component wants the data. Both go through the caller's token rather
 * than the shared key alone, so the backend resolves the same identity — and
 * the same clinic — that the page was rendered for.
 * proxyJsonToBackend dành cho route handlers, trả về NextResponse. Còn
 * server component muốn lấy dữ liệu. Cả hai đều đi qua token của người gọi
 * thay vì chỉ dùng key dùng chung, để backend xác định cùng danh tính — và
 * cùng phòng khám — mà trang đã được render cho.
 *
 * Returns null when there is no session or the backend refuses. Callers render
 * the page without the extra detail rather than failing: these are progress
 * indicators, not the reason the screen exists.
 * Trả về null khi không có session hoặc backend từ chối. Người gọi render
 * trang mà không có chi tiết thêm thay vì fail: đây là các chỉ báo tiến độ,
 * không phải lý do tồn tại của màn hình.
 */
export async function fetchFromBackend<T>(path: string): Promise<T | null> {
  // Nếu API_BASE chưa cấu hình thì trả về null (không có dữ liệu)
  if (!API_BASE) return null;

  // Lấy client Supabase phía server
  const supabase = await getSupabaseServer();
  // Cùng lý do — xem proxyJsonToBackend. getSession() không refresh; getUser() thì có.
  // Gọi getUser() trước để refresh token nếu cần
  await supabase.auth.getUser();
  // Lấy session hiện tại
  const {
    data: { session },
  } = await supabase.auth.getSession();
  // Trích xuất access_token
  const token = session?.access_token;
  // Nếu không có token thì trả về null
  if (!token) return null;

  // Tạo headers với Authorization Bearer token
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  // Lấy API key dùng chung
  const apiKey = process.env.BACKEND_API_KEY;
  // Nếu có API key thì thêm vào header
  if (apiKey) headers["X-API-Key"] = apiKey;

  try {
    // Gửi GET request đến backend FastAPI
    const res = await fetch(`${API_BASE}${path}`, { headers, cache: "no-store" });
    // Nếu response không thành công thì trả về null
    if (!res.ok) return null;
    // Parse JSON response và trả về dữ liệu kiểu T
    return (await res.json()) as T;
  } catch {
    // Nếu có lỗi xảy ra thì trả về null
    return null;
  }
}