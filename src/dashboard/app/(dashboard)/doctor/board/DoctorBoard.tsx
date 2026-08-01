"use client";

/**
 * Bàn khám — the doctor's board.
 *
 * Same endpoint as the reception queue, one parameter different
 * (workspace=khu_bac_si). That is the whole argument for having made the
 * worklist data-driven: the doctor's board was not a second query to write.
 *
 * What IS different is the grouping. Reception works a first-come queue; a
 * doctor's list divides into three questions — who can I see now, who is still
 * upstream, and who am I already with. The designs group the same way ("Chờ
 * khám / Đang khám / Quay lại đọc kết quả"), and the first two fall straight
 * out of the kernel's gate state. The third needs the lab-result lane that
 * queue_order.py already implements for /queue and the kernel does not model
 * yet, so it is not faked here.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import PriorityChip from "@/components/ui/PriorityChip";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import WorkItemActions from "@/components/ui/WorkItemActions";
import { STATUS_PRESENTATION, resolveStatus } from "@/lib/work-item-status";
import { patientLine, waitedMinutes, type WorklistItem } from "@/lib/worklist";

interface Blocker {
  node_code: string;
  dependency_type: string;
}

/** Blocked first: those are the ones whose reason the doctor needs to see. */
function group(items: WorklistItem[]) {
  return {
    working: items.filter((i) => i.status === "IN_PROGRESS"),
    ready: items.filter((i) => i.status === "PENDING" && !i.blocked),
    waiting: items.filter((i) => i.status === "PENDING" && i.blocked),
  };
}

