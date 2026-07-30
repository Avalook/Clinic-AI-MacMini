// /api/clinical-form — lưu phản hồi FORM khám chuyên khoa (engine config-driven).
//   GET  ?visitId=&serviceCode=         → form_data đã lưu (hoặc {} nếu chưa có).
//   POST { visitId, serviceCode, form_data }  → tạo/cập nhật (upsert) form_data.
//   PATCH = alias POST (cùng upsert).
// Gate: ai có quyền ghi lâm sàng (canWriteClinical: BS, BS siêu âm, TKYK, Điều dưỡng)
// mới ghi. service_code phải có trong registry.
//
// ⚠️ SAFETY GATE FINALIZED (migration 043 append-only đang PENDING → ép Ở APP LAYER):
//   visit.status = 'FINALIZED' → form READ-ONLY, route TỪ CHỐI ghi (409). Sửa hồ sơ
//   đã chốt phải qua luồng đính chính (visit_amendment) — KHÔNG tự chế ở đây, KHÔNG
//   tự đổi visit.status. (Cùng nguyên tắc /api/clinical-record.)

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { canWriteClinical } from "../../../lib/roles";
import { getFormSchema } from "../../../lib/form-schemas";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

// GET: đọc qua RLS (caller). Không cần quyền ghi.
export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const url = new URL(request.url);
  const visitId = (url.searchParams.get("visitId") ?? "").trim();
  const serviceCode = (url.searchParams.get("serviceCode") ?? "").trim();
  if (!visitId || !serviceCode) {
    return NextResponse.json({ error: "Thiếu visitId / serviceCode." }, { status: 400 });
  }

  const { data } = await caller
    .from("clinical_form_response")
    .select("form_data, updated_at")
    .eq("visit_id", visitId)
    .eq("service_code", serviceCode.toUpperCase())
    .maybeSingle();

  return NextResponse.json({
    form_data: (data?.form_data as Record<string, unknown> | null) ?? {},
    updated_at: (data?.updated_at as string | null) ?? null,
  });
}

interface WriteBody {
  visitId?: string;
  serviceCode?: string;
  form_data?: unknown;
}

async function write(request: Request) {
  // 1) Auth + gate bác sĩ.
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const role = await getClinicRole();
  if (!canWriteClinical(role)) {
    return NextResponse.json(
      { error: "Bạn không có quyền điền phiếu khám chuyên khoa." },
      { status: 403 },
    );
  }

  let body: WriteBody;
  try {
    body = (await request.json()) as WriteBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const visitId = (body.visitId ?? "").trim();
  const serviceCode = (body.serviceCode ?? "").trim().toUpperCase();
  if (!visitId || !serviceCode) {
    return NextResponse.json({ error: "Thiếu visitId / serviceCode." }, { status: 400 });
  }
  if (!getFormSchema(serviceCode)) {
    return NextResponse.json(
      { error: `Chưa có cấu hình form cho service_code ${serviceCode}.` },
      { status: 400 },
    );
  }
  const formData =
    body.form_data && typeof body.form_data === "object" && !Array.isArray(body.form_data)
      ? (body.form_data as Record<string, unknown>)
      : {};

  // The FINALIZED gate and the upsert live in FastAPI, in one transaction. The
  // schema check above stays here because lib/form-schemas is the rendering
  // registry; the backend checks the same code against clinical_form_catalogue,
  // which is the same list kept where both sides can read it (ADR-0011).
  return proxyJsonToBackend("PUT", "/api/v1/clinical-forms", {
    visit_id: visitId,
    service_code: serviceCode,
    form_data: formData,
  });
}

export const POST = write;
export const PATCH = write;
