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
  /** Đợt 3 (27/09/2026, bản v2): ô ẩn sau một chip tên ô — bấm chip mới hiện.
   *  Ô đã có giá trị LUÔN hiện (thu gọn không giấu dữ liệu). */
  thu_gon?: boolean;
  /** Chỉ hiện khi ô chọn `o` đang chọn mã `la` ("Chi tiết dị ứng thuốc" khi
   *  "Dị ứng thuốc: Có"). Ô đã có giá trị LUÔN hiện. */
  hien_khi?: { o: string; la: string };
  /** Cả nhóm nằm trong ngăn gập — mặc định đóng, tự mở khi có ô điền. */
  gap?: boolean;
  /** Ô thêm sau khi trích nguồn — lý do (chỉ để đối chiếu). */
  them_sau_nguon?: string;
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
  /** Tệp: kiểu thật (máy chủ dò bằng nội dung). DICOM = không vẽ được, chỉ tải về. */
  mime?: string | null;
  /** Tệp: NULL/HOP_LE = in được; CHO_XAC_NHAN / TU_CHOI thì KHÔNG in. */
  xac_nhan_trang_thai?: string | null;
  khung?: MucPhieu[] | null;
  du_lieu?: Record<string, ONhap> | null;
}

/** LẦN CHỈ ĐỊNH của lượt (06/10/2026) — MÁY CHỦ quyết, màn chỉ vẽ nhãn.
 *  Mặc định chỉ định vào `hien_tai`; chỉ nút "Chỉ định thêm (lần `ke_tiep`)"
 *  mới mở lần mới (`mo_moi_duoc` = lần hiện tại còn chỉ định sống). */
export interface LanChiDinh {
  hien_tai: number | null;
  ke_tiep: number;
  mo_moi_duoc: boolean;
}

/** Lệnh "mở lần mới" gửi kèm chỉ định: `lan_dang_thay` = lần hiện tại màn thấy. */
export interface LenhLanChiDinh {
  lan_moi: boolean;
  lan_dang_thay: number | null;
}

export type KetQuaDatChiDinh =
  | { ok: true; order_ids?: string[]; lan?: number | null }
  | { ok: false; loi: string };

export type DatChiDinh = (
  codes: string[],
  /** Mã tick "Bắt buộc" (25/09/2026) — quầy thu không bỏ được. */
  batBuoc: string[],
  lan?: LenhLanChiDinh,
) => Promise<KetQuaDatChiDinh>;

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
  /** Mẫu để ĐIỀN (01/10/2026, máy chủ quyết): đã gắn, hoặc mặc định của máy
   *  (gợi ý / CHUNG nhập tự do) khi quản lý chưa gắn. */
  mau_chon_duoc?: MauKetQuaNgan[];
  mau_chon_san?: string | null;
  /** true = quản lý chưa gắn mẫu, mẫu chọn sẵn là mặc định của máy. */
  mau_mac_dinh?: boolean;
  /** Lần chỉ định trong lượt (1, 2, 3… mỗi lần bấm chốt). null = mang sang. */
  lan?: number | null;
  chi_dinh_luc?: string | null;
  /** Chỉ định mang sang từ lượt trước. */
  mang_sang?: boolean;
  /** Làm thêm tại quầy (01/10/2026): "Làm thêm tại quầy tiếp đón"; null = bác sĩ. */
  lam_them?: string | null;
  /** Mã sản phẩm KiotViet (mã phòng khám) — hiện cạnh tên (27/09/2026). */
  ma_kiotviet?: string | null;
  gia?: number | null;
  /** Đã thu tiền dịch vụ này (phiếu thu PAID). */
  da_thu?: boolean;
  /** Khách trả TRỰC TIẾP cho đối tác (27/09/2026) — phòng khám không thu. */
  doi_tac_thu?: boolean;
  /** Đối tác đã ghi nhận thu tiền khách (bàn đối tác). */
  doi_tac_da_thu?: boolean;
  /** Bác sĩ đã xem kết quả lúc nào — chưa xem thì đếm "N mới". */
  da_xem_luc?: string | null;
  /** Bác sĩ tick "Bắt buộc" (25/09/2026) — quầy thu không bỏ được. */
  bat_buoc?: boolean;
  /** Làm ở đối tác: trạng thái bàn đối tác. null = làm tại phòng khám. */
  doi_tac?: TrangThaiDoiTac | null;
  /** Chỉ định ĐIỀU TRỊ (nhóm DIEU_TRI — máy chủ suy theo dữ liệu, 07/10/2026):
   *  bản in lượt xếp vào mục "Điều trị" (phiếu 2 ô), không vào CLS. */
  dieu_tri?: boolean;
}

