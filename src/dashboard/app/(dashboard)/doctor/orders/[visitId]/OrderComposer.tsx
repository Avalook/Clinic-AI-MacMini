"use client";

/**
 * Order composer — the doctor picks services, and work appears in the room that
 * performs each one.
 *
 * Grouped BY ROOM rather than by the price list's own categories. The price
 * list has one group ("dich_vu") for all 29 services, which tells the doctor
 * nothing; the room does — ordering four things that all happen in the
 * ultrasound room is one trip for the patient, and seeing them together is how
 * you notice that.
 *
 * The bundles ("Bộ khám phụ khoa cơ bản") in the design are not here: there is
 * no bundle table, and inventing five hard-coded bundles in a component would
 * put clinical protocol in the frontend, which is the one place it must never
 * live. It belongs in the catalogue, as data, next to the services.
 */

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import StatusChip from "@/components/ui/StatusChip";

export interface CatalogueEntry {
  service_code: string;
  name: string;
  unit_price: number | null;
  node_code: string | null;
  node_name: string | null;
  workspace: string | null;
  orderable: boolean;
}

interface Duplicate {
  service_code: string;
  name: string | null;
  ordered_at: string;
}

function money(v: number | null): string {
  return v == null ? "—" : `${v.toLocaleString("vi-VN")} đ`;
}

