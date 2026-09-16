// POST /api/doi-tac/da-lay-mau  { chi_dinh_id }
// Đối tác xác nhận đã lấy mẫu cho xét nghiệm họ tự lấy. Luật (việc nào được bấm)
// nằm ở máy chủ — `LuotKhamService.doi_tac_da_lay_mau`.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(request: Request) {
  const than = (await request.json().catch(() => null)) as {
    chi_dinh_id?: unknown;
  } | null;
  const id = typeof than?.chi_dinh_id === "string" ? than.chi_dinh_id : "";
  if (!UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Mã việc không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/doi-tac/viec/${encodeURIComponent(id)}/da-lay-mau`,
    {},
  );
}
