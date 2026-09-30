// Khôi phục (Hoàn tác) tệp kết quả đã xoá mềm (V9, 30/09/2026) — trong 30 ngày,
// khi tệp vật lý còn. Proxy mỏng tới FastAPI
// POST /api/v1/cskh/ket-qua/tep/{tepId}/khoi-phuc; máy chủ kiểm quyền.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

export async function POST(
  _request: Request,
  ctx: { params: Promise<{ tepId: string }> },
) {
  const { tepId } = await ctx.params;
  const id = (tepId ?? "").trim();
  if (!id) {
    return NextResponse.json({ error: "Thiếu mã tệp." }, { status: 400 });
  }
  const duong = `/api/v1/cskh/ket-qua/tep/${encodeURIComponent(id)}/khoi-phuc`;
  return proxyJsonToBackend("POST", duong, {});
}
