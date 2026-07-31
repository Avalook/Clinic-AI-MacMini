"use client";

/**
 * Bàn thu ngân — the cashier's board.
 *
 * The third screen on the same worklist endpoint (workspace=thu_ngan_dong_luot).
 * Three nodes live there: đối soát chi phí, thanh toán, đóng lượt khám.
 *
 * WHAT THIS SCREEN CAN AND CANNOT DO TODAY. The clinic's price list is entirely
 * empty — service_price and drug_catalog have no unit_price at all, in
 * production as well as locally, and every payment ever recorded is 0. So the
 * "thanh toán" step cannot compute an amount, and this screen does not pretend
 * to: it shows what the patient actually had done, which is the reconciliation
 * step's real job, and says plainly that the totals are not available.
 *
 * A zero shown as a total would be read as "nothing to pay". An em dash with a
 * reason cannot be.
 */

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import WorkItemActions from "@/components/ui/WorkItemActions";
import { STATUS_PRESENTATION, resolveStatus } from "@/lib/work-item-status";
import { patientLine, waitedMinutes, type WorklistItem } from "@/lib/worklist";

interface ChargeLine {
  node_name: string | null;
  node_status: string;
  name: string | null;
  service_code: string | null;
  unit_price: number | null;
}

interface Charges {
  lines: ChargeLine[];
  payments: { id: string; amount: number; voided_at: string | null; kind: string | null }[];
  line_count: number;
  unpriced_lines: number;
  subtotal: number;
  collected: number;
  outstanding: number;
}

const money = (v: number | null) =>
  v == null ? "—" : `${v.toLocaleString("vi-VN")} đ`;

export default function CashierBoard({ items }: { items: WorklistItem[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(items[0]?.id ?? null);
  const selected = items.find((i) => i.id === selectedId) ?? items[0] ?? null;

  if (items.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-10 text-center">
        <p className="font-medium text-ink">Không có lượt khám nào chờ thu ngân</p>
        <p className="mt-1 text-sm text-ink-muted">
          Các bước đối soát, thanh toán và đóng lượt sẽ hiện ở đây.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(330px,400px)_1fr]">
      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-medium text-ink-soft">
          Chờ xử lý ({items.length})
        </h2>
        {items.map((item) => {
          const tone = resolveStatus(item);
          const on = item.id === selected?.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelectedId(item.id)}
              aria-current={on ? "true" : undefined}
              className={`w-full rounded-card border px-4 py-3 text-left transition-colors ${
                on
                  ? "border-l-[3px] border-brand-600 bg-surface-selected"
                  : "border-line bg-surface hover:bg-surface-sunken"
              }`}
            >
              <div className="flex items-start gap-3">
                <span className="flex-1">
                  <span className="block font-medium text-ink">
                    {item.patient.full_name ?? "Chưa rõ tên"}
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
                    {waitedMinutes(item)}′
                  </span>
                </span>
              </div>
            </button>
          );
        })}
      </section>
      {selected ? <Detail item={selected} /> : null}
    </div>
  );
}

function Detail({ item }: { item: WorklistItem }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fetched, setFetched] = useState<{ id: string; data: Charges } | null>(null);
  const charges = fetched?.id === item.visit_id ? fetched.data : null;
  const tone = resolveStatus(item);

  useEffect(() => {
    if (!item.visit_id) return;
    const visitId = item.visit_id;
    let cancelled = false;
    fetch(`/api/visits/${visitId}/charges`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled && d && !d.error) setFetched({ id: visitId, data: d as Charges });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [item.visit_id]);

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
            {patientLine(item.patient)} · {item.node_name ?? item.node_code}
          </p>
        </div>
        <StatusChip
          tone={STATUS_PRESENTATION[tone].token as StatusTone}
          label={STATUS_PRESENTATION[tone].label}
          size="md"
        />
      </header>

      <div>
        <h3 className="mb-2 text-sm font-medium text-ink-soft">
          Dịch vụ đã chỉ định {charges ? `(${charges.line_count})` : ""}
        </h3>
        {charges === null ? (
          <p className="text-sm text-ink-faint">Đang tải…</p>
        ) : charges.lines.length === 0 ? (
          <p className="rounded-control bg-surface-sunken px-3 py-2 text-sm text-ink-muted">
            Lượt khám này chưa có chỉ định dịch vụ nào.
          </p>
        ) : (
          <ul className="divide-y divide-line rounded-card border border-line">
            {charges.lines.map((l, i) => (
              <li
                key={`${l.service_code}-${i}`}
                className="flex items-center gap-3 px-3 py-2 text-sm"
              >
                <span className="flex-1">
                  <span className="block text-ink">{l.name ?? l.service_code}</span>
                  <span className="block text-xs text-ink-faint">
                    {l.node_name} · {l.service_code}
                  </span>
                </span>
                {/* Through the shared resolver, not a second vocabulary. I
                    first wrote custom labels here and paired "Chưa thực hiện"
                    with the `ready` tone — a green chip on a line that has NOT
                    been done, which reads as the opposite of the truth. The
                    line's state IS its work item's state; there is no reason
                    for the cashier's screen to name it differently from the
                    board it came from. */}
                {(() => {
                  const s = resolveStatus({
                    status: l.node_status as WorklistItem["status"],
                  });
                  return (
                    <StatusChip
                      tone={STATUS_PRESENTATION[s].token as StatusTone}
                      label={STATUS_PRESENTATION[s].label}
                    />
                  );
                })()}
                <span className="w-24 text-right text-ink-soft tabular-nums">
                  {money(l.unit_price)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {charges && charges.unpriced_lines > 0 ? (
        /* A zero here would be read as "nothing to pay". */
        <div className="rounded-control bg-warning-bg px-3 py-2.5 text-sm text-warning">
          <p className="font-medium">Chưa tính được thành tiền</p>
          <p className="mt-0.5 text-xs">
            {charges.unpriced_lines}/{charges.line_count} dịch vụ chưa có giá
            trong bảng giá. Phải nhập bảng giá trước khi màn này thu tiền được —
            hiện tại chỉ dùng để đối soát dịch vụ đã thực hiện.
          </p>
        </div>
      ) : charges ? (
        <dl className="grid grid-cols-3 gap-4 border-y border-line py-3 text-sm">
          <div>
            <dt className="text-xs text-ink-muted">Tạm tính</dt>
            <dd className="text-ink tabular-nums">{money(charges.subtotal)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Đã thu</dt>
            <dd className="text-ink tabular-nums">{money(charges.collected)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Còn lại</dt>
            <dd className="font-medium text-ink tabular-nums">
              {money(charges.outstanding)}
            </dd>
          </div>
        </dl>
      ) : null}

      <WorkItemActions
        status={item.status}
        blocked={item.blocked}
        actionableByMe={item.actionable_by_me}
        actorRoles={item.actor_roles}
        pending={pending}
        error={error}
        onIssue={issue}
      />

      <p className="rounded-control border border-dashed border-line-strong px-3 py-2 text-xs text-ink-muted">
        Chưa có ở màn này: thu tiền thật (cần bảng giá), in hoá đơn, cổng POS.
        `POST /payments` đã tồn tại nhưng chưa nối vào đây — nối một nút thu tiền
        vào một bảng giá rỗng chỉ tạo ra những khoản 0đ như 5 dòng đang có ở
        production.
      </p>
    </section>
  );
}
