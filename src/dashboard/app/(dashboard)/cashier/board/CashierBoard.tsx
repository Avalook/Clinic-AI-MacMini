"use client";

/**
 * Cost reconciliation uses the reference screen's list / ledger / inspector
 * layout while staying inside the data the current API actually returns.
 * There is no discrepancy record or external-source price in the schema yet,
 * so those controls remain visibly unavailable instead of displaying demo
 * facts as if they were operational data.
 */

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
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
  payments: {
    id: string;
    amount: number;
    voided_at: string | null;
    kind: string | null;
  }[];
  line_count: number;
  unpriced_lines: number;
  subtotal: number;
  collected: number;
  outstanding: number;
}

type ListFilter = "ALL" | "PENDING" | "IN_PROGRESS" | "BLOCKED";

const money = (value: number | null) =>
  value == null ? "—" : `${value.toLocaleString("vi-VN")} đ`;

const initials = (name: string | null) => {
  if (!name) return "?";
  const words = name.trim().split(/\s+/);
  return `${words.at(-2)?.[0] ?? ""}${words.at(-1)?.[0] ?? ""}`.toUpperCase();
};

const time = (value: string | null) =>
  value
    ? new Date(value).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

export default function CashierBoard({ items }: { items: WorklistItem[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(items[0]?.id ?? null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ListFilter>("ALL");

  const visibleItems = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi");
    return items.filter((item) => {
      const matchesQuery =
        needle.length === 0 ||
        [
          item.patient.full_name,
          item.patient.patient_code,
          item.visit_id,
        ].some((value) => value?.toLocaleLowerCase("vi").includes(needle));
      const matchesFilter =
        filter === "ALL" ||
        (filter === "BLOCKED" ? item.blocked : item.status === filter);
      return matchesQuery && matchesFilter;
    });
  }, [filter, items, query]);
  const selected =
    visibleItems.find((item) => item.id === selectedId) ?? visibleItems[0] ?? null;

  if (items.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-10 text-center shadow-card">
        <p className="font-medium text-ink">Không có lượt khám nào chờ thu ngân</p>
        <p className="mt-1 text-sm text-ink-muted">
          Các bước đối soát, thanh toán và đóng lượt sẽ hiện ở đây.
        </p>
      </div>
    );
  }

  // Cột giữa rộng hơn hai cột bên: bảng đối soát có ba cột tiền, và ở tỉ lệ cũ
  // cột "Đã thu" bị đẩy ra ngoài khung cuộn ngang. Trên màn hình mà việc duy
  // nhất của nó là đối soát tiền, số tiền không được là thứ bị cắt.
  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(200px,0.68fr)_minmax(430px,1.9fr)_minmax(240px,0.9fr)]">
      <section
        aria-label="Danh sách lượt khám"
        className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
      >
        <header className="border-b border-line px-3 py-3">
          <h2 className="text-sm font-semibold text-ink">Danh sách lượt khám</h2>
          <label className="mt-2 flex h-9 items-center gap-2 rounded-control border border-line bg-surface px-2.5 focus-within:border-brand-500">
            <Search aria-hidden className="size-4 shrink-0 text-ink-muted" />
            {/* Cột trái hẹp lại để nhường chỗ cho ba cột tiền, nên placeholder
                đầy đủ bị cắt giữa chừng. Câu đầy đủ chuyển sang nhãn — trình
                đọc màn hình vẫn nghe đủ, mắt vẫn hiểu tìm được bằng gì. */}
            <span className="sr-only">Tìm tên, mã BN hoặc mã lượt khám</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm tên, mã BN, mã lượt"
              className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          <label className="mt-2 block">
            <span className="sr-only">Lọc trạng thái</span>
            <select
              value={filter}
              onChange={(event) => setFilter(event.target.value as ListFilter)}
              className="h-9 w-full rounded-control border border-line bg-surface px-2.5 text-xs text-ink-soft outline-none focus:border-brand-500"
            >
              <option value="ALL">Tất cả trạng thái</option>
              <option value="PENDING">Chờ xử lý</option>
              <option value="IN_PROGRESS">Đang xử lý</option>
              <option value="BLOCKED">Bị chặn</option>
            </select>
          </label>
        </header>

        <div className="px-2 py-2">
          <p className="px-1 pb-2 text-xs font-semibold text-ink-soft">
            Lượt đang xử lý ({visibleItems.length})
          </p>
          <div className="max-h-[680px] space-y-1.5 overflow-y-auto">
            {visibleItems.length === 0 ? (
              <p className="rounded-control bg-surface-sunken px-3 py-6 text-center text-xs text-ink-muted">
                Không tìm thấy lượt khám phù hợp.
              </p>
            ) : (
              visibleItems.map((item) => (
                <VisitRow
                  key={item.id}
                  item={item}
                  selected={item.id === selected?.id}
                  onSelect={() => setSelectedId(item.id)}
                />
              ))
            )}
          </div>
        </div>
      </section>

      {selected ? <ReconciliationDetail item={selected} /> : null}
    </div>
  );
}

