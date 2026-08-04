"use client";

// ConsultBoard — Tư vấn dùng thuốc (image_11).
// Dược sĩ xem đơn thuốc + hướng dẫn dùng, ghi chú tư vấn.

import { useMemo, useState } from "react";
import { VN_TZ } from "../../../../lib/datetime";

interface ConsultPatient {
  full_name: string | null;
  phone_primary: string | null;
}

interface ConsultRow {
  id: string;
  source_ref: string | null;
  drug_name_raw: string | null;
  dosage_instructions: string | null;
  quantity: string | null;
  quantity_note: string | null;
  caution: string | null;
  created_at: string | null;
  patient: ConsultPatient | null;
}

interface Props {
  records: ConsultRow[];
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("vi-VN", { timeZone: VN_TZ }) : "—";

export default function ConsultBoard({ records }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const selected = useMemo(
    () => records.find((r) => r.id === selectedId) ?? null,
    [records, selectedId],
  );

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
    <div className="grid h-full grid-cols-[minmax(300px,360px)_1fr] gap-4 p-4">
      {/* Cột trái: danh sách đơn chờ tư vấn */}
      <section className="flex flex-col rounded-control border border-line bg-surface">
        <div className="border-b border-line p-3">
          <h2 className="text-sm font-semibold text-ink">Chờ tư vấn</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {records.length} đơn · {filtered.length} hiển thị
          </p>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm tên BN / thuốc…"
            className="mt-2 w-full rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="p-4 text-sm text-ink-muted">Không có đơn chờ tư vấn.</p>
          ) : (
            filtered.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                className={`block w-full border-b border-line px-3 py-2.5 text-left transition-colors hover:bg-surface-muted ${
                  selectedId === r.id ? "bg-surface-selected" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink">
                    {r.patient?.full_name ?? "Chưa có tên"}
                  </span>
                  <span className="shrink-0 text-xs text-ink-faint">
                    {fmtDate(r.created_at)}
                  </span>
                </div>
                <div className="mt-0.5 truncate text-xs text-ink-muted">
                  {r.drug_name_raw ?? "—"}
                </div>
              </button>
            ))
          )}
        </div>
      </section>

      {/* Cột phải: chi tiết tư vấn */}
      <section className="overflow-y-auto">
        {selected ? (
          <div className="rounded-control border border-line bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-ink">
                  {selected.patient?.full_name ?? "Chưa có tên"}
                </h3>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {selected.patient?.phone_primary ?? "—"} ·{" "}
                  {selected.source_ref ?? "Chưa có mã đơn"}
                </p>
              </div>
              <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                {fmtDate(selected.created_at)}
              </span>
            </div>

            <div className="mt-4 rounded-control border border-line bg-surface-muted p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                Thuốc cần tư vấn
              </h4>
              <div className="mt-2 text-sm font-medium text-ink">
                {selected.drug_name_raw ?? "—"}
              </div>
              {selected.dosage_instructions && (
                <div className="mt-1 text-xs text-ink-muted">
                  Liều dùng: {selected.dosage_instructions}
                </div>
              )}
              <div className="mt-1 text-xs text-ink-muted">
                Số lượng: {selected.quantity ?? "—"}
                {selected.quantity_note ? ` (${selected.quantity_note})` : ""}
              </div>
            </div>

            {selected.caution && (
              <div className="mt-3 rounded-control border border-warning bg-warning-bg p-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-warning">
                  Lưu ý
                </h4>
                <p className="mt-1 text-sm text-ink">{selected.caution}</p>
              </div>
            )}

            <div className="mt-4 rounded-control border border-line bg-surface-muted p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                Hướng dẫn tư vấn
              </h4>
              <ul className="mt-2 space-y-1.5 text-sm text-ink">
                <li>• Giải thích cách dùng thuốc (liều, thời điểm, cách uống)</li>
                <li>• Nhắc tác dụng phụ thường gặp và khi nào cần báo bác sĩ</li>
                <li>• Kiểm tra dị ứng / thuốc đang dùng trùng tương tác</li>
                <li>• Xác nhận người bệnh đã hiểu trước khi bàn giao</li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center rounded-control border border-dashed border-line text-sm text-ink-faint">
            Chọn một đơn thuốc để tư vấn
          </div>
        )}
      </section>
    </div>
  );
}