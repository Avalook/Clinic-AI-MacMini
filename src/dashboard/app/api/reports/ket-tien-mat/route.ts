// /api/reports/ket-tien-mat — KIỂM KÊ TIỀN MẶT KÉT đầu ca – cuối ca (31/10/2026).
//
// GET  ?ngay&ca&co_so                                   → két của đúng một ca
// POST { hanh_dong: "quy_dau", ngay, ca, co_so, tong?, dem?, ly_do? }
// POST { hanh_dong: "dem_cuoi", ngay, ca, co_so, tong?, dem?, ly_do_lech?, nguoi_nhan? }
// POST { hanh_dong: "mo_lai", ngay, ca, co_so, ly_do }
//
// Chỉ chuyển tiếp; ai làm được, dự kiến / lệch, vết — FastAPI quyết.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const s = new URL(request.url).searchParams;
  const q = new URLSearchParams({
    ngay: s.get("ngay") ?? "",
    ca: s.get("ca") ?? "",
    co_so: s.get("co_so") ?? "",
  });
  return proxyJsonToBackend("GET", `/api/v1/reports/ket-tien-mat?${q}`, undefined);
}

export async function POST(request: Request) {
  const b = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!b || typeof b !== "object") {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const { hanh_dong, ngay, ca, co_so } = b;
  if (hanh_dong !== "quy_dau" && hanh_dong !== "dem_cuoi" && hanh_dong !== "mo_lai") {
    return NextResponse.json({ error: "Thao tác không hợp lệ" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/reports/ket-tien-mat", {
    hanh_dong,
    ngay,
    ca,
    co_so,
    tong: b.tong ?? null,
    dem: b.dem ?? null,
    ly_do: b.ly_do ?? null,
    ly_do_lech: b.ly_do_lech ?? null,
    nguoi_nhan: b.nguoi_nhan ?? null,
  });
}
