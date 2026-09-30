"use client";

// Bảng "Lịch hẹn khám (check đặt lịch)" — TÁI CẤU TRÚC 2026-07-02 theo mô hình
// "rạp chiếu phim": gom theo NGÀY → KHUNG GIỜ 15' → BÁC SĨ TRỰC; mỗi bác sĩ tối
// đa 2 dòng lịch hẹn kênh thường (BN1/BN2) + 1 dòng khách vãng lai (WALK_IN).
// Khi chỗ vãng lai của khung còn trống (và khung chưa qua) hiện Ô XANH "đặt vào
// đây" — hôm nay thì bấm được, dẫn sang Tạo bệnh nhân với ngày/giờ/bác sĩ điền
// sẵn. Số ghế trực tiếp còn trống do MÁY CHỦ trả trên từng dòng
// (`ghe_truc_tiep_con`, theo luật riêng bác sĩ × khung — 29/09/2026).
// Read-only với dữ liệu thật từ appointment; cột thao tác check-in/sinh hiệu
// giữ nguyên như bản trước.

import { useState, Fragment, type MouseEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ChevronDown, ChevronRight, MoreHorizontal } from "lucide-react";
import {
  canCheckin,
  canManageAppt,
  canWriteIntake,
  isNurseRole,
  type ClinicRole,
} from "../../../lib/roles";
import DoiLichTaiCho from "../_lam-viec/DoiLichTaiCho";
import {
  DoiDichVuKhamTaiCho,
  GhiChamSocTaiCho,
  HuyLichTaiCho,
  type LichTaiCho,
} from "../_lam-viec/ThaoTacLichTaiCho";
import { PopupHanhTrinhKhach } from "../_lam-viec/HanhTrinhKhach";
import { hrefDatLich, hrefHoSoKhach, hrefThemKhach } from "../../../lib/lien-ket-lich";
import { dayLabel, fmtDayMonth, todayVn } from "../../../lib/roster";
import { ngayVN, nowMs, VN_TZ } from "../../../lib/datetime";
import { doctorName } from "../../../lib/doctor-name";
import { slotMs, slotBucketMs, isWalkinChannel } from "../../../lib/slot-capacity";
import { useBookingPolicy } from "../BookingPolicyContext";
import { laKhamMoi, nhanPhanLoaiKham } from "../../../lib/phan-loai-kham";
import { chipClass, type ChipTone } from "@/components/ui/Chip";
import { buttonClass } from "@/components/ui/Button";
import NutInPhieu from "@/components/ui/NutInPhieu";
import type { BookingPolicy } from "../../../lib/booking-policy";
import NutCheckIn from "@/components/ui/NutCheckIn";
import { CA_TUAN, locTheoNgay, ngayDangChon, tabNgay } from "./loc-ngay";
import type { MaXacMinh } from "@/lib/xac-minh";

