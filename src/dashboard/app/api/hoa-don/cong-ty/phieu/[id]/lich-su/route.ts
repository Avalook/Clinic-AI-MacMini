// Lịch sử ghi / sửa / bỏ công ty của một phiếu thu (G5c). Proxy mỏng.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!UUID_RE.test(id)) return NextResponse.json({ error: "Mã phiếu thu không hợp lệ" }, { status: 400 });
  return proxyJsonToBackend("GET", `/api/v1/hoa-don/cong-ty/phieu/${id}/lich-su`, undefined);
}
