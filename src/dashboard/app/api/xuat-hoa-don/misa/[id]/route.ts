// Một lần xuất MISA (G5c): chi tiết hoá đơn có thay đổi · bỏ đánh dấu · khôi phục.
// Proxy mỏng — kiểm mã, còn lại máy chủ quyết.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type Ctx = { params: Promise<{ id: string }> };

async function maLan(ctx: Ctx): Promise<string | NextResponse> {
  const { id } = await ctx.params;
  return UUID_RE.test(id) ? id : NextResponse.json({ error: "Mã lần xuất không hợp lệ" }, { status: 400 });
}

export async function GET(_req: Request, ctx: Ctx) {
  const id = await maLan(ctx);
  if (id instanceof NextResponse) return id;
  return proxyJsonToBackend("GET", `/api/v1/hoa-don/misa-xuat/${id}`, undefined);
}

export async function DELETE(_req: Request, ctx: Ctx) {
  const id = await maLan(ctx);
  if (id instanceof NextResponse) return id;
  return proxyJsonToBackend("DELETE", `/api/v1/hoa-don/misa-xuat/${id}`, undefined);
}

export async function PUT(_req: Request, ctx: Ctx) {
  const id = await maLan(ctx);
  if (id instanceof NextResponse) return id;
  return proxyJsonToBackend("PUT", `/api/v1/hoa-don/misa-xuat/${id}`, {});
}
