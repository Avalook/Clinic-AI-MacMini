// Đích của các link trên bảng lịch hẹn (Tiếp đón khách / Trang chủ) — MỘT chỗ
// dựng URL, có test khoá (tests/menu-lich-tai-cho-boundary.test.mts).

/** Màn Thêm khách hàng (`/patients/new`). Tham số khớp đúng thứ `page.tsx` của
 *  màn ấy đọc: `date` (YYYY-MM-DD) · `time` (HH:mm) · `doctor` (staff id) → điền
 *  sẵn khung + bác sĩ. Không truyền gì → biểu mẫu trống (nút ở thanh QueueBoard).
 *
 *  Tuyền 29/09/2026: dòng "＋ Thêm khách hàng" ở Tiếp đón từng trỏ nhầm sang màn
 *  Đặt lịch (`/appointments?ngay=&gio=&bac_si=`). */
export function hrefThemKhach(
  o: { ngay?: string | null; gio?: string | null; bacSi?: string | null } = {},
): string {
  const q = new URLSearchParams();
  if (o.ngay) q.set("date", o.ngay);
  if (o.gio) q.set("time", o.gio);
  if (o.bacSi) q.set("doctor", o.bacSi);
  const s = q.toString();
  return s ? `/patients/new?${s}` : "/patients/new";
}

/** Màn Đặt lịch điền sẵn khung (`/appointments?ngay=&gio=&bac_si=`) — lối của
 *  CSKH/Quản lý ("＋ Đặt lịch vào đây"). */
export function hrefDatLich(o: { ngay: string; gio: string; bacSi: string }): string {
  const q = new URLSearchParams({ ngay: o.ngay, gio: o.gio, bac_si: o.bacSi });
  return `/appointments?${q.toString()}`;
}

/** Hồ sơ khách ở Danh sách bệnh nhân — `?chon=` mở sẵn đúng khách
 *  (PatientListView `chonSan`). Tuyền 29/09/2026: mục ⋯ "Mở hồ sơ khách" nhảy
 *  thẳng sang đó, cùng tab. */
export function hrefHoSoKhach(clinicPatientId: string): string {
  return `/patient-list?chon=${encodeURIComponent(clinicPatientId)}`;
}
