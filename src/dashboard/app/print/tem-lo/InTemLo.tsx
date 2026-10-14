"use client";

import { useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import { thanhVachCode128B } from "../../../lib/ma-vach";
import { docKho } from "../../(dashboard)/pharmacy/inventory/gui-kho";
import type { LoQuet } from "../../(dashboard)/pharmacy/inventory/OQuetMa";
import { fmtNgay } from "../../(dashboard)/pharmacy/ban-thuoc";

type Kho = "decal" | "a4";

const gioiHan = (v: string, thap: number, cao: number, macDinh: number): number => {
  const n = Number(v.replace(",", "."));
  return Number.isFinite(n) ? Math.min(cao, Math.max(thap, n)) : macDinh;
};

function Vach({ ma }: { ma: string }) {
  const v = thanhVachCode128B(ma);
  if (!v) return null;
  return (
    <svg
      viewBox={`0 0 ${v.rong} 1`}
      preserveAspectRatio="none"
      className="block h-[9mm] w-full"
      role="img"
      aria-label={`Mã vạch ${ma}`}
    >
      {v.thanh.map((t) => (
        <rect key={t.x} x={t.x} y={0} width={t.w} height={1} fill="#000" />
      ))}
    </svg>
  );
}

export default function InTemLo({ ids, phieu }: { ids: string; phieu: string }) {
  const [ds, setDs] = useState<LoQuet[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [kho, setKho] = useState<Kho>("decal");
  const [rong, setRong] = useState("50");
  const [cao, setCao] = useState("30");
  const [soBan, setSoBan] = useState("1");

  useEffect(() => {
    let huy = false;
    void (async () => {
      const kq = await docKho<{ items: LoQuet[] }>("tem-lo", { ids, phieu });
      if (huy) return;
      if (!kq.ok) setLoi(kq.loi);
      else setDs(kq.data.items);
    })();
    return () => {
      huy = true;
    };
  }, [ids, phieu]);

  const w = gioiHan(rong, 20, 200, 50);
  const h = gioiHan(cao, 15, 200, 30);
  const ban = Math.round(gioiHan(soBan, 1, 20, 1));
  const tem = useMemo(
    () => (ds ?? []).flatMap((lo) => Array.from({ length: ban }, (_, i) => ({ lo, i }))),
    [ds, ban],
  );

  // Khổ decal: mỗi tem một trang cỡ w×h, không lề. A4: lưới tem cỡ w×h, lề 10mm.
  const kieu =
    kho === "decal"
      ? `@page { size: ${w}mm ${h}mm; margin: 0; } @media print { .tem { break-after: page; } }`
      : `@page { size: A4; margin: 10mm; } @media print { .tem { break-inside: avoid; } }`;

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!ds) return <p className="p-8 text-body text-ink-muted">Đang tải tem…</p>;
  return (
    <main className="mx-auto w-full bg-surface p-4 text-body text-ink print:p-0">
      <style>{kieu}</style>
      <div className="mb-4 flex flex-wrap items-end gap-3 print:hidden">
        <label className="text-meta text-ink-soft">
          Khổ giấy
          <select
            value={kho}
            onChange={(e) => setKho(e.target.value as Kho)}
            className="mt-1 block min-h-10 rounded-control border border-line bg-surface px-2"
          >
            <option value="decal">Tem decal (mỗi tem một nhãn)</option>
            <option value="a4">A4 nhiều tem</option>
          </select>
        </label>
        <label className="text-meta text-ink-soft">
          Rộng (mm)
          <input
            value={rong}
            inputMode="decimal"
            onChange={(e) => setRong(e.target.value)}
            className="mt-1 block min-h-10 w-20 rounded-control border border-line bg-surface px-2"
          />
        </label>
        <label className="text-meta text-ink-soft">
          Cao (mm)
          <input
            value={cao}
            inputMode="decimal"
            onChange={(e) => setCao(e.target.value)}
            className="mt-1 block min-h-10 w-20 rounded-control border border-line bg-surface px-2"
          />
        </label>
        <label className="text-meta text-ink-soft">
          Số tem mỗi lô
          <input
            value={soBan}
            inputMode="numeric"
            onChange={(e) => setSoBan(e.target.value)}
            className="mt-1 block min-h-10 w-20 rounded-control border border-line bg-surface px-2"
          />
        </label>
        <Button type="button" variant="primary" disabled={tem.length === 0} onClick={() => window.print()}>
          In {tem.length} tem
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      {tem.length === 0 ? (
        <p className="text-ink-muted">Không có lô nào để in tem (lô không thuộc kho cơ sở đang làm?).</p>
      ) : null}
      <div className={kho === "a4" ? "flex flex-wrap gap-[2mm]" : ""}>
        {tem.map(({ lo, i }) => (
          <div
            key={`${lo.id}-${i}`}
            className="tem flex flex-col justify-between overflow-hidden border border-dashed border-line bg-white p-[1.5mm] text-black print:border-0"
            style={{ width: `${w}mm`, height: `${h}mm` }}
          >
            <p className="line-clamp-2 text-[7pt] font-semibold leading-tight">{lo.ten_thuoc ?? "—"}</p>
            <p className="text-[7pt] leading-tight">
              Lô {lo.batch_code} · HSD {lo.expiry_date ? fmtNgay(lo.expiry_date) : "chưa có"}
            </p>
            <div>
              <Vach ma={lo.ma_tem} />
              <p className="text-center font-mono text-[7pt] leading-none">{lo.ma_tem}</p>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
