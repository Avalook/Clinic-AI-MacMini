// Gọi máy chủ cho các màn làm việc theo phòng (Tuyền chốt 16/09/2026).
//
// MỘT ĐƯỜNG DỮ LIỆU: lượt khám → hàng chờ phòng → khám → chỉ định → kết quả →
// bác sĩ duyệt. Mọi màn phòng (bàn khám, siêu âm, thủ thuật, lấy mẫu, duyệt kết
// quả) đọc và ghi qua đây — không màn nào tự nói chuyện với bảng cũ.
//
// Chỉ là ống dẫn: thứ tự hàng chờ, ai được bấm gì, kết quả phiên khám là gì…
// đều do máy chủ quyết. Tệp này không chứa luật nào.

import { nhanLoi } from "@/lib/loi-api";

export type TrangThaiHang =
  | "blocked"
  | "waiting"
  | "called"
  | "serving"
  | "done";

export interface DongHangCho {
  id: string;
  trang_thai: TrangThaiHang;
  /** KHAM = lượt khám chính của bác sĩ · TU_VAN = hàng bác sĩ tư vấn ·
   *  DICH_VU = chỉ định xếp vào phòng. */
  loai: "KHAM" | "TU_VAN" | "DICH_VU";
  /** Mã phiên khám (KHAM) hoặc mã chỉ định (DICH_VU). */
  ref_id: string;
  visit_id: string;
  clinic_patient_id: string;
  appointment_id: string | null;
  so_thu_tu: number;
  /** Số booking (lúc đặt) · số check-in (quầy cấp) — hiện bằng `SoLuot`. */
  so_booking?: number | null;
  so_tiep_don?: number | null;
  ten: string;
  ma_bn: string;
  uu_tien: boolean;
  uu_tien_ly_do: string | null;
  viec: string | null;
  dich_vu_kham: string | null;
  form_code: string | null;
  service_code: string | null;
  node_code: string | null;
  exec_status: string | null;
  phien_status: string | null;
  bac_si: string | null;
  phong: string | null;
  vao_hang_luc: string | null;
  /** Mốc check-in của cả lượt — đồng hồ tổng không đếm lại khi quay về bác sĩ. */
  checkin_luc: string | null;
  /** PRIMARY = khám lần đầu trong lượt · REVIEW = quay lại đọc kết quả. */
  vong: string | null;
  /** Lần gọi vào gần nhất (null = chưa gọi). */
  goi_luc: string | null;
  bat_dau_luc: string | null;
  xong_luc: string | null;
  ket_qua_luc: string | null;
  duyet_luc: string | null;
  /** Lượt đã hoàn tất khám (FINALIZED/AMENDED) — phiếu khoá theo mốc này. */
  da_ky?: boolean;
  ky_luc?: string | null;
  nguoi_ky?: string | null;
  /** Người thực hiện chỉ định (phòng dịch vụ). */
  nguoi_lam?: string | null;
  /** Nội dung kết quả đã ghi — chỉ vai đọc lâm sàng nhận được. */
  ket_qua_ghi?: string | null;
  ly_do_khong_lam?: string | null;
}

export interface Phong {
  id: string;
  code: string;
  ten: string;
  tang: string | null;
  nodes: string[];
  vi_tri?: string[];
}

export interface PhongHomNay {
  phong_cua_toi: Phong[];
  tat_ca_phong: Phong[];
}

export type KetQuaDoc<T> = { ok: true; data: T } | { ok: false; loi: string };

