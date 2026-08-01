"use client";

// Điều phối siêu âm / xét nghiệm. service_log hiện chưa có phòng SA1–SA3 hay
// SLA, vì vậy UI không giả lập phân phòng; chỉ render các mốc thực có trong dữ liệu.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  ClipboardList,
  Clock3,
  FlaskConical,
  PauseCircle,
  Play,
  Printer,
  Search,
  Stethoscope,
  Trash2,
  X,
} from "lucide-react";

import StatusChip, { type StatusTone } from "../../../components/ui/StatusChip";
import Stepper, { type Step } from "../../../components/ui/Stepper";
import { fmtTime } from "../../../lib/datetime";
import {
  resolveSaWorkflowStatus,
  sonoPatientDisplayName,
  type SaWorkflowStatus,
} from "../../../lib/clinical-workspace-policy";
import { INPUT, LABEL } from "../form-ui";
import {
  EmptyWorkspace,
  Monogram,
  PanelHeading,
  WorkspaceMetric,
  WorkspaceMetricRow,
} from "../tasks/WorkspacePrimitives";
import workspaceStyles from "../tasks/WorkspacePrimitives.module.css";

export interface SonoRow {
  id: string;
  kind: "SA" | "XN";
  service_name_raw: string | null;
  status: string | null;
  result_text: string | null;
  started_at: string | null;
  sent_to_lab_at: string | null;
  finished_at: string | null;
  created_at: string;
  patient: { full_name: string | null; patient_code: string | null } | null;
}

type QueueKind = "SA" | "XN";

const SA_STATUS: Record<SaWorkflowStatus, { label: string; tone: StatusTone }> = {
  WAITING: { label: "Chờ khám", tone: "ready" },
  IN_PROGRESS: { label: "Đang thực hiện", tone: "in_progress" },
  DONE: { label: "Hoàn tất", tone: "completed" },
  CANCELLED: { label: "Đã hủy", tone: "cancelled" },
};
const UNKNOWN_SA_STATUS: { label: string; tone: StatusTone } = {
  label: "Chưa xác định",
  tone: "blocked",
};

function SaBadge({ status }: { status: string | null }) {
  const resolvedStatus = resolveSaWorkflowStatus(status);
  const item = resolvedStatus ? SA_STATUS[resolvedStatus] : UNKNOWN_SA_STATUS;
  return <StatusChip tone={item.tone} label={item.label} />;
}

function PrintLink({ id }: { id: string }) {
  return (
    <a
      href={`/print/sono/${id}`}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="In phiếu"
      className="inline-flex items-center gap-1.5 rounded-control border border-line bg-surface px-2.5 py-1.5 text-xs font-medium text-ink-soft hover:bg-surface-sunken"
    >
      <Printer className="size-3.5" /> In phiếu
    </a>
  );
}

function patientLabel(row: SonoRow): string {
  return sonoPatientDisplayName(row.patient?.full_name);
}

