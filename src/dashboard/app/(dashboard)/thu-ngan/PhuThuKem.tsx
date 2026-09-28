"use client";

// MÓN KÈM DỊCH VỤ — tick "thêm đầu dò" + sửa giá ở THU TIỀN DỊCH VỤ (Tuyền
// 28/09/2026: "thêm ô tick vào thu dịch vụ là thêm đầu dò và điền được giá vào").
//
// Máy chủ quyết dịch vụ nào có món kèm, giá mặc định, ai sửa được và khoá khi đã
// thu (`GET /luot-kham/visits/{id}/phu-thu`, `POST /luot-kham/orders/{id}/
// phu-thu`). Tick là vào hoá đơn DỊCH VỤ — thu cùng lần. Kho gắn sau.

import { useCallback, useEffect, useState } from "react";

import { docBang, guiThaoTac } from "../_lam-viec/api";
import { INPUT } from "../form-ui";

interface Mon {
  mau_id: string;
  ten: string;
  gia_mac_dinh: number | null;
  chon: boolean;
  don_gia: number | null;
  da_thu: boolean;
}

interface DichVu {
  order_id: string;
  dich_vu: string;
  mon: Mon[];
}

interface PhuThu {
  dich_vu: DichVu[];
  duoc_sua: boolean;
}

const so = (n: number | null) => (n == null ? "" : String(n));

export default function PhuThuKem({
  visitId,
  onDoi,
}: {
  visitId: string;
  onDoi?: () => void;
}) {
  const [pt, setPt] = useState<PhuThu | null>(null);
  const [gia, setGia] = useState<Record<string, string>>({});
  const [dangGui, setDangGui] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  const nap = useCallback(async () => {
    const kq = await docBang<PhuThu>("phu-thu", { luot: visitId });
    if (kq.ok) setPt(kq.data);
  }, [visitId]);

  useEffect(() => {
    // Nạp lần đầu khi mở lượt — dữ liệu từ máy chủ.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void nap();
  }, [nap]);

  if (!pt || pt.dich_vu.length === 0) return null;

  async function gui(d: DichVu, m: Mon, chon: boolean) {
    const khoa = `${d.order_id}:${m.mau_id}`;
    setDangGui(khoa);
    setLoi(null);
    const kq = await guiThaoTac("phu-thu", d.order_id, {
      mau_id: m.mau_id,
      chon,
      don_gia: gia[khoa] ?? so(m.don_gia ?? m.gia_mac_dinh),
    });
    setDangGui(null);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setPt(kq.data as unknown as PhuThu);
    onDoi?.();
  }

  return (
    <section className="space-y-2 rounded-control border border-line bg-surface p-3">
      <h3 className="text-body font-semibold text-ink">Món kèm dịch vụ</h3>
      {pt.dich_vu.map((d) => (
        <div key={d.order_id} className="space-y-1">
          <p className="text-meta text-ink-muted">{d.dich_vu}</p>
          {d.mon.map((m) => {
            const khoa = `${d.order_id}:${m.mau_id}`;
            const khoaTick = !pt.duoc_sua || m.da_thu || dangGui === khoa;
            return (
              <div key={khoa} className="flex flex-wrap items-center gap-3 px-1">
                <label className="flex min-h-10 flex-1 cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    checked={m.chon}
                    disabled={khoaTick}
                    onChange={(e) => void gui(d, m, e.target.checked)}
                    className="size-4 accent-brand-600"
                  />
                  <span className="text-body text-ink">{m.ten}</span>
                </label>
                <label className="flex items-center gap-2 text-meta text-ink-muted">
                  Giá
                  <input
                    inputMode="numeric"
                    value={gia[khoa] ?? so(m.don_gia ?? m.gia_mac_dinh)}
                    disabled={khoaTick}
                    onChange={(e) => setGia((g) => ({ ...g, [khoa]: e.target.value }))}
                    // Đang tick mà sửa giá: rời ô là lưu giá mới.
                    onBlur={() => {
                      if (m.chon && gia[khoa] !== undefined) void gui(d, m, true);
                    }}
                    className={`${INPUT} w-32 text-right`}
                    aria-label={`Giá ${m.ten}`}
                  />
                  đ
                </label>
                {m.da_thu ? (
                  <span className="text-meta text-ink-muted">Đã thu</span>
                ) : null}
              </div>
            );
          })}
        </div>
      ))}
      {loi ? <p className="text-meta text-danger">{loi}</p> : null}
    </section>
  );
}
