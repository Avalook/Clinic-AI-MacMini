// Phiếu KẾT QUẢ XN / SIÊU ÂM của 1 dòng service_log — IN khổ NGANG (landscape).
// Đặt NGOÀI nhóm (dashboard) → không sidebar, in sạch. Đọc THẬT qua RLS; client
// SonoResultPrint lo nút In + CSS in landscape. Không sửa dữ liệu (chỉ hiển thị).

import { notFound } from "next/navigation";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { requireClinicRole } from "../../../../lib/clinic-session";
import SonoResultPrint, { type SonoPrintData } from "./SonoResultPrint";

export const dynamic = "force-dynamic";

const one = <T,>(x: T | T[] | null | undefined): T | null =>
  !x ? null : Array.isArray(x) ? (x[0] ?? null) : x;

export default async function SonoPrintPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireClinicRole(); // chặn xem kết quả XN/SA qua URL khi chưa đăng nhập/chọn vai
  const { id } = await params;
  const supabase = await getSupabaseServer();

  const { data } = await supabase
    .from("service_log")
    .select(
      `id, kind, service_name_raw, status, result_text,
       started_at, sent_to_lab_at, finished_at, created_at,
       patient:patient!clinic_patient_id ( full_name, patient_code, date_of_birth, gender, phone_primary )`,
    )
    .eq("id", id)
    .maybeSingle();

  if (!data) notFound();

  const p = one(
    (data as { patient: unknown }).patient as
      | Record<string, unknown>
      | Record<string, unknown>[]
      | null,
  );

  const form: SonoPrintData = {
    kind: (data as { kind: string | null }).kind === "XN" ? "XN" : "SA",
    service_name: (data as { service_name_raw: string | null }).service_name_raw ?? "",
    status: (data as { status: string | null }).status ?? "",
    result_text: (data as { result_text: string | null }).result_text ?? "",
    started_at: (data as { started_at: string | null }).started_at,
    sent_to_lab_at: (data as { sent_to_lab_at: string | null }).sent_to_lab_at,
    finished_at: (data as { finished_at: string | null }).finished_at,
    patient_name: (p?.full_name as string | null) ?? "",
    patient_code: (p?.patient_code as string | null) ?? "",
    date_of_birth: (p?.date_of_birth as string | null) ?? "",
    gender: (p?.gender as string | null) ?? "",
    phone: (p?.phone_primary as string | null) ?? "",
  };

  return <SonoResultPrint data={form} />;
}
