// BẢY PHIẾU KHÁM — kiểu dữ liệu và phép biến đổi THUẦN cho màn vẽ phiếu.
//
// Không luật nghiệp vụ nào ở đây. Khung, khoá, "ô nào hợp lệ" do máy chủ quyết
// (`PhieuKhamService`); "hồ sơ đã chốt chưa" do clinical shell quyết và truyền
// vào thành chế độ. Tệp này chỉ làm ba việc mà màn nào vẽ phiếu cũng cần và
// phải giống nhau:
//
//   1. gom các ô liền nhau thành NHÓM (tiêu đề nhỏ) và BẢNG (ô có `bang`);
//   2. bật/tắt một lựa chọn mà vẫn giữ đúng thứ tự của khung;
//   3. dựng gói tự lưu mà KHÔNG xoá dấu nguồn của giá trị — ô không ai đụng
//      tới giữ nguyên nguồn cũ, ô người gõ mới thành USER.
//
// Định danh luôn là KHOÁ (`ma`). Nhãn (`ten`) chỉ để hiển thị, không bao giờ
// đem đi so khớp.

export type KieuO = "text" | "so" | "ngay" | "doan_van" | "chon" | "nhieu_chon";

export interface LuaChon {
  ma: string;
  ten: string;
}

export interface BangCuaO {
  ma: string;
  ten: string;
  cot: string[];
}

export interface OPhieu {
  ma: string;
  ten: string;
  kieu: KieuO;
  nhom?: string;
  goi_y?: string;
  /** Đơn vị ô số ("ngày", "mm"…) — khung chưa có thì màn tách từ nhãn
   *  (`lib/o-so.ts::nhanVaDonVi`), chỉ để hiển thị. */
  don_vi?: string;
  lua_chon?: LuaChon[];
  bang?: BangCuaO;
  hang?: string;
  cot?: string;
  /** Nhãn do người trích đặt, không có trong tài liệu nguồn. */
  ten_tu_dat?: boolean;
}

export type LoaiLienKet =
  | "mang_sang"
  | "chi_dinh_cls"
  | "don_thuoc"
  | "chi_dinh_thu_thuat";

export interface MucPhieu {
  ma: string;
  ten: string;
  /** Mục dạng BẢNG của mẫu kết quả v3 (26/09/2026) — giá trị ô {ma_cột: giá trị}. */
  cot?: { ma: string; ten: string }[];
  lien_ket?: { loai: LoaiLienKet; truong?: string[]; rang_buoc?: string };
  block: OPhieu[];
}

export type GiaTriO = string | string[];

export interface ONhap {
  gia_tri: GiaTriO;
  nguon: string;
}

export interface KetQuaMotChiDinh {
  loai: "PHIEU" | "TEP";
  phieu_id?: string;
  tep_id?: string;
  form_id?: string;
  ten: string | null;
  trang_thai?: "DRAFT" | "READY";
  dang_sua?: boolean;
  ban_thu?: number | null;
  hoan_tat_luc?: string | null;
  tai_len_luc?: string;
  loai_tep?: string;
  /** Tệp: NULL/HOP_LE = in được; CHO_XAC_NHAN / TU_CHOI thì KHÔNG in. */
  xac_nhan_trang_thai?: string | null;
  khung?: MucPhieu[] | null;
  du_lieu?: Record<string, ONhap> | null;
}

export interface ChiDinhVaKetQua {
  service_order_id: string;
  service_code: string;
  /** CHỈ để hiển thị — không đem đi so khớp. */
  ten_hien_thi: string;
  thuc_hien: string | null;
  ket_qua_trang_thai: "CO_KET_QUA" | "DANG_NHAP" | "CHUA_CO";
  ket_qua: KetQuaMotChiDinh[];
  /** Mẫu kết quả đã gắn cho dịch vụ (Danh mục & biểu mẫu). */
  mau_ket_qua?: MauKetQuaNgan[];
  /** Lần chỉ định trong lượt (1, 2, 3… mỗi lần bấm chốt). null = mang sang. */
  lan?: number | null;
  chi_dinh_luc?: string | null;
  /** Chỉ định mang sang từ lượt trước. */
  mang_sang?: boolean;
  /** Mã sản phẩm KiotViet (mã phòng khám) — hiện cạnh tên (27/09/2026). */
  ma_kiotviet?: string | null;
  gia?: number | null;
  /** Đã thu tiền dịch vụ này (phiếu thu PAID). */
  da_thu?: boolean;
  /** Bác sĩ đã xem kết quả lúc nào — chưa xem thì đếm "N mới". */
  da_xem_luc?: string | null;
  /** Bác sĩ tick "Bắt buộc" (25/09/2026) — quầy thu không bỏ được. */
  bat_buoc?: boolean;
  /** Làm ở đối tác: trạng thái bàn đối tác. null = làm tại phòng khám. */
  doi_tac?: TrangThaiDoiTac | null;
}

