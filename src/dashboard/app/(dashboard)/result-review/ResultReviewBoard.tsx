"use client";

// ResultReviewBoard — Duyệt kết quả (image_9 + image_3).
// Hàng đợi kết quả XN chờ bác sĩ duyệt. Ký duyệt / trả lại chỉnh sửa.

import { useMemo, useState } from "react";

interface ReviewPatient {
  full_name: string | null;
  phone_primary: string | null;
}

interface ReviewRow {
  lab_result_id: string;
  test_code: string;
  test_name: string;
  result_value: string | null;
  result_numeric: number | null;
  result_unit: string | null;
  reference_range_low: number | null;
  reference_range_high: number | null;
  flag: string | null;
  triage_group: string | null;
  requires_doctor_review: boolean;
  is_finalized: boolean;
  result_received_at: string;
  patient: ReviewPatient | null;
}

interface Props {
  results: ReviewRow[];
}

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

const FLAG_LABEL: Record<string, string> = {
  NORMAL: "Bình thường",
  HIGH: "Cao",
  LOW: "Thấp",
  CRITICAL_HIGH: "Cao nguy kịch",
  CRITICAL_LOW: "Thấp nguy kịch",
  ABNORMAL: "Bất thường",
};

export default function ResultReviewBoard({ results }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const selected = useMemo(
    () => results.find((r) => r.lab_result_id === selectedId) ?? null,
    [results, selectedId],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return results;
    return results.filter(
      (r) =>
        r.patient?.full_name?.toLowerCase().includes(q) ||
        r.test_name.toLowerCase().includes(q) ||
        r.test_code.toLowerCase().includes(q),
    );
  }, [results, search]);

  return (
    <div className="grid h-full grid-cols-[minmax(320px,400px)_1fr] gap-4 p-4">
      {/* Cột trái: hàng đợi */}
      <section className="flex flex-col rounded-control border border-line bg-surface">
        <div className="border-b border-line p-3">
          <h2 className="text-sm font-semibold text-ink">Chờ duyệt</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {results.length} kết quả · {filtered.length} hiển thị
          </p>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm BN / xét nghiệm…"
            className="mt-2 w-full rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="p-4 text-sm text-ink-muted">Không có kết quả chờ duyệt.</p>
          ) : (
            filtered.map((r) => (
              <button
                key={r.lab_result_id}
                onClick={() => setSelectedId(r.lab_result_id)}
                className={`block w-full border-b border-line px-3 py-2.5 text-left transition-colors hover:bg-surface-muted ${
                  selectedId === r.lab_result_id ? "bg-surface-selected" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink">
                    {r.patient?.full_name ?? "Chưa có tên"}
                  </span>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      r.flag === "CRITICAL_HIGH" || r.flag === "CRITICAL_LOW"
                        ? "bg-danger-bg text-danger"
                        : r.flag && r.flag !== "NORMAL"
                          ? "bg-warning-bg text-warning"
                          : "bg-success-bg text-success"
                    }`}
                  >
                    {FLAG_LABEL[r.flag ?? ""] ?? r.flag ?? "—"}
                  </span>
                </div>
                <div className="mt-0.5 truncate text-xs text-ink-muted">
                  {r.test_name} · {r.result_value ?? r.result_numeric ?? "—"}
                  {r.result_unit ? ` ${r.result_unit}` : ""}
                </div>
                <div className="mt-0.5 text-xs text-ink-faint">
                  {fmtDate(r.result_received_at)}
                </div>
              </button>
            ))
          )}
        </div>
      </section>

      {/* Cột phải: chi tiết + hành động */}
      <section className="overflow-y-auto">
        {selected ? (
          <div className="rounded-control border border-line bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-ink">
                  {selected.patient?.full_name ?? "Chưa có tên"}
                </h3>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {selected.patient?.phone_primary ?? "—"} · {selected.test_code}
                </p>
              </div>
              <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                {selected.triage_group ?? "PENDING"}
              </span>
            </div>

            <div className="mt-4 rounded-control border border-line bg-surface-muted p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                {selected.test_name}
              </h4>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-semibold text-ink">
                  {selected.result_value ?? selected.result_numeric ?? "—"}
                </span>
                {selected.result_unit && (
                  <span className="text-sm text-ink-muted">
                    {selected.result_unit}
                  </span>
                )}
              </div>
              {(selected.reference_range_low != null ||
                selected.reference_range_high != null) && (
                <div className="mt-1 text-xs text-ink-muted">
                  Tham chiếu: {selected.reference_range_low ?? "—"} –{" "}
                  {selected.reference_range_high ?? "—"}
                </div>
              )}
              {selected.flag && (
                <div className="mt-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      selected.flag === "CRITICAL_HIGH" ||
                      selected.flag === "CRITICAL_LOW"
                        ? "bg-danger-bg text-danger"
                        : selected.flag !== "NORMAL"
                          ? "bg-warning-bg text-warning"
                          : "bg-success-bg text-success"
                    }`}
                  >
                    {FLAG_LABEL[selected.flag] ?? selected.flag}
                  </span>
                </div>
              )}
            </div>

            <div className="mt-4 flex gap-2">
              <button className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700">
                Ký duyệt & cho phép trả kết quả
              </button>
              <button className="rounded-control border border-line bg-surface px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-surface-muted">
                Trả lại chỉnh sửa
              </button>
            </div>
            <p className="mt-2 text-xs text-ink-faint">
              Ghi chú: hành động ký duyệt cần API backend (FastAPI service) để
              cập nhật is_finalized + reviewed_by_staff_id.
            </p>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center rounded-control border border-dashed border-line text-sm text-ink-faint">
            Chọn một kết quả để duyệt
          </div>
        )}
      </section>
    </div>
  );
}