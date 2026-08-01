"use client";

import {
  CheckCircle2,
  CircleAlert,
  ClipboardPlus,
  CreditCard,
  FlaskConical,
  HeartPulse,
  Pill,
  Search,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";

import PriorityChip from "@/components/ui/PriorityChip";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import WorkItemActions from "@/components/ui/WorkItemActions";
import { STATUS_PRESENTATION, resolveStatus } from "@/lib/work-item-status";
import { patientLine, waitedMinutes, type WorklistItem } from "@/lib/worklist";

interface Blocker {
  node_code: string;
  dependency_type: string;
}

function group(items: WorklistItem[]) {
  return {
    working: items.filter((item) => item.status === "IN_PROGRESS"),
    ready: items.filter((item) => item.status === "PENDING" && !item.blocked),
    waiting: items.filter((item) => item.status === "PENDING" && item.blocked),
  };
}

function initials(name: string | null): string {
  if (!name) return "BN";
  const words = name.trim().split(/\s+/);
  return words
    .slice(-2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}

function appointmentTime(item: WorklistItem): string {
  if (!item.slot_start) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(item.slot_start));
}

function PatientRow({
  item,
  selected,
  onSelect,
}: {
  item: WorklistItem;
  selected: boolean;
  onSelect: () => void;
}) {
  const tone = resolveStatus(item);

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={`w-full border-l-[3px] px-2.5 py-3 text-left transition-colors ${
        selected
          ? "border-brand-500 bg-surface-selected"
          : "border-transparent bg-surface hover:bg-surface-sunken"
      }`}
    >
      <span className="flex items-start gap-2.5">
        <span className="grid size-9 shrink-0 place-items-center rounded-full border border-line bg-surface-sunken text-xs font-semibold text-ink-soft">
          {initials(item.patient.full_name)}
        </span>
        <span className="min-w-0 flex-1">
          {/* title= trên mọi ô có thể bị cắt: cột hẹp lại là chuyện của trình
              duyệt, còn "bệnh nhân nào, bước nào" thì bác sĩ luôn phải đọc
              được — rê chuột là ra đủ chữ. */}
          <span className="flex items-center gap-1.5">
            <span
              className="truncate text-sm font-semibold text-ink"
              title={item.patient.full_name ?? undefined}
            >
              {item.patient.full_name ?? "Chưa rõ tên"}
            </span>
            {item.is_priority_slot ? <PriorityChip priority="P0" /> : null}
          </span>
          <span className="mt-0.5 block truncate text-xs text-ink-muted">
            {item.patient.patient_code ?? "Chưa có mã BN"}
            {patientLine(item.patient) ? ` · ${patientLine(item.patient)}` : ""}
          </span>
          <span className="mt-1 flex items-center gap-2 text-xs text-ink-faint">
            <span className="truncate" title={item.node_name ?? item.node_code}>
              {item.node_name ?? item.node_code}
            </span>
            <span aria-hidden="true">·</span>
            <span className="shrink-0">chờ {waitedMinutes(item)}′</span>
          </span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1">
          <span className="text-xs tabular-nums text-ink-muted">
            {appointmentTime(item)}
          </span>
          <StatusChip
            tone={STATUS_PRESENTATION[tone].token as StatusTone}
            label={STATUS_PRESENTATION[tone].label}
          />
        </span>
      </span>
    </button>
  );
}

function PatientGroup({
  title,
  items,
  selectedId,
  onSelect,
  emptyLabel,
}: {
  title: string;
  items: WorklistItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  emptyLabel?: string;
}) {
  return (
    <section>
      <h3 className="border-y border-line bg-surface-muted px-3 py-2 text-xs font-semibold text-ink-soft">
        {title} ({items.length})
      </h3>
      {items.length > 0 ? (
        <div className="divide-y divide-line">
          {items.map((item) => (
            <PatientRow
              key={item.id}
              item={item}
              selected={item.id === selectedId}
              onSelect={() => onSelect(item.id)}
            />
          ))}
        </div>
      ) : emptyLabel ? (
        <p className="px-3 py-3 text-xs text-ink-faint">{emptyLabel}</p>
      ) : null}
    </section>
  );
}

