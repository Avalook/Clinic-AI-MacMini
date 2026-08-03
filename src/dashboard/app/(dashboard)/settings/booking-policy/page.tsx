// Luật đặt lịch của phòng khám — Trưởng ca + Quản lý sửa được (C.3 write path).
// Trang riêng vì /settings (nhân viên + tài khoản) chỉ dành cho MANAGEMENT;
// Trưởng ca được sửa luật đặt lịch nhưng KHÔNG được tạo user.

import { redirect } from "next/navigation";
import { getClinicRole } from "../../../../lib/clinic-session";
import { isOpsAdmin } from "../../../../lib/roles";
import { getBookingPolicy } from "../../../../lib/booking-policy";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import BookingPolicyCard from "../BookingPolicyCard";
import OverridePolicyCard, { type DoctorOpt } from "../OverridePolicyCard";
import MeasuredDurationCard, {
  type DurationStatRow,
} from "../MeasuredDurationCard";
import { listBookableDoctors } from "../../../../lib/doctors-server";

export const dynamic = "force-dynamic";

export default async function BookingPolicyPage() {
  const role = await getClinicRole();
  if (!isOpsAdmin(role)) redirect("/home");

  const supabase = await getSupabaseServer();
  const [bookingPolicy, staffRes, durationRes] = await Promise.all([
    getBookingPolicy(),
    listBookableDoctors(),
    // Thời lượng ĐO ĐƯỢC, đặt cạnh chỗ chỉnh số chỗ. RLS của view là
    // security_invoker nên nó chỉ trả số liệu của phòng khám đang đăng nhập.
    // Giới hạn 40 dòng, ưu tiên khung có nhiều ca nhất — bảng này để cân lịch,
    // không phải để tra cứu toàn bộ lịch sử.
    supabase
      .from("v_consultation_duration_stats")
      .select(
        "doctor_id, vn_weekday, vn_hour, patient_kind, sample_count, median_minutes, p90_minutes",
      )
      .order("sample_count", { ascending: false })
      .limit(40),
  ]);

  // DoctorOpt dùng `name`, helper trả `label` — đổi tên trường, không đổi nguồn.
  const doctors: DoctorOpt[] = staffRes.map((d) => ({
    id: d.id,
    name: d.label,
  }));

  // View trả doctor_id; đổi sang tên ở đây thay vì embed trong truy vấn —
  // v_consultation_duration_stats là view, PostgREST không suy ra được khoá
  // ngoại để nhúng, và danh sách bác sĩ vừa đọc xong ngay trên.
  const doctorName = new Map(doctors.map((d) => [d.id, d.name]));
  const durationRows: DurationStatRow[] = (
    (durationRes.data as
      | (Omit<DurationStatRow, "doctor_name"> & { doctor_id: string | null })[]
      | null) ?? []
  ).map((r) => ({
    doctor_name: r.doctor_id ? (doctorName.get(r.doctor_id) ?? null) : null,
    vn_weekday: r.vn_weekday,
    vn_hour: r.vn_hour,
    patient_kind: r.patient_kind,
    sample_count: r.sample_count,
    median_minutes: r.median_minutes,
    p90_minutes: r.p90_minutes,
  }));

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">
          Luật đặt lịch
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Khung giờ và số chỗ mỗi khung — áp dụng cho phòng khám này.
        </p>
      </header>

      {/* key theo chính giá trị của luật: sau khi Lưu, router.refresh() đọc lại
          luật mới nhưng useState bên trong form chỉ khởi tạo lúc MOUNT, nên form
          sẽ hiện số CŨ và Trưởng ca tưởng chưa lưu được rồi bấm lại. Đổi key là
          remount, và form nói đúng thứ vừa ghi. */}
      <BookingPolicyCard
        key={
          bookingPolicy
            ? `${bookingPolicy.slotMinutes}-${bookingPolicy.regularCap}-${bookingPolicy.walkinCap}`
            : "chua-doc-duoc"
        }
        policy={bookingPolicy}
      />

      <OverridePolicyCard doctors={doctors} policy={bookingPolicy} />

      <MeasuredDurationCard rows={durationRows} />
    </main>
  );
}