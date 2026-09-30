import { NextRequest } from "next/server";
import { proxyJsonToBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("POST", "/api/v1/ops/traffic", body);
}
