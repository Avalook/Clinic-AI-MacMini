// DANH SÁCH TIẾP ĐÓN (27/09/2026, đợt 3 — bản mẫu Tuyền duyệt).
//
// Máy chủ (`GET /api/v1/reception/danh-sach`, `services/tiep_don_service.py`)
// đã chia buổi, xếp thứ tự và TÍNH chip trạng thái (trễ bao lâu, đang ở đâu,
// bước tiếp). Ở đây chỉ còn việc của trình duyệt: lọc theo tab + ô tìm ngay tại
// chỗ, và đổi `loai` thành tông màu. Hàm thuần — kiểm bằng `node --test`.

import type { ChipTone } from "@/components/ui/Chip";

export type LoaiTrangThai = "cho" | "tre" | "den" | "dang_o" | "ve" | "khong_den";
export type NhomTab = "chua_den" | "da_den" | "khac";
export type TabTiepDon = "tat_ca" | "chua_den" | "da_den";

export interface DongTiepDon {
  appointment_id: string;
  visit_id: string | null;
  clinic_patient_id: string | null;
  ten: string | null;
  ma_khach: string | null;
  sdt: string | null;
  so_booking: number | null;
  so_tiep_don: number | null;
  gio_hen: string | null;
  loai_kham: string | null;
  /** Ghi chú CSKH lúc đặt lịch (`appointment.notes`). */
  ghi_chu?: string | null;
  bac_si: string | null;
  loai_khach: string | null;
  uu_tien: boolean;
  uu_tien_ly_do: string | null;
  trang_thai: { loai: LoaiTrangThai; nhan: string; nhom: NhomTab };
  check_in_duoc: boolean;
  check_out_duoc: boolean;
  /** Khách đã về — máy chủ cho "Hoàn tác" mở lại lượt (01/10/2026). */
  mo_lai_duoc?: boolean;
  /** Hoàn tác CHECK-IN được (09/10/2026) — máy chủ: chỉ khi khách chưa có việc
   *  thật nào sau check-in. Lệnh ghi vẫn tự kiểm lại. */
  hoan_tac_duoc?: boolean;
  /** Vì sao không hoàn tác check-in được ("Khách đã được đo sinh hiệu — …"). */
  ly_do_khong_hoan_tac?: string | null;
}

export interface BuoiTiepDon {
  ma: string;
  nhan: string;
  dong: DongTiepDon[];
}

export interface GoiTiepDon {
  ngay: string;
  buoi: BuoiTiepDon[];
  dem: { tat_ca: number; chua_den: number; da_den: number };
  bi_cat: boolean;
}

/** Tông chip theo loại trạng thái máy chủ trả. Loại lạ → xám (không vỡ màn). */
export function toneTrangThai(loai: string): ChipTone {
  switch (loai) {
    case "tre":
      return "warning";
    case "den":
      return "success";
    case "dang_o":
      return "dang_o";
    default:
      return "neutral";
  }
}

