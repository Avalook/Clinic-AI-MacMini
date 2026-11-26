// Cách dùng có cấu trúc (PR E, 26/11/2026) — HÌNH dữ liệu + chữ hiển thị. Mọi phép
// tính (liều/ngày, số ngày, ngày hết, gợi ý số lượng, câu in) ở máy chủ:
// `src/clinicai/services/thuoc/cach_dung.py`, cửa `POST /api/v1/thuoc/cach-dung/tinh`.

export type KieuDung = "ngay" | "tuan" | "thang" | "cach_ngay" | "chu_ky" | "chu";

/** Cùng hình `CachDung` ở máy chủ. Số có thể về dạng chuỗi ("0.5") — đọc bằng `so`. */
export interface CachDungCT {
  kieu: KieuDung;
  moi_lan?: number | string | null;
  khoang_lan?: [number | string, number | string] | null;
  so_lan?: number | null;
  khoang_so_lan?: [number, number] | null;
  tu_ngay?: number | null;
  den_ngay?: number | null;
  trong_ngay?: number | null;
  don_vi_lieu?: string;
  thoi_diem?: string;
}

export interface KetQuaCachDung {
  tinh_duoc: boolean;
  ly_do: string | null;
  cau: string;
  lieu_ngay: string | null;
  so_ngay: number | null;
  ngay_het: string | null;
  so_lieu_can: string | null;
  goi_y_so_luong: number | null;
  uoc_tinh: { kinh_toi: string; bat_dau: string; het: string } | null;
  /** Thuốc dùng theo chu kỳ kinh — màn hiện khung "Tính ngày uống theo kỳ kinh". */
  theo_chu_ky?: boolean;
  /** Mốc "uống từ ngày thứ … đến ngày thứ …" đang dùng (câu cách dùng hoặc bác sĩ sửa). */
  tu_ngay?: number | null;
  den_ngay?: number | null;
}

export interface KetQuaTinh {
  ngay_ke: string;
  kinh: { kinh_lan_cuoi: string | null; chu_ky: string | null; nguon: string | null; doc_duoc: boolean };
  dong: KetQuaCachDung[];
}

export const NHAN_KIEU: [KieuDung, string][] = [
  ["ngay", "Mỗi ngày"],
  ["tuan", "Mỗi tuần"],
  ["cach_ngay", "Cách ngày"],
  ["chu_ky", "Theo chu kỳ kinh"],
  ["chu", "Chỉ ghi chữ"],
];

/** "0.5" / 0.5 / null → số hoặc null. */
export function so(x: number | string | null | undefined): number | null {
  if (x == null || x === "") return null;
  const n = Number(String(x).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

/** Các số chọn được trong khoảng (bước 0,5 nếu khoảng có số lẻ, không thì 1). */
export function soTrongKhoang(k: [number | string, number | string]): number[] {
  const a = so(k[0]) ?? 0;
  const b = so(k[1]) ?? 0;
  const buoc = Number.isInteger(a) && Number.isInteger(b) ? 1 : 0.5;
  const ra: number[] = [];
  for (let x = a; x <= b + 1e-9 && ra.length < 50; x += buoc) ra.push(Math.round(x * 100) / 100);
  return ra;
}

/** "2026-12-25" → "25/12/2026" (chỉ đổi cách viết, không tính). */
export function ngayVn(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

/** Dòng kết quả cho bác sĩ đọc — ghép chữ từ số máy chủ đã tính. */
export function dongKetQua(k: KetQuaCachDung): string {
  if (!k.tinh_duoc) return k.ly_do ?? "";
  if (k.uoc_tinh) {
    const u = k.uoc_tinh;
    return `Uống từ ${ngayVn(u.bat_dau)} đến ${ngayVn(u.het)} (${k.so_ngay} ngày, kỳ kinh tính từ ${ngayVn(u.kinh_toi)})`;
  }
  if (!k.ngay_het) return `${k.so_ngay} ngày theo chu kỳ kinh — nhập ngày bắt đầu kỳ kinh để ra ngày uống cụ thể.`;
  return `${k.so_ngay} ngày → hết ${ngayVn(k.ngay_het)}`;
}