export type TrangThaiDoiTac = "CHO_LAY_MAU" | "DA_LAY_MAU" | "CHO_TAI_LIEU" | "DA_GUI_KET_QUA";

export const NHAN_DOI_TAC: Record<TrangThaiDoiTac, string> = {
  CHO_LAY_MAU: "Đối tác · chờ lấy mẫu",
  DA_LAY_MAU: "Đối tác · đã lấy mẫu",
  CHO_TAI_LIEU: "Đối tác · chờ tài liệu",
  DA_GUI_KET_QUA: "Đối tác · đã gửi kết quả",
};

/** Một mẫu kết quả (18 mẫu KQ_*): `ma` không kèm tiền tố `KQ_`. */
export interface MauKetQuaNgan {
  ma: string;
  ten: string;
  nhom?: string | null;
}

/** Một dòng danh mục mục C — nhãn nguồn + mã/giá THẬT máy chủ đã gắn. */
export interface MucCls {
  nhan: string;
  cach_tra_ket_qua: string;
  form_id_ket_qua: string | null;
  /** null = phòng khám chưa có dịch vụ này → ô khoá. */
  service_code: string | null;
  gia?: number | null;
  /** Mã phòng khám (KiotViet) — dòng "Dịch vụ khác trong bảng giá". */
  ma_kiotviet?: string | null;
}

export interface NhomCls {
  nhom: string;
  muc: MucCls[];
}

/** Hậu tố máy chủ gắn cho nhóm dịch vụ có trong bảng giá mà phiếu giấy không
 *  liệt kê (`phieu_kham_service.py`, 26/09/2026). */
export const HAU_TO_DANH_MUC_PK = " (danh mục phòng khám)";

/**
 * Tách danh mục mục C/F như bản giao diện mẫu (27/09/2026): nhóm theo PHIẾU
 * GIẤY (luôn mở) và MỘT danh sách "Dịch vụ khác trong bảng giá" (gập) — mỗi
 * dòng kèm tên nhóm gốc (đã bỏ hậu tố) để bác sĩ biết phòng làm.
 */
export function tachDanhMucKhac(ds: readonly NhomCls[]): {
  chinh: NhomCls[];
  khac: (MucCls & { nhom_goc: string })[];
} {
  const chinh: NhomCls[] = [];
  const khac: (MucCls & { nhom_goc: string })[] = [];
  for (const n of ds ?? []) {
    if (!n || !Array.isArray(n.muc)) continue;
    if (typeof n.nhom === "string" && n.nhom.endsWith(HAU_TO_DANH_MUC_PK)) {
      const goc = n.nhom.slice(0, -HAU_TO_DANH_MUC_PK.length);
      for (const m of n.muc) khac.push({ ...m, nhom_goc: goc });
    } else {
      chinh.push(n);
    }
  }
  return { chinh, khac };
}

/** Chip mẫu kết quả ở dòng danh mục (bản mẫu `badgeMau`): đối tác · mẫu PDF ·
 *  tự do. Chỉ đọc cờ máy chủ đã gắn (`cach_tra_ket_qua`, `form_id_ket_qua`). */
export function chipMauDanhMuc(m: Pick<MucCls, "cach_tra_ket_qua" | "form_id_ket_qua">): {
  nhan: string;
  tone: "info" | "brand" | "neutral";
} {
  if (m.cach_tra_ket_qua === "Đối tác") return { nhan: "đối tác", tone: "info" };
  if (m.form_id_ket_qua && m.form_id_ket_qua !== "KQ_CHUNG") return { nhan: "mẫu PDF", tone: "brand" };
  return { nhan: "tự do", tone: "neutral" };
}

