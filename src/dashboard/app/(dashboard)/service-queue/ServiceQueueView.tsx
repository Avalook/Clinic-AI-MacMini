"use client";

// Hàng đợi dịch vụ / thủ thuật. Mutation giữ nguyên contract /api/service-log;
// phần mới chỉ tổ chức lại thành list → workspace thực hiện → lịch sử.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  ClipboardList,
  Clock3,
  FileCheck2,
  Play,
  Plus,
  Search,
  Stethoscope,
} from "lucide-react";

import { fmtDateTimeOrDate, fmtTime, isVnMidnight } from "../../../lib/datetime";
import { canFinishService } from "../../../lib/clinical-workspace-policy";
import { INPUT, LABEL } from "../form-ui";
import {
  EmptyWorkspace,
  Monogram,
  PanelHeading,
  WorkspaceMetric,
  WorkspaceMetricRow,
} from "../tasks/WorkspacePrimitives";
import workspaceStyles from "../tasks/WorkspacePrimitives.module.css";

export interface ServiceRow {
  id: string;
  service_name_raw: string | null;
  status: string | null;
  result_text: string | null;
  performer_text: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  patient: { full_name: string; patient_code: string } | null;
}

function patientLabel(row: ServiceRow): string {
  return row.patient?.full_name ?? "Chưa gắn người bệnh";
}

