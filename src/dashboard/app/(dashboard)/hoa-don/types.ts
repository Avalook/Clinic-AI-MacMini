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
/** Một việc làm tiền của phiếu thay đổi SAU khi bấm thu (máy chủ tính). */
export interface SuKien {
  luc: string | null;
  loai: "DOI_HINH_THUC" | "BO_DICH_VU" | "HOAN_TIEN" | "HUY_PHIEU";
  nguoi: string | null; mo_ta: string; ly_do: string | null; so_tien: number;
  trang_thai?: string; sau_giay?: number | null;
}
/** Việc còn tồn của mọi ngày — quầy / CSKH xử lý bằng nút có sẵn thì tự hết. */
export interface ViecTon {
  loai: string; ten_loai: string; luc: string | null;
  patient_id: string | null; ten: string | null; ma_bn: string | null;
  so_tien: number; ma: string | null; visit_id: string | null; kind: string | null;
  mo_ta: string | null; nguoi: string | null;
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
  su_kien?: SuKien[];
}
export interface KhachHoaDon {
  id: string; ten: string; ma_bn: string | null; so_dien_thoai: string | null;
  da_thu: number; da_hoan: number; cho_hoan: number; thu_rong: number;
  tong_truoc_giam: number; giam_gia: number;
  da_thu_dich_vu?: number; da_thu_thuoc?: number; chua_tra_lai?: number;
  viec_ton?: ViecTon[]; co_phieu_huy?: boolean;
  so_phieu: number; trang_thai: string; phieu: PhieuThu[];
  can_doi_soat?: boolean; canh_bao?: string[];
}
export interface DanhSachData {
  tu: string; den: string; access: ReportAccess;
  tong: {
    tong_truoc_giam: number; giam_gia: number; da_thu: number; da_hoan: number; cho_hoan: number;
    thu_rong: number; so_phieu: number; so_khach: number;
    chua_tra_lai?: number; so_viec_ton?: number; gia_tri_huy?: number; so_huy?: number;
  };
  /** Tổng các dòng khách đang hiện (máy chủ cộng) — dòng TỔNG cuối bảng. */
  tong_khach?: { so_phieu: number; giam_gia: number; da_thu: number; da_hoan: number; chua_tra_lai: number; thu_rong: number; so_khach_con_ton: number };
  khach: KhachHoaDon[];
  viec_ton?: ViecTon[];
}
export const TRANG_THAI: Record<string, string> = {
  DA_THU: "Đã thu", CHO_HOAN: "Chờ hoàn", HOAN_MOT_PHAN: "Hoàn một phần",
  HOAN_TOAN_BO: "Hoàn toàn bộ", DA_HUY: "Đã hủy", HON_HOP: "Nhiều trạng thái",
};
export const TEN_SU_KIEN: Record<SuKien["loai"], string> = {
  DOI_HINH_THUC: "Đổi hình thức", BO_DICH_VU: "Bỏ dịch vụ sau thu",
  HOAN_TIEN: "Hoàn tiền", HUY_PHIEU: "Huỷ phiếu",
};
export const tien = (n: number) => `${n.toLocaleString("vi-VN")}đ`;
export function ngayGio(value: string | null) {
  if (!value) return "Không có dữ liệu";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Không có dữ liệu" : date.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
}
/** Giờ:phút:giây theo giờ VN (mốc thu của từng phiếu). */
export function gio(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleTimeString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour12: false });
}
/** "5 giờ" / "2 ngày" — đã tồn bao lâu, chỉ để hiển thị. */
export function daTon(value: string | null, bayGio: number = Date.now()) {
  if (!value) return "—";
  const t = new Date(value).getTime();
  if (Number.isNaN(t)) return "—";
  const phut = Math.max(0, Math.round((bayGio - t) / 60_000));
  if (phut < 60) return `${phut} phút`;
  if (phut < 24 * 60) return `${Math.round(phut / 60)} giờ`;
  return `${Math.round(phut / (24 * 60))} ngày`;
}
