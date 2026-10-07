// "Danh sách bệnh nhân" — TOÀN BỘ hồ sơ của phòng khám, kèm đã khám mấy lần
// và những lần nào. Màn TRA CỨU dùng chung cho mọi vai (Tuyền chốt 16/09/2026);
// việc chăm sóc của CSKH nằm ở Quản lý khách hàng.
//
// DỮ LIỆU TỪ BACKEND (`GET /api/v1/patients/danh-sach`), không đọc Supabase.
// Bản cũ tự đếm lượt ở đây với bộ lọc "COMPLETED hoặc CHECKED_IN trong HÔM NAY"
// — qua nửa đêm, mọi lượt check-in hôm qua chưa đóng biến mất (46/46 "Chưa
// khám", "Có lượt đang mở = 0") trong khi màn Quản lý khách hàng vẫn ghi "đang
// chờ khám". Luật đếm lượt + lọc thư ký theo bác sĩ giờ ở
// danh_sach_benh_nhan_service.py.
//
// PHÂN TRANG Ở MÁY CHỦ (06/10/2026): ~8.700 hồ sơ (8.600 nhập từ Notion). Mỗi
// lần dựng trang chỉ nhận 50 dòng + số đếm toàn bộ; tìm / tab / xếp / trang đi
// qua URL rồi xuống `/api/v1/patients/danh-sach`.
//
// Bấm tên BN: chỉ vai LÂM SÀNG được bật hồ sơ lâm sàng ở panel phải; route
// /api/clinical-record còn chặn độc lập.

import { fetchFromBackend } from "../../../lib/backend-proxy";
import { coMotQuyen, docDuocYKhoa } from "../../../lib/quyen-cua-toi";
import { Activity, CalendarClock, RotateCcw, UserPlus, UsersRound } from "lucide-react";
import {
  requireNavAccess,
  getVaiHomNay,
  getVaiChinh,
  getQuyenCuaToi,
} from "../../../lib/clinic-session";
import {
  canEditPatient,
  canManageAppt,
  canWriteIntake,
  isDoctorRole,
} from "../../../lib/roles";
import PatientListView, { type ExaminedRow, type TongDanhSach } from "./PatientListView";
import type { DoctorApptRow } from "../tasks/DoctorApptRow";

export const dynamic = "force-dynamic";

type PatientFull = NonNullable<DoctorApptRow["patient"]>;

interface LuotApi {
  id: string;
  clinic_patient_id: string;
  status: string;
  queue_number: string | null;
  slot_start: string;
  booking_channel: string | null;
  service_name: string | null;
  doctor_name: string | null;
  closed_at: string | null;
  /** Lượt khám thật + loại dữ liệu (v5 | notion | cu | trong) — 07/10/2026. */
  visit_id?: string | null;
  loai_du_lieu?: string | null;
}

interface DongApi {
  ho_so: PatientFull & { patient_sdt_them?: { so_dien_thoai: string; loai: string }[] };
  so_luot: number;
  phan_loai: ExaminedRow["phan_loai"];
  dang_mo: boolean;
  luot: LuotApi[];
}

interface DanhSachApi {
  /** Đếm trên TOÀN BỘ hồ sơ (ô tổng + số ở tab), không theo ô tìm / tab / trang. */
  tong: TongDanhSach;
  /** MỘT trang (≤ `mot_trang` dòng) đã tìm + lọc + xếp ở máy chủ. */
  dong: DongApi[];
  trang: number;
  mot_trang: number;
  so_trang: number;
  /** Số hồ sơ khớp ô tìm + tab — "Hiển thị x–y trên N". */
  so_khop: number;
  /** Khách `?chon=` khi KHÔNG nằm trong trang trả về. */
  chon: DongApi | null;
}

/** Một dòng API → một dòng màn hình. */
function thanhDong(d: DongApi): ExaminedRow {
  const ganNhat = d.luot[0] ?? null;
  return {
    clinic_patient_id: d.ho_so.clinic_patient_id,
    patient_code: d.ho_so.patient_code,
    full_name: d.ho_so.full_name,
    phone_primary: d.ho_so.phone_primary,
    date_of_birth: d.ho_so.date_of_birth,
    gender: d.ho_so.gender,
    visit_count: d.so_luot,
    visits: d.luot.map((l) => ({
      id: l.id,
      slot_start: l.slot_start,
      status: l.status,
      service_name: l.service_name,
      doctor_name: l.doctor_name,
      visit_id: l.visit_id ?? null,
      loai_du_lieu: l.loai_du_lieu ?? null,
    })),
    latest: ganNhat?.slot_start ?? null,
    phan_loai: d.phan_loai,
    dang_mo: d.dang_mo,
    hoso: d.ho_so,
    appt: ganNhat
      ? ({
          id: ganNhat.id,
          slot_start: ganNhat.slot_start,
          status: ganNhat.status,
          queue_number: ganNhat.queue_number,
          booking_channel: ganNhat.booking_channel,
          patient: d.ho_so,
          service: ganNhat.service_name ? { name: ganNhat.service_name } : null,
        } as unknown as DoctorApptRow)
      : null,
  };
}

/** Lấy một giá trị chuỗi từ searchParams (Next có thể trả mảng khi lặp khoá). */
function mot(v: string | string[] | undefined): string | null {
  const x = Array.isArray(v) ? v[0] : v;
  return typeof x === "string" && x !== "" ? x : null;
}

