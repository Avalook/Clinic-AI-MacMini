// Shared plumbing for the four /api/pharmacy write routes (B.3).
//
// Kho thuốc là bốn thao tác gần giống nhau (nhập, xuất, điều chỉnh, huỷ) nên
// bốn route handler dễ trở thành bốn bản sao của cùng một đoạn: đọc JSON, lấy
// Idempotency-Key, chuyển tiếp. Gom vào đây để chỗ nào cũng chặt như nhau —
// đặc biệt là chỗ idempotency, thứ mà quên ở đúng một route là đủ để một lần
// bấm đúp biến thành hai lô hàng.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "./backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value);
}

export function badRequest(message: string): NextResponse {
  return NextResponse.json({ error: message }, { status: 400 });
}

/** Parse the request body, or null if it is not an object. */
export async function readJsonObject(
  request: Request,
): Promise<Record<string, unknown> | null> {
  try {
    const raw = await request.json();
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    return raw as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Forward a pharmacy write to FastAPI, carrying the browser's Idempotency-Key
 * through untouched.
 *
 * The key must come from the client: one generated here would be new on every
 * retry of the same click, which makes the whole mechanism decorative. Missing
 * key = rejected, rather than silently letting a double-click through.
 */
export async function forwardPharmacyWrite(
  request: Request,
  path: string,
  body: unknown,
): Promise<NextResponse> {
  const key = request.headers.get("Idempotency-Key");
  if (!key) return badRequest("Thiếu Idempotency-Key.");
  return proxyJsonToBackend("POST", path, body, { "Idempotency-Key": key });
}
