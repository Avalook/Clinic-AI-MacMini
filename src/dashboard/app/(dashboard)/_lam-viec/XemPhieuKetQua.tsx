"use client";

// Phiếu kết quả ĐÃ HOÀN TẤT — CHỈ ĐỌC, cho bác sĩ chính / thư ký ở Bàn khám.
// Trước 24/09 phiếu chỉ mở được ở phòng làm, nên bác sĩ chính không đọc được
// kết quả dạng phiếu. Mở lần đầu là máy chủ tự ghi "đã xem" (Tuyền chốt 24/09:
// duyệt không bắt buộc) — màn không phải bấm gì thêm.

import { useEffect, useState } from "react";

interface O {
  ma: string;
  ten: string;
  kieu: string;
}
interface Muc {
  ma: string;
  ten: string;
  block: O[];
  /** Mục dạng bảng (mẫu v3) — giá trị ô là {ma_cột: giá trị}. */
  cot?: { ma: string; ten: string }[];
}
interface Phieu {
  id: string;
  form_id: string;
  khung: Muc[];
  du_lieu: Record<string, { gia_tri: string; nguon: string }>;
  dang_sua: boolean;
}

export default function XemPhieuKetQua({ serviceOrderId }: { serviceOrderId: string }) {
  const [phieu, setPhieu] = useState<Phieu[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    void (async () => {
      try {
        const r = await fetch(`/api/phieu?xem=${serviceOrderId}`, { cache: "no-store" });
        const d = (await r.json().catch(() => null)) as
          | { phieu?: Phieu[]; message?: string; error?: string }
          | null;
        if (huy) return;
        if (!r.ok) setLoi(d?.message ?? d?.error ?? "Không đọc được phiếu kết quả.");
        else setPhieu(d?.phieu ?? []);
      } catch {
        if (!huy) setLoi("Mất kết nối.");
      }
    })();
    return () => {
      huy = true;
    };
  }, [serviceOrderId]);

  if (loi) {
    return (
      <p role="alert" className="text-meta text-danger">
        {loi}
      </p>
    );
  }
  if (phieu === null) return <p className="text-meta text-ink-muted">Đang tải phiếu…</p>;
  if (phieu.length === 0) {
    return <p className="text-meta text-ink-muted">Chưa có phiếu kết quả hoàn tất.</p>;
  }
  return (
    <div className="space-y-3">
      {phieu.map((p) => (
        <div key={p.id} className="rounded-control border border-line p-2">
          {p.dang_sua ? (
            <p className="mb-1 text-label text-warning">
              Phòng đang sửa phiếu này — đây là bản chính thức hiện tại.
            </p>
          ) : null}
          {p.khung.map((m) => (
            <div key={m.ma} className="mb-2">
              <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
                {m.ten}
              </p>
              <dl className="grid grid-cols-1 gap-x-3 sm:grid-cols-2">
                {m.block.map((o) => {
                  const g: unknown = p.du_lieu[o.ma]?.gia_tri ?? "";
                  // Mục dạng BẢNG (mẫu v3): {ma_cột: giá trị} → "Thai A: … · Thai B: …".
                  const v =
                    g && typeof g === "object" && !Array.isArray(g)
                      ? (m.cot ?? [])
                          .map((c) => {
                            const x = (g as Record<string, unknown>)[c.ma];
                            return x === "" || x == null ? "" : `${c.ten}: ${String(x)}`;
                          })
                          .filter(Boolean)
                          .join(" · ")
                      : Array.isArray(g)
                        ? g.join(", ")
                        : String(g);
                  return (
                    <div key={o.ma} className="flex gap-2 text-meta">
                      <dt className="text-ink-muted">{o.ten}:</dt>
                      <dd className="whitespace-pre-line text-ink">{v || "—"}</dd>
                    </div>
                  );
                })}
              </dl>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
