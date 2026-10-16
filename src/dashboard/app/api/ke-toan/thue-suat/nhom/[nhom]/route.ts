// Đặt thuế suất GTGT theo NHÓM hàng (G5b/C2). Proxy mỏng — chuẩn hoá + quyền ở máy chủ.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

const NHOM = new Set(["DICH_VU", "THUOC", "VAT_TU"]);

export async function PUT(request: Request, { params }: { params: Promise<{ nhom: string }> }) {
  const { nhom } = await params;
  if (!NHOM.has(nhom)) return NextResponse.json({ error: "Nhóm hàng không có thật." }, { status: 400 });
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("PUT", `/api/v1/ke-toan/thue-suat/nhom/${nhom}`, body);
}
