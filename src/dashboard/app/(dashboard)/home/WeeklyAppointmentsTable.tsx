"use client";

// Bảng "Lịch hẹn khám (check đặt lịch)" — TÁI CẤU TRÚC 2026-07-02 theo mô hình
// "rạp chiếu phim": gom theo NGÀY → KHUNG GIỜ 15' → BÁC SĨ TRỰC; mỗi bác sĩ tối
// đa 2 dòng lịch hẹn kênh thường (BN1/BN2) + 1 dòng khách vãng lai (WALK_IN).
// Khi chỗ vãng lai của khung còn trống (và khung chưa qua) hiện Ô XANH "đặt vào
// đây" — hôm nay thì bấm được, dẫn sang Tạo bệnh nhân với ngày/giờ/bác sĩ điền
// sẵn. Luật 2+1 nằm ở lib/slot-capacity (server chặn cứng — đây là hiển thị).
// Read-only với dữ liệu thật từ appointment; cột thao tác check-in/sinh hiệu
// giữ nguyên như bản trước.

import { useState, Fragment } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronDown, ChevronRight, MoreHorizontal, X } from "lucide-react";
import {
  canCheckin,
  canManageAppt,
  canWriteIntake,
  isNurseRole,
  type ClinicRole,
} from "../../../lib/roles";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import { dayLabel, fmtDayMonth, todayVn } from "../../../lib/roster";
import { nowMs, VN_TZ } from "../../../lib/datetime";
import { doctorName } from "../../../lib/doctor-name";
import {
  slotMs,
  slotBucketMs,
  isWalkinChannel,
  isDeadStatus,
} from "../../../lib/slot-capacity";
import { useBookingPolicy } from "../BookingPolicyContext";
import { laKhamMoi, nhanPhanLoaiKham } from "../../../lib/phan-loai-kham";
import { chipClass } from "@/components/ui/Chip";
import { buttonClass } from "@/components/ui/Button";
import NutInPhieu from "@/components/ui/NutInPhieu";
import type { BookingPolicy } from "../../../lib/booking-policy";
import NutCheckIn from "@/components/ui/NutCheckIn";
import type { MaXacMinh } from "@/lib/xac-minh";

export interface WeekApptRow {
  id: string;
  slot_start: string;
  status: string;
  queue_number: string | null;
  doctor_id: string | null;
  booking_channel: string | null;
  /** Giá trị BACKEND trả: "Tái khám" | "Khám lần đầu" | "". Chữ hiện lên
   *  màn hình đi qua `nhanPhanLoaiKham` — xem lib/phan-loai-kham.ts. */
  /** Bác sĩ của lịch này không còn ca KHÁM vào ngày khám — backend tính
   *  (week_appointments_service), cùng luật với màn Quản lý khách hàng. */
  mat_bac_si?: boolean;
  /** Bác sĩ đã bị gỡ khỏi lịch khi ca trực của họ bị xoá. Sau khi gỡ,
   *  `doctor_id` về NULL nên `mat_bac_si` tắt — cột này giữ cho màn hình còn
   *  nói được, và nói rõ đổi từ ai. */
  bac_si_da_go?: string | null;
  /** Bác sĩ bị gỡ ĐÃ CÓ CA KHÁM TRỞ LẠI hôm đó — đổi câu cảnh báo: đây là
   *  việc nội bộ (gán lại bác sĩ), không phải lý do gọi khách. */
  bac_si_da_go_co_ca_lai?: boolean;
  /** Lịch vượt sức chứa sau khi công bố lịch trực (backend, 16/09/2026). */
  vuot_suc_chua?: boolean;
  phan_loai: string;
  /** THỨ TỰ GỌI — backend tính (services/queue_order.py). Màn hình chỉ xếp
   *  theo con số này, không tự tính lại. Trước đây mỗi màn gọi compareQueue()
   *  từ một bản chép của luật bằng TypeScript. */
  call_order?: number | null;
  /** Làn: -2 ƯT · -1 chờ đọc KQ · 0 có hẹn đúng giờ · 1 vãng lai/đến muộn */
  call_tier?: number | null;
  /** UU_TIEN | CHO_DOC_KQ | DAT_TRUOC_DUNG_GIO | DEN_TRUC_TIEP | DEN_TRE | CHUA_DEN */
  call_reason?: string | null;
  /** Có người đến TRƯỚC mà bị xếp SAU mình — chỗ cần một câu giải thích. */
  promoted?: boolean;
  promoted_over?: number;
  /** ĐÃ ghi sinh hiệu (đủ 3 vital bắt buộc) chưa — tắt "!" nhắc điều dưỡng. */
  has_vitals?: boolean;
  patient: {
    clinic_patient_id: string;
    full_name: string;
    patient_code: string;
    phone_primary: string | null;
    date_of_birth: string | null;
    phone_secondary: string | null;
    gender: string | null;
    ethnicity: string | null;
    nationality: string | null;
    occupation: string | null;
    patient_objection: string | null;
    address: string | null;
    guardian_name: string | null;
  } | null;
  doctor: { full_name: string } | null;
  service: { name: string } | null;
}
export interface ApptDay {
  date: string;
  items: WeekApptRow[];
}
/** Bác sĩ trực ca (work_roster LICH_KHAM) theo ngày — nuôi các nhóm bác sĩ
 *  hiện cả khi CHƯA có lịch trong khung (để thấy chỗ vãng lai còn trống). */
