import { NextResponse } from "next/server";
import { fetchFromBackend, proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET() {
  const data = await fetchFromBackend<{ mode: string }>(
    "/api/v1/config/feature-mode",
  );
  if (!data) {
    return NextResponse.json({ ok: false, mode: "FULL_CLINIC" });
  }
  return NextResponse.json({ ok: true, mode: data.mode ?? "FULL_CLINIC" });
}

export async function PUT(request: Request) {
  const body = await request.json();
  return proxyJsonToBackend("PUT", "/api/v1/config/feature-mode", body);
}
