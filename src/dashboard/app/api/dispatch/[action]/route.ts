// Proxy các thao tác điều phối xuống FastAPI.
//
// MỘT route handler cho bốn thao tác thay vì bốn file gần giống nhau. Danh sách
// trắng ở dưới quyết định đường nào hợp lệ — một `[action]` trần sẽ cho phép gọi
// bất kỳ đường nào dưới /api/v1/dispatch/, kể cả đường mới thêm sau này mà chưa
// ai cân nhắc có nên mở ra trình duyệt không.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

/** Thao tác cho phép → (phương thức, đường backend). */
const ACTIONS: Record<string, { method: "POST" | "PUT"; path: string }> = {
  move: { method: "POST", path: "/api/v1/dispatch/move" },
  "transfer-room": { method: "POST", path: "/api/v1/dispatch/transfer-room" },
  route: { method: "POST", path: "/api/v1/dispatch/route" },
  threshold: { method: "PUT", path: "/api/v1/dispatch/threshold" },
  // Bác sĩ chính nghỉ giữa chừng → chuyển lượt, bắt buộc lý do (15/09/2026).
  "doi-bac-si": { method: "POST", path: "/api/v1/dispatch/doi-bac-si" },
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

  // Cửa quyền là việc của BACKEND (dispatch.manage — lego Điều phối khách; câu từ chối của
  // backend đã là tiếng Việt) — proxy chỉ kiểm đã đăng nhập
  // (kiểm toán 27/09/2026: cửa vai ở đây chặn người đã được cấp lego).

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
