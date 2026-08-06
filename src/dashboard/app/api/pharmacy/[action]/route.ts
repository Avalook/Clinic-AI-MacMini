// Proxy các thao tác nhà thuốc xuống FastAPI.
//
// Trước đây bốn màn /pharmacy đọc thẳng Supabase và KHÔNG có đường ghi nào —
// RLS chỉ cấp SELECT, nên kể cả gắn nút thì trình duyệt cũng không ghi được.
// Mọi thao tác kho đi qua đây.
//
// Danh sách trắng ở dưới quyết định đường nào hợp lệ. Một `[action]` trần sẽ
// mở luôn cả những đường thêm sau này mà chưa ai cân nhắc có nên cho trình
// duyệt gọi không.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

/** Thao tác cho phép → đường backend. */
const ACTIONS: Record<string, string> = {
  receive: "/api/v1/pharmacy/receive",
  dispense: "/api/v1/pharmacy/dispense",
  refuse: "/api/v1/pharmacy/refuse",
  "close-line": "/api/v1/pharmacy/close-line",
  adjust: "/api/v1/pharmacy/adjust",
  discard: "/api/v1/pharmacy/discard",
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

  // Backend chặn lần nữa (require_role PHARMACIST/MANAGEMENT). Chặn ở đây để
  // người không có quyền đọc được một câu tiếng Việt thay vì 403 trần.
  const role = await getClinicRole();
  if (role !== "PHARMACIST" && role !== "MANAGEMENT") {
    return NextResponse.json(
      { error: "Chỉ Dược sĩ / Quản lý mới được thao tác kho thuốc." },
      { status: 403 },
    );
  }

  const { action } = await params;
  const path = ACTIONS[action];
  if (!path) {
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

  return proxyJsonToBackend("POST", path, body);
}
