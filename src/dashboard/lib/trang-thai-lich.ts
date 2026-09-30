// NHÃN TRẠNG THÁI LỊCH / LƯỢT — máy chủ quyết (Tuyền 30/09/2026: "đã checkout
// rồi nhưng ở mấy trang chủ hay trang lịch hẹn khám vẫn ghi là đang khám").
//
// Máy chủ (`core/trang_thai_lich.py` → `trang_thai_hien_thi`) trả sẵn
// `{ma, nhan, tone}` trên mỗi dòng lịch ở lưới lịch tuần (Trang chủ + Tiếp đón),
// bảng "Trạng thái BN buổi khám", màn Quản lý khách hàng. Màn chỉ VẼ `nhan`
// bằng màu `tone`; không tự dịch `appointment.status` nữa. Ở đây chỉ còn kiểu
// dữ liệu và phép đổi tone sang bộ màu của StatusChip.

import type { ChipTone } from "@/components/ui/Chip";
import type { StatusTone } from "@/components/ui/StatusChip";

export type MaTrangThai =
  | "CHUA_XAC_NHAN"
  | "DA_DAT"
  | "HUY"
  | "KHONG_DEN"
  | "BS_TU_CHOI"
  | "DA_CHECK_IN"
  | "DANG_O"
  | "DANG_CHO"
  | "DA_THU_DU"
  | "KHAM_XONG"
  | "DA_VE"
  | "VE_GIUA_CHUNG"
  | "KHAC";

export interface TrangThaiHienThi {
  ma: MaTrangThai;
  /** Chữ trên chip — máy chủ viết. */
  nhan: string;
  tone: ChipTone;
}

/** Khách đã tới và CÒN trong phòng khám. */
export const MA_CON_O: readonly MaTrangThai[] = [
  "DA_CHECK_IN",
  "DANG_O",
  "DANG_CHO",
  "DA_THU_DU",
  "KHAM_XONG",
];

/** Khách đã rời phòng khám (check-out / về giữa chừng). */
export const MA_DA_ROI: readonly MaTrangThai[] = ["DA_VE", "VE_GIUA_CHUNG"];

/** Tone của Chip → tone của StatusChip (màn CSKH vẽ bằng StatusChip). */
const SANG_STATUS: Record<ChipTone, StatusTone> = {
  success: "assigned",
  warning: "ready",
  danger: "overdue",
  brand: "assigned",
  neutral: "cancelled",
  info: "completed",
  run: "in_progress",
  dang_o: "in_progress",
  doi_tac: "in_progress",
};

export function statusToneCua(tt: TrangThaiHienThi): StatusTone {
  return SANG_STATUS[tt.tone] ?? "ready";
}
