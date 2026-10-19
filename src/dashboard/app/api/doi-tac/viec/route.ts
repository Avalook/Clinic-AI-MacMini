// GET /api/doi-tac/viec?chi_dinh=<uuid>
// MỘT việc đối tác (Phòng đối tác, 16/10/2026): trạng thái, thu hộ, tệp, mẫu
// kết quả — cùng dữ liệu với bàn `/doi-tac`. Máy chủ gác (`partner.work`).

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  const id = new URL(request.url).searchParams.get("chi_dinh") ?? "";
  if (!UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Mã việc không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend("GET", `/api/v1/doi-tac/viec/${encodeURIComponent(id)}`, undefined);
}
