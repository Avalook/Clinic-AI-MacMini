"use client";

import Link from "next/link";
import {
  CalendarCheck2,
  CalendarClock,
  ClipboardList,
  FlaskConical,
  PhoneCall,
  Search,
  UserRoundX,
} from "lucide-react";
import { useMemo, useState } from "react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import { fmtDate, fmtDateTimeOrDate, fmtTimeOrNone } from "@/lib/datetime";
import { doctorName } from "@/lib/doctor-name";
import { FollowupMarkButton } from "./CskhFollowupList";

export interface CskhTodayAppointment {
  id: string;
  slotStart: string;
  patient: {
    id: string;
    fullName: string | null;
    phone: string | null;
  } | null;
  doctorName: string | null;
  serviceName: string | null;
}

export interface CskhRecall {
  patientId: string;
  fullName: string;
  phone: string | null;
  dueDate: string;
  repeatTests: string[];
  instruction: string;
}

export interface CskhFollowup {
  patientId: string;
  fullName: string;
  phone: string | null;
  dueDate: string;
  overdueDays: number;
  tierLabel: string;
}

export interface CskhLabResult {
  id: string;
  testName: string | null;
  receivedAt: string | null;
  patient: {
    id: string;
    fullName: string | null;
    phone: string | null;
  } | null;
  releaseAllowed: boolean;
  releaseLabel: string;
}

type TaskKind = "tomorrow" | "declined" | "recall" | "followup" | "lab";
type TaskTab = "all" | TaskKind;

interface CskhTask {
  id: string;
  kind: TaskKind;
  patientId: string | null;
  patientName: string;
  phone: string | null;
  title: string;
  subtitle: string;
  scheduledAt: string | null;
  statusLabel: string;
  statusTone: StatusTone;
  appointment?: CskhTodayAppointment;
  recall?: CskhRecall;
  followup?: CskhFollowup;
  lab?: CskhLabResult;
}

const TASK_TABS: { key: TaskTab; label: string }[] = [
  { key: "all", label: "Tất cả việc" },
  { key: "tomorrow", label: "Lịch ngày mai" },
  { key: "declined", label: "Bị từ chối" },
  { key: "recall", label: "Tái khám" },
  { key: "followup", label: "Quá hạn" },
  { key: "lab", label: "Kết quả XN" },
];

const TASK_KIND_LABEL: Record<TaskKind, string> = {
  tomorrow: "Lịch ngày mai",
  declined: "Bị bác sĩ từ chối",
  recall: "Đến hạn tái khám",
  followup: "Quá hạn tái khám",
  lab: "Kết quả xét nghiệm",
};

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words
    .slice(-2)
    .map((word) => word[0]?.toLocaleUpperCase("vi-VN") ?? "")
    .join("") || "KH";
}

function TaskSymbol({ kind }: { kind: TaskKind }) {
  const props = { className: "size-4", "aria-hidden": true } as const;
  if (kind === "tomorrow") return <CalendarCheck2 {...props} />;
  if (kind === "declined") return <UserRoundX {...props} />;
  if (kind === "recall") return <CalendarClock {...props} />;
  if (kind === "followup") return <PhoneCall {...props} />;
  return <FlaskConical {...props} />;
}

function taskTime(task: CskhTask): string {
  if (!task.scheduledAt) return "Chưa có mốc thời gian";
  if (task.kind === "tomorrow" || task.kind === "declined") {
    return fmtDateTimeOrDate(task.scheduledAt);
  }
  if (task.kind === "lab") return fmtTimeOrNone(task.scheduledAt);
  return fmtDate(task.scheduledAt);
}

