// Hình thức thu — chỉ còn HAI (Tuyền 01/10/2026: "bỏ nút QR, chuyển khoản với QR
// là một"). Một lần thu chia được nhiều phần: Tiền mặt + Chuyển khoản.
//
// File này CHỈ chứa tên hiển thị + định dạng. Luật (tổng các phần = số cần thu,
// khách đưa ≥ tiền mặt, có chuyển khoản thì chờ xác minh) nằm ở máy chủ
// (`services/phan_thu.py`, trigger `payment_cycle_phan_kiem_tong`). Màn chỉ cộng
// để HIỂN THỊ "còn thiếu / trả lại khách" trong lúc gõ — máy chủ quyết.

export type HinhThucThu = "CASH" | "TRANSFER";

/** Một phần của lần thu như máy chủ trả (`phan_thu_hieu_luc`). */
export interface PhanThu {
  hinh_thuc: HinhThucThu | null;
  so_tien: number;
  khach_dua?: number | null;
}

/** Phần gửi lên khi thu (`phan` của POST /api/payment). */
export interface PhanGui {
  hinh_thuc: HinhThucThu;
  so_tien: number;
  khach_dua?: number | null;
}

/** Tên hiển thị — QR cũ đọc là Chuyển khoản. */
export const TEN_HINH_THUC: Record<string, string> = {
  CASH: "Tiền mặt",
  TRANSFER: "Chuyển khoản",
  QR: "Chuyển khoản",
};

export function tenHinhThuc(ma: string | null | undefined): string {
  return ma ? (TEN_HINH_THUC[ma] ?? ma) : "";
}

export function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

/** "Tiền mặt" · "Tiền mặt 500.000đ + Chuyển khoản 200.000đ" · "" (không rõ). */
export function nhanPhan(phan: PhanThu[] | null | undefined): string {
  const co = (phan ?? []).filter((p) => p.hinh_thuc);
  if (co.length === 0) return "";
  if (co.length === 1) return tenHinhThuc(co[0].hinh_thuc);
  return co.map((p) => `${tenHinhThuc(p.hinh_thuc)} ${tien(p.so_tien)}`).join(" + ");
}

/** Tiền thừa trả khách (khách đưa − phần tiền mặt) — chỉ hiển thị. */
export function traLai(phan: PhanThu[] | PhanGui[] | null | undefined): number | null {
  for (const p of phan ?? []) {
    if (p.hinh_thuc === "CASH" && p.khach_dua != null && p.khach_dua > p.so_tien) {
      return p.khach_dua - p.so_tien;
    }
  }
  return null;
}

/** Có phần chuyển khoản → lần thu chờ xác minh (máy chủ quyết; màn đổi chữ nút). */
export function coChuyenKhoan(phan: PhanGui[]): boolean {
  return phan.some((p) => p.hinh_thuc === "TRANSFER");
}

/** Đọc số tiền gõ tay ("500.000", "500000", "500k") → số đồng; rác → null. */
export function docSoTien(chu: string): number | null {
  const s = chu.trim().toLowerCase().replace(/\s/g, "");
  if (!s) return null;
  // "500k" / "1,5k" = nghìn đồng; còn lại dấu . , là phân cách hàng nghìn.
  const so = s.endsWith("k")
    ? Number(s.slice(0, -1).replace(",", ".")) * 1000
    : Number(s.replace(/[.,]/g, ""));
  if (!Number.isFinite(so) || so < 0) return null;
  return Math.round(so);
}
