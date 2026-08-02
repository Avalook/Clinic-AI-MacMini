"use client";

// HistoryBoard — Lịch sử bàn giao thuốc (image_10).
// Tra cứu bản ghi thuốc đã cấp cho từng bệnh nhân (read-only).

import { useMemo, useState } from "react";

interface HistPatient {
  full_name: string | null;
  phone_primary: string | null;
}

interface HistRow {
  id: string;
  source_ref: string | null;
  drug_name_raw: string | null;
  dosage_instructions: string | null;
  quantity: string | null;
  quantity_note: string | null;
  created_at: string | null;
  patient: HistPatient | null;
}

interface Props {
  records: HistRow[];
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "—";

export default function HistoryBoard({ records }: Props) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return records;
    return records.filter(
      (r) =>
        r.patient?.full_name?.toLowerCase().includes(q) ||
        r.drug_name_raw?.toLowerCase().includes(q) ||
        r.source_ref?.toLowerCase().includes(q),
    );
  }, [records, search]);

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Lịch sử bàn giao thuốc</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {records.length} bản ghi · {filtered.length} hiển thị
          </p>
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Tìm tên BN / thuốc / mã đơn…"
          className="w-64 rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
        />
      </div>

      <div className="flex-1 overflow-auto rounded-control border border-line bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-surface-muted text-xs uppercase tracking-wide text-ink-muted">
            <tr>
              <th className="px-3 py-2">Bệnh nhân</th>
              <th className="px-3 py-2">Thuốc</th>
              <th className="px-3 py-2">Liều dùng</th>
              <th className="px-3 py-2 text-right">SL</th>
              <th className="px-3 py-2">Mã đơn</th>
              <th className="px-3 py-2">Thời điểm</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-ink-muted">
                  Không có bản ghi nào.
                </td>
              </tr>
            ) : (
              filtered.map((r) => (
                <tr key={r.id} className="border-t border-line hover:bg-surface-muted">
                  <td className="px-3 py-2 font-medium text-ink">
                    {r.patient?.full_name ?? "—"}
                    {r.patient?.phone_primary ? (
                      <span className="ml-1 text-xs text-ink-faint">
                        {r.patient.phone_primary}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-ink">{r.drug_name_raw ?? "—"}</td>
                  <td className="px-3 py-2 text-ink-muted">
                    {r.dosage_instructions ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right text-ink">
                    {r.quantity ?? "—"}
                    {r.quantity_note ? ` (${r.quantity_note})` : ""}
                  </td>
                  <td className="px-3 py-2 text-ink-muted">{r.source_ref ?? "—"}</td>
                  <td className="px-3 py-2 text-ink-muted">{fmtDate(r.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}