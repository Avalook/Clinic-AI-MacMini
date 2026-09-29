/**
 * Thanh ngày ngang — hàm THUẦN (Tuyền 27/09/2026: "mở rộng khung thời gian tra
 * cứu: xem khách hôm qua, hôm kia, tuần trước…; hiện lịch ra như thanh ngang mà
 * bấm cũng tiện").
 *
 * Mọi ngày là chuỗi `yyyy-mm-dd` theo giờ Việt Nam. Tính bằng UTC trên chuỗi
 * ngày (không qua `new Date()` địa phương) để máy đặt múi giờ nào cũng ra cùng
 * một ngày.
 *
 * LUẬT KHOẢNG là gương của `cua_so_khoang` phía máy chủ (danh_sach_khach_cskh.py):
 * rác → null (không ném), thiếu một đầu → một ngày, ngược → đổi chỗ, dài quá
 * 366 ngày → cắt giữ đầu cuối. Máy chủ vẫn là nơi quyết; đây chỉ để thanh ngày
 * hiện đúng chip đang chọn.
 */

export interface Khoang {
  tu: string;
  den: string;
}

export type MaNhanh =
  | "hom-nay"
  | "hom-qua"
  | "hom-kia"
  | "7-ngay"
  | "tuan-truoc"
  | "30-ngay";

export const NHANH: readonly { ma: MaNhanh; nhan: string }[] = [
  { ma: "hom-nay", nhan: "Hôm nay" },
  { ma: "hom-qua", nhan: "Hôm qua" },
  { ma: "hom-kia", nhan: "Hôm kia" },
  { ma: "7-ngay", nhan: "7 ngày" },
  { ma: "tuan-truoc", nhan: "Tuần trước" },
  { ma: "30-ngay", nhan: "30 ngày" },
];

export const KHOANG_TOI_DA_NGAY = 366;

const NGAY_RE = /^(\d{4})-(\d{2})-(\d{2})/;
const MOT_NGAY = 86_400_000;
const THU = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"] as const;

function msCua(ngay: string): number | null {
  const m = NGAY_RE.exec(ngay);
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const ms = Date.UTC(y, mo - 1, d);
  const kiem = new Date(ms);
  // 2026-02-31 → Date tự lăn sang tháng 3: coi là rác.
  if (kiem.getUTCFullYear() !== y || kiem.getUTCMonth() !== mo - 1 || kiem.getUTCDate() !== d) {
    return null;
  }
  return ms;
}

