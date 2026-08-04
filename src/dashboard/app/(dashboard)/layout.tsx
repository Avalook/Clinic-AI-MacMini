import { redirect } from "next/navigation";
import Shell from "./Shell";
import DeclinedNotice, { type DeclinedItem } from "./DeclinedNotice";
import { NotificationProvider } from "./NotificationContext";
import { BookingPolicyProvider } from "./BookingPolicyContext";
import RealtimeRefresher from "./RealtimeRefresher";
import { leaveClinic } from "../(auth)/enter/actions";
import { getSupabaseServer } from "../../lib/supabase-server";
import { getCurrentStaff } from "../../lib/current-staff";
import { getClinicId, getClinicRole } from "../../lib/clinic-session";
import { ROLE_LABEL, canWriteIntake } from "../../lib/roles";
import { fmtDayTime, vnTodayRangeUtc } from "../../lib/datetime";
import { getBookingPolicy } from "../../lib/booking-policy";
import { getFeatureMode } from "../../lib/feature-mode";

interface DeclinedRow {
  id: string;
  slot_start: string;
  patient: { full_name: string } | null;
  doctor: { full_name: string } | null;
}

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const role = await getClinicRole();
  if (!role) redirect("/login");

  // Identity comes from the staff row linked to the authenticated user.
  //
  // PHÒNG KHÁM + CƠ SỞ ĐI KÈM TÊN, KHÔNG PHẢI TUỲ CHỌN. Yêu cầu "tài khoản nào
  // cũng phải có id phòng khám, cơ sở khám để không bị nhầm nữa" chỉ có tác dụng
  // nếu người dùng ĐỌC được nó. Lưu đúng trong database mà không hiện ra thì
  // đúng cái nhầm đó vẫn xảy ra — lễ tân đặt lịch cho cơ sở khác mà không có gì
  // trên màn hình mâu thuẫn với họ.
  //
  // Một truy vấn ít hơn: getCurrentStaff() đã đọc staff + membership + tên cơ
  // sở và được cache theo lượt render, còn khối cũ ở đây gọi lại bảng staff lần
  // thứ hai cho đúng một cột.
  const staff = await getCurrentStaff();
  const staffId = staff?.id ?? null;
  const who = staff?.full_name ?? staff?.short_name ?? "";
  const place = [staff?.clinic_name, staff?.location_name]
    .filter(Boolean)
    .join(" · ");
  const identity = [ROLE_LABEL[role], who, place]
    .filter(Boolean)
    .join(" · ");

  // BA THỨ NÀY KHÔNG PHỤ THUỘC NHAU — nên chúng đi CÙNG LÚC.
  //
  // Layout chạy lại ở MỌI lần chuyển trang, và trước đây nó chờ ba lượt mạng
  // nối đuôi nhau. Supabase ở Seoul, phòng khám ở Việt Nam: đo được ~180ms mỗi
  // lượt, nên riêng khối này tốn ~540ms trước khi trang bắt đầu làm việc của
  // nó. Gộp lại còn một lượt.
  //
  // Đo trực tiếp (04/08): 4 truy vấn tuần tự 830ms → song song 213ms.
  const [declinedRows, bookingPolicy, featureMode, clinicId] = await Promise.all([
    canWriteIntake(role) ? loadDeclined() : Promise.resolve([]),
    getBookingPolicy(),
    getFeatureMode(),
    getClinicId(),
  ]);

  // Reception / CSKH / management get a top-right notice of appointments a
  // doctor declined (from today onward), so they can re-assign them.
  const declined: DeclinedItem[] = declinedRows.map((r) => ({
    id: r.id,
    patientName: r.patient?.full_name ?? "—",
    time: fmtDayTime(r.slot_start),
    doctorName: r.doctor?.full_name ?? "—",
  }));

  return (
    <NotificationProvider staffId={staffId}>
      <BookingPolicyProvider policy={bookingPolicy}>
        <Shell role={role} identity={identity} featureMode={featureMode} leaveAction={leaveClinic}>
          {children}
          <DeclinedNotice items={declined} />
          <RealtimeRefresher clinicId={clinicId} />
        </Shell>
      </BookingPolicyProvider>
    </NotificationProvider>
  );
}

/** Lịch bác sĩ đã từ chối, từ hôm nay trở đi — để CSKH xếp lại bác sĩ khác. */
async function loadDeclined(): Promise<DeclinedRow[]> {
  const supabase = await getSupabaseServer();
  const { startUtc } = vnTodayRangeUtc();
  const { data } = await supabase
    .from("appointment")
    .select(
      "id, slot_start, patient:patient!clinic_patient_id ( full_name ), doctor:staff!doctor_id ( full_name )",
    )
    .eq("status", "DOCTOR_DECLINED")
    .gte("slot_start", startUtc)
    .order("slot_start", { ascending: true })
    .limit(20);
  return (data as DeclinedRow[] | null) ?? [];
}
