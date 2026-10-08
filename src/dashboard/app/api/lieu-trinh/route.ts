// /api/lieu-trinh — liệu trình điều trị nhiều buổi (08/10/2026). Chỉ chuyển
// tiếp xuống FastAPI theo DANH SÁCH TRẮNG; quyền, con số, trạng thái và nút nào
// bấm được đều do backend (`services/lieu_trinh_service.py`, `lieu_trinh_tien.py`).
// Mã trên đường dẫn phải là UUID — chuỗi tự do nối vào URL là mở đường lạ.
//
//   GET  ?xem=theo-luot&id=<lượt>     thẻ liệu trình ở hồ sơ khám
//   GET  ?xem=quay&id=<lượt>          khối "Liệu trình" ở quầy thu dịch vụ
//   GET  ?xem=lich-su&id=<liệu trình> "Lịch sử sửa"
//   GET  ?xem=chi-tiet&id=<liệu trình> | ?xem=theo-khach&id=<khách>
//   GET  ?xem=chip&luot=v1,v2 | ?xem=cskh&loai=…&qua_ngay=…&ca_co_lich=…
//   POST { thao_tac, id?, du_lieu }   (du_lieu mang idempotency_key)

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const V1 = "/api/v1/lieu-trinh";

/** `?xem=` → đường backend cần một mã UUID. */
const DOC_THEO_ID: Record<string, (id: string) => string> = {
  "theo-luot": (id) => `${V1}/theo-luot/${id}`,
  quay: (id) => `${V1}/quay/${id}`,
  "lich-su": (id) => `${V1}/${id}/lich-su`,
  "chi-tiet": (id) => `${V1}/${id}`,
  "theo-khach": (id) => `${V1}/theo-khach/${id}`,
};

/** Lệnh có mã trên đường dẫn (id = liệu trình / dòng trả trước). */
const LENH_THEO_ID: Record<string, (id: string) => string> = {
  "dieu-chinh": (id) => `${V1}/${id}/dieu-chinh`,
  "dang-ky": (id) => `${V1}/${id}/dang-ky`,
  dung: (id) => `${V1}/${id}/dung`,
  "mo-lai": (id) => `${V1}/${id}/mo-lai`,
  "hoan-tac": (id) => `${V1}/${id}/hoan-tac`,
  "bo-tra-truoc": (id) => `${V1}/tra-truoc/${id}/bo`,
};

/** Lệnh không có mã trên đường dẫn (mã nằm trong thân). */
const LENH: Record<string, string> = {
  tao: V1,
  gan: "/api/v1/lieu-trinh-buoi/gan",
  go: "/api/v1/lieu-trinh-buoi/go",
  "tra-truoc": `${V1}/tra-truoc`,
};

async function daDangNhap(): Promise<boolean> {
  const db = await getSupabaseServer();
  const {
    data: { user },
  } = await db.auth.getUser();
  return Boolean(user);
}

function sai(message: string) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status: 400 });
}

export async function GET(request: Request) {
  if (!(await daDangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const sp = new URL(request.url).searchParams;
  const xem = sp.get("xem") ?? "";
  const theoId = DOC_THEO_ID[xem];
  if (theoId) {
    const id = sp.get("id") ?? "";
    if (!UUID.test(id)) return sai("Mã không hợp lệ.");
    return proxyJsonToBackend("GET", theoId(id), undefined);
  }
  if (xem === "chip") {
    const q = new URLSearchParams({ luot: (sp.get("luot") ?? "").slice(0, 12000) });
    return proxyJsonToBackend("GET", `${V1}/chip?${q.toString()}`, undefined);
  }
  if (xem === "cskh") {
    const q = new URLSearchParams({ loai: (sp.get("loai") ?? "").slice(0, 20) });
    const qn = sp.get("qua_ngay");
    if (qn) q.set("qua_ngay", qn.slice(0, 10));
    if (sp.get("ca_co_lich") === "true") q.set("ca_co_lich", "true");
    return proxyJsonToBackend("GET", `${V1}/cskh?${q.toString()}`, undefined);
  }
  return sai("Bảng cần đọc không hợp lệ.");
}

export async function POST(request: Request) {
  if (!(await daDangNhap())) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const than = (await request.json().catch(() => null)) as {
    thao_tac?: unknown;
    id?: unknown;
    du_lieu?: unknown;
  } | null;
  const tt = typeof than?.thao_tac === "string" ? than.thao_tac : "";
  const duLieu = than?.du_lieu && typeof than.du_lieu === "object" ? than.du_lieu : {};
  const theoId = LENH_THEO_ID[tt];
  if (theoId) {
    const id = typeof than?.id === "string" ? than.id : "";
    if (!UUID.test(id)) return sai("Mã không hợp lệ.");
    return proxyJsonToBackend("POST", theoId(id), duLieu);
  }
  const duong = LENH[tt];
  if (!duong) return sai("Thao tác không hợp lệ.");
  return proxyJsonToBackend("POST", duong, duLieu);
}
