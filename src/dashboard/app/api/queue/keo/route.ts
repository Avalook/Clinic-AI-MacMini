// Lễ tân kéo một khách lên/xuống trong hàng chờ (Tuyền chốt 15/09/2026).
// Proxy mỏng — ai được kéo và mốc mới do FastAPI quyết.

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("POST", "/api/v1/queue/keo", body);
}
