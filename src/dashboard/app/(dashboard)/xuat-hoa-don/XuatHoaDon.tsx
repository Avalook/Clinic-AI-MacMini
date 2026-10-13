"use client";

// Xuất hoá đơn (Tuyền 13/10/2026): kế toán tải file Excel ĐÚNG mẫu nhập hoá đơn
// GTGT (MISA) thay vì gõ tay từng phiếu thu. Máy chủ dựng hoá đơn và file từ
// chính tệp mẫu; màn chỉ chọn phạm vi, xem trước và tải.

import { useEffect, useState, type ReactNode } from "react";
import { buttonClass } from "@/components/ui/Button";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";
import LichKhoangNgay from "@/components/ui/LichKhoangNgay";
import { todayVn } from "@/lib/roster";
import { khoangNhanh, type Khoang } from "@/lib/thanh-ngay";
import { INPUT } from "../form-ui";
import { tien } from "../hoa-don/types";

type DongHang = { ten: string; dvt: string; so_luong: number; don_gia: number; thanh_tien: number };
type HoaDon = {
  stt: number; ma_phieu: string; kind: string; ngay: string; ten_khach: string; ma_bn: string | null;
  so_dien_thoai: string; hinh_thuc: string; dong: DongHang[]; tong: number; ghi_chu: string[];
};
type XuatData = { tu: string; den: string; hoa_don: HoaDon[]; so_hoa_don: number; so_dong: number; tong: number };

function OLoc({ ten, children }: { ten: string; children: ReactNode }) {
  return (
    <label className="min-w-0 space-y-1 text-meta text-ink-muted">
      <span className="block">{ten}</span>
      {children}
    </label>
  );
}

function DongHangGon({ dong }: { dong: DongHang[] }) {
  return (
    <ul className="space-y-0.5">
      {dong.map((d, i) => (
        <li key={i} className="text-body text-ink">
          {d.ten} <span className="text-meta text-ink-muted">· {d.so_luong} {d.dvt || ""} × {d.don_gia.toLocaleString("vi-VN")}</span>
        </li>
      ))}
    </ul>
  );
}

function GhiChu({ h }: { h: HoaDon }) {
  return h.ghi_chu.length ? (
    <div className="flex flex-col items-start gap-1">
      {h.ghi_chu.map(g => <span key={g} className="inline-block rounded-chip bg-warning-bg px-2 py-0.5 text-meta font-medium text-warning">{g}</span>)}
    </div>
  ) : null;
}

