// /api/lam-them — nút "+ dịch vụ" (làm thêm tại quầy) ở Tiếp đón / Đo sinh hiệu
// và danh sách nút của quản lý (01/10/2026).
//
// Chỉ chuyển tiếp. Quyền (lego Tiếp đón / Sinh hiệu cho nút, `config.wiring.manage`
// cho danh sách) và mọi luật nằm ở FastAPI (`lam_them_tai_quay_service.py`).

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";

const NOI = new Set(["tiep_don", "sinh_hieu"]);
// Mã dịch vụ nối vào đường dẫn: chỉ chữ / số / gạch — không mở đường backend lạ.
const MA_RE = /^[A-Za-z0-9_.-]{1,64}$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function coPhien(): Promise<boolean> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return Boolean(user);
}

function sai(): NextResponse {
  return NextResponse.json(
    { error: "BAD_REQUEST", message: "Thao tác không hợp lệ." },
    { status: 400 },
  );
}

export async function GET(request: Request) {
  if (!(await coPhien())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const q = new URL(request.url).searchParams;
  if (q.get("cau_hinh") === "1") {
    return proxyJsonToBackend("GET", "/api/v1/lam-them/cau-hinh", undefined);
  }
  const noi = q.get("noi") ?? "";
  if (!NOI.has(noi)) return sai();
  // Mã lượt rác bị bỏ ở đây (máy chủ cũng bỏ) — chỉ UUID đi tiếp.
  const luot = (q.get("luot") ?? "")
    .split(",")
    .filter((x) => UUID_RE.test(x))
    .slice(0, 300)
    .join(",");
  return proxyJsonToBackend(
    "GET",
    `/api/v1/lam-them/nut?noi=${noi}&luot=${encodeURIComponent(luot)}`,
    undefined,
  );
}

export async function POST(request: Request) {
  if (!(await coPhien())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const than = (await request.json().catch(() => null)) as
    | { thao_tac?: string; service_code?: string; du_lieu?: unknown }
    | null;
  const ma = typeof than?.service_code === "string" ? than.service_code : "";
  switch (than?.thao_tac) {
    case "dat":
      return proxyJsonToBackend("POST", "/api/v1/lam-them/dat", than?.du_lieu ?? {});
    case "dong-dich-vu":
      return proxyJsonToBackend("POST", "/api/v1/lam-them/dong-dich-vu", than?.du_lieu ?? {});
    case "hoan-tac-dich-vu":
      return proxyJsonToBackend("POST", "/api/v1/lam-them/hoan-tac-dich-vu", than?.du_lieu ?? {});
    case "luu-muc":
      if (!MA_RE.test(ma)) break;
      return proxyJsonToBackend(
        "PUT",
        `/api/v1/lam-them/cau-hinh/${encodeURIComponent(ma)}`,
        than?.du_lieu ?? {},
      );
    case "bo-muc":
      if (!MA_RE.test(ma)) break;
      return proxyJsonToBackend(
        "DELETE",
        `/api/v1/lam-them/cau-hinh/${encodeURIComponent(ma)}`,
        undefined,
      );
    case "doi-thu-tu":
      return proxyJsonToBackend(
        "PUT",
        "/api/v1/lam-them/cau-hinh-thu-tu",
        than?.du_lieu ?? {},
      );
  }
  return sai();
}
