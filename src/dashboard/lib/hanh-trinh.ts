// Dải hành trình ở đầu phiếu khám (lát 5, 26/09/2026) — phần CHẠY THEO ĐỒNG HỒ.
//
// Mốc (đã xong gì, lúc nào) do máy chủ tính (`phieu_kham/hanh_trinh.py`). Ở đây
// chỉ còn thứ phải đổi theo giây trên trình duyệt: nhãn trên đoạn nối ("chờ 8
// phút", "đang 12 phút") và chữ giờ của từng mốc. Hàm thuần — test bằng node.

import { fmtDayTime, fmtTime } from "./datetime.ts";

export type TrangThaiMoc = "xong" | "dang" | "chua";

export interface LanGui {
  lan: number | null;
  luc: string;
  so: number;
}

export interface MocMayChu {
  ma: string;
  ten: string;
  noi: string;
  bat: string | null;
  ket: string | null;
  trang_thai: TrangThaiMoc;
  hom_truoc?: boolean;
  cac_lan?: LanGui[];
  con_cho?: number;
  /** Sinh hiệu (29/09): giờ các lần ĐO LẠI — `ket` là lần đo đầu. */
  do_lai?: string[];
}

/** Trục trạng thái một chiều của từng chỉ định — máy chủ quyết (`dung_tung_dich_vu`). */
export type TrangThaiDichVu = "CHO_THU" | "CHO_LAM" | "DANG_LAM" | "XONG" | "BO";

/** Một dòng bảng "Từng dịch vụ" (27/09/2026) — thời điểm ISO, null = chưa tới. */
export interface DichVuHanhTrinh {
  id: string | null;
  ten: string;
  lan: number | null;
  noi: string;
  trang_thai: TrangThaiDichVu;
  gui: string;
  thu: string | null;
  bat_dau: string | null;
  xong: string | null;
  /** Khách trả TRỰC TIẾP cho đối tác (27/09/2026): đối tác đã thu chưa.
   *  null/thiếu = phòng khám thu. */
  doi_tac_thu_tien?: "DA_THU" | "CHUA_THU" | null;
}

export interface HanhTrinh {
  dang_o: string;
  moc: MocMayChu[];
  /** Số chỉ định đang ở đối tác (khách không phải có mặt). */
  ngoai_cho: number;
  /** Máy chủ cũ chưa trả → không có bảng. */
  tung_dich_vu?: DichVuHanhTrinh[];
}

export interface Doan {
  nhan: string | null;
  trangThai: TrangThaiMoc;
}

/** 7 → "7 phút"; 65 → "1 giờ 5 phút"; 120 → "2 giờ". */
export function khoang(phut: number): string {
  const p = Math.max(0, Math.floor(phut));
  if (p < 60) return `${p} phút`;
  const g = Math.floor(p / 60);
  return p % 60 ? `${g} giờ ${p % 60} phút` : `${g} giờ`;
}

const phutGiua = (a: string, b: number) => (b - new Date(a).getTime()) / 60_000;

/** Chữ giờ dưới tên mốc — sinh hiệu đo lại thì thêm "· đo lại 10:45" (giờ
 *  thật, không gộp vào thời gian làm; 29/09/2026). */
export function gioMoc(m: MocMayChu): string {
  const chinh = gioMocChinh(m);
  const doLai = (m.do_lai ?? []).filter(Boolean).map((t) => fmtTime(t));
  if (!chinh || doLai.length === 0) return chinh;
  return `${chinh} · đo lại ${doLai.join(", ")}`;
}

function gioMocChinh(m: MocMayChu): string {
  if (m.cac_lan && m.cac_lan.length > 0) {
    return m.cac_lan
      .map((x) => `${x.lan == null ? "Mang sang" : `Lần ${x.lan}`} ${fmtTime(x.luc)}`)
      .join(" · ");
  }
  if (!m.bat) return "";
  if (m.hom_truoc) return fmtDayTime(m.bat);
  if (m.ket && m.ket !== m.bat) {
    const a = fmtTime(m.bat);
    const b = fmtTime(m.ket);
    return a === b ? a : `${a} → ${b}`;
  }
  return fmtTime(m.bat);
}

