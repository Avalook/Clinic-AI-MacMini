// Liệu trình điều trị nhiều buổi (08/10/2026) — kiểu dữ liệu máy chủ trả + MỘT
// chỗ gọi `/api/lieu-trinh`. Mọi con số (đã làm, đã trả, còn nợ, tối đa trả
// trước), trạng thái và nút nào bấm được đều do máy chủ tính
// (`services/lieu_trinh_service.py`, `lieu_trinh_tien.py`); ở đây chỉ có nhãn
// để vẽ và câu ghép số cho người đọc.

import { nhanLoi, type ThanLoi } from "./loi-api";

export type TrangThaiLieuTrinh = "DE_XUAT" | "DANG_LAM" | "XONG" | "DUNG";

export const NHAN_TRANG_THAI_LT: Record<TrangThaiLieuTrinh, string> = {
  DE_XUAT: "Đề xuất",
  DANG_LAM: "Đang làm",
  XONG: "Xong",
  DUNG: "Dừng",
};

/** Một ô của phiếu điều trị đã có chữ (tóm tắt diễn tiến buổi). */
export interface OKetQuaBuoi {
  ma: string;
  ten: string;
  gia_tri: string;
}

/** Một buổi (chỉ định) của liệu trình — `_BUOI_SQL`. `buoi_so` = số HIỆN theo
 *  thứ tự làm xong (máy chủ, `v_lieu_trinh_buoi`); buổi chưa làm đứng sau. */
export interface BuoiLieuTrinh {
  id: string;
  order_id: string;
  visit_id: string;
  buoi_so: number;
  tra_truoc: boolean;
  song: boolean;
  da_lam: boolean;
  ngay: string | null;
  /** "Bàn khám" / tên phòng / null (chưa làm, chưa xếp phòng). */
  noi_lam: string | null;
  xong_luc?: string | null;
  /** Ô phiếu điều trị có chữ ("Cảm nhận", "Vấn đề sau điều trị"…). */
  ket_qua?: OKetQuaBuoi[];
}

export interface LieuTrinh {
  id: string;
  service_code: string;
  service_name: string;
  so_buoi: number;
  don_gia: number;
  ghi_chu_lo_trinh: string | null;
  trang_thai: TrangThaiLieuTrinh;
  revision: number;
  da_lam: number;
  da_tra: number;
  /** Buổi đã thu LẺ (không bằng tiền trả trước) — máy chủ đếm. */
  tra_le?: number;
  so_gan: number;
  con_lai: number;
  con_tra_truoc: number;
  chua_tra: number;
  tien_con_lai: number;
  /** Buổi của kế hoạch chưa có chỉ định nào (máy chủ tính). */
  chua_gan?: number;
  de_xuat_boi: string | null;
  ly_do_dung: string | null;
  nguon_visit_id: string | null;
  /** Chỉ định bác sĩ đề xuất lộ trình từ đó (đề xuất vẫn để nó là buổi lẻ). */
  nguon_order_id?: string | null;
  tao_luc?: string | null;
  buoi?: BuoiLieuTrinh[];
  /** Nút trên dải — máy chủ quyết theo trạng thái. */
  nut?: { dieu_chinh: boolean; dung: boolean; mo_lai: boolean };
  /** Lần sửa mới nhất do người bấm còn hoàn tác được. */
  hoan_tac?: { lich_su_id: string; hanh_dong: string } | null;
}

export interface UngVien {
  id: string;
  trang_thai: TrangThaiLieuTrinh;
  so_buoi: number;
  da_lam: number;
  tao_luc: string | null;
  /** Cho [Khách chọn lộ trình] bỏ tick "tính buổi hôm nay" (lệnh đăng ký). */
  revision: number;
}

