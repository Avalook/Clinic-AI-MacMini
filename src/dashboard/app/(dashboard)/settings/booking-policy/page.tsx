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

export const dynamic = "force-dynamic";

export default async function BookingPolicyPage() {
  const role = await getClinicRole();
  if (!isOpsAdmin(role)) redirect("/home");

  const supabase = await getSupabaseServer();
  const [bookingPolicy, staffRes] = await Promise.all([
    getBookingPolicy(),
    supabase
      .from("staff")
      .select("id, full_name")
      .in("primary_department", ["DOCTOR", "ULTRASOUND_DOCTOR"])
      .eq("is_active", true)
      .order("full_name"),
  ]);

  const doctors: DoctorOpt[] = (staffRes.data ?? []).map((s) => ({
    id: s.id,
    name: s.full_name,
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

      <BookingPolicyCard policy={bookingPolicy} />

      <OverridePolicyCard doctors={doctors} policy={bookingPolicy} />
    </main>
  );
}