// /api/sono — tiến trình màn ĐD siêu âm trên service_log (T-DASH-DDSA-A01).
//   POST  { kind: "SA"|"XN", service_name, patient_code? }      → thêm dòng vào hàng đợi
//   PATCH (a) SA:  { id, action: "start"|"finish"|"cancel" }    → đổi trạng thái dòng SA
//   PATCH (b) XN:  { id, milestone: "sample"|"sendlab"|"result", value: boolean }
//                  → toggle 3 mốc: lấy mẫu=started_at · gửi lab=sent_to_lab_at · có KQ=finished_at
//   DELETE { id }                                               → xoá dòng khỏi hàng đợi
// Ghi qua service-role (service_log chỉ có RLS SELECT). Gate = ĐD siêu âm + Quản lý.
// KHÔNG đụng lab_result, KHÔNG ghi visit.status (FINALIZED là gate của bác sĩ).

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { getClinicRole } from "../../../lib/clinic-session";

async function guard() {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) {
    return { res: NextResponse.json({ error: "Unauthorised" }, { status: 401 }) };
  }
  const role = await getClinicRole();
  if (role !== "NURSE_ULTRASOUND" && role !== "MANAGEMENT") {
    return {
      res: NextResponse.json(
        { error: "Chỉ ĐD siêu âm / Quản lý mới ghi tiến trình." },
        { status: 403 },
      ),
    };
  }
  const db = getSupabaseService();
  if (!db) {
    return {
      res: NextResponse.json(
        { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
        { status: 503 },
      ),
    };
  }
  return { role, db };
}

interface PostBody {
  kind?: string;
  service_name?: string;
  patient_code?: string;
}

export async function POST(request: Request) {
  const g = await guard();
  if ("res" in g) return g.res;
  const { role, db } = g;

  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const kind = body.kind === "SA" || body.kind === "XN" ? body.kind : null;
  const serviceName = (body.service_name ?? "").trim();
  const patientCode = (body.patient_code ?? "").trim();
  if (!kind) {
    return NextResponse.json({ error: "kind phải là SA / XN." }, { status: 400 });
  }
  if (!serviceName) {
    return NextResponse.json({ error: "Thiếu tên dịch vụ." }, { status: 400 });
  }

  // Mã BN tuỳ chọn → resolve clinic_patient_id.
  let clinicPatientId: string | null = null;
  if (patientCode) {
    const { data: p } = await db
      .from("patient")
      .select("clinic_patient_id")
      .eq("patient_code", patientCode)
      .maybeSingle();
    clinicPatientId = (p?.clinic_patient_id as string | null) ?? null;
    if (!clinicPatientId) {
      return NextResponse.json(
        { error: `Không tìm thấy bệnh nhân mã ${patientCode}.` },
        { status: 404 },
      );
    }
  }

  const sourceRef = `dash-sono-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const { data, error } = await db
    .from("service_log")
    .insert({
      source_ref: sourceRef,
      kind,
      clinic_patient_id: clinicPatientId,
      service_name_raw: serviceName,
      status: "WAITING",
      ordered_at: new Date().toISOString(),
      created_by_text: `${role} · dashboard:sono`,
      patient_link_raw: patientCode || null,
    })
    .select("id")
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, id: data.id });
}

interface PatchBody {
  id?: string;
  // (a) SA
  action?: "start" | "finish" | "cancel";
  // (b) XN
  milestone?: "sample" | "sendlab" | "result";
  value?: boolean;
}

// (b) XN milestone → cột timestamp tương ứng.
const XN_COLUMN: Record<string, string> = {
  sample: "started_at", // lấy mẫu
  sendlab: "sent_to_lab_at", // gửi lab
  result: "finished_at", // có KQ
};

export async function PATCH(request: Request) {
  const g = await guard();
  if ("res" in g) return g.res;
  const { db } = g;

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id." }, { status: 400 });

  const now = new Date().toISOString();
  const patch: Record<string, unknown> = { updated_at: now };

  if (body.action) {
    // (a) SA: start → finish → cancel.
    if (body.action === "start") {
      patch.started_at = now;
      patch.status = "IN_PROGRESS";
    } else if (body.action === "finish") {
      patch.finished_at = now;
      patch.status = "DONE";
    } else if (body.action === "cancel") {
      patch.status = "CANCELLED";
    } else {
      return NextResponse.json({ error: "action không hợp lệ." }, { status: 400 });
    }
  } else if (body.milestone) {
    // (b) XN: toggle có/chưa từng mốc.
    const col = XN_COLUMN[body.milestone];
    if (!col) {
      return NextResponse.json({ error: "milestone không hợp lệ." }, { status: 400 });
    }
    patch[col] = body.value ? now : null;
  } else {
    return NextResponse.json(
      { error: "Cần action (SA) hoặc milestone (XN)." },
      { status: 400 },
    );
  }

  const { data, error } = await db
    .from("service_log")
    .update(patch)
    .eq("id", id)
    .select("id")
    .maybeSingle();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data) return NextResponse.json({ error: "Không tìm thấy dòng." }, { status: 404 });
  return NextResponse.json({ ok: true });
}

export async function DELETE(request: Request) {
  const g = await guard();
  if ("res" in g) return g.res;
  const { db } = g;

  let body: { id?: string };
  try {
    body = (await request.json()) as { id?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id." }, { status: 400 });

  const { error } = await db.from("service_log").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