export default async function PatientListPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // TRẠNG THÁI MÀN NẰM TRÊN URL (06/10/2026): `?trang=&q=&loc=&sap=&chon=` —
  // F5 hay gửi link vẫn đúng trang, đúng ô tìm, đúng tab. Máy chủ đọc rác thành
  // mặc định (trang chữ → 1, tab lạ → tất cả), nên ở đây chỉ chuyển tiếp.
  const sp = await searchParams;
  const chon = mot(sp.chon);
  const boLoc = { q: mot(sp.q), loc: mot(sp.loc), sap: mot(sp.sap) };
  await requireNavAccess("/patient-list");
  const vaiHomNay = await getVaiHomNay();
  const role = await getVaiChinh();
  // Mở hồ sơ y khoa trong popup: theo QUYỀN, không theo vai (24/09/2026).
  const enablePopup = await docDuocYKhoa();
  // MỞ FULL LEGO (30/09/2026): nút theo LEGO, không theo vai. Máy chủ chưa trả
  // lời quyền (`null`) → rơi về vai như trước.
  const quyen = await getQuyenCuaToi();
  const theoQuyen = (can: readonly string[], vai: boolean) =>
    quyen === null ? vai : coMotQuyen(quyen, can);
  const showRebook =
    enablePopup && theoQuyen(["booking.create"], vaiHomNay.some(canWriteIntake));
  const showPager = theoQuyen(
    ["clinical.consult.perform"],
    vaiHomNay.some(isDoctorRole),
  );
  // Sửa hành chính — khớp `_PATIENT_EDIT_GUARD` (api/v1/patients.py).
  const canEditAdmin = theoQuyen(
    ["patient.create", "crm.manage", "reception.checkin.perform", "clinical.record.write"],
    canEditPatient(role),
  );
  const canBook = theoQuyen(
    ["booking.create", "booking.manage"],
    canManageAppt(role) || canWriteIntake(role),
  );

  const thamSo = new URLSearchParams();
  for (const [k, v] of Object.entries({ trang: mot(sp.trang), ...boLoc, chon })) {
    if (v) thamSo.set(k, v);
  }
  const goi = await fetchFromBackend<DanhSachApi>(
    `/api/v1/patients/danh-sach${thamSo.size ? `?${thamSo.toString()}` : ""}`,
  );

  const rows: ExaminedRow[] = (goi?.dong ?? []).map(thanhDong);
  const chonRow = goi?.chon ? thanhDong(goi.chon) : null;
  const t = goi?.tong ?? { ho_so: 0, dang_mo: 0, lan_dau: 0, tai_kham: 0, chua_kham: 0 };

  return (
    <div className="mx-auto max-w-[1540px] space-y-4">
      {/* Tiêu đề nằm ở THANH TRÊN CÙNG (GlobalHeader) — cùng chỗ với mọi
          trang khác, thay vì vẽ lại lần thứ hai ngay dưới nó. */}

      <section aria-label="Tổng quan danh sách bệnh nhân" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SummaryCard icon={<UsersRound size={17} />} label="Tổng hồ sơ" value={t.ho_so} tone="brand" />
        <SummaryCard icon={<Activity size={17} />} label="Có lượt đang mở" value={t.dang_mo} tone="success" />
        <SummaryCard icon={<CalendarClock size={17} />} label="Khám lần đầu" value={t.lan_dau} tone="warning" />
        <SummaryCard icon={<RotateCcw size={17} />} label="Tái khám" value={t.tai_kham} tone="brand" />
        <SummaryCard icon={<UserPlus size={17} />} label="Chưa khám lần nào" value={t.chua_kham} tone="warning" />
      </section>

      {goi === null ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          Không đọc được danh sách bệnh nhân. Thử tải lại trang.
        </div>
      ) : (
        // Chỉ vai lâm sàng có popup; quyền sửa hành chính vẫn được gate riêng ở
        // trang /patients/[id] và PATCH /api/patients.
        <PatientListView
          rows={rows}
          chonRow={chonRow}
          tong={t}
          phanTrang={{
            trang: goi.trang ?? 1,
            soTrang: goi.so_trang ?? 1,
            soKhop: goi.so_khop ?? rows.length,
            motTrang: goi.mot_trang ?? 50,
          }}
          boLoc={boLoc}
          enablePopup={enablePopup}
          canEditAdmin={canEditAdmin}
          /* Nút Tái khám: CSKH/Lễ tân. Pager lượt khám: Bác sĩ. */
          showRebook={showRebook}
          enableVisitPager={showPager}
          canBook={canBook}
          chonSan={chon}
        />
      )}
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  tone: "brand" | "success" | "warning";
}) {
  const tones = {
    brand: "bg-brand-50 text-brand-700",
    success: "bg-success-bg text-success",
    warning: "bg-warning-bg text-warning",
  };
  return (
    <article className="flex items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 shadow-card">
      <span className={`flex h-9 w-9 items-center justify-center rounded-control ${tones[tone]}`}>{icon}</span>
      <div>
        <p className="text-xs text-ink-muted">{label}</p>
        <p className="mt-0.5 text-xl font-semibold tabular-nums text-ink">{value}</p>
      </div>
    </article>
  );
}
