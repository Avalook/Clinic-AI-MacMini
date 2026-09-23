// Phiếu kết quả — proxy mỏng sang Form Template Engine ở FastAPI.
//
//   GET  /api/phieu                      → các biểu mẫu đang dùng
//   POST /api/phieu  { thao_tac: "mo" }  → mở (hoặc lấy lại) phiếu của chỉ định
//   POST /api/phieu  { thao_tac: "luu"|"hoan-tat"|"mo-sua"|"huy-sua", phieu_id }
//
// Không chép luật nào: "Hoàn tất = xác nhận toàn bộ", nguồn giá trị hợp lệ,
// ai được điền (`result.form.fill`) đều nằm trong service. Tầng này chỉ kiểm
// hình dạng mã để chuỗi tự do không nối được vào URL backend.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Thao tác cần mã phiếu trên đường dẫn. */
const THEO_PHIEU: Record<string, (id: string) => string> = {
  luu: (id) => `/api/v1/phieu/${id}/luu`,
  "hoan-tat": (id) => `/api/v1/phieu/${id}/hoan-tat`,
  // Mở lại phiếu đã hoàn tất để sửa. Không có đường nào "xoá kết quả" —
  // sửa thì được, mất dấu thì không.
  "mo-sua": (id) => `/api/v1/phieu/${id}/mo-sua`,
  // Bỏ bản sửa đang gõ dở. KHÔNG có đường nào xoá kết quả chính thức.
  "huy-sua": (id) => `/api/v1/phieu/${id}/huy-sua`,
};

export async function GET(request: Request) {
  // Xem phiếu ĐÃ HOÀN TẤT của một chỉ định — chỉ đọc (Bàn khám, nhóm 3 nợ).
  const xem = new URL(request.url).searchParams.get("xem") ?? "";
  if (xem) {
    if (!UUID_RE.test(xem)) {
      return NextResponse.json(
        { error: "BAD_REQUEST", message: "Mã chỉ định không hợp lệ." },
        { status: 400 },
      );
    }
    return proxyJsonToBackend("GET", `/api/v1/phieu/xem/${xem}`, undefined);
  }
  return proxyJsonToBackend("GET", "/api/v1/bieu-mau", undefined);
}

export async function POST(request: Request) {
  let than: { thao_tac?: unknown; phieu_id?: unknown; du_lieu?: unknown };
  try {
    than = await request.json();
  } catch {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Dữ liệu gửi lên không đọc được." },
      { status: 400 },
    );
  }
  const ten = typeof than.thao_tac === "string" ? than.thao_tac : "";

  if (ten === "mo") {
    return proxyJsonToBackend("POST", "/api/v1/phieu/mo", than.du_lieu ?? {});
  }

  const duong = THEO_PHIEU[ten];
  const id = typeof than.phieu_id === "string" ? than.phieu_id : "";
  if (!duong || !UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Thao tác hoặc mã phiếu không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend("POST", duong(id), than.du_lieu ?? {});
}
