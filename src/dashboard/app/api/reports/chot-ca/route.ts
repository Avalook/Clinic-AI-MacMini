// /api/reports/chot-ca — KHOÁ SỔ THEO CA (G4c, 14/10/2026).
//
// POST { hanh_dong: "chot", ngay, ca, co_so, ghi_chu? } → chốt ca
// POST { hanh_dong: "mo_khoa", id, ly_do }            → Quản lý mở khoá
//
// Chỉ chuyển tiếp; ai chốt / mở khoá được, số chụp, khoá trùng — FastAPI quyết.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body || typeof body !== "object") {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  if (body.hanh_dong === "chot") {
    const { ngay, ca, co_so, ghi_chu } = body;
    return proxyJsonToBackend("POST", "/api/v1/reports/chot-ca", { ngay, ca, co_so, ghi_chu });
  }
  if (body.hanh_dong === "mo_khoa") {
    const { id, ly_do } = body;
    return proxyJsonToBackend("POST", "/api/v1/reports/chot-ca/mo-khoa", { id, ly_do });
  }
  return NextResponse.json({ error: "Thao tác không hợp lệ" }, { status: 400 });
}
