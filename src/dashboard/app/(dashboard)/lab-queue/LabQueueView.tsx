"use client";

// Hàng đợi xét nghiệm: dữ liệu vẫn là lab_result qua RLS và chỉ lưu qua
// /api/lab-result. Bố cục ba vùng theo workspace lâm sàng không tạo thêm KQ giả.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CircleAlert,
  ExternalLink,
  FileCheck2,
  FileText,
  FlaskConical,
  Search,
} from "lucide-react";

import { fmtDateTimeOrDate } from "../../../lib/datetime";
import { toHref } from "../../../lib/url";
import { INPUT, LABEL } from "../form-ui";
import {
  EmptyWorkspace,
  Monogram,
  PanelHeading,
  WorkspaceMetric,
  WorkspaceMetricRow,
} from "../tasks/WorkspacePrimitives";
import workspaceStyles from "../tasks/WorkspacePrimitives.module.css";

export interface LabRow {
  lab_result_id: string;
  test_name: string;
  result_value: string | null;
  external_ref: string | null;
  lab_provider: string | null;
  result_received_at: string | null;
  created_at: string | null;
  patient: {
    full_name: string;
    patient_code: string;
    phone_primary: string | null;
  } | null;
}

function patientLabel(row: LabRow): string {
  return row.patient?.full_name ?? "Chưa gắn người bệnh";
}

