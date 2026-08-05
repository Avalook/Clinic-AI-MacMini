import { NextResponse } from "next/server";
import { fetchFromBackend, proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET() {
  // Đường backend là /api/v1/feature-mode, KHÔNG có đoạn "config": routers/config.py
  // gắn vào app với tags=["config"], mà tags chỉ gom nhóm trong /docs — nó không
  // tạo ra đoạn đường dẫn nào. src/tests/test_dashboard_backend_paths.py canh chỗ này.
  const data = await fetchFromBackend<{ mode: string }>("/api/v1/feature-mode");
  if (!data) {
    return NextResponse.json({ ok: false, mode: "FULL_CLINIC" });
  }
  return NextResponse.json({ ok: true, mode: data.mode ?? "FULL_CLINIC" });
}

export async function PUT(request: Request) {
  const body = await request.json();
  return proxyJsonToBackend("PUT", "/api/v1/feature-mode", body);
}
