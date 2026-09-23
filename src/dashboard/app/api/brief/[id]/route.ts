// /api/brief/[id]
//   POST → sinh "tóm tắt trước khám" cho 1 bệnh nhân.
//
// CẦU NỐI ĐẦU TIÊN dashboard → FastAPI. Mọi route khác đọc/ghi thẳng Supabase;
// riêng tóm tắt do FastAPI lo (POST /api/v1/brief/{id}) vì cần LLM + tổng hợp
// nhiều bảng. Proxy CHẠY PHÍA SERVER nên:
//   - KHÔNG dính CORS (server→server, không phải trình duyệt→FastAPI),
//   - giữ BACKEND_API_KEY ở server (không lộ ra bundle trình duyệt).
//
// CHỈ gọi-và-trả, KHÔNG lưu kết quả vào DB.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";

// FastAPI base URL. Server-only (không phải NEXT_PUBLIC) vì lời gọi đi từ server.
// Missing configuration is a broken deployment, never an implicit localhost.
const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // 1) Phải đăng nhập (cổng chung Supabase).
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Chưa đăng nhập." }, { status: 401 });
  }
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    return NextResponse.json({ error: "Chưa đăng nhập." }, { status: 401 });
  }

  // 2) Ai được tóm tắt khách nào là việc của BACKEND (`_can_generate_brief`:
  //    vai bác sĩ/thư ký + đúng khách của mình). Trang này từng tự đọc bảng
  //    `appointment` để kiểm lặp lại — một quyết định ở frontend, bỏ 24/09/2026.

  if (!UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "Mã bệnh nhân không hợp lệ." },
      { status: 400 },
    );
  }

  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }

  // 4) Proxy sang FastAPI with both the caller identity and the shared
  // server-to-server credential.
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  // Tóm tắt gọi LLM → có thể vài giây. Đặt trần 60s để backend treo không kéo
  // theo request này treo mãi.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/brief/${id}`, {
      method: "POST",
      headers,
      signal: controller.signal,
      cache: "no-store",
    });
  } catch {
    // ECONNREFUSED / timeout / DNS… — KHÔNG echo chi tiết (có thể lộ nội bộ).
    return NextResponse.json(
      {
        error:
          "Không kết nối được máy chủ tóm tắt. Kiểm tra dịch vụ FastAPI đã bật chưa.",
      },
      { status: 502 },
    );
  } finally {
    clearTimeout(timeout);
  }

  if (res.status === 404) {
    return NextResponse.json(
      { error: "Không tìm thấy bệnh nhân để tóm tắt." },
      { status: 404 },
    );
  }
  if (res.status === 401 || res.status === 403) {
    return NextResponse.json(
      { error: "Sai cấu hình khóa API giữa dashboard và máy chủ tóm tắt." },
      { status: 502 },
    );
  }
  if (!res.ok) {
    return NextResponse.json(
      { error: "Máy chủ tóm tắt gặp lỗi khi tạo tóm tắt. Thử lại sau." },
      { status: 502 },
    );
  }

  let payload: { markdown?: string; elapsed_ms?: number };
  try {
    payload = (await res.json()) as { markdown?: string; elapsed_ms?: number };
  } catch {
    return NextResponse.json(
      { error: "Máy chủ tóm tắt trả dữ liệu không đọc được." },
      { status: 502 },
    );
  }

  // Chỉ chuyển phần markdown + thời gian; KHÔNG lưu, KHÔNG log nội dung BN.
  return NextResponse.json({
    markdown: payload.markdown ?? "",
    elapsed_ms: payload.elapsed_ms ?? null,
  });
}
