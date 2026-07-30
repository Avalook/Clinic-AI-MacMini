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
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
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
  return { role };
}

interface PostBody {
  kind?: string;
  service_name?: string;
  patient_code?: string;
}

export async function POST(request: Request) {
  const g = await guard();
  if ("res" in g) return g.res;

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

  // W5 (ADR-0012). Off until SERVICE_LOG_VIA_BACKEND=1.
  // The patient-code lookup and the insert share one transaction in FastAPI.
  return proxyJsonToBackend("POST", "/api/v1/sono/queue", {
    kind,
    service_name: serviceName,
    patient_code: patientCode || null,
  });
}

interface PatchBody {
  id?: string;
  // (a) SA
  action?: "start" | "finish" | "cancel";
  // (b) XN
  milestone?: "sample" | "sendlab" | "result";
  value?: boolean;
}

export async function PATCH(request: Request) {
  const g = await guard();
  if ("res" in g) return g.res;

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id." }, { status: 400 });

  return proxyJsonToBackend("PATCH", `/api/v1/sono/queue/${id}`, {
    action: body.action ?? null,
    milestone: body.milestone ?? null,
    value: body.value ?? null,
  });
}

export async function DELETE(request: Request) {
  const g = await guard();
  if ("res" in g) return g.res;

  let body: { id?: string };
  try {
    body = (await request.json()) as { id?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id." }, { status: 400 });

  return proxyJsonToBackend("DELETE", `/api/v1/sono/queue/${id}`, {});
}
