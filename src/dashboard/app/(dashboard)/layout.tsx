import { redirect } from "next/navigation";
import Shell from "./Shell";
import DeclinedNotice, { type DeclinedItem } from "./DeclinedNotice";
import { NotificationProvider } from "./NotificationContext";
import { BookingPolicyProvider } from "./BookingPolicyContext";
import RealtimeRefresher from "./RealtimeRefresher";
import { leaveClinic } from "../(auth)/enter/actions";
import { getSupabaseServer } from "../../lib/supabase-server";
import { getClinicRole, getClinicStaffId } from "../../lib/clinic-session";
import { ROLE_LABEL, canWriteIntake } from "../../lib/roles";
import { fmtDayTime, vnTodayRangeUtc } from "../../lib/datetime";
import { getBookingPolicy } from "../../lib/booking-policy";

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
  let identity = ROLE_LABEL[role];
  const staffId = await getClinicStaffId();
  if (staffId) {
    const supabase = await getSupabaseServer();
    const { data } = await supabase
      .from("staff")
      .select("full_name, short_name")
      .eq("id", staffId)
      .maybeSingle();
    if (data) identity = `${ROLE_LABEL[role]} · ${data.full_name ?? data.short_name}`;
  }

  // Reception / CSKH / management get a top-right notice of appointments a
  // doctor declined (from today onward), so they can re-assign them.
  let declined: DeclinedItem[] = [];
  if (canWriteIntake(role)) {
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
    declined = ((data as DeclinedRow[] | null) ?? []).map((r) => ({
      id: r.id,
      patientName: r.patient?.full_name ?? "—",
      time: fmtDayTime(r.slot_start),
      doctorName: r.doctor?.full_name ?? "—",
    }));
  }

  // Đọc một lần cho cả cây: mọi lưới khung giờ phía dưới phải vẽ theo đúng luật
  // mà trigger enforce_slot_capacity sẽ dùng để từ chối, không theo hằng số.
  const bookingPolicy = await getBookingPolicy();

  return (
    <NotificationProvider staffId={staffId}>
      <BookingPolicyProvider policy={bookingPolicy}>
        <Shell role={role} identity={identity} leaveAction={leaveClinic}>
          {children}
          <DeclinedNotice items={declined} />
          <RealtimeRefresher />
        </Shell>
      </BookingPolicyProvider>
    </NotificationProvider>
  );
}
