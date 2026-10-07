// HÀNH TRÌNH KHÁCH (Tuyền chốt 29/09/2026) — phần CHẠY THEO ĐỒNG HỒ và chữ.
//
// Máy chủ quyết mọi thứ (`hanh_trinh_khach_service.py`): khách đang ở phòng
// nào, đang chờ phòng nào, STT, từng bước xong / đang / chờ, giờ vào hàng /
// bắt đầu / xong. Ở đây chỉ còn: đổi thời điểm thành "chờ 12′", "làm 6′" theo
// đồng hồ trình duyệt, và ghép câu hiển thị. Hàm thuần — test bằng node.

import { fmtTime } from "./datetime.ts";

/** Trạng thái một bước / một đoạn thanh. `khong` = lúc về vẫn chưa làm. */
export type TrangThaiBuoc = "xong" | "dang" | "cho" | "doi_tac" | "chua" | "khong";

/** Trạng thái một thẻ dịch vụ (máy chủ quyết). */
export type TrangThaiThe = "XONG" | "DANG_LAM" | "CHO_LAM" | "CHO_THU" | "DOI_TAC" | "BO";

export type TrangThaiDangO = "DANG_O" | "DANG_CHO" | "DANG_GOI" | "DA_VE" | "BO_VE" | "O_QUAY";

export interface DangO {
  trang_thai: TrangThaiDangO;
  /** "Đang ở" / "Đang chờ" / "Đã về" / "Bỏ về" — máy chủ viết. */
  nhan: string;
  /** Tên PHÒNG thật. */
  noi: string;
  tu_luc: string | null;
  stt: number | null;
  /** Lượt hồ sơ cũ chuyển từ Notion: chỉ có ngày — máy chủ đã bỏ mọi giờ. */
  ho_so_cu?: boolean;
}

export interface HanhTrinhGon extends DangO {
  /** Giờ các lần ĐO LẠI sinh hiệu (29/09) — hiện rõ ở dòng gọn. */
  do_lai?: string[];
  /** Dịch vụ LÀM LẠI: tên + số lần (29/09). */
  lam_lai?: { ten: string; lan: number }[];
  /** Tên dịch vụ làm thêm tại quầy (01/10/2026). Máy chủ cũ chưa trả → không có. */
  lam_them?: string[];
  xong_buoi: boolean;
  doan: TrangThaiBuoc[];
  dv_xong: number;
  dv_tong: number;
  con_cho: string[];
}

/** Một LẦN LÀM của một dịch vụ (làm lại = lần 2, 3…) — máy chủ trả. */
export interface LanLam {
  so: number;
  trang_thai: string | null;
  vao: string | null;
  bat_dau: string | null;
  xong: string | null;
  /** Lần bị dừng giữa chừng: giờ dừng. */
  dung: string | null;
}

export interface TheDichVu {
  id: string | null;
  ten: string;
  noi: string;
  doi_tac: boolean;
  trang_thai: TrangThaiThe;
  vao: string | null;
  bat_dau: string | null;
  xong: string | null;
  thu: string | null;
  lay_mau: string | null;
  stt: number | null;
  so_truoc: number | null;
  /** Số lần làm (≥ 2 = làm lại). Máy chủ cũ chưa trả → 1. */
  so_lan?: number;
  /** Mọi lần làm khi LÀM LẠI (lần 1 vẫn giữ); một lần → rỗng. */
  lan?: LanLam[];
  /** Làm thêm tại quầy (01/10/2026): "Làm thêm tại quầy tiếp đón"; null = bác
   *  sĩ chỉ định. Máy chủ cũ chưa trả → không có. */
  lam_them?: string | null;
  /** Làm thêm tại quầy đã đóng: người đóng (Hoàn tất kết quả ở quầy). */
  xong_boi?: string | null;
}

export interface BuocHanhTrinh {
  ma: string;
  ten: string;
  trang_thai: TrangThaiBuoc;
  noi: string;
  ai: string | null;
  vao: string | null;
  bat_dau: string | null;
  xong: string | null;
  ghi_chu: string | null;
  dich_vu: TheDichVu[] | null;
  /** Bước CHƯA xảy ra (chữ giữ chỗ) — xám "dự kiến", không giờ. */
  du_kien?: boolean;
  /** Bước Khám của lượt Điều trị / Khác chưa qua bàn khám (07/10/2026) — mờ
   *  "tuỳ chọn", không phải việc còn thiếu. Máy chủ cũ chưa trả → không có. */
  tuy_chon?: boolean;
  /** Chỗ là chữ giữ chỗ ("Bàn khám", chưa biết phòng thật). */
  noi_du_kien?: boolean;
  /** Sinh hiệu: giờ các lần đo lại + mọi lần đo kèm người đo. */
  do_lai?: string[];
  lan_do?: { luc: string; ai: string | null }[];
  /** Bước Khám: "chỉ định N dịch vụ · thu tiền HH:MM (người thu)". */
  so_chi_dinh?: number;
  thu_luc?: string | null;
  nguoi_thu?: string | null;
  cho_thu?: number;
  /** Bước Khám đang KHÁM LẠI (đã hoàn tác "Khám xong") — máy chủ quyết. */
  kham_lai?: boolean;
  mo_lai_luc?: string | null;
  /** Câu máy chủ viết: "Dịch vụ khám: <tên> · <giá>" hoặc "Loại khám <tên> ·
   *  0đ (chưa chọn dịch vụ khám con)". */
  dich_vu_kham?: string | null;
}

