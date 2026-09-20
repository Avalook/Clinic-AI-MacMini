// Dựng dữ liệu cho bảng "Lịch hẹn khám" (WeeklyAppointmentsTable) từ gói
// /api/v1/home/bang-dieu-khien.
//
// HAI MÀN, MỘT PHÉP DỰNG (18/09/2026): Trang chủ vẽ cả tuần để XEM; Tiếp đón
// khách vẽ riêng hôm nay để CHECK-IN. Cùng một hàm để hai bảng không thể lệch
// nhau về khách nào nằm ngày nào, bác sĩ nào trực, ai đã đo sinh hiệu.

import { vnLocalToUtcISO } from "../../../lib/datetime";
import { weekDates } from "../../../lib/roster";
import type { ApptDay, DutyByDate, WeekApptRow } from "./WeeklyAppointmentsTable";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Phần của gói trang chủ mà bảng lịch cần. */
export interface GoiLichHen {
  tuan_hen: WeekApptRow[];
  truc_ca: { work_date: string; staff_id: string; staff_name: string | null }[];
  tien_trinh: { appointment_id?: string | null; vitals_recorded: boolean }[];
}

export function dungLichHenTuan(
  goi: GoiLichHen | null,
  weekAppt: string,
): { apptDays: ApptDay[]; dutyByDate: DutyByDate } {
  const weekApptRows = goi?.tuan_hen ?? [];

  // Bác sĩ TRỰC CA từng ngày của TUẦN LỊCH HẸN (weekAppt ≠ weekRoster!) — nuôi
  // các nhóm bác sĩ + ô xanh "đặt vào đây" trong bảng Lịch hẹn khám.
  const dutyByDate: DutyByDate = {};
  for (const r of goi?.truc_ca ?? []) {
    const list = dutyByDate[r.work_date] ?? [];
    if (!list.some((d) => d.id === r.staff_id)) {
      list.push({ id: r.staff_id, name: r.staff_name ?? "" });
    }
    dutyByDate[r.work_date] = list;
  }

  // Cờ "đã đo sinh hiệu" — luật "đủ vital" nằm trong visit_progress_service,
  // trang chỉ nhận cờ, nên Lễ tân không cần (và không có) quyền đọc bệnh án.
  const vitalsRecorded = new Set(
    (goi?.tien_trinh ?? [])
      .filter((p) => p.vitals_recorded && p.appointment_id)
      .map((p) => p.appointment_id as string),
  );

  const t0 = new Date(vnLocalToUtcISO(weekAppt, "00:00")).getTime();
  const apptDays: ApptDay[] = weekDates(weekAppt).map((date, i) => {
    const s = t0 + i * DAY_MS;
    const e = s + DAY_MS;
    const items = weekApptRows
      .filter((a) => {
        const t = new Date(a.slot_start).getTime();
        return t >= s && t < e;
      })
      // phan_loai đã do backend tính; ở đây chỉ gắn thêm cờ sinh hiệu.
      .map((a) => ({ ...a, has_vitals: vitalsRecorded.has(a.id) }));
    return { date, items };
  });

  return { apptDays, dutyByDate };
}
