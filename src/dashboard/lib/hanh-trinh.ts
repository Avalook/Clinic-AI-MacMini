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
}

export interface HanhTrinh {
  dang_o: string;
  moc: MocMayChu[];
  /** Số chỉ định đang ở đối tác (khách không phải có mặt). */
  ngoai_cho: number;
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

/** Chữ giờ dưới tên mốc. */
export function gioMoc(m: MocMayChu): string {
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
