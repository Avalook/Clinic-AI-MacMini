"use client";

import { useEffect, useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";

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
        <Button type="button" variant="primary" disabled={ds.length !== 1} onClick={() => window.print()}>
          In / tải PDF
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      {ds.length === 0 ? (
        <p className="text-ink-muted">Lượt này chưa có lần thu tiền thuốc nào.</p>
      ) : null}
      {/* Phiếu nào ra phiếu đó (Tuyền 28/09/2026): MỘT lần thu → in thẳng; nhiều
          lần thu → danh sách, mỗi lần thu mở phiếu riêng (`/print/phieu-thu`). */}
      {ds.length === 1 ? <PhieuThuGiay p={ds[0]} /> : null}
      {ds.length > 1 ? (
        <ul className="space-y-2">
          {ds.map((p) => (
            <li key={p.ma} className="flex items-center justify-between gap-2">
              <span>
                {p.ma} · {p.tong.toLocaleString("vi-VN")}đ
              </span>
              <a
                href={`/print/phieu-thu/${p.id}?loai=thu`}
                target="_blank"
                rel="noopener"
                className={buttonClass("primary", "sm")}
              >
                Mở · in
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </main>
  );
}
