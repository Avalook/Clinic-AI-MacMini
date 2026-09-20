// Xác nhận tệp kết quả: HOP_LE hoặc TU_CHOI (bắt buộc lý do).
// Proxy mỏng tới FastAPI POST /api/v1/cskh/ket-qua/tep/{tepId}/xac-nhan.
// Fail-closed: thiếu capability ket_qua.xac_nhan -> 403.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

export async function POST(
  request: Request,
  ctx: { params: Promise<{ tepId: string }> },
) {
  const { tepId } = await ctx.params;
  const id = (tepId ?? "").trim();
  if (!id) {
    return NextResponse.json({ error: "Thiếu mã tệp." }, { status: 400 });
  }

  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Dữ liệu gửi lên không đúng chuẩn JSON." },
      { status: 400 },
    );
  }

  return proxyJsonToBackend(
    "POST",
    `/api/v1/cskh/ket-qua/tep/${encodeURIComponent(id)}/xac-nhan`,
    body,
  );
}
