"use client";

// Kế toán (G5a, 14/10/2026): thống kê THEO HÀNG HOÁ — một dòng một mặt hàng trong
// kỳ (mã, tên, ĐVT, số lượng, tiền trước / sau giảm). Máy chủ gom và tính; màn
// chỉ chọn phạm vi, xem nhanh và tải Excel. Cột thuế suất / tiền thuế để trống
// cho tới khi kế toán đặt thuế (gói sau).

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { buttonClass } from "@/components/ui/Button";
import ThanhTab from "@/components/ui/ThanhTab";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";
import LichKhoangNgay from "@/components/ui/LichKhoangNgay";
import { todayVn } from "@/lib/roster";
import { khoangNhanh, type Khoang } from "@/lib/thanh-ngay";
import { INPUT } from "../form-ui";
import { tien } from "../hoa-don/types";
import ThueSuat from "./ThueSuat";
import { tenThueSuat } from "./thue-suat";

type Hang = {
  nhom: string; ma: string; ten: string; dvt: string; so_luong: number;
  tien_truoc_giam: number; giam_gia: number; tien_sau_giam: number;
  thue_suat: string | null; tien_thue: number | null;
};
type Data = {
  tu: string; den: string; so_hoa_don: number; hang_hoa: Hang[]; so_mat_hang: number;
  tong_truoc_giam: number; tong_giam_gia: number; tong_sau_giam: number;
  /** Số dòng hàng chưa có thuế suất + tổng thuế đã tách — máy chủ tính. */
  dong_chua_thue: number; tong_thue: number;
};

const TEN_NHOM: Record<string, string> = { DICH_VU: "Dịch vụ", THUOC: "Thuốc", VAT_TU: "Vật tư" };

function OLoc({ ten, children }: { ten: string; children: ReactNode }) {
  return (
    <label className="min-w-0 space-y-1 text-meta text-ink-muted">
      <span className="block">{ten}</span>
      {children}
    </label>
  );
}

const TAB = [
  { ma: "hang_hoa", nhan: "Theo hàng hoá" },
  { ma: "thue", nhan: "Thuế suất" },
] as const;

