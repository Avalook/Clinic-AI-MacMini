// Kiểu dữ liệu bàn XN — khớp `ViecOut` / `TienOut` của `routers/xet_nghiem_ban.py`.

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
  trang_thai: TrangThai;
  nut: Nut;
}

export interface DongTien {
  id: string;
  loai: string;
  so_tien: number;
  tien_mat: number;
  chuyen_khoan: number;
  hinh_thuc: string;
  ma_giao_dich: string | null;
  ghi_luc: string;
  ten: string | null;
  ten_khach: string | null;
  ma_bn: string | null;
  nguoi: string | null;
}

export const tien = (n: number | null | undefined) =>
  n === null || n === undefined ? "" : `${n.toLocaleString("vi-VN")}đ`;

export const ngayVN = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("vi-VN") : "");

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