export type DutyByDate = Record<string, { id: string; name: string }[]>;

const NO_DOCTOR = "Chưa phân bác sĩ";

function PhanLoai({ value }: { value: string }) {
  const nhan = nhanPhanLoaiKham(value);
  if (!nhan) return <span className="text-ink-faint">—</span>;
  return (
    <span className={chipClass(laKhamMoi(value) ? "success" : "warning")}>
      {nhan}
    </span>
  );
}

// Ô thân chung — DESIGN.md §6: CHỈ KẺ NGANG, bằng hairline. Kẻ dọc chính là
// thứ làm bảng này "nhìn như Google Sheets" (Tuyền, 15/08/2026); căn cột và
// khoảng trắng làm việc của nó. Đệm ngang nới 8→12px vì không còn vách ngăn.
const CELL = "border-b border-hairline px-3 py-2 align-top";
// Tiêu đề cột: nền trung tính thay cho dải teal — màu thương hiệu không dùng
// để kẻ khung (DESIGN.md §2), nó dành cho hành động và điểm nhấn.
const TH =
  "border-b border-hairline bg-surface-muted px-3 py-2 text-left text-label font-semibold uppercase tracking-wide text-ink-muted";

const STATUS_VN: Record<string, string> = {
  SCHEDULED: "Chưa xác nhận",
  CSKH_CONFIRMED: "Đã xác nhận",
  CONFIRMED: "Đã xác nhận",
  CHECKED_IN: "Đã check-in",
  COMPLETED: "Đã khám xong",
  NO_SHOW: "Không đến",
  CANCELLED: "Đã huỷ",
  DOCTOR_DECLINED: "Bác sĩ từ chối",
};

