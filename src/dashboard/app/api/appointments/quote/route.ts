// GET /api/appointments/quote?date=YYYY-MM-DD&location_id=...&doctor_id=...
// Capacity Phase 1 (T-20260629-CAP-01) — proxy xuống FastAPI.
// Logic tính ngân sách + tải hiện có đã chuyển xuống capacity_service.py (backend).
// Frontend chỉ chuyển tiếp request + token, KHÔNG chứa logic nghiệp vụ.
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

export async function GET(request: Request) {
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

  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date");
  const location_id = searchParams.get("location_id");
  const doctor_id = searchParams.get("doctor_id");

  if (!date || !location_id) {
    return NextResponse.json(
      { error: "Thiếu date / location_id." },
      { status: 400 },
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
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  // Build query string for backend
  const params = new URLSearchParams({ date, location_id });
  if (doctor_id) params.set("doctor_id", doctor_id);

  try {
    const res = await fetch(
      `${API_BASE}/api/v1/appointments/quote?${params.toString()}`,
      { headers, cache: "no-store" },
    );
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