/** Bỏ dấu + chữ thường + gọn khoảng trắng — để gõ "nga" tìm được "Ngà". */
export function chuanHoa(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/** Những gì ô tìm so được của MỘT khách — chung cho danh sách tiếp đón và
 *  bảng Lịch hẹn, để gõ một từ khoá hai bảng lọc như nhau. */
interface KhachTim {
  ten?: string | null;
  ma_khach?: string | null;
  so_booking?: number | null;
  sdt?: string | null;
}

/** `kim` đã chuẩn hoá (`chuanHoa`). Rỗng = khớp mọi khách. */
function khop(d: KhachTim, kim: string): boolean {
  if (!kim) return true;
  const chu = chuanHoa(
    [d.ten, d.ma_khach, d.so_booking != null ? `#${d.so_booking}` : null]
      .filter(Boolean)
      .join(" "),
  );
  if (chu.includes(kim)) return true;
  // SĐT: so theo CHỮ SỐ — "0900 001" khớp "0900001237".
  const so = kim.replace(/\D/g, "");
  return so.length >= 3 && (d.sdt ?? "").replace(/\D/g, "").includes(so);
}

function trongTab(d: DongTiepDon, tab: TabTiepDon): boolean {
  if (tab === "tat_ca") return true;
  return d.trang_thai?.nhom === tab;
}

/** Lọc tại chỗ: tab + ô tìm (tên, mã khách, SĐT, #booking). Buổi rỗng bị bỏ. */
export function locTiepDon(
  buoi: readonly BuoiTiepDon[] | null | undefined,
  tab: TabTiepDon,
  tim: string,
): BuoiTiepDon[] {
  if (!Array.isArray(buoi)) return [];
  const kim = chuanHoa(typeof tim === "string" ? tim : "");
  return buoi
    .map((b) => ({
      ...b,
      dong: (Array.isArray(b?.dong) ? b.dong : []).filter(
        (d: DongTiepDon) => trongTab(d, tab) && khop(d, kim),
      ),
    }))
    .filter((b) => b.dong.length > 0);
}

/** Bộ lọc thanh trên cùng màn Tiếp đón (09/10/2026): một ô tìm + tab lọc CẢ
 *  bảng Lịch hẹn lẫn danh sách tiếp đón. */
export interface LocTiepDon {
  tab: TabTiepDon;
  tim: string;
}

export const LOC_MAC_DINH: LocTiepDon = { tab: "tat_ca", tim: "" };

/** Đang lọc gì không (tab khác "Tất cả" hoặc ô tìm có chữ). Rác → không lọc. */
export function dangLoc(loc: LocTiepDon | null | undefined): boolean {
  if (!loc) return false;
  const tim = typeof loc.tim === "string" ? loc.tim.trim() : "";
  return loc.tab === "chua_den" || loc.tab === "da_den" || tim !== "";
}

/** Trạng thái lịch hẹn → tab. Cùng nghĩa với `nhom` máy chủ trả cho danh sách
 *  tiếp đón: chưa tới quầy = "Chưa đến"; đã check-in (kể cả khám xong) = "Đã
 *  check-in"; không đến / huỷ / bác sĩ từ chối chỉ ở "Tất cả". */
export function nhomLichHen(status: string | null | undefined): NhomTab {
  if (status === "SCHEDULED" || status === "CSKH_CONFIRMED" || status === "CONFIRMED") {
    return "chua_den";
  }
  if (status === "CHECKED_IN" || status === "COMPLETED") return "da_den";
  return "khac";
}

/** Một dòng bảng Lịch hẹn — chỉ phần bộ lọc cần (`WeekApptRow` thoả). */
export interface DongLichLoc {
  status: string;
  so_booking?: number | null;
  patient?: {
    full_name?: string | null;
    patient_code?: string | null;
    phone_primary?: string | null;
  } | null;
}

/** Lọc bảng Lịch hẹn theo cùng tab + ô tìm. GIỮ mọi ngày (dải ngày không nhảy),
 *  chỉ bớt lịch trong ngày. Không lọc gì → trả nguyên mảng. */
export function locLichHen<R extends DongLichLoc, D extends { items: readonly R[] }>(
  days: readonly D[] | null | undefined,
  loc: LocTiepDon | null | undefined,
): D[] {
  if (!Array.isArray(days)) return [];
  if (!loc || !dangLoc(loc)) return [...days];
  const kim = chuanHoa(typeof loc.tim === "string" ? loc.tim : "");
  // Tab lạ → như "Tất cả" (không lọc mất cả bảng).
  const tab = loc.tab === "chua_den" || loc.tab === "da_den" ? loc.tab : null;
  return days.map((d) => {
    const items: readonly R[] = Array.isArray(d?.items) ? d.items : [];
    return {
      ...d,
      items: items.filter(
        (a: R) =>
          (tab === null || nhomLichHen(a?.status) === tab) &&
          khop(
            {
              ten: a?.patient?.full_name,
              ma_khach: a?.patient?.patient_code,
              so_booking: a?.so_booking,
              sdt: a?.patient?.phone_primary,
            },
            kim,
          ),
      ),
    };
  });
}

/** Hướng xem danh sách (29/09/2026, Tuyền): CÁCH XEM, không phải luật.
 *  Máy chủ trả sẵn thứ tự CŨ → MỚI theo giờ vào hàng thật (đã check-in: giờ
 *  check-in; chưa đến: giờ hẹn). "Mới nhất trước" chỉ đảo lại — cả buổi lẫn
 *  dòng trong buổi — màn không tự tính mốc nào. */
export type HuongXep = "cu_truoc" | "moi_truoc";

export const HUONG_XEP_MAC_DINH: HuongXep = "cu_truoc";

/** Khoá localStorage nhớ lựa chọn của máy quầy (chỉ là tiện lợi của người xem). */
export const KHOA_HUONG_XEP = "clinicai:tiep-don:huong-xep";

export function laHuongXep(x: unknown): x is HuongXep {
  return x === "cu_truoc" || x === "moi_truoc";
}

export function sapXepTiepDon(
  buoi: readonly BuoiTiepDon[] | null | undefined,
  huong: HuongXep,
): BuoiTiepDon[] {
  if (!Array.isArray(buoi)) return [];
  if (huong !== "moi_truoc") return [...buoi];
  return [...buoi]
    .reverse()
    .map((b) => ({ ...b, dong: [...(Array.isArray(b?.dong) ? b.dong : [])].reverse() }));
}

/** Đọc hướng đã nhớ; kho bị chặn / giá trị lạ → mặc định (không ném). */
export function docHuongXep(): HuongXep {
  try {
    const v = typeof window === "undefined" ? null : window.localStorage.getItem(KHOA_HUONG_XEP);
    return laHuongXep(v) ? v : HUONG_XEP_MAC_DINH;
  } catch {
    return HUONG_XEP_MAC_DINH;
  }
}

export function ghiHuongXep(huong: HuongXep): void {
  try {
    if (typeof window !== "undefined") window.localStorage.setItem(KHOA_HUONG_XEP, huong);
  } catch {
    // Kho bị chặn (chế độ riêng tư…) — lựa chọn chỉ sống tới lúc tải lại trang.
  }
}

/** "08:30 · Hiếm muộn · BS A · 0900 001 237" — bỏ ô trống. */
export function dongPhu(parts: readonly (string | null | undefined)[]): string {
  return parts.filter((p) => typeof p === "string" && p.trim() !== "").join(" · ");
}
