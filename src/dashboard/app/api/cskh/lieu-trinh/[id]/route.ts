// Một liệu trình — lịch sử sửa + lệnh của CSKH (08/10/2026).
//
//   GET                                                   → lịch sử sửa (dòng hoàn tác được)
//   POST { thao_tac: "dang-ky", expected_revision, so_buoi?, idempotency_key }
//   POST { thao_tac: "dung",    expected_revision, ly_do?,   idempotency_key }
//   POST { thao_tac: "mo-lai",  expected_revision,           idempotency_key }
//   POST { thao_tac: "hoan-tac", lich_su_id, expected_revision, idempotency_key }
//
// Chỉ là ống dẫn: quyền (crm.manage | booking.create, khối y khoa), bản cũ
// (409 STALE_LIEU_TRINH), bấm hai lần — FastAPI + Postgres quyết.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "@/lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const LENH = new Set(["dang-ky", "dung", "mo-lai", "hoan-tac"]);

function sai(message: string) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status: 400 });
}

export async function GET(_request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  if (!UUID_RE.test(id)) return sai("Mã liệu trình không hợp lệ.");
  return proxyJsonToBackend("GET", `/api/v1/lieu-trinh/${id}/lich-su`, undefined);
}

export async function POST(request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  if (!UUID_RE.test(id)) return sai("Mã liệu trình không hợp lệ.");
  const than = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  const lenh = than?.thao_tac;
  if (typeof lenh !== "string" || !LENH.has(lenh)) return sai("Thao tác không hợp lệ.");
  const conLai: Record<string, unknown> = { ...than };
  delete conLai.thao_tac;
  return proxyJsonToBackend("POST", `/api/v1/lieu-trinh/${id}/${lenh}`, conLai);
}
