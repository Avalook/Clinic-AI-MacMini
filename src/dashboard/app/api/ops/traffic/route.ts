import { NextRequest } from "next/server";

import { proxyJsonToBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

// Đi qua proxy chung để gửi kèm phiên đăng nhập nhân viên (30/09/2026): bản gọi
// thẳng FastAPI không kèm phiên từng mở báo cáo lưu lượng cho cả Internet.
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("POST", "/api/v1/ops/traffic", body);
}
