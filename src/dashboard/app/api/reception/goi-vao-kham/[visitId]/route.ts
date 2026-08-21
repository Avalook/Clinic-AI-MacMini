// Mốc "gọi vào khám" của quầy lễ tân — một cặp bấm/bấm-lại.
//
//   POST   → ghi mốc, đóng bước tiếp nhận, mở đồng hồ KHÁM
//   DELETE → rút lại mốc (backend từ chối nếu bác sĩ đã động vào)
//
// Route mỏng đúng như mọi route khác: không luật nào ở đây, chỉ chuyển tiếp và
// GIỮ NGUYÊN mã lỗi + câu lỗi của backend — câu "bước X đã bắt đầu" là thứ
// người ngồi quầy cần đọc, nuốt nó đi là họ chỉ biết "không được".

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

function layId(visitId: string): string | null {
  const s = (visitId ?? "").trim();
  return s.length > 0 ? s : null;
}

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ visitId: string }> },
) {
  const { visitId } = await params;
  const id = layId(visitId);
  if (!id) {
    return NextResponse.json({ error: "Thiếu id lượt khám." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/reception/goi-vao-kham/${encodeURIComponent(id)}`,
    {},
  );
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ visitId: string }> },
) {
  const { visitId } = await params;
  const id = layId(visitId);
  if (!id) {
    return NextResponse.json({ error: "Thiếu id lượt khám." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "DELETE",
    `/api/v1/reception/goi-vao-kham/${encodeURIComponent(id)}`,
    {},
  );
}
