// Công ty trong HỒ SƠ khách (G5c): danh sách + thêm / sửa. Proxy mỏng — quyền
// (Lễ tân / CSKH / Thu ngân / Kế toán), MST chỉ nhắc, ghi rác 422: máy chủ quyết.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type Ctx = { params: Promise<{ id: string }> };

async function maKhach(ctx: Ctx): Promise<string | NextResponse> {
  const { id } = await ctx.params;
  return UUID_RE.test(id) ? id : NextResponse.json({ error: "Mã khách hàng không hợp lệ" }, { status: 400 });
}

export async function GET(request: Request, ctx: Ctx) {
  const id = await maKhach(ctx);
  if (id instanceof NextResponse) return id;
  const caDaAn = new URL(request.url).searchParams.get("ca_da_an") === "true";
  return proxyJsonToBackend("GET", `/api/v1/hoa-don/cong-ty/khach/${id}?ca_da_an=${caDaAn}`, undefined);
}

export async function PUT(request: Request, ctx: Ctx) {
  const id = await maKhach(ctx);
  if (id instanceof NextResponse) return id;
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("PUT", `/api/v1/hoa-don/cong-ty/khach/${id}`, body);
}