export default function XuatHoaDon({ coSo }: { coSo: CoSo[] }) {
  const homNay = todayVn();
  const [khoang, setKhoang] = useState<Khoang>({ tu: homNay, den: homNay });
  const [loai, setLoai] = useState("");
  const [coSoChon, setCoSoChon] = useState("");
  const [data, setData] = useState<XuatData | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);
  const chuoi = new URLSearchParams({ tu: khoang.tu, den: khoang.den, loai, co_so: coSoChon }).toString();

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setDangTai(true); setLoi(null);
      try {
        const r = await fetch(`/api/xuat-hoa-don?${chuoi}`, { cache: "no-store", signal: controller.signal });
        const d = await r.json();
        if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được hoá đơn trong phạm vi đã chọn.");
        if (!controller.signal.aborted) setData(d);
      } catch (e) {
        if (!controller.signal.aborted) { setData(null); setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
      } finally { if (!controller.signal.aborted) setDangTai(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [chuoi]);

  const ds = data?.hoa_don ?? [];
  const coHoaDon = ds.length > 0;

  return (
    <div className="min-w-0 space-y-4">
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
        <OLoc ten="Loại hoá đơn">
          <select aria-label="Loại hoá đơn" className={`${INPUT} w-full`} value={loai} onChange={e => setLoai(e.target.value)}>
            <option value="">Dịch vụ và thuốc</option>
            <option value="dich_vu">Dịch vụ</option>
            <option value="thuoc">Thuốc</option>
          </select>
        </OLoc>
        <OLoc ten="Cơ sở">
          <ChonCoSoO coSo={coSo} dangChon={coSoChon} onChon={setCoSoChon} className="w-full" />
        </OLoc>
        <div className="flex items-end">
          {coHoaDon ? (
            <a href={`/api/xuat-hoa-don?${chuoi}&xuat=xlsx`} className={`${buttonClass("primary", "md")} w-full justify-center`}>
              Tải file Excel ({data?.so_hoa_don} hoá đơn)
            </a>
          ) : (
            <button type="button" disabled className={`${buttonClass("primary", "md")} w-full justify-center`}>Tải file Excel</button>
          )}
        </div>
      </div>

      {loi ? <p role="alert" className="rounded-control bg-danger-bg p-3 text-body text-danger">{loi}</p> : null}
      {dangTai && !data ? <p role="status" className="text-body text-ink-muted">Đang tải hoá đơn…</p> : null}

      {data ? (
        <>
          <dl className="grid grid-cols-3 gap-4 rounded-card bg-surface p-4 ring-1 ring-hairline">
            <div><dt className="text-meta text-ink-muted">Số hoá đơn</dt><dd className="tabular-nums text-emph font-semibold text-ink">{data.so_hoa_don}</dd></div>
            <div><dt className="text-meta text-ink-muted">Số dòng hàng</dt><dd className="tabular-nums text-emph font-semibold text-ink">{data.so_dong}</dd></div>
            <div><dt className="text-meta text-ink-muted">Tổng thành tiền</dt><dd className="tabular-nums text-emph font-semibold text-ink">{tien(data.tong)}</dd></div>
          </dl>
          <p className="text-meta text-ink-muted">Mỗi phiếu thu là một hoá đơn, xếp theo giờ thu. Không gồm phiếu đã huỷ; dòng đã hoàn tiền xong được trừ. Số tiền là số khách thực trả (sau giảm giá).</p>

          {!coHoaDon ? <p className="rounded-card bg-surface p-4 text-body text-ink-muted ring-1 ring-hairline">Không có phiếu thu trong phạm vi đã chọn.</p> : null}
          {coHoaDon ? (
            <div className="hidden overflow-x-auto rounded-card bg-surface ring-1 ring-hairline md:block">
              <table className="w-full text-body">
                <thead className="bg-surface-muted text-left text-meta text-ink-muted">
                  <tr>
                    {["STT", "Ngày", "Khách hàng", "Hình thức", "Hàng hoá / dịch vụ", "Thành tiền", "Ghi chú"].map((t, i) => (
                      <th key={t} className={`px-3 py-2 font-semibold ${i === 0 || i === 5 ? "text-right" : ""}`}>{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ds.map(h => (
                    <tr key={h.ma_phieu} className="border-t border-hairline align-top">
                      <td className="px-3 py-3 text-right tabular-nums">{h.stt}</td>
                      <td className="whitespace-nowrap px-3 py-3 tabular-nums">{h.ngay}<span className="block text-meta text-ink-muted">{h.ma_phieu}</span></td>
                      <td className="px-3 py-3">{h.ten_khach || "—"}<span className="block text-meta text-ink-muted">{h.ma_bn || "—"} · {h.so_dien_thoai || "—"}</span></td>
                      <td className="whitespace-nowrap px-3 py-3">{h.hinh_thuc || "—"}</td>
                      <td className="px-3 py-3"><DongHangGon dong={h.dong} /></td>
                      <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(h.tong)}</td>
                      <td className="px-3 py-3"><GhiChu h={h} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <div className="space-y-3 md:hidden">
            {ds.map(h => (
              <div key={h.ma_phieu} className="rounded-card bg-surface p-4 ring-1 ring-hairline">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span className="text-emph font-semibold text-ink">{h.stt}. {h.ten_khach || "—"}</span>
                  <span className="tabular-nums text-emph font-semibold text-ink">{tien(h.tong)}</span>
                </div>
                <p className="text-meta text-ink-muted">{h.ngay} · {h.ma_phieu} · {h.hinh_thuc || "—"}</p>
                <div className="mt-2"><DongHangGon dong={h.dong} /></div>
                <div className="mt-2"><GhiChu h={h} /></div>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
