import { proxyJsonToBackend } from "@/lib/backend-proxy";

export async function GET(request: Request) {
  const ngay = new URL(request.url).searchParams.get("ngay") ?? "";
  return proxyJsonToBackend("GET", `/api/v1/reports/access?ngay=${encodeURIComponent(ngay)}`, undefined);
}