function QueuePanel({
  items,
  selectedId,
  onSelect,
  query,
  onQueryChange,
}: {
  items: WorklistItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
}) {
  const grouped = group(items);

  return (
    <aside
      aria-label="Hàng đợi đang mở"
      className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      <div className="border-b border-line px-3 py-3">
        <h2 className="text-sm font-semibold text-ink">Hàng đợi đang mở</h2>
        <label className="mt-2 flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
          <Search className="size-4 shrink-0" aria-hidden="true" />
          <span className="sr-only">Tìm bệnh nhân hoặc mã hồ sơ</span>
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Tìm bệnh nhân hoặc mã hồ sơ"
            className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
      </div>

      <div className="max-h-[720px] overflow-y-auto">
        <PatientGroup
          title="Chờ khám"
          items={grouped.ready}
          selectedId={selectedId}
          onSelect={onSelect}
          emptyLabel="Không có bệnh nhân sẵn sàng khám."
        />
        <PatientGroup
          title="Đang khám"
          items={grouped.working}
          selectedId={selectedId}
          onSelect={onSelect}
          emptyLabel="Chưa có lượt đang khám."
        />
        <PatientGroup
          title="Chờ bước trước"
          items={grouped.waiting}
          selectedId={selectedId}
          onSelect={onSelect}
        />
        <PatientGroup
          title="Quay lại đọc kết quả"
          items={[]}
          selectedId={selectedId}
          onSelect={onSelect}
          emptyLabel="Chưa có luồng kết quả quay lại từ backend."
        />
      </div>

      <div className="border-t border-line px-3 py-2 text-xs text-ink-muted">
        Tổng: {items.length} bước công việc
      </div>
    </aside>
  );
}

function EmptyClinicalCard({ title, message }: { title: string; message: string }) {
  return (
    <section className="rounded-card border border-line bg-surface p-3.5">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-3 rounded-control border border-dashed border-line-strong bg-surface-muted px-3 py-4 text-center text-xs text-ink-muted">
        {message}
      </p>
    </section>
  );
}

const WORKSPACE_TABS = [
  "Khám bác sĩ",
  "Chỉ định",
  "Kết quả",
  "Đơn thuốc",
  "Thuốc & thanh toán",
] as const;

