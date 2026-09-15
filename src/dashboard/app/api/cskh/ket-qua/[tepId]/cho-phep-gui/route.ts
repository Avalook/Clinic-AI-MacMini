// Bác sĩ cho phép gửi một tệp kết quả cho khách (Tuyền chốt 15/09/2026).
// Proxy mỏng — FastAPI kiểm vai bác sĩ; trigger DB chặn gửi khi chưa cho phép.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

export async function POST(
  _request: Request,
  ctx: { params: Promise<{ tepId: string }> },
) {
  const { tepId } = await ctx.params;
  const id = (tepId ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id tệp." }, { status: 400 });
  return proxyJsonToBackend(
    "POST",
    `/api/v1/cskh/ket-qua/tep/${encodeURIComponent(id)}/cho-phep-gui`,
    {},
  );
}
