"use client";

/**
 * Hàng đợi tiếp nhận — the reception desk's board.
 *
 * Two columns, not the design's three. The third column ("Điều phối tại quầy",
 * with the counter occupancy and the TV preview) has no schema behind it: there
 * is no counter table, no called_at, and no display device anywhere in the
 * system. Drawing it with invented numbers would make the desk trust a panel
 * that reports nothing, so it is left out and named as missing on the screen
 * instead. What IS real — the queue, the patient, the step they are on, what
 * comes next — is here.
 */

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import PriorityChip from "@/components/ui/PriorityChip";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import Stepper, { type Step } from "@/components/ui/Stepper";
import {
  STATUS_PRESENTATION,
  minutesPastDue,
  resolveStatus,
} from "@/lib/work-item-status";
import {
  patientLine,
  waitedMinutes,
  type WorklistItem,
} from "@/lib/worklist";

/** The sub-steps of reception, as the design draws them. */
function receptionSteps(item: WorklistItem): Step[] {
  const arrived = item.checked_in_at ?? item.created_at;
  const t = (v: string | null) =>
    v ? new Date(v).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }) : undefined;

  const started = item.status === "IN_PROGRESS";
  return [
    { label: "Vào hàng đợi", state: "done", detail: t(arrived) },
    {
      label: "Đang xử lý",
      state: started ? "done" : "current",
      detail: started ? t(item.started_at) : "Chưa bắt đầu",
    },
    {
      label: item.node_name ?? item.node_code,
      state: started ? "current" : "upcoming",
      detail: item.blocked ? "Đang bị chặn" : undefined,
    },
    { label: "Hoàn tất tiếp nhận", state: "upcoming", detail: "Chưa hoàn tất" },
  ];
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
  const waited = waitedMinutes(item);
  const late = minutesPastDue(item);

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
        <span className="mt-0.5 min-w-14 rounded-control bg-surface-sunken px-2 py-1 text-center text-sm font-semibold text-ink">
          {item.queue_number ?? "—"}
        </span>
        <span className="flex-1">
          <span className="flex items-center gap-2">
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
          <span
            className={`text-xs ${
              late !== null && late > 0 ? "text-status-overdue" : "text-ink-muted"
            }`}
          >
            {late !== null && late > 0 ? `quá hạn ${late}′` : `chờ ${waited}′`}
          </span>
        </span>
      </div>
    </button>
  );
}

export default function QueueBoard({ items }: { items: WorklistItem[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(items[0]?.id ?? null);
  const selected = items.find((i) => i.id === selectedId) ?? items[0] ?? null;

  if (items.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-10 text-center">
        <p className="font-medium text-ink">Hàng đợi trống</p>
        <p className="mt-1 text-sm text-ink-muted">
          Chưa có người bệnh nào chờ tiếp nhận hôm nay.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(340px,420px)_1fr]">
      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-medium text-ink-soft">
          Danh sách hàng đợi ({items.length})
        </h2>
        <div className="flex flex-col gap-2">
          {items.map((item) => (
            <Row
              key={item.id}
              item={item}
              selected={item.id === selected?.id}
              onSelect={() => setSelectedId(item.id)}
            />
          ))}
        </div>
      </section>

      {selected ? <Detail item={selected} /> : null}
    </div>
  );
}

function Detail({ item }: { item: WorklistItem }) {
  const tone = resolveStatus(item);
  const waited = waitedMinutes(item);

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
        <Field label="Số thứ tự" value={item.queue_number ?? "—"} />
        <Field label="Điện thoại" value={item.patient.phone_primary ?? "—"} />
        <Field label="Thời gian chờ" value={`${waited} phút`} />
        <Field
          label="Giờ hẹn"
          value={
            item.slot_start
              ? new Date(item.slot_start).toLocaleTimeString("vi-VN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—"
          }
        />
        <Field
          label="Kênh đặt"
          value={item.booking_channel === "WALK_IN" ? "Đến trực tiếp" : "Đặt hẹn"}
        />
        <Field label="Ưu tiên" value={item.is_priority_slot ? "Có" : "Không"} />
      </dl>

      <div>
        <h3 className="mb-3 text-sm font-medium text-ink-soft">Trạng thái xử lý</h3>
        <Stepper steps={receptionSteps(item)} />
      </div>

      {item.blocked ? (
        <p className="rounded-control bg-status-blocked-bg px-3 py-2 text-sm text-status-blocked">
          Bước này đang bị chặn bởi một bước chưa xong. Cổng quy trình sẽ mở khi
          bước trước hoàn tất.
        </p>
      ) : null}

      {!item.actionable_by_me ? (
        <p className="rounded-control bg-surface-sunken px-3 py-2 text-sm text-ink-muted">
          Bước này thuộc vai trò {item.actor_roles.join(", ") || "khác"} — bạn xem
          được nhưng không thao tác được.
        </p>
      ) : null}

      <Actions item={item} />

      {/* The counter dispatch column of the design lives here in spirit. It is
       * named rather than drawn, because inventing a counter number would be
       * worse than admitting there is not one yet. */}
      <p className="rounded-control border border-dashed border-line-strong px-3 py-2 text-xs text-ink-muted">
        Chưa có: điều phối quầy, số đã gọi, màn hình TV phòng chờ. Hệ thống chưa
        có bảng quầy hay mốc thời điểm gọi số — cần quyết định schema trước khi
        dựng phần này.
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

function Actions({ item }: { item: WorklistItem }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const disabled = pending || item.blocked || !item.actionable_by_me;

  async function issue(command: "start" | "complete") {
    setError(null);
    const res = await fetch(`/api/work-items/${item.id}/commands/${command}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // The version this screen last read. Sending it turns "someone else
      // already moved this patient along" into a refusal the desk can see,
      // instead of one clerk silently overwriting another.
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
    <div className="flex flex-col gap-2">
      {error ? (
        <p className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {item.status === "PENDING" ? (
          <button
            type="button"
            disabled={disabled}
            onClick={() => issue("start")}
            className="rounded-control border border-line px-4 py-2.5 text-sm font-medium text-ink hover:bg-surface-sunken disabled:cursor-not-allowed disabled:opacity-50"
          >
            Bắt đầu xử lý
          </button>
        ) : null}
        <button
          type="button"
          disabled={disabled}
          onClick={() => issue("complete")}
          className="rounded-control bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "Đang lưu…" : "Hoàn tất bước này"}
        </button>
      </div>
    </div>
  );
}
