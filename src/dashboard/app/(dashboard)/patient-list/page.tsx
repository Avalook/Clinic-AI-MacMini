// "Danh sách bệnh nhân" — TOÀN BỘ hồ sơ của phòng khám, kèm đã khám mấy lần
// và những ngày nào. Đọc qua Supabase RLS.
//
// NỀN LÀ BẢNG `patient`, KHÔNG PHẢI BẢNG LỊCH HẸN. Bản trước dựng danh sách từ
// `appointment`, nên một người đã có hồ sơ mà chưa khám lần nào thì KHÔNG hề
// xuất hiện — lễ tân vừa tạo hồ sơ xong, mở danh sách ra không thấy đâu, và
// không có cách nào biết là do chưa khám hay do tạo hỏng. Lịch hẹn giờ chỉ để
// ĐẾM lượt và lấy ngày; ai chưa khám thì hiện với 0 lượt, đứng ở nhóm riêng.
//
// Bấm tên BN: chỉ vai LÂM SÀNG được bật hồ sơ lâm sàng ở panel phải. Vai vận
// hành đi tới trang thông tin hành chính; route /api/clinical-record còn chặn
// độc lập để không thể bypass bằng cách gọi API trực tiếp.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { Activity, CalendarClock, RotateCcw, UserPlus, UsersRound } from "lucide-react";
import { requireNavAccess, getClinicRole } from "../../../lib/clinic-session";
import {
  canEditPatient,
  canReadClinical,
  canWriteIntake,
  isDoctorRole,
} from "../../../lib/roles";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import PatientListView, { type ExaminedRow } from "./PatientListView";
import type { DoctorApptRow } from "../tasks/DoctorWorkBoard";

export const dynamic = "force-dynamic";

// Đủ trường để dựng hồ sơ lâm sàng (mục I Hành chính) trong popup.
type PatientFull = NonNullable<DoctorApptRow["patient"]>;
interface ApptJoin {
  id: string;
  status: string;
  queue_number: string | null;
  slot_start: string;
  patient: PatientFull | PatientFull[] | null;
  service: { name: string } | { name: string }[] | null;
}

const SELECT = `
  id, status, queue_number, slot_start,
  patient:patient!clinic_patient_id (
    clinic_patient_id, patient_code, full_name, date_of_birth,
    phone_primary, phone_secondary, gender, ethnicity, nationality,
    occupation, patient_objection, address, guardian_name
  ),
  service:service_type!service_type_id ( name )
`;

const one = <T,>(x: T | T[] | null): T | null =>
  !x ? null : Array.isArray(x) ? (x[0] ?? null) : x;