function ClinicalWorkspace({ item }: { item: WorklistItem | null }) {
  if (!item) {
    return (
      <section
        aria-label="Hồ sơ khám bệnh"
        className="grid min-h-96 place-items-center rounded-card border border-line bg-surface p-8 text-center shadow-card"
      >
        <div>
          <Stethoscope className="mx-auto size-8 text-brand-500" aria-hidden="true" />
          <p className="mt-3 font-medium text-ink">Chưa có người bệnh để mở hồ sơ</p>
          <p className="mt-1 text-sm text-ink-muted">
            Bàn khám chưa nhận được lượt khám nào từ backend.
          </p>
        </div>
      </section>
    );
  }

  const tone = resolveStatus(item);

  return (
    <section
      aria-label="Hồ sơ khám bệnh"
      className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      <header className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="grid size-11 place-items-center rounded-full border border-line bg-surface-sunken text-sm font-semibold text-ink-soft">
            {initials(item.patient.full_name)}
          </span>
          <div className="min-w-44 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-ink">
                {item.patient.full_name ?? "Chưa rõ tên"}
              </h2>
              <StatusChip
                tone={STATUS_PRESENTATION[tone].token as StatusTone}
                label={STATUS_PRESENTATION[tone].label}
                size="md"
              />
            </div>
            <p className="text-xs text-ink-muted">
              {patientLine(item.patient) || "Chưa có thông tin nhân khẩu học"}
              {item.patient.patient_code ? ` · ${item.patient.patient_code}` : ""}
            </p>
          </div>
          <dl className="grid grid-cols-3 divide-x divide-line text-xs">
            <WorkflowField label="Số thứ tự" value={item.queue_number ?? "—"} />
            <WorkflowField label="Đã chờ" value={`${waitedMinutes(item)} phút`} />
            <WorkflowField label="Bước hiện tại" value={item.node_name ?? item.node_code} />
          </dl>
        </div>

        <div className="mt-3 flex items-center gap-2 rounded-control border border-dashed border-line bg-surface-muted px-3 py-2 text-xs text-ink-muted">
          <HeartPulse className="size-4 shrink-0 text-brand-600" aria-hidden="true" />
          <span>Màn này chưa kết nối nguồn dữ liệu sinh hiệu</span>
        </div>
      </header>

      <nav aria-label="Các phần hồ sơ khám" className="flex overflow-x-auto border-b border-line px-3">
        {WORKSPACE_TABS.map((tab, index) => (
          <span
            key={tab}
            aria-current={index === 0 ? "page" : undefined}
            aria-disabled={index === 0 ? undefined : "true"}
            title={index === 0 ? undefined : "Màn này chưa kết nối nguồn dữ liệu"}
            className={`shrink-0 border-b-2 px-3 py-3 text-xs font-medium ${
              index === 0
                ? "border-brand-500 text-brand-700"
                : "border-transparent text-ink-faint"
            }`}
          >
            {tab}
          </span>
        ))}
      </nav>

      <div className="grid gap-3 bg-surface-muted p-3 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="grid content-start gap-3 sm:grid-cols-2">
          <EmptyClinicalCard title="1. Lý do khám" message="Màn này chưa kết nối nội dung khám lâm sàng" />
          <EmptyClinicalCard title="2. Bệnh sử" message="Màn này chưa kết nối nội dung khám lâm sàng" />
          <EmptyClinicalCard title="3. Khám lâm sàng" message="Màn này chưa kết nối nội dung khám lâm sàng" />
          <EmptyClinicalCard title="4. Chẩn đoán" message="Màn này chưa kết nối nguồn dữ liệu chẩn đoán" />
          <EmptyClinicalCard title="5. Kế hoạch điều trị" message="Màn này chưa kết nối nguồn dữ liệu điều trị" />
          <EmptyClinicalCard title="Xác nhận tư vấn" message="Màn này chưa kết nối nguồn xác nhận tư vấn" />
        </div>

        <section className="rounded-card border border-line bg-surface p-3.5">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-4 text-specialty-service" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-ink">Chỉ định & kết quả liên quan</h3>
          </div>
          <p className="mt-3 rounded-control border border-dashed border-line-strong bg-surface-muted px-3 py-6 text-center text-xs text-ink-muted">
            Màn này chưa kết nối chỉ định hoặc kết quả để hiển thị
          </p>
          {item.visit_id && item.node_code === "LUOTKHAM-05" && !item.blocked ? (
            <Link
              href={`/doctor/orders/${item.visit_id}`}
              className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-control border border-brand-600 px-3 py-2.5 text-sm font-medium text-brand-700 hover:bg-brand-50"
            >
              <ClipboardPlus className="size-4" aria-hidden="true" />
              Mở màn chỉ định dịch vụ
            </Link>
          ) : null}
        </section>
      </div>
    </section>
  );
}

function WorkflowField({ label, value }: { label: string; value: string }) {
  return (
    <div className="max-w-36 px-3 first:pl-0">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="mt-0.5 truncate font-medium text-ink" title={value}>
        {value}
      </dd>
    </div>
  );
}

