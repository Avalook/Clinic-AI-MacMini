"use client";

// Các lần đã đánh dấu "đã xuất sang MISA" (G5c, Tuyền 14/10/2026). Kế toán thấy: lần
// nào, ai đánh dấu, bao nhiêu hoá đơn, và hoá đơn nào CÓ THAY ĐỔI SAU KHI XUẤT (hoàn
// tiền, đổi dòng, đổi công ty / người mua) để vào MISA sửa. Bỏ đánh dấu hoàn tác được
// (Khôi phục). Màn chỉ vẽ + gửi lệnh; so sánh dấu vân tay làm ở máy chủ.

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import { tien } from "../hoa-don/types";

type LanXuat = {
  id: string; tu_ngay: string; den_ngay: string; so_hoa_don: number; tong_tien: number;
  ghi_chu: string; xuat_luc: string; huy_luc: string | null; xuat_boi_ten: string | null;
};
type ChiTiet = {
  hoa_don: { payment_cycle_id: string; ma_phieu: string; tong: number; co_thay_doi: boolean; ly_do: string[] }[];
  so_co_thay_doi: number;
};

const ngay = (iso: string) => new Date(iso).toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
const ngayGio = (iso: string) => new Date(iso).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

export default function LanXuatMisa({ lamMoi, onDoi, onQuyen }: {
  lamMoi: number; onDoi: () => void; onQuyen: (co: boolean) => void;
}) {
  const [ds, setDs] = useState<LanXuat[] | null>(null);
  const [khongQuyen, setKhongQuyen] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [mo, setMo] = useState<string | null>(null);
  const [chiTiet, setChiTiet] = useState<ChiTiet | null>(null);
  const [dangLam, setDangLam] = useState<string | null>(null);

  const tai = useCallback(async () => {
    try {
      const r = await fetch("/api/xuat-hoa-don/misa", { cache: "no-store" });
      if (r.status === 403) { setKhongQuyen(true); onQuyen(false); return; }
      const d = await r.json();
      if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được các lần đã xuất.");
      setDs(d.lan_xuat);
    } catch (e) { setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
  }, [onQuyen]);
  useEffect(() => {
    const t = setTimeout(() => { void tai(); }, 0);
    return () => clearTimeout(t);
  }, [tai, lamMoi]);

  const xem = async (id: string) => {
    if (mo === id) { setMo(null); setChiTiet(null); return; }
    setMo(id); setChiTiet(null);
    const r = await fetch(`/api/xuat-hoa-don/misa/${id}`, { cache: "no-store" });
    const d = await r.json().catch(() => ({}));
    if (r.ok) setChiTiet(d); else setLoi(typeof d.error === "string" ? d.error : "Không đọc được chi tiết lần xuất.");
  };
  const doi = async (id: string, method: "DELETE" | "PUT") => {
    setDangLam(id); setLoi(null);
    try {
      const r = await fetch(`/api/xuat-hoa-don/misa/${id}`, { method });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Máy chủ chưa lưu được — thử lại.");
      await tai(); onDoi();
    } catch (e) { setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
    finally { setDangLam(null); }
  };

  if (khongQuyen || !ds) return loi ? <p role="alert" className="rounded-control bg-danger-bg p-3 text-body text-danger">{loi}</p> : null;
  return (
    <section className="space-y-2 rounded-card bg-surface p-4 ring-1 ring-hairline">
      <h2 className="text-emph font-semibold text-ink">Các lần đã xuất sang MISA</h2>
      {loi ? <p role="alert" className="rounded-control bg-danger-bg p-2 text-danger">{loi}</p> : null}
      {ds.length === 0 ? <p className="text-body text-ink-muted">Chưa đánh dấu lần nào. Tải file Excel rồi bấm “Đánh dấu đã xuất MISA”.</p> : (
        <ul className="divide-y divide-hairline">
          {ds.map(l => (
            <li key={l.id} className="py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className={l.huy_luc ? "text-ink-muted line-through" : "text-ink"}>
                  {ngay(l.tu_ngay)}{l.tu_ngay !== l.den_ngay ? ` → ${ngay(l.den_ngay)}` : ""} · {l.so_hoa_don} hoá đơn · {tien(l.tong_tien)}
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-meta text-ink-muted">{ngayGio(l.xuat_luc)} · {l.xuat_boi_ten ?? "—"}{l.huy_luc ? " · đã bỏ đánh dấu" : ""}</span>
                  <Button size="sm" variant="ghost" onClick={() => void xem(l.id)}>{mo === l.id ? "Ẩn" : "Xem thay đổi"}</Button>
                  {l.huy_luc
                    ? <Button size="sm" disabled={dangLam === l.id} onClick={() => void doi(l.id, "PUT")}>Khôi phục</Button>
                    : <Button size="sm" variant="ghost" disabled={dangLam === l.id} onClick={() => void doi(l.id, "DELETE")}>Bỏ đánh dấu</Button>}
                </span>
              </div>
              {l.ghi_chu ? <p className="text-meta text-ink-muted">{l.ghi_chu}</p> : null}
              {mo === l.id ? (
                <div className="mt-2 rounded-control bg-surface-muted p-3">
                  {!chiTiet ? <p className="text-meta text-ink-muted">Đang so với dữ liệu hiện tại…</p>
                    : chiTiet.so_co_thay_doi === 0 ? <p className="text-body text-ink-muted">Không có hoá đơn nào thay đổi sau khi xuất.</p> : (
                      <>
                        <p className="mb-1 text-body font-semibold text-ink">{chiTiet.so_co_thay_doi} hoá đơn có thay đổi sau khi xuất — vào MISA kiểm lại:</p>
                        <ul className="space-y-1">
                          {chiTiet.hoa_don.filter(h => h.co_thay_doi).map(h => (
                            <li key={h.payment_cycle_id} className="text-body">
                              <span className="tabular-nums">{h.ma_phieu}</span> · {tien(h.tong)}
                              <span className="block text-meta text-ink-muted">{h.ly_do.join(" · ")}</span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
