// Proxy các thao tác điều phối xuống FastAPI.
//
// MỘT route handler cho bốn thao tác thay vì bốn file gần giống nhau. Danh sách
// trắng ở dưới quyết định đường nào hợp lệ — một `[action]` trần sẽ cho phép gọi
// bất kỳ đường nào dưới /api/v1/dispatch/, kể cả đường mới thêm sau này mà chưa
// ai cân nhắc có nên mở ra trình duyệt không.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

/** Thao tác cho phép → (phương thức, đường backend). */
const ACTIONS: Record<string, { method: "POST" | "PUT"; path: string }> = {
  move: { method: "POST", path: "/api/v1/dispatch/move" },
  "transfer-room": { method: "POST", path: "/api/v1/dispatch/transfer-room" },
  route: { method: "POST", path: "/api/v1/dispatch/route" },
  threshold: { method: "PUT", path: "/api/v1/dispatch/threshold" },
};

export async function POST(
  request: Request,
  { params }: { params: Promise<{ action: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  // Backend cũng chặn (require_role TRUONG_CA/MANAGEMENT). Chặn ở đây nữa để
  // người không có quyền nhận một câu tiếng Việt thay vì 403 trần từ API.
  const role = await getClinicRole();
  if (role !== "TRUONG_CA" && role !== "MANAGEMENT") {
    return NextResponse.json(
      { error: "Chỉ Trưởng ca / Quản lý mới được điều phối." },
      { status: 403 },
    );
  }

  const { action } = await params;
  const target = ACTIONS[action];
  if (!target) {
    return NextResponse.json(
      { error: `Thao tác không hợp lệ: ${action}` },
      { status: 400 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  return proxyJsonToBackend(target.method, target.path, body);
}