function CoordinationSection({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-card border border-line bg-surface p-3">
      <header className="flex items-center gap-2">
        <span className="text-brand-600">{icon}</span>
        <h3 className="flex-1 text-xs font-semibold text-ink">{title}</h3>
      </header>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function CoordinationPanel({ item }: { item: WorklistItem | null }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fetched, setFetched] = useState<{ id: string; blockers: Blocker[] } | null>(null);
  const blockers = item && fetched?.id === item.id ? fetched.blockers : null;

  useEffect(() => {
    if (!item?.blocked) return;
    let cancelled = false;
    fetch(`/api/work-items/${item.id}/blockers?phase=start`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!cancelled && data) {
          setFetched({ id: item.id, blockers: data.blockers ?? [] });
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [item?.id, item?.blocked]);

  async function issue(command: "start" | "complete") {
    if (!item) return;
    setError(null);
    const response = await fetch(`/api/work-items/${item.id}/commands/${command}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_version: item.version }),
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null;
      setError(body?.error ?? `Không thực hiện được (HTTP ${response.status})`);
      return;
    }
    startTransition(() => router.refresh());
  }

  return (
    <aside
      aria-label="Việc còn thiếu và điều phối"
      className="min-w-0 rounded-card border border-line bg-surface-muted p-3 shadow-card"
    >
      <h2 className="mb-3 text-sm font-semibold text-ink">Việc còn thiếu & điều phối</h2>

      {!item ? (
        <p className="rounded-control border border-dashed border-line-strong bg-surface px-3 py-5 text-center text-xs text-ink-muted">
          Chưa có lượt khám để điều phối.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <CoordinationSection
            icon={<CheckCircle2 className="size-4" aria-hidden="true" />}
            title="Việc cần hoàn tất"
          >
            <div className="flex items-start gap-2 text-xs text-ink-soft">
              <span className="mt-0.5 size-3.5 shrink-0 rounded border border-brand-500 bg-brand-50" />
              <span>{item.node_name ?? item.node_code}</span>
            </div>
            {item.blocked ? (
              <p className="mt-2 text-xs text-warning">
                Còn bước phía trước chưa hoàn tất.
              </p>
            ) : null}
          </CoordinationSection>

          <CoordinationSection
            icon={<Stethoscope className="size-4" aria-hidden="true" />}
            title="Dịch vụ song song"
          >
            <p className="text-xs text-ink-muted">Chưa có dịch vụ song song từ backend.</p>
          </CoordinationSection>

          <CoordinationSection
            icon={<CircleAlert className="size-4" aria-hidden="true" />}
            title="Quay lại đọc kết quả"
          >
            <p className="text-xs text-ink-muted">Chưa có kết quả quay lại cần xử lý.</p>
          </CoordinationSection>

          <CoordinationSection
            icon={<Pill className="size-4" aria-hidden="true" />}
            title="Tóm tắt đơn thuốc"
          >
            <p className="text-xs text-ink-muted">Màn này chưa kết nối dữ liệu đơn thuốc</p>
          </CoordinationSection>

          <CoordinationSection
            icon={<CreditCard className="size-4" aria-hidden="true" />}
            title="Thuốc & thanh toán"
          >
            <p className="text-xs text-ink-muted">Màn này chưa kết nối dữ liệu thanh toán</p>
          </CoordinationSection>

          <div className="border-t border-line pt-3">
            <WorkItemActions
              status={item.status}
              blocked={item.blocked}
              actionableByMe={item.actionable_by_me}
              actorRoles={item.actor_roles}
              blockedBy={(blockers ?? []).map((blocker) => blocker.node_code)}
              pending={pending}
              error={error}
              onIssue={issue}
              startLabel="Bắt đầu khám"
              completeLabel="Hoàn tất bước này"
            />
          </div>
        </div>
      )}
    </aside>
  );
}

export default function DoctorBoard({ items }: { items: WorklistItem[] }) {
  const [query, setQuery] = useState("");
  const visibleItems = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi");
    if (!needle) return items;
    return items.filter((item) =>
      [item.patient.full_name, item.patient.patient_code, item.queue_number]
        .filter(Boolean)
        .some((value) => value?.toLocaleLowerCase("vi").includes(needle)),
    );
  }, [items, query]);
  const grouped = group(visibleItems);
  const first = grouped.working[0] ?? grouped.ready[0] ?? grouped.waiting[0] ?? null;
  const [selectedId, setSelectedId] = useState<string | null>(first?.id ?? null);
  const selected = visibleItems.find((item) => item.id === selectedId) ?? first;

  return (
    <div className="grid items-start gap-3 xl:grid-cols-[minmax(250px,1.05fr)_minmax(420px,1.7fr)_minmax(230px,0.72fr)]">
      <QueuePanel
        items={visibleItems}
        selectedId={selected?.id ?? null}
        onSelect={setSelectedId}
        query={query}
        onQueryChange={setQuery}
      />
      <ClinicalWorkspace item={selected} />
      <CoordinationPanel item={selected} />
    </div>
  );
}
