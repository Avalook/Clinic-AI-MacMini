// Liệu trình điều trị nhiều buổi — KIỂU dữ liệu máy chủ trả + chữ hiển thị
// (08/10/2026, docs/KE-HOACH-LIEU-TRINH.md). Mọi luật (trạng thái, đếm buổi,
// tiền, ai được làm gì) nằm ở FastAPI `lieu_trinh_service.py` + Postgres; tệp này
// chỉ ghép chữ từ số máy chủ đã tính — hàm thuần, có test.

export type TrangThaiLieuTrinh = "DE_XUAT" | "DANG_LAM" | "XONG" | "DUNG";

/** Một liệu trình (GET /lieu-trinh/theo-khach, /lieu-trinh/cskh). */
export interface LieuTrinh {
  id: string;
  khach_id: string;
  ten_khach: string | null;
  ma_khach: string | null;
  sdt: string | null;
  service_code: string;
  service_name: string;
  /** Loại khám nhóm Điều trị của dịch vụ — bộ đặt lịch khoá vào đây. */
  service_type_id: string | null;
  so_buoi: number;
  don_gia: number;
  ghi_chu_lo_trinh: string | null;
  trang_thai: TrangThaiLieuTrinh;
  tao_luc: string | null;
  de_xuat_boi: string | null;
  dang_ky_luc: string | null;
  dang_ky_boi: string | null;
  dung_luc: string | null;
  dung_boi: string | null;
  ly_do_dung: string | null;
  revision: number;
  da_tra: number;
  /** Buổi đã thu lẻ (không bằng tiền trả trước). */
  tra_le?: number;
  da_lam: number;
  con_lai: number;
  con_tra_truoc: number;
  chua_tra: number;
  tien_con_lai: number;
  /** Lần cuối khách có buổi (giờ check-in của lượt). */
  lan_cuoi: string | null;
  /** Chỉ ở danh sách CSKH. */
  lich_hen_sap_toi?: string | null;
  /** "Sắp hết lộ trình" — lý do máy chủ tính ("còn 1 buổi" / "đã dùng hết N
   *  buổi trả trước, còn M buổi chưa trả"); null = không sắp hết. */
  sap_het_ly_do?: string | null;
  /** Khung khách: CSKH đã [Đã xử lý] đúng mốc hiện tại. */
  sap_het_da_xu_ly?: boolean;
}

/** Một dòng "Lịch sử sửa" (GET /lieu-trinh/{id}/lich-su). */
export interface DongLichSuLieuTrinh {
  loai: "SUA" | "GAN" | "GO";
  id: string;
  revision?: number;
  hanh_dong?: string;
  ban_cu?: Record<string, unknown> | null;
  ban_moi?: Record<string, unknown> | null;
  buoi_so?: number;
  cach?: string | null;
  luc: string | null;
  boi: string | null;
  hoan_tac_duoc: boolean;
}

/** Chip theo lô lượt (GET /lieu-trinh/chip?luot=…). */
export interface ChipLieuTrinh {
  /** order_id → buổi đang gắn. */
  chi_dinh: Record<
    string,
    {
      visit_id: string;
      lieu_trinh_id: string;
      buoi_so: number;
      so_buoi: number;
      /** Buổi đã làm xong chưa — số đánh theo thứ tự làm xong (09/10/2026). */
      da_lam?: boolean;
      /** "Buổi k/N · đã làm / chưa làm" máy chủ ghép. */
      chu?: string;
      tra_truoc: boolean;
      service_name: string;
      trang_thai: TrangThaiLieuTrinh;
    }
  >;
  /** visit_id → liệu trình đang làm của khách (kể cả xong mà còn buổi đã trả). */
  khach: Record<
    string,
    {
      lieu_trinh_id: string;
      service_name: string;
      so_buoi: number;
      da_lam: number;
      con_lai: number;
      con_tra_truoc: number;
    }[]
  >;
}

export const NHAN_TRANG_THAI_LT: Record<TrangThaiLieuTrinh, string> = {
  DE_XUAT: "Đề xuất",
  DANG_LAM: "Đang làm",
  XONG: "Xong",
  DUNG: "Đã dừng",
};

export const NHAN_HANH_DONG_LT: Record<string, string> = {
  TAO: "Lập liệu trình",
  DIEU_CHINH: "Điều chỉnh",
  DANG_KY: "Đăng ký",
  DUNG: "Dừng",
  MO_LAI: "Mở lại",
  HOAN_TAC: "Hoàn tác",
  TU_DONG: "Hệ thống tự cập nhật",
};

/** Ba danh sách của tab Liệu trình (máy chủ lọc). */
export type LoaiDsCskh = "sap_het" | "de_xuat" | "dang_do";

