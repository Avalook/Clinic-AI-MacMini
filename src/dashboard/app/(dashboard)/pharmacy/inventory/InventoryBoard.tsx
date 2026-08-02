"use client";

// InventoryBoard — Kho & tồn kho theo lô (image_9 phần kho).
// Bảng lô thuốc: mã lô, hạn dùng, tồn, đơn vị, giá nhập, trạng thái (còn hạn/sắp hết hạn/hết hạn).

import { useMemo, useState } from "react";

interface InvDrug {
  name_base: string | null;
  name_raw: string | null;
  variant: string | null;
}

interface InvBatch {
  id: string;
  batch_code: string;
  expiry_date: string;
  quantity_on_hand: number;
  unit: string;
  cost_price: number | null;
  received_at: string | null;
  drug: InvDrug | null;
}

interface Props {
  batches: InvBatch[];
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("vi-VN") : "—";

const fmtQty = (n: number) =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(n);

type ExpiryState = "ok" | "soon" | "expired";

function expiryState(b: InvBatch, nowMs: number): ExpiryState {
  const exp = +new Date(b.expiry_date);
  if (exp < nowMs) return "expired";
  const soon = nowMs + 90 * 24 * 60 * 60 * 1000; // 90 ngày
  return exp <= soon ? "soon" : "ok";
}

const STATE_LABEL: Record<ExpiryState, string> = {
  ok: "Còn hạn",
  soon: "Sắp hết hạn",
  expired: "Hết hạn",
};

export default function InventoryBoard({ batches }: Props) {
  const [filter, setFilter] = useState<"all" | ExpiryState>("all");
  const [search, setSearch] = useState("");
  // Lazy init — chạy đúng 1 lần khi mount, không gọi Date.now() trong render.
  const [nowMs] = useState(() => Date.now());

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return batches.filter((b) => {
      const state = expiryState(b, nowMs);
      if (filter !== "all" && state !== filter) return false;
      if (!q) return true;
      return (
        b.drug?.name_base?.toLowerCase().includes(q) ||
        b.drug?.name_raw?.toLowerCase().includes(q) ||
        b.batch_code.toLowerCase().includes(q)
      );
    });
  }, [batches, filter, search, nowMs]);

  const summary = useMemo(() => {
    let totalUnits = 0;
    let soonCount = 0;
    let expiredCount = 0;
    for (const b of batches) {
      totalUnits += b.quantity_on_hand;
      const s = expiryState(b, nowMs);
      if (s === "soon") soonCount++;
      if (s === "expired") expiredCount++;
    }
    return { totalUnits, soonCount, expiredCount };
  }, [batches, nowMs]);

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      {/* KPI */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-control border border-line bg-surface p-3">
          <div className="text-2xl font-semibold text-ink">{batches.length}</div>
          <div className="text-xs text-ink-muted">Lô thuốc</div>
        </div>
        <div className="rounded-control border border-line bg-surface p-3">
          <div className="text-2xl font-semibold text-ink">
            {fmtQty(summary.totalUnits)}
          </div>
          <div className="text-xs text-ink-muted">Tổng tồn (đơn vị)</div>
        </div>
        <div className="rounded-control border border-line bg-surface p-3">
          <div
            className={`text-2xl font-semibold ${
              summary.soonCount > 0 ? "text-warning" : "text-ink"
            }`}
          >
            {summary.soonCount}
          </div>
          <div className="text-xs text-ink-muted">Sắp hết hạn (≤90 ngày)</div>
        </div>
        <div className="rounded-control border border-line bg-surface p-3">
          <div
            className={`text-2xl font-semibold ${
              summary.expiredCount > 0 ? "text-danger" : "text-ink"
            }`}
          >
            {summary.expiredCount}
          </div>
          <div className="text-xs text-ink-muted">Hết hạn</div>
        </div>
      </div>

      {/* Filter + search */}
      <div className="flex flex-wrap items-center gap-2">
        {(["all", "ok", "soon", "expired"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              filter === f
                ? "bg-brand-600 text-white"
                : "bg-surface-muted text-ink-muted hover:bg-surface-selected"
            }`}
          >
            {f === "all" ? "Tất cả" : STATE_LABEL[f]}
          </button>
        ))}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Tìm thuốc / mã lô…"
          className="ml-auto w-56 rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
        />
      </div>

      {/* Bảng lô */}
      <div className="flex-1 overflow-auto rounded-control border border-line bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-surface-muted text-xs uppercase tracking-wide text-ink-muted">
            <tr>
              <th className="px-3 py-2">Thuốc</th>
              <th className="px-3 py-2">Mã lô</th>
              <th className="px-3 py-2">Hạn dùng</th>
              <th className="px-3 py-2 text-right">Tồn</th>
              <th className="px-3 py-2">Đơn vị</th>
              <th className="px-3 py-2 text-right">Giá nhập</th>
              <th className="px-3 py-2">Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-ink-muted">
                  Không có lô thuốc nào.
                </td>
              </tr>
            ) : (
              rows.map((b) => {
                const st = expiryState(b, nowMs);
                return (
                  <tr key={b.id} className="border-t border-line hover:bg-surface-muted">
                    <td className="px-3 py-2 font-medium text-ink">
                      {b.drug?.name_base ?? b.drug?.name_raw ?? "—"}
                      {b.drug?.variant ? ` (${b.drug.variant})` : ""}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{b.batch_code}</td>
                    <td className="px-3 py-2 text-ink-muted">{fmtDate(b.expiry_date)}</td>
                    <td className="px-3 py-2 text-right font-semibold text-ink">
                      {fmtQty(b.quantity_on_hand)}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{b.unit}</td>
                    <td className="px-3 py-2 text-right text-ink-muted">
                      {b.cost_price == null
                        ? "—"
                        : new Intl.NumberFormat("vi-VN", {
                            maximumFractionDigits: 0,
                          }).format(b.cost_price)}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          st === "ok"
                            ? "bg-success-bg text-success"
                            : st === "soon"
                              ? "bg-warning-bg text-warning"
                              : "bg-danger-bg text-danger"
                        }`}
                      >
                        {STATE_LABEL[st]}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-ink-faint">
        Ghi chú: thêm/nhập lô mới cần API backend (FastAPI service, service_role).
      </p>
    </div>
  );
}