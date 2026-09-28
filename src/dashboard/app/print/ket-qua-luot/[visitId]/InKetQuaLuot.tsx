"use client";

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import type { ChiDinhVaKetQua } from "@/lib/phieu-kham";

import InKetQua from "../../ket-qua/[orderId]/InKetQua";

export default function InKetQuaLuot({ visitId }: { visitId: string }) {
  const [ds, setDs] = useState<ChiDinhVaKetQua[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    void (async () => {
      const r = await fetch(`/api/phieu-kham?visit_id=${encodeURIComponent(visitId)}`, {
        cache: "no-store",
      });
      const d = (await r.json().catch(() => null)) as {
        chi_dinh?: ChiDinhVaKetQua[];
        message?: string;
      } | null;
      if (huy) return;
      if (!r.ok || !d) setLoi(d?.message ?? "Không đọc được kết quả của lượt này.");
      // Chỉ chỉ định ĐÃ có kết quả (phiếu hoặc tệp) — chưa làm thì không in.
      else setDs((d.chi_dinh ?? []).filter((c) => c.ket_qua.length > 0));
    })();
    return () => {
      huy = true;
    };
  }, [visitId]);

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!ds) return <p className="p-8 text-body text-ink-muted">Đang tải kết quả…</p>;
  return (
    <main className="mx-auto max-w-3xl bg-surface p-8 text-body text-ink print:max-w-none print:p-0">
      <div className="mb-6 flex flex-wrap gap-2 print:hidden">
        <Button type="button" variant="primary" disabled={ds.length === 0} onClick={() => window.print()}>
          In / tải PDF
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
        <span className="self-center text-meta text-ink-muted">
          {ds.length} phiếu kết quả
        </span>
      </div>
      {ds.length === 0 ? (
        <p className="text-ink-muted">Lượt này chưa có kết quả nào để in.</p>
      ) : null}
      {ds.map((c, i) => (
        <div key={c.service_order_id} className={i > 0 ? "mt-12 break-before-page print:mt-0" : ""}>
          <InKetQua orderId={c.service_order_id} nhung />
        </div>
      ))}
    </main>
  );
}
