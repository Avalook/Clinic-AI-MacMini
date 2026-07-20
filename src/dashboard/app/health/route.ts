import { NextResponse } from "next/server";

// Liveness probe for the compose healthcheck + Uptime Kuma. No DB/auth work —
// just proves the Next.js server is up. Always dynamic (never cached).
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok", service: "dashboard" });
}
