// Phiếu khám — proxy mỏng sang `/api/v1/phieu-kham/*` ở FastAPI.
//
//   GET /api/phieu-kham                          → bảy phiếu (tên)
//   GET /api/phieu-kham?form_id=NT[&version=2]   → khung của một phiên bản
//   GET /api/phieu-kham?xem=tham-chieu           → danh mục C / F / thuốc của nguồn
//   GET /api/phieu-kham?visit_id=…&xem=dau-phieu → hành chính + sinh hiệu + tư vấn
//   GET /api/phieu-kham?visit_id=…               → kết quả CLS theo từng chỉ định
//   GET /api/phieu-kham?visit_id=…&xem=phieu[&form_id=NT] → phiếu của lượt
//   GET /api/phieu-kham?visit_id=…&xem=don-thuoc → đơn thuốc của lượt
//   GET /api/phieu-kham?visit_id=…&xem=lich-su[&chon=NT] → lịch sử sửa phiếu (P4A)
//   PUT /api/phieu-kham {thao_tac: "luu-phieu", visit_id, form_id, thay_doi}  (chỉ ô vừa đổi — lát 2)
//   PUT /api/phieu-kham {thao_tac: "luu-phieu", visit_id, form_id, du_lieu, expected_revision}  (cả gói — cũ)
//   PUT /api/phieu-kham {thao_tac: "luu-don", visit_id, dong, ly_do?}
//
// Chỗ lưu: bảng `phieu_kham_luot` (migration 20260924000008). Tầng này chỉ kiểm
// HÌNH của mã để chuỗi tự do không nối được vào đường dẫn backend; luật ở máy chủ.

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
    if (xem === "phieu") {
      const f = q.get("chon");
      if (f !== null && !FORM_RE.test(f)) return sai("Mã phiếu không hợp lệ.");
      const hoi = f ? `?form_id=${f}` : "";
      return proxyJsonToBackend("GET", `/api/v1/phieu-kham/luot/${visitId}/phieu` + hoi, undefined);
    }
    if (xem === "lich-su") {
      const f = q.get("chon");
      if (f !== null && !FORM_RE.test(f)) return sai("Mã phiếu không hợp lệ.");
      const hoi = f ? `?form_id=${f}` : "";
      return proxyJsonToBackend("GET", `/api/v1/phieu-kham/luot/${visitId}/lich-su` + hoi, undefined);
    }
    const duoi =
      xem === "dau-phieu" ? "dau-phieu" : xem === "don-thuoc" ? "don-thuoc" : "ket-qua-chi-dinh";
    return proxyJsonToBackend(
      "GET",
      `/api/v1/phieu-kham/luot/${visitId}/${duoi}`,
      undefined,
    );
  }
  return proxyJsonToBackend("GET", "/api/v1/phieu-kham/dinh-nghia", undefined);
}

export async function PUT(request: Request) {
  const than = (await request.json().catch(() => null)) as {
    thao_tac?: string;
    visit_id?: string;
    [k: string]: unknown;
  } | null;
  if (!than || typeof than.visit_id !== "string" || !UUID_RE.test(than.visit_id)) {
    return sai("Mã lượt khám không hợp lệ.");
  }
  const { thao_tac, visit_id, ...con } = than;
  if (thao_tac === "luu-phieu") {
    return proxyJsonToBackend("PUT", `/api/v1/phieu-kham/luot/${visit_id}/phieu`, con);
  }
  if (thao_tac === "luu-don") {
    return proxyJsonToBackend("PUT", `/api/v1/phieu-kham/luot/${visit_id}/don-thuoc`, con);
  }
  return sai("Thao tác không hợp lệ.");
}
