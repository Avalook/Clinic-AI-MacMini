import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";
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

  // Cửa quyền là việc của BACKEND (lab.py _REVIEW_GUARD = quyền
  // result.review.approve) — proxy chỉ kiểm đăng nhập (kiểm toán 27/09/2026:
  // cửa vai "bác sĩ" ở đây chặn người đã được cấp khối duyệt kết quả).

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

