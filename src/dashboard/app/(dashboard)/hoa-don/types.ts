import type { ReportAccess } from "../reports/access";

export interface DongHoaDon {
  id: string; ten: string; so_luong: number; thanh_tien: number; da_bo: boolean;
  thanh_tien_truoc_giam?: number; giam_gia?: number;
}
export interface PhieuHoan {
  id: string; ma: string; so_tien: number; trang_thai: string; hinh_thuc?: string | null;
  lap_luc: string | null; hoan_luc: string | null;
  nguoi_lap: string | null; nguoi_hoan: string | null; ly_do: string | null;
  huy_luc?: string | null; nguoi_huy?: string | null; ly_do_huy?: string | null;
  dong: DongHoaDon[];
}
export interface PhieuThu {
  id: string; ma: string; visit_id: string; kind: string; trang_thai: string;
  thu_trong_ky?: boolean; can_doi_soat?: boolean;
  so_tien: number; da_hoan: number; cho_hoan: number; thu_rong: number;
  tong_truoc_giam: number; giam_gia: number; kieu_giam: "AMOUNT" | "PERCENT" | null;
  gia_tri_giam: number | null; ly_do_giam: string | null; nguoi_giam: string | null; giam_luc: string | null;
  hinh_thuc: string; lap_luc: string | null; thu_luc: string | null; huy_luc: string | null;
  nguoi_lap: string | null; nguoi_thu: string | null; nguoi_huy: string | null;
  ly_do_huy: string | null; dong: DongHoaDon[]; hoan: PhieuHoan[];
}
export interface KhachHoaDon {
  id: string; ten: string; ma_bn: string | null; so_dien_thoai: string | null;
  da_thu: number; da_hoan: number; cho_hoan: number; thu_rong: number;
  tong_truoc_giam: number; giam_gia: number;
  so_phieu: number; trang_thai: string; phieu: PhieuThu[];
  can_doi_soat?: boolean; canh_bao?: string[];
}
export interface DanhSachData {
  tu: string; den: string; access: ReportAccess;
  tong: { tong_truoc_giam: number; giam_gia: number; da_thu: number; da_hoan: number; cho_hoan: number; thu_rong: number; so_phieu: number; so_khach: number };
  khach: KhachHoaDon[];
}
export const TRANG_THAI: Record<string, string> = {
  DA_THU: "Đã thu", CHO_HOAN: "Chờ hoàn", HOAN_MOT_PHAN: "Hoàn một phần",
  HOAN_TOAN_BO: "Hoàn toàn bộ", DA_HUY: "Đã hủy", HON_HOP: "Nhiều trạng thái",
};
export const tien = (n: number) => `${n.toLocaleString("vi-VN")}đ`;
export function ngayGio(value: string | null) {
  if (!value) return "Không có dữ liệu";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Không có dữ liệu" : date.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
}