export interface DauPhieu {
  /** Nhãn ngắn theo khoá bind của nguồn ("HA", "CN"…) — máy chủ giữ. */
  nhan: Record<string, string>;
  hanh_chinh: Record<string, string | number | null>;
  sinh_hieu: Record<string, string | number | null>;
  sinh_hieu_luc: string | null;
  tu_van: { noi_dung: string; luc: string; vong: number; consultation_id?: string }[];
  /** Ô HỒ SƠ đồng bộ từ bảng khách (24/09/2026) — thứ tự hiện. */
  ho_so?: string[];
  /** Thẻ khách Y HỆT bản giao diện mẫu (27/09/2026). */
  the_khach?: {
    bac_si: string | null;
    kenh_dat: string | null;
    co_so: string | null;
    loai_kham: string | null;
    /** Số booking (lúc đặt) + số check-in (quầy cấp) — `components/ui/SoLuot`. */
    so_booking?: number | null;
    so_tiep_don?: number | null;
    /** Đầu trang bản in (27/09/2026): tên phòng khám + địa chỉ cơ sở của lượt. */
    phong_kham?: string | null;
    dia_chi_co_so?: string | null;
  };
  /** Chín ô thẻ sinh hiệu: nhãn đầy đủ + giá trị đã kèm đơn vị. */
  the_sinh_hieu?: { khoa: string; nhan: string; gia_tri: string | null }[];
  sinh_hieu_nguoi?: string | null;
}

/** Khung của MỘT phiên bản — phiếu đã điền ghim phiên bản của nó. */
export interface DinhNghiaPhieu {
  form_id: string;
  version: number;
  ten: string;
  khung: MucPhieu[];
}

/**
 * Chế độ phiếu — NHẬN từ clinical shell, gói phiếu không tự quyết mốc chốt.
 *   editable          đang khám, gõ được
 *   finalized_locked  hồ sơ đã chốt, chỉ đọc
 *   amendment_mode    đang đính chính — gõ được, dấu vết là việc của shell
 */
export type CheDoPhieu = "editable" | "finalized_locked" | "amendment_mode";

/** Chế độ lạ = KHÔNG ghi được (đóng khi nghi ngờ), giống máy chủ. */
export function ghiDuoc(cheDo: string | null | undefined): boolean {
  return cheDo === "editable" || cheDo === "amendment_mode";
}

// ---------------------------------------------------------------------------
// 1. Gom ô thành nhóm và bảng
// ---------------------------------------------------------------------------
export interface HangBang {
  hang: string;
  /** Theo đúng thứ tự `bang.cot`; ô thiếu ở cột nào thì null. */
  o: (OPhieu | null)[];
}

export type DonViVe =
  | { loai: "o"; o: OPhieu }
  | { loai: "bang"; bang: BangCuaO; hang: HangBang[] };

export interface NhomVe {
  tieu_de: string | null;
  don_vi: DonViVe[];
}

/** Ô liền nhau cùng `nhom` → một nhóm; ô liền nhau cùng `bang.ma` → một bảng. */
export function gomNhom(block: OPhieu[]): NhomVe[] {
  const ra: NhomVe[] = [];
  for (const o of block) {
    const tieuDe = o.nhom ?? null;
    let nhom = ra[ra.length - 1];
    if (!nhom || nhom.tieu_de !== tieuDe) {
      nhom = { tieu_de: tieuDe, don_vi: [] };
      ra.push(nhom);
    }
    if (!o.bang) {
      nhom.don_vi.push({ loai: "o", o });
      continue;
    }
    const cuoi = nhom.don_vi[nhom.don_vi.length - 1];
    let bang: Extract<DonViVe, { loai: "bang" }>;
    if (cuoi && cuoi.loai === "bang" && cuoi.bang.ma === o.bang.ma) {
      bang = cuoi;
    } else {
      bang = { loai: "bang", bang: o.bang, hang: [] };
      nhom.don_vi.push(bang);
    }
    const tenHang = o.hang ?? o.ten;
    let hang = bang.hang.find((h) => h.hang === tenHang);
    if (!hang) {
      hang = { hang: tenHang, o: o.bang.cot.map(() => null) };
      bang.hang.push(hang);
    }
    const viTri = Math.max(0, o.bang.cot.indexOf(o.cot ?? ""));
    hang.o[viTri] = o;
  }
  return ra;
}