export default function OrderComposer({
  visitId,
  patientName,
  catalogue,
}: {
  visitId: string;
  patientName: string;
  catalogue: CatalogueEntry[];
}) {
  const router = useRouter();
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [dupes, setDupes] = useState<Duplicate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const rooms = new Map<string, CatalogueEntry[]>();
  for (const s of catalogue) {
    if (query && !`${s.name} ${s.service_code}`.toLowerCase().includes(query.toLowerCase())) {
      continue;
    }
    const key = s.node_name ?? "Chưa cấu hình phòng thực hiện";
    if (!rooms.has(key)) rooms.set(key, []);
    rooms.get(key)!.push(s);
  }

  const selected = catalogue.filter((s) => chosen.has(s.service_code));
  const subtotal = selected.reduce((sum, s) => sum + (s.unit_price ?? 0), 0);
  const anyPriceMissing = selected.some((s) => s.unit_price == null);

  async function toggle(code: string) {
    const next = new Set(chosen);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setChosen(next);
    setDone(null);

    // Ask about duplicates as the doctor builds the list, not at submit: the
    // point is to change her mind before she orders, not to warn her after.
    const codes = [...next];
    if (codes.length === 0) {
      setDupes([]);
      return;
    }
    const res = await fetch(`/api/visits/${visitId}/service-orders/duplicates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service_codes: codes }),
    });
    if (res.ok) setDupes((await res.json()) as Duplicate[]);
  }

  async function submit() {
    setError(null);
    setDone(null);
    const res = await fetch(`/api/visits/${visitId}/service-orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service_codes: [...chosen] }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      setError(body?.error ?? `Không gửi được chỉ định (HTTP ${res.status})`);
      return;
    }
    const rooms = (await res.json()) as { node_code: string; service_count: number }[];
    setDone(
      `Đã gửi ${chosen.size} dịch vụ tới ${rooms.length} phòng: ` +
        rooms.map((r) => `${r.node_code} (${r.service_count})`).join(", "),
    );
    setChosen(new Set());
    setDupes([]);
    startTransition(() => router.refresh());
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
      <section className="flex flex-col gap-4">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Tìm dịch vụ theo tên hoặc mã…"
          className="w-full rounded-control border border-line bg-surface px-4 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-brand-500 focus:outline-none"
        />

        {[...rooms.entries()].map(([room, services]) => (
          <div
            key={room}
            className="rounded-card border border-line bg-surface shadow-card"
          >
            <header className="flex items-baseline justify-between border-b border-line px-4 py-2.5">
              <h3 className="text-sm font-medium text-ink">{room}</h3>
              <span className="text-xs text-ink-faint">
                {services.length} dịch vụ
              </span>
            </header>
            <ul className="divide-y divide-line">
              {services.map((s) => (
                <li key={s.service_code}>
                  <label
                    className={`flex items-center gap-3 px-4 py-2.5 text-sm ${
                      s.orderable
                        ? "cursor-pointer hover:bg-surface-sunken"
                        : "cursor-not-allowed opacity-60"
                    }`}
                  >
                    <input
                      type="checkbox"
                      disabled={!s.orderable}
                      checked={chosen.has(s.service_code)}
                      onChange={() => toggle(s.service_code)}
                      className="h-4 w-4 accent-[var(--color-brand-600)]"
                    />
                    <span className="flex-1">
                      <span className="block text-ink">{s.name}</span>
                      <span className="block text-xs text-ink-faint tabular-nums">
                        {s.service_code}
                      </span>
                    </span>
                    {!s.orderable ? (
                      <StatusChip
                        tone="blocked"
                        label="Chưa gắn phòng thực hiện"
                      />
                    ) : (
                      <span className="text-sm text-ink-soft tabular-nums">
                        {money(s.unit_price)}
                      </span>
                    )}
                  </label>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <aside className="flex h-fit flex-col gap-3 rounded-card border border-line bg-surface p-4 shadow-card lg:sticky lg:top-4">
        <h3 className="font-medium text-ink">Tóm tắt chỉ định</h3>
        <p className="text-sm text-ink-muted">{patientName}</p>

        {selected.length === 0 ? (
          <p className="py-6 text-center text-sm text-ink-faint">
            Chưa chọn dịch vụ nào.
          </p>
        ) : (
          <ul className="flex flex-col gap-1 border-y border-line py-3 text-sm">
            {selected.map((s) => (
              <li key={s.service_code} className="flex justify-between gap-2">
                <span className="text-ink">{s.name}</span>
                <span className="text-ink-soft tabular-nums">
                  {money(s.unit_price)}
                </span>
              </li>
            ))}
          </ul>
        )}

        <div className="flex justify-between text-sm">
          <span className="text-ink-muted">Tổng dịch vụ</span>
          <span className="font-medium text-ink tabular-nums">
            {selected.length}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-ink-muted">Tạm tính</span>
          <span className="font-semibold text-ink tabular-nums">
            {money(subtotal || null)}
          </span>
        </div>
        {anyPriceMissing ? (
          /* Silence here would read as free. */
          <p className="rounded-control bg-status-on-hold-bg px-2.5 py-1.5 text-xs text-status-on-hold">
            Một số dịch vụ chưa có giá trong bảng giá — tạm tính chưa đầy đủ.
          </p>
        ) : null}

        {dupes.length > 0 ? (
          <div className="rounded-control bg-status-on-hold-bg px-2.5 py-2 text-xs text-status-on-hold">
            <p className="font-medium">Đã chỉ định trùng trong 30 ngày</p>
            <ul className="mt-1 list-inside list-disc">
              {dupes.map((d) => (
                <li key={`${d.service_code}-${d.ordered_at}`}>
                  {d.name ?? d.service_code} —{" "}
                  {new Date(d.ordered_at).toLocaleDateString("vi-VN")}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {error ? (
          <p className="rounded-control bg-danger-bg px-2.5 py-2 text-sm text-danger">
            {error}
          </p>
        ) : null}
        {done ? (
          <p className="rounded-control bg-status-completed-bg px-2.5 py-2 text-sm text-status-completed">
            {done}
          </p>
        ) : null}

        <button
          type="button"
          disabled={selected.length === 0 || pending}
          onClick={submit}
          className="rounded-control bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "Đang gửi…" : "Gửi chỉ định"}
        </button>
        <p className="text-xs text-ink-faint">
          Gửi chỉ định không đóng bước &ldquo;Tạo chỉ định dịch vụ&rdquo; — bác
          sĩ đóng bước đó ở Bàn khám khi đã xong.
        </p>
      </aside>
    </div>
  );
}
