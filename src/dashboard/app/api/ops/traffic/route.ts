import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const apiBase = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");
  if (!apiBase) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => ({}));
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  try {
    const res = await fetch(`${apiBase}/api/v1/ops/traffic`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    const msg =
      err instanceof Error ? err.message : "Không thể kết nối tới máy chủ backend.";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
