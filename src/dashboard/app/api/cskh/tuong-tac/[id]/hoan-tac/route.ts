// Rút lại một lần chạm bấm nhầm.
//
// KHÔNG XOÁ GÌ. Backend đặt `huy_luc`/`huy_boi_staff_id` trên chính dòng ấy;
// dòng ở lại trong sổ, chỉ thôi được `v_viec_cskh` tính vào. Xem migration
// 20260810000009 để biết vì sao không dùng "bút toán đảo".
//
//   POST (thân rỗng) → { ok: true }

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const tuongTacId = (id ?? "").trim();
  if (!tuongTacId) {
    return NextResponse.json({ error: "Thiếu id thao tác." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/cskh/tuong-tac/${encodeURIComponent(tuongTacId)}/hoan-tac`,
    {},
  );
}
