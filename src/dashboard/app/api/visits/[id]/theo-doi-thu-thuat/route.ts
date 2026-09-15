// Theo dõi sau thủ thuật — bác sĩ quyết, CSKH chỉ nhìn (16/09/2026). Proxy mỏng.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function maLuot(params: Promise<{ id: string }>) {
  const { id } = await params;
  return UUID_RE.test(id) ? id : null;
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const id = await maLuot(params);
  if (!id) return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
  return proxyJsonToBackend("GET", `/api/v1/visits/${id}/theo-doi-thu-thuat`, null);
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const id = await maLuot(params);
  if (!id) return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
  const body = await request.json().catch(() => null);
  return proxyJsonToBackend("PUT", `/api/v1/visits/${id}/theo-doi-thu-thuat`, body);
}