function SonoWorkflow({
  row,
  busy,
  onAction,
}: {
  row: SonoRow;
  busy: boolean;
  onAction: (action: "start" | "finish" | "cancel") => void;
}) {
  const status = resolveSaWorkflowStatus(row.status);
  const steps: Step[] = [
    {
      label: "Chờ thực hiện",
      state: status === null ? "upcoming" : status === "WAITING" ? "current" : "done",
      detail: status === null ? "Chưa xác định" : fmtTime(row.created_at),
    },
    {
      label: "Đang thực hiện",
      state:
        status === null
          ? "upcoming"
          : status === "IN_PROGRESS"
            ? "current"
            : status === "DONE"
              ? "done"
              : "upcoming",
      detail: status === null ? "Chưa xác định" : row.started_at ? fmtTime(row.started_at) : "Chưa bắt đầu",
    },
    {
      label: "Hoàn tất",
      state: status === "DONE" ? "done" : "upcoming",
      detail: status === null ? "Chưa xác định" : row.finished_at ? fmtTime(row.finished_at) : "Chưa hoàn tất",
    },
  ];
  const done = status === "DONE" || status === "CANCELLED";

  return (
    <section className="space-y-4">
      <div className="rounded-control border border-line bg-surface-muted p-3.5">
        <Stepper steps={steps} />
      </div>
      {status === null ? (
        <p className="rounded-control border border-warning bg-warning-bg px-3 py-2.5 text-xs text-warning">
          Trạng thái nguồn chưa xác định; các thao tác siêu âm được khóa để tránh suy diễn dữ liệu.
        </p>
      ) : status === "CANCELLED" ? (
        <p className="rounded-control border border-danger bg-danger-bg px-3 py-2.5 text-xs text-danger">
          Yêu cầu này đã được hủy qua luồng hiện có.
        </p>
      ) : null}
      {status !== null && !done ? (
        <div className="flex flex-wrap gap-2">
          {status === "WAITING" ? (
            <button
              type="button"
              onClick={() => onAction("start")}
              disabled={busy}
              className="inline-flex min-h-10 items-center gap-2 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              <Play className="size-4" /> Bắt đầu
            </button>
          ) : null}
          {status === "IN_PROGRESS" ? (
            <button
              type="button"
              onClick={() => onAction("finish")}
              disabled={busy}
              className="inline-flex min-h-10 items-center gap-2 rounded-control border border-success bg-surface px-4 text-sm font-semibold text-success hover:bg-success-bg disabled:opacity-50"
            >
              <Check className="size-4" /> Hoàn tất
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => onAction("cancel")}
            disabled={busy}
            className="inline-flex min-h-10 items-center gap-2 rounded-control border border-danger bg-surface px-4 text-sm font-semibold text-danger hover:bg-danger-bg disabled:opacity-50"
          >
            <X className="size-4" /> Hủy yêu cầu
          </button>
        </div>
      ) : null}
    </section>
  );
}

function MilestoneButton({
  label,
  at,
  busy,
  onToggle,
}: {
  label: string;
  at: string | null;
  busy: boolean;
  onToggle: (value: boolean) => void;
}) {
  const reached = Boolean(at);
  return (
    <button
      type="button"
      onClick={() => onToggle(!reached)}
      disabled={busy}
      aria-pressed={reached}
      title={reached ? "Bỏ đánh dấu mốc này" : `Đánh dấu ${label}`}
      className={`flex w-full items-center justify-between gap-3 rounded-control border px-3 py-2.5 text-left text-xs font-medium disabled:opacity-50 ${
        reached
          ? "border-success bg-success-bg text-success"
          : "border-line bg-surface text-ink-muted hover:bg-surface-sunken"
      }`}
    >
      <span>{label}</span>
      <span className="shrink-0">{reached ? `Có · ${fmtTime(at)}` : "Đánh dấu"}</span>
    </button>
  );
}

function LabWorkflow({
  row,
  busy,
  onToggle,
}: {
  row: SonoRow;
  busy: boolean;
  onToggle: (milestone: "sample" | "sendlab" | "result", value: boolean) => void;
}) {
  const steps: Step[] = [
    {
      label: "Lấy mẫu",
      state: row.started_at ? "done" : "current",
      detail: row.started_at ? fmtTime(row.started_at) : "Chưa đánh dấu",
    },
    {
      label: "Gửi lab",
      state: row.sent_to_lab_at ? "done" : row.started_at ? "current" : "upcoming",
      detail: row.sent_to_lab_at ? fmtTime(row.sent_to_lab_at) : "Chưa đánh dấu",
    },
    {
      label: "Có kết quả",
      state: row.finished_at ? "done" : row.sent_to_lab_at ? "current" : "upcoming",
      detail: row.finished_at ? fmtTime(row.finished_at) : "Chưa đánh dấu",
    },
  ];

  return (
    <section className="space-y-4">
      <div className="rounded-control border border-line bg-surface-muted p-3.5"><Stepper steps={steps} /></div>
      <div className="space-y-2">
        <MilestoneButton label="Lấy mẫu" at={row.started_at} busy={busy} onToggle={(value) => onToggle("sample", value)} />
        <MilestoneButton label="Gửi lab" at={row.sent_to_lab_at} busy={busy} onToggle={(value) => onToggle("sendlab", value)} />
        <MilestoneButton label="Có KQ" at={row.finished_at} busy={busy} onToggle={(value) => onToggle("result", value)} />
      </div>
    </section>
  );
}

function AddForm({
  kind,
  busy,
  onAdd,
}: {
  kind: QueueKind;
  busy: boolean;
  onAdd: (body: unknown) => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");

  async function submit() {
    const ok = await onAdd({
      kind,
      service_name: name.trim(),
      patient_code: code.trim() || undefined,
    });
    if (ok) {
      setName("");
      setCode("");
    }
  }

  return (
    <div className="space-y-3 p-3.5">
      <div>
        <label className={LABEL} htmlFor={`sono-name-${kind}`}>{kind === "SA" ? "Dịch vụ siêu âm" : "Xét nghiệm"}</label>
        <input
          id={`sono-name-${kind}`}
          className={INPUT}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={kind === "SA" ? "Ví dụ: Siêu âm thai" : "Ví dụ: Công thức máu"}
        />
      </div>
      <div>
        <label className={LABEL} htmlFor={`sono-code-${kind}`}>Mã BN (tùy chọn)</label>
        <input
          id={`sono-code-${kind}`}
          className={INPUT}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="Mã bệnh nhân"
        />
      </div>
      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="inline-flex min-h-10 items-center gap-2 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
      >
        <ClipboardList className="size-4" /> {busy ? "Đang lưu…" : "Thêm yêu cầu"}
      </button>
    </div>
  );
}

export default function SonoView({ sa, xn }: { sa: SonoRow[]; xn: SonoRow[] }) {
  const router = useRouter();
  const [kind, setKind] = useState<QueueKind>("SA");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRows = kind === "SA" ? sa : xn;
  const normalizedQuery = query.trim().toLocaleLowerCase("vi-VN");
  const visibleRows = useMemo(
    () =>
      activeRows.filter((row) =>
        !normalizedQuery
          ? true
          : [row.service_name_raw, row.patient?.full_name, row.patient?.patient_code]
              .filter(Boolean)
              .some((value) => value?.toLocaleLowerCase("vi-VN").includes(normalizedQuery)),
      ),
    [activeRows, normalizedQuery],
  );
  const selected = visibleRows.find((row) => row.id === selectedId) ?? visibleRows[0] ?? null;
  const selectedUnknownSaStatus =
    kind === "SA" &&
    selected !== null &&
    resolveSaWorkflowStatus(selected.status) === null;
  const waiting = sa.filter((row) => resolveSaWorkflowStatus(row.status) === "WAITING").length;
  const inProgress = sa.filter((row) => resolveSaWorkflowStatus(row.status) === "IN_PROGRESS").length;
  const completed = sa.filter((row) => resolveSaWorkflowStatus(row.status) === "DONE").length;
  const resultReady = xn.filter((row) => Boolean(row.finished_at)).length;

  async function send(method: string, body: unknown): Promise<boolean> {
    setError(null);
    setBusy(true);
    try {
      const response = await fetch("/api/sono", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        setError((await response.json().catch(() => ({}))).error ?? "Có lỗi xảy ra.");
        return false;
      }
      router.refresh();
      return true;
    } catch {
      setError("Không kết nối được máy chủ. Vui lòng thử lại.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <WorkspaceMetricRow>
        <WorkspaceMetric label="Yêu cầu siêu âm" value={sa.length} icon={<Stethoscope className="size-5" />} tone="brand" />
        <WorkspaceMetric label="Chờ khám" value={waiting} icon={<Clock3 className="size-5" />} tone={waiting ? "warning" : "neutral"} />
        <WorkspaceMetric label="Đang thực hiện" value={inProgress} icon={<Play className="size-5" />} tone={inProgress ? "brand" : "neutral"} />
        <WorkspaceMetric label="Mẫu đã có KQ" value={resultReady} icon={<FlaskConical className="size-5" />} tone={resultReady ? "success" : "neutral"} detail={`${completed} yêu cầu SA hoàn tất`} />
      </WorkspaceMetricRow>

      {error ? <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-sm text-danger">{error}</p> : null}

      <div className={workspaceStyles.workspace}>
      <div className={`${workspaceStyles.threeColumn} ${workspaceStyles.sono}`}>
        <aside
          aria-label="Hàng đợi siêu âm"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Hàng đợi siêu âm" detail={kind === "SA" ? `${visibleRows.length} yêu cầu hiển thị` : `${visibleRows.length} mẫu xét nghiệm hiển thị`} />
          <div className="space-y-3 border-b border-line p-3">
            <div className="grid grid-cols-2 gap-1 rounded-control bg-surface-muted p-1" aria-label="Chọn loại hàng đợi">
              {(["SA", "XN"] as QueueKind[]).map((candidate) => (
                <button
                  type="button"
                  key={candidate}
                  onClick={() => { setKind(candidate); setSelectedId(null); }}
                  aria-pressed={kind === candidate}
                  className={`rounded-chip px-2 py-1.5 text-xs font-medium transition-colors ${
                    kind === candidate ? "bg-brand-600 text-white" : "text-ink-muted hover:bg-surface"
                  }`}
                >
                  {candidate === "SA" ? `Siêu âm (${sa.length})` : `Xét nghiệm (${xn.length})`}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Tìm bệnh nhân hoặc dịch vụ</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm bệnh nhân, dịch vụ" className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint" />
            </label>
          </div>
          <div className="max-h-[620px] overflow-y-auto">
            {visibleRows.length ? (
              visibleRows.map((row) => (
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
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-semibold text-ink">{patientLabel(row)}</span>
                        <span className="shrink-0 text-xs tabular-nums text-ink-muted">{fmtTime(row.created_at)}</span>
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-ink-muted">{row.patient?.patient_code ?? "Chưa có mã BN"}</span>
                      <span className="mt-1 flex items-center justify-between gap-2">
                        <span className="truncate text-xs text-ink-faint">{row.service_name_raw ?? "Chưa có tên dịch vụ"}</span>
                        {kind === "SA" ? <SaBadge status={row.status} /> : <span className={`rounded-chip px-1.5 py-0.5 text-[11px] font-medium ${row.finished_at ? "bg-success-bg text-success" : "bg-surface-sunken text-ink-muted"}`}>{row.finished_at ? "Có KQ" : "Đang xử lý"}</span>}
                      </span>
                    </span>
                  </span>
                </button>
              ))
            ) : (
              <EmptyWorkspace title="Không có yêu cầu phù hợp" detail="Thử đổi loại hàng đợi hoặc từ khóa tìm kiếm." icon={<Search className="size-7" />} />
            )}
          </div>
        </aside>

        <section
          aria-label="Điều phối yêu cầu siêu âm"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title={kind === "SA" ? "Điều phối yêu cầu siêu âm" : "Luồng xét nghiệm"} detail="Thao tác chỉ dựa trên các mốc service_log hiện có." />
          {selected ? (
            <div className="space-y-4 p-4">
              <div className="rounded-control border border-line bg-surface-muted p-3.5">
                <div className="flex items-start gap-3">
                  <Monogram value={selected.patient?.full_name} className="size-11 text-sm" />
                  <div className="min-w-0 flex-1">
                    <p className="text-base font-semibold text-ink">{patientLabel(selected)}</p>
                    <p className="mt-0.5 text-xs text-ink-muted">{selected.patient?.patient_code ?? "Chưa có mã BN"}</p>
                    <p className="mt-2 text-sm font-medium text-brand-800">{selected.service_name_raw ?? "Chưa có tên dịch vụ"}</p>
                  </div>
                  {kind === "SA" ? <SaBadge status={selected.status} /> : null}
                </div>
              </div>
              {kind === "SA" ? (
                <>
                  <p className="flex gap-2 rounded-control border border-brand-100 bg-brand-50 px-3 py-2.5 text-xs leading-5 text-brand-800">
                    <PauseCircle className="mt-0.5 size-4 shrink-0" />
                    Chưa có dữ liệu phòng SA1–SA3 hoặc phép gán phòng trong nguồn hiện tại; màn này không tự gán hoặc chuyển phòng.
                  </p>
                  <SonoWorkflow row={selected} busy={busy} onAction={(action) => { void send("PATCH", { id: selected.id, action }); }} />
                </>
              ) : (
                <LabWorkflow row={selected} busy={busy} onToggle={(milestone, value) => { void send("PATCH", { id: selected.id, milestone, value }); }} />
              )}
            </div>
          ) : (
            <div className="p-4"><EmptyWorkspace title="Chưa có yêu cầu được chọn" detail="Chọn một dòng ở hàng đợi để cập nhật các mốc thực hiện." icon={<Stethoscope className="size-7" />} /></div>
          )}
        </section>

        <aside
          aria-label="Chi tiết yêu cầu siêu âm"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title={kind === "SA" ? "Chi tiết yêu cầu" : "Chi tiết mẫu xét nghiệm"} detail="Không hiển thị thông tin phòng, SLA hay chỉ định khi backend chưa cung cấp." />
          {selected ? (
            <div className="space-y-4 p-3.5">
              <dl className="space-y-2 rounded-control border border-line bg-surface-muted p-3 text-xs">
                <div className="flex justify-between gap-3"><dt className="text-ink-muted">Tạo lúc</dt><dd className="font-medium tabular-nums text-ink">{fmtTime(selected.created_at)}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-ink-muted">Bệnh nhân</dt><dd className="max-w-[65%] truncate text-right font-medium text-ink">{patientLabel(selected)}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-ink-muted">Mã BN</dt><dd className="font-medium text-ink">{selected.patient?.patient_code ?? "Chưa có"}</dd></div>
                {kind === "SA" ? <div className="flex justify-between gap-3"><dt className="text-ink-muted">Trạng thái</dt><dd><SaBadge status={selected.status} /></dd></div> : null}
              </dl>
              {selected.result_text ? <section className="rounded-control border border-line bg-surface p-3"><h3 className="text-xs font-semibold text-ink-soft">Ghi chú / kết quả</h3><p className="mt-2 text-xs leading-5 text-ink-muted">{selected.result_text}</p></section> : null}
              <div className="flex flex-wrap gap-2">
                <PrintLink id={selected.id} />
                <button
                  type="button"
                  onClick={() => { void send("DELETE", { id: selected.id }); }}
                  disabled={busy || selectedUnknownSaStatus}
                  title={selectedUnknownSaStatus ? "Không thể xóa khi trạng thái siêu âm chưa xác định" : undefined}
                  className="inline-flex items-center gap-1.5 rounded-control border border-danger bg-surface px-2.5 py-1.5 text-xs font-medium text-danger hover:bg-danger-bg disabled:opacity-50"
                >
                  <Trash2 className="size-3.5" /> Xóa dòng
                </button>
              </div>
            </div>
          ) : null}
          <div className={selected ? "border-t border-line" : ""}>
            <PanelHeading title={kind === "SA" ? "Thêm yêu cầu siêu âm" : "Thêm mẫu xét nghiệm"} />
            <AddForm kind={kind} busy={busy} onAdd={(body) => send("POST", body)} />
          </div>
        </aside>
      </div>
      </div>
    </div>
  );
}
