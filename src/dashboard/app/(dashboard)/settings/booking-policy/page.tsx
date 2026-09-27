// Luật đặt lịch của phòng khám — Trưởng ca + Quản lý sửa được (C.3 write path).
// Trang riêng vì /settings (nhân viên + tài khoản) chỉ dành cho MANAGEMENT;
// Trưởng ca được sửa luật đặt lịch nhưng KHÔNG được tạo user.

// Vai làm việc hôm nay (xét mọi vai, gồm vai tài khoản)
import { requireNavAccess } from "../../../../lib/clinic-session";
// Nhập các hàm lấy luật đặt lịch và danh sách luật
import {
  getBookingPolicy, // Hàm lấy luật đặt lịch hiện tại
  listBookingRules, // Hàm lấy danh sách các luật override
} from "../../../../lib/booking-policy";
// Nhập hàm getSupabaseServer để lấy client Supabase phía server
import { layDichVu } from "../../../../lib/danh-muc";
// Nhập component BookingPolicyCard để hiển thị luật đặt lịch
import BookingPolicyCard from "../BookingPolicyCard";
import GioCaLamViecCard from "../GioCaLamViecCard";
// Nhập component OverridePolicyCard và kiểu DoctorOpt
import OverridePolicyCard, { type DoctorOpt } from "../OverridePolicyCard";
import LuatBacSiCard, { type LuatBacSi } from "../LuatBacSiCard";
import { fetchFromBackend } from "../../../../lib/backend-proxy";
// Nhập component MeasuredDurationCard và kiểu DurationStatRow
import MeasuredDurationCard, {
  type DurationStatRow,
} from "../MeasuredDurationCard";
// Nhập hàm listBookableDoctors để lấy danh sách bác sĩ có thể đặt lịch
import { listBookableDoctors } from "../../../../lib/doctors-server";

// Ép Next.js render trang này động (không cache) — luôn lấy dữ liệu mới nhất
export const dynamic = "force-dynamic";

// Component chính của trang luật đặt lịch (server component)
export default async function BookingPolicyPage() {
  // Lego 18 "Cài đặt phòng khám" (27/09/2026) — trước gác vai isOpsAdmin nên
  // trưởng ca có lego Cài đặt TẮT vẫn vào được (backend đã đòi
  // config.clinic.manage: màn mở ra mà lưu gì cũng 403).
  await requireNavAccess("/settings/booking-policy");

  // Chạy song song các truy vấn để tối ưu hiệu năng
  const [bookingPolicy, staffRes, rules, durationRes, svcRes, luatRes] =
    await Promise.all([
    getBookingPolicy(), // Lấy luật đặt lịch hiện tại
    listBookableDoctors(), // Lấy danh sách bác sĩ có thể đặt lịch
    listBookingRules(), // Lấy danh sách các luật override
    // Thời lượng ĐO ĐƯỢC + danh mục dịch vụ đang bật — qua backend (24/09/2026;
    // trang từng đọc thẳng view thống kê và `service_type` bằng Supabase).
    fetchFromBackend<{
      items: (Omit<DurationStatRow, "doctor_name"> & { doctor_id: string | null })[];
    }>("/api/v1/booking-rules/thoi-luong-do"),
    layDichVu(),
    // Luật bắt buộc bác sĩ — qua FastAPI, vì bảng luật không mở đường ghi cho
    // client và đường đọc cũng đi cùng một cửa cho nhất quán.
    fetchFromBackend<{ items: LuatBacSi[] }>("/api/v1/booking-rules/doctor"),
  ]);

  // DoctorOpt dùng `name`, helper trả `label` — đổi tên trường, không đổi nguồn.
  // Chuyển đổi danh sách bác sĩ sang định dạng DoctorOpt
  const doctors: DoctorOpt[] = staffRes.map((d) => ({
    id: d.id, // ID bác sĩ
    name: d.label, // Tên bác sĩ (đổi từ label sang name)
  }));

  // View trả doctor_id; đổi sang tên ở đây thay vì embed trong truy vấn —
  // v_consultation_duration_stats là view, PostgREST không suy ra được khoá
  // ngoại để nhúng, và danh sách bác sĩ vừa đọc xong ngay trên.
  // Tạo map từ ID bác sĩ sang tên bác sĩ
  const doctorName = new Map(doctors.map((d) => [d.id, d.name]));
  // Chuyển đổi dữ liệu thời lượng khám sang định dạng DurationStatRow
  const durationRows: DurationStatRow[] = (
    durationRes?.items ?? []
  ).map((r) => ({
    doctor_name: r.doctor_id ? (doctorName.get(r.doctor_id) ?? null) : null, // Tên bác sĩ từ map
    vn_weekday: r.vn_weekday, // Thứ trong tuần
    vn_hour: r.vn_hour, // Giờ trong ngày
    patient_kind: r.patient_kind, // Loại bệnh nhân
    sample_count: r.sample_count, // Số mẫu
    median_minutes: r.median_minutes, // Thời lượng trung vị (phút)
    p90_minutes: r.p90_minutes, // Thời lượng phân vị 90 (phút)
  }));

  return (
    // Container chính của trang
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      {/* Phần đầu trang */}
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
      {/* Card luật đặt lịch với key theo giá trị để remount khi luật thay đổi */}
      <BookingPolicyCard
        key={
          bookingPolicy
            ? `${bookingPolicy.slotMinutes}-${bookingPolicy.regularCap}-${bookingPolicy.walkinCap}` // Key theo 3 con số
            : "chua-doc-duoc" // Key khi chưa đọc được
        }
        policy={bookingPolicy} // Luật đặt lịch hiện tại
      />

      {/* Giờ ba ca — đặt NGAY SAU luật đặt lịch vì hai thứ trả lời cùng một câu
          hỏi ("phòng khám nhận lịch lúc nào, mỗi khung mấy chỗ") và cùng một
          lớp gác quyền. Trước 21/08/2026 giờ ca chỉ đổi được bằng lệnh SQL. */}
      <GioCaLamViecCard />

      {/* Card luật override theo bác sĩ/khung giờ */}
      <OverridePolicyCard doctors={doctors} policy={bookingPolicy} rules={rules} />

      <LuatBacSiCard
        services={svcRes.map(
          (s) => ({ id: s.id, label: s.name }),
        )}
        doctors={doctors.map((d) => ({ id: d.id, label: d.name }))}
        luat={luatRes?.items ?? []}
      />

      {/* Card thống kê thời lượng khám đo được */}
      <MeasuredDurationCard rows={durationRows} />
    </main>
  );
}