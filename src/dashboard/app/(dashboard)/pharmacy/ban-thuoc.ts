// Kiểu dữ liệu của màn Nhà thuốc — đúng hình `GET /api/v1/pharmacy/ban-thuoc`
// (backend `ban_thuoc_service`, contract tiền–thuốc CP4).
//
// Màn này KHÔNG tự suy luật: giai đoạn của lượt và các nút được phép của từng
// dòng / từng lô đều do máy chủ trả (`giai_doan`, `thao_tac`). Ở đây chỉ có
// nhãn và màu để vẽ.

import type { StatusTone } from "@/components/ui/StatusChip";
import { VN_TZ } from "../../../lib/datetime";

export type GiaiDoan =
  | "CHUA_SAN_SANG"
  | "SAN_SANG"
  | "CHO_XAC_MINH"
  | "DA_THU"
  | "CAN_DOI_SOAT"
  | "DA_THU_CU";

export interface LoGoiY {
  drug_batch_id: string;
  batch_code: string;
  expiry_date: string;
  unit: string;
  /** Thuốc trên kệ. */
  ton_vat_ly: number;
  /** Số hệ thống dùng để chống bán trùng — chưa phải tên chính thức của kho (HOLD J6). */
  co_the_phan_lo: number;
}

export interface PhanLo {
  allocation_id: string;
  drug_batch_id: string;
  batch_code: string;
  expiry_date: string;
  quantity: number;
  handed_over_qty: number;
  con_giao: number;
  dang_giu: boolean;
  da_ban: boolean;
  /** Đã từng ghi bán (kể cả khi phần chưa giao sau đó đã huỷ). */
  co_sale: boolean;
  thao_tac: { bo: boolean; doi: boolean; giao: boolean };
}

/** Một lần GIAO (DISPENSE) — khách trả thuốc phải chọn đúng lần giao gốc. */
export interface LanGiao {
  dispense_txn_id: string;
  batch_code: string;
  so_luong: number;
  luc: string;
  da_tra: number;
  con_tra: number;
  thao_tac: { tra: boolean };
}

export interface DongDon {
  id: string;
  drug_name_raw: string | null;
  quantity_text: string | null;
  quantity_num: number | null;
  unit: string | null;
  purchased_qty: number | null;
  dispensed_qty: number;
  dispense_status: string | null;
  closed: boolean;
  refusal_reason: string | null;
  dosage_instructions: string | null;
  drug_catalog_id: string | null;
  ten_thuoc_kho: string | null;
  can_lo: number;
  da_chon: number;
  phan_lo: PhanLo[];
  lo_goi_y: LoGoiY[];
  xuat: LanGiao[];
  /** Đã bán mà chưa giao (mọi lần thu). */
  chua_giao: number;
  /** Phần chưa giao còn thiếu căn cứ (chưa huỷ phiếu, chưa hoàn xong đủ). */
  can_hoan: number;
  thao_tac: {
    xac_dinh_thuoc: boolean;
    khai_so_mua: boolean;
    chon_lo: boolean;
    giao_luong_cu: boolean;
    tu_choi: boolean;
    chot: boolean;
    huy_chua_giao: boolean;
  };
}

export interface LuotThuoc {
  visit_id: string;
  ten_khach: string | null;
  /** Số booking (lúc đặt) + số check-in (quầy cấp) — `components/ui/SoLuot`. */
  so_booking?: number | null;
  so_tiep_don?: number | null;
  patient_code: string | null;
  phone: string | null;
  kham_xong: boolean;
  giai_doan: GiaiDoan;
  lan_thu: {
    payment_cycle_id: string;
    status: string;
    method: string | null;
    can_doi_soat: boolean;
  } | null;
  dong: DongDon[];
}

export interface ThuocDanhMuc {
  id: string;
  name_base: string;
  variant: string | null;
}

export interface ManNhaThuoc {
  luot: LuotThuoc[];
  danh_muc: ThuocDanhMuc[];
  hom_nay: string;
  /** Người xem có được ghi ở nhà thuốc không — máy chủ đã AND vào mọi nút. */
  co_quyen_ghi: boolean;
}

export const GIAI_DOAN: Record<GiaiDoan, { nhan: string; tone: StatusTone; giai_thich: string }> = {
  CHUA_SAN_SANG: {
    nhan: "Chờ bác sĩ khám xong",
    tone: "skipped",
    giai_thich:
      "Bác sĩ chưa bấm Khám xong — đơn còn có thể thay đổi. Chỉ xem; chưa chọn lô.",
  },
  SAN_SANG: {
    nhan: "Chọn lô",
    tone: "ready",
    giai_thich:
      "Xác định thuốc trong kho, số khách mua, rồi chọn lô đủ số bán. Chọn lô chưa giữ chỗ — thu tiền xong mới bán.",
  },
  CHO_XAC_MINH: {
    nhan: "Chờ xác minh chuyển khoản",
    tone: "assigned",
    giai_thich:
      "Khách chuyển khoản / QR, thu ngân chưa xác minh. Các lô đang được giữ; chỉ đổi lô được.",
  },
  DA_THU: {
    nhan: "Đã thu — giao thuốc",
    tone: "in_progress",
    giai_thich: "Tiền thuốc đã thu. Giao từ đúng lô đã bán; giao một phần được.",
  },
  CAN_DOI_SOAT: {
    nhan: "Cần đối soát",
    tone: "blocked",
    giai_thich:
      "Đã nhận tiền nhưng chưa ghi bán được thuốc (lô không còn bán được). Không giao — báo quản lý đối soát.",
  },
  DA_THU_CU: {
    nhan: "Đã thu (luồng cũ)",
    tone: "in_progress",
    giai_thich: "Lần thu trước khi có phân lô. Cấp thuốc theo cách cũ.",
  },
};

export const NHAN_CAP: Record<string, string> = {
  CHUA_CAP: "Chưa giao",
  CAP_MOT_PHAN: "Đã giao một phần",
  CAP_DU: "Đã giao đủ",
  TU_CHOI: "Khách không lấy",
};

export const fmtSo = (n: number | null | undefined) =>
  n === null || n === undefined
    ? "—"
    : new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(n);

/** Ngày dạng "YYYY-MM-DD" (hạn dùng) — nửa đêm UTC là 07:00 giờ VN, cùng ngày. */
export const fmtNgay = (iso: string) =>
  new Date(iso).toLocaleDateString("vi-VN", { timeZone: VN_TZ });