export interface WeekApptRow {
  id: string;
  slot_start: string;
  status: string;
  queue_number: string | null;
  /** Số booking — cấp NGAY lúc đặt, theo ngày hẹn (luồng chuẩn bước 4). */
  so_booking?: number | null;
  /** Số quầy — cấp lúc check-in. Đứng cạnh số booking. */
  so_tiep_don?: number | null;
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
  /** Lịch còn chiếm ghế không — máy chủ tính (danh sách trạng thái chết chỉ
   *  còn ở Python, 29/09/2026). */
  giu_cho?: boolean;
  /** Ghế TRỰC TIẾP còn trống ở (bác sĩ × khung) của dòng này, theo luật riêng
   *  của bác sĩ ấy. null = máy chủ không biết → không mời đặt. */
  ghe_truc_tiep_con?: number | null;
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
  /** Lượt khám của lịch (đã check-in) — bấm tên mở Hành trình khách. */
  visit_id?: string | null;
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

/** Trạng thái lịch: chấm màu + chữ (kiểu Linear). Chỉ đọc `status` — không
 *  tự suy "trễ" từ giờ: khách trễ đếm ở backend (cột Cần xử lý). */
const TONE_TT: Record<string, ChipTone> = {
  SCHEDULED: "warning",
  CSKH_CONFIRMED: "neutral",
  CONFIRMED: "neutral",
  CHECKED_IN: "success",
  COMPLETED: "info",
};
function TrangThaiLich({ status }: { status: string }) {
  return (
    <span className={chipClass(TONE_TT[status] ?? "neutral")}>
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {STATUS_VN[status] ?? status}
    </span>
  );
}

/** Bác sĩ của dòng: tên, dịch vụ ở dòng phụ (bỏ vòng tròn — Tuyền 27/09/2026). */
function BacSiDong({
  ten,
  ma,
  dichVu,
}: {
  ten: string;
  ma: string | null;
  dichVu: string | null;
}) {
  return (
    <div className="min-w-0">
      <span className={`block whitespace-nowrap ${ma ? "text-ink" : "text-ink-faint"}`}>
        {ten || NO_DOCTOR}
      </span>
      {dichVu ? <span className="block whitespace-nowrap text-meta text-ink-muted">{dichVu}</span> : null}
    </div>
  );
}

// Ô thân chung — KHÔNG KẺ (Tuyền chốt "bảng A", 27/09/2026). Trước đó là kẻ
// ngang hairline mọi dòng (DESIGN.md §6, bỏ kẻ dọc 15/08); nay dòng tách
// nhau bằng khoảng trắng + nền khi rê chuột.
const CELL = "px-2 py-2 align-middle";
// Tiêu đề cột: chữ thường nhạt, không nền, không chữ hoa — nó chỉ để tra
// cột, không để đọc; màu thương hiệu dành cho hành động (DESIGN.md §2).
const TH =
  "border-b border-hairline px-2 py-2 text-left text-meta font-medium text-ink-faint";

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
  doctor?: { label: string; span: number; id: string }; // dòng đầu nhóm bác sĩ ("" = chưa phân)
  appt?: WeekApptRow; // dòng lịch thật…
  /** …hoặc ô xanh "đặt vào đây" (href null = chỉ nhìn). `themKhach` = lối quầy
   *  "＋ Thêm khách hàng" (màn Thêm khách hàng); không = "＋ Đặt lịch vào đây". */
  free?: { href: string | null; themKhach: boolean };
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
  /** Người quầy (check-in được): ô trống là "＋ Thêm khách hàng" → màn Thêm
   *  khách hàng điền sẵn ngày/giờ/bác sĩ (Tuyền 29/09/2026). */
  themKhach = false,
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
      // Thứ tự gọi do backend tính sẵn (call_order) — luật chỉ còn một bản,
      // ở Python.
      const theoThuTuGoi = (a: WeekApptRow, b: WeekApptRow) =>
        (a.call_order ?? 0) - (b.call_order ?? 0);
      const regular = mine
        .filter((a) => !isWalkinChannel(a.booking_channel))
        .sort(theoThuTuGoi);
      const walkins = mine
        .filter((a) => isWalkinChannel(a.booking_channel))
        .sort(theoThuTuGoi);
      // Ghế trực tiếp còn trống — SỐ CỦA MÁY CHỦ (trần theo bác sĩ × khung,
      // đếm như trigger). Trước 29/09/2026 bảng tự đếm rồi so với trần CHUNG của
      // phòng khám, nên mời "đặt vào đây" ở khung mà luật riêng đã hạ về 0.
      const gheTrucTiepCon =
        mine.find((a) => typeof a.ghe_truc_tiep_con === "number")?.ghe_truc_tiep_con ??
        null;
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
        const khung = { ngay: day.date, gio: bucketHHMM(bucketMs), bacSi: g.id };
        groupRows.push({
          key: `${bucketMs}-${g.id}-free`,
          free: {
            href: themKhach ? hrefThemKhach(khung) : hrefDatLich(khung),
            themKhach,
          },
        });
      } else if (
        canBook &&
        g.id &&
        bucketNotPast &&
        gheTrucTiepCon !== null &&
        gheTrucTiepCon > 0
      ) {
        groupRows.push({
          key: `${bucketMs}-${g.id}-free`,
          free: {
            href: isToday
              ? hrefThemKhach({ ngay: day.date, gio: bucketHHMM(bucketMs), bacSi: g.id })
              : null,
            themKhach,
          },
        });
      }
      if (groupRows.length === 0) continue;
      groupRows[0].doctor = { label: g.label, span: groupRows.length, id: g.id };
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

/** Trạng thái còn đổi sang hôm nay + check-in được (khách chưa tới quầy). */
const TRUOC_KHI_DEN = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"];
/** Trạng thái còn đổi lịch được (máy chủ chốt lại — `_ALIVE`). */
const CON_SONG = [...TRUOC_KHI_DEN, "CHECKED_IN"];

/** Đóng menu `<details>` chứa nút vừa bấm. */
function dongMenu(el: HTMLElement) {
  el.closest("details")?.removeAttribute("open");
}

/** Thao tác tại chỗ đang mở từ menu ⋯ (29/09/2026; "dichVu" = V5 30/09). */
type LoaiTaiCho = "huy" | "goi" | "dichVu";

/** Dòng lịch → dữ liệu vẽ đầu hộp của thao tác tại chỗ. */
function lichTaiCho(a: WeekApptRow): LichTaiCho | null {
  const p = a.patient;
  if (!p?.clinic_patient_id) return null;
  return {
    id: a.id,
    slot_start: a.slot_start,
    clinic_patient_id: p.clinic_patient_id,
    ten: p.full_name ?? "",
    sdt: p.phone_primary,
    bac_si: a.doctor?.full_name ?? null,
    dich_vu: a.service?.name ?? null,
  };
}

