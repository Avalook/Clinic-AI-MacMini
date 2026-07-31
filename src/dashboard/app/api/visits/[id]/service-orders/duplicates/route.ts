// Which of these services the patient already had ordered in the last 30 days.
// POST because the list of codes is the question; nothing is written.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

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
  return proxyJsonToBackend(
    "POST",
    `/api/v1/visits/${id}/service-orders/duplicates`,
    body,
  );
}