// ---------------------------------------------------------------------------
// 2. Bật/tắt lựa chọn — giữ thứ tự của khung
// ---------------------------------------------------------------------------
export function batTatLuaChon(
  dangChon: readonly string[],
  ma: string,
  thuTuKhung: readonly LuaChon[],
): string[] {
  const tap = new Set(dangChon);
  if (tap.has(ma)) tap.delete(ma);
  else tap.add(ma);
  return thuTuKhung.map((l) => l.ma).filter((m) => tap.has(m));
}

// ---------------------------------------------------------------------------
// 3. Gói tự lưu — không xoá dấu nguồn
// ---------------------------------------------------------------------------
function giongNhau(a: GiaTriO | undefined, b: GiaTriO | undefined): boolean {
  if (Array.isArray(a) || Array.isArray(b)) {
    const x = Array.isArray(a) ? a : [];
    const y = Array.isArray(b) ? b : [];
    return x.length === y.length && x.every((v, i) => v === y[i]);
  }
  return (a ?? "") === (b ?? "");
}

function rong(v: GiaTriO | undefined): boolean {
  return v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
}

/**
 * `dangCo`: giá trị đang thấy trên màn. `goc`: bản máy chủ trả lúc mở.
 * Ô không đổi giữ NGUỒN CŨ (vd `PATIENT_CONTEXT`); ô đổi thành `USER`.
 * Ô rỗng mà gốc cũng không có thì không gửi — không đẻ khoá rỗng vô nghĩa.
 */
/** CHỈ các ô khác bản đã lưu gần nhất (lát 2, 26/09/2026) — gửi phần này thay
 *  cho cả phiếu: hai người sửa hai ô khác nhau không còn 409 / mất chữ đang gõ. */
export function phanThayDoi(
  goi: Record<string, ONhap>,
  daLuu: Record<string, ONhap>,
): Record<string, ONhap> {
  const ra: Record<string, ONhap> = {};
  for (const [ma, o] of Object.entries(goi)) {
    const cu = daLuu[ma];
    if (!cu || !giongNhau(cu.gia_tri, o.gia_tri) || cu.nguon !== o.nguon) ra[ma] = o;
  }
  return ra;
}

export function dungGoiLuu(
  dangCo: Record<string, GiaTriO>,
  goc: Record<string, ONhap>,
): Record<string, ONhap> {
  const ra: Record<string, ONhap> = {};
  for (const [ma, v] of Object.entries(dangCo)) {
    const cu = goc[ma];
    if (cu && giongNhau(cu.gia_tri, v)) {
      ra[ma] = { gia_tri: cu.gia_tri, nguon: cu.nguon };
      continue;
    }
    if (!cu && rong(v)) continue;
    ra[ma] = { gia_tri: v, nguon: "USER" };
  }
  return ra;
}

/** Giá trị ban đầu cho màn từ bản máy chủ. */
export function giaTriBanDau(duLieu: Record<string, ONhap>): Record<string, GiaTriO> {
  return Object.fromEntries(Object.entries(duLieu).map(([k, v]) => [k, v.gia_tri]));
}

// ---------------------------------------------------------------------------
// Tham chiếu nguồn (mục E, F) — nhãn CHỜ ÁNH XẠ, chưa phải định danh
// ---------------------------------------------------------------------------
export interface MauThuoc {
  ma: string;
  nhan_nguon: string;
  brand: string;
  type: string;
  dosage: string;
  note: string;
  unit: string;
  /** null = chưa gắn thuốc kho → chưa thu tiền, chưa cấp được. */
  drug_catalog_id: string | null;
  gia?: number | null;
}

export interface ThuThuatNguon {
  ma: string;
  nhan: string;
  form_id_ket_qua: string | null;
  /** null = danh mục chưa gắn mã dịch vụ → chưa tạo được chỉ định. */
  service_code: string | null;
  gia?: number | null;
}

/** Một dòng đơn thuốc trên phiếu — hình của contract `prescription`. */
export interface DongThuoc {
  /** Mã dòng `prescription` đã lưu — thiếu thì máy chủ tạo dòng mới. */
  id?: string | null;
  drug_catalog_id: string | null;
  ten_thuoc: string;
  duong_dung: string;
  so_luong: string;
  don_vi: string;
  cach_dung: string;
  luu_y: string;
  /** Mẫu cách dùng đã điền sẵn dòng này (nếu có) — để còn biết chữ từ đâu ra. */
  mau_ma: string | null;
}

