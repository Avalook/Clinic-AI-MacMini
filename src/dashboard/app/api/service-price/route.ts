// Bảng giá khung dịch vụ/thuốc (service_price) — CRUD scaffold cho màn Thu ngân.
//   POST   { service_code, name, group }                 → thêm 1 dòng giá (unit_price để trống)
//   PATCH  { id, unit_price?, name?, active? }            → sửa giá / tên / bật-tắt
//   DELETE { id }                                         → xoá 1 dòng
// service_price chỉ có RLS SELECT → mọi write phải qua service-role (bypass RLS).
// Chỉ Thu ngân + Quản lý được ghi (khớp canSeeNav("/cashier")).

import { NextResponse } from "next/server";
import { configViaBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { isCashierRole, isTruongCaRole } from "../../../lib/roles";

type PriceGroup = "thuoc" | "dich_vu";

type Auth =
  | { ok: true; admin: SupabaseClient }
  | { ok: false; res: NextResponse };

async function authorize(): Promise<Auth> {
  const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return {
      ok: false,
      res: NextResponse.json(
        { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
        { status: 503 },
      ),
    };
  }
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) {
    return {
      ok: false,
      res: NextResponse.json({ error: "Unauthorised" }, { status: 401 }),
    };
  }
  const role = await getClinicRole();
  if (!isCashierRole(role) && role !== "MANAGEMENT" && !isTruongCaRole(role)) {
    return {
      ok: false,
      res: NextResponse.json(
        { error: "Chỉ Thu ngân / Quản lý / Trưởng ca được sửa bảng giá." },
        { status: 403 },
      ),
    };
  }
  const admin = createClient(SUPABASE_URL, SERVICE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return { ok: true, admin };
}

// Chuẩn hoá unit_price: "" / null / undefined → null; số hợp lệ ≥ 0 → số; sai → undefined (báo lỗi).
function parsePrice(v: unknown): number | null | undefined {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n) || n < 0) return undefined;
  return Math.round(n);
}

interface PostBody {
  service_code?: string;
  name?: string;
  group?: string;
  unit_price?: unknown;
}

export async function POST(request: Request) {
  const auth = await authorize();
  if (!auth.ok) return auth.res;

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

  if (!service_code || !name) {
    return NextResponse.json({ error: "Thiếu mã hoặc tên dịch vụ." }, { status: 400 });
  }
  if (!group) {
    return NextResponse.json({ error: "Nhóm phải là thuoc / dich_vu." }, { status: 400 });
  }
  if (unit_price === undefined) {
    return NextResponse.json({ error: "Đơn giá không hợp lệ." }, { status: 400 });
  }

  // W5 (ADR-0012). Off until CONFIG_VIA_BACKEND=1.
  if (configViaBackend()) {
    return proxyJsonToBackend("POST", "/api/v1/service-prices", {
      service_code,
      name,
      group,
      unit_price,
    });
  }

  const { data, error } = await auth.admin
    .from("service_price")
    .insert({ service_code, name, group, unit_price })
    .select("id")
    .single();

  if (error) {
    // 23505 = unique_violation (trùng mã trong nhóm).
    const status = error.code === "23505" ? 409 : 500;
    return NextResponse.json({ error: error.message }, { status });
  }
  return NextResponse.json({ ok: true, id: data.id });
}

interface PatchBody {
  id?: string;
  unit_price?: unknown;
  name?: string;
  active?: boolean;
}

export async function PATCH(request: Request) {
  const auth = await authorize();
  if (!auth.ok) return auth.res;

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id." }, { status: 400 });

  const patch: Record<string, unknown> = { updated_at: new Date().toISOString() };
  if ("unit_price" in body) {
    const unit_price = parsePrice(body.unit_price);
    if (unit_price === undefined) {
      return NextResponse.json({ error: "Đơn giá không hợp lệ." }, { status: 400 });
    }
    patch.unit_price = unit_price;
  }
  if (typeof body.name === "string" && body.name.trim()) patch.name = body.name.trim();
  if (typeof body.active === "boolean") patch.active = body.active;

  if (configViaBackend()) {
    return proxyJsonToBackend("PATCH", `/api/v1/service-prices/${id}`, {
      name: body.name ?? null,
      ...("unit_price" in body ? { unit_price: body.unit_price ?? null } : {}),
      active: typeof body.active === "boolean" ? body.active : null,
    });
  }

  const { error } = await auth.admin.from("service_price").update(patch).eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

export async function DELETE(request: Request) {
  const auth = await authorize();
  if (!auth.ok) return auth.res;

  let body: { id?: string };
  try {
    body = (await request.json()) as { id?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id." }, { status: 400 });

  if (configViaBackend()) {
    return proxyJsonToBackend("DELETE", `/api/v1/service-prices/${id}`, {});
  }

  const { error } = await auth.admin.from("service_price").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
