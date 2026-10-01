// Ngoại lệ ca trực lâm sàng — route chỉ chuyển tiếp; backend hỏi permission.manage.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const ngay = new URL(request.url).searchParams.get("ngay")?.trim() ?? "";
  const suffix = ngay ? `?ngay=${encodeURIComponent(ngay)}` : "";
  return proxyJsonToBackend(
    "GET",
    "/api/v1/roster/clinical-exceptions" + suffix,
    undefined,
  );
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Dữ liệu gửi lên không hợp lệ." }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/roster/clinical-exceptions", body);
}

export async function DELETE(request: Request) {
  const id = new URL(request.url).searchParams.get("id")?.trim() ?? "";
  if (!id) {
    return NextResponse.json({ error: "Thiếu ngoại lệ cần huỷ." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "DELETE",
    `/api/v1/roster/clinical-exceptions/${encodeURIComponent(id)}`,
    undefined,
  );
}
