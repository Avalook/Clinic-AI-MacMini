"use client";

import { useEffect, useState, type ReactNode } from "react";
import Button, { buttonClass } from "@/components/ui/Button";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";
import { todayVn } from "@/lib/roster";
import { INPUT } from "../form-ui";
import NgayTrucBaoCao, { type ReportCalendar } from "../reports/NgayTrucBaoCao";
import ChiTietHoaDon from "./ChiTietHoaDon";
import { TRANG_THAI, tien, type DanhSachData, type KhachHoaDon } from "./types";

function OLoc({ ten, children }: { ten: string; children: ReactNode }) {
  return <label className="min-w-0 space-y-1 text-meta text-ink-muted"><span className="block">{ten}</span>{children}</label>;
}
function SoTien({ ten, so }: { ten: string; so: number }) {
  return <div><dt className="text-meta text-ink-muted">{ten}</dt><dd className="tabular-nums font-semibold text-ink">{tien(so)}</dd></div>;
}
function CanhBao({ khach }: { khach: KhachHoaDon }) {
  return <>{(khach.canh_bao ?? []).map(cau => <span key={cau} className="mt-1 block rounded-chip bg-warning-bg px-2 py-1 text-meta text-warning">{cau}</span>)}{khach.can_doi_soat && !khach.canh_bao?.length ? <span className="mt-1 block text-meta text-warning">Cần kiểm tra</span> : null}</>;
}
function TrangThai({ ma }: { ma: string }) {
  return <span className={`rounded-chip px-2 py-1 text-meta ${ma === "DA_THU" ? "bg-success-bg text-success" : "bg-warning-bg text-warning"}`}>{TRANG_THAI[ma] ?? ma}</span>;
}

