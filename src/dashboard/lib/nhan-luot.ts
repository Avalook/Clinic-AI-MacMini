// Nhãn đếm LƯỢT của khách — MÁY CHỦ tính (`services/nhan_luot.py`, Tuyền chốt
// 08/10/2026): mỗi lần check-in = một lượt khám, đếm theo thời gian trên toàn bộ
// lượt của khách ("Lượt khám n"); điều trị đếm theo buổi ("Buổi k/N" /
// "Điều trị · buổi lẻ"), không ăn số lượt khám; lịch chưa tới "Lịch hẹn", huỷ
// "Đã huỷ". Tệp này CHỈ ghép chữ từ trường máy chủ trả — không đếm gì cả.

import { fmtDate, fmtDateTimeOrDate, fmtTime } from "./datetime.ts";

export type LoaiLuot = "KHAM" | "DIEU_TRI" | "THUOC" | "LICH" | "HUY";

/** Trường `nhan_luot` máy chủ gắn vào mỗi lượt / lịch. */
export interface NhanLuot {
  nhan: string;
  loai: LoaiLuot;
  /** Thứ tự lượt khám (chỉ loại KHAM). */
  so: number | null;
  /** "Buổi k/N" khi lượt có buổi liệu trình (kể cả lượt khám làm buổi 1). */
  buoi: string | null;
}

/** Chữ nhãn của một lượt; máy chủ chưa trả (bản cũ / lỗi đọc) → chữ dự phòng
 *  trung tính, KHÔNG tự đếm. */
export function chuNhanLuot(n: NhanLuot | null | undefined, duPhong = "Lượt"): string {
  return n?.nhan || duPhong;
}

/** Chip phụ "Buổi k/N" cho lượt KHÁM có làm buổi liệu trình (lượt điều trị thì
 *  nhãn chính đã là "Buổi k/N"). */
export function chipBuoiPhu(n: NhanLuot | null | undefined): string | null {
  return n && n.loai === "KHAM" && n.buoi ? n.buoi : null;
}

/** Mốc giờ của một lượt để hiện cạnh nhãn.
 *
 *  Lượt ĐÃ TỚI (máy chủ có giờ check-in) → giờ THẬT: "08/10 · đến 08:12 · khám
 *  xong 09:40 · về 09:59" (mốc nào chưa có thì bỏ). Chưa tới → giờ hẹn. Không
 *  bao giờ hiện giờ hẹn cho lượt đã khám xong — giờ slot có thể là giờ đặt lịch
 *  ảo (20:30) trong khi khách về 09:59 (ảnh Tuyền 08/10). Giờ VN. */
export function gioLuot(l: {
  slot_start?: string | null;
  bat_dau?: string | null;
  kham_xong_luc?: string | null;
  ket_thuc?: string | null;
}): string {
  if (!l.bat_dau) return l.slot_start ? fmtDateTimeOrDate(l.slot_start) : "Chưa có lịch hẹn";
  const phan = [fmtDate(l.bat_dau), `đến ${fmtTime(l.bat_dau)}`];
  if (l.kham_xong_luc) phan.push(`khám xong ${fmtTime(l.kham_xong_luc)}`);
  if (l.ket_thuc) phan.push(`về ${fmtTime(l.ket_thuc)}`);
  return phan.join(" · ");
}