/** Ô đã ghi của PHIẾU ĐIỀU TRỊ một chỉ định (mỗi ô một nhãn — tên ô, không lặp
 *  tên mục) — bản in lượt. Phiếu điều trị không có bước Hoàn tất nên máy chủ trả
 *  nội dung cả khi phiếu còn DRAFT. Rác / thiếu → mảng rỗng, không ném. */
export function oPhieuDieuTri(c: ChiDinhVaKetQua): { ma: string; ten: string; gia: string }[] {
  const k = c.ket_qua.find((x) => x.loai === "PHIEU" && x.form_id === "KQ_PHIEU_DIEU_TRI" && x.khung);
  if (!k || !Array.isArray(k.khung)) return [];
  const duLieu = (k.du_lieu ?? {}) as Record<string, { gia_tri?: unknown } | undefined>;
  return (k.khung as { block?: { ma?: string; ten?: string }[] }[])
    .flatMap((m) => m.block ?? [])
    .flatMap((o) => {
      const g = o.ma ? duLieu[o.ma]?.gia_tri : null;
      return o.ma && typeof g === "string" && g.trim() ? [{ ma: o.ma, ten: o.ten ?? o.ma, gia: g }] : [];
    });
}

export type TrangThaiDoiTac = "CHO_LAY_MAU" | "DA_LAY_MAU" | "DA_NHAN_MAU" | "DA_GUI_KET_QUA";

export const NHAN_DOI_TAC: Record<TrangThaiDoiTac, string> = {
  CHO_LAY_MAU: "Đối tác · chờ lấy mẫu",
  DA_LAY_MAU: "Đối tác · đã lấy mẫu",
  DA_NHAN_MAU: "Đối tác · đã nhận mẫu · xong",
  DA_GUI_KET_QUA: "Đối tác · đã gửi kết quả",
};

/** Một mẫu kết quả (18 mẫu KQ_*): `ma` không kèm tiền tố `KQ_`. */
export interface MauKetQuaNgan {
  ma: string;
  ten: string;
  nhom?: string | null;
  /** Mẫu của CHÍNH dịch vụ này (máy chủ tính). false = của dịch vụ khác. */
  cua_dich_vu?: boolean;
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
  /** Khách trả TRỰC TIẾP cho đối tác (27/09/2026, máy chủ nói): giá chỉ tham
   *  khảo, không cộng vào tổng phòng khám. */
  doi_tac_thu?: boolean;
  /** Nhóm hàng của danh mục chuẩn ("Siêu âm › Siêu âm thai", "XN thu hộ"…) —
   *  máy chủ gắn (01/10/2026), dùng để gom kết quả tìm. */
  nhom_hang?: string | null;
  /** Câu khoá ô (vd chưa gắn nhóm việc) — máy chủ quyết; có = ô tick khoá. */
  khoa?: string | null;
  /** TÊN THẬT trong bảng giá (C21, 02/10/2026) — màn hiện tên này, `nhan` (nhãn
   *  phiếu giấy) thành dòng phụ khi khác; ô tìm dò cả hai. */
  ten_dich_vu?: string | null;
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
  /** "lượt trước" khi số đo của lượt khác cùng buổi (máy chủ trả); null = lượt này. */
  sinh_hieu_nguon?: string | null;
  tu_van: { noi_dung: string; luc: string; vong: number; consultation_id?: string }[];
  /** MỌI phiên tư vấn của lượt + bản mới nhất (kể cả chưa ghi / đã xoá trắng) —
   *  chỗ sửa tại chỗ của bác sĩ tư vấn và bác sĩ chính (27/09/2026, mục 12). */
  phien_tu_van?: {
    consultation_id: string;
    vong: number;
    noi_dung: string;
    luc: string | null;
    nguoi: string | null;
  }[];
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
  /** Mọi ô của nhóm khai `gap` → cả nhóm vào ngăn gập. */
  gap: boolean;
}

