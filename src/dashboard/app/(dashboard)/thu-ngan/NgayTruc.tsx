"use client";

import { useEffect, useState } from "react";
import { useDoiCa } from "../dung-doi-ca";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";
import { ngayNgan } from "@/lib/thanh-ngay";

export interface NgayTrucDong {
  ngay: string;
  cac_ca: string[];
  co_so_ids: string[];
  co_so_theo_ca?: Record<string, string[]>;
  co_so?: { id: string; ten: string }[];
}
interface DanhSachNgay {
  quay?: string;
  quan_ly: boolean;
  thao_tac?: boolean;
  dang_truc?: { ca: string; co_so_id: string }[];
  items: NgayTrucDong[];
  next_cursor: string | null;
}
export interface PhamViQuay {
  ca?: string;
  coSo?: string;
  restricted?: boolean;
}
const TEN_CA: Record<string, string> = { SANG: "Ca sáng", CHIEU: "Ca chiều", TOI: "Ca tối", FULL: "Cả ngày" };

export function useNgayTruc(quay: "dich_vu" | "thuoc", ngay: string) {
  const doiCa = useDoiCa();
  const [ds, setDs] = useState<DanhSachNgay | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [caChon, setCa] = useState("");
  const [coSoChon, setCoSo] = useState("");
  const [them, setThem] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const tai = () => void fetch(`/api/cashier?xem=ngay-truc&quay=${quay}`, { cache: "no-store", signal: controller.signal })
      .then(async r => {
        const d = await r.json();
        if (!r.ok || !Array.isArray(d.items)) throw new Error(d.error ?? d.message ?? "Không đọc được ngày trực.");
        if (!controller.signal.aborted) {
          setDs(previous => previous?.quay === quay ? { ...d, quay, items: [...d.items, ...previous.items.filter(p => !d.items.some((i: NgayTrucDong) => i.ngay === p.ngay))], next_cursor: previous.next_cursor } : { ...d, quay });
          setLoi(null);
        }
      }).catch(e => {
        if (!controller.signal.aborted) { setLoi(e instanceof Error ? e.message : "Không đọc được ngày trực."); setDs(null); }
      });
    tai();
    // Tab ẩn thì huỷ hẳn nhịp (bản `setInterval` trần vẫn hỏi cả lúc ẩn). Hiện lại
    // thì chuông ca (`doiCa`) đã làm effect này chạy lại — không hỏi thêm.
    const goNhip = nhipKhiHien(tai, 30_000, { hoiKhiHien: false });
    return () => { controller.abort(); goNhip(); };
  }, [quay, doiCa]);
  const xemThem = async () => {
    if (!ds?.next_cursor || them) return;
    setThem(true);
    try {
      const r = await fetch(`/api/cashier?xem=ngay-truc&quay=${quay}&cursor=${encodeURIComponent(ds.next_cursor)}`, { cache: "no-store" });
      const d: DanhSachNgay & { error?: string } = await r.json();
      if (!r.ok || !Array.isArray(d.items)) throw new Error(d.error ?? "Không đọc được ngày trực trước đó.");
      setDs(previous => previous?.quay === quay ? { ...d, quay, items: [...previous.items, ...d.items.filter(i => !previous.items.some(p => p.ngay === i.ngay))] } : { ...d, quay });
      setLoi(null);
    } catch (e) { setLoi(e instanceof Error ? e.message : "Không đọc được ngày trực trước đó."); }
    finally { setThem(false); }
  };
  const currentDs = ds?.quay === quay ? ds : null;
  const dong = currentDs?.items.find(d => d.ngay === ngay) ?? currentDs?.items[0];
  const restricted = currentDs ? !currentDs.quan_ly : true;
  const ca = restricted ? (dong?.cac_ca.includes(caChon) ? caChon : dong?.cac_ca[0]) : undefined;
  const coSoIds = (ca ? dong?.co_so_theo_ca?.[ca] : undefined) ?? dong?.co_so_ids ?? [];
  const coSo = restricted ? (coSoIds.includes(coSoChon) ? coSoChon : coSoIds[0]) : undefined;
  return { ds: currentDs, loi, dong, ca, coSo, coSoIds, restricted, ngayXem: restricted ? dong?.ngay : ngay,
    thaoTac: currentDs?.thao_tac === true, dangTruc: currentDs?.dang_truc ?? [],
    setCa, setCoSo, xemThem, them, ready: !!currentDs && (!restricted || !!dong) };
}

export default function NgayTruc({ state, onChon }: { state: ReturnType<typeof useNgayTruc>; onChon: (ngay: string) => void }) {
  return <section aria-label="Ngày và ca trực được xem" className="space-y-2">
    <p className="text-body font-medium text-ink">Ngày trực của bạn</p>
    <div className="flex flex-wrap gap-2">
      {(state.ds?.items ?? []).map(d => <button key={d.ngay} type="button" aria-pressed={state.ngayXem === d.ngay}
        className={`min-h-10 rounded-control px-3 text-body ${state.ngayXem === d.ngay ? "bg-brand-600 text-white" : "bg-surface-muted text-ink"}`}
        onClick={() => onChon(d.ngay)}>{ngayNgan(d.ngay)}</button>)}
      {state.ds?.next_cursor ? <button type="button" disabled={state.them} className="min-h-10 px-3 text-body text-brand-700" onClick={() => void state.xemThem()}>{state.them ? "Đang tải…" : "Ngày trước đó"}</button> : null}
    </div>
    {state.dong && state.restricted ? <div className="flex flex-wrap gap-2">
      {state.dong.cac_ca.map(ca => <button key={ca} type="button" aria-pressed={state.ca === ca} onClick={() => state.setCa(ca)}
        className={`min-h-10 rounded-control px-3 text-body ${state.ca === ca ? "bg-brand-600 text-white" : "bg-surface-muted text-ink"}`}>{TEN_CA[ca] ?? ca}</button>)}
      {state.coSoIds.length > 1 ? <select aria-label="Cơ sở trực" value={state.coSo} onChange={e => state.setCoSo(e.target.value)} className="min-h-10 rounded-control bg-surface px-3 ring-1 ring-line-strong">
        {state.coSoIds.map((id, i) => <option key={id} value={id}>{state.dong?.co_so?.find(c => c.id === id)?.ten ?? `Cơ sở trực ${i + 1}`}</option>)}
      </select> : null}
    </div> : state.ds ? <p className="text-body text-ink-muted">Chưa có ngày trực được duyệt cho quầy này.</p> : !state.loi ? <p role="status" className="text-body text-ink-muted">Đang đọc ngày trực…</p> : null}
    {state.loi ? <p role="alert" className="text-body text-danger">{state.loi}</p> : null}
  </section>;
}
