// Truyền dòng sự kiện từ FastAPI về trình duyệt.
//
// VÌ SAO PHẢI ĐI VÒNG QUA ĐÂY. Trình duyệt mở SSE bằng `EventSource`, mà
// EventSource KHÔNG đặt được header — không gắn được `Authorization: Bearer`.
// Route này chạy trên máy chủ nên gắn được, y hệt mọi lời gọi khác trong
// backend-proxy.ts. Nhờ vậy cửa gác phía FastAPI không phải mở lối riêng cho
// SSE.
//
// ĐÃ CÂN NHẮC VÀ BỎ: cho trình duyệt gọi thẳng FastAPI với token trong query
// string. Làm thế là ghi token vào log truy cập của mọi proxy trên đường —
// đọc được, sống lâu, đủ để đóng giả người dùng.
//
// KHÔNG DÙNG proxyJsonToBackend. Hàm ấy đọc trọn phần thân rồi mới trả lời
// (`res.text()`), đúng cho JSON và sai hoàn toàn ở đây: một dòng SSE không bao
// giờ kết thúc, nên đọc trọn nghĩa là treo mãi. Chỗ này phải chuyền thẳng
// `res.body`.

import { getSupabaseServer } from "../../../../lib/supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

// Dòng sự kiện phải sống lâu, nên không được để Next đệm hay dựng sẵn.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
// Next mặc định cắt route handler sau 15s trên một số nền tảng. Dòng này phải
// mở hàng giờ; 0 = không giới hạn.
export const maxDuration = 0;

export async function GET(request: Request): Promise<Response> {
  if (!API_BASE) {
    return new Response("CLINIC_API_URL chưa cấu hình", { status: 503 });
  }

  const supabase = await getSupabaseServer();
  // getSession() chỉ đọc cookie, không làm mới. getUser() đổi refresh token lấy
  // access token còn hạn — cùng lý do đã ghi trong backend-proxy.ts.
  await supabase.auth.getUser();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return new Response("Chưa đăng nhập", { status: 401 });

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: "text/event-stream",
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE}/api/v1/events/stream`, {
      headers,
      // Trình duyệt đóng tab → request này bị huỷ → tín hiệu phải truyền tiếp
      // lên FastAPI, không thì mỗi tab đóng để lại một dòng treo bên đó.
      signal: request.signal,
      cache: "no-store",
    });
  } catch {
    return new Response("Không kết nối được máy chủ", { status: 502 });
  }

  if (!upstream.ok || !upstream.body) {
    return new Response("Máy chủ từ chối dòng sự kiện", {
      status: upstream.status || 502,
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
