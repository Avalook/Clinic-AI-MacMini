// CSKH / Lễ tân intake: create a patient, then optionally book an
// appointment. Writes go through /api/patients + /api/appointments
// (service-role); this page only loads the dropdown options.

import { redirect } from "next/navigation";
import Link from "next/link";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { getCurrentStaff } from "../../../../lib/current-staff";
import { canWriteIntake, isNurseRole } from "../../../../lib/roles";
import NewPatientForm, { type Option, type ProvinceOpt } from "./NewPatientForm";
import { listBookableDoctors } from "../../../../lib/doctors-server";

export const dynamic = "force-dynamic";

export default async function NewPatientPage({
  searchParams,
}: {
  searchParams: Promise<{
    date?: string;
    time?: string;
    doctor?: string;
    mode?: string;
  }>;
}) {
  // Ô xanh "đặt vào đây" (bảng Lịch hẹn khám trang chủ) dẫn sang đây kèm
  // ?date&time&doctor để điền sẵn khung + bác sĩ cho khách vãng lai.
  const { date: qDate, time: qTime, doctor: qDoctor, mode: qMode } =
    await searchParams;
  const role = await getClinicRole();
  if (!canWriteIntake(role)) redirect("/home");
  const nurse = isNurseRole(role);
  // Trưởng ca + Quản lý làm được CẢ hai luồng: online (full — như CSKH, chọn ô đỏ
  // BN1/BN2) và vãng lai (walkin — như Lễ tân, chọn ô xanh). Chuyển bằng ?mode=walkin.
  // Các vai khác giữ luồng CỐ ĐỊNH: CSKH → full; Lễ tân/điều dưỡng → walkin.
  const canBothFlows = role === "TRUONG_CA" || role === "MANAGEMENT";
  const forcedWalkin = nurse || role === "RECEPTION";
  const walkinMode = forcedWalkin || (canBothFlows && qMode === "walkin");
  const variant = walkinMode ? "walkin" : "full";
  // `h1` cũ đã bỏ: tiêu đề nay ở thanh trên cùng, và nó không đọc được
  // `?mode=` nên phải là MỘT câu đúng cho cả hai luồng. Hai nút chọn luồng bên
  // dưới đã nói rõ người dùng đang ở luồng nào.

  const supabase = await getSupabaseServer();
  const [locRes, svcRes, docRes, provRes] = await Promise.all([
    supabase.from("clinic_location").select("id, name").order("name"),
    supabase.from("service_type").select("id, name").order("name"),
    listBookableDoctors(),
    // 34 tỉnh/thành sau sáp nhập — phường/xã load runtime theo tỉnh (/api/wards).
    // Trước đây phải đọc bằng service-role vì province bật RLS mà không có policy
    // SELECT nào; 20260730000002 đã thêm policy (ADR-0012).
    supabase.from("province").select("code, name, full_name").order("name"),
  ]);

  const locations: Option[] = (locRes.data ?? []).map((r) => ({
    id: r.id as string,
    label: r.name as string,
  }));
  // Lọc bỏ dịch vụ rác "FREE" (option import từ Notion) khỏi dropdown đặt lịch
  // — feedback B5#3 ("tại sao có chữ free trong dịch vụ khám").
  const services: Option[] = (svcRes.data ?? [])
    .filter((r) => (r.name as string)?.trim().toUpperCase() !== "FREE")
    .map((r) => ({
      id: r.id as string,
      label: r.name as string,
    }));
  const doctors: Option[] = docRes;
  const provinces: ProvinceOpt[] = (provRes.data ?? []).map((r) => ({
    code: r.code as string,
    name: r.name as string,
    fullName: r.full_name as string,
  }));

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      {/* Tiêu đề nằm ở THANH TRÊN CÙNG (GlobalHeader). Ở đây chỉ còn thứ BẤM
          ĐƯỢC — hai nút chọn luồng của Trưởng ca — vì đó là việc, không phải
          nhãn. */}
      {canBothFlows && (
        <header className="rounded-card border border-line bg-surface px-4 py-3 shadow-card sm:px-5">
          <div className="mt-4 inline-flex rounded-control border border-line bg-surface-muted p-1 text-sm">
            <Link
              href="/patients/new"
              className={
                "rounded-md px-3 py-1.5 font-medium transition-colors " +
                (!walkinMode
                  ? "bg-white text-brand-700 shadow-sm"
                  : "text-ink-muted hover:text-ink")
              }
            >
              Nhập thông tin khách hàng mới
            </Link>
            <Link
              href="/patients/new?mode=walkin"
              className={
                "rounded-md px-3 py-1.5 font-medium transition-colors " +
                (walkinMode
                  ? "bg-white text-brand-700 shadow-sm"
                  : "text-ink-muted hover:text-ink")
              }
            >
              Tạo bệnh nhân mới
            </Link>
          </div>
        </header>
      )}
      <NewPatientForm
        staffId={(await getCurrentStaff())?.id ?? null}
        role={role}
        locations={locations}
        services={services}
        doctors={doctors}
        provinces={provinces}
        variant={variant}
        // Ẩn tiêu đề + thanh bước RIÊNG của biểu mẫu: trang này đã có tiêu đề
        // ở thanh trên cùng, và hai thanh bước chồng nhau thì không thanh nào
        // đáng tin.
        nhung
        initialAppt={
          qDate || qTime || qDoctor
            ? { date: qDate, time: qTime, doctorId: qDoctor }
            : undefined
        }
      />
    </div>
  );
}