function LabResultEditor({ row }: { row: LabRow }) {
  const router = useRouter();
  const [summary, setSummary] = useState("");
  const [link, setLink] = useState("");
  const [provider, setProvider] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    if (!summary.trim() && !link.trim()) {
      setErr("Nhập tóm tắt hoặc dán link phiếu.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const response = await fetch("/api/lab-result", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lab_result_id: row.lab_result_id,
          result_value: summary,
          result_link: link,
          lab_provider: provider,
        }),
      });
      if (!response.ok) {
        setErr((await response.json().catch(() => ({})))?.error ?? "Lỗi lưu kết quả.");
        return;
      }
      router.refresh();
    } catch {
      setErr("Không kết nối được máy chủ. Vui lòng thử lại.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 p-4">
      <div className="rounded-control border border-line bg-surface-muted p-3">
        <div className="flex items-start gap-3">
          <Monogram value={row.patient?.full_name} />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">{patientLabel(row)}</p>
            <p className="mt-0.5 text-xs text-ink-muted">
              {row.patient?.patient_code ?? "Chưa có mã BN"}
              {row.patient?.phone_primary ? ` · ${row.patient.phone_primary}` : ""}
            </p>
            <p className="mt-2 text-sm font-medium text-brand-800">{row.test_name}</p>
          </div>
        </div>
      </div>

      <div>
        <label className={LABEL} htmlFor={`lab-summary-${row.lab_result_id}`}>Tóm tắt kết quả</label>
        <input
          id={`lab-summary-${row.lab_result_id}`}
          className={INPUT}
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          placeholder="Ví dụ: HPV âm tính, chưa phát hiện bất thường…"
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className={LABEL} htmlFor={`lab-link-${row.lab_result_id}`}>Link phiếu (PDF / Drive)</label>
          <input
            id={`lab-link-${row.lab_result_id}`}
            className={INPUT}
            value={link}
            onChange={(event) => setLink(event.target.value)}
            placeholder="https://…"
            inputMode="url"
          />
        </div>
        <div>
          <label className={LABEL} htmlFor={`lab-provider-${row.lab_result_id}`}>Nhà cung cấp lab</label>
          <input
            id={`lab-provider-${row.lab_result_id}`}
            className={INPUT}
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
            placeholder="Tên nhà cung cấp (nếu có)"
          />
        </div>
      </div>
      {err ? <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-xs text-danger">{err}</p> : null}
      <button
        type="button"
        onClick={save}
        disabled={busy}
        className="inline-flex min-h-10 items-center gap-2 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
      >
        <FileCheck2 className="size-4" /> {busy ? "Đang lưu…" : "Lưu kết quả"}
      </button>
    </div>
  );
}

export default function LabQueueView({
  pending,
  done,
}: {
  pending: LabRow[];
  done: LabRow[];
}) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const normalizedQuery = query.trim().toLocaleLowerCase("vi-VN");
  const visiblePending = useMemo(
    () =>
      pending.filter((row) =>
        !normalizedQuery
          ? true
          : [row.test_name, row.patient?.full_name, row.patient?.patient_code]
              .filter(Boolean)
              .some((value) => value?.toLocaleLowerCase("vi-VN").includes(normalizedQuery)),
      ),
    [normalizedQuery, pending],
  );
  const selected = visiblePending.find((row) => row.lab_result_id === selectedId) ?? visiblePending[0] ?? null;
  const withExternalFile = done.filter((row) => Boolean(toHref(row.external_ref))).length;

  return (
    <div className="space-y-4">
      <WorkspaceMetricRow>
        <WorkspaceMetric label="Chờ nhập kết quả" value={pending.length} icon={<FlaskConical className="size-5" />} tone="warning" />
        <WorkspaceMetric label="Đã trả gần đây" value={done.length} icon={<FileCheck2 className="size-5" />} tone="success" />
        <WorkspaceMetric label="Có phiếu đính kèm" value={withExternalFile} icon={<FileText className="size-5" />} tone="brand" />
        <WorkspaceMetric label="Cần chọn để nhập" value={visiblePending.length} icon={<CircleAlert className="size-5" />} tone={visiblePending.length ? "neutral" : "success"} />
      </WorkspaceMetricRow>

      <div className={workspaceStyles.workspace}>
      <div className={`${workspaceStyles.threeColumn} ${workspaceStyles.lab}`}>
        <aside
          aria-label="Danh sách xét nghiệm"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Danh sách xét nghiệm" detail={`${visiblePending.length} kết quả chưa nhập`} />
          <div className="border-b border-line p-3">
            <label className="flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Tìm xét nghiệm, bệnh nhân hoặc mã BN</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm xét nghiệm, bệnh nhân"
                className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
              />
            </label>
          </div>
          <div className="max-h-[620px] overflow-y-auto">
            {visiblePending.length ? (
              visiblePending.map((row) => (
                <button
                  type="button"
                  key={row.lab_result_id}
                  onClick={() => setSelectedId(row.lab_result_id)}
                  aria-current={row.lab_result_id === selected?.lab_result_id ? "true" : undefined}
                  className={`w-full border-l-[3px] px-3 py-3 text-left transition-colors ${
                    row.lab_result_id === selected?.lab_result_id
                      ? "border-brand-500 bg-surface-selected"
                      : "border-transparent bg-surface hover:bg-surface-sunken"
                  }`}
                >
                  <span className="flex gap-2.5">
                    <Monogram value={row.patient?.full_name} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-ink">{patientLabel(row)}</span>
                      <span className="mt-0.5 block truncate text-xs text-ink-muted">{row.patient?.patient_code ?? "Chưa có mã BN"}</span>
                      <span className="mt-1 block truncate text-xs text-brand-800">{row.test_name}</span>
                    </span>
                  </span>
                </button>
              ))
            ) : (
              <EmptyWorkspace title="Không có kết quả phù hợp" detail="Thử đổi từ khóa tìm kiếm hoặc chờ chỉ định mới từ bác sĩ." icon={<FlaskConical className="size-7" />} />
            )}
          </div>
        </aside>

        <section
          aria-label="Nhập kết quả xét nghiệm"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Nhập kết quả xét nghiệm" detail="Nhập tóm tắt và/hoặc liên kết phiếu do lab gửi." />
          {selected ? (
            <LabResultEditor key={selected.lab_result_id} row={selected} />
          ) : (
            <div className="p-4"><EmptyWorkspace title="Chưa có kết quả để nhập" detail="Khi có chỉ định xét nghiệm chưa trả, nó sẽ xuất hiện trong danh sách bên trái." icon={<FlaskConical className="size-7" />} /></div>
          )}
        </section>

        <aside
          aria-label="Kết quả đã trả"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Kết quả đã trả" detail={`${done.length} bản ghi gần đây`} />
          <div className="max-h-[690px] space-y-2 overflow-y-auto p-2.5">
            {done.length ? (
              done.map((row) => {
                const href = toHref(row.external_ref);
                return (
                  <article key={row.lab_result_id} className="rounded-control border border-line bg-surface p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-ink">{row.test_name}</p>
                        <p className="mt-0.5 truncate text-xs text-ink-muted">{patientLabel(row)} · {row.patient?.patient_code ?? "Chưa có mã"}</p>
                      </div>
                      {href ? (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex shrink-0 items-center gap-1 rounded-chip bg-brand-50 px-2 py-1 text-xs font-medium text-brand-800 hover:bg-brand-100">
                          <ExternalLink className="size-3" /> Phiếu
                        </a>
                      ) : null}
                    </div>
                    {row.result_value ? <p className="mt-2 text-xs leading-5 text-ink-soft">{row.result_value}</p> : null}
                    {row.lab_provider ? <p className="mt-1 text-xs text-ink-muted">{row.lab_provider}</p> : null}
                    <p className="mt-2 text-[11px] text-ink-faint">{fmtDateTimeOrDate(row.result_received_at)}</p>
                  </article>
                );
              })
            ) : (
              <EmptyWorkspace title="Chưa có kết quả đã trả" detail="Các bản ghi có tóm tắt hoặc phiếu đính kèm sẽ xuất hiện tại đây." icon={<FileCheck2 className="size-7" />} />
            )}
          </div>
        </aside>
      </div>
      </div>
    </div>
  );
}
