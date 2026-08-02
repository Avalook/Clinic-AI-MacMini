// POST /api/lab-result/{id}/send-back — bác sĩ trả kết quả về để chỉnh sửa.
//
// Đối xứng với /review: cùng một quyết định nhìn từ hai phía, nên cùng một
// hàng rào vai. Backend không đụng vào kết quả — nó mở một việc trong
// staff_task để có người chịu trách nhiệm sửa; cổng an toàn (requires_doctor_
// review / is_finalized) giữ nguyên, nên trả lại KHÔNG bao giờ mở đường cho
// kết quả chạy tới bệnh nhân.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";
import { getClinicRole } from "../../../../../lib/clinic-session";
import { canReviewLabResult } from "../../../../../lib/roles";
import { getSupabaseServer } from "../../../../../lib/supabase-server";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Giữ đúng ngưỡng của MIN_SEND_BACK_REASON trong lab_safety_service.py: chặn ở
// đây chỉ để báo lỗi bằng tiếng người, không phải để thay backend quyết định.
const MIN_REASON = 5;

interface SendBackBody {
  clinic_patient_id?: string;
  reason?: string;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Chưa đăng nhập." }, { status: 401 });
  }

  const role = await getClinicRole();
  if (!canReviewLabResult(role)) {
    return NextResponse.json(
      { error: "Chỉ bác sĩ mới trả lại kết quả xét nghiệm." },
      { status: 403 },
    );
  }

  const { id } = await params;
  let body: SendBackBody;
  try {
    body = (await request.json()) as SendBackBody;
  } catch {
    return NextResponse.json({ error: "JSON không hợp lệ." }, { status: 400 });
  }

  const clinicPatientId = (body.clinic_patient_id ?? "").trim();
  if (!UUID_RE.test(id) || !UUID_RE.test(clinicPatientId)) {
    return NextResponse.json(
      { error: "Mã kết quả hoặc bệnh nhân không hợp lệ." },
      { status: 400 },
    );
  }

  const reason = (body.reason ?? "").trim();
  if (reason.length < MIN_REASON) {
    return NextResponse.json(
      { error: "Ghi rõ cần sửa gì thì phòng xét nghiệm mới sửa được." },
      { status: 400 },
    );
  }

  return proxyJsonToBackend("POST", `/api/v1/lab/results/${id}/send-back`, {
    clinic_patient_id: clinicPatientId,
    reason,
  });
}