function ServiceExecutionEditor({ row }: { row: ServiceRow }) {
  const router = useRouter();
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const started = Boolean(row.started_at);
  const canFinish = canFinishService(row.started_at);

  async function act(action: "start" | "finish") {
    if (action === "finish" && !canFinish) {
      setErr("Cần bắt đầu dịch vụ trước khi hoàn tất.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const response = await fetch("/api/service-log", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: row.id, action, result_text: result }),
      });
      if (!response.ok) {
        setErr((await response.json().catch(() => ({})))?.error ?? "Lỗi cập nhật.");
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
      <div className="rounded-control border border-line bg-surface-muted p-3.5">
        <div className="flex items-start gap-3">
          <Monogram value={row.patient?.full_name} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink">{patientLabel(row)}</p>
            <p className="mt-0.5 text-xs text-ink-muted">{row.patient?.patient_code ?? "Chưa có mã BN"}</p>
            <p className="mt-2 text-base font-semibold text-brand-800">{row.service_name_raw ?? "Chưa có tên dịch vụ"}</p>
            <p className="mt-1 text-xs text-ink-muted">
              {row.performer_text ? `Người thực hiện: ${row.performer_text}` : "Chưa ghi người thực hiện"}
            </p>
          </div>
          <span className={`rounded-chip px-2 py-1 text-xs font-medium ${started ? "bg-status-in-progress-bg text-status-in-progress" : "bg-surface-sunken text-ink-muted"}`}>
            {started ? "Đang thực hiện" : "Chờ thực hiện"}
          </span>
        </div>
        {started ? (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-ink-muted">
            <Clock3 className="size-3.5" /> Bắt đầu: {isVnMidnight(row.started_at) ? "Chưa có giờ hợp lệ" : fmtTime(row.started_at)}
          </p>
        ) : null}
      </div>

      {started ? (
        <div>
          <label className={LABEL} htmlFor={`service-result-${row.id}`}>Kết quả / ghi chú khi hoàn tất</label>
          <textarea
            id={`service-result-${row.id}`}
            className={`${INPUT} min-h-24 resize-y`}
            value={result}
            onChange={(event) => setResult(event.target.value)}
            placeholder="Nhập kết quả hoặc ghi chú thực hiện"
          />
        </div>
      ) : (
        <p className="rounded-control border border-dashed border-line-strong bg-surface-muted px-3 py-3 text-xs leading-5 text-ink-muted">
          Bắt đầu để ghi mốc thời gian thực hiện. Kết quả chỉ được nhập trong bước hoàn tất.
        </p>
      )}

      {err ? <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-xs text-danger">{err}</p> : null}
      <div className="flex flex-wrap gap-2">
        {!started ? (
          <button
            type="button"
            onClick={() => act("start")}
            disabled={busy}
            className="inline-flex min-h-10 items-center gap-2 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            <Play className="size-4" /> Bắt đầu
          </button>
        ) : null}
        {canFinish ? (
          <button
            type="button"
            onClick={() => act("finish")}
            disabled={busy}
            className="inline-flex min-h-10 items-center gap-2 rounded-control border border-success bg-surface px-4 text-sm font-semibold text-success hover:bg-success-bg disabled:opacity-50"
          >
            <Check className="size-4" /> {busy ? "Đang cập nhật…" : "Hoàn tất"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function CreateServiceForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [patientCode, setPatientCode] = useState("");
  const [performer, setPerformer] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    if (!name.trim()) {
      setErr("Nhập tên dịch vụ.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const response = await fetch("/api/service-log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_name: name,
          patient_code: patientCode,
          performer,
        }),
      });
      if (!response.ok) {
        setErr((await response.json().catch(() => ({})))?.error ?? "Lỗi tạo việc.");
        return;
      }
      setName("");
      setPatientCode("");
      setPerformer("");
      router.refresh();
    } catch {
      setErr("Không kết nối được máy chủ. Vui lòng thử lại.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3 p-3.5">
      <div>
        <label className={LABEL} htmlFor="service-name">Tên dịch vụ / thủ thuật *</label>
        <input id="service-name" className={INPUT} value={name} onChange={(event) => setName(event.target.value)} placeholder="Ví dụ: Thủ thuật hoặc dịch vụ" />
      </div>
      <div>
        <label className={LABEL} htmlFor="service-patient-code">Mã BN (nếu có)</label>
        <input id="service-patient-code" className={INPUT} value={patientCode} onChange={(event) => setPatientCode(event.target.value)} placeholder="Mã bệnh nhân" />
      </div>
      <div>
        <label className={LABEL} htmlFor="service-performer">Người làm</label>
        <input id="service-performer" className={INPUT} value={performer} onChange={(event) => setPerformer(event.target.value)} placeholder="Tên điều dưỡng / KTV" />
      </div>
      {err ? <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-xs text-danger">{err}</p> : null}
      <button type="button" onClick={create} disabled={busy} className="inline-flex min-h-10 items-center gap-2 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50">
        <Plus className="size-4" /> {busy ? "Đang tạo…" : "Thêm việc"}
      </button>
    </div>
  );
}

export default function ServiceQueueView({
  active,
  done,
}: {
  active: ServiceRow[];
  done: ServiceRow[];
}) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const normalizedQuery = query.trim().toLocaleLowerCase("vi-VN");
  const visibleActive = useMemo(
    () =>
      active.filter((row) =>
        !normalizedQuery
          ? true
          : [row.service_name_raw, row.patient?.full_name, row.patient?.patient_code, row.performer_text]
              .filter(Boolean)
              .some((value) => value?.toLocaleLowerCase("vi-VN").includes(normalizedQuery)),
      ),
    [active, normalizedQuery],
  );
  const selected = visibleActive.find((row) => row.id === selectedId) ?? visibleActive[0] ?? null;
  const inProgress = active.filter((row) => Boolean(row.started_at)).length;

  return (
    <div className="space-y-4">
      <WorkspaceMetricRow>
        <WorkspaceMetric label="Chờ thực hiện" value={active.length - inProgress} icon={<ClipboardList className="size-5" />} tone="brand" />
        <WorkspaceMetric label="Đang thực hiện" value={inProgress} icon={<Stethoscope className="size-5" />} tone={inProgress ? "warning" : "neutral"} />
        <WorkspaceMetric label="Hoàn tất gần đây" value={done.length} icon={<FileCheck2 className="size-5" />} tone="success" />
        <WorkspaceMetric label="Hiển thị trong hàng đợi" value={visibleActive.length} icon={<Search className="size-5" />} tone="neutral" />
      </WorkspaceMetricRow>

      <div className={workspaceStyles.workspace}>
      <div className={`${workspaceStyles.threeColumn} ${workspaceStyles.service}`}>
        <aside
          aria-label="Danh sách dịch vụ"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Danh sách dịch vụ" detail={`${visibleActive.length} việc đang chờ hoặc thực hiện`} />
          <div className="border-b border-line p-3">
            <label className="flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Tìm dịch vụ, bệnh nhân hoặc người thực hiện</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm dịch vụ, bệnh nhân" className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint" />
            </label>
          </div>
          <div className="max-h-[620px] overflow-y-auto">
            {visibleActive.length ? (
              visibleActive.map((row) => {
                const started = Boolean(row.started_at);
                return (
                  <button
                    type="button"
                    key={row.id}
                    onClick={() => setSelectedId(row.id)}
                    aria-current={row.id === selected?.id ? "true" : undefined}
                    className={`w-full border-l-[3px] px-3 py-3 text-left transition-colors ${
                      row.id === selected?.id ? "border-brand-500 bg-surface-selected" : "border-transparent bg-surface hover:bg-surface-sunken"
                    }`}
                  >
                    <span className="flex gap-2.5">
                      <Monogram value={row.patient?.full_name} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-ink">{row.service_name_raw ?? "Chưa có tên dịch vụ"}</span>
                        <span className="mt-0.5 block truncate text-xs text-ink-muted">{patientLabel(row)} · {row.patient?.patient_code ?? "Chưa có mã"}</span>
                        <span className={`mt-1 inline-flex rounded-chip px-1.5 py-0.5 text-[11px] font-medium ${started ? "bg-status-in-progress-bg text-status-in-progress" : "bg-surface-sunken text-ink-muted"}`}>
                          {started ? "Đang thực hiện" : "Chờ thực hiện"}
                        </span>
                      </span>
                    </span>
                  </button>
                );
              })
            ) : (
              <EmptyWorkspace title="Không có việc phù hợp" detail="Thử đổi từ khóa tìm kiếm hoặc tạo một việc dịch vụ mới." icon={<Search className="size-7" />} />
            )}
          </div>
        </aside>

        <section
          aria-label="Thực hiện dịch vụ"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Thực hiện dịch vụ" detail="Bắt đầu để ghi mốc, hoàn tất để lưu kết quả hoặc ghi chú." />
          {selected ? (
            <ServiceExecutionEditor key={selected.id} row={selected} />
          ) : (
            <div className="p-4"><EmptyWorkspace title="Chưa có việc được chọn" detail="Chọn một dịch vụ ở cột bên trái để thao tác." icon={<Stethoscope className="size-7" />} /></div>
          )}
        </section>

        <aside
          aria-label="Dịch vụ đã hoàn tất"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Tạo việc dịch vụ" detail="Tạo một dòng mới qua API hiện có." />
          <CreateServiceForm />
          <div className="border-y border-line"><PanelHeading title="Dịch vụ đã hoàn tất" detail={`${done.length} việc gần đây`} /></div>
          <div className="max-h-[360px] space-y-2 overflow-y-auto p-2.5">
            {done.length ? (
              done.map((row) => (
                <article key={row.id} className="rounded-control border border-line bg-surface p-3">
                  <p className="truncate text-sm font-semibold text-ink">{row.service_name_raw ?? "Chưa có tên dịch vụ"}</p>
                  <p className="mt-0.5 truncate text-xs text-ink-muted">{patientLabel(row)} · {row.patient?.patient_code ?? "Chưa có mã"}</p>
                  {row.result_text ? <p className="mt-2 text-xs leading-5 text-ink-soft">{row.result_text}</p> : null}
                  <p className="mt-2 text-[11px] text-ink-faint">{fmtDateTimeOrDate(row.finished_at)}</p>
                </article>
              ))
            ) : (
              <EmptyWorkspace title="Chưa có việc hoàn tất" detail="Các dịch vụ được đánh dấu hoàn tất sẽ xuất hiện ở đây." icon={<FileCheck2 className="size-7" />} />
            )}
          </div>
        </aside>
      </div>
      </div>
    </div>
  );
}