export interface TiepTheo {
  noi: string;
  stt: number | null;
  so_nguoi_cho: number | null;
  ghi_chu: string | null;
  /** Chưa có chỗ chờ thật / chưa biết phòng — xám "dự kiến". */
  du_kien?: boolean;
}

export interface HanhTrinhKhach {
  visit_id: string;
  gon: HanhTrinhGon;
  dang_o: DangO;
  tiep_theo: TiepTheo[];
  buoc: BuocHanhTrinh[];
  /** Lịch sử xếp / đổi phòng theo mã chỉ định (29/09/2026) — câu máy chủ viết. */
  lich_su_phong?: Record<string, DongLichSuPhong[]>;
}

export interface DongLichSuPhong {
  luc: string | null;
  nguon: string | null;
  ten_nguon: string;
  ai: string | null;
  tu_phong: string | null;
  den_phong: string | null;
  ly_do: string | null;
  /** "Trưởng ca chuyển phòng khi đang làm A → B: máy hỏng". */
  cau: string;
}

function ms(v: string | null | undefined): number | null {
  if (!v) return null;
  const t = Date.parse(v);
  return Number.isFinite(t) ? t : null;
}

/** Số phút từ `tu` tới `den` (thời điểm ISO hoặc ms). Rác / thiếu → null; không bao giờ âm. */
export function phut(tu: string | null | undefined, den: string | number | null | undefined): number | null {
  const a = ms(tu);
  const b = typeof den === "number" ? (Number.isFinite(den) ? den : null) : ms(den);
  if (a == null || b == null) return null;
  return Math.max(0, Math.floor((b - a) / 60_000));
}

/** "HH:MM" — rỗng khi thiếu / rác. */
export function gio(v: string | null | undefined): string {
  return ms(v) == null ? "" : fmtTime(v as string);
}

/** Chip của dòng gọn: "đang làm từ 10:58 · 6′" | "chờ 12′ · STT 2" | "xong buổi". */
export function chipGon(
  g: DangO,
  bayGio: number,
): { nhan: string; tone: "run" | "warning" | "success" | "neutral" } | null {
  const p = phut(g.tu_luc, bayGio);
  switch (g.trang_thai) {
    case "DANG_O":
      return {
        nhan: [g.tu_luc ? `đang làm từ ${gio(g.tu_luc)}` : "đang làm", p != null ? `${p}′` : null]
          .filter(Boolean)
          .join(" · "),
        tone: "run",
      };
    case "DANG_CHO":
    case "DANG_GOI":
      return {
        nhan: [
          g.trang_thai === "DANG_GOI" ? "đang gọi vào" : null,
          p != null ? `chờ ${p}′` : "đang chờ",
          g.stt != null ? `STT ${g.stt}` : null,
        ]
          .filter(Boolean)
          .join(" · "),
        tone: "warning",
      };
    case "DA_VE":
      return { nhan: "xong buổi", tone: "success" };
    case "BO_VE":
      return { nhan: "bỏ về giữa chừng", tone: "neutral" };
    default:
      return null;
  }
}

/** Tên chỗ ở dòng gọn — đã về thì "Check-out 11:20"; hồ sơ cũ không có giờ. */
export function noiGon(g: DangO): string {
  if (g.ho_so_cu) return "Hồ sơ cũ · không rõ giờ";
  if (g.trang_thai === "DA_VE") return g.tu_luc ? `Check-out ${gio(g.tu_luc)}` : "Check-out";
  return g.noi;
}

/** Dòng nhỏ dưới thanh: "2/3 dịch vụ xong · còn chờ: Lấy mẫu · KQ đối tác ·
 *  sinh hiệu đo lại 10:45 · làm lại: Siêu âm (lần 2)". */
export function dongPhuGon(g: HanhTrinhGon): string {
  const ra: string[] = [];
  if (g.dv_tong > 0) ra.push(`${g.dv_xong}/${g.dv_tong} dịch vụ xong`);
  if (g.con_cho.length > 0) ra.push(`còn chờ: ${g.con_cho.join(" · ")}`);
  const doLai = (g.do_lai ?? []).map(gio).filter(Boolean);
  if (doLai.length > 0) ra.push(`sinh hiệu đo lại ${doLai.join(", ")}`);
  const lamLai = g.lam_lai ?? [];
  if (lamLai.length > 0) {
    ra.push(`làm lại: ${lamLai.map((x) => `${x.ten} (lần ${x.lan})`).join(", ")}`);
  }
  const lamThem = g.lam_them ?? [];
  if (lamThem.length > 0) ra.push(`làm thêm tại quầy: ${lamThem.join(", ")}`);
  return ra.join(" · ");
}

