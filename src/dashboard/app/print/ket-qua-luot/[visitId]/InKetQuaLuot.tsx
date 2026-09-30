"use client";

// PHIẾU NÀO RA PHIẾU ĐÓ (Tuyền 28/09/2026: "tách biệt tất cả ra chứ, phiếu nào ra
// phiếu đó, fill đẹp A4 chứ không phải nối thành 1 file duy nhất"). Trang này
// chỉ là DANH SÁCH các chỉ định đã có kết quả của lượt; mỗi dòng mở ĐÚNG trang
// in của chỉ định ấy (`/print/ket-qua/[order]` — hai bên: phiếu A4 và ảnh, mỗi
// bên in / tải PDF / tải ảnh riêng). Không còn bản nối mọi phiếu làm một tệp.

import { useEffect, useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import { NHAN_KET_QUA, anhInDuoc, type ChiDinhVaKetQua } from "@/lib/phieu-kham";

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
    <main className="mx-auto w-full max-w-3xl space-y-4 p-4 text-body text-ink sm:p-8">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-title font-semibold text-ink">Kết quả của lượt khám</h1>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      <p className="text-meta text-ink-muted">
        Mỗi phiếu in riêng một tệp A4. Mở phiếu → bên phải là phiếu (có / không ảnh), bên
        trái là ảnh — mỗi bên có nút In / tải PDF và tải ảnh, video riêng.
      </p>
      {ds.length === 0 ? (
        <p className="text-ink-muted">Lượt này chưa có kết quả nào để in.</p>
      ) : (
        <ul className="space-y-2">
          {ds.map((c) => {
            const soAnh = anhInDuoc(c).length;
            return (
              <li
                key={c.service_order_id}
                className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink">{c.ten_hien_thi}</p>
                  <p className="text-meta text-ink-muted">
                    {NHAN_KET_QUA[c.ket_qua_trang_thai]}
                    {soAnh ? ` · ${soAnh} ảnh` : ""}
                  </p>
                </div>
                <a
                  href={`/print/ket-qua/${c.service_order_id}`}
                  target="_blank"
                  rel="noopener"
                  className={buttonClass("primary")}
                >
                  Mở phiếu · in / PDF
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
