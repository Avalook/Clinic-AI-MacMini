// Dọn dữ liệu khách thử — proxy mỏng sang FastAPI cho màn
// `/settings/don-du-lieu-thu` (30/09/2026).
//
//   GET  /api/don-du-lieu-thu?ngay=YYYY-MM-DD   → khách có lịch / lượt ngày ấy
//   POST {thao_tac: "xem-truoc", khach: [id]}    → số dòng sẽ xoá + khách bị chặn
//   POST {thao_tac: "xoa", khach: [id], xac_nhan: "XOA"}
//
// Tầng này chỉ kiểm HÌNH (ngày, uuid). Quyền (`permission.manage`), khách nào bị
// chặn, chữ xác nhận — máy chủ quyết.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const NGAY_RE = /^\d{4}-\d{2}-\d{2}$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function sai(message: string) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status: 400 });
}

export async function GET(request: Request) {
  const ngay = new URL(request.url).searchParams.get("ngay") ?? "";
  const q = NGAY_RE.test(ngay) ? `?ngay=${ngay}` : "";
  return proxyJsonToBackend("GET", `/api/v1/quan-tri/don-du-lieu-thu${q}`, undefined);
}

export async function POST(request: Request) {
  let b: { thao_tac?: unknown; khach?: unknown; xac_nhan?: unknown };
  try {
    b = (await request.json()) as typeof b;
  } catch {
    return sai("Dữ liệu gửi lên không đọc được.");
  }
  const khach = Array.isArray(b.khach) ? b.khach.map((x) => String(x)) : [];
  if (khach.length === 0 || khach.length > 500 || !khach.every((x) => UUID_RE.test(x))) {
    return sai("Danh sách khách không hợp lệ.");
  }
  if (b.thao_tac === "xem-truoc") {
    return proxyJsonToBackend("POST", "/api/v1/quan-tri/don-du-lieu-thu/xem-truoc", { khach });
  }
  if (b.thao_tac === "xoa") {
    const xacNhan = typeof b.xac_nhan === "string" ? b.xac_nhan.slice(0, 20) : "";
    return proxyJsonToBackend(
      "POST",
      "/api/v1/quan-tri/don-du-lieu-thu/xoa",
      { khach, xac_nhan: xacNhan },
      request.headers.get("Idempotency-Key") ?? undefined,
    );
  }
  return sai("Không rõ thao tác.");
}
