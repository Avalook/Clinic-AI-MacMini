// Xoá mềm một tệp kết quả (V9, 30/09/2026) — lý do bắt buộc, khôi phục được
// 30 ngày. Proxy mỏng tới FastAPI POST /api/v1/cskh/ket-qua/tep/{tepId}/xoa:
// ai xoá được, xoá thường hay "Đính chính – gỡ tệp" do máy chủ quyết.

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

  const duong = `/api/v1/cskh/ket-qua/tep/${encodeURIComponent(id)}/xoa`;
  return proxyJsonToBackend("POST", duong, body);
}
