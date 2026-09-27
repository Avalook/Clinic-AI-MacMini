// POST /api/doi-tac/huy-da-thu  { chi_dinh_id, ly_do }
// Đối tác huỷ ghi nhận "đã thu tiền khách" (bắt buộc lý do — máy chủ kiểm,
// `DoiTacService.huy_da_thu`). Dòng cũ không xoá, giữ lại kèm lý do.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(request: Request) {
  const than = (await request.json().catch(() => null)) as {
    chi_dinh_id?: unknown;
    ly_do?: unknown;
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
    `/api/v1/doi-tac/viec/${encodeURIComponent(id)}/huy-da-thu`,
    { ly_do: typeof than?.ly_do === "string" ? than.ly_do : null },
  );
}
