// Order services on a visit. Thin proxy — every rule (which room performs what,
// whether a service may be ordered, how several ultrasounds collapse into one
// visit to the room) lives in SQL, where it holds for every caller.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã lượt khám không hợp lệ" }, { status: 400 });
  }
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("POST", `/api/v1/visits/${id}/service-orders`, body);
}