/** Chọn một thuốc từ danh mục gợi ý → dòng đơn điền sẵn, bác sĩ sửa được. */
export function dongTuMau(m: MauThuoc): DongThuoc {
  return {
    drug_catalog_id: m.drug_catalog_id,
    ten_thuoc: m.nhan_nguon,
    duong_dung: m.type,
    so_luong: "",
    don_vi: m.unit,
    cach_dung: m.dosage,
    luu_y: m.note,
    mau_ma: m.ma,
  };
}

// Đơn thuốc ↔ bảng `prescription`. Bảng không có cột đường dùng / đơn vị
// (IP-5): ghép vào `dosage_instructions` ("Uống — …") và `quantity` ("10 hộp"),
// tách lại khi đọc. Chữ ghép giữ nguyên nghĩa cho nhà thuốc đọc.
export interface DongDonMayChu {
  id: string;
  drug_catalog_id: string | null;
  drug_name_raw: string | null;
  quantity: string | null;
  dosage_instructions: string | null;
  caution: string | null;
}

const NOI = " — ";

export function dongTuDon(r: DongDonMayChu): DongThuoc {
  const sl = (r.quantity ?? "").trim();
  const m = /^([\d.,/]+)\s*(.*)$/.exec(sl);
  const cd = r.dosage_instructions ?? "";
  const i = cd.indexOf(NOI);
  return {
    id: r.id,
    drug_catalog_id: r.drug_catalog_id,
    ten_thuoc: r.drug_name_raw ?? "",
    duong_dung: i > 0 ? cd.slice(0, i) : "",
    // Không bắt đầu bằng số (vd lần tự lưu đầu khi mới chọn thuốc: "hộp") →
    // cả chuỗi là ĐƠN VỊ. Bấm thật 23/09: nhét vào số lượng thì gõ "2" thành "hộp2".
    so_luong: m ? m[1] : "",
    don_vi: m ? m[2] : sl,
    cach_dung: i > 0 ? cd.slice(i + NOI.length) : cd,
    luu_y: r.caution ?? "",
    mau_ma: null,
  };
}

export function donTuDong(d: DongThuoc) {
  return {
    id: d.id ?? null,
    drug_catalog_id: d.drug_catalog_id,
    drug_name: d.ten_thuoc.trim(),
    quantity: [d.so_luong.trim(), d.don_vi.trim()].filter(Boolean).join(" "),
    dosage: [d.duong_dung.trim(), d.cach_dung.trim()].filter(Boolean).join(NOI),
    caution: d.luu_y.trim(),
  };
}

export function tienVn(n: number | null | undefined): string {
  return typeof n === "number" ? `${n.toLocaleString("vi-VN")} đ` : "chưa có giá";
}

/** Tìm thuốc theo tên / đường dùng, không phân biệt dấu và hoa thường. */
export function locMauThuoc(ds: readonly MauThuoc[], tu: string): MauThuoc[] {
  const bo = (s: string) =>
    s.normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/đ/gi, "d").toLowerCase();
  const q = bo(tu.trim());
  if (!q) return [...ds];
  return ds.filter((m) => bo(`${m.nhan_nguon} ${m.brand} ${m.type}`).includes(q));
}

// ---------------------------------------------------------------------------
// Hiển thị
// ---------------------------------------------------------------------------
/** Ô trống in "—" (DESIGN.md §6.5), không bỏ trắng. */
/** BA KHỐI của phiếu bác sĩ chính (Tuyền chốt 25/09/2026 — bản giao diện mẫu):
 *  gom các mục SẴN CÓ, không đổi `ma` ô nào — phiếu đã lưu vẫn đọc đúng. Mục
 *  hành chính luôn nằm trên, ngoài các khối. Màn khám và bản in dùng chung. */
export const KHOI_PHIEU: { so: 1 | 2 | 3; ten: string; muc: string[] }[] = [
  { so: 1, ten: "Thông tin cơ bản", muc: ["A", "B"] },
  { so: 2, ten: "Chỉ định cận lâm sàng", muc: ["C"] },
  { so: 3, ten: "Chỉ định điều trị", muc: ["D", "E", "F", "G"] },
];

/** Ô đã có dữ liệu? (rỗng · mảng rỗng · bảng mọi cột rỗng = chưa) — bản in ẩn ô trống. */
export function coNhap(nhap: ONhap | undefined): boolean {
  const g: unknown = nhap?.gia_tri;
  if (g === null || g === undefined) return false;
  if (Array.isArray(g)) return g.length > 0;
  if (typeof g === "object") {
    return Object.values(g as Record<string, unknown>).some((v) => v !== "" && v != null);
  }
  return String(g).trim() !== "";
}

