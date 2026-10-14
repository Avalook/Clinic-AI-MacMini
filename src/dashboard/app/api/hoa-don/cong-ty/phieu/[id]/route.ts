// Hoá đơn công ty trên MỘT phiếu thu (G5c): đọc / ghi bản chụp / bỏ chọn. Proxy mỏng —
// quyền (Lễ tân / CSKH / Thu ngân / Kế toán), MST chỉ nhắc, lịch sử sửa: máy chủ quyết.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type Ctx = { params: Promise<{ id: string }> };

async function maPhieu(ctx: Ctx): Promise<string | NextResponse> {
  const { id } = await ctx.params;
  return UUID_RE.test(id) ? id : NextResponse.json({ error: "Mã phiếu thu không hợp lệ" }, { status: 400 });
}

export async function GET(_req: Request, ctx: Ctx) {
  const id = await maPhieu(ctx);
  if (id instanceof NextResponse) return id;
  return proxyJsonToBackend("GET", `/api/v1/hoa-don/cong-ty/phieu/${id}`, undefined);
}

export async function PUT(request: Request, ctx: Ctx) {
  const id = await maPhieu(ctx);
  if (id instanceof NextResponse) return id;
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("PUT", `/api/v1/hoa-don/cong-ty/phieu/${id}`, body);
}

export async function DELETE(_req: Request, ctx: Ctx) {
  const id = await maPhieu(ctx);
  if (id instanceof NextResponse) return id;
  return proxyJsonToBackend("DELETE", `/api/v1/hoa-don/cong-ty/phieu/${id}`, undefined);
}