export async function docBang<T>(
  xem: string | null,
  thamSo: Record<string, string> = {},
): Promise<KetQuaDoc<T>> {
  const q = new URLSearchParams(thamSo);
  if (xem) q.set("xem", xem);
  const qs = q.toString();
  try {
    const r = await fetch(`/api/luot-kham${qs ? `?${qs}` : ""}`, {
      cache: "no-store",
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) return { ok: false, loi: nhanLoi(d, "Không đọc được dữ liệu.") };
    return { ok: true, data: d as T };
  } catch {
    return { ok: false, loi: "Mất kết nối tới máy chủ." };
  }
}

// Khoá gửi lại đặt ở MỨC MODULE: gọi Date.now/Math.random trong thân component
// vi phạm luật thuần khiết của React (react-hooks/purity).
function khoaGuiLai(): string {
  return `lv-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export async function guiThaoTac(
  thaoTac: string,
  id: string,
  duLieu: Record<string, unknown> = {},
): Promise<{ ok: true; data: Record<string, unknown> } | { ok: false; loi: string }> {
  try {
    const r = await fetch("/api/luot-kham", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": khoaGuiLai(),
      },
      body: JSON.stringify({ thao_tac: thaoTac, id, du_lieu: duLieu }),
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) return { ok: false, loi: nhanLoi(d, "Thao tác không thành công.") };
    return { ok: true, data: (d ?? {}) as Record<string, unknown> };
  } catch {
    return { ok: false, loi: "Mất kết nối — thao tác CHƯA được ghi." };
  }
}

/** "chờ 12 phút" từ một mốc ISO. Rỗng khi không tính được. */
export function soPhutTu(iso: string | null, den?: string | null): string {
  if (!iso) return "";
  const cuoi = den ? new Date(den).getTime() : Date.now();
  const phut = Math.floor((cuoi - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(phut) || phut < 0) return "";
  if (phut < 60) return `${phut} phút`;
  return `${Math.floor(phut / 60)} giờ ${phut % 60} phút`;
}

export function gioVn(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

// ── Thực hiện dịch vụ (Lifecycle v1 Slice 5) ───────────────────────────────
// Màn phòng đọc cái này TRƯỚC khi bấm, vì mỗi lệnh phải kèm đúng số revision
// đang thấy: bấm bằng số cũ nghĩa là đang ghi đè việc người khác vừa làm, và
// máy chủ từ chối thay vì im lặng nhận.

export interface LanLam {
  id: string;
  attempt_no: number;
  status: "IN_PROGRESS" | "COMPLETED" | "INTERRUPTED";
  started_at: string | null;
  completed_at: string | null;
  interrupted_at: string | null;
  interruption_reason_code: string | null;
  bat_dau_boi: string | null;
  xong_boi: string | null;
}

export interface ThucHien {
  order_id: string;
  service_code: string;
  service_name: string | null;
  selection_status: string;
  billing_status: string;
  routing_status: string;
  execution_status: string;
  execution_revision: number;
  routing_revision: number;
  room_id: string | null;
  visit_id: string;
  /** Đầu dịch vụ ở phòng (27/09/2026): mã phòng khám (SP KiotViet) + giá bảng giá. */
  ma_kiotviet?: string | null;
  gia?: number | null;
  lan_dang_chay: LanLam | null;
  /** Lần làm gần nhất, và nó đã dừng giữa chừng — nút "Làm lại" trỏ vào đây. */
  lan_da_dung: LanLam | null;
  cac_lan: LanLam[];
  mau_ket_qua: { ma: string; ten: string; nhom: string | null }[];
  /** Mẫu chọn sẵn: mẫu đã gắn, hoặc mẫu gợi ý của phiếu v5 (23/09 khuya). */
  mau_goi_y?: string | null;
  /** Máy chủ xếp READY trước (mở lại khách = mở phiếu đã Hoàn tất — đợt 3). */
  phieu: {
    id: string;
    form_id: string;
    trang_thai: string;
    revision: number;
    hoan_tat_luc: string | null;
  }[];
  /** Dịch vụ đã xong mà phiếu kết quả chỉ còn nháp (27/09/2026, đợt 3). */
  phieu_chua_hoan_tat?: boolean;
  ly_do_khong_lam: string[];
  ly_do_gian_doan: string[];
}

/** Mã lý do → câu người đọc được. Mã lạ thì hiện nguyên mã, không giấu. */
export const LY_DO_TIENG_VIET: Record<string, string> = {
  PATIENT_DECLINED_AT_ROOM: "Khách từ chối ngay tại phòng",
  CLINICAL_CONTRAINDICATION_BEFORE_START: "Chống chỉ định — phát hiện trước khi làm",
  EQUIPMENT_UNAVAILABLE_BEFORE_START: "Máy/dụng cụ không dùng được",
  STAFF_UNAVAILABLE: "Không có người làm",
  EQUIPMENT_FAILURE: "Máy hỏng giữa chừng",
  PATIENT_REQUEST: "Khách xin dừng",
  CLINICAL_SAFETY: "Lý do an toàn cho khách",
  TECHNICAL_FAILURE: "Trục trặc kỹ thuật",
  OTHER: "Lý do khác",
};
