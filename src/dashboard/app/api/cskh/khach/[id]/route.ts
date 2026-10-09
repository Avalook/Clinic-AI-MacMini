// Khung phải của MỘT khách (27/09/2026) — màn Quản lý khách hàng + Tiếp đón.
//
//   GET  ?xem=tom-tat                  → mọi thứ của khách (lịch, lượt, chỉ định
//                                        chưa làm, tiền, hẹn tái khám)
//   GET  ?xem=ghi-chu                  → sổ ghi chú chung về khách
//   POST { thao_tac: "ghi", noi_dung } → ghi một ghi chú
//   POST { thao_tac: "go", ghi_chu_id } → người ghi gỡ ghi chú của mình
//   GET  ?xem=phan-hoi-thuoc           → lượt có đơn + phản hồi sau dùng thuốc
//   POST { thao_tac: "phan-hoi-thuoc", noi_dung, visit_id?, kenh? } → ghi phản hồi
//   POST { thao_tac: "go-phan-hoi-thuoc", phan_hoi_id } → người ghi gỡ phản hồi
//
// Chỉ là ống dẫn: ai được xem / ghi và mọi luật nằm ở FastAPI
// (`ghi_chu_khach_service.py`, `phan_hoi_thuoc_service.py`). Người ghi lấy từ phiên, không từ trình duyệt.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "@/lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function sai(message: string) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status: 400 });
}

export async function GET(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  if (!UUID_RE.test(id)) return sai("Mã khách không hợp lệ.");
  const xem = new URL(request.url).searchParams.get("xem");
  if (xem === "tom-tat") {
    return proxyJsonToBackend("GET", `/api/v1/cskh/khach/${id}/tom-tat`, undefined);
  }
  if (xem === "ghi-chu") {
    return proxyJsonToBackend("GET", `/api/v1/cskh/khach/${id}/ghi-chu`, undefined);
  }
  if (xem === "phan-hoi-thuoc") {
    return proxyJsonToBackend("GET", `/api/v1/cskh/khach/${id}/phan-hoi-thuoc`, undefined);
  }
  return sai("Thiếu ?xem=tom-tat | ghi-chu | phan-hoi-thuoc.");
}

export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  if (!UUID_RE.test(id)) return sai("Mã khách không hợp lệ.");
  const than = (await request.json().catch(() => null)) as
    | {
        thao_tac?: string;
        noi_dung?: unknown;
        ghi_chu_id?: unknown;
        visit_id?: unknown;
        kenh?: unknown;
        phan_hoi_id?: unknown;
      }
    | null;
  if (than?.thao_tac === "ghi") {
    return proxyJsonToBackend("POST", `/api/v1/cskh/khach/${id}/ghi-chu`, {
      noi_dung: than.noi_dung,
    });
  }
  if (
    than?.thao_tac === "go" &&
    typeof than.ghi_chu_id === "string" &&
    UUID_RE.test(than.ghi_chu_id)
  ) {
    return proxyJsonToBackend("POST", `/api/v1/cskh/ghi-chu/${than.ghi_chu_id}/go`, {});
  }
  if (than?.thao_tac === "phan-hoi-thuoc") {
    // Chuyển tiếp Idempotency-Key (chống ghi trùng khi rớt mạng rồi bấm lại).
    return proxyJsonToBackend(
      "POST",
      `/api/v1/cskh/khach/${id}/phan-hoi-thuoc`,
      { noi_dung: than.noi_dung, visit_id: than.visit_id ?? null, kenh: than.kenh ?? "GOI" },
      request.headers.get("Idempotency-Key") ?? undefined,
    );
  }
  if (
    than?.thao_tac === "go-phan-hoi-thuoc" &&
    typeof than.phan_hoi_id === "string" &&
    UUID_RE.test(than.phan_hoi_id)
  ) {
    return proxyJsonToBackend("POST", `/api/v1/cskh/phan-hoi-thuoc/${than.phan_hoi_id}/go`, {});
  }
  return sai("Thao tác không hợp lệ.");
}
