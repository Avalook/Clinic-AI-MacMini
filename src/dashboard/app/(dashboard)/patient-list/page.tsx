// "Danh sách bệnh nhân" — TOÀN BỘ hồ sơ của phòng khám, kèm đã khám mấy lần
// và những lần nào. Màn TRA CỨU dùng chung cho mọi vai (Tuyền chốt 16/09/2026);
// việc chăm sóc của CSKH nằm ở Quản lý khách hàng.
//
// DỮ LIỆU TỪ BACKEND (`GET /api/v1/patients/danh-sach`), không đọc Supabase.
// Bản cũ tự đếm lượt ở đây với bộ lọc "COMPLETED hoặc CHECKED_IN trong HÔM NAY"
// — qua nửa đêm, mọi lượt check-in hôm qua chưa đóng biến mất (46/46 "Chưa
// khám", "Có lượt đang mở = 0") trong khi màn Quản lý khách hàng vẫn ghi "đang
// chờ khám". Luật đếm lượt + lọc thư ký theo bác sĩ giờ ở
// danh_sach_benh_nhan_service.py.
//
// Bấm tên BN: chỉ vai LÂM SÀNG được bật hồ sơ lâm sàng ở panel phải; route
// /api/clinical-record còn chặn độc lập.

import { fetchFromBackend } from "../../../lib/backend-proxy";
import { Activity, CalendarClock, RotateCcw, UserPlus, UsersRound } from "lucide-react";
import { requireNavAccess, getClinicRole } from "../../../lib/clinic-session";
import {
  canEditPatient,
  canManageAppt,
  canReadClinical,
  canWriteIntake,
  isDoctorRole,
} from "../../../lib/roles";
import PatientListView, { type ExaminedRow } from "./PatientListView";
import type { DoctorApptRow } from "../tasks/DoctorWorkBoard";

export const dynamic = "force-dynamic";

type PatientFull = NonNullable<DoctorApptRow["patient"]>;

interface LuotApi {
  id: string;
  clinic_patient_id: string;
  status: string;
  queue_number: string | null;
  slot_start: string;
  booking_channel: string | null;
  service_name: string | null;
  doctor_name: string | null;
  closed_at: string | null;
}

interface DanhSachApi {
  tong: { ho_so: number; dang_mo: number; lan_dau: number; tai_kham: number; chua_kham: number };
  dong: {
    ho_so: PatientFull & { patient_sdt_them?: { so_dien_thoai: string; loai: string }[] };
    so_luot: number;
    phan_loai: ExaminedRow["phan_loai"];
    dang_mo: boolean;
    luot: LuotApi[];
  }[];
}

export default async function PatientListPage() {
  await requireNavAccess("/patient-list");
  const role = await getClinicRole();
  const enablePopup = canReadClinical(role);
  const showRebook = enablePopup && canWriteIntake(role);
  const showPager = isDoctorRole(role);

  const goi = await fetchFromBackend<DanhSachApi>("/api/v1/patients/danh-sach");

  const rows: ExaminedRow[] = (goi?.dong ?? []).map((d) => {
    const ganNhat = d.luot[0] ?? null;
    return {
      clinic_patient_id: d.ho_so.clinic_patient_id,
      patient_code: d.ho_so.patient_code,
      full_name: d.ho_so.full_name,
      phone_primary: d.ho_so.phone_primary,
      date_of_birth: d.ho_so.date_of_birth,
      gender: d.ho_so.gender,
      visit_count: d.so_luot,
      visits: d.luot.map((l) => ({
        id: l.id,
        slot_start: l.slot_start,
        status: l.status,
        service_name: l.service_name,
        doctor_name: l.doctor_name,
      })),
      latest: ganNhat?.slot_start ?? null,
      phan_loai: d.phan_loai,
      dang_mo: d.dang_mo,
      hoso: d.ho_so,
      appt: ganNhat
        ? ({
            id: ganNhat.id,
            slot_start: ganNhat.slot_start,
            status: ganNhat.status,
            queue_number: ganNhat.queue_number,
            booking_channel: ganNhat.booking_channel,
            patient: d.ho_so,
            service: ganNhat.service_name ? { name: ganNhat.service_name } : null,
          } as unknown as DoctorApptRow)
        : null,
    };
  });
  const t = goi?.tong ?? { ho_so: 0, dang_mo: 0, lan_dau: 0, tai_kham: 0, chua_kham: 0 };

  return (
    <div className="mx-auto max-w-[1540px] space-y-4">
      {/* Tiêu đề nằm ở THANH TRÊN CÙNG (GlobalHeader) — cùng chỗ với mọi
          trang khác, thay vì vẽ lại lần thứ hai ngay dưới nó. */}

      <section aria-label="Tổng quan danh sách bệnh nhân" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SummaryCard icon={<UsersRound size={17} />} label="Tổng hồ sơ" value={t.ho_so} tone="brand" />
        <SummaryCard icon={<Activity size={17} />} label="Có lượt đang mở" value={t.dang_mo} tone="success" />
        <SummaryCard icon={<CalendarClock size={17} />} label="Khám lần đầu" value={t.lan_dau} tone="warning" />
        <SummaryCard icon={<RotateCcw size={17} />} label="Tái khám" value={t.tai_kham} tone="brand" />
        <SummaryCard icon={<UserPlus size={17} />} label="Chưa khám lần nào" value={t.chua_kham} tone="warning" />
      </section>

      {goi === null ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          Không đọc được danh sách bệnh nhân. Thử tải lại trang.
        </div>
      ) : (
        // Chỉ vai lâm sàng có popup; quyền sửa hành chính vẫn được gate riêng ở
        // trang /patients/[id] và PATCH /api/patients.
        <PatientListView
          rows={rows}
          enablePopup={enablePopup}
          canEditAdmin={canEditPatient(role)}
          /* Nút tóm tắt trước khám chỉ cho BÁC SĨ. */
          showPreVisitBrief={isDoctorRole(role)}
          /* Nút Tái khám: CSKH/Lễ tân. Pager lượt khám: Bác sĩ. */
          showRebook={showRebook}
          enableVisitPager={showPager}
          canBook={canManageAppt(role) || canWriteIntake(role)}
        />
      )}
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  tone: "brand" | "success" | "warning";
}) {
  const tones = {
    brand: "bg-brand-50 text-brand-700",
    success: "bg-success-bg text-success",
    warning: "bg-warning-bg text-warning",
  };
  return (
    <article className="flex items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 shadow-card">
      <span className={`flex h-9 w-9 items-center justify-center rounded-control ${tones[tone]}`}>{icon}</span>
      <div>
        <p className="text-xs text-ink-muted">{label}</p>
        <p className="mt-0.5 text-xl font-semibold tabular-nums text-ink">{value}</p>
      </div>
    </article>
  );
}