/** Menu "…" của một dòng lịch — MỌI dòng (29/09/2026). "Đổi lịch" / "Đổi sang
 *  hôm nay" mở popover Đổi lịch; "Huỷ lịch" và "Gọi / ghi chăm sóc" mở popover
 *  làm TẠI CHỖ neo dòng; "Mở hồ sơ khách" nhảy sang Danh sách bệnh nhân với
 *  khách chọn sẵn. Mỗi mục chỉ hiện với quyền tương ứng (máy chủ vẫn tự kiểm). */
function MenuLich({
  a,
  laHomNay,
  duocDoiLich,
  duocDoiDichVu,
  duocGhiChamSoc,
  duocXemHoSo,
  onDoiLich,
  onTaiCho,
}: {
  a: WeekApptRow;
  laHomNay: boolean;
  duocDoiLich: boolean;
  duocDoiDichVu: boolean;
  duocGhiChamSoc: boolean;
  duocXemHoSo: boolean;
  onDoiLich: (neo: HTMLElement, ngayDau?: string) => void;
  onTaiCho: (loai: LoaiTaiCho, neo: HTMLElement) => void;
}) {
  const pid = a.patient?.clinic_patient_id;
  if (!pid) return null;
  const doiDuoc = duocDoiLich && CON_SONG.includes(a.status);
  // Đổi dịch vụ khám (V5): lịch còn sống; đổi được hay không (đã khám, đã thu
  // tiền khám…) do máy chủ nói trong popover.
  const doiDichVuDuoc = duocDoiDichVu && CON_SONG.includes(a.status);
  if (
    !doiDuoc &&
    !doiDichVuDuoc &&
    !duocGhiChamSoc &&
    !duocXemHoSo &&
    !a.patient?.phone_primary
  )
    return null;
  const MUC = "block w-full rounded-control px-2 py-1.5 text-left hover:bg-surface-muted";
  const moTaiCho = (loai: LoaiTaiCho) => (e: MouseEvent<HTMLButtonElement>) => {
    const tr = e.currentTarget.closest("tr");
    dongMenu(e.currentTarget);
    if (tr) onTaiCho(loai, tr);
  };
  return (
    <details className="relative">
      <summary
        aria-label="Thao tác với lịch này"
        className="grid size-7 cursor-pointer list-none place-items-center rounded-control text-ink-muted hover:bg-surface-sunken"
      >
        <MoreHorizontal className="size-4" />
      </summary>
      <div className="absolute right-0 z-20 mt-1 w-52 rounded-card border border-hairline bg-surface p-1 text-body shadow-panel">
        {duocXemHoSo ? (
          <Link href={hrefHoSoKhach(pid)} className={MUC}>
            Mở hồ sơ khách
          </Link>
        ) : null}
        {duocGhiChamSoc ? (
          <button type="button" className={MUC} onClick={moTaiCho("goi")}>
            Gọi / ghi chăm sóc
          </button>
        ) : null}
        {doiDuoc && !laHomNay && TRUOC_KHI_DEN.includes(a.status) ? (
          <button
            type="button"
            className={`${MUC} font-medium text-brand-700`}
            onClick={(e) => {
              const tr = e.currentTarget.closest("tr");
              dongMenu(e.currentTarget);
              if (tr) onDoiLich(tr);
            }}
          >
            Đổi sang hôm nay
          </button>
        ) : null}
        {doiDuoc ? (
          <button
            type="button"
            className={MUC}
            onClick={(e) => {
              const tr = e.currentTarget.closest("tr");
              dongMenu(e.currentTarget);
              if (tr) onDoiLich(tr, ngayVN(a.slot_start));
            }}
          >
            Đổi lịch
          </button>
        ) : null}
        {doiDichVuDuoc ? (
          <button type="button" className={MUC} onClick={moTaiCho("dichVu")}>
            Đổi dịch vụ khám
          </button>
        ) : null}
        {doiDuoc ? (
          <button type="button" className={`${MUC} text-danger`} onClick={moTaiCho("huy")}>
            Huỷ lịch (ghi lý do)
          </button>
        ) : null}
        {a.patient?.phone_primary && (
          <a href={`tel:${a.patient.phone_primary}`} className={MUC}>
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
  dutyByDate = {},
  choDoSinhHieu,
  choCheckIn = false,
  chonNgay = false,
  choThemKhach = true,
  duocCheckIn,
  duocDoiLich,
  duocDatLich,
  duocDoiDichVu = false,
  duocGhiChamSoc = false,
  duocXemHoSo = false,
  moHoSoKhach = true,
}: {
  days: ApptDay[];
  role: ClinicRole | null;
  dutyByDate?: DutyByDate;
  /** Hiện cột "Điền sinh hiệu". Trang chủ quyết theo VỊ TRÍ hôm nay (đứng Đo
   *  chỉ số); không truyền thì theo vai điều dưỡng như trước. */
  choDoSinhHieu?: boolean;
  /** Hiện cột Check-in / Không đến / Hoàn tác. CHỈ màn Tiếp đón khách bật
   *  (Tuyền chốt 18/09/2026: check-in bỏ khỏi Trang chủ — một việc, một chỗ).
   *  Trang chủ không truyền → bảng chỉ để xem. */
  choCheckIn?: boolean;
  /** Hàng chip T2…CN + "Cả tuần" lọc bảng còn MỘT ngày, giữ trên `?ngay=`
   *  (27/09/2026, đợt 3). CHỈ Trang chủ bật — Tiếp đón khách đã vẽ riêng hôm
   *  nay nên không truyền. */
  chonNgay?: boolean;
  /** Dòng "+ Thêm khách hàng / Đặt lịch vào đây" dưới từng bác sĩ mỗi khung.
   *  Trang chủ TẮT (Tuyền 28/09/2026: nhiều bác sĩ thì dòng này lặp khắp bảng;
   *  đặt lịch làm ở màn Đặt lịch). Tiếp đón khách giữ nguyên. */
  choThemKhach?: boolean;
  /** Được bấm Check-in theo LEGO của tài khoản (`reception.checkin.perform`) —
   *  đợt 3, 27/09/2026 ("chỉ dùng lego"). Không truyền (máy chủ chưa trả lời
   *  quyền) → theo vai như trước. */
  duocCheckIn?: boolean;
  /** Được đổi lịch theo LEGO (`booking.manage`) — trang truyền từ quyền của
   *  tài khoản. Không truyền → theo vai như trước. */
  duocDoiLich?: boolean;
  /** Ô trống mở màn Đặt lịch theo LEGO (`booking.create`) — mở full lego
   *  30/09/2026. Không truyền → theo vai như trước. */
  duocDatLich?: boolean;
  /** ⋯ "Đổi dịch vụ khám" (V5, 30/09/2026) — có `booking.manage` hoặc
   *  `reception.checkin.perform` (`QUYEN_DOI_DICH_VU_KHAM`). Không truyền → ẩn. */
  duocDoiDichVu?: boolean;
  /** ⋯ "Gọi / ghi chăm sóc" — có quyền ghi sổ tương tác CSKH
   *  (`QUYEN_GHI_CHAM_SOC`). Không truyền → ẩn. */
  duocGhiChamSoc?: boolean;
  /** ⋯ "Mở hồ sơ khách" (link Danh sách bệnh nhân `?chon=`) — người xem vào
   *  được `/patient-list` (trang hỏi `moDuocMan`). Không truyền → ẩn. */
  duocXemHoSo?: boolean;
  /** Người xem mở được màn Quản lý khách hàng (`moDuocMan("/customers")`) —
   *  bấm tên khách CHƯA check-in mở hồ sơ ở đó. */
  moHoSoKhach?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // Ngày đang chọn đọc THẲNG từ thanh địa chỉ mỗi lần vẽ, không giữ state riêng:
  // bấm "Tuần sau" / "Về tuần này" (Link của WeekNav) là URL đổi và lựa chọn
  // đi theo — state riêng thì giữ nhầm ngày của tuần cũ khi đổi tuần.
  const ngayChon = chonNgay
    ? ngayDangChon(searchParams.get("ngay"), days.map((d) => d.date), todayVn())
    : null;
  const daysHien = chonNgay ? locTheoNgay(days, ngayChon) : days;
  /** Đổi ngày: chỉ ghi lại URL (không tải lại trang, không gọi máy chủ) — dữ
   *  liệu cả tuần đã có sẵn trên màn. */
  function chonNgayMoi(ma: string) {
    const sp = new URLSearchParams(searchParams.toString());
    sp.set("ngay", ma);
    window.history.replaceState(null, "", `${pathname}?${sp.toString()}`);
  }
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Popover Đổi lịch tại chỗ (29/09/2026) + popup Hành trình khách.
  const [doiLich, setDoiLich] = useState<{
    id: string;
    neo: HTMLElement;
    ngayDau?: string;
  } | null>(null);
  const [hanhTrinh, setHanhTrinh] = useState<{ id: string; ten: string } | null>(null);
  // Huỷ / Gọi-ghi chăm sóc / Hồ sơ khách tại chỗ (29/09/2026).
  const [taiCho, setTaiCho] = useState<{
    loai: LoaiTaiCho;
    lich: LichTaiCho;
    neo: HTMLElement;
  } | null>(null);
  const [thongBao, setThongBao] = useState<string | null>(null);
  // Bảng này gom lịch theo KHUNG — độ dài khung và số chỗ vãng lai là cấu hình
  // của phòng khám, nên không có bản mặc định ở đây.
  const policy = useBookingPolicy();

  // GẬP / MỞ THEO NGÀY (ảnh Tuyền 16/09/2026): ngày có lịch mở sẵn, ngày trống
  // gập gọn một dòng. `moTay` giữ lựa chọn tay theo ngày; chưa bấm thì theo
  // mặc định — đổi tuần không kéo theo trạng thái của tuần cũ.
  const [moTay, setMoTay] = useState<Record<string, boolean>>({});
  const dangMo = (d: ApptDay) => moTay[d.date] ?? d.items.length > 0;
  const showActions = choCheckIn && (duocCheckIn ?? canCheckin(role));
  // Menu "…" ở MỌI dòng cho người đổi được lịch (29/09/2026) — kể cả màn Tiếp
  // đón (trước đây ẩn khi có cột check-in).
  const doiLichDuoc = duocDoiLich ?? canManageAppt(role);
  const coMenu =
    doiLichDuoc || showActions || duocDoiDichVu || duocGhiChamSoc || duocXemHoSo;
  /** Dòng "＋ Thêm khách hàng" theo LEGO check-in máy chủ trả (`duocCheckIn`),
   *  không theo vai (30/09/2026). Máy chủ chưa trả lời quyền → không mời. */
  const quayThemKhach = duocCheckIn === true;
  const homNay = todayVn();
  /** Màn Tiếp đón, ngày KHÁC hôm nay, khách chưa tới: bấm dòng / tên mở thẳng
   *  Đổi lịch với "Hôm nay" chọn sẵn (Tuyền 29/09/2026). */
  const moDoiSangHomNay = (a: WeekApptRow, ngay: string) =>
    choCheckIn && doiLichDuoc && ngay !== homNay && TRUOC_KHI_DEN.includes(a.status);

  /** Bấm TÊN khách: (Tiếp đón, ngày khác) → Đổi lịch; đã có lượt khám →
   *  Hành trình khách; chưa → hồ sơ khách. */
  function bamTen(a: WeekApptRow, ngay: string, neo: HTMLElement | null) {
    if (moDoiSangHomNay(a, ngay) && neo) {
      setDoiLich({ id: a.id, neo });
      return;
    }
    if (a.visit_id) {
      setHanhTrinh({ id: a.visit_id, ten: a.patient?.full_name ?? "" });
      return;
    }
    const pid = a.patient?.clinic_patient_id;
    if (pid && moHoSoKhach) router.push(`/customers?selected=${pid}`);
  }

  // Điều dưỡng: KHÔNG check-in (việc Lễ tân) mà điền SINH HIỆU ngay trên lịch hẹn.
  const isNurse = choDoSinhHieu ?? isNurseRole(role);
  const showActionCol = showActions || isNurse;
  const nCols = 4 + (showActions ? 0 : 1) + (showActionCol ? 1 : 0) + (coMenu ? 1 : 0);

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

  function daDoiLich(cau: string) {
    setThongBao(cau);
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
      <p className="py-10 text-center text-body text-ink-muted">
        Chưa có lịch hẹn nào trong tuần này.
      </p>
    );
  }

  const now = nowMs();

  return (
    <div className="space-y-2">
      {error && (
        <div className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">
          {error}
        </div>
      )}
      {thongBao && (
        <div
          role="status"
          className="flex items-center justify-between gap-2 rounded-control bg-success-bg px-3 py-2 text-meta text-success"
        >
          <span>✓ {thongBao}</span>
          <button
            type="button"
            onClick={() => setThongBao(null)}
            className="rounded-control px-1.5 text-label font-medium hover:bg-surface"
          >
            Đóng
          </button>
        </div>
      )}
      {/* DẢI NGÀY KIỂU TAB (Tuyền 27/09/2026: "tối giản thông minh, đừng bày
          hết ra"): chữ trần, gạch chân ngày đang xem, số lịch nhạt bên cạnh —
          thay hàng chip hộp. Hẹp thì cuộn ngang trong dải, không vỡ dòng. */}
      {chonNgay ? (
        <div className="flex items-end gap-2 border-b border-hairline">
          <div
            role="tablist"
            aria-label="Chọn ngày xem lịch hẹn"
            className="-mb-px flex min-w-0 flex-1 overflow-x-auto"
          >
            {tabNgay(days).map((t) => {
              const dang = (ngayChon ?? CA_TUAN) === t.ma;
              const laHomNay = t.ma === todayVn();
              return (
                <button
                  key={t.ma}
                  type="button"
                  role="tab"
                  aria-selected={dang}
                  title={t.title}
                  onClick={() => chonNgayMoi(t.ma)}
                  className={`inline-flex h-9 shrink-0 items-center gap-1 border-b-2 px-2.5 text-meta whitespace-nowrap transition-colors ${
                    dang
                      ? "border-brand-600 font-semibold text-ink"
                      : `border-transparent hover:text-ink ${laHomNay ? "text-brand-700" : "text-ink-muted"}`
                  }`}
                >
                  {t.nhan}
                  {t.so > 0 ? (
                    <span className="rounded-chip bg-surface-sunken px-1 text-label font-medium tabular-nums text-ink-muted">
                      {t.so}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
          {/* Mở/Đóng tất cả chỉ có nghĩa khi đang xem NHIỀU ngày. */}
          {daysHien.length > 1 ? (
            <div className="hidden shrink-0 items-center gap-1 pb-1.5 sm:flex">
              <button
                type="button"
                onClick={() => setMoTay(Object.fromEntries(daysHien.map((d) => [d.date, true])))}
                className="rounded-control px-2 py-1 text-label text-ink-muted hover:bg-surface-sunken hover:text-ink"
              >
                Mở tất cả
              </button>
              <button
                type="button"
                onClick={() => setMoTay(Object.fromEntries(daysHien.map((d) => [d.date, false])))}
                className="rounded-control px-2 py-1 text-label text-ink-muted hover:bg-surface-sunken hover:text-ink"
              >
                Đóng tất cả
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
      {/* BẢNG KHÔNG KẺ KIỂU LINEAR (Tuyền chốt Trang chủ "bảng A", 27/09/2026):
          bỏ khung viền quanh bảng, bỏ dải tiêu đề chữ hoa, bỏ gộp ô theo
          bác sĩ. Mỗi dòng tự đủ nghĩa: giờ · khách (tên đậm + dòng phụ nhạt)
          · bác sĩ + dịch vụ · trạng thái chấm màu · loại
          khám. Khung giờ chỉ in ở dòng đầu khung — thứ nhóm dòng là khoảng
          trắng, không phải lưới ô. */}
      <div className="max-h-[88vh] min-h-45 max-w-full overflow-auto">
        <table className="w-full min-w-160 border-collapse text-body">
          <thead className="sticky top-0 z-10 bg-surface">
            <tr>
              <th className={`${TH} w-16`}>Giờ</th>
              <th className={`${TH} min-w-48`}>Khách</th>
              <th className={`${TH} min-w-44`}>Bác sĩ · dịch vụ</th>
              {!showActions && <th className={TH}>Trạng thái</th>}
              <th className={TH}>Phân loại</th>
              {showActionCol && (
                <th className={`${TH} min-w-38`}>
                  {isNurse ? "Sinh hiệu" : "Thao tác Check-in"}
                </th>
              )}
              {coMenu && <th className={`${TH} w-12`}><span className="sr-only">Thao tác</span></th>}
            </tr>
          </thead>
          <tbody>
            {daysHien.map((day) => {
              const rows = buildDayRows(
                day,
                dutyByDate[day.date] ?? [],
                now,
                choThemKhach && (duocDatLich ?? canWriteIntake(role)),
                policy,
                // LỄ TÂN ĐI CHUNG ĐƯỜNG VỚI CSKH (Tuyền 16/09/2026): ô trống mở
                // màn đặt lịch, không còn rẽ sang biểu mẫu vãng lai của riêng
                // quầy. "Vãng lai" nay chỉ là một KÊNH ĐẶT, không phải một
                // luồng — nên ngày mai, ngày kia cũng bấm được, không chỉ hôm nay.
                choThemKhach && (doiLichDuoc || quayThemKhach),
                // Người quầy: "＋ Thêm khách hàng" về màn Thêm khách hàng, không
                // phải màn Đặt lịch (Tuyền 29/09/2026). Theo lego check-in.
                quayThemKhach,
              );
              const mo = dangMo(day);
              // Bác sĩ của từng dòng: buildDayRows chỉ gắn nhãn ở dòng ĐẦU nhóm
              // (thời bảng còn gộp ô) — mang nhãn ấy xuống các dòng sau.
              let bacSiNhom: { label: string; id: string | null } = { label: "", id: null };
              return (
                <Fragment key={day.date}>
                  {/* Dòng tiêu đề NGÀY — bấm để gập / mở. Ngày trống nói
                      "chưa có lịch hẹn" NGAY trên dòng này, không thêm dòng. */}
                  {/* Đang xem MỘT ngày thì dải ngày đã nói ngày nào — bỏ dòng này. */}
                  {daysHien.length > 1 ? (
                  <tr>
                    <td colSpan={nCols} className="px-2 pb-1 pt-4 first:pt-2">
                      <button
                        type="button"
                        onClick={() => setMoTay((m) => ({ ...m, [day.date]: !mo }))}
                        aria-expanded={mo}
                        className="inline-flex items-center gap-1.5 rounded-control px-1 py-0.5 text-meta font-semibold text-ink-soft hover:bg-surface-sunken"
                      >
                        {mo ? (
                          <ChevronDown className="size-4 text-ink-muted" />
                        ) : (
                          <ChevronRight className="size-4 text-ink-muted" />
                        )}
                        {dayLabel(day.date)} · {fmtDayMonth(day.date)}
                        <span className="font-normal text-ink-faint">
                          {day.items.length > 0 ? `${day.items.length} lịch` : "chưa có lịch hẹn"}
                        </span>
                      </button>
                    </td>
                  </tr>
                  ) : null}
                  {(!mo && daysHien.length > 1) || rows.length === 0 ? null : (
                    rows.map((r) => {
                      const a = r.appt;
                      if (r.doctor) {
                        bacSiNhom = {
                          label: r.doctor.label,
                          id: r.doctor.id || null,
                        };
                      }
                      return (
                        <tr
                          key={r.key}
                          className={`group transition-colors hover:bg-surface-sunken ${
                            a && moDoiSangHomNay(a, day.date) ? "cursor-pointer" : ""
                          }`}
                          onClick={
                            a && moDoiSangHomNay(a, day.date)
                              ? (e) => {
                                  // Nút / link / menu trong dòng tự làm việc của chúng.
                                  const t = e.target as HTMLElement;
                                  if (t.closest("button,a,summary,details,input,select")) return;
                                  setDoiLich({ id: a.id, neo: e.currentTarget });
                                }
                              : undefined
                          }
                        >
                          <td className={`${CELL} whitespace-nowrap tabular-nums font-semibold text-ink`}>
                            {r.bucket ? r.bucket.label.split(" - ")[0] : ""}
                          </td>
                          {a ? (
                            <>
                              <td className={`${CELL} text-ink`}>
                                {/* BÁC SĨ NGHỈ SAU KHI KHÁCH ĐÃ ĐẶT.
                                    Đặt ngay tại dòng lịch, không gom về đầu
                                    bảng: người đọc quét dọc cột giờ để gọi tên,
                                    nên câu cảnh báo phải nằm ở đúng dòng họ
                                    đang nhìn. Cùng nguồn với khung báo ở Quản
                                    lý khách hàng (16/09/2026). Gỡ ca KHÔNG huỷ
                                    lịch (luật 15/09): việc là gọi khách đổi
                                    lịch, hoặc gán lại bác sĩ khi ca đã xếp lại. */}
                                {/* SỐ BOOKING ĐỨNG ĐẦU DÒNG (Tuyền 27/09/2026: "đưa số
                                    booking ra chỗ ô tròn trước tên"), không vòng tròn. */}
                                <div className="flex items-baseline gap-2">
                                  <span className="w-7 shrink-0 text-right text-meta tabular-nums text-ink-faint">
                                    {a.so_booking != null ? `#${a.so_booking}` : ""}
                                  </span>
                                  <div className="min-w-0">
                                    {(a.mat_bac_si || a.bac_si_da_go || a.vuot_suc_chua) && (
                                      <span className="mb-1 block rounded-chip bg-warning-bg px-1.5 py-0.5 text-label font-semibold text-warning">
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
                                    {a.visit_id || moHoSoKhach || moDoiSangHomNay(a, day.date) ? (
                                      <button
                                        type="button"
                                        onClick={(e) => bamTen(a, day.date, e.currentTarget.closest("tr"))}
                                        className="flex items-center gap-1.5 text-left font-medium text-ink hover:text-brand-700 hover:underline"
                                      >
                                        {isNurse &&
                                          a.status === "CHECKED_IN" &&
                                          !a.has_vitals && (
                                            <span
                                              title="Cần điền sinh hiệu"
                                              className="inline-flex size-4 shrink-0 animate-pulse items-center justify-center rounded-full bg-danger text-label font-bold leading-none text-white motion-reduce:animate-none"
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
                                    <span className="block text-meta text-ink-muted">
                                      {a.patient?.phone_primary ?? a.patient?.patient_code}
                                      {a.so_tiep_don != null ? ` · Quầy ${a.so_tiep_don}` : ""}
                                      {isWalkinChannel(a.booking_channel) ? " · vãng lai" : ""}
                                    </span>
                                  </div>
                                </div>
                              </td>
                              <td className={CELL}>
                                <BacSiDong
                                  ten={bacSiNhom.label}
                                  ma={a.doctor_id}
                                  dichVu={a.service?.name ?? null}
                                />
                              </td>
                              {!showActions && (
                                <td className={CELL}>
                                  <TrangThaiLich status={a.status} />
                                </td>
                              )}
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
                                       dòng dưới (Tuyền 16/09/2026). */
                                    <div className="flex items-center gap-1.5">
                                      <span className={chipClass("success")}>
                                        Đang chờ khám
                                      </span>
                                      <button
                                        type="button"
                                        onClick={() => act(a.id, "undo_checkin")}
                                        disabled={busyId === a.id}
                                        title="Hoàn tác check-in"
                                        className="rounded-chip border border-line px-2 py-0.5 text-label font-medium text-ink-muted hover:border-ink-muted hover:text-ink disabled:opacity-50"
                                      >
                                        Hoàn tác
                                      </button>
                                    </div>
                                  ) : TRUOC_KHI_DEN.includes(a.status) && day.date !== homNay ? (
                                    // Check-in / Không đến CHỈ ở hôm nay (29/09/2026).
                                    // Ngày khác: bấm dòng để đổi sang hôm nay.
                                    <TrangThaiLich status={a.status} />
                                  ) : TRUOC_KHI_DEN.includes(a.status) ? (
                                    <div className="flex items-center gap-2">
                                      <NutCheckIn
                                        size="sm"
                                        onChon={() => act(a.id, "checkin")}
                                        disabled={busyId === a.id}
                                      >
                                        {busyId === a.id ? "..." : "Check-in"}
                                      </NutCheckIn>
                                      {/* Viền bo quanh "Không đến" — chữ trần cạnh
                                          một nút có nền trông như chú thích. */}
                                      <button
                                        type="button"
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
                                // Nút "…" chỉ hiện khi rê chuột / đang mở / đang
                                // chọn bằng bàn phím — dòng lặng khi chỉ đọc.
                                <td className={`${CELL} opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 has-[[open]]:opacity-100 max-md:opacity-100`}>
                                  <MenuLich
                                    a={a}
                                    laHomNay={day.date === homNay}
                                    duocDoiLich={doiLichDuoc}
                                    duocDoiDichVu={duocDoiDichVu}
                                    duocGhiChamSoc={duocGhiChamSoc}
                                    duocXemHoSo={duocXemHoSo}
                                    onDoiLich={(neo, ngayDau) => setDoiLich({ id: a.id, neo, ngayDau })}
                                    onTaiCho={(loai, neo) => {
                                      const lich = lichTaiCho(a);
                                      if (lich) setTaiCho({ loai, lich, neo });
                                    }}
                                  />
                                </td>
                              )}
                            </>
                          ) : (
                            <>
                              <td className={CELL}>
                                {r.free?.href ? (
                                  <Link
                                    href={r.free.href}
                                    className="inline-flex items-center rounded-chip px-2 py-1 text-meta font-medium text-success hover:bg-success-bg"
                                  >
                                    {r.free.themKhach
                                      ? "＋ Thêm khách hàng"
                                      : "＋ Đặt lịch vào đây"}
                                  </Link>
                                ) : (
                                  <span className="px-2 text-meta text-ink-faint">
                                    còn trống
                                  </span>
                                )}
                              </td>
                              <td className={CELL}>
                                {/* Dòng chỗ trống: tên bác sĩ nhạt — chỉ để biết chỗ của ai. */}
                                <BacSiDong ten={bacSiNhom.label} ma={null} dichVu={null} />
                              </td>
                              {!showActions && <td className={CELL} />}
                              <td className={CELL} />
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

      {doiLich ? (
        <DoiLichTaiCho
          key={`${doiLich.id}-${doiLich.ngayDau ?? ""}`}
          lichId={doiLich.id}
          neo={doiLich.neo}
          ngayDau={doiLich.ngayDau}
          onDong={() => setDoiLich(null)}
          onXong={daDoiLich}
        />
      ) : null}
      {taiCho?.loai === "huy" ? (
        <HuyLichTaiCho
          key={`huy-${taiCho.lich.id}`}
          lich={taiCho.lich}
          neo={taiCho.neo}
          onDong={() => setTaiCho(null)}
          onXong={daDoiLich}
        />
      ) : taiCho?.loai === "dichVu" ? (
        <DoiDichVuKhamTaiCho
          key={`dv-${taiCho.lich.id}`}
          lich={taiCho.lich}
          neo={taiCho.neo}
          onDong={() => setTaiCho(null)}
          onXong={daDoiLich}
        />
      ) : taiCho?.loai === "goi" ? (
        <GhiChamSocTaiCho
          key={`goi-${taiCho.lich.id}`}
          lich={taiCho.lich}
          neo={taiCho.neo}
          onDong={() => setTaiCho(null)}
          onXong={daDoiLich}
        />
      ) : null}
      {hanhTrinh ? (
        <PopupHanhTrinhKhach
          visitId={hanhTrinh.id}
          ten={hanhTrinh.ten}
          onDong={() => setHanhTrinh(null)}
        />
      ) : null}
    </div>
  );
}
