// CSKH / Lễ tân intake: create a patient, then optionally book an
// appointment. Writes go through /api/patients + /api/appointments
// (service-role); this page only loads the dropdown options.

import Link from "next/link";
import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { layCoSo } from "../../../../lib/danh-muc";
import { moDuocMan, requireNavAccess, vaiLamViec } from "../../../../lib/clinic-session";
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
  // Cửa = lego 11 "Thêm bệnh nhân" (27/09/2026) — trước gác vai canWriteIntake,
  // nên người được cấp lego mà khác vai bị đá về, còn thu ngân mang vai CSKH
  // suy từ lego Chăm sóc khách thì lọt dù lego này tắt.
  await requireNavAccess("/patients/new");
  // Vai LÀM VIỆC hôm nay — chỉ để chọn LUỒNG biểu mẫu (điều dưỡng đứng Lễ tân
  // thì mở đúng màn lễ tân), không còn quyết được vào hay không.
  const role = await vaiLamViec(canWriteIntake);
  const nurse = isNurseRole(role);
  // Trưởng ca + Quản lý làm được CẢ hai luồng: online (full — như CSKH, chọn ô đỏ
  // BN1/BN2) và vãng lai (walkin — như Lễ tân, chọn ô xanh). Chuyển bằng ?mode=walkin.
  // Các vai khác giữ luồng CỐ ĐỊNH: CSKH → full; Lễ tân/điều dưỡng → walkin.
  const canBothFlows = role === "TRUONG_CA" || role === "MANAGEMENT";
  // LỄ TÂN RỜI KHỎI LUỒNG "VÃNG LAI" (Tuyền 16/09/2026).
  //
  // *"vãng lai giờ hiểu chung là đến trực tiếp, chưa có trong cơ sở dữ liệu thì
  // là khách mới, có rồi thì là khách cũ và đặt trực tiếp thôi"* — tức nó không
  // phải một LUỒNG riêng, chỉ là một KÊNH ĐẶT. Nên Lễ tân dùng đúng biểu mẫu
  // của CSKH: đủ thông tin hành chính, và có bảng Bác sĩ × tuần để nhìn lịch
  // tổng quan trước khi chọn giờ — thứ lưới vãng lai cũ không có.
  //
  // Điều dưỡng vẫn ở luồng cũ: họ không có quyền check-in nên không đi được
  // đường "Trực tiếp hôm nay ⇒ tự check-in". Gỡ nốt khi làm tới vai ấy.
  const forcedWalkin = nurse;
  const walkinMode = forcedWalkin || (canBothFlows && qMode === "walkin");
  const variant = walkinMode ? "walkin" : "full";
  // `h1` cũ đã bỏ: tiêu đề nay ở thanh trên cùng, và nó không đọc được
  // `?mode=` nên phải là MỘT câu đúng cho cả hai luồng. Hai nút chọn luồng bên
  // dưới đã nói rõ người dùng đang ở luồng nào.

  // Danh mục qua backend (24/09/2026 — trang từng đọc thẳng 3 bảng bằng
  // Supabase). Phường/xã load runtime theo tỉnh (/api/wards).
  // Lưu xong về màn Tiếp đón khách (Tuyền 29/09/2026) — chỉ khi người này
  // vào được màn ấy, hỏi ĐÚNG luật cửa của trang đích (lego), không hỏi vai.
  // Danh sách DỊCH VỤ không nạp ở đây nữa (07/10/2026): ô chọn 4 nhóm
  // (`_lam-viec/ChonDichVuDatLich`) tự hỏi `/api/catalog/dich-vu-dat-lich`.
  const [coSo, docRes, tinh, veTiepDon] = await Promise.all([
    layCoSo(),
    listBookableDoctors(),
    fetchFromBackend<{ code: string; name: string; full_name: string }[]>(
      "/api/v1/catalog/provinces",
    ),
    moDuocMan("/reception/queue"),
  ]);

  const locations: Option[] = coSo.map((r) => ({ id: r.id, label: r.name }));
  const doctors: Option[] = docRes;
  const provinces: ProvinceOpt[] = (tinh ?? []).map((r) => ({
    code: r.code,
    name: r.name,
    fullName: r.full_name,
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
        coSoMacDinhId={(await getCurrentStaff())?.primary_location_id ?? null}
        role={role}
        locations={locations}
        doctors={doctors}
        provinces={provinces}
        variant={variant}
        veTiepDon={veTiepDon}
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