function VisitRow({
  item,
  selected,
  onSelect,
}: {
  item: WorklistItem;
  selected: boolean;
  onSelect: () => void;
}) {
  const status = resolveStatus(item);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={`w-full rounded-control border p-2.5 text-left transition-colors ${
        selected
          ? "border-brand-500 bg-surface-selected"
          : "border-line bg-surface hover:bg-surface-sunken"
      }`}
    >
      <span className="flex items-start gap-2.5">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-surface-sunken text-xs font-medium text-ink-soft">
          {initials(item.patient.full_name)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">
            {item.patient.full_name ?? "Chưa rõ tên"}
          </span>
          <span className="mt-0.5 block truncate text-[11px] text-ink-muted">
            {patientLine(item.patient) || "Chưa có nhân khẩu học"}
          </span>
          <span className="mt-0.5 block truncate text-[11px] text-ink-muted">
            {item.patient.patient_code ?? "Chưa có mã BN"} · {item.visit_id ?? "Chưa có mã lượt"}
          </span>
          <span className="mt-1.5 flex items-center justify-between gap-2">
            <span className="text-[11px] text-ink-faint">
              {time(item.started_at ?? item.created_at)} · chờ {waitedMinutes(item)}′
            </span>
            <StatusChip
              tone={STATUS_PRESENTATION[status].token as StatusTone}
              label={STATUS_PRESENTATION[status].label}
            />
          </span>
        </span>
      </span>
    </button>
  );
}

