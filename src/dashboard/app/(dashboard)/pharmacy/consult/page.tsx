// Tư vấn dùng thuốc — dòng thuốc còn việc. Đọc qua backend
// `GET /api/v1/pharmacy/cho-tu-van` (24/09/2026; trước đọc thẳng `prescription`
// bằng Supabase). Chỉ dòng chưa chốt, chưa bị đính chính (CP6).

import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { requireNavAccess } from "../../../../lib/clinic-session";
import ConsultBoard from "./ConsultBoard";

export const dynamic = "force-dynamic";

interface DongChoTuVan {
  id: string;
  source_ref: string | null;
  drug_name_raw: string | null;
  dosage_instructions: string | null;
  quantity: string | null;
  quantity_note: string | null;
  caution: string | null;
  created_at: string | null;
  full_name: string | null;
  phone_primary: string | null;
}

export default async function PharmacyConsultPage() {
  await requireNavAccess("/pharmacy/consult");
  const data = await fetchFromBackend<{ items: DongChoTuVan[] }>(
    "/api/v1/pharmacy/cho-tu-van",
  );
  if (!data) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được đơn thuốc (máy chủ không trả lời hoặc tài khoản chưa có quyền xem
        nhà thuốc).
      </div>
    );
  }
  const records = data.items.map(({ full_name, phone_primary, ...r }) => ({
    ...r,
    patient: { full_name, phone_primary },
  }));
  return <ConsultBoard records={records} />;
}
