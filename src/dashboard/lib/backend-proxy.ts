// backend-proxy — server→server forwarding from Next route handlers to FastAPI.
//
// Phase 4 (Cụm B/C): as business logic moves into FastAPI, a Next route becomes a
// thin proxy. Unlike the older brief/patients proxies, this forwards the caller's
// Supabase access token (Authorization: Bearer …) so the backend can verify
// identity → staff → role (server-authoritative, identity.py), in addition to the
// shared X-API-Key.
//
// The cutover is finished: every business route proxies unconditionally, the
// per-route *_VIA_BACKEND flags are gone, and no route holds a legacy
// direct-Supabase branch to fall back to. CLINIC_API_URL not being set is now a
// broken deployment rather than a supported mode, so it fails loudly.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "./supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

/**
 * `getUser()` NHƯNG KHÔNG ĐƯỢC PHÉP LÀM SẬP TRANG.
 *
 * `getUser()` đổi refresh token lấy access token mới, và Supabase XOAY refresh
 * token: dùng một lần là hỏng. Trên một lần bấm "Đặt lịch hẹn" có ít nhất hai
 * chỗ cùng đổi — `proxy.ts` chạy cho mọi request, rồi `router.refresh()` kéo
 * server component render lại và chuỗi này gọi lần nữa. Chỗ về sau cầm đúng
 * cái token vừa bị xoay và nhận `AuthApiError: refresh_token_not_found`.
 *
 * Ba chỗ gọi `getUser()` ở file này đều để trần, nên lỗi ấy ném thẳng qua
 * render của server component: Next dựng trang lỗi tối kèm nút thử lại. Người
 * dùng thấy màn đen SAU KHI lịch đã lưu thành công — tưởng đặt hỏng, bấm lại,
 * và chỉ có khoá idempotency chặn được lịch thứ hai.
 *
 * Nuốt lỗi ở đây là ĐÚNG chứ không phải giấu: mục đích duy nhất của lời gọi
 * này là làm mới token *nếu làm được*. Không làm được thì `getSession()` ngay
 * dưới vẫn đọc cookie mà `proxy.ts` vừa đặt trong chính request này. Còn nếu
 * phiên hỏng thật thì `token` ra null và các chỗ gọi đã xử lý sẵn (401 / null)
 * — tức là đá về /login, chứ không phải một trang lỗi không nói gì.
 *
 * Chỉ nuốt lỗi xác thực. Lỗi khác (mạng, DNS) vẫn ném để còn thấy mà sửa.
 */
async function refreshQuietly(
  supabase: Awaited<ReturnType<typeof getSupabaseServer>>,
): Promise<void> {
  try {
    await supabase.auth.getUser();
  } catch (err) {
    if ((err as { __isAuthError?: boolean } | null)?.__isAuthError) return;
    throw err;
  }
}

/**
 * Forward a JSON body to a FastAPI endpoint, attaching the caller's Supabase
 * access token (Bearer) + the shared X-API-Key, and mirror the backend's
 * status/body back to the browser as the { ok } / { error } shape the UI expects.
 */
