// /api/reports/cuoi-ngay — Báo cáo cuối ngày (29/09/2026), chỉ đọc.
//
// Chuyển tiếp thẳng `/api/v1/reports/cuoi-ngay` (JSON) hoặc `.csv` (`?xuat=csv`).
// Lớp này chỉ kiểm đăng nhập; quyền `report.view` do FastAPI gác. Ngày không
// đúng dạng thì bỏ — máy chủ tự về hôm nay.

import { NextResponse } from "next/server";
import { getCallerAuthHeaders, proxyJsonToBackend } from "../../../../lib/backend-proxy";

const NGAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const url = new URL(request.url);
  const q = new URLSearchParams();
  for (const k of ["tu", "den"]) {
    const v = url.searchParams.get(k) ?? "";
    if (NGAY_RE.test(v)) q.set(k, v);
  }
  // Xem riêng tiền dịch vụ / tiền thuốc (01/10/2026); rác thì bỏ → cả hai.
  const loai = url.searchParams.get("loai");
  if (loai === "dich_vu" || loai === "thuoc") q.set("loai", loai);
  // Một cơ sở (08/10/2026); rỗng = tất cả. Chuyển nguyên — máy chủ tự xử mã rác
  // (ra số 0), không để lớp này lặng lẽ biến một cơ sở thành "tất cả".
  const coSo = url.searchParams.get("co_so") ?? "";
  if (coSo) q.set("co_so", coSo.slice(0, 64));
  if (url.searchParams.get("xuat") !== "csv") {
    return proxyJsonToBackend("GET", `/api/v1/reports/cuoi-ngay?${q.toString()}`, undefined);
  }
  const headers = await getCallerAuthHeaders();
  const base = process.env.CLINIC_API_URL;
  if (!headers || !base) {
    return NextResponse.json({ error: "Chưa đăng nhập hoặc thiếu CLINIC_API_URL" }, { status: 401 });
  }
  const res = await fetch(`${base}/api/v1/reports/cuoi-ngay.csv?${q.toString()}`, {
    headers,
    cache: "no-store",
  });
  return new NextResponse(res.body, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "text/csv; charset=utf-8",
      "Content-Disposition":
        res.headers.get("Content-Disposition") ?? 'attachment; filename="bao-cao-cuoi-ngay.csv"',
      "Cache-Control": "private, no-store",
    },
  });
}
