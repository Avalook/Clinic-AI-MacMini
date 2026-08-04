// GET/POST/DELETE /api/appointments/slot-hold — giữ chỗ trong lúc CSKH đang chọn.
//
// Quang (2026-08-04): 10 phút giữ chỗ là để CSKH KHÁC thấy khung này đang có
// người chọn mà tránh đặt trùng — không phải để giữ tiếp sau khi đã đặt xong.
//
// Chỉ chuyển tiếp. Ai được giữ, giữ bao lâu, giữ chồng nhau ra sao đều nằm ở
// slot_hold_service.py — một bản sao luật ở đây là một bản sao sẽ lệch.
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

async function proxy(
  request: Request,
  method: "GET" | "POST" | "DELETE",
): Promise<NextResponse> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }

  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  let url = `${API_BASE}/api/v1/appointments/slot-hold`;
  let body: string | undefined;
  if (method === "GET") {
    const date = new URL(request.url).searchParams.get("date");
    if (!date) return NextResponse.json({ error: "Thiếu date." }, { status: 400 });
    url += `?date=${encodeURIComponent(date)}`;
  } else if (method === "POST") {
    body = JSON.stringify(await request.json().catch(() => ({})));
  }

  try {
    const res = await fetch(url, { method, headers, body, cache: "no-store" });
    const text = await res.text();
    let payload: unknown = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      payload = { error: text || "Lỗi máy chủ" };
    }
    return NextResponse.json(payload, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Không kết nối được máy chủ xử lý" },
      { status: 502 },
    );
  }
}

export const GET = (r: Request) => proxy(r, "GET");
export const POST = (r: Request) => proxy(r, "POST");
export const DELETE = (r: Request) => proxy(r, "DELETE");