// Nhãn khung theo giờ VN: "17:00 - 17:15" (dài đúng slotMinutes của PK).
function bucketLabel(bucketMs: number, policy: BookingPolicy): string {
  const hhmm = (ms: number) =>
    new Date(ms).toLocaleTimeString("vi-VN", {
      timeZone: VN_TZ,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  return `${hhmm(bucketMs)} - ${hhmm(bucketMs + slotMs(policy))}`;
}

// Giờ HH:MM (VN) của đầu khung — làm query ?time= cho link "đặt vào đây".
function bucketHHMM(bucketMs: number): string {
  return new Date(bucketMs).toLocaleTimeString("en-GB", {
    timeZone: VN_TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// Mô tả 1 dòng render sau khi gom khung giờ → bác sĩ (rowSpan tính sẵn).
interface RowDesc {
  key: string;
  bucket?: { label: string; span: number }; // chỉ dòng đầu của khung
  doctor?: { label: string; span: number }; // chỉ dòng đầu của nhóm bác sĩ
  appt?: WeekApptRow; // dòng lịch thật…
  free?: { href: string | null }; // …hoặc ô xanh "đặt vào đây" (href null = chỉ nhìn)
}

// Gom lịch 1 ngày thành các dòng render. duty = bác sĩ trực ngày đó (nhóm hiện
// cả khi chưa có lịch trong khung để thấy chỗ vãng lai trống).
function buildDayRows(
  day: ApptDay,
  duty: { id: string; name: string }[],
  now: number,
  canBook: boolean,
  policy: BookingPolicy,
  /** CSKH/Quản lý: "Đặt lịch vào đây" mở màn Đặt lịch điền sẵn khung — mọi
   *  ngày chưa qua, số chỗ thật do màn đặt lịch (backend) nói (16/09/2026). */
  datLichTaiMan = false,
): RowDesc[] {
  const isToday = day.date === todayVn();
  // Khung giờ có ít nhất 1 lịch (mọi trạng thái — lịch huỷ vẫn hiện để check).
  const byBucket = new Map<number, WeekApptRow[]>();
  for (const a of day.items) {
    const b = slotBucketMs(a.slot_start, policy);
    const list = byBucket.get(b) ?? [];
    list.push(a);
    byBucket.set(b, list);
  }
  const out: RowDesc[] = [];
  for (const bucketMs of [...byBucket.keys()].sort((x, y) => x - y)) {
    const inBucket = byBucket.get(bucketMs)!;
    const bucketNotPast = bucketMs >= now;
    // Thứ tự nhóm bác sĩ: bác sĩ TRỰC trước (theo thứ tự roster), rồi bác sĩ
    // khác có lịch (theo tên), "Chưa phân bác sĩ" cuối cùng.
    const groups: { id: string; label: string }[] = [];
    const seen = new Set<string>();
    if (bucketNotPast) {
      for (const d of duty) {
        groups.push({ id: d.id, label: doctorName(d.name) });
        seen.add(d.id);
      }
    }
    const extras = inBucket
      .filter((a) => !seen.has(a.doctor_id ?? ""))
      .map((a) => ({
        id: a.doctor_id ?? "",
        label: a.doctor?.full_name ? doctorName(a.doctor.full_name) : NO_DOCTOR,
      }))
      .filter((g, i, arr) => arr.findIndex((x) => x.id === g.id) === i)
      .sort((x, y) =>
        x.id === "" ? 1 : y.id === "" ? -1 : x.label.localeCompare(y.label, "vi"),
      );
    groups.push(...extras);

    const bucketRows: RowDesc[] = [];
    for (const g of groups) {
      const mine = inBucket.filter((a) => (a.doctor_id ?? "") === g.id);
      // BÁC SĨ KHÔNG CÓ LỊCH TRONG KHUNG NÀY THÌ ẨN (Tuyền 17/09/2026: "không
      // có lịch thì ẩn đi"). Trước đây mọi bác sĩ trực đều chiếm một dòng xanh
      // "+ Thêm khách hàng" ở MỌI khung — cả bác sĩ siêu âm, thủ thuật vốn không
      // nhận lịch khám — nên bảng dài gấp mấy lần số lịch thật. Đặt lịch mới
      // cho bác sĩ chưa có ai vẫn làm ở màn Đặt lịch.
      if (mine.length === 0) continue;
      // Thứ tự gọi do backend tính sẵn (call_order). Xem ghi chú ở
      // DoctorWorkBoard: luật chỉ còn một bản, ở Python.
      const theoThuTuGoi = (a: WeekApptRow, b: WeekApptRow) =>
        (a.call_order ?? 0) - (b.call_order ?? 0);
      const regular = mine
        .filter((a) => !isWalkinChannel(a.booking_channel))
        .sort(theoThuTuGoi);
      const walkins = mine
        .filter((a) => isWalkinChannel(a.booking_channel))
        .sort(theoThuTuGoi);
      const walkinAlive = walkins.filter((a) => !isDeadStatus(a.status)).length;
      const groupRows: RowDesc[] = [];
      for (const a of [...regular, ...walkins]) {
        groupRows.push({ key: a.id, appt: a });
      }
      // Ô XANH "đặt vào đây": chỗ vãng lai còn trống + khung chưa qua. Chỉ ngày
      // HÔM NAY mới bấm được (walk-in là khách đến trực tiếp trong ngày); ngày
      // sau chỉ hiện trạng thái. Nhóm "Chưa phân bác sĩ" không có ô này.
      // CHỈ vai đặt lịch (CSKH/Lễ tân/QL/Trưởng ca) mới thấy hàng này — bác sĩ,
      // điều dưỡng không đặt lịch nên bỏ hẳn cho gọn.
      if (datLichTaiMan && g.id && bucketNotPast) {
        groupRows.push({
          key: `${bucketMs}-${g.id}-free`,
          free: {
            href: `/appointments?ngay=${day.date}&gio=${encodeURIComponent(
              bucketHHMM(bucketMs),
            )}&bac_si=${g.id}`,
          },
        });
      } else if (canBook && g.id && bucketNotPast && walkinAlive < policy.walkinCap) {
        groupRows.push({
          key: `${bucketMs}-${g.id}-free`,
          free: {
            href: isToday
              ? `/patients/new?date=${day.date}&time=${encodeURIComponent(
                  bucketHHMM(bucketMs),
                )}&doctor=${g.id}`
              : null,
          },
        });
      }
      if (groupRows.length === 0) continue;
      groupRows[0].doctor = { label: g.label, span: groupRows.length };
      bucketRows.push(...groupRows);
    }
    if (bucketRows.length === 0) continue;
    bucketRows[0].bucket = {
      label: bucketLabel(bucketMs, policy),
      span: bucketRows.length,
    };
    out.push(...bucketRows);
  }
  return out;
}

/** Menu "…" của một dòng lịch cho CSKH — đúng các thao tác đã có ở Quản lý
 *  khách hàng (không có check-in: CSKH không check-in, luật 15/09/2026). */
function MenuLich({ a }: { a: WeekApptRow }) {
  const pid = a.patient?.clinic_patient_id;
  if (!pid) return null;
  const hoSo = `/customers?selected=${pid}&luot=${a.id}`;
  return (
    <details className="relative">
      <summary
        aria-label="Thao tác với lịch này"
        className="grid size-7 cursor-pointer list-none place-items-center rounded-control text-ink-muted hover:bg-surface-sunken"
      >
        <MoreHorizontal className="size-4" />
      </summary>
      <div className="absolute right-0 z-20 mt-1 w-52 rounded-card border border-hairline bg-surface p-1 text-body shadow-panel">
        <Link href={hoSo} className="block rounded-control px-2 py-1.5 hover:bg-surface-muted">
          Mở hồ sơ khách
        </Link>
        <Link href={hoSo} className="block rounded-control px-2 py-1.5 hover:bg-surface-muted">
          Gọi / ghi chăm sóc
        </Link>
        <Link href={hoSo} className="block rounded-control px-2 py-1.5 hover:bg-surface-muted">
          Đổi / huỷ lịch (ghi lý do)
        </Link>
        {a.patient?.phone_primary && (
          <a
            href={`tel:${a.patient.phone_primary}`}
            className="block rounded-control px-2 py-1.5 hover:bg-surface-muted"
          >
            📞 {a.patient.phone_primary}
          </a>
        )}
      </div>
    </details>
  );
}

export default function WeeklyAppointmentsTable({
  days,
  role,
  staffId,
  canWriteClinical = false,
  dutyByDate = {},
  choDoSinhHieu,
}: {
  days: ApptDay[];
  role: ClinicRole | null;
  staffId: string | null;
  canWriteClinical?: boolean;
  dutyByDate?: DutyByDate;
  /** Hiện cột "Điền sinh hiệu". Trang chủ quyết theo VỊ TRÍ hôm nay (đứng Đo
   *  chỉ số); không truyền thì theo vai điều dưỡng như trước. */
  choDoSinhHieu?: boolean;
}) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selAppt, setSelAppt] = useState<WeekApptRow | null>(null);
  // Bảng này gom lịch theo KHUNG — độ dài khung và số chỗ vãng lai là cấu hình
  // của phòng khám, nên không có bản mặc định ở đây.
  const policy = useBookingPolicy();

  // GẬP / MỞ THEO NGÀY (ảnh Tuyền 16/09/2026): ngày có lịch mở sẵn, ngày trống
  // gập gọn một dòng. `moTay` giữ lựa chọn tay theo ngày; chưa bấm thì theo
  // mặc định — đổi tuần không kéo theo trạng thái của tuần cũ.
  const [moTay, setMoTay] = useState<Record<string, boolean>>({});
  const dangMo = (d: ApptDay) => moTay[d.date] ?? d.items.length > 0;
  // Menu "…" cho vai quản lý lịch hẹn không có cột check-in (CSKH).
  const coMenu = canManageAppt(role) && !canCheckin(role);

  const showActions = canCheckin(role);
  // Điều dưỡng: KHÔNG check-in (việc Lễ tân) mà điền SINH HIỆU ngay trên lịch hẹn.
  const isNurse = choDoSinhHieu ?? isNurseRole(role);
  const showActionCol = showActions || isNurse;
  const nCols = (showActionCol ? 6 : 5) + (coMenu ? 1 : 0);

  async function act(
    id: string,
    action: "checkin" | "undo_checkin" | "no_show",
    xacMinhCach?: MaXacMinh,
  ) {
    if (busyId) return;
    setBusyId(id);
    setError(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action, xac_minh_cach: xacMinhCach }),
    });
    setBusyId(null);
    if (!res.ok) {
      setError((await res.json()).error ?? "Có lỗi xảy ra.");
      return;
    }
    router.refresh();
  }

  // Gom nhầm khung thì hai lịch khác giờ nằm chung một dòng "Khung giờ" — sai
  // im lặng, tệ hơn không hiện.
  if (!policy) {
    return (
      <div className="rounded-card border border-danger-bg bg-danger-bg px-4 py-6 text-center text-sm text-danger shadow-card">
        Chưa đọc được luật đặt lịch của phòng khám (độ dài khung giờ) — chưa hiện
        được lịch tuần. Thử tải lại trang; còn lỗi thì báo kỹ thuật.
      </div>
    );
  }

  // Cả tuần KHÔNG có lịch → thẻ rỗng GỌN (không dựng bảng trống huơ).
  if (days.every((d) => d.items.length === 0)) {
    return (
      <div className="rounded-card border border-dashed border-line bg-surface px-4 py-10 text-center text-sm text-ink-muted shadow-card">
        Chưa có lịch hẹn nào trong tuần này.
      </div>
    );
  }

  const now = nowMs();

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg bg-danger-bg px-3 py-2 text-xs text-danger">
          {error}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => setMoTay(Object.fromEntries(days.map((d) => [d.date, true])))}
          className="rounded-control px-2 py-1 text-label text-ink-soft ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
        >
          Mở tất cả
        </button>
        <button
          type="button"
          onClick={() => setMoTay(Object.fromEntries(days.map((d) => [d.date, false])))}
          className="rounded-control px-2 py-1 text-label text-ink-soft ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
        >
          Đóng tất cả
        </button>
      </div>
      <div className="max-h-[88vh] min-h-45 max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
        <table className="w-full min-w-max border-collapse text-xs">
          <thead className="sticky top-0 z-10">
            <tr>
              <th className={`${TH} min-w-23`}>Khung giờ</th>
              <th className={`${TH} min-w-30`}>Bác sĩ</th>
              <th className={`${TH} min-w-50`}>Thông tin</th>
              <th className={`${TH} min-w-33`}>Dịch vụ khám</th>
              <th className={`${TH} min-w-28`}>Phân loại khám</th>
              {showActionCol && (
                <th className={`${TH} min-w-38`}>
                  {isNurse ? "Sinh hiệu" : "Thao tác Check-in"}
                </th>
              )}
              {coMenu && <th className={`${TH} w-12`}>Thao tác</th>}
            </tr>
          </thead>
          <tbody>
            {days.map((day) => {
              const rows = buildDayRows(
                day,
                dutyByDate[day.date] ?? [],
                now,
                canWriteIntake(role),
                policy,
                // LỄ TÂN ĐI CHUNG ĐƯỜNG VỚI CSKH (Tuyền 16/09/2026): ô trống mở
                // màn đặt lịch, không còn rẽ sang biểu mẫu vãng lai của riêng
                // quầy. "Vãng lai" nay chỉ là một KÊNH ĐẶT, không phải một
                // luồng — nên ngày mai, ngày kia cũng bấm được, không chỉ hôm nay.
                canManageAppt(role) || canCheckin(role),
              );
              const mo = dangMo(day);
              return (
                <Fragment key={day.date}>
                  {/* Dòng tiêu đề NGÀY — bấm để gập / mở. Ngày trống nói
                      "chưa có lịch hẹn" NGAY trên dòng này, không thêm dòng. */}
                  <tr className="bg-surface-muted">
                    <td
                      colSpan={nCols}
                      className="border-b border-hairline border-l-3 border-l-brand-600 px-3 py-1.5 text-sm font-semibold text-ink"
                    >
                      <button
                        type="button"
                        onClick={() => setMoTay((m) => ({ ...m, [day.date]: !mo }))}
                        aria-expanded={mo}
                        className="inline-flex items-center gap-1.5"
                      >
                        {mo ? (
                          <ChevronDown className="size-4 text-ink-muted" />
                        ) : (
                          <ChevronRight className="size-4 text-ink-muted" />
                        )}
                        {dayLabel(day.date)} · {fmtDayMonth(day.date)}
                        <span className={`ml-1 ${chipClass("neutral")}`}>
                          {day.items.length} lịch
                        </span>
                      </button>
                      {day.items.length === 0 && (
                        <span className="ml-3 text-label font-normal text-ink-faint">
                          — Chưa có lịch hẹn —
                        </span>
                      )}
                    </td>
                  </tr>
                  {!mo || rows.length === 0 ? null : (
                    rows.map((r) => {
                      const a = r.appt;
                      return (
                        <tr
                          key={r.key}
                          className={r.free ? "bg-success-bg" : "bg-white"}
                        >
                          {r.bucket && (
                            <td
                              rowSpan={r.bucket.span}
                              className={`${CELL} whitespace-nowrap bg-white font-medium text-ink`}
                            >
                              {r.bucket.label}
                            </td>
                          )}
                          {r.doctor && (
                            <td
                              rowSpan={r.doctor.span}
                              className={`${CELL} whitespace-nowrap bg-white font-medium text-brand-700`}
                            >
                              {r.doctor.label}
                            </td>
                          )}
                          {a ? (
                            <>
                              <td className={`${CELL} text-ink`}>
                                {/* BÁC SĨ NGHỈ SAU KHI KHÁCH ĐÃ ĐẶT.
                                    Đặt ngay tại dòng lịch, không gom về đầu
                                    bảng: người đọc quét dọc cột giờ để gọi tên,
                                    nên câu cảnh báo phải nằm ở đúng dòng họ
                                    đang nhìn. */}
                                {/* CẢNH BÁO CAM NGAY TRÊN DÒNG LỊCH — cùng nguồn với khung
                                    báo ở Quản lý khách hàng (16/09/2026). Gỡ ca KHÔNG
                                    huỷ lịch (luật 15/09): việc là gọi khách đổi lịch,
                                    hoặc gán lại bác sĩ khi ca đã xếp lại. */}
                                {(a.mat_bac_si || a.bac_si_da_go || a.vuot_suc_chua) && (
                                  <span className="mb-1 block rounded bg-warning-bg px-1.5 py-0.5 text-label font-semibold text-warning">
                                    ⚠{" "}
                                    {a.vuot_suc_chua
                                      ? "Khung đã đủ số lượng khám — gọi khách chốt hoặc đổi lịch"
                                      : a.bac_si_da_go
                                        ? a.bac_si_da_go_co_ca_lai
                                          ? `Ca của ${a.bac_si_da_go} đã xếp lại — gán lại bác sĩ nếu còn chỗ`
                                          : `${a.bac_si_da_go} không còn ca — gọi khách đổi lịch`
                                        : "Bác sĩ đã đổi lịch làm việc — gọi khách đổi lịch"}
                                  </span>
                                )}
                                {canWriteClinical ? (
                                  <button
                                    onClick={() => setSelAppt(a)}
                                    className="flex items-center gap-1.5 font-medium text-brand-600 hover:underline text-left"
                                  >
                                    {isNurse &&
                                      a.status === "CHECKED_IN" &&
                                      !a.has_vitals && (
                                        <span
                                          title="Cần điền sinh hiệu"
                                          className="inline-flex h-4 w-4 shrink-0 animate-pulse items-center justify-center rounded-full bg-danger text-label font-bold leading-none text-white motion-reduce:animate-none"
                                        >
                                          !
                                        </span>
                                      )}
                                    {a.patient?.full_name ?? "—"}
                                  </button>
                                ) : (
                                  <span className="block font-medium">
                                    {a.patient?.full_name ?? "—"}
                                  </span>
                                )}
                                <span className="block font-mono text-label text-ink-muted">
                                  {a.patient?.patient_code}
                                  {a.patient?.phone_primary
                                    ? ` · ${a.patient.phone_primary}`
                                    : ""}
                                  {isWalkinChannel(a.booking_channel)
                                    ? " · vãng lai"
                                    : ""}
                                </span>
                              </td>
                              <td className={`${CELL} text-ink-soft`}>
                                {a.service?.name ?? (
                                  <span className="text-ink-faint">—</span>
                                )}
                              </td>
                              <td className={CELL}>
                                <PhanLoai value={a.phan_loai} />
                              </td>
                              {showActionCol && (
                                <td className={CELL}>
                                  {isNurse ? (
                                    ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"].includes(
                                      a.status,
                                    ) ? (
                                      <span className={chipClass("neutral")}>
                                        {STATUS_VN[a.status] ?? a.status}
                                      </span>
                                    ) : a.status !== "CHECKED_IN" &&
                                      a.status !== "COMPLETED" ? (
                                      // Chưa check-in → điều dưỡng CHƯA điền sinh hiệu
                                      // được (lễ tân phải check-in trước).
                                      <span className="text-label text-ink-faint">
                                        Chờ lễ tân check-in
                                      </span>
                                    ) : (
                                      <div className="flex items-center gap-1.5">
                                        {/* ĐO Ở MÀN ĐO SINH HIỆU (17/09/2026). Biểu mẫu cũ
                                            trong bảng này ghi vào bệnh án chứ không vào
                                            vital_measurement, nên đo ở đây thì hàng chờ bác
                                            sĩ không mở và cờ "đã đo" không bao giờ bật. */}
                                        {a.has_vitals ? (
                                          <span className={chipClass("success")}>Đã đo sinh hiệu</span>
                                        ) : (
                                          <Link href="/do-sinh-hieu" className={buttonClass("primary", "sm")}>
                                            Đo sinh hiệu
                                          </Link>
                                        )}
                                        {a.status === "COMPLETED" && (
                                          <NutInPhieu href={`/print/${a.id}`} />
                                        )}
                                      </div>
                                    )
                                  ) : a.status === "COMPLETED" ? (
                                    <div className="flex items-center gap-1.5">
                                      <span className={chipClass("neutral")}>
                                        Đã khám xong
                                      </span>
                                      <NutInPhieu href={`/print/${a.id}`} />
                                    </div>
                                  ) : a.status === "CHECKED_IN" ? (
                                    /* "Hoàn tác" ĐỨNG CẠNH chip, không xuống
                                       dòng dưới (Tuyền 16/09/2026): chữ "Hoàn
                                       tác check-in" nằm một mình một dòng dưới
                                       mỗi khách làm cột này cao gấp đôi, mà
                                       ngay bên trái đã có chữ "Đang chờ khám"
                                       nói rõ đang hoàn tác cái gì. */
                                    <div className="flex items-center gap-1.5">
                                      <span className={chipClass("success")}>
                                        Đang chờ khám
                                      </span>
                                      <button
                                        onClick={() => act(a.id, "undo_checkin")}
                                        disabled={busyId === a.id}
                                        title="Hoàn tác check-in"
                                        className="rounded-chip border border-line px-2 py-0.5 text-label font-medium text-ink-muted hover:border-ink-muted hover:text-ink disabled:opacity-50"
                                      >
                                        Hoàn tác
                                      </button>
                                    </div>
                                  ) : ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"].includes(
                                      a.status,
                                    ) ? (
                                    <div className="flex items-center gap-2">
                                      <NutCheckIn
                                        size="sm"
                                        onChon={() => act(a.id, "checkin")}
                                        disabled={busyId === a.id}
                                      >
                                        {busyId === a.id ? "..." : "Check-in"}
                                      </NutCheckIn>
                                      {/* Viền bo quanh "Không đến" — cùng lý
                                          do với "Hoàn tác": chữ trần cạnh một
                                          nút có nền trông như dòng chú thích,
                                          không như thứ bấm được. */}
                                      <button
                                        onClick={() => act(a.id, "no_show")}
                                        disabled={busyId === a.id}
                                        className="rounded-chip border border-line px-2 py-0.5 text-label font-medium text-ink-muted hover:border-danger hover:text-danger disabled:opacity-50"
                                      >
                                        Không đến
                                      </button>
                                    </div>
                                  ) : (
                                    <span className={chipClass("neutral")}>
                                      {STATUS_VN[a.status] ?? a.status}
                                    </span>
                                  )}
                                </td>
                              )}
                              {coMenu && (
                                <td className={CELL}>
                                  <MenuLich a={a} />
                                </td>
                              )}
                            </>
                          ) : (
                            <>
                              <td className={`${CELL}`}>
                                {r.free?.href ? (
                                  <Link
                                    href={r.free.href}
                                    className="inline-block rounded bg-success-bg px-2 py-1 text-label font-semibold text-success hover:bg-success-bg"
                                  >
                                    {canCheckin(role)
                                      ? "＋ Thêm khách hàng"
                                      : "＋ Đặt lịch vào đây"}
                                  </Link>
                                ) : (
                                  <span className="inline-block rounded bg-success-bg px-2 py-1 text-label font-medium text-success/70">
                                    đặt vào đây (còn trống)
                                  </span>
                                )}
                              </td>
                              {/* Ô trống chưa có lịch thì chưa có dịch vụ để ghi. */}
                              <td className={`${CELL} text-ink-faint`}>—</td>
                              <td className={CELL}>
                                <PhanLoai value="Khám lần đầu" />
                              </td>
                              {showActionCol && <td className={CELL} />}
                              {coMenu && <td className={CELL} />}
                            </>
                          )}
                        </tr>
                      );
                    })
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {canWriteClinical && selAppt && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={() => setSelAppt(null)}>
          <div className="flex h-full w-full max-w-lg flex-col border-l border-hairline bg-surface p-4 shadow-panel" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between border-b border-hairline pb-2">
              <h3 className="text-base font-semibold text-brand-800">Hành chính & Sinh hiệu bệnh nhân</h3>
              <button onClick={() => setSelAppt(null)} className="rounded-md p-1 text-brand-800 hover:bg-brand-100">
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto">
              <ClinicalRecordForm
                appt={selAppt}
                staffId={staffId}
                vitalsOnly
                readOnly={!canWriteClinical}
                fill
                onClose={() => setSelAppt(null)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
