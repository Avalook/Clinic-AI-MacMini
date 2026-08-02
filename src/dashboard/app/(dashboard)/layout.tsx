import { redirect } from "next/navigation";
import Shell from "./Shell";
import DeclinedNotice, { type DeclinedItem } from "./DeclinedNotice";
import { NotificationProvider } from "./NotificationContext";
import RealtimeRefresher from "./RealtimeRefresher";
import { signOutStaff } from "../(auth)/login/actions";
import { getSupabaseServer } from "../../lib/supabase-server";
import { getClinicRole, getClinicStaffId } from "../../lib/clinic-session";
import { getStaffContext } from "../../lib/current-staff";
import { ROLE_LABEL, canWriteIntake } from "../../lib/roles";
import { fmtDayTime, vnTodayRangeUtc } from "../../lib/datetime";

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
  const context = await getStaffContext();
  // Nhiều membership không phải là "không có quyền" — trước đây cả hai trường
  // hợp đều bị đá về trang đăng nhập, bác sĩ chạy sô ra khỏi app không kèm lý do.
  if (context.status === "must_choose_clinic") redirect("/choose-clinic");

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

  return (
    <NotificationProvider staffId={staffId}>
      <Shell
        role={role}
        identity={identity}
        leaveAction={signOutStaff}
        clinicSwitchHref={
          context.status === "resolved" && context.choices.length > 1
            ? "/choose-clinic?switch=1"
            : null
        }
      >
        {children}
        <DeclinedNotice items={declined} />
        <RealtimeRefresher />
      </Shell>
    </NotificationProvider>
  );
}