/** Một chỉ định điều trị của lượt + buổi đang gắn. */
export interface ChiDinhLieuTrinh {
  order_id: string;
  service_code: string;
  service_name: string;
  song: boolean;
  lieu_trinh_id: string | null;
  buoi_so: number | null;
  /** Buổi đang gắn đã làm xong chưa (số hiện theo thứ tự làm xong). */
  buoi_da_lam?: boolean;
  /** "Buổi k/N · đã làm" / "· chưa làm" — máy chủ ghép; rỗng = buổi lẻ. */
  chu_buoi?: string;
  tra_truoc: boolean | null;
  ung_vien: UngVien[];
  can_chon: boolean;
  /** `khach_chon`: buổi lẻ + có lộ trình bác sĩ đề xuất → [Khách chọn lộ trình]. */
  nut?: { tao: boolean; go: boolean; tach: boolean; chon: boolean; khach_chon?: boolean };
}

export interface LieuTrinhLuot {
  visit_id: string;
  clinic_patient_id: string;
  lieu_trinh: LieuTrinh[];
  chi_dinh: ChiDinhLieuTrinh[];
  dich_vu_de_xuat?: { service_code: string; ten: string }[];
  /** Người xem có quyền sửa liệu trình (không → dải chỉ đọc, kể cả ở phòng). */
  ghi_duoc?: boolean;
}

/** Dòng lịch sử sửa (kế hoạch + gắn/gỡ buổi). */
export interface DongLichSuLT {
  loai: "SUA" | "GAN" | "GO";
  id: string;
  hanh_dong?: string;
  ban_cu?: Record<string, unknown> | null;
  ban_moi?: Record<string, unknown> | null;
  buoi_so?: number;
  cach?: string | null;
  luc: string | null;
  boi: string | null;
  hoan_tac_duoc: boolean;
}

/** Khối "Liệu trình" của quầy thu dịch vụ — `LieuTrinhTienService.quay`. */
export interface LieuTrinhQuay {
  id: string;
  service_name: string;
  trang_thai: TrangThaiLieuTrinh;
  so_buoi: number;
  don_gia: number;
  da_lam: number;
  da_tra: number;
  tra_le?: number;
  con_lai: number;
  con_tra_truoc: number;
  chua_tra: number;
  tien_con_lai: number;
  buoi_hom_nay_trong_hoa_don: number;
  tra_truoc_dang_chon: { id: string; so_buoi: number; don_gia: number } | null;
  tra_truoc_toi_da: number;
  goi_y_tra_them: boolean;
  /** Câu gợi ý của máy chủ (khách chưa từng trả trước ≠ hết buổi đã trả). */
  cau_goi_y?: string | null;
  hoan_duoc_toi_da: number;
  dong_hoan_duoc: { payment_cycle_id: string; con_hoan_duoc: number; luc_thu: string | null }[];
}

/** Nhãn hành động trong lịch sử sửa. */
export const NHAN_HANH_DONG_LT: Record<string, string> = {
  TAO: "Tạo liệu trình",
  DIEU_CHINH: "Điều chỉnh",
  DANG_KY: "Đăng ký",
  DUNG: "Dừng",
  MO_LAI: "Mở lại",
  HOAN_TAC: "Hoàn tác",
  TU_THEM_BUOI: "Tự thêm buổi",
  TU_DONG: "Tự đổi trạng thái",
};

/** "đã trả 3 buổi (1 lẻ + 2 trả trước)" — `da_tra` của máy chủ là số buổi
 *  TRẢ TRƯỚC, buổi thu lẻ đếm riêng (`tra_le`); gộp lại để "còn nợ" khớp tổng. */
export function nhanDaTra(daTraTruoc: number, traLe = 0): string {
  const tong = daTraTruoc + traLe;
  if (tong <= 0) return "chưa trả buổi nào";
  if (traLe > 0 && daTraTruoc > 0) return `đã trả ${tong} buổi (${traLe} lẻ + ${daTraTruoc} trả trước)`;
  if (daTraTruoc > 0) return `đã trả trước ${daTraTruoc} buổi`;
  return `đã trả ${traLe} buổi (trả lẻ)`;
}

/** Nhãn nút hoàn tác thao tác gần nhất. Thao tác gần nhất CHÍNH LÀ một lần
 *  hoàn tác → nút là "Làm lại" (trước ghi "Hoàn tác hoàn tác"). */
