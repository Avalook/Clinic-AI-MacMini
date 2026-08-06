// What is still in the way of a work item.
//
//   GET /api/work-items/{id}/blockers?phase=start|complete
//     → { phase, blockers: [{ node_code, dependency_type }], open }
//
// The board already knows an item is blocked; a doctor looking at a patient she
// cannot start needs the next thing — WHICH step is holding it. Fetched per
// selection rather than per row, because the answer is only interesting for the
// one patient being looked at and doing it for the whole list is an N+1 against
// a gate function.

import { NextResponse } from "next/server";

import { getCallerAuthHeaders } from "../../../../../lib/backend-proxy";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã đầu việc không hợp lệ" }, { status: 400 });
  }
  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }

  const phase =
    new URL(request.url).searchParams.get("phase") === "complete"
      ? "complete"
      : "start";

  // Header lấy từ chỗ dùng chung. Bản cũ tự dựng ở đây và QUÊN getUser(), nên
  // sau một tiếng token hết hạn là chỗ này báo "chưa đăng nhập" trong khi mọi
  // trang khác vẫn chạy — xem getCallerAuthHeaders trong backend-proxy.ts.
  const headers = await getCallerAuthHeaders();
  if (!headers) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });

  try {
    const res = await fetch(
      `${API_BASE}/api/v1/work-items/${id}/blockers?phase=${phase}`,
      { headers, cache: "no-store" },
    );
    return NextResponse.json(await res.json(), { status: res.status });
  } catch {
    return NextResponse.json({ error: "Không kết nối được máy chủ" }, { status: 502 });
  }
}
