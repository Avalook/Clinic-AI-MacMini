// Đánh dấu / bỏ dấu khách ưu tiên kèm lý do (Tuyền chốt 15/09/2026). Proxy mỏng.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã khách hàng không hợp lệ" }, { status: 400 });
  }
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("PUT", `/api/v1/patients/${id}/uu-tien`, body);
}