function Row({
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
      className={`w-full rounded-card border px-4 py-3 text-left transition-colors ${
        selected
          ? "border-l-[3px] border-brand-600 bg-surface-selected"
          : "border-line bg-surface hover:bg-surface-sunken"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 min-w-12 rounded-control bg-surface-sunken px-2 py-1 text-center text-sm font-semibold text-ink tabular-nums">
          {item.queue_number ?? "—"}
        </span>
        <span className="flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-ink">
              {item.patient.full_name ?? "Chưa rõ tên"}
            </span>
            {item.is_priority_slot ? <PriorityChip priority="P0" /> : null}
          </span>
          <span className="block text-xs text-ink-muted">
            {patientLine(item.patient)}
            {item.patient.patient_code ? ` · ${item.patient.patient_code}` : ""}
          </span>
          <span className="mt-1 block text-xs text-ink-soft">
            {item.node_name ?? item.node_code}
          </span>
        </span>
        <span className="flex flex-col items-end gap-1">
          <StatusChip
            tone={STATUS_PRESENTATION[tone].token as StatusTone}
            label={STATUS_PRESENTATION[tone].label}
          />
          <span className="text-xs text-ink-muted tabular-nums">
            chờ {waitedMinutes(item)}′
          </span>
        </span>
      </div>
    </button>
  );
}

function Group({
  title,
  hint,
  items,
  selectedId,
  onSelect,
}: {
  title: string;
  hint: string;
  items: WorklistItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <div>
        <h2 className="text-sm font-medium text-ink-soft">
          {title} ({items.length})
        </h2>
        <p className="text-xs text-ink-faint">{hint}</p>
      </div>
      {items.map((i) => (
        <Row
          key={i.id}
          item={i}
          selected={i.id === selectedId}
          onSelect={() => onSelect(i.id)}
        />
      ))}
    </section>
  );
}

export default function DoctorBoard({ items }: { items: WorklistItem[] }) {
  const g = group(items);
  // Default to someone the doctor can actually act on, not simply the first
  // row: a board that opens on a blocked patient invites a click that fails.
  const first = g.working[0] ?? g.ready[0] ?? g.waiting[0] ?? null;
  const [selectedId, setSelectedId] = useState<string | null>(first?.id ?? null);
  const selected = items.find((i) => i.id === selectedId) ?? first;

  if (items.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-10 text-center">
        <p className="font-medium text-ink">Chưa có người bệnh nào</p>
        <p className="mt-1 text-sm text-ink-muted">
          Bàn khám trống — chưa có lượt khám nào đến bước của bác sĩ.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(340px,420px)_1fr]">
      <div className="flex flex-col gap-5">
        <Group
          title="Đang khám"
          hint="Bác sĩ đã bắt đầu, chưa hoàn tất."
          items={g.working}
          selectedId={selected?.id ?? null}
          onSelect={setSelectedId}
        />
        <Group
          title="Sẵn sàng khám"
          hint="Các bước trước đã xong, cổng quy trình đã mở."
          items={g.ready}
          selectedId={selected?.id ?? null}
          onSelect={setSelectedId}
        />
        <Group
          title="Chờ bước trước"
          hint="Chưa khám được — còn bước phía trước chưa hoàn tất."
          items={g.waiting}
          selectedId={selected?.id ?? null}
          onSelect={setSelectedId}
        />
      </div>
      {selected ? <Detail item={selected} /> : null}
    </div>
  );
}

function Detail({ item }: { item: WorklistItem }) {
  const tone = resolveStatus(item);
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  // Keyed by item id rather than cleared on selection change. Clearing meant a
  // setState synchronously inside the effect, which the React Compiler rejects
  // for good reason — and deriving staleness is more correct anyway: a slow
  // response for the previous patient can never paint under the current one.
  const [fetched, setFetched] = useState<{
    id: string;
    blockers: Blocker[];
  } | null>(null);
  const blockers = fetched?.id === item.id ? fetched.blockers : null;

  // Only ask when it matters. An unblocked item has nothing to explain, and the
  // gate function is not free.
  useEffect(() => {
    if (!item.blocked) return;
    let cancelled = false;
    fetch(`/api/work-items/${item.id}/blockers?phase=start`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled && d) setFetched({ id: item.id, blockers: d.blockers ?? [] });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [item.id, item.blocked]);

  async function issue(command: "start" | "complete") {
    setError(null);
    const res = await fetch(`/api/work-items/${item.id}/commands/${command}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_version: item.version }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      setError(body?.error ?? `Không thực hiện được (HTTP ${res.status})`);
      return;
    }
    startTransition(() => router.refresh());
  }


  return (
    <section className="flex flex-col gap-4 rounded-card border border-line bg-surface p-5 shadow-card">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-ink">
            {item.patient.full_name ?? "Chưa rõ tên"}
          </h2>
          <p className="text-sm text-ink-muted">
            {patientLine(item.patient)}
            {item.patient.patient_code ? ` · ${item.patient.patient_code}` : ""}
          </p>
        </div>
        <StatusChip
          tone={STATUS_PRESENTATION[tone].token as StatusTone}
          label={STATUS_PRESENTATION[tone].label}
          size="md"
        />
      </header>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 border-y border-line py-4 text-sm sm:grid-cols-3">
        <Field label="Bước hiện tại" value={item.node_name ?? item.node_code} />
        <Field label="Số thứ tự" value={item.queue_number ?? "—"} />
        <Field label="Đã chờ" value={`${waitedMinutes(item)} phút`} />
      </dl>

      {/* The order composer needed its visit_id typed into the URL, which meant
          the walkthrough told a doctor to run psql. A screen you reach by
          querying the database is a screen nobody reaches. */}
      {item.visit_id && item.node_code === "LUOTKHAM-05" && !item.blocked ? (
        <Link
          href={`/doctor/orders/${item.visit_id}`}
          className="inline-flex w-fit items-center gap-2 rounded-control border border-brand-600 px-4 py-2.5 text-sm font-medium text-brand-700 hover:bg-brand-50"
        >
          Mở màn chỉ định dịch vụ →
        </Link>
      ) : null}

      <WorkItemActions
        status={item.status}
        blocked={item.blocked}
        actionableByMe={item.actionable_by_me}
        actorRoles={item.actor_roles}
        blockedBy={(blockers ?? []).map((b) => b.node_code)}
        pending={pending}
        error={error}
        onIssue={issue}
        startLabel="Bắt đầu khám"
      />

      <p className="rounded-control border border-dashed border-line-strong px-3 py-2 text-xs text-ink-muted">
        Chưa có ở màn này: ghi chẩn đoán, soạn chỉ định dịch vụ, ký duyệt kết
        quả. Chúng là các node riêng (KHAM-*, DICHVU-DUYET-KETQUA) mà check-in
        chưa sinh ra — cần quyết định khi nào tạo chúng.
      </p>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
