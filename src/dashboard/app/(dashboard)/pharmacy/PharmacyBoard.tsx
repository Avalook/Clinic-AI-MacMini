"use client";

// Màn Nhà thuốc (contract tiền–thuốc CP4, 19/09/2026).
//
// Theo LƯỢT KHÁM, không theo từng dòng đơn: tiền thuốc thu theo lượt, nên giai
// đoạn (chờ khám xong → chọn lô → chờ xác minh → đã thu, giao) cũng là của lượt.
// Giai đoạn và các nút được phép đến từ máy chủ; ở đây chỉ vẽ.

import { useMemo, useState } from "react";
import Button from "@/components/ui/Button";
import StatusChip from "@/components/ui/StatusChip";
import XemLuot from "../_lam-viec/XemLuot";
import DongThuoc from "./DongThuoc";
import { GIAI_DOAN, type LuotThuoc, type ManNhaThuoc } from "./ban-thuoc";

type Tab = "dang_lam" | "xong";

const xongHet = (l: LuotThuoc) => l.dong.every((d) => d.closed);

export default function PharmacyBoard({ man }: { man: ManNhaThuoc }) {
  const [chon, setChon] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("dang_lam");
  const [tim, setTim] = useState("");
  const [xemLuot, setXemLuot] = useState<string | null>(null);

  const dem = useMemo(
    () => ({
      dang_lam: man.luot.filter((l) => !xongHet(l)).length,
      xong: man.luot.filter(xongHet).length,
    }),
    [man.luot],
  );
  const danhSach = useMemo(() => {
    const q = tim.trim().toLowerCase();
    return man.luot
      .filter((l) => (tab === "xong" ? xongHet(l) : !xongHet(l)))
      .filter(
        (l) =>
          !q ||
          l.ten_khach?.toLowerCase().includes(q) ||
          l.patient_code?.toLowerCase().includes(q) ||
          l.dong.some((d) => d.drug_name_raw?.toLowerCase().includes(q)),
      );
  }, [man.luot, tab, tim]);
  const luot = man.luot.find((l) => l.visit_id === chon) ?? null;

  return (
    <div className="grid h-full grid-cols-1 gap-4 p-4 lg:grid-cols-3">
      {/* ── Danh sách lượt ── */}
      <section className="flex flex-col rounded-card border border-line bg-surface lg:col-span-1">
        <div className="border-b border-line p-3">
          <h2 className="text-emph font-semibold text-ink">Đơn thuốc</h2>
          <div role="tablist" aria-label="Nhóm lượt" className="mt-2 flex flex-wrap gap-1">
            {(
              [
                ["dang_lam", "Đang xử lý"],
                ["xong", "Xong hôm nay"],
              ] as const
            ).map(([ma, nhan]) => (
              <Button
                key={ma}
                size="sm"
                role="tab"
                aria-selected={tab === ma}
                variant={tab === ma ? "primary" : "ghost"}
                onClick={() => setTab(ma)}
              >
                {nhan} ({dem[ma]})
              </Button>
            ))}
          </div>
          <input
            value={tim}
            onChange={(e) => setTim(e.target.value)}
            placeholder="Tìm tên / mã khách / thuốc…"
            aria-label="Tìm đơn thuốc"
            className="mt-2 w-full rounded-control border border-line bg-surface-muted px-3 py-2 text-body text-ink outline-none focus:border-brand-500"
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {danhSach.length === 0 ? (
            <p className="p-4 text-body text-ink-muted">Không có lượt nào.</p>
          ) : (
            danhSach.map((l) => {
              const gd = GIAI_DOAN[l.giai_doan];
              return (
                <button
                  key={l.visit_id}
                  type="button"
                  onClick={() => setChon(l.visit_id)}
                  className={`block min-h-10 w-full border-b border-line px-3 py-2 text-left transition-colors hover:bg-surface-muted ${
                    chon === l.visit_id ? "bg-surface-selected" : ""
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-emph font-medium text-ink">
                      {l.ten_khach ?? "Chưa có tên"}
                    </span>
                    <StatusChip tone={xongHet(l) ? "completed" : gd.tone} label={xongHet(l) ? "Xong" : gd.nhan} />
                  </div>
                  <div className="mt-1 truncate text-meta text-ink-muted">
                    {l.patient_code ?? "—"} · {l.dong.length} thuốc:{" "}
                    {l.dong.map((d) => d.drug_name_raw ?? "—").join(", ")}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </section>

      {/* ── Chi tiết lượt ── */}
      <section className="flex flex-col gap-3 overflow-y-auto lg:col-span-2">
        {luot ? (
          <div className="space-y-3 rounded-card border border-line bg-surface p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h3 className="text-title font-semibold text-ink">
                  {luot.ten_khach ?? "Chưa có tên"}
                </h3>
                <p className="text-meta text-ink-muted">
                  {luot.patient_code ?? "—"} · {luot.phone ?? "—"}
                </p>
              </div>
              <StatusChip
                size="md"
                tone={GIAI_DOAN[luot.giai_doan].tone}
                label={GIAI_DOAN[luot.giai_doan].nhan}
              />
            </div>
            <p className="rounded-control bg-surface-muted px-3 py-2 text-meta text-ink-soft">
              {GIAI_DOAN[luot.giai_doan].giai_thich}
            </p>
            <Button size="sm" variant="ghost" onClick={() => setXemLuot(luot.visit_id)}>
              Xem chi tiết lượt &amp; lịch sử cấp
            </Button>
            {xemLuot ? <XemLuot visitId={xemLuot} onDong={() => setXemLuot(null)} /> : null}
            {luot.dong.map((d) => (
              <DongThuoc key={`${d.id}-${luot.giai_doan}`} dong={d} danhMuc={man.danh_muc} />
            ))}
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center rounded-card border border-dashed border-line p-6 text-body text-ink-faint">
            Chọn một lượt để xem đơn thuốc
          </div>
        )}
      </section>
    </div>
  );
}