function ReconciliationDetail({ item }: { item: WorklistItem }) {
  const [loadErrorId, setLoadErrorId] = useState<string | null>(null);
  const [fetched, setFetched] = useState<{ id: string; data: Charges } | null>(null);
  const [selectedLine, setSelectedLine] = useState(0);
  const charges = fetched?.id === item.visit_id ? fetched.data : null;
  const chargeUnavailable = item.visit_id === null || loadErrorId === item.visit_id;
  const currentLine = charges?.lines[selectedLine] ?? charges?.lines[0] ?? null;
  const status = resolveStatus(item);

  useEffect(() => {
    if (!item.visit_id) return;
    const visitId = item.visit_id;
    let cancelled = false;
    fetch(`/api/visits/${visitId}/charges`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!cancelled && data && !data.error) {
          setFetched({ id: visitId, data: data as Charges });
          setLoadErrorId((current) => (current === visitId ? null : current));
        } else if (!cancelled) {
          setLoadErrorId(visitId);
        }
      })
      .catch(() => {
        if (!cancelled) setLoadErrorId(visitId);
      });
    return () => {
      cancelled = true;
    };
  }, [item.visit_id]);

  // The API has no discrepancy records, external-source values or signed
  // reconciliation record. Keep the workflow unchanged until that evidence
  // exists, so staff cannot start a step that the UI cannot safely complete.

  return (
    <>
      <section
        aria-label="Bảng đối soát chi tiết"
        className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
      >
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line p-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-line bg-surface-sunken text-sm font-medium text-ink-soft">
              {initials(item.patient.full_name)}
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-ink">
                {item.patient.full_name ?? "Chưa rõ tên"}
              </h2>
              <p className="text-xs text-ink-muted">
                {patientLine(item.patient) || "Chưa có nhân khẩu học"}
              </p>
              <p className="mt-1 text-xs text-ink-muted">
                {item.patient.patient_code ?? "Chưa có mã BN"}
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs sm:grid-cols-3">
            <Info label="Mã lượt khám" value={item.visit_id ?? "—"} />
            <Info label="Bước hiện tại" value={item.node_name ?? item.node_code} />
            <Info label="Bắt đầu" value={time(item.started_at)} />
          </dl>
        </header>

        <dl className="grid grid-cols-3 divide-x divide-line border-b border-line py-3 text-center">
          <Total
            label="Tổng phát sinh"
            value={
              charges && charges.unpriced_lines === 0 ? money(charges.subtotal) : "—"
            }
          />
          <Total label="Đã thu" value={charges ? money(charges.collected) : "—"} tone="success" />
          <Total
            label="Còn mở"
            value={
              charges && charges.unpriced_lines === 0 ? money(charges.outstanding) : "—"
            }
            tone="danger"
          />
        </dl>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] border-collapse text-xs">
            <thead className="bg-surface-muted text-ink-muted">
              <tr>
                <th className="border-b border-line px-2 py-2 text-left font-medium">Nguồn</th>
                <th className="border-b border-line px-2 py-2 text-left font-medium">Hạng mục</th>
                <th className="border-b border-line px-2 py-2 text-left font-medium">Trạng thái thực hiện</th>
                {/* Ba cột tiền không xuống dòng và không co lại: chúng là lý do
                    màn này tồn tại, nên phần bị ép phải là cột chữ bên trái. */}
                <th className="w-[88px] whitespace-nowrap border-b border-line px-2 py-2 text-right font-medium">Phải thu</th>
                <th className="w-[88px] whitespace-nowrap border-b border-line px-2 py-2 text-right font-medium">Đã thu</th>
                <th className="w-[88px] whitespace-nowrap border-b border-line px-2 py-2 text-right font-medium">Sai lệch</th>
              </tr>
            </thead>
            <tbody>
              {chargeUnavailable ? (
                <MessageRow message="Không tải được dữ liệu chi phí của lượt khám này." />
              ) : charges === null ? (
                <MessageRow message="Đang tải dữ liệu đối soát…" />
              ) : charges.lines.length === 0 ? (
                <MessageRow message="Lượt khám này chưa có chỉ định dịch vụ nào." />
              ) : (
                charges.lines.map((l, index) => {
                  const lineStatus = resolveStatus({
                    status: l.node_status as WorklistItem["status"],
                  });
                  return (
                    <tr
                      key={`${l.service_code}-${index}`}
                      className={`border-b border-line last:border-0 hover:bg-surface-sunken ${
                        currentLine === l ? "bg-surface-selected" : ""
                      }`}
                    >
                      <td className="px-2 py-3 text-ink-soft">{l.node_name ?? "—"}</td>
                      <td className="px-2 py-3">
                        <button
                          type="button"
                          onClick={() => setSelectedLine(index)}
                          aria-pressed={currentLine === l}
                          aria-label={`Chọn hạng mục ${l.name ?? l.service_code ?? "chưa rõ"}`}
                          className="block w-full rounded text-left outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                        >
                          <span className="block font-medium text-ink">
                            {l.name ?? l.service_code ?? "Chưa rõ hạng mục"}
                          </span>
                          <span className="mt-0.5 block text-[11px] text-ink-faint">
                            {l.service_code ?? "Chưa có mã"}
                          </span>
                        </button>
                      </td>
                      <td className="px-2 py-3">
                        <StatusChip
                          tone={STATUS_PRESENTATION[lineStatus].token as StatusTone}
                          label={STATUS_PRESENTATION[lineStatus].label}
                        />
                      </td>
                      <td className="px-2 py-3 text-right font-medium text-ink tabular-nums">
                        {money(l.unit_price)}
                      </td>
                      <td className="px-2 py-3 text-right text-ink-muted">—</td>
                      <td className="px-2 py-3 text-right text-ink-muted">Chưa có dữ liệu</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="border-t border-line p-3">
          {charges && charges.unpriced_lines > 0 ? (
            <div className="rounded-control border border-warning bg-warning-bg px-3 py-2.5 text-sm text-warning">
              <p className="font-medium">Chưa tính được thành tiền</p>
              <p className="mt-0.5 text-xs">
                {charges.unpriced_lines}/{charges.line_count} dịch vụ chưa có giá trong bảng giá.
                Tạm tính phần đã có giá là {money(charges.subtotal)}; cần nhập đủ giá trước khi
                có thể xác định tổng phát sinh và số còn mở.
              </p>
            </div>
          ) : (
            <p className="rounded-control border border-line bg-surface-sunken px-3 py-2 text-xs text-ink-muted">
              Bảng chưa phân bổ số tiền đã thu theo từng hạng mục; tổng đã thu phía trên là số thật của lượt khám.
            </p>
          )}
        </div>
      </section>

      <aside
        aria-label="Chi tiết đối soát"
        className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
      >
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">Chi tiết đối soát</h2>
        </div>

        <div className="space-y-4 p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-ink-muted">Trạng thái bước</span>
            <StatusChip
              tone={STATUS_PRESENTATION[status].token as StatusTone}
              label={STATUS_PRESENTATION[status].label}
            />
          </div>

          <section className="border-t border-line pt-3">
            <h3 className="text-xs font-semibold text-ink">Hạng mục đang chọn</h3>
            {currentLine ? (
              <dl className="mt-2 grid grid-cols-[105px_1fr] gap-x-3 gap-y-2 text-xs">
                <InfoRow label="Nguồn" value={currentLine.node_name ?? "—"} />
                <InfoRow label="Dịch vụ" value={currentLine.name ?? currentLine.service_code ?? "—"} />
                <InfoRow label="Mã" value={currentLine.service_code ?? "—"} />
                <InfoRow label="Giá hệ thống" value={money(currentLine.unit_price)} />
                <InfoRow label="Nguồn ngoài" value="Chưa có dữ liệu" />
              </dl>
            ) : (
              <p className="mt-2 text-xs text-ink-muted">Chọn một hạng mục để xem chi tiết.</p>
            )}
          </section>

          <section className="rounded-control border border-line p-3">
            <h3 className="text-xs font-semibold text-ink">Checklist trước khi đối soát</h3>
            <ul className="mt-2 space-y-2 text-xs">
              <Check
                ok={Boolean(charges && charges.line_count > 0)}
                label="Có dữ liệu dịch vụ của lượt khám"
              />
              <Check
                ok={Boolean(charges && charges.unpriced_lines === 0)}
                label="Bảng giá đầy đủ"
              />
              <Check ok={false} label="Chưa có nguồn dữ liệu sai lệch chi tiết" />
              <Check ok={false} label="Chưa có biên bản đối soát nguồn ngoài" />
            </ul>
          </section>

          <label className="block">
            <span className="text-xs font-medium text-ink-soft">Ghi chú kiểm tra</span>
            <textarea
              disabled
              rows={3}
              placeholder="Chưa có nơi lưu ghi chú đối soát."
              className="mt-1.5 w-full resize-none rounded-control border border-line bg-surface-sunken px-3 py-2 text-xs text-ink-muted placeholder:text-ink-faint"
            />
          </label>

          <div className="rounded-control border border-brand-200 bg-brand-50 px-3 py-2.5 text-xs text-brand-700">
            <p className="font-medium">Quyền đối soát</p>
            <p className="mt-0.5">
              {item.actionable_by_me
                ? "Bước hiện tại chờ nguồn sai lệch và biên bản đối soát trước khi có thể bắt đầu."
                : "Bạn chỉ có quyền xem bước này."}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 border-t border-line pt-3">
            <button
              type="button"
              disabled
              title="Chưa có API giao việc xử lý sai lệch"
              className="rounded-control border border-line bg-surface-sunken px-2 py-2 text-xs font-medium text-ink-faint disabled:cursor-not-allowed"
            >
              Giao việc xử lý
            </button>
            <button
              type="button"
              disabled
              title="Chưa có API lưu ghi chú đối soát"
              className="rounded-control border border-line bg-surface-sunken px-2 py-2 text-xs font-medium text-ink-faint disabled:cursor-not-allowed"
            >
              Lưu ghi chú
            </button>

            {item.status === "PENDING" ? (
              <button
                type="button"
                disabled
                title="Chưa có nguồn sai lệch và biên bản đối soát để hoàn tất quy trình"
                className="col-span-2 rounded-control border border-brand-600 bg-surface px-3 py-2.5 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken disabled:text-ink-faint"
              >
                Bắt đầu đối soát
              </button>
            ) : null}

            <button
              type="button"
              disabled
              title="Chưa có nguồn sai lệch và biên bản đối soát để xác nhận"
              className="col-span-2 rounded-control bg-brand-600 px-3 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
            >
              {item.status === "COMPLETED"
                ? "Đã đối soát"
                : "Xác nhận đã đối soát"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] text-ink-muted">{label}</dt>
      <dd className="mt-0.5 max-w-44 truncate font-medium text-ink" title={value}>
        {value}
      </dd>
    </div>
  );
}

function Total({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "success" | "danger";
}) {
  const color =
    tone === "success" ? "text-success" : tone === "danger" ? "text-danger" : "text-ink";
  return (
    <div className="px-2">
      <dt className="text-[11px] text-ink-muted">{label}</dt>
      <dd className={`mt-1 text-base font-semibold tabular-nums ${color}`}>{value}</dd>
    </div>
  );
}

function MessageRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={6} className="px-3 py-10 text-center text-sm text-ink-muted">
        {message}
      </td>
    </tr>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-ink-muted">{label}</dt>
      <dd className="min-w-0 break-words text-ink">{value}</dd>
    </>
  );
}

function Check({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-start gap-2">
      <span
        aria-hidden
        className={`mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border text-[10px] ${
          ok
            ? "border-success bg-success-bg text-success"
            : "border-line-strong bg-surface-sunken text-ink-muted"
        }`}
      >
        {ok ? "✓" : "—"}
      </span>
      <span className={ok ? "text-success" : "text-ink-muted"}>{label}</span>
    </li>
  );
}