export function hienThi(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

/** Giá trị một ô của phiếu kết quả, đọc theo KHOÁ lựa chọn → nhãn. */
export function giaTriDoc(
  o: OPhieu,
  nhap: ONhap | undefined,
  cot?: { ma: string; ten: string }[],
): string {
  if (!nhap) return "—";
  const g: unknown = nhap.gia_tri;
  // Ô mục BẢNG (mẫu kết quả v3): {ma_cột: giá trị}. Trả thẳng object cho React
  // vẽ là sập cả khối kết quả.
  if (g && typeof g === "object" && !Array.isArray(g)) {
    const ds = Object.entries(g as Record<string, unknown>)
      .filter(([, v]) => v !== "" && v != null)
      .map(([c, v]) => `${cot?.find((x) => x.ma === c)?.ten ?? c}: ${String(v)}`);
    return ds.length ? ds.join(" · ") : "—";
  }
  if (rong(nhap.gia_tri)) return "—";
  if (Array.isArray(nhap.gia_tri)) {
    const nhan = new Map((o.lua_chon ?? []).map((l) => [l.ma, l.ten]));
    return nhap.gia_tri.map((m) => nhan.get(m) ?? m).join(", ");
  }
  if (o.kieu === "chon") {
    return o.lua_chon?.find((l) => l.ma === nhap.gia_tri)?.ten ?? nhap.gia_tri;
  }
  return nhap.gia_tri;
}

/** Ô "Kết luận" của phiếu kết quả — tách riêng khỏi các dòng số đo. */
export const LA_KET_LUAN = (ma: string, ten: string) =>
  ma === "ket_luan" || /^kết luận/i.test(ten.trim());

/**
 * Các dòng CÓ giá trị của một phiếu kết quả READY + câu kết luận (tách riêng).
 * Dùng chung cho màn khám (mục "Đã chỉ định & kết quả") và bản in phiếu khám —
 * hai nơi đọc một kết quả phải ra cùng một chữ.
 */
export function dongKetQua(k: KetQuaMotChiDinh): {
  dong: { nhan: string; gia: string }[];
  ketLuan: string | null;
} {
  const dong: { nhan: string; gia: string }[] = [];
  let ketLuan: string | null = null;
  for (const m of k.khung ?? []) {
    for (const o of m.block) {
      const nhap = k.du_lieu?.[o.ma];
      if (!coNhap(nhap)) continue;
      const g: unknown = nhap?.gia_tri;
      const donVi = (gia: string) => (o.goi_y && /\d$/.test(gia) ? `${gia} ${o.goi_y}` : gia);
      if (m.cot && g && typeof g === "object" && !Array.isArray(g)) {
        for (const c of m.cot) {
          const v = (g as Record<string, unknown>)[c.ma];
          if (v === "" || v == null) continue;
          dong.push({ nhan: `${o.ten} · ${c.ten}`, gia: donVi(String(v)) });
        }
        continue;
      }
      const gia = giaTriDoc(o, nhap, m.cot);
      if (LA_KET_LUAN(o.ma, o.ten)) ketLuan = gia;
      else dong.push({ nhan: o.ten, gia: donVi(gia) });
    }
  }
  return { dong, ketLuan };
}

/** Ảnh IN ĐƯỢC của một chỉ định: ảnh, đã xác nhận hợp lệ (hoặc tải ở phòng). */
export function anhInDuoc(d: ChiDinhVaKetQua): KetQuaMotChiDinh[] {
  return d.ket_qua
    .filter(
      (k) =>
        k.loai === "TEP" &&
        k.tep_id &&
        k.loai_tep === "ANH" &&
        (k.xac_nhan_trang_thai ?? "HOP_LE") === "HOP_LE",
    )
    .sort((a, b) => (a.tai_len_luc ?? "").localeCompare(b.tai_len_luc ?? ""));
}

export const NHAN_KET_QUA: Record<ChiDinhVaKetQua["ket_qua_trang_thai"], string> = {
  CO_KET_QUA: "Có kết quả",
  DANG_NHAP: "Đang nhập kết quả",
  CHUA_CO: "Chưa có kết quả",
};