/** Sinh hiệu đo nhiều lần: "Đo lần 1 10:33 (Lan) · đo lại 10:45 (Mai)".
 *  Một lần (hoặc máy chủ cũ) → rỗng: giờ chính của bước đã đủ. */
export function dongDoSinhHieu(b: Pick<BuocHanhTrinh, "lan_do">): string {
  const ds = (b.lan_do ?? []).filter((x) => gio(x.luc));
  if (ds.length < 2) return "";
  return ds
    .map((x, i) => `${i === 0 ? "Đo lần 1" : "đo lại"} ${gio(x.luc)}${x.ai ? ` (${x.ai})` : ""}`)
    .join(" · ");
}

/** Một dòng lần làm: "Lần 1 · vào 10:55 · chờ 5′ · bắt đầu 11:00 · làm 5′ ·
 *  dừng 11:05". Lần đang chờ làm lại: "Lần 2 · vào 11:06 · đang chờ 3′". */
export function dongLanLam(l: LanLam, bayGio: number, dungDongHo = false): string {
  const ket = l.xong ?? l.dung;
  let tg = thoiGian({ vao: l.vao, bat_dau: l.bat_dau, xong: ket }, bayGio, dungDongHo);
  if (!l.xong && l.dung) tg = tg.replace(/xong (\d)/, "dừng $1");
  return [`Lần ${l.so}`, tg].filter(Boolean).join(" · ");
}

/**
 * Giờ của một bước / một thẻ: "vào 10:57 · chờ 5′ · bắt đầu 11:02 · làm 3′ ·
 * xong 11:05". Chỉ ghép mốc đã có; đoạn còn chạy (đang chờ / đang làm) tính
 * tới `bayGio` — trừ khi `dungDongHo` (khách đã về: đồng hồ dừng).
 */
export function thoiGian(
  x: { vao: string | null; bat_dau: string | null; xong: string | null },
  bayGio: number,
  dungDongHo = false,
): string {
  // Giờ rác coi như chưa có — không in "vào " trống.
  const sach = (v: string | null) => (ms(v) == null ? null : v);
  const vao = sach(x.vao);
  const bat = sach(x.bat_dau);
  const xong = sach(x.xong);
  // Mốc một thời điểm (check-in, check-out): chỉ một giờ.
  if (bat && xong && bat === xong && !vao) return gio(bat);
  const ra: string[] = [];
  if (vao) ra.push(`vào ${gio(vao)}`);
  if (vao && bat) {
    const p = phut(vao, bat);
    if (p != null) ra.push(`chờ ${p}′`);
  } else if (vao && !bat && !xong && !dungDongHo) {
    const p = phut(vao, bayGio);
    if (p != null) ra.push(`đang chờ ${p}′`);
  }
  if (bat) ra.push(`bắt đầu ${gio(bat)}`);
  if (bat && xong) {
    const p = phut(bat, xong);
    if (p != null) ra.push(`làm ${p}′`);
  } else if (bat && !dungDongHo) {
    const p = phut(bat, bayGio);
    if (p != null) ra.push(`đang làm ${p}′`);
  }
  if (xong) ra.push(`xong ${gio(xong)}`);
  return ra.join(" · ");
}

/** Ghi chú bước Khám: "Chỉ định 3 dịch vụ · thu tiền 10:56 (Vũ Thu Hà)". */
export function ghiChuKham(b: BuocHanhTrinh): string {
  const ra: string[] = [];
  if (b.so_chi_dinh) ra.push(`Chỉ định ${b.so_chi_dinh} dịch vụ`);
  if (b.thu_luc) ra.push(`thu tiền ${gio(b.thu_luc)}${b.nguoi_thu ? ` (${b.nguoi_thu})` : ""}`);
  else if (b.cho_thu) ra.push(`chờ thu tiền ${b.cho_thu} dịch vụ`);
  return ra.join(" · ");
}

/** Dòng trạng thái của một thẻ dịch vụ: "Xong 11:05" / "Đang làm 6′" / … */
export function nhanThe(t: TheDichVu, bayGio: number, dungDongHo = false): string {
  switch (t.trang_thai) {
    case "XONG":
      return t.xong ? `Xong ${gio(t.xong)}` : "Xong";
    case "DANG_LAM": {
      const p = dungDongHo ? null : phut(t.bat_dau, bayGio);
      return p != null ? `Đang làm ${p}′` : "Đang làm";
    }
    case "DOI_TAC":
      return "Chờ kết quả đối tác";
    case "CHO_THU":
      return "Chờ thu tiền";
    case "CHO_LAM":
      return t.stt != null ? `Chờ làm · STT ${t.stt}` : "Chờ làm";
    default:
      return "Khách không làm";
  }
}

/** Số dịch vụ xong trên tổng (không tính khách bỏ) — nhãn đếm bước "Làm dịch vụ". */
export function demThe(ds: TheDichVu[]): string {
  const lam = ds.filter((t) => t.trang_thai !== "BO");
  return `${lam.filter((t) => t.trang_thai === "XONG").length}/${lam.length} xong`;
}