function makeTasks({
  tomorrow,
  declined,
  recalls,
  followups,
  labs,
}: Pick<
  CskhTodayWorkspaceProps,
  "tomorrow" | "declined" | "recalls" | "followups" | "labs"
>): CskhTask[] {
  return [
    ...tomorrow.map((appointment) => ({
      id: `tomorrow:${appointment.id}`,
      kind: "tomorrow" as const,
      patientId: appointment.patient?.id ?? null,
      patientName: appointment.patient?.fullName ?? "Không rõ tên khách hàng",
      phone: appointment.patient?.phone ?? null,
      title: "Gọi xác nhận lịch hẹn",
      subtitle: [
        appointment.serviceName ?? "Chưa chọn dịch vụ",
        appointment.doctorName ? doctorName(appointment.doctorName) : null,
      ]
        .filter(Boolean)
        .join(" · "),
      scheduledAt: appointment.slotStart,
      statusLabel: "Chờ xác nhận",
      statusTone: "ready" as const,
      appointment,
    })),
    ...declined.map((appointment) => ({
      id: `declined:${appointment.id}`,
      kind: "declined" as const,
      patientId: appointment.patient?.id ?? null,
      patientName: appointment.patient?.fullName ?? "Không rõ tên khách hàng",
      phone: appointment.patient?.phone ?? null,
      title: "Phân lại lịch bị từ chối",
      subtitle: appointment.doctorName
        ? `Bác sĩ từ chối: ${doctorName(appointment.doctorName)}`
        : "Lịch bị bác sĩ từ chối",
      scheduledAt: appointment.slotStart,
      statusLabel: "Bị từ chối",
      statusTone: "cancelled" as const,
      appointment,
    })),
    ...recalls.map((recall) => ({
      id: `recall:${recall.patientId}`,
      kind: "recall" as const,
      patientId: recall.patientId,
      patientName: recall.fullName,
      phone: recall.phone,
      title: "Đặt lịch tái khám",
      subtitle:
        recall.repeatTests.length > 0
          ? `XN cần làm lại: ${recall.repeatTests.join(", ")}`
          : recall.instruction || "Bác sĩ đã dặn tái khám",
      scheduledAt: recall.dueDate,
      statusLabel: "Đến hạn tái khám",
      statusTone: "ready" as const,
      recall,
    })),
    ...followups.map((followup) => ({
      id: `followup:${followup.patientId}:${followup.tierLabel}`,
      kind: "followup" as const,
      patientId: followup.patientId,
      patientName: followup.fullName,
      phone: followup.phone,
      title: "Nhắc gọi tái khám",
      subtitle: `${followup.tierLabel} · quá hạn ${followup.overdueDays} ngày`,
      scheduledAt: followup.dueDate,
      statusLabel: `Quá hạn ${followup.overdueDays} ngày`,
      statusTone: "overdue" as const,
      followup,
    })),
    ...labs.map((lab) => ({
      id: `lab:${lab.id}`,
      kind: "lab" as const,
      patientId: lab.patient?.id ?? null,
      patientName: lab.patient?.fullName ?? "Không rõ tên khách hàng",
      phone: lab.patient?.phone ?? null,
      title: "Kết quả XN mới về",
      subtitle: lab.testName ?? "Xét nghiệm",
      scheduledAt: lab.receivedAt,
      statusLabel: lab.releaseLabel,
      statusTone: lab.releaseAllowed ? ("completed" as const) : ("blocked" as const),
      lab,
    })),
  ];
}

interface CskhTodayWorkspaceProps {
  todayLabel: string;
  tomorrow: CskhTodayAppointment[];
  declined: CskhTodayAppointment[];
  recalls: CskhRecall[];
  followups: CskhFollowup[];
  labs: CskhLabResult[];
}