export function nhanNutHoanTac(hanhDong: string | null | undefined): string {
  if (hanhDong === "HOAN_TAC") return "Làm lại thao tác vừa hoàn tác";
  const ten = NHAN_HANH_DONG_LT[hanhDong ?? ""];
  return ten ? `Hoàn tác ${ten.toLowerCase()}` : "Hoàn tác";
}

/** Một dòng lịch sử sửa: chỉ ghi phần THẬT SỰ đổi (số buổi / trạng thái / ghi
 *  chú) — trước ghi "6 → 6 buổi" cho Dừng, Hoàn tác. Rỗng = không đổi gì. */
export function nhanDoiLieuTrinh(
  cu: Record<string, unknown> | null | undefined,
  moi: Record<string, unknown> | null | undefined,
): string {
  if (!moi) return "";
  const ra: string[] = [];
  const sb = (x: unknown) => (x == null ? "—" : String(x));
  if (!cu || cu.so_buoi !== moi.so_buoi) ra.push(`${sb(cu?.so_buoi)} → ${sb(moi.so_buoi)} buổi`);
  if (cu && cu.trang_thai !== moi.trang_thai) {
    const tt = (x: unknown) => NHAN_TRANG_THAI_LT[x as TrangThaiLieuTrinh] ?? sb(x);
    ra.push(`${tt(cu.trang_thai)} → ${tt(moi.trang_thai)}`);
  }
  if (cu && (cu.ghi_chu_lo_trinh ?? null) !== (moi.ghi_chu_lo_trinh ?? null)) ra.push("đổi ghi chú lộ trình");
  return ra.join(" · ");
}

export function tienLT(n: number): string {
  return `${n.toLocaleString("vi-VN")}đ`;
}

/** Chip của một buổi: "Buổi 3/10 · chưa làm · đã trả trước" — số máy chủ đánh
 *  theo thứ tự làm xong; `daLam` không rõ (dữ liệu cũ) thì không ghi. */
export function nhanBuoi(
  buoiSo: number,
  soBuoi: number,
  traTruoc: boolean | null | undefined,
  daLam?: boolean | null,
): string {
  const lam = daLam === true ? " · đã làm" : daLam === false ? " · chưa làm" : "";
  return `Buổi ${buoiSo}/${soBuoi}${lam}${traTruoc ? " · đã trả trước" : ""}`;
}

/** Khoá gửi lại cho MỘT lần bấm (máy chủ cần 8–200 ký tự). */
export function khoaLT(): string {
  return `lt-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

export type KetQuaLT<T> =
  | { ok: true; data: T }
  | { ok: false; ma: string | null; loi: string; chiTiet: Record<string, unknown> | null };

/** Đọc một bảng liệu trình (`xem` + mã). null = hỏng (màn giữ bản cũ). */
export async function docLT<T>(xem: string, id: string): Promise<T | null> {
  const r = await fetch(`/api/lieu-trinh?xem=${xem}&id=${id}`, { cache: "no-store" }).catch(() => null);
  if (!r || !r.ok) return null;
  return ((await r.json().catch(() => null)) as T | null) ?? null;
}

/** Gửi một lệnh liệu trình. `du_lieu` chưa có khoá gửi lại thì thêm. */
export async function lenhLT<T = Record<string, unknown>>(
  thaoTac: string,
  duLieu: Record<string, unknown>,
  id?: string,
): Promise<KetQuaLT<T>> {
  try {
    const r = await fetch("/api/lieu-trinh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thao_tac: thaoTac,
        id,
        du_lieu: { idempotency_key: khoaLT(), ...duLieu },
      }),
    });
    const d = (await r.json().catch(() => null)) as (ThanLoi & { chi_tiet?: unknown }) | null;
    if (r.ok) return { ok: true, data: d as T };
    return {
      ok: false,
      ma: typeof d?.error === "string" ? d.error : null,
      loi: nhanLoi(d, "Không ghi được thao tác liệu trình."),
      chiTiet: d?.chi_tiet && typeof d.chi_tiet === "object" ? (d.chi_tiet as Record<string, unknown>) : null,
    };
  } catch {
    return { ok: false, ma: null, loi: "Mất kết nối — chưa ghi. Thử lại.", chiTiet: null };
  }
}