export async function proxyJsonToBackend(
  // "GET" CÓ TRONG DANH SÁCH, và nó không thừa.
  //
  // `fetchFromBackend` tiện cho server component vì nó trả `T | null`. Nhưng
  // `null` XOÁ MẤT mã trạng thái và câu lỗi: route `/api/roster?staff_id=` gọi
  // nó, thấy null, rồi trả 503 "Không đọc được phạm vi vị trí" — trong khi
  // backend đã trả 404 kèm câu "Không tìm thấy nhân viên này". Người dùng đọc
  // thành "máy chủ hỏng", và 503 trong log lúc có sự cố là một dấu vết dẫn sai.
  //
  // Đo khi nghiệm thu 10/08/2026 với một `staff_id` không tồn tại.
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body: unknown,
  // Chuyển tiếp Idempotency-Key khi route gọi có gửi.
  //
  // Backend đã có sẵn cả cơ chế (api/idempotency.py: reserve khoá, phát lại
  // response đã lưu, TTL 24h) và booking router đã gọi idem.acquire() —
  // nhưng header là TUỲ CHỌN, và file này chưa bao giờ gửi nó. Nên chốt
  // chống-gửi-hai-lần nằm đó không chạy ngày nào. Ngày 04/08 một bệnh nhân
  // có ba lịch cùng khung 17:15, tạo cách nhau 10 và 5 giây.
  //
  // THAM SỐ THỨ TƯ, TUỲ CHỌN, ĐẶT CUỐI: 40 lời gọi trên 30 file đang dùng
  // hàm này. Đổi chữ ký bắt buộc là sửa cả 30 file cho một tính năng mà 29
  // chỗ không cần.
  idempotencyKey?: string,
): Promise<NextResponse> {
  if (!API_BASE) {
    // Previously a flag returned false here and the route quietly used its
    // legacy branch. There is no legacy branch now, so an unset CLINIC_API_URL
    // must say so instead of failing as a confusing 502 per request.
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }
  const supabase = await getSupabaseServer();
  // getSession() chỉ đọc cookie cục bộ — không refresh. Khi access token hết
  // hạn, nó trả null dù người dùng vẫn còn phiên hợp lệ. getUser() đổi refresh
  // token lấy access token mới trong bộ nhớ client; gọi trước getSession() để
  // có token dùng được, kể cả trong server component nơi setAll() là no-op.
  await refreshQuietly(supabase);
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;
  // Backend chỉ đọc header này khi nó CÓ; thiếu thì request chạy như cũ.
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      // GET không được mang thân — `fetch` ném nếu có.
      ...(method === "GET" ? {} : { body: JSON.stringify(body) }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: "Không kết nối được máy chủ xử lý" },
      { status: 502 },
    );
  }

  const text = await res.text();
  let payload: unknown = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { error: text || "Lỗi máy chủ" };
  }
  // FastAPI domain errors come back as { error, message }; surface `message` to the UI.
  if (
    !res.ok &&
    payload &&
    typeof payload === "object" &&
    "message" in payload
  ) {
    const msg = (payload as { message?: string }).message;
    return NextResponse.json({ error: msg ?? "Lỗi xử lý" }, { status: res.status });
  }
  return NextResponse.json(payload, { status: res.status });
}

/** Header xác thực của chính người đang gọi, hoặc null khi chưa đăng nhập.
 *
 * TÁCH RA VÌ ĐÃ CÓ BẢY CHỖ CHÉP LẠI ĐOẠN NÀY, VÀ CẢ BẢY ĐỀU CHÉP THIẾU.
 *
 * Đoạn đúng là `getUser()` rồi mới `getSession()`. Bảy chỗ kia gọi thẳng
 * `getSession()` — và `getSession()` CHỈ ĐỌC COOKIE, không làm mới. Token
 * Supabase sống một tiếng, nên sau một tiếng nó trả null dù người dùng vẫn
 * đăng nhập hợp lệ: màn hình ấy báo "Chưa đăng nhập" trong khi mọi trang khác
 * chạy bình thường. Mỗi tiếng một lần, ở đúng bảy màn.
 *
 * `getUser()` đổi refresh token lấy access token mới trong bộ nhớ client, nên
 * gọi nó trước là đủ. Một dòng — nhưng là một dòng mà bảy người chép quên,
 * nên nó thuộc về đây chứ không thuộc về từng chỗ gọi.
 */
export async function getCallerAuthHeaders(): Promise<Record<
  string,
  string
> | null> {
  const supabase = await getSupabaseServer();
  await refreshQuietly(supabase);
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return null;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;
  return headers;
}

/** Server-side GET from FastAPI, with the caller's own token.
 *
 * proxyJsonToBackend is for route handlers, which return a NextResponse. A
 * server component wants the data. Both go through the caller's token rather
 * than the shared key alone, so the backend resolves the same identity — and
 * the same clinic — that the page was rendered for.
 *
 * Returns null when there is no session or the backend refuses. Callers render
 * the page without the extra detail rather than failing: these are progress
 * indicators, not the reason the screen exists.
 */
export async function fetchFromBackend<T>(path: string): Promise<T | null> {
  if (!API_BASE) return null;

  const supabase = await getSupabaseServer();
  // Cùng lý do — xem proxyJsonToBackend. getSession() không refresh; getUser() thì có.
  await refreshQuietly(supabase);
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return null;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  try {
    const res = await fetch(`${API_BASE}${path}`, { headers, cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
