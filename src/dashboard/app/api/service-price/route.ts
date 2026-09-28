// Bảng giá khung dịch vụ/thuốc (service_price) — CRUD scaffold cho màn Bảng giá.
//   GET    ?xem=phong-lam                                  → phòng làm (node) để chọn
//   POST   { service_code?, ma_kiotviet?, name, group, unit_price?, node_code?, billing_owner? }
//   PATCH  { id, unit_price?, name?, active?, ma_kiotviet?, node_code?, billing_owner? }
//
// BÊN THU (29/09/2026): CLINIC | EXTERNAL_PARTNER, chọn tay ở Bảng giá. Tầng này
// chỉ kiểm HÌNH (một trong hai chữ); máy chủ giữ lựa chọn khỏi bị phòng làm ghi đè.
//   DELETE { id }
//
// QUYỀN Ở MÁY CHỦ (26/09/2026). Bản cũ tự chặn theo VAI (Thu ngân / Quản lý /
// Trưởng ca) ở đây — người được bật lego "Bảng giá" mà không mang ba vai ấy bị
// chặn oan dù máy chủ cho phép. Tầng này chỉ kiểm đăng nhập + HÌNH dữ liệu;
// máy chủ hỏi quyền `price.service.manage`.
//
// MÃ PHÒNG KHÁM (mã SP KiotViet) là mã chuẩn để tra/nhập/hiển thị; `service_code`
// giữ làm khoá ẩn — bỏ trống khi có mã phòng khám thì máy chủ tự sinh `KV_<mã>`.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";

type PriceGroup = "thuoc" | "dich_vu";

const MA_KV_RE = /^[A-Za-z0-9_-]{1,32}$/;
const NODE_RE = /^[A-Z0-9_-]{1,64}$/;

async function daDangNhap(): Promise<NextResponse | null> {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  return user ? null : NextResponse.json({ error: "Unauthorised" }, { status: 401 });
}

function sai(message: string) {
  return NextResponse.json({ error: message }, { status: 400 });
}

// Chuẩn hoá unit_price: "" / null / undefined → null; số hợp lệ ≥ 0 → số; sai → undefined (báo lỗi).
function parsePrice(v: unknown): number | null | undefined {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n) || n < 0) return undefined;
  return Math.round(n);
}

/** "" / null → null (gỡ mã); hợp lệ → chuỗi đã bỏ khoảng trắng; sai → undefined. */
function parseMaKv(v: unknown): string | null | undefined {
  if (v === null || v === undefined) return null;
  if (typeof v !== "string") return undefined;
  const s = v.trim();
  if (!s) return null;
  return MA_KV_RE.test(s) ? s : undefined;
}

/** Bên thu: "" / null → null (theo phòng làm); CLINIC | EXTERNAL_PARTNER; sai → undefined. */
function parseBenThu(v: unknown): string | null | undefined {
  if (v === null || v === undefined || v === "") return null;
  return v === "CLINIC" || v === "EXTERNAL_PARTNER" ? v : undefined;
}

function parseNode(v: unknown): string | null | undefined {
  if (v === null || v === undefined || v === "") return null;
  return typeof v === "string" && NODE_RE.test(v) ? v : undefined;
}

export async function GET(request: Request) {
  const chan = await daDangNhap();
  if (chan) return chan;
  const xem = new URL(request.url).searchParams.get("xem");
  if (xem !== "phong-lam") return sai("Không rõ cần đọc gì.");
  return proxyJsonToBackend("GET", "/api/v1/service-prices/phong-lam", undefined);
}

interface PostBody {
  service_code?: string;
  ma_kiotviet?: unknown;
  name?: string;
  group?: string;
  unit_price?: unknown;
  node_code?: unknown;
  billing_owner?: unknown;
}

export async function POST(request: Request) {
  const chan = await daDangNhap();
  if (chan) return chan;

  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const service_code = (body.service_code ?? "").trim();
  const name = (body.name ?? "").trim();
  const group = body.group === "thuoc" || body.group === "dich_vu" ? (body.group as PriceGroup) : null;
  const unit_price = parsePrice(body.unit_price);
  const ma_kiotviet = parseMaKv(body.ma_kiotviet);
  const node_code = parseNode(body.node_code);
  const billing_owner = parseBenThu(body.billing_owner);

  if ((!service_code && !ma_kiotviet) || !name) {
    return sai("Thiếu mã phòng khám (hoặc mã dịch vụ) hoặc tên.");
  }
  if (!group) return sai("Nhóm phải là thuoc / dich_vu.");
  if (unit_price === undefined) return sai("Đơn giá không hợp lệ.");
  if (ma_kiotviet === undefined) return sai("Mã phòng khám chỉ gồm chữ, số, gạch.");
  if (node_code === undefined) return sai("Phòng làm không hợp lệ.");
  if (billing_owner === undefined) return sai("Bên thu không hợp lệ.");

  // Mã trùng là 409 từ FastAPI, không phải một dòng thứ hai không ai để ý.
  return proxyJsonToBackend("POST", "/api/v1/service-prices", {
    service_code,
    name,
    group,
    unit_price,
    ma_kiotviet,
    node_code,
    ...(billing_owner ? { billing_owner } : {}),
  });
}

interface PatchBody {
  id?: string;
  unit_price?: unknown;
  name?: string;
  active?: boolean;
  ma_kiotviet?: unknown;
  node_code?: unknown;
  billing_owner?: unknown;
}

export async function PATCH(request: Request) {
  const chan = await daDangNhap();
  if (chan) return chan;

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return sai("Thiếu id.");
  if ("unit_price" in body && parsePrice(body.unit_price) === undefined) {
    return sai("Đơn giá không hợp lệ.");
  }
  const ma = "ma_kiotviet" in body ? parseMaKv(body.ma_kiotviet) : null;
  if (ma === undefined) return sai("Mã phòng khám chỉ gồm chữ, số, gạch.");
  const node = "node_code" in body ? parseNode(body.node_code) : null;
  if (node === undefined) return sai("Phòng làm không hợp lệ.");
  const ben = "billing_owner" in body ? parseBenThu(body.billing_owner) : null;
  if (ben === undefined) return sai("Bên thu không hợp lệ.");

  return proxyJsonToBackend("PATCH", `/api/v1/service-prices/${id}`, {
    name: body.name ?? null,
    ...("unit_price" in body ? { unit_price: body.unit_price ?? null } : {}),
    active: typeof body.active === "boolean" ? body.active : null,
    ...("ma_kiotviet" in body ? { ma_kiotviet: ma } : {}),
    ...("node_code" in body && node ? { node_code: node } : {}),
    ...(ben ? { billing_owner: ben } : {}),
  });
}

export async function DELETE(request: Request) {
  const chan = await daDangNhap();
  if (chan) return chan;

  let body: { id?: string };
  try {
    body = (await request.json()) as { id?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return sai("Thiếu id.");

  return proxyJsonToBackend("DELETE", `/api/v1/service-prices/${id}`, {});
}