/** Chip "Sắp hết lộ trình · <lý do>" (null khi không sắp hết). */
export function nhanSapHet(l: Pick<LieuTrinh, "sap_het_ly_do" | "sap_het_da_xu_ly">): string | null {
  if (!l.sap_het_ly_do) return null;
  return `Sắp hết lộ trình · ${l.sap_het_ly_do}${l.sap_het_da_xu_ly ? " · CSKH đã xử lý" : ""}`;
}

/** [Thêm buổi]: số buổi kế hoạch MỚI = hiện tại + số gõ (1..200 tổng). Gõ rác /
 *  ≤ 0 / vượt 200 → null (nút tắt) — không ném. Lệnh gửi `dang-ky` với số này
 *  (CSKH được đăng ký thêm buổi; máy chủ gác quyền + bản cũ). */
export function soBuoiSauKhiThem(hienTai: number, raw: string): number | null {
  const s = raw.trim();
  if (!/^\d{1,3}$/.test(s)) return null;
  const them = Number(s);
  const tong = hienTai + them;
  return them >= 1 && tong <= 200 ? tong : null;
}

/** Ngưỡng "quá X ngày chưa quay lại" để chọn nhanh (mặc định = máy chủ: 14). */
export const QUA_NGAY_CHON = [7, 14, 30, 60] as const;
export const QUA_NGAY_MAC_DINH = 14;

/** Trần lượt một lần gọi chip (máy chủ cắt ở 300). */
const TRAN_LUOT = 300;

/** Khoá ổn định cho một lô lượt: bỏ rỗng, bỏ trùng, xếp — đổi thứ tự hiển thị
 *  không gọi lại máy chủ. */
export function khoaLuot(ids: readonly (string | null | undefined)[]): string {
  return [...new Set(ids.filter((x): x is string => typeof x === "string" && x !== ""))]
    .sort()
    .slice(0, TRAN_LUOT)
    .join(",");
}

/** "Buổi 3/10 · chưa làm · đã trả trước" — chip trên dòng chỉ định. Chữ máy
 *  chủ ghép (`chu`) đi trước; thiếu thì ghép từ số + `da_lam`. */
export function nhanBuoi(c: {
  buoi_so: number;
  so_buoi: number;
  tra_truoc: boolean;
  da_lam?: boolean;
  chu?: string;
}): string {
  const lam = c.da_lam === true ? " · đã làm" : c.da_lam === false ? " · chưa làm" : "";
  return `${c.chu || `Buổi ${c.buoi_so}/${c.so_buoi}${lam}`}${c.tra_truoc ? " · đã trả trước" : ""}`;
}

/** Dòng KHÁCH ở phòng dịch vụ (một khách một dòng): "Buổi k/N · chưa làm"
 *  của chỉ định đầu tiên (trong các chỉ định / dòng hàng chờ phòng đang thấy)
 *  thuộc liệu trình. Không có → null (dòng giữ nguyên). */
export function nhanBuoiCuaLuot(
  chip: ChipLieuTrinh | null,
  visitId: string,
  cacChiDinh: readonly ({ id: string } | { ref_id: string })[],
): string | null {
  if (!chip) return null;
  for (const x of cacChiDinh) {
    const c = chip.chi_dinh["ref_id" in x ? x.ref_id : x.id];
    if (c && c.visit_id === visitId) return nhanBuoi(c);
  }
  return null;
}

/** Chip theo LƯỢT (tiếp đón, hàng chờ bàn khám):
 *  "Liệu trình Ghế điện: còn 3 buổi đã trả" — rỗng khi khách không có liệu trình
 *  nào đang chạy. Nhiều liệu trình → nối bằng " · ". */
export function nhanLieuTrinhLuot(chip: ChipLieuTrinh | null, visitId: string | null): string | null {
  if (!chip || !visitId) return null;
  const ds = chip.khach[visitId] ?? [];
  if (ds.length === 0) return null;
  return ds
    .map((l) =>
      l.con_tra_truoc > 0
        ? `Liệu trình ${l.service_name}: còn ${l.con_tra_truoc} buổi đã trả`
        : `Liệu trình ${l.service_name}: đã làm ${l.da_lam}/${l.so_buoi}`,
    )
    .join(" · ");
}

/** "Buổi 2/5" (đã làm / kế hoạch) cho dòng CSKH / khung khách. */
export function nhanTienDo(l: Pick<LieuTrinh, "da_lam" | "so_buoi">): string {
  return `Đã làm ${l.da_lam}/${l.so_buoi} buổi`;
}

/** Số buổi CSKH chọn khi đăng ký: "1" | "N" (cả lộ trình) | số gõ tay.
 *  Rác / ngoài 1..200 → null (nút Đăng ký tắt) — không ném. */
export function docSoBuoiDangKy(raw: string): number | null {
  const s = raw.trim();
  if (!/^\d{1,3}$/.test(s)) return null;
  const n = Number(s);
  return n >= 1 && n <= 200 ? n : null;
}