export default function CskhTodayWorkspace(props: CskhTodayWorkspaceProps) {
  const [tab, setTab] = useState<TaskTab>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const tasks = useMemo(() => makeTasks(props), [props]);
  const visibleTasks = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    return tasks.filter((task) => {
      const matchesTab = tab === "all" || task.kind === tab;
      const haystack = [
        task.patientName,
        task.phone,
        task.title,
        task.subtitle,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("vi-VN");
      return matchesTab && (!needle || haystack.includes(needle));
    });
  }, [query, tab, tasks]);
  const selected =
    visibleTasks.find((task) => task.id === selectedId) ?? visibleTasks[0] ?? null;

  return (
    <div className="space-y-3">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand-700">
            CSKH · {props.todayLabel}
          </p>
          <h1 className="mt-1 text-xl font-semibold text-ink">Cần làm hôm nay</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Danh sách tự sinh từ lịch hẹn, nhắc tái khám và kết quả xét nghiệm.
          </p>
        </div>
        <Link
          href="/tasks"
          className="inline-flex min-h-9 items-center rounded-control border border-line bg-surface px-3 text-sm font-medium text-ink hover:bg-surface-sunken"
        >
          Mở Công việc của tôi
        </Link>
      </header>

      <StatRow>
        <StatCard
          label="Lịch ngày mai"
          value={props.tomorrow.length}
          tone="brand"
          icon={<CalendarCheck2 className="size-5" />}
        />
        <StatCard
          label="Bị từ chối"
          value={props.declined.length}
          tone="danger"
          icon={<UserRoundX className="size-5" />}
        />
        <StatCard
          label="Đến hạn tái khám"
          value={props.recalls.length}
          tone="warning"
          icon={<CalendarClock className="size-5" />}
        />
        <StatCard
          label="Kết quả XN"
          value={props.labs.length}
          tone="success"
          icon={<FlaskConical className="size-5" />}
        />
      </StatRow>

      <div className="grid items-start gap-3 xl:grid-cols-[minmax(250px,0.9fr)_minmax(360px,1.25fr)_minmax(240px,0.8fr)]">
        <section
          aria-label="Danh sách việc CSKH"
          className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <header className="border-b border-line p-3">
            <h2 className="text-sm font-semibold text-ink">Danh sách việc CSKH</h2>
            <div className="mt-3 flex overflow-x-auto border-b border-line text-xs">
              {TASK_TABS.map((entry) => (
                <button
                  key={entry.key}
                  type="button"
                  onClick={() => setTab(entry.key)}
                  aria-pressed={tab === entry.key}
                  className={`shrink-0 border-b-2 px-2.5 py-2 font-medium transition-colors ${
                    tab === entry.key
                      ? "border-brand-600 text-brand-700"
                      : "border-transparent text-ink-muted hover:text-ink"
                  }`}
                >
                  {entry.label}
                </button>
              ))}
            </div>
            <label className="mt-3 flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
              <Search className="size-4" aria-hidden="true" />
              <span className="sr-only">Tìm công việc hoặc khách hàng</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm công việc hoặc khách hàng"
                className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
              />
            </label>
          </header>

          <div className="max-h-[610px] overflow-y-auto">
            {visibleTasks.length > 0 ? (
              visibleTasks.map((task) => {
                const active = task.id === selected?.id;
                return (
                  <button
                    key={task.id}
                    type="button"
                    onClick={() => setSelectedId(task.id)}
                    aria-current={active ? "true" : undefined}
                    className={`flex w-full items-start gap-2.5 border-b border-line px-3 py-3 text-left transition-colors last:border-b-0 ${
                      active
                        ? "border-l-2 border-l-brand-500 bg-surface-selected"
                        : "border-l-2 border-l-transparent hover:bg-surface-sunken"
                    }`}
                  >
                    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-50 text-brand-700">
                      <TaskSymbol kind={task.kind} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-semibold text-ink">
                          {task.patientName}
                        </span>
                        <span className="shrink-0 text-[11px] tabular-nums text-ink-muted">
                          {taskTime(task)}
                        </span>
                      </span>
                      <span className="mt-0.5 block truncate text-xs font-medium text-ink-soft">
                        {task.title}
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-ink-muted">
                        {task.subtitle || "Chưa có thông tin bổ sung"}
                      </span>
                      <span className="mt-2 inline-flex">
                        <StatusChip tone={task.statusTone} label={task.statusLabel} />
                      </span>
                    </span>
                  </button>
                );
              })
            ) : (
              <p className="px-4 py-12 text-center text-sm text-ink-muted">
                Không có công việc khớp bộ lọc.
              </p>
            )}
          </div>
        </section>

        <section
          aria-label="Chi tiết công việc"
          className="rounded-card border border-line bg-surface p-4 shadow-card"
        >
          {selected ? (
            <>
              <div className="flex items-start gap-3 border-b border-line pb-4">
                <span className="grid size-12 shrink-0 place-items-center rounded-full bg-surface-sunken text-sm font-semibold text-ink-soft">
                  {initials(selected.patientName)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-brand-700">
                        {TASK_KIND_LABEL[selected.kind]}
                      </p>
                      <h2 className="mt-1 truncate text-lg font-semibold text-ink">
                        {selected.patientName}
                      </h2>
                    </div>
                    <StatusChip tone={selected.statusTone} label={selected.statusLabel} />
                  </div>
                  <p className="mt-1 text-sm text-ink-muted">
                    {selected.phone ?? "Chưa có số điện thoại"}
                  </p>
                </div>
              </div>

              <div className="space-y-4 py-4">
                <div>
                  <h3 className="text-sm font-semibold text-ink">Nội dung công việc</h3>
                  <p className="mt-1 text-sm text-ink-soft">{selected.title}</p>
                  <p className="mt-1 text-sm text-ink-muted">{selected.subtitle}</p>
                </div>

                <dl className="grid gap-3 rounded-control border border-line bg-surface-muted p-3 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-xs text-ink-muted">Mốc xử lý</dt>
                    <dd className="mt-1 font-medium text-ink">{taskTime(selected)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-muted">Nguồn</dt>
                    <dd className="mt-1 font-medium text-ink">
                      {TASK_KIND_LABEL[selected.kind]}
                    </dd>
                  </div>
                </dl>

                {selected.recall?.instruction ? (
                  <div className="rounded-control border border-line p-3">
                    <h3 className="text-sm font-semibold text-ink">Dặn tái khám</h3>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-ink-soft">
                      {selected.recall.instruction}
                    </p>
                  </div>
                ) : null}

                {selected.lab ? (
                  <div className="rounded-control border border-line p-3">
                    <h3 className="text-sm font-semibold text-ink">Điều kiện thông báo</h3>
                    <p className="mt-1 text-sm text-ink-soft">
                      {selected.lab.releaseAllowed
                        ? "Kết quả đã đạt điều kiện hiển thị cho CSKH theo quy tắc phát hành."
                        : "Kết quả chưa đạt điều kiện phát hành; không được thông báo cho khách hàng."}
                    </p>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <div className="grid min-h-72 place-items-center text-center">
              <div>
                <ClipboardList className="mx-auto size-7 text-ink-faint" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-ink">Chưa chọn công việc</p>
                <p className="mt-1 text-xs text-ink-muted">
                  Chọn một dòng bên trái để xem dữ liệu có thể xử lý.
                </p>
              </div>
            </div>
          )}
        </section>

        <aside
          aria-label="Điều phối công việc"
          className="rounded-card border border-line bg-surface p-4 shadow-card"
        >
          <h2 className="text-sm font-semibold text-ink">Điều phối công việc</h2>
          {selected ? (
            <div className="mt-4 space-y-4">
              <div className="rounded-control border border-line bg-surface-muted p-3">
                <p className="text-xs text-ink-muted">Trạng thái hiện tại</p>
                <div className="mt-2">
                  <StatusChip tone={selected.statusTone} label={selected.statusLabel} />
                </div>
              </div>

              {selected.kind === "tomorrow" || selected.kind === "declined" ? (
                <>
                  <p className="text-sm text-ink-muted">
                    Xác nhận hoặc phân lại lịch được thực hiện tại bảng công việc hiện có.
                  </p>
                  <Link
                    href="/tasks"
                    className="flex min-h-10 items-center justify-center rounded-control bg-brand-600 px-3 text-sm font-semibold text-white hover:bg-brand-700"
                  >
                    Mở Công việc của tôi
                  </Link>
                </>
              ) : null}

              {selected.kind === "followup" && selected.followup ? (
                <FollowupMarkButton patientId={selected.followup.patientId} />
              ) : null}

              {selected.kind === "recall" ? (
                <div className="space-y-3 rounded-control border border-dashed border-line-strong bg-surface-muted p-3">
                  <p className="text-sm text-ink-muted">
                    Chưa có thao tác đặt lịch trực tiếp trên danh sách này. Mở hồ sơ khách hàng để xử lý lịch hẹn.
                  </p>
                  {selected.patientId ? (
                    <Link
                      href={`/customers?selected=${selected.patientId}`}
                      className="flex min-h-10 items-center justify-center rounded-control border border-brand-500 bg-surface px-3 text-sm font-semibold text-brand-700 hover:bg-brand-50"
                    >
                      Mở hồ sơ khách hàng
                    </Link>
                  ) : (
                    <p className="text-sm text-ink-muted">
                      Chưa có mã bệnh nhân để mở hồ sơ.
                    </p>
                  )}
                </div>
              ) : null}

              {selected.kind === "lab" ? (
                <p className="rounded-control border border-dashed border-line-strong bg-surface-muted p-3 text-sm text-ink-muted">
                  Danh sách này chỉ hiển thị quyết định phát hành. Chưa có thao tác báo kết quả trong luồng này.
                </p>
              ) : null}
            </div>
          ) : (
            <p className="mt-3 text-sm text-ink-muted">
              Các thao tác chỉ xuất hiện khi chọn công việc có hợp đồng backend tương ứng.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}
