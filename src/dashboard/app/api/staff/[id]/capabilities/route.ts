// GET/POST/DELETE /api/staff/[id]/capabilities
// Proxy mỏng sang FastAPI:
//   GET    /api/v1/staff/{id}/capabilities
//   POST   /api/v1/staff/{id}/capabilities
//   DELETE /api/v1/staff/{id}/capabilities/{capability}
//
// Phân quyền: Cấp/thu hồi yêu cầu MANAGEMENT; đọc trạng thái yêu cầu nhân sự phòng khám.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

export async function GET(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const staffId = (id ?? "").trim();
  if (!staffId) {
    return NextResponse.json({ error: "Thiếu mã nhân sự" }, { status: 400 });
  }

  return proxyJsonToBackend(
    "GET",
    `/api/v1/staff/${encodeURIComponent(staffId)}/capabilities`,
    undefined,
  );
}

export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const staffId = (id ?? "").trim();
  if (!staffId) {
    return NextResponse.json({ error: "Thiếu mã nhân sự" }, { status: 400 });
  }

  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Dữ liệu gửi lên không đúng chuẩn JSON" },
      { status: 400 },
    );
  }

  return proxyJsonToBackend(
    "POST",
    `/api/v1/staff/${encodeURIComponent(staffId)}/capabilities`,
    body,
  );
}

export async function DELETE(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const staffId = (id ?? "").trim();
  if (!staffId) {
    return NextResponse.json({ error: "Thiếu mã nhân sự" }, { status: 400 });
  }

  const { searchParams } = new URL(request.url);
  let capability = (searchParams.get("capability") ?? "").trim();
  if (!capability) {
    try {
      const body = (await request.json()) as { capability?: string };
      capability = (body?.capability ?? "").trim();
    } catch {
      // ignore
    }
  }

  if (!capability) {
    return NextResponse.json(
      { error: "Thiếu tên capability cần thu hồi" },
      { status: 400 },
    );
  }

  return proxyJsonToBackend(
    "DELETE",
    `/api/v1/staff/${encodeURIComponent(staffId)}/capabilities/${encodeURIComponent(capability)}`,
    undefined,
  );
}