export default function DanhSachHoaDon({ coSo }: { coSo: CoSo[] }) {
  const [tu, setTu] = useState(todayVn);
  const [den, setDen] = useState(todayVn);
  const [tim, setTim] = useState("");
  const [loai, setLoai] = useState("");
  const [trangThai, setTrangThai] = useState("");
  const [canKiemTra, setCanKiemTra] = useState(false);
  const [ca, setCa] = useState("FULL");
  const [coSoChon, setCoSoChon] = useState("");
  const [access, setAccess] = useState<ReportCalendar | null>(null);
  const [data, setData] = useState<DanhSachData | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);
  const [lan, setLan] = useState(0);
  const [khach, setKhach] = useState<KhachHoaDon | null>(null);
  const restricted = !!access && !access.legacy && !access.quan_ly;
  const exportQuery = new URLSearchParams({ tu, den, tim, loai, trang_thai: trangThai, ca, co_so: coSoChon, can_kiem_tra: String(canKiemTra), xuat: "xlsx" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/reports/access?ngay=${encodeURIComponent(tu)}`, { cache: "no-store", signal: controller.signal })
      .then(async r => { if (!r.ok) throw new Error("Không đọc được phạm vi xem báo cáo."); return r.json(); })
      .then((a: ReportCalendar) => { setAccess(a); })
      .catch(e => { if (!controller.signal.aborted) setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); });
    return () => controller.abort();
  }, [tu]);

  useEffect(() => {
    const controller = new AbortController();
    const q = new URLSearchParams({ tu, den, tim, loai, trang_thai: trangThai, ca, co_so: coSoChon, can_kiem_tra: String(canKiemTra) });
    const timer = setTimeout(async () => {
      setDangTai(true); setData(null); setKhach(null); setLoi(null);
      try {
        const r = await fetch(`/api/hoa-don?${q}`, { cache: "no-store", signal: controller.signal });
        const d = await r.json();
        if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được danh sách hoá đơn trong phạm vi đã chọn.");
        if (!controller.signal.aborted) setData(d);
      } catch (e) {
        if (!controller.signal.aborted) setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ.");
      } finally { if (!controller.signal.aborted) setDangTai(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [tu, den, tim, loai, trangThai, ca, coSoChon, canKiemTra, lan]);

  return <div className="min-w-0 space-y-4">
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {!restricted ? <><OLoc ten="Từ ngày"><input aria-label="Từ ngày" type="date" className={`${INPUT} w-full`} value={tu} onChange={e => { setTu(e.target.value); if (restricted) setDen(e.target.value); }} /></OLoc>
      <OLoc ten="Đến ngày"><input aria-label="Đến ngày" type="date" className={`${INPUT} w-full`} value={den} onChange={e => setDen(e.target.value)} /></OLoc></> : null}
      <OLoc ten="Ca"><select aria-label="Ca" className={`${INPUT} w-full`} value={ca} onChange={e => setCa(e.target.value)}>
        <option value="FULL">Cả ngày</option>{["SANG", "CHIEU", "TOI"].map((v, i) => <option key={v} value={v}>{["Sáng", "Chiều", "Tối"][i]}</option>)}
      </select></OLoc>
      <OLoc ten="Cơ sở"><ChonCoSoO coSo={restricted ? coSo.filter(c => access.co_so_ids.includes(c.id)) : coSo} dangChon={coSoChon} onChon={setCoSoChon} /></OLoc>
      <OLoc ten="Tìm khách / mã phiếu"><input aria-label="Tìm khách hoặc mã phiếu" className={`${INPUT} w-full`} value={tim} onChange={e => setTim(e.target.value)} placeholder="Tên, mã khách, SĐT, mã phiếu" /></OLoc>
      <OLoc ten="Loại phiếu"><select aria-label="Loại phiếu" className={`${INPUT} w-full`} value={loai} onChange={e => setLoai(e.target.value)}><option value="">Dịch vụ và thuốc</option><option value="dich_vu">Dịch vụ</option><option value="thuoc">Thuốc</option></select></OLoc>
      <OLoc ten="Trạng thái"><select aria-label="Trạng thái" className={`${INPUT} w-full`} value={trangThai} onChange={e => setTrangThai(e.target.value)}><option value="">Tất cả trạng thái</option>{Object.entries(TRANG_THAI).filter(([ma]) => ma !== "HON_HOP").map(([ma, ten]) => <option key={ma} value={ma}>{ten}</option>)}</select></OLoc>
      <div className="flex flex-wrap items-end gap-3"><label className="flex min-h-10 items-center gap-2 text-body text-ink"><input type="checkbox" checked={canKiemTra} onChange={e => setCanKiemTra(e.target.checked)} />Chỉ cần kiểm tra</label><Button type="button" onClick={() => setLan(n => n + 1)}>Tải lại</Button></div>
    </div>
    {restricted ? <NgayTrucBaoCao access={access} ngay={tu} onChon={v => { setTu(v); setDen(v); }} /> : null}
    {loi ? <p role="alert" className="rounded-control bg-danger-bg p-3 text-body text-danger">{loi}</p> : null}
    {dangTai ? <p role="status" className="text-body text-ink-muted">Đang tải hoá đơn…</p> : null}
    {data ? <>
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-emph font-semibold text-ink">Giao dịch trong kỳ đã chọn</h2><a href={`/api/hoa-don?${exportQuery}`} className={buttonClass("secondary", "md")}>Xuất Excel</a></div>
      <dl className="grid grid-cols-2 gap-4 rounded-card bg-surface p-4 ring-1 ring-hairline md:grid-cols-4">
        <SoTien ten="Đã thu" so={data.tong.da_thu} /><SoTien ten="Đã trả lại" so={data.tong.da_hoan} /><SoTien ten="Chờ trả lại" so={data.tong.cho_hoan} /><SoTien ten="Thu ròng" so={data.tong.thu_rong} />
      </dl>
      <p className="text-meta text-ink-muted">{data.tong.so_khach} khách · {data.tong.so_phieu} phiếu. Bảng khách thể hiện toàn bộ các phiếu liên quan, kể cả phiếu thu ngoài kỳ có hoàn trong kỳ. Tổng theo khách có thể khác tổng giao dịch trong kỳ.</p>
      {!data.khach.length ? <p className="rounded-card bg-surface p-4 text-body text-ink-muted ring-1 ring-hairline">Không có hoá đơn trong phạm vi đã chọn.</p> : null}
      <div className="hidden overflow-x-auto rounded-card bg-surface ring-1 ring-hairline md:block">
        <table className="w-full text-body"><thead className="bg-surface-muted text-left text-meta text-ink-muted"><tr>{["Khách hàng", "Số phiếu", "Đã thu", "Đã hoàn", "Chờ hoàn", "Thu ròng", "Trạng thái", "Chi tiết"].map((t, i) => <th key={t} className={`px-3 py-2 font-semibold ${i > 0 && i < 6 ? "text-right" : ""}`}>{t}</th>)}</tr></thead>
          <tbody>{data.khach.map(k => <tr key={k.id} className="border-t border-hairline hover:bg-surface-muted">
            <td className="px-3 py-3"><span className="font-semibold">{k.ten}</span><span className="block text-meta text-ink-muted">{k.ma_bn || "—"} · {k.so_dien_thoai || "—"}</span></td>
            <td className="px-3 py-3 text-right tabular-nums">{k.so_phieu}</td>{[k.da_thu, k.da_hoan, k.cho_hoan, k.thu_rong].map((n, i) => <td key={i} className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(n)}</td>)}
            <td className="px-3 py-3"><TrangThai ma={k.trang_thai} /><CanhBao khach={k} /></td><td className="px-3 py-3"><Button type="button" size="sm" onClick={() => setKhach(k)} aria-label={`Xem hoá đơn ${k.ten}`}>Xem</Button></td>
          </tr>)}</tbody></table>
      </div>
      <div className="space-y-3 md:hidden">{data.khach.map(k => <article key={k.id} className="rounded-card bg-surface p-4 ring-1 ring-hairline">
        <div className="flex flex-wrap justify-between gap-2"><h2 className="text-emph font-semibold">{k.ten}</h2><TrangThai ma={k.trang_thai} /></div>
        <CanhBao khach={k} />
        <p className="mt-1 text-meta text-ink-muted">{k.ma_bn || "—"} · {k.so_phieu} phiếu</p>
        <dl className="my-3 grid grid-cols-2 gap-3"><SoTien ten="Đã thu" so={k.da_thu} /><SoTien ten="Đã hoàn" so={k.da_hoan} /><SoTien ten="Chờ hoàn" so={k.cho_hoan} /><SoTien ten="Thu ròng" so={k.thu_rong} /></dl>
        <Button type="button" onClick={() => setKhach(k)} aria-label={`Xem hoá đơn ${k.ten}`}>Xem hoá đơn</Button>
      </article>)}</div>
    </> : null}
    {khach ? <ChiTietHoaDon khach={khach} onDong={() => setKhach(null)} /> : null}
  </div>;
}
