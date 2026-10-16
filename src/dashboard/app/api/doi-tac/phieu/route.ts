// Phiếu kết quả của VIỆC ĐỐI TÁC (16/10/2026) — cùng thân với `/api/phieu`,
// nhưng đi cửa đối tác (`/api/v1/doi-tac/phieu/*`, `get_partner_identity`): tài
// khoản đối tác điền phiếu theo mẫu của đúng việc của mình rồi Trả kết quả.
//
//   POST { thao_tac: "mo", du_lieu: { service_order_id, form_id } }
//   POST { thao_tac: "luu"|"hoan-tat"|"mo-sua"|"huy-sua", phieu_id, du_lieu }
//
// Không chép luật nào: ai được điền (việc của bàn đối tác) — `doi_quyen_dien`.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const THEO_PHIEU: Record<string, (id: string) => string> = {
  luu: (id) => `/api/v1/doi-tac/phieu/${id}/luu`,
  "hoan-tat": (id) => `/api/v1/doi-tac/phieu/${id}/hoan-tat`,
  "mo-sua": (id) => `/api/v1/doi-tac/phieu/${id}/mo-sua`,
  "huy-sua": (id) => `/api/v1/doi-tac/phieu/${id}/huy-sua`,
};

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
    return proxyJsonToBackend("POST", "/api/v1/doi-tac/phieu/mo", than.du_lieu ?? {});
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
