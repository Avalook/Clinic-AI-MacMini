// Nhà thuốc — Tư vấn dùng thuốc (image_11).
// Dược sĩ hướng dẫn người bệnh cách dùng thuốc trước khi bàn giao.

import { getSupabaseServer } from "../../../../lib/supabase-server";
import { requireNavAccess } from "../../../../lib/clinic-session";
import ConsultBoard from "./ConsultBoard";

export const dynamic = "force-dynamic";

export default async function PharmacyConsultPage() {
  await requireNavAccess("/pharmacy/consult");
  const supabase = await getSupabaseServer();

  const { data: records, error } = await supabase
    .from("prescription")
    .select(
      `id, source_ref, drug_name_raw, dosage_instructions, quantity, quantity_note, caution, created_at,
       patient:clinic_patient_id(full_name, phone_primary)`,
    )
    // CHỜ TƯ VẤN = còn việc. Bản trước đọc cả bảng không lọc, nên đơn từ nhiều
    // tháng trước nằm mãi trong danh sách "chờ" — và danh sách chờ nào cũng
    // chỉ dài thêm thì không ai còn nhìn nó nữa.
    .is("closed_at", null)
    .order("created_at", { ascending: false })
    .limit(100);

  if (error) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được đơn thuốc: {error.message}
      </div>
    );
  }

  interface PatientRaw {
    full_name: string | null;
    phone_primary: string | null;
  }
  type Raw = Omit<(typeof records)[number], "patient"> & {
    patient: PatientRaw[] | null;
  };
  const normalized = (records ?? []).map((r: Raw) => ({
    ...r,
    patient: r.patient?.[0] ?? null,
  }));

  return <ConsultBoard records={normalized} />;
}