/** Ô liền nhau cùng `nhom` → một nhóm; ô liền nhau cùng `bang.ma` → một bảng. */
export function gomNhom(block: OPhieu[]): NhomVe[] {
  const ra: NhomVe[] = [];
  for (const o of block) {
    const tieuDe = o.nhom ?? null;
    let nhom = ra[ra.length - 1];
    if (!nhom || nhom.tieu_de !== tieuDe) {
      nhom = { tieu_de: tieuDe, don_vi: [], gap: Boolean(o.gap) };
      ra.push(nhom);
    }
    nhom.gap = nhom.gap && Boolean(o.gap);
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
// 1b. Ô nào đang hiện (đợt 3, 27/09/2026 — góp ý phòng khám, khung v2)
// ---------------------------------------------------------------------------
/** Ô đã có giá trị? (chuỗi trắng · mảng rỗng = chưa). */
export function coGiaTriO(v: GiaTriO | undefined): boolean {
  return Array.isArray(v) ? v.length > 0 : typeof v === "string" && v.trim() !== "";
}

/**
 * Ô có đang hiện trên màn không. Luật ĐỌC TỪ KHUNG, không so tên nhóm:
 *   · có giá trị → luôn hiện (không bao giờ giấu dữ liệu, kể cả phiếu cũ);
 *   · `hien_khi` → hiện khi ô chọn kia đang chọn đúng mã;
 *   · `thu_gon`  → hiện khi người dùng đã bấm chip của nó (`daMo` — trạng thái
 *                  màn, không lưu);
 *   · còn lại    → hiện.
 */
export function oDangHien(
  o: OPhieu,
  gia: Readonly<Record<string, GiaTriO>>,
  daMo: ReadonlySet<string>,
): boolean {
  if (coGiaTriO(gia[o.ma])) return true;
  if (o.hien_khi) {
    const v = gia[o.hien_khi.o];
    return Array.isArray(v) ? v.includes(o.hien_khi.la) : v === o.hien_khi.la;
  }
  if (o.thu_gon) return daMo.has(o.ma);
  return true;
}

/** Ô `thu_gon` của nhóm CHƯA hiện — mỗi ô một chip "+ tên ô". */
export function oThuGonDangAn(
  nhom: NhomVe,
  gia: Readonly<Record<string, GiaTriO>>,
  daMo: ReadonlySet<string>,
): OPhieu[] {
  return nhom.don_vi.flatMap((d) =>
    d.loai === "o" && d.o.thu_gon && !oDangHien(d.o, gia, daMo) ? [d.o] : [],
  );
}

/** Mọi ô của một nhóm (kể cả ô trong bảng). */
export function oCuaNhom(nhom: NhomVe): OPhieu[] {
  return nhom.don_vi.flatMap((d) =>
    d.loai === "o" ? [d.o] : d.hang.flatMap((h) => h.o.filter((o): o is OPhieu => o !== null)),
  );
}

/** Số ô đã điền trong một danh sách ô — chip "N ô đã điền". */
export function soODaDien(ds: readonly OPhieu[], gia: Readonly<Record<string, GiaTriO>>): number {
  return ds.filter((o) => coGiaTriO(gia[o.ma])).length;
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

/** Cảnh báo từng ô máy chủ trả khi lưu (số / ngày không đọc được → lưu RỖNG). */
export interface CanhBaoO {
  ma: string;
  ten: string;
  loi: string;
}

function laCanhBao(x: unknown): x is CanhBaoO {
  if (!x || typeof x !== "object") return false;
  const o = x as Record<string, unknown>;
  return typeof o.ma === "string" && o.ma !== "" && typeof o.ten === "string" && typeof o.loi === "string";
}

/**
 * Gộp cảnh báo sau một lần tự lưu (đợt 3, 27/09/2026). Tự lưu chỉ gửi các ô
 * VỪA ĐỔI (`phanThayDoi`), nên `canh_bao` máy chủ trả chỉ nói về các ô ấy: ô
 * vừa gửi lấy cảnh báo mới (hoặc hết cảnh báo), ô khác GIỮ cảnh báo cũ — nếu
 * không, lưu một ô khác là xoá mất câu "“28-30” không phải số — ô để trống".
 * `moi` từ mạng: rác → coi như không có cảnh báo.
 */
export function gopCanhBao(
  cu: readonly CanhBaoO[],
  daGui: readonly string[],
  moi: unknown,
): CanhBaoO[] {
  const gui = new Set(daGui);
  const ra = cu.filter((c) => !gui.has(c.ma));
  const co = new Set(ra.map((c) => c.ma));
  for (const c of Array.isArray(moi) ? moi : []) {
    if (!laCanhBao(c) || co.has(c.ma)) continue;
    co.add(c.ma);
    ra.push({ ma: c.ma, ten: c.ten, loi: c.loi });
  }
  return ra;
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
  /** Nhóm như bản giao diện mẫu (`CHI_DINH_DT`, 27/09/2026): "Thủ thuật",
   *  "Sàn chậu — trải nghiệm 5 phút ghế ĐTT", "Sàn chậu — định hướng điều trị". */
  nhom?: string | null;
  /** Câu khoá ô do máy chủ gắn (vd chưa gắn nhóm việc) — 01/10/2026. */
  khoa?: string | null;
  /** Tên thật trong bảng giá (C21) — xem `MucCls.ten_dich_vu`. */
  ten_dich_vu?: string | null;
}

/** Nhóm mặc định khi máy chủ (bản cũ) chưa gửi `nhom` của thủ thuật. */
export const NHOM_THU_THUAT_MAC_DINH = "Thủ thuật / kỹ thuật điều trị";

/**
 * Danh mục khối 3 (thủ thuật · điều trị) theo NHÓM của máy chủ, giữ thứ tự
 * xuất hiện — cùng hình `NhomCls` với khối 2 để dùng chung `DanhMucChiDinh`.
 * Chỉ trình bày: nhóm nào, dòng nào là việc của `tham_chieu_nguon.json`.
 */
export function nhomThuThuat(ds: readonly ThuThuatNguon[] | null | undefined): NhomCls[] {
  const ra: NhomCls[] = [];
  const theoTen = new Map<string, NhomCls>();
  for (const t of ds ?? []) {
    if (!t || typeof t.nhan !== "string") continue;
    const ten = typeof t.nhom === "string" && t.nhom.trim() ? t.nhom.trim() : NHOM_THU_THUAT_MAC_DINH;
    let n = theoTen.get(ten);
    if (!n) {
      n = { nhom: ten, muc: [] };
      theoTen.set(ten, n);
      ra.push(n);
    }
    n.muc.push({
      nhan: t.nhan,
      cach_tra_ket_qua: t.form_id_ket_qua ? "Có biểu mẫu" : "",
      form_id_ket_qua: t.form_id_ket_qua,
      service_code: t.service_code,
      gia: t.gia ?? null,
      khoa: t.khoa ?? null,
      ten_dich_vu: t.ten_dich_vu ?? null,
    });
  }
  return ra;
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
  /** Đơn giá KHO (máy chủ, `drug_catalog.unit_price`) — chỉ để HIỂN THỊ; tiền
   *  thật do quầy thu tính. null = ngoài danh mục kho / kho chưa có giá. */
  don_gia?: number | null;
  /** ĐVT của kho (`don_vi_ban`) — có thì ĐVT là CHỮ, không phải ô gõ. */
  dvt_kho?: string | null;
  /** C14: số lượng do QUẦY THU THUỐC điền (bác sĩ để trống) — máy chủ trả; chỉ
   *  để hiện nhãn "SL do thu ngân điền", không gửi ngược lên. */
  so_luong_do_thu_ngan?: boolean;
  /** C19: số bác sĩ kê GỐC khi quầy đã đặt số khác (null = bác sĩ để trống). */
  so_luong_ke_goc?: string | null;
}

/** Chọn một thuốc từ danh mục gợi ý → dòng đơn điền sẵn, bác sĩ sửa được. */
export function dongTuMau(m: MauThuoc): DongThuoc {
  const dvtKho = m.drug_catalog_id ? m.unit.trim() || null : null;
  return {
    drug_catalog_id: m.drug_catalog_id,
    ten_thuoc: m.nhan_nguon,
    duong_dung: m.type,
    so_luong: "",
    don_vi: m.unit,
    cach_dung: m.dosage,
    luu_y: m.note,
    mau_ma: m.ma,
    don_gia: m.drug_catalog_id ? (m.gia ?? null) : null,
    dvt_kho: dvtKho,
  };
}

/** "+ Thuốc ngoài danh mục": dòng trống, bác sĩ gõ tên / ĐVT tự do. Chưa có tên
 *  thì chưa lưu (`luuDon` bỏ dòng không tên). */
export function dongNgoaiDanhMuc(): DongThuoc {
  return {
    drug_catalog_id: null,
    ten_thuoc: "",
    duong_dung: "",
    so_luong: "",
    don_vi: "",
    cach_dung: "",
    luu_y: "",
    mau_ma: null,
    don_gia: null,
    dvt_kho: null,
  };
}

/**
 * Số lượng đọc được từ chữ bác sĩ gõ — CÙNG luật với máy chủ
 * (`public.so_luong_tu_van_ban`): "30", "1,5", "2 viên" → số; "1/2", "uống đến
 * hết", "0" → null (không đoán).
 */
export function soLuongTuChu(s: string): number | null {
  const t = s.trim();
  if (!/^[0-9]+(?:[.,][0-9]+)?\s*(?:$|[^0-9/.,].*$)/.test(t)) return null;
  const n = Number(/^[0-9]+(?:[.,][0-9]+)?/.exec(t)![0].replace(",", "."));
  return n > 0 ? n : null;
}

/**
 * Thành tiền dự tính của một dòng — CHỈ để bác sĩ nhìn, quầy thu mới là nơi
 * tính tiền. null khi thiếu giá, số lượng không đọc được, hoặc ĐVT gõ khác ĐVT
 * kho (giá kho tính theo ĐVT kho — "2 hộp" nhân giá một viên là sai).
 */
export function thanhTienDong(d: DongThuoc): number | null {
  if (d.don_gia == null) return null;
  const sl = soLuongTuChu(d.so_luong);
  if (sl == null) return null;
  const bo = (x: string) => x.trim().toLowerCase();
  if (d.dvt_kho && d.don_vi.trim() && bo(d.don_vi) !== bo(d.dvt_kho)) return null;
  return Math.round(d.don_gia * sl);
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
  /** Đơn giá + ĐVT của kho (27/09/2026) — máy chủ cũ chưa trả thì thiếu. */
  don_gia?: number | null;
  dvt_kho?: string | null;
  /** C14: quầy thu thuốc điền số lượng bác sĩ để trống. */
  so_luong_do_thu_ngan?: boolean;
  /** C19: số bác sĩ kê gốc khi quầy đã sửa. */
  so_luong_ke_goc?: string | null;
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
    // Đơn cũ chưa ghi đơn vị mà kho có → lấy ĐVT kho (ô ĐVT giờ là chữ của kho).
    // Đơn đã ghi đơn vị thì GIỮ chữ đã ghi — không lặng lẽ đổi "2 hộp" thành
    // "2 viên" ở lần tự lưu sau.
    don_vi: (m ? m[2] : sl) || (r.dvt_kho ?? ""),
    cach_dung: i > 0 ? cd.slice(i + NOI.length) : cd,
    luu_y: r.caution ?? "",
    mau_ma: null,
    don_gia: r.don_gia ?? null,
    dvt_kho: r.dvt_kho ?? null,
    so_luong_do_thu_ngan: r.so_luong_do_thu_ngan ?? false,
    so_luong_ke_goc: r.so_luong_ke_goc ?? null,
  };
}

/** Phần SỐ của chữ số lượng ("10 viên" → "10"). */
function phanSo(chu: string | null | undefined): string {
  const m = /^([\d.,/]+)/.exec((chu ?? "").trim());
  return m ? m[1] : "";
}

/**
 * Quầy thu thuốc vừa điền / sửa số lượng (C14) → đưa vào đơn ĐANG MỞ của bác sĩ
 * mà không đè chữ bác sĩ đang gõ: chỉ dòng (cùng mã) mà bác sĩ còn để trống số
 * lượng, hoặc đã mang nhãn "do thu ngân điền". Trả `null` khi không có gì đổi.
 */
export function gopSoLuongQuayDien(hienTai: DongThuoc[], may: DongThuoc[]): DongThuoc[] | null {
  let doi = false;
  const ra = hienTai.map((d) => {
    const m = d.id ? may.find((x) => x.id === d.id) : undefined;
    if (!m || !m.so_luong_do_thu_ngan) return d;
    // Bác sĩ đang gõ số KHÁC số mình đã lưu thì không đè; còn nguyên số đã lưu
    // (= số kê gốc quầy vừa sửa) thì theo số của quầy (C19).
    const nguyenSoCu = !!m.so_luong_ke_goc && d.so_luong === phanSo(m.so_luong_ke_goc);
    if (d.so_luong.trim() !== "" && !d.so_luong_do_thu_ngan && !nguyenSoCu) return d;
    if (d.so_luong === m.so_luong && d.don_vi === m.don_vi && d.so_luong_do_thu_ngan) return d;
    doi = true;
    return {
      ...d,
      so_luong: m.so_luong,
      don_vi: m.don_vi,
      so_luong_do_thu_ngan: true,
      so_luong_ke_goc: m.so_luong_ke_goc ?? null,
    };
  });
  return doi ? ra : null;
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

/** Bỏ dấu + thường — tìm "sieu am" ra "Siêu âm". */
export function boDauTim(s: string): string {
  return s.normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/đ/gi, "d").toLowerCase();
}

/** Tên hiện của một mục danh mục chỉ định (C21, 02/10/2026): TÊN THẬT của bảng
 *  giá làm tên chính; nhãn phiếu giấy cũ thành dòng phụ khi khác — hàm thuần. */
export function tenHienMuc(m: Pick<MucCls, "nhan" | "ten_dich_vu">): { chinh: string; phieuGiay: string | null } {
  const that = (m.ten_dich_vu ?? "").trim();
  if (!that) return { chinh: m.nhan, phieuGiay: null };
  const khac = boDauTim(that) !== boDauTim(m.nhan ?? "");
  return { chinh: that, phieuGiay: khac ? m.nhan : null };
}

/**
 * TÌM trong danh mục chỉ định (01/10/2026 — Tuyền: "không được để dịch vụ nào
 * bị lọt"): gõ "PRP", "NIPT", "liên cầu" ra ngay, kể cả mục nằm trong ngăn gập
 * "Dịch vụ khác trong bảng giá". Kết quả gom theo NHÓM HÀNG (máy chủ gắn; mục
 * phiếu giấy chưa có nhóm hàng thì theo nhóm phiếu), mỗi dịch vụ một lần.
 * Hàm thuần — chỉ lọc chữ, không quyết dịch vụ nào được chỉ định.
 */
export function timDanhMucChiDinh(ds: readonly NhomCls[], tu: string): NhomCls[] {
  const q = boDauTim(tu.trim());
  if (!q) return [];
  const da = new Set<string>();
  const nhom = new Map<string, MucCls[]>();
  for (const n of ds ?? []) {
    if (!n || !Array.isArray(n.muc)) continue;
    const goc = n.nhom.endsWith(HAU_TO_DANH_MUC_PK) ? n.nhom.slice(0, -HAU_TO_DANH_MUC_PK.length) : n.nhom;
    for (const m of n.muc) {
      const khoa = m.service_code ?? `nhan:${m.nhan}`;
      if (da.has(khoa)) continue;
      if (!boDauTim(`${m.nhan} ${m.ten_dich_vu ?? ""} ${m.ma_kiotviet ?? ""} ${m.nhom_hang ?? ""} ${goc}`).includes(q))
        continue;
      da.add(khoa);
      const ten = m.nhom_hang || goc;
      nhom.set(ten, [...(nhom.get(ten) ?? []), m]);
    }
  }
  return [...nhom.entries()].map(([ten, muc]) => ({ nhom: ten, muc }));
}

/** Ngăn "Dịch vụ khác trong bảng giá": gom lại theo nhóm hàng, giữ thứ tự máy chủ. */
export function gomTheoNhomGoc<T extends { nhom_goc: string }>(ds: readonly T[]): [string, T[]][] {
  const m = new Map<string, T[]>();
  for (const x of ds) m.set(x.nhom_goc, [...(m.get(x.nhom_goc) ?? []), x]);
  return [...m.entries()];
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
/** BỐN KHỐI của phiếu bác sĩ chính: gom các mục SẴN CÓ của mẫu JSON, không đổi
 *  `ma` ô nào — phiếu đã lưu vẫn đọc đúng. Mục hành chính luôn nằm trên, ngoài
 *  các khối. Khối 3 còn có thẻ CHỈ ĐỊNH ĐIỀU TRỊ (không thuộc mẫu JSON — shell vẽ
 *  qua `oDieuTri`, đứng đầu khối, đúng chỗ ô "Chẩn đoán và xử lý" cũ). */
export type SoKhoi = 1 | 2 | 3 | 4;
export const KHOI_PHIEU: { so: SoKhoi; ten: string; muc: string[] }[] = [
  { so: 1, ten: "Thông tin cơ bản", muc: ["A", "B"] },
  { so: 2, ten: "Chỉ định cận lâm sàng", muc: ["C"] },
  { so: 3, ten: "Chỉ định điều trị", muc: ["D", "F", "G"] },
  { so: 4, ten: "Đơn thuốc", muc: ["E"] },
];

/** Mục đã BỎ khỏi phiếu mới (Tuyền chốt Q1 08/10: "Chẩn đoán và xử lý" — phiếu
 *  2 ô của thẻ điều trị thay chỗ). Không xoá khỏi mẫu JSON (phiếu cũ vẫn đọc,
 *  bản in vẫn in): lượt có dữ liệu thì hiện CHỈ ĐỌC, lượt trống thì không hiện.
 *  Mở lại = bỏ mã khỏi danh sách này. */
export const MUC_DA_BO: readonly string[] = ["D"];

/** Chia chỉ định của lượt theo chỗ hiện trên hồ sơ khám. ĐIỀU TRỊ theo MỘT định
 *  nghĩa — cờ `dieu_tri` máy chủ trả (dịch vụ mà loại khám nhóm DIEU_TRI trỏ tới)
 *  — và xét TRƯỚC: Ghế điện nằm cả trong danh mục thủ thuật vẫn chỉ ra một thẻ
 *  điều trị; Laser tiền đình không ở danh mục thủ thuật cũng không rơi vào CLS.
 *  Phần còn lại: mã trong danh mục thủ thuật → thủ thuật, khác → CLS. */
export function phanChiDinh(
  ds: readonly ChiDinhVaKetQua[],
  maThuThuat?: ReadonlySet<string>,
): { dieuTri: ChiDinhVaKetQua[]; thuThuat: ChiDinhVaKetQua[]; cls: ChiDinhVaKetQua[] } {
  const ra = { dieuTri: [] as ChiDinhVaKetQua[], thuThuat: [] as ChiDinhVaKetQua[], cls: [] as ChiDinhVaKetQua[] };
  for (const c of ds) {
    if (c.dieu_tri) ra.dieuTri.push(c);
    else if (maThuThuat?.has(c.service_code)) ra.thuThuat.push(c);
    else ra.cls.push(c);
  }
  return ra;
}

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
  // Ô ngày lưu "YYYY-MM-DD" (giá trị của <input type=date>); đọc/in theo kiểu VN.
  const ngay = o.kieu === "ngay" ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(nhap.gia_tri.trim()) : null;
  if (ngay) return `${ngay[3]}/${ngay[2]}/${ngay[1]}`;
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

export const MIME_DICOM = "application/dicom";

/** Tệp DICOM (máy siêu âm xuất thẳng): trình duyệt KHÔNG vẽ được bằng thẻ img —
 *  coi là tài liệu tải về, không phải ảnh (27/09/2026, đợt 3). Rác → false. */
export function laDicom(mime: unknown): boolean {
  return typeof mime === "string" && mime.trim().toLowerCase() === MIME_DICOM;
}

/** Ảnh IN ĐƯỢC của một chỉ định: ảnh trình duyệt vẽ được (không DICOM), đã xác
 *  nhận hợp lệ (hoặc tải ở phòng). */
export function anhInDuoc(d: ChiDinhVaKetQua): KetQuaMotChiDinh[] {
  return d.ket_qua
    .filter(
      (k) =>
        k.loai === "TEP" &&
        k.tep_id &&
        k.loai_tep === "ANH" &&
        !laDicom(k.mime) &&
        (k.xac_nhan_trang_thai ?? "HOP_LE") === "HOP_LE",
    )
    .sort((a, b) => (a.tai_len_luc ?? "").localeCompare(b.tai_len_luc ?? ""));
}

export const NHAN_KET_QUA: Record<ChiDinhVaKetQua["ket_qua_trang_thai"], string> = {
  CO_KET_QUA: "Có kết quả",
  DANG_NHAP: "Đang nhập kết quả",
  CHUA_CO: "Chưa có kết quả",
};

// ---------------------------------------------------------------------------
// Hẹn tái khám — chip chọn nhanh ở mục G (27/09/2026, bản giao diện mẫu)
// ---------------------------------------------------------------------------
/** Ô "Ngày tái khám" của mọi phiếu: `pk_follow_date`, `hmvs_follow_date`… —
 *  CÙNG quy ước máy chủ dùng để sinh nhắc tái khám (`right(key, 12) = '_follow_date'`). */
export function laONgayTaiKham(ma: string): boolean {
  return ma.endsWith("_follow_date");
}

export const HEN_NHANH = [
  { nhan: "1 tuần", ngay: 7, thang: 0 },
  { nhan: "2 tuần", ngay: 14, thang: 0 },
  { nhan: "1 tháng", ngay: 0, thang: 1 },
  { nhan: "3 tháng", ngay: 0, thang: 3 },
] as const;

/**
 * Ngày hẹn = hôm nay (giờ VN, "YYYY-MM-DD" — lấy bằng `vnYmd()`) cộng khoảng.
 * Tháng là tháng LỊCH ("1 tháng" từ 15/09 là 15/10, không phải +30 ngày); ngày
 * không có ở tháng đích thì lùi về ngày cuối tháng (31/01 + 1 tháng = 28 hoặc
 * 29/02). Đầu vào rác → "" (không ném — luật ngày/giờ của CLAUDE.md).
 */
export function ngayHenTaiKham(homNay: string, khoang: { ngay: number; thang: number }): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(homNay.trim());
  if (!m) return "";
  const [nam, thang, ngay] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const goc = new Date(Date.UTC(nam, thang - 1, ngay));
  if (goc.getUTCMonth() !== thang - 1 || goc.getUTCDate() !== ngay) return "";
  const cuoiThangDich = new Date(Date.UTC(nam, thang - 1 + khoang.thang + 1, 0)).getUTCDate();
  const d = new Date(
    Date.UTC(nam, thang - 1 + khoang.thang, Math.min(ngay, cuoiThangDich) + khoang.ngay),
  );
  return d.toISOString().slice(0, 10);
}

/**
 * Tổng tiền PHÒNG KHÁM của các mục đang chọn ở danh mục chỉ định: bỏ mục khách
 * trả trực tiếp cho đối tác (`doi_tac_thu` — cờ máy chủ, 27/09/2026) và mục
 * chưa có giá. Thuần.
 */
export function tongPhongKham(chon: readonly string[], muc: readonly MucCls[]): number {
  const gia = new Map<string, number>();
  for (const m of muc) {
    if (m.service_code && !m.doi_tac_thu && typeof m.gia === "number") gia.set(m.service_code, m.gia);
  }
  return chon.reduce((t, c) => t + (gia.get(c) ?? 0), 0);
}

/** Tên phiếu kết quả khi IN / xem (Tuyền 28/09/2026: "mấy cái loại phiếu tự do
 *  ấy, nhớ đẩy tên phiếu lên chứ đang để chữ tự do nhìn buồn cười"): mẫu nhập
 *  tự do (`KQ_CHUNG`) mang tên DỊCH VỤ — "Kết quả <dịch vụ>"; mẫu riêng giữ tên
 *  mẫu. */
export function tenPhieuKetQua(
  p: { form_id?: string | null; ten: string | null },
  dichVu: string | null | undefined,
): string {
  const tuDo = p.form_id === "KQ_CHUNG" || /tự do/i.test(p.ten ?? "");
  if (tuDo && dichVu) return `Kết quả ${dichVu}`;
  return p.ten ?? (dichVu ? `Kết quả ${dichVu}` : "Phiếu kết quả");
}