export default async function PatientListPage() {
  await requireNavAccess("/patient-list");
  const role = await getClinicRole();
  // Membership role is authoritative. Operational roles keep the administrative
  // patient page but never mount ClinicalRecordForm.
  const enablePopup = canReadClinical(role);
  // Nút tái khám chỉ tồn tại bên trong popup; vai vận hành đặt lại lịch từ trang
  // hành chính /patients/[id], nên không cần nạp option khi popup bị chặn.
  const showRebook = enablePopup && canWriteIntake(role);
  // Bác sĩ: pager ◀ ▶ xem lượt khám trước/sau ngay trong phiếu.
  const showPager = isDoctorRole(role);
  const supabase = await getSupabaseServer();

  // KHÔNG CÒN NẠP OPTION CHO MODAL ĐẶT LỊCH NHANH.
  //
  // Modal ấy (`QuickBookingModal` → `CskhBookingGrid`) là màn dựng sẵn và đã bị
  // xoá; nút "Tái khám" nay đi tới `/appointments` — màn đặt lịch thật, tự nạp
  // dịch vụ / bác sĩ / cơ sở của chính nó. Ba truy vấn ở đây chỉ để nuôi một
  // modal không còn tồn tại.
  const { startUtc: todayStartUtc, endUtc: todayEndUtc } = vnTodayRangeUtc();
  // Hồ sơ: nguồn của danh sách. Lịch hẹn: nguồn của các lượt khám.
  const qPatients = supabase
    .from("patient")
    .select(
      "clinic_patient_id, patient_code, full_name, date_of_birth, " +
        "phone_primary, phone_secondary, gender, ethnicity, nationality, " +
        "occupation, patient_objection, address, guardian_name, " +
        "patient_sdt_them ( so_dien_thoai, loai )",
    )
    .order("created_at", { ascending: false })
    .limit(5000);

  const qList = supabase
    .from("appointment")
    .select(SELECT)
    .or(
      `status.eq.COMPLETED,and(status.in.(CHECKED_IN,IN_PROGRESS),slot_start.gte.${todayStartUtc},slot_start.lt.${todayEndUtc})`,
    )
    .order("slot_start", { ascending: false })
    .limit(2000);

  const [{ data, error }, { data: pdata, error: perror }] = await Promise.all([
    qList,
    qPatients,
  ]);

  // BN xuất hiện ở "Danh sách bệnh nhân" khi: (a) đã khám xong (COMPLETED) — lịch
  // sử; HOẶC (b) ĐANG khám HÔM NAY (CHECKED_IN/IN_PROGRESS) — walk-in vừa tiếp
  // nhận hiện ngay, không phải chờ đóng lượt khám. Trước đây chỉ lọc COMPLETED nên
  // khách đến trực tiếp (auto CHECKED_IN) nằm ở "khách hàng" mà không lọt danh sách
  // này. Active giới hạn TRONG NGÀY để không kéo về mọi lượt CHECKED_IN cũ bị bỏ dở.
  // Sắp xếp mới→cũ để lần xuất hiện ĐẦU của mỗi BN chính là lượt gần nhất. Cap 2000.
  const raw = (data as ApptJoin[] | null) ?? [];
  const map = new Map<string, ExaminedRow>();

  // Mọi hồ sơ vào trước với 0 lượt. Vòng lịch hẹn bên dưới chỉ cộng thêm.
  for (const p of (pdata as PatientFull[] | null) ?? []) {
    map.set(p.clinic_patient_id, {
      clinic_patient_id: p.clinic_patient_id,
      patient_code: p.patient_code,
      full_name: p.full_name,
      phone_primary: p.phone_primary,
      date_of_birth: p.date_of_birth,
      gender: p.gender,
      visit_count: 0,
      visits: [],
      latest: null,
      phan_loai: "Chưa khám",
      hoso: p,
      appt: null,
    });
  }
  for (const a of raw) {
    const p = one(a.patient);
    if (!p) continue;
    const cur = map.get(p.clinic_patient_id);
    if (cur) {
      cur.visit_count += 1;
      // Lượt ĐẦU TIÊN gặp của mỗi hồ sơ là lượt gần nhất (đã order desc) — đó
      // cũng là lượt nuôi panel bên phải.
      if (cur.appt === null) {
        cur.latest = a.slot_start;
        cur.hoso = p;
        cur.appt = {
          id: a.id,
          slot_start: a.slot_start,
          status: a.status,
          queue_number: a.queue_number,
          patient: p,
          service: one(a.service),
        };
      }
      // Giữ lại TỪNG lượt, không chỉ đếm. Trước đây chỉ có `visit_count`, nên
      // màn hình nói được "3 lượt" mà không nói được ba lượt ấy là những lần
      // nào — Lễ tân phải mở hồ sơ mới biết.
      cur.visits.push({
        id: a.id,
        slot_start: a.slot_start,
        status: a.status,
        service_name: one(a.service)?.name ?? null,
      });
    } else {
      map.set(p.clinic_patient_id, {
        clinic_patient_id: p.clinic_patient_id,
        patient_code: p.patient_code,
        full_name: p.full_name,
        phone_primary: p.phone_primary,
        date_of_birth: p.date_of_birth,
        gender: p.gender,
        visit_count: 1,
        visits: [
          {
            id: a.id,
            slot_start: a.slot_start,
            status: a.status,
            service_name: one(a.service)?.name ?? null,
          },
        ],
        latest: a.slot_start, // lần xuất hiện đầu = gần nhất (đã order desc)
        phan_loai: "Khám lần đầu",
        hoso: p,
        // Lượt khám GẦN NHẤT — mở trong popup hồ sơ lâm sàng (chỉ đọc).
        appt: {
          id: a.id,
          slot_start: a.slot_start,
          status: a.status,
          queue_number: a.queue_number,
          patient: p,
          service: one(a.service),
        },
      });
    }
  }
  const rows: ExaminedRow[] = [...map.values()]
    .map(
      (r): ExaminedRow => ({
        ...r,
        phan_loai:
          r.visit_count === 0
            ? "Chưa khám"
            : r.visit_count >= 2
              ? "Tái khám"
              : "Khám lần đầu",
      }),
    )
    // Đã khám lên trước, mới nhất trước. Chưa khám xuống cuối, xếp theo tên —
    // xếp theo ngày tạo thì hai người tạo cùng lúc đứng cạnh nhau ngẫu nhiên
    // và không tra được bằng mắt.
    .sort((a, b) => {
      if (a.latest && b.latest) return a.latest < b.latest ? 1 : -1;
      if (a.latest) return -1;
      if (b.latest) return 1;
      return a.full_name.localeCompare(b.full_name, "vi");
    });
  const activeVisits = rows.filter(
    (row) => row.appt && ["CHECKED_IN", "IN_PROGRESS"].includes(row.appt.status),
  ).length;
  const firstVisits = rows.filter((row) => row.phan_loai === "Khám lần đầu").length;
  const returnVisits = rows.filter((row) => row.phan_loai === "Tái khám").length;
  const chuaKham = rows.filter((row) => row.phan_loai === "Chưa khám").length;

  return (
    <div className="mx-auto max-w-[1540px] space-y-4">
      {/* Tiêu đề nằm ở THANH TRÊN CÙNG (GlobalHeader) — cùng chỗ với mọi
          trang khác, thay vì vẽ lại lần thứ hai ngay dưới nó. */}

      <section aria-label="Tổng quan danh sách bệnh nhân" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SummaryCard icon={<UsersRound size={17} />} label="Tổng hồ sơ" value={rows.length} tone="brand" />
        <SummaryCard icon={<Activity size={17} />} label="Có lượt đang mở" value={activeVisits} tone="success" />
        <SummaryCard icon={<CalendarClock size={17} />} label="Khám lần đầu" value={firstVisits} tone="warning" />
        <SummaryCard icon={<RotateCcw size={17} />} label="Tái khám" value={returnVisits} tone="brand" />
        <SummaryCard icon={<UserPlus size={17} />} label="Chưa khám lần nào" value={chuaKham} tone="warning" />
      </section>

      {error || perror ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {(error ?? perror)?.message}
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
