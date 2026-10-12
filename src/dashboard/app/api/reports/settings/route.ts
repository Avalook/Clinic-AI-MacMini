import { proxyJsonToBackend } from "@/lib/backend-proxy";

export async function GET() {
  return proxyJsonToBackend("GET", "/api/v1/reports/settings", undefined);
}

export async function PATCH(request: Request) {
  return proxyJsonToBackend("PATCH", "/api/v1/reports/settings", await request.json());
}
