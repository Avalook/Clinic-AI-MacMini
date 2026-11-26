// Proxy thuốc (26/11/2026) → FastAPI `/api/v1/thuoc/*`: xoá thuốc chưa từng dùng (lưu
// bản chụp trước), danh sách thuốc đã xoá, khôi phục. Luật + quyền ở máy chủ; route
// chỉ chuyển tiếp theo danh sách trắng dưới đây.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function dangNhap() {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  return user;
}

export async function GET(request: Request, { params }: { params: Promise<{ action: string }> }) {
  if (!(await dangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const { action } = await params;
  if (action === "da-xoa") return proxyJsonToBackend("GET", "/api/v1/thuoc/da-xoa", undefined);
  const id = new URL(request.url).searchParams.get("id") ?? "";
  if (action === "xoa-duoc" && UUID_RE.test(id)) {
    return proxyJsonToBackend("GET", `/api/v1/thuoc/${id}/xoa-duoc`, undefined);
  }
  if (action === "cach-dung" && UUID_RE.test(id)) {
    return proxyJsonToBackend("GET", `/api/v1/thuoc/${id}/cach-dung`, undefined);
  }
  if (action === "don-vi-con" && UUID_RE.test(id)) {
    return proxyJsonToBackend("GET", `/api/v1/thuoc/${id}/don-vi-con`, undefined);
  }
  return NextResponse.json({ error: `Không đọc được: ${action}` }, { status: 400 });
}

export async function POST(request: Request, { params }: { params: Promise<{ action: string }> }) {
  if (!(await dangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const { action } = await params;
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = typeof body?.id === "string" ? body.id : "";
  if (action === "xoa" && UUID_RE.test(id)) {
    return proxyJsonToBackend("POST", `/api/v1/thuoc/${id}/xoa`, { ly_do: body.ly_do ?? null });
  }
  if (action === "khoi-phuc" && UUID_RE.test(id)) {
    return proxyJsonToBackend("POST", `/api/v1/thuoc/da-xoa/${id}/khoi-phuc`, {});
  }
  // Cách dùng có cấu trúc (PR E): tính ở máy chủ / lưu mặc định của danh mục.
  if (action === "cach-dung-tinh") return proxyJsonToBackend("POST", "/api/v1/thuoc/cach-dung/tinh", body);
  if (action === "luu-cach-dung" && UUID_RE.test(id)) {
    const { ct, so_lieu_moi_don_vi_goc } = body;
    return proxyJsonToBackend("PUT", `/api/v1/thuoc/${id}/cach-dung`, { ct, so_lieu_moi_don_vi_goc });
  }
  // Đơn vị con + số con / mẹ + giá con (Tuyền 26/11).
  if (action === "luu-don-vi-con" && UUID_RE.test(id)) {
    const { don_vi_con, so_con, gia_con } = body;
    return proxyJsonToBackend("PUT", `/api/v1/thuoc/${id}/don-vi-con`, { don_vi_con, so_con, gia_con });
  }
  return NextResponse.json({ error: `Thao tác không hợp lệ: ${action}` }, { status: 400 });
}
