import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";
import { getClinicRole } from "../../../../../lib/clinic-session";
import { isDoctorRole } from "../../../../../lib/roles";
import { getSupabaseServer } from "../../../../../lib/supabase-server";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

interface ReviewBody {
  clinic_patient_id?: string;
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
  if (!isDoctorRole(role)) {
    return NextResponse.json(
      { error: "Chỉ bác sĩ mới duyệt kết quả xét nghiệm." },
      { status: 403 },
    );
  }

  const { id } = await params;
  let body: ReviewBody;
  try {
    body = (await request.json()) as ReviewBody;
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

  return proxyJsonToBackend(
    "POST",
    `/api/v1/lab/results/${id}/review`,
    { clinic_patient_id: clinicPatientId },
  );
}

