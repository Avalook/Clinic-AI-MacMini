// Chỉ định nháp của một lượt: thư ký nhập (POST gộp / PUT sửa cả danh sách),
// bác sĩ và thư ký cùng xem (GET). Proxy mỏng — ai được làm gì do FastAPI quyết.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function visitId(params: Promise<{ id: string }>): Promise<string | null> {
  const { id } = await params;
  return UUID_RE.test(id) ? id : null;
}

function badId() {
  return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const id = await visitId(params);
  if (!id) return badId();
  return proxyJsonToBackend("GET", `/api/v1/visits/${id}/service-orders/draft`, null);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const id = await visitId(params);
  if (!id) return badId();
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("POST", `/api/v1/visits/${id}/service-orders/draft`, body);
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const id = await visitId(params);
  if (!id) return badId();
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("PUT", `/api/v1/visits/${id}/service-orders/draft`, body);
}
