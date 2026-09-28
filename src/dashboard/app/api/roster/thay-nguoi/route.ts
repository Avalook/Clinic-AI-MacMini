// Đổi người đứng một ca (29/09/2026) — trưởng ca thay Hà bằng B giữa ca.
//   POST { id, staff_id, ly_do? } → /api/v1/roster/shifts/{id}/thay-nguoi
// Ai được đổi (quyền `roster.shift.swap` hoặc người xếp lịch), ca nào đổi được
// (hôm nay / ngày tới) là việc của backend — route chỉ chuyển tiếp.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  let body: { id?: string; staff_id?: string; ly_do?: string | null };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  const staffId = (body.staff_id ?? "").trim();
  if (!id || !staffId) {
    return NextResponse.json({ error: "Thiếu ca hoặc người thay." }, { status: 400 });
  }
  return proxyJsonToBackend("POST", `/api/v1/roster/shifts/${encodeURIComponent(id)}/thay-nguoi`, {
    staff_id: staffId,
    ly_do: body.ly_do ?? null,
  });
}
