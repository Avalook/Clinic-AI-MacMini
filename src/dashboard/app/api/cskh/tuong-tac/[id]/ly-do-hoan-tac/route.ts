// Ghi lý do làm lại — SAU khi hoàn tác, tuỳ chọn (Đặng Dương 17/08/2026:
// "có phần ghi chú để ghi thông tin, ví dụ lý do làm lại, để nhân sự dễ báo
// cáo và quản lý nắm được không?").
//
// Hoàn tác vẫn MỘT cú bấm (Quang 10/08 — không hộp xác nhận); ô lý do hiện
// SAU đó và bỏ qua được. Backend chỉ nhận vào dòng ĐÃ hoàn tác.
//
//   POST { ly_do } → { ok: true }

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const tuongTacId = (id ?? "").trim();
  if (!tuongTacId) {
    return NextResponse.json({ error: "Thiếu id thao tác." }, { status: 400 });
  }
  const body = (await request.json().catch(() => null)) as {
    ly_do?: string;
  } | null;
  if (!body?.ly_do?.trim()) {
    return NextResponse.json(
      { error: "Lý do trống thì không có gì để ghi." },
      { status: 422 },
    );
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/cskh/tuong-tac/${encodeURIComponent(tuongTacId)}/ly-do-hoan-tac`,
    { ly_do: body.ly_do.trim() },
  );
}
