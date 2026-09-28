"use client";

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";

import { KIEU_HOA_DON, PhieuThuGiay, type Phieu } from "../../phieu-thu/[id]/InPhieuThu";

export default function InHoaDonThuoc({ visitId }: { visitId: string }) {
  const [ds, setDs] = useState<Phieu[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    void (async () => {
      const r = await fetch(
        `/api/cashier?xem=phieu-luot&visit=${encodeURIComponent(visitId)}&kind=thuoc`,
        { cache: "no-store" },
      );
      const d = (await r.json().catch(() => null)) as {
        phieu?: Phieu[];
        message?: string;
        error?: string;
      } | null;
      if (huy) return;
      if (!r.ok || !d) setLoi(d?.message ?? d?.error ?? "Không đọc được hoá đơn thuốc.");
      else setDs(d.phieu ?? []);
    })();
    return () => {
      huy = true;
    };
  }, [visitId]);

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!ds) return <p className="p-8 text-body text-ink-muted">Đang tải hoá đơn…</p>;
  return (
    <main className="mx-auto max-w-xs bg-surface p-4 text-body text-ink print:max-w-none print:p-0">
      <style>{KIEU_HOA_DON}</style>
      <div className="mb-4 flex gap-2 print:hidden">
        <Button type="button" variant="primary" disabled={ds.length === 0} onClick={() => window.print()}>
          In / tải PDF
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      {ds.length === 0 ? (
        <p className="text-ink-muted">Lượt này chưa có lần thu tiền thuốc nào.</p>
      ) : null}
      {ds.map((p, i) => (
        <article key={p.ma} className={i > 0 ? "mt-8 break-before-page print:mt-0" : ""}>
          <PhieuThuGiay p={p} />
        </article>
      ))}
    </main>
  );
}