function chuoiCua(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

/** Ngày hợp lệ `yyyy-mm-dd` (bỏ phần giờ nếu có); rác → null, không ném. */
export function docNgay(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const ms = msCua(v.trim());
  return ms == null ? null : chuoiCua(ms);
}

/** `ngay` + `n` ngày; ngày rác → "". */
export function congNgay(ngay: string, n: number): string {
  const ms = msCua(ngay);
  return ms == null || !Number.isFinite(n) ? "" : chuoiCua(ms + Math.trunc(n) * MOT_NGAY);
}

/** Số ngày từ `a` tới `b` (b − a); rác → NaN. */
function cachNgay(a: string, b: string): number {
  const x = msCua(a);
  const y = msCua(b);
  return x == null || y == null ? Number.NaN : Math.round((y - x) / MOT_NGAY);
}

/** Thứ Hai của tuần chứa `ngay` (tuần bắt đầu thứ Hai, như máy chủ). */
function thuHai(ngay: string): string {
  const ms = msCua(ngay);
  if (ms == null) return "";
  const thu = new Date(ms).getUTCDay(); // 0 = CN
  return congNgay(ngay, -((thu + 6) % 7));
}

/** Khoảng tuỳ chọn đã chuẩn hoá — gương `cua_so_khoang`. */
export function docKhoang(tu: unknown, den: unknown): Khoang | null {
  let a = docNgay(tu);
  let b = docNgay(den);
  if (a == null && b == null) return null;
  a = a ?? b!;
  b = b ?? a;
  if (b < a) [a, b] = [b, a];
  if (cachNgay(a, b) > KHOANG_TOI_DA_NGAY) a = congNgay(b, -KHOANG_TOI_DA_NGAY);
  return { tu: a, den: b };
}

/** Khoảng của một chip bấm nhanh, tính từ `homNay`. `homNay` rác → null. */
export function khoangNhanh(ma: MaNhanh, homNay: string): Khoang | null {
  if (docNgay(homNay) == null) return null;
  switch (ma) {
    case "hom-nay":
      return { tu: homNay, den: homNay };
    case "hom-qua": {
      const d = congNgay(homNay, -1);
      return { tu: d, den: d };
    }
    case "hom-kia": {
      const d = congNgay(homNay, -2);
      return { tu: d, den: d };
    }
    case "7-ngay":
      return { tu: congNgay(homNay, -6), den: homNay };
    case "tuan-truoc": {
      const t2 = congNgay(thuHai(homNay), -7);
      return { tu: t2, den: congNgay(t2, 6) };
    }
    case "30-ngay":
      return { tu: congNgay(homNay, -29), den: homNay };
    default:
      return null;
  }
}

/** Chip nào khớp đúng khoảng này (để tô) — không khớp chip nào → null. */
export function maCuaKhoang(k: Khoang | null, homNay: string): MaNhanh | null {
  if (!k) return null;
  for (const { ma } of NHANH) {
    const x = khoangNhanh(ma, homNay);
    if (x && x.tu === k.tu && x.den === k.den) return ma;
  }
  return null;
}

/** Kỳ cũ của màn (`?period=today|week|month`) đổi ra khoảng — để thanh ngày
 *  tô đúng khi mở bằng đường dẫn cũ. `all`/rác → null. */
export function khoangTuKy(ky: string | null | undefined, homNay: string): Khoang | null {
  if (docNgay(homNay) == null) return null;
  if (ky === "today") return { tu: homNay, den: homNay };
  if (ky === "week") {
    const t2 = thuHai(homNay);
    return { tu: t2, den: congNgay(t2, 6) };
  }
  if (ky === "month") {
    const dau = `${homNay.slice(0, 8)}01`;
    const thangSau = congNgay(dau, 32).slice(0, 8) + "01";
    return { tu: dau, den: congNgay(thangSau, -1) };
  }
  return null;
}

/** "27/09" */
export function ngayNgan(ngay: string): string {
  const d = docNgay(ngay);
  return d ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : "—";
}

/** Nhãn khoảng: "27/09" (một ngày) · "21/09 – 27/09". */
export function nhanKhoang(k: Khoang | null): string {
  if (!k) return "Tất cả";
  return k.tu === k.den ? ngayNgan(k.tu) : `${ngayNgan(k.tu)} – ${ngayNgan(k.den)}`;
}

export interface ONgay {
  ngay: string;
  thu: string;
  so: string;
  homNay: boolean;
}

/** Dải ngày ngang: `truoc` ngày trước hôm nay → `sau` ngày sau. `homNay` rác → []. */
export function daiNgay(homNay: string, truoc: number, sau: number): ONgay[] {
  if (docNgay(homNay) == null) return [];
  const out: ONgay[] = [];
  for (let i = -Math.max(0, truoc); i <= Math.max(0, sau); i++) {
    const ngay = congNgay(homNay, i);
    const ms = msCua(ngay)!;
    out.push({ ngay, thu: THU[new Date(ms).getUTCDay()], so: ngayNgan(ngay), homNay: i === 0 });
  }
  return out;
}

/** Ngày XEM của các màn làm việc (Tuyền 29/09/2026 — Đo sinh hiệu, Bàn khám tư
 *  vấn, Bàn khám, phòng dịch vụ): đọc `?ngay=` trên thanh địa chỉ để F5 không
 *  mất ngày đang chọn. Rác / thiếu / ngày TƯƠNG LAI → hôm nay (không ném). Máy
 *  chủ vẫn tự đọc lại ngày (`doc_ngay_xem`) — đây chỉ để thanh ngày tô đúng. */
export function ngayXemTuUrl(v: unknown, homNay: string): string {
  const ngay = docNgay(v);
  if (ngay == null || docNgay(homNay) == null) return homNay;
  return ngay > homNay ? homNay : ngay;
}
