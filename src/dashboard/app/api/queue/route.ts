// Hàng chờ đã check-in hôm nay, ĐÚNG thứ tự gọi (FastAPI xếp). Proxy mỏng.

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

export async function GET(request: Request) {
  const ngay = new URL(request.url).searchParams.get("date");
  if (ngay && /^\d{4}-\d{2}-\d{2}$/.test(ngay)) {
    return proxyJsonToBackend("GET", `/api/v1/queue?date=${ngay}`, null);
  }
  return proxyJsonToBackend("GET", "/api/v1/queue", null);
}
