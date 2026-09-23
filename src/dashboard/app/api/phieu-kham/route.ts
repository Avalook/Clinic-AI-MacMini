// Phiếu khám — proxy mỏng, CHỈ ĐỌC, sang `/api/v1/phieu-kham/*` ở FastAPI.
//
//   GET /api/phieu-kham                          → bảy phiếu (tên)
//   GET /api/phieu-kham?form_id=NT[&version=2]   → khung của một phiên bản
//   GET /api/phieu-kham?xem=tham-chieu           → danh mục C / F / thuốc của nguồn
//   GET /api/phieu-kham?visit_id=…&xem=dau-phieu → hành chính + sinh hiệu + tư vấn
//   GET /api/phieu-kham?visit_id=…               → kết quả CLS theo từng chỉ định
//
// KHÔNG có đường ghi: phiếu khám gắn vào consultation/visit, chỗ lưu chưa có
// (INTEGRATION_BLOCKER — docs/phieu-kham/TICH-HOP.md). Tầng này chỉ kiểm HÌNH
// của mã để chuỗi tự do không nối được vào đường dẫn backend.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const FORM_RE = /^[A-Z][A-Z_]{1,31}$/;

function sai(message: string) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status: 400 });
}

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams;
  const xem = q.get("xem");
  const formId = q.get("form_id");
  const visitId = q.get("visit_id");

  if (xem === "tham-chieu") {
    return proxyJsonToBackend("GET", "/api/v1/phieu-kham/tham-chieu", undefined);
  }
  if (formId !== null) {
    if (!FORM_RE.test(formId)) return sai("Mã phiếu không hợp lệ.");
    const version = q.get("version");
    if (version !== null && !/^[1-9][0-9]{0,5}$/.test(version)) {
      return sai("Phiên bản không hợp lệ.");
    }
    const hoi = version !== null ? `?version=${version}` : "";
    return proxyJsonToBackend(
      "GET",
      `/api/v1/phieu-kham/dinh-nghia/${formId}${hoi}`,
      undefined,
    );
  }
  if (visitId !== null) {
    if (!UUID_RE.test(visitId)) return sai("Mã lượt khám không hợp lệ.");
    const duoi = xem === "dau-phieu" ? "dau-phieu" : "ket-qua-chi-dinh";
    return proxyJsonToBackend(
      "GET",
      `/api/v1/phieu-kham/luot/${visitId}/${duoi}`,
      undefined,
    );
  }
  return proxyJsonToBackend("GET", "/api/v1/phieu-kham/dinh-nghia", undefined);
}
