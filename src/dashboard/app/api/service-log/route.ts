// /api/service-log — luồng Dịch vụ / thủ thuật (điều dưỡng/KTV thực hiện).
//   POST  { service_name, patient_code?, performer? }   → tạo việc (chờ làm).
//   PATCH { id, action: "start" | "finish", result_text? }
//         start  → started_at = now, status 'Đang làm'.
//         finish → finished_at = now, status 'Hoàn tất' (+ result_text).
// Ghi qua service-role (service_log chỉ có RLS SELECT). Gate = canCheckin
// (ĐD/Lễ tân/QL).

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getClinicRole } from "../../../lib/clinic-session";
import { canWriteClinical } from "../../../lib/roles";

interface PostBody {
  service_name?: string;
  patient_code?: string;
  performer?: string;
}
interface PatchBody {
  id?: string;
  action?: "start" | "finish";
  result_text?: string;
}

async function guard() {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) {
    return { res: NextResponse.json({ error: "Unauthorised" }, { status: 401 }) };
  }
  const role = await getClinicRole();
  // Log dịch vụ (SA/XN) = LÂM SÀNG → chỉ Bác sĩ / Điều dưỡng / Thư ký Y khoa.
  // Lễ tân / Quản lý KHÔNG ghi (recap 17/6).
  if (!canWriteClinical(role)) {
    return {
      res: NextResponse.json(
        { error: "Chỉ Bác sĩ / Điều dưỡng / Thư ký Y khoa mới ghi dịch vụ." },
        { status: 403 },
      ),
    };
  }
  return { user, role };
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
  const serviceName = (body.service_name ?? "").trim();
  const patientCode = (body.patient_code ?? "").trim();
  const performer = (body.performer ?? "").trim() || null;
  if (!serviceName) {
    return NextResponse.json({ error: "Thiếu tên dịch vụ." }, { status: 400 });
  }

  // Patient lookup, insert and audit event share one transaction in FastAPI.
  return proxyJsonToBackend("POST", "/api/v1/service-log", {
    service_name: serviceName,
    patient_code: patientCode || null,
    performer,
  });
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
  const action = body.action;
  if (!id || (action !== "start" && action !== "finish")) {
    return NextResponse.json({ error: "Thiếu id hoặc action không hợp lệ." }, { status: 400 });
  }

  return proxyJsonToBackend("PATCH", `/api/v1/service-log/${id}`, {
    action,
    result_text: body.result_text ?? null,
  });
}
