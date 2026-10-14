// Đặt thuế suất GTGT cho TỪNG mặt hàng (G5b/C2). Proxy mỏng — chuẩn hoá + quyền ở máy chủ.

import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

export async function PUT(request: Request) {
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("PUT", "/api/v1/ke-toan/thue-suat/mat-hang", body);
}
