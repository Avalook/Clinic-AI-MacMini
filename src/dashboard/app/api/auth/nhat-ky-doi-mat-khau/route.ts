// Nhật ký tự đổi mật khẩu cá nhân — chuyển tiếp sang FastAPI.
import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST() {
  const res = await proxyJsonToBackend(
    "POST",
    "/api/v1/me/nhat-ky-doi-mat-khau",
    {},
  );
  if (!res.ok) {
    return res;
  }
  return NextResponse.json({ ok: true });
}
