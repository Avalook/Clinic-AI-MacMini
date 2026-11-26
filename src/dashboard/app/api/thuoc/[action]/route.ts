// Proxy thuốc (26/11/2026) → FastAPI `/api/v1/thuoc/*`: gợi ý tên gần giống, "Nhờ kho
// thêm thuốc", xoá thuốc chưa từng dùng. Luật + quyền ở máy chủ; route chỉ chuyển tiếp
// theo danh sách trắng dưới đây.

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
  const q = new URL(request.url).searchParams;
  if (action === "goi-y") {
    return proxyJsonToBackend("GET", "/api/v1/thuoc/goi-y?" + new URLSearchParams({ ten: q.get("ten") ?? "" }), undefined);
  }
  if (action === "nho-kho") return proxyJsonToBackend("GET", "/api/v1/thuoc/nho-kho", undefined);
  const id = q.get("id") ?? "";
  if (action === "xoa-duoc" && UUID_RE.test(id)) {
    return proxyJsonToBackend("GET", `/api/v1/thuoc/${id}/xoa-duoc`, undefined);
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
  if (action === "nho-kho") return proxyJsonToBackend("POST", "/api/v1/thuoc/nho-kho", body);
  if (action === "danh-dau" && UUID_RE.test(id)) {
    return proxyJsonToBackend("POST", `/api/v1/thuoc/nho-kho/${id}/danh-dau`, { xong: !!body.xong });
  }
  if (action === "xoa" && UUID_RE.test(id)) {
    return proxyJsonToBackend("POST", `/api/v1/thuoc/${id}/xoa`, {});
  }
  return NextResponse.json({ error: `Thao tác không hợp lệ: ${action}` }, { status: 400 });
}