/**
 * Nhãn đoạn nối sau mốc thứ i: khoảng CHỜ giữa lúc mốc này xong (hoặc bắt đầu,
 * nếu mốc chỉ có một thời điểm) và lúc mốc sau bắt đầu. Đoạn sau mốc gần nhất
 * đã bắt đầu là đoạn ĐANG chạy: "đang …" nếu mốc ấy chưa xong, "chờ …" nếu đã
 * xong mà mốc sau chưa tới.
 */
export function doanNoi(moc: MocMayChu[], bayGio: number): Doan[] {
  const cuoi = moc.reduce((k, m, i) => (m.bat != null ? i : k), -1);
  return moc.slice(0, -1).map((m, i) => {
    const sau = moc[i + 1];
    if (m.hom_truoc) return { nhan: "hôm trước", trangThai: "xong" };
    if (m.bat != null && sau.bat != null) {
      const tu = m.ket ?? m.bat;
      const p = phutGiua(tu, new Date(sau.bat).getTime());
      return { nhan: p >= 1 ? khoang(p) : null, trangThai: "xong" };
    }
    if (i === cuoi && m.trang_thai !== "chua") {
      const tu = m.ket ?? m.bat!;
      const p = phutGiua(tu, bayGio);
      if (p < 1) return { nhan: "vừa xong", trangThai: "dang" };
      return {
        nhan: m.ket ? `chờ ${khoang(p)}` : `đang ${khoang(p)}`,
        trangThai: "dang",
      };
    }
    return { nhan: null, trangThai: m.trang_thai === "xong" ? "xong" : "chua" };
  });
}

export interface PhutDichVu {
  /** "Gửi 08:45 · Thu 08:50 · Bắt đầu 09:00 · Xong 09:20" — chỉ mốc đã có. */
  moc: string;
  /** Phút CHỜ: từ lúc thu (chưa thu thì lúc gửi) tới lúc bắt đầu — hoặc tới
   *  bây giờ nếu còn đang chờ. null = không nói (khách bỏ; xong mà không có giờ bắt đầu). */
  cho: number | null;
  /** Phút LÀM: bắt đầu → xong, hoặc → bây giờ nếu đang làm. */
  lam: number | null;
  /** Tổng: gửi → xong, hoặc → bây giờ nếu chưa xong. null = khách bỏ. */
  tong: number | null;
  /** Còn chạy theo đồng hồ (chưa xong). */
  dangChay: boolean;
}

/**
 * Số phút của một dòng "Từng dịch vụ": chờ → làm → tổng. Dòng chưa xong tính
 * tới `bayGio` để nhích theo phút như nhãn trên dải mốc. Không bao giờ âm
 * (giờ máy lệch vài giây vẫn ra 0).
 */
export function phutDichVu(d: DichVuHanhTrinh, bayGio: number): PhutDichVu {
  const cacMoc: [string, string | null][] = [
    ["Gửi", d.gui],
    ["Thu", d.thu],
    ["Bắt đầu", d.bat_dau],
    ["Xong", d.xong],
  ];
  const moc = cacMoc
    .flatMap(([a, v]) => (v ? [`${a} ${fmtTime(v)}`] : []))
    .join(" · ");
  if (d.trang_thai === "BO") return { moc, cho: null, lam: null, tong: null, dangChay: false };
  const ms = (v: string) => new Date(v).getTime();
  const phut = (a: number, b: number) => Math.max(0, Math.floor((b - a) / 60_000));
  const xong = d.xong ? ms(d.xong) : null;
  const cuoi = xong ?? bayGio;
  const tuCho = ms(d.thu ?? d.gui);
  const batDau = d.bat_dau ? ms(d.bat_dau) : null;
  const cho = batDau != null ? phut(tuCho, batDau) : xong == null ? phut(tuCho, bayGio) : null;
  const lam = batDau != null ? phut(batDau, cuoi) : null;
  return { moc, cho, lam, tong: phut(ms(d.gui), cuoi), dangChay: xong == null };
}
