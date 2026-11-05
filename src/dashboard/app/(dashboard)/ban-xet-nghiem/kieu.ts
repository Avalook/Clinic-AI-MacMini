// Kiểu dữ liệu bàn XN — khớp `BanOut` / `ViecOut` / `TienOut` / `QuaTrinhOut` của
// `routers/xet_nghiem_ban.py`. Mọi cờ, chữ, màu chip, mốc hành trình do máy chủ tính.

import type { ChipTone } from "@/components/ui/Chip";
import type { StepState } from "@/components/ui/Stepper";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

export interface TrangThai {
  ma: string;
  nhan: string;
  qua_hen: boolean;
  so_ngay_qua_hen: number;
  muc_qua_hen: string | null;
  qua_han_lay_mau: boolean;
  co_ban_moi_chua_gui: boolean;
  da_hoan_tien: boolean;
  co_the_lay_mau: boolean;
  ly_do_khong_lay_mau: string | null;
  mau: ChipTone;
  con_ton: boolean;
  vi_sao: string;
}

export interface Nut {
  ghi_thu: boolean;
  huy_thu: boolean;
  hoan_tien: boolean;
  con_hoan_duoc: number;
  cho_qua: boolean;
  go_cho_qua: boolean;
  lay_mau: boolean;
  huy_mau: boolean;
  tai_ket_qua: boolean;
  gui: boolean;
  thu_hoi: boolean;
  dong: boolean;
  mo_lai: boolean;
  hoan_tac: { lenh: string; nhan: string } | null;
}

export interface Moc {
  ten: string;
  luc: string | null;
  trang_thai: StepState;
}

export interface Viec {
  order_id: string;
  visit_id: string | null;
  ten_dich_vu: string | null;
  doi_tac_id: string;
  ten_doi_tac: string;
  clinic_patient_id: string | null;
  ten_khach: string | null;
  ma_bn: string | null;
  mau_id: string | null;
  ma_mau: string | null;
  hen_tra_ngay: string | null;
  tep_id: string | null;
  ten_tep: string | null;
  ma_giao_dich: string | null;
  gia_goi_y: number | null;
  da_thu: number | null;
  tien_mat: number | null;
  chuyen_khoan: number | null;
  da_hoan: number | null;
  tao_luc: string;
  ngay_chi_dinh: string;
  tep_luc: string | null;
  so_ngay_cho: number;
  hanh_trinh: Moc[];
  trang_thai: TrangThai;
  nut: Nut;
}

export interface Khach {
  khoa: string;
  ngay: string;
  ten: string;
  ma_bn: string | null;
  order_ids: string[];
  nhan: string;
  mau: ChipTone;
}

export interface Loc {
  ma: string;
  nhan: string;
  ton: boolean;
}

export interface Ban {
  viec: Viec[];
  khach: Khach[];
  loc: Loc[];
  quan_ly: boolean;
}

export interface DongTien {
  id: string;
  loai: string;
  so_tien: number;
  tien_mat: number;
  chuyen_khoan: number;
  hinh_thuc: string;
  ma_giao_dich: string | null;
  gia_goi_y: number | null;
  ghi_luc: string;
  ten: string | null;
  ten_khach: string | null;
  ma_bn: string | null;
  nguoi: string | null;
}

export const tien = (n: number | null | undefined) =>
  n === null || n === undefined ? "" : `${n.toLocaleString("vi-VN")}đ`;

const VN = "Asia/Ho_Chi_Minh";

/** "05/11" từ "2026-11-05" hoặc mốc giờ ISO. */
export const ngayNgan = (iso: string | null) =>
  iso ? new Date(iso.length === 10 ? `${iso}T00:00:00+07:00` : iso).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", timeZone: VN }) : "";

export const ngayVN = (iso: string | null) =>
  iso ? new Date(iso.length === 10 ? `${iso}T00:00:00+07:00` : iso).toLocaleDateString("vi-VN", { timeZone: VN }) : "";

/** "09:40 05/11". */
export const gioNgay = (iso: string | null) =>
  iso
    ? `${new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: VN })} ${ngayNgan(iso)}`
    : "";

/** Hôm nay theo giờ VN, dạng "2026-11-05" (so với `ngay_chi_dinh` của máy chủ). */
export const homNayVN = () => new Date().toLocaleDateString("sv-SE", { timeZone: VN });

/** Gửi một lệnh bàn XN (JSON). Trả câu lỗi máy chủ (tiếng Việt) hoặc null. */
export async function lenh(duong: string, body: unknown): Promise<string | null> {
  try {
    const r = await fetch(`/api/xet-nghiem/ban/${duong}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.ok) return null;
    return loiDocDuoc(await r.json().catch(() => null), `Chưa làm được (HTTP ${r.status}).`);
  } catch {
    return "Mất kết nối — chưa làm được.";
  }
}
