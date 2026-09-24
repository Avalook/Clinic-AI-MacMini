// Đặt lịch CSKH — Hub đặt lịch hẹn sử dụng dữ liệu thật từ DB.

import { fetchFromBackend } from "../../../lib/backend-proxy";
import { requireNavAccess } from "../../../lib/clinic-session";
import BookingHub, {
  type PatientLite,
  type ApptLite,
} from "./BookingHub";
import type { Option, ProvinceOpt } from "../patients/new/NewPatientForm";
import { listBookableDoctors } from "../../../lib/doctors-server";
import { getCurrentStaff } from "../../../lib/current-staff";
import { vaiLamViec } from "../../../lib/clinic-session";
import { canWriteIntake } from "../../../lib/roles";

export const dynamic = "force-dynamic";

export default async function AppointmentsPage() {
  await requireNavAccess("/appointments");
  // 24/09/2026: một lần đọc ở backend (`GET /api/v1/appointments/hub-dat-lich`)
  // thay vì tự đọc 6 bảng bằng Supabase — kể cả luật "khách khám lần mấy /
  // đang trong chuỗi tái khám" (services/man_dat_lich_doc.py). Ở đây chỉ còn
  // trình bày nhãn.
  const [hub, docRes] = await Promise.all([
    fetchFromBackend<{
      locations: { id: string; name: string }[];
      services: { id: string; name: string | null }[];
      provinces: { code: string; name: string; full_name: string }[];
      patients: PatientLite[];
      appts: ApptLite[];
      lan_kham: Record<string, { soLanKham: number; laTaiKham: boolean }>;
    }>("/api/v1/appointments/hub-dat-lich"),
    listBookableDoctors(),
  ]);

  const locations: Option[] = (hub?.locations ?? []).map((r) => ({
    id: r.id,
    label: r.name,
  }));
  const services: Option[] = (hub?.services ?? [])
    .filter((r) => (r.name ?? "").trim().toUpperCase() !== "FREE")
    .map((r) => ({
      id: r.id,
      label: (r.name ?? "").replace(/^[\*\#\s]+/, "").trim(),
    }));
  const doctors: Option[] = docRes;
  const provinces: ProvinceOpt[] = (hub?.provinces ?? []).map((r) => ({
    code: r.code,
    name: r.name,
    fullName: r.full_name,
  }));
  const patients: PatientLite[] = hub?.patients ?? [];
  const lanKham = hub?.lan_kham ?? {};
  const appts: ApptLite[] = hub?.appts ?? [];
  const error = hub === null ? { message: "máy chủ không trả lời hoặc chưa có quyền đặt lịch." } : null;

  return (
    <div className="space-y-3">
      {error ? (
        <div className="rounded-2xl bg-danger-bg px-4 py-3 text-sm text-danger">
          Không nạp được dữ liệu: {error.message}
        </div>
      ) : null}

      <BookingHub
        locations={locations}
        coSoMacDinhId={(await getCurrentStaff())?.primary_location_id ?? null}
        services={services}
        doctors={doctors}
        provinces={provinces}
        patients={patients}
        appts={appts}
        lanKham={lanKham}
        // VAI THẬT của người đang mở màn — màn này nay dùng chung cho CSKH và
        // Lễ tân, và hai vai không đặt được cùng một kênh: kênh "Trực tiếp" kéo
        // theo tự check-in, mà CSKH không được check-in (luật Tuyền 15/09).
        // Truyền vai xuống thay vì một cờ suy sẵn — biểu mẫu khách mới bên
        // trong cũng cần biết nó đang phục vụ ai.
        vai={await vaiLamViec(canWriteIntake)}
      />
    </div>
  );
}
