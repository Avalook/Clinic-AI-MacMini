"use client";

// Khung "Tính ngày uống theo kỳ kinh" dưới cách dùng của thuốc dùng theo chu kỳ kinh
// (Tuyền 26/11). ĐÓNG mặc định: không đưa ra ngày nào (không bịa). MỞ: bác sĩ nhập/sửa
// ngày bắt đầu kỳ kinh gần nhất, độ dài chu kỳ và "uống từ ngày thứ … đến ngày thứ …"
// (điền sẵn từ câu cách dùng, sửa được — không fix cứng). Ngày 1 = ngày đầu ra máu kinh;
// chu kỳ trung bình 28 ngày, bình thường 21–35 (Cleveland Clinic, Merck Manuals).

import ONhap from "@/components/ui/ONhap";

export type Kinh = { kinh_lan_cuoi: string; chu_ky: string };
export type Moc = { tu_ngay: number; den_ngay: number };

/** "2026-11-24" (ô ngày) ↔ "24/11/2026" (máy chủ đọc kiểu Việt Nam). */
const sangVn = (iso: string) => (iso ? iso.split("-").reverse().join("/") : "");
const sangIso = (vn: string) => {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(vn.trim());
  return m ? `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}` : "";
};

/** Ngày khám là ngày thứ mấy của kỳ kinh (1 = ngày đầu ra máu). */
export function ngayThuCuaKy(kinhVn: string, ckChu: string, ngayKeIso: string): number | null {
  const iso = sangIso(kinhVn);
  if (!iso || !ngayKeIso) return null;
  const ck = Number(ckChu) || 28;
  const lech = Math.floor((Date.parse(ngayKeIso.slice(0, 10)) - Date.parse(iso)) / 86_400_000);
  return lech < 0 ? null : (lech % ck) + 1;
}

const O = "block text-meta text-ink-muted";

export default function KyKinh({
  mo,
  onMo,
  kinh,
  onKinh,
  moc,
  onMoc,
  ngayKe,
  ketQua,
  chiDoc,
}: {
  mo: boolean;
  onMo: (mo: boolean) => void;
  kinh: Kinh;
  onKinh: (k: Kinh) => void;
  moc: Moc | null;
  onMoc: (m: Moc) => void;
  ngayKe: string | null;
  ketQua: string | null;
  chiDoc: boolean;
}) {
  const thu = mo ? ngayThuCuaKy(kinh.kinh_lan_cuoi, kinh.chu_ky, ngayKe ?? "") : null;
  const so = (v: string) => Math.max(1, Math.min(60, Number(v) || 1));
  return (
    <div className="rounded-control border border-brand-600/30 bg-brand-50 p-2 sm:col-span-12">
      <button
        type="button"
        className="text-body font-bold text-brand-700"
        aria-expanded={mo}
        onClick={() => onMo(!mo)}
      >
        {mo ? "▾" : "▸"} Tính ngày uống theo kỳ kinh
      </button>
      {mo ? (
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-6">
          <label className={`${O} col-span-2`}>
            Ngày bắt đầu kỳ kinh gần nhất (ngày đầu ra máu)
            <ONhap
              type="date"
              className="w-full"
              value={sangIso(kinh.kinh_lan_cuoi)}
              disabled={chiDoc}
              onChange={(e) => onKinh({ ...kinh, kinh_lan_cuoi: sangVn(e.target.value) })}
            />
          </label>
          <label className={O}>
            Chu kỳ (ngày)
            <ONhap
              className="w-full"
              inputMode="numeric"
              value={kinh.chu_ky}
              placeholder="28"
              disabled={chiDoc}
              onChange={(e) => onKinh({ ...kinh, chu_ky: e.target.value })}
            />
          </label>
          <label className={O}>
            Uống từ ngày thứ
            <ONhap
              className="w-full"
              inputMode="numeric"
              value={moc ? String(moc.tu_ngay) : ""}
              disabled={chiDoc}
              onChange={(e) => onMoc({ tu_ngay: so(e.target.value), den_ngay: moc?.den_ngay ?? 28 })}
            />
          </label>
          <label className={O}>
            đến ngày thứ
            <ONhap
              className="w-full"
              inputMode="numeric"
              value={moc ? String(moc.den_ngay) : ""}
              disabled={chiDoc}
              onChange={(e) => onMoc({ tu_ngay: moc?.tu_ngay ?? 1, den_ngay: so(e.target.value) })}
            />
          </label>
          <p className="col-span-2 self-end text-meta text-ink-muted sm:col-span-1">
            Chu kỳ trống = 28 ngày.
          </p>
          {thu ? (
            <p className="col-span-2 text-body font-semibold text-ink sm:col-span-6">
              Hôm nay (ngày khám) là ngày thứ {thu} của kỳ kinh.
            </p>
          ) : null}
          {ketQua ? (
            <p className="col-span-2 text-body font-semibold text-success sm:col-span-6" role="status">
              {ketQua}
            </p>
          ) : (
            <p className="col-span-2 text-meta text-ink-muted sm:col-span-6">
              Nhập ngày bắt đầu kỳ kinh để ra ngày uống cụ thể.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