export default function KeToan({ coSo }: { coSo: CoSo[] }) {
  const [tab, setTab] = useState<(typeof TAB)[number]["ma"]>("hang_hoa");
  const homNay = todayVn();
  const [khoang, setKhoang] = useState<Khoang>({ tu: homNay, den: homNay });
  const [loai, setLoai] = useState("");
  const [coSoChon, setCoSoChon] = useState("");
  const [data, setData] = useState<Data | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);
  const chuoi = new URLSearchParams({ tu: khoang.tu, den: khoang.den, loai, co_so: coSoChon }).toString();

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setDangTai(true); setLoi(null);
      try {
        const r = await fetch(`/api/theo-hang-hoa?${chuoi}`, { cache: "no-store", signal: controller.signal });
        const d = await r.json();
        if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được thống kê trong phạm vi đã chọn.");
        if (!controller.signal.aborted) setData(d);
      } catch (e) {
        if (!controller.signal.aborted) { setData(null); setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
      } finally { if (!controller.signal.aborted) setDangTai(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [chuoi]);

  const ds = data?.hang_hoa ?? [];
  const coHang = ds.length > 0;

  return (
    <div className="min-w-0 space-y-4">
      <ThanhTab muc={TAB} chon={tab} onChon={setTab} nhan="Kế toán" />
      {tab === "thue" ? <ThueSuat /> : null}
      <div className={tab === "thue" ? "hidden" : "min-w-0 space-y-4"}>
      <div className="flex flex-wrap items-center gap-2 text-body">
        <span className="rounded-chip bg-info-bg px-3 py-1 text-meta font-semibold text-info">Theo hàng hoá</span>
        <Link href="/xuat-hoa-don" className="rounded-chip px-3 py-1 text-meta text-ink-muted ring-1 ring-hairline hover:text-ink">Xuất hoá đơn →</Link>
        <Link href="/hoa-don" className="rounded-chip px-3 py-1 text-meta text-ink-muted ring-1 ring-hairline hover:text-ink">Danh sách hoá đơn →</Link>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1.3fr_1fr_1fr_1fr]">
        <OLoc ten="Ngày thu">
          <div className="[&>div>button]:h-10 [&>div>button]:w-full">
            <LichKhoangNgay
              khoang={khoang}
              homNay={homNay}
              nhan="Khoảng ngày"
              dangTai={dangTai}
              onChon={k => setKhoang(k ?? khoangNhanh("30-ngay", homNay) ?? { tu: homNay, den: homNay })}
            />
          </div>
        </OLoc>
        <OLoc ten="Loại phiếu thu">
          <select aria-label="Loại phiếu thu" className={`${INPUT} w-full`} value={loai} onChange={e => setLoai(e.target.value)}>
            <option value="">Dịch vụ và thuốc</option>
            <option value="dich_vu">Dịch vụ</option>
            <option value="thuoc">Thuốc</option>
          </select>
        </OLoc>
        <OLoc ten="Cơ sở">
          <ChonCoSoO coSo={coSo} dangChon={coSoChon} onChon={setCoSoChon} className="w-full" />
        </OLoc>
        <div className="flex items-end">
          {coHang ? (
            <a href={`/api/theo-hang-hoa?${chuoi}&xuat=xlsx`} className={`${buttonClass("primary", "md")} w-full justify-center`}>
              Tải file Excel ({data?.so_mat_hang} mặt hàng)
            </a>
          ) : (
            <button type="button" disabled className={`${buttonClass("primary", "md")} w-full justify-center`}>Tải file Excel</button>
          )}
        </div>
      </div>

      {loi ? <p role="alert" className="rounded-control bg-danger-bg p-3 text-body text-danger">{loi}</p> : null}
      {dangTai && !data ? <p role="status" className="text-body text-ink-muted">Đang tải thống kê…</p> : null}

      {data ? (
        <>
          <dl className="grid grid-cols-2 gap-4 rounded-card bg-surface p-4 ring-1 ring-hairline sm:grid-cols-5">
            <div><dt className="text-meta text-ink-muted">Số mặt hàng</dt><dd className="tabular-nums text-emph font-semibold text-ink">{data.so_mat_hang}</dd></div>
            <div><dt className="text-meta text-ink-muted">Trước giảm</dt><dd className="tabular-nums text-emph font-semibold text-ink">{tien(data.tong_truoc_giam)}</dd></div>
            <div><dt className="text-meta text-ink-muted">Giảm giá</dt><dd className="tabular-nums text-emph font-semibold text-ink">{tien(data.tong_giam_gia)}</dd></div>
            <div><dt className="text-meta text-ink-muted">Sau giảm (thực thu)</dt><dd className="tabular-nums text-emph font-semibold text-ink">{tien(data.tong_sau_giam)}</dd></div>
            <div><dt className="text-meta text-ink-muted">Tiền thuế (đã tách)</dt><dd className="tabular-nums text-emph font-semibold text-ink">{tien(data.tong_thue)}</dd></div>
          </dl>
          {data.dong_chua_thue > 0 ? (
            <p role="status" className="rounded-control bg-info-bg p-3 text-body text-info">
              {data.dong_chua_thue} dòng hàng chưa có thuế suất — cột thuế để trống.{" "}
              <button type="button" className="font-semibold underline" onClick={() => setTab("thue")}>Đặt thuế suất</button>
            </p>
          ) : null}

          {!coHang ? <p className="rounded-card bg-surface p-4 text-body text-ink-muted ring-1 ring-hairline">Không có phiếu thu trong phạm vi đã chọn.</p> : null}
          {coHang ? (
            <div className="hidden overflow-x-auto rounded-card bg-surface ring-1 ring-hairline md:block">
              <table className="w-full text-body">
                <thead className="bg-surface-muted text-left text-meta text-ink-muted">
                  <tr>
                    {["Nhóm", "Mã", "Tên hàng hoá / dịch vụ", "ĐVT", "SL", "Trước giảm", "Giảm", "Sau giảm", "Thuế suất", "Tiền thuế"].map((t, i) => (
                      <th key={t} className={`px-3 py-2 font-semibold ${i >= 4 ? "text-right" : ""}`}>{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ds.map((h, i) => (
                    <tr key={`${h.nhom}-${h.ma}-${h.ten}-${h.dvt}-${i}`} className="border-t border-hairline align-top">
                      <td className="whitespace-nowrap px-3 py-2">{TEN_NHOM[h.nhom] ?? h.nhom}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-ink-muted">{h.ma || "—"}</td>
                      <td className="px-3 py-2">{h.ten}</td>
                      <td className="whitespace-nowrap px-3 py-2">{h.dvt || "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{h.so_luong}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{tien(h.tien_truoc_giam)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{h.giam_gia ? tien(h.giam_gia) : "—"}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums font-semibold">{tien(h.tien_sau_giam)}</td>
                      <td className="px-3 py-2 text-right text-ink-muted">{tenThueSuat(h.thue_suat) || "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{h.tien_thue === null ? "—" : tien(h.tien_thue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <div className="space-y-3 md:hidden">
            {ds.map((h, i) => (
              <div key={`${h.nhom}-${h.ma}-${h.ten}-${h.dvt}-${i}`} className="rounded-card bg-surface p-4 ring-1 ring-hairline">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span className="text-emph font-semibold text-ink">{h.ten}</span>
                  <span className="tabular-nums text-emph font-semibold text-ink">{tien(h.tien_sau_giam)}</span>
                </div>
                <p className="text-meta text-ink-muted">{TEN_NHOM[h.nhom] ?? h.nhom}{h.ma ? ` · ${h.ma}` : ""} · {h.so_luong} {h.dvt || ""}</p>
                {h.giam_gia ? <p className="text-meta text-ink-muted">Trước giảm {tien(h.tien_truoc_giam)} · giảm {tien(h.giam_gia)}</p> : null}
              </div>
            ))}
          </div>
        </>
      ) : null}
      </div>
    </div>
  );
}
