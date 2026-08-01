"use client";

/**
 * Price-catalog workspace shared by the medicine and service routes.
 *
 * These routes configure prices; they do not collect payment or dispense
 * medicine. The V2 treatment therefore borrows the references' dense catalog,
 * summary strip and right-hand action panel without inventing patient,
 * obligation, stock or transaction data that this endpoint does not provide.
 */

import {
  CircleAlert,
  CircleCheck,
  CirclePause,
  ClipboardList,
  Info,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

export type PriceGroup = "thuoc" | "dich_vu";

export interface PriceRow {
  id: string;
  service_code: string;
  name: string;
  group: PriceGroup;
  unit_price: number | null;
  active: boolean;
}

type CatalogFilter = "ALL" | "ACTIVE" | "INACTIVE" | "UNPRICED";

const VIEW_LABEL: Record<PriceGroup, string> = {
  thuoc: "Bảng giá thuốc",
  dich_vu: "Bảng giá dịch vụ",
};

const VIEWS: PriceGroup[] = ["thuoc", "dich_vu"];

const inputClass =
  "h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink " +
  "outline-none placeholder:text-ink-faint focus:border-brand-500 focus:ring-2 focus:ring-brand-100 " +
  "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint";

function formatVnd(value: number | null): string {
  if (value === null) return "— Chưa nhập";
  return `${new Intl.NumberFormat("vi-VN").format(value)} ₫`;
}

export default function CashierView({
  rows,
  group: lockedGroup,
}: {
  rows: PriceRow[];
  group?: PriceGroup;
}) {
  const router = useRouter();
  const [view, setView] = useState<PriceGroup>(lockedGroup ?? "thuoc");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<CatalogFilter>("ALL");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});

  const activeCount = rows.filter((row) => row.active).length;
  const missingPriceCount = rows.filter((row) => row.unit_price === null).length;
  const inactiveCount = rows.length - activeCount;

  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi");
    return rows.filter((row) => {
      if (row.group !== view) return false;
      const matchesQuery =
        needle.length === 0 ||
        row.service_code.toLocaleLowerCase("vi").includes(needle) ||
        row.name.toLocaleLowerCase("vi").includes(needle);
      const matchesFilter =
        filter === "ALL" ||
        (filter === "ACTIVE" && row.active) ||
        (filter === "INACTIVE" && !row.active) ||
        (filter === "UNPRICED" && row.unit_price === null);
      return matchesQuery && matchesFilter;
    });
  }, [filter, query, rows, view]);

  async function send(method: "POST" | "PATCH" | "DELETE", body: unknown) {
    setError(null);
    setBusy(true);
    try {
      const response = await fetch("/api/service-price", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const result = (await response.json().catch(() => null)) as {
          error?: string;
        } | null;
        setError(result?.error ?? "Không lưu được thay đổi. Vui lòng thử lại.");
        return false;
      }
      router.refresh();
      return true;
    } catch {
      setError("Không kết nối được máy chủ. Thay đổi chưa được lưu.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function add() {
    if (!code.trim() || !name.trim()) {
      setError("Mã và tên là hai trường bắt buộc.");
      return;
    }
    const ok = await send("POST", {
      service_code: code.trim(),
      name: name.trim(),
      group: view,
      unit_price: price.trim() === "" ? null : price.trim(),
    });
    if (ok) {
      setCode("");
      setName("");
      setPrice("");
    }
  }

  async function savePrice(id: string) {
    const raw = draft[id];
    if (raw === undefined) return;
    const ok = await send("PATCH", {
      id,
      unit_price: raw.trim() === "" ? null : raw.trim(),
    });
    if (ok) {
      setDraft((current) =>
        Object.fromEntries(Object.entries(current).filter(([key]) => key !== id)),
      );
    }
  }

  async function toggleActive(row: PriceRow) {
    await send("PATCH", { id: row.id, active: !row.active });
  }

  async function remove(id: string, rowName: string) {
    if (!window.confirm(`Xoá “${rowName}” khỏi bảng giá? Thao tác này không thể hoàn tác.`)) {
      return;
    }
    await send("DELETE", { id });
  }

  return (
    <div className="space-y-4">
      {!lockedGroup ? (
        <div className="inline-flex rounded-control border border-line bg-surface p-1 shadow-card">
          {VIEWS.map((group) => (
            <button
              key={group}
              type="button"
              onClick={() => setView(group)}
              aria-pressed={view === group}
              className={`rounded-chip px-4 py-2 text-sm font-medium transition-colors ${
                view === group
                  ? "bg-brand-600 text-white"
                  : "text-ink-soft hover:bg-surface-sunken"
              }`}
            >
              {VIEW_LABEL[group]}
            </button>
          ))}
        </div>
      ) : null}

      <section
        aria-label="Tổng quan bảng giá"
        className="grid overflow-hidden rounded-card border border-line bg-surface shadow-card sm:grid-cols-2 xl:grid-cols-4"
      >
        <Metric icon={<ClipboardList className="size-5" />} label="Tổng danh mục" value={rows.length} />
        <Metric icon={<CircleCheck className="size-5" />} label="Đang áp dụng" value={activeCount} tone="success" />
        <Metric icon={<CirclePause className="size-5" />} label="Tạm ngưng" value={inactiveCount} />
        <Metric icon={<CircleAlert className="size-5" />} label="Thiếu giá" value={missingPriceCount} tone="warning" />
      </section>

      {error ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2.5 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="grid items-start gap-4 2xl:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]">
        <section
          aria-label="Danh mục bảng giá"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-ink">Danh mục hiện tại</h2>
              <p className="text-xs text-ink-muted">Hiển thị {visible.length} trong {rows.length} dòng</p>
            </div>
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              <label className="flex h-9 min-w-60 items-center gap-2 rounded-control border border-line bg-surface px-2.5 focus-within:border-brand-500">
                <Search aria-hidden className="size-4 shrink-0 text-ink-muted" />
                <span className="sr-only">Tìm theo mã hoặc tên</span>
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Tìm theo mã hoặc tên"
                  className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
                />
              </label>
              <label>
                <span className="sr-only">Lọc trạng thái giá</span>
                <select
                  value={filter}
                  onChange={(event) => setFilter(event.target.value as CatalogFilter)}
                  className="h-9 w-full rounded-control border border-line bg-surface px-2.5 text-xs text-ink-soft outline-none focus:border-brand-500 sm:w-40"
                >
                  <option value="ALL">Tất cả trạng thái</option>
                  <option value="ACTIVE">Đang áp dụng</option>
                  <option value="INACTIVE">Tạm ngưng</option>
                  <option value="UNPRICED">Thiếu giá</option>
                </select>
              </label>
            </div>
          </header>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-sm">
              <thead className="bg-surface-muted text-xs text-ink-muted">
                <tr>
                  <th className="border-b border-line px-4 py-2.5 text-left font-medium">Mã danh mục</th>
                  <th className="border-b border-line px-4 py-2.5 text-left font-medium">Tên thuốc / dịch vụ</th>
                  <th className="border-b border-line px-4 py-2.5 text-left font-medium">Đơn giá</th>
                  <th className="border-b border-line px-4 py-2.5 text-left font-medium">Trạng thái</th>
                  <th className="border-b border-line px-4 py-2.5 text-right font-medium">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {visible.length === 0 ? (
                  <tr>
                    <td className="px-4 py-12 text-center text-sm text-ink-muted" colSpan={5}>
                      Không có dòng bảng giá phù hợp.
                    </td>
                  </tr>
                ) : (
                  visible.map((row) => {
                    const editedPrice = draft[row.id];
                    const editing = editedPrice !== undefined;
                    return (
                      <tr key={row.id} className="hover:bg-surface-muted">
                        <td className="px-4 py-3 font-mono text-xs font-medium text-ink-soft">
                          {row.service_code}
                        </td>
                        <td className="px-4 py-3 text-ink">{row.name}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <input
                              aria-label={`Đơn giá ${row.name}`}
                              className="h-9 w-32 rounded-control border border-line bg-surface px-2.5 text-right text-sm text-ink tabular-nums outline-none placeholder:text-ink-faint focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                              inputMode="numeric"
                              value={editing ? editedPrice : row.unit_price ?? ""}
                              placeholder="Chưa nhập"
                              disabled={busy}
                              onChange={(event) =>
                                setDraft((current) => ({
                                  ...current,
                                  [row.id]: event.target.value,
                                }))
                              }
                            />
                            {editing ? (
                              <button
                                type="button"
                                onClick={() => savePrice(row.id)}
                                disabled={busy}
                                className="rounded-control bg-brand-600 px-3 py-2 text-xs font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
                              >
                                Lưu
                              </button>
                            ) : (
                              <span className="whitespace-nowrap text-xs text-ink-muted">
                                {formatVnd(row.unit_price)}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-ink-soft">
                            <input
                              type="checkbox"
                              checked={row.active}
                              disabled={busy}
                              onChange={() => toggleActive(row)}
                              className="size-4 accent-brand-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500"
                            />
                            {row.active ? "Đang áp dụng" : "Tạm ngưng"}
                          </label>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            onClick={() => remove(row.id, row.name)}
                            disabled={busy}
                            aria-label={`Xoá ${row.name}`}
                            className="rounded-control p-2 text-ink-faint hover:bg-danger-bg hover:text-danger focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <Trash2 aria-hidden className="size-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        <aside
          aria-label="Thêm dòng bảng giá"
          className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <header className="border-b border-line px-4 py-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Plus aria-hidden className="size-4 text-brand-600" />
              Thêm vào {VIEW_LABEL[view].toLocaleLowerCase("vi")}
            </h2>
            <p className="mt-1 text-xs text-ink-muted">Tạo một mã mới trong danh mục đang chọn.</p>
          </header>

          <div className="space-y-4 p-4">
            <Field label="Mã danh mục" required>
              <input
                className={inputClass}
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder={view === "thuoc" ? "VD: MED001" : "VD: DV001"}
                maxLength={64}
                required
              />
            </Field>
            <Field label={view === "thuoc" ? "Tên thuốc" : "Tên dịch vụ"} required>
              <input
                className={inputClass}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Nhập tên hiển thị"
                maxLength={200}
                required
              />
            </Field>
            <Field label="Đơn giá (₫)">
              <input
                className={inputClass}
                value={price}
                inputMode="numeric"
                onChange={(event) => setPrice(event.target.value)}
                placeholder="Có thể để trống"
              />
            </Field>

            <div className="rounded-control border border-warning bg-warning-bg px-3 py-2.5 text-xs text-warning">
              <p className="flex items-center gap-1.5 font-medium">
                <Info aria-hidden className="size-4" />
                Giá trống chưa thể dùng để thu tiền
              </p>
              <p className="mt-1">
                Dòng vẫn được lưu để hoàn thiện danh mục, nhưng màn thu ngân phải tiếp tục khóa tổng tiền.
              </p>
            </div>

            <button
              type="button"
              onClick={add}
              disabled={busy || !code.trim() || !name.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
            >
              <Plus aria-hidden className="size-4" />
              {busy ? "Đang lưu…" : "Thêm dòng bảng giá"}
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  tone = "neutral",
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  tone?: "neutral" | "success" | "warning";
}) {
  const iconTone =
    tone === "success"
      ? "bg-success-bg text-success"
      : tone === "warning"
        ? "bg-warning-bg text-warning"
        : "bg-brand-50 text-brand-600";
  return (
    <div className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 sm:[&:nth-child(odd)]:border-r xl:border-b-0 xl:border-r xl:last:border-r-0">
      <span aria-hidden className={`flex size-10 shrink-0 items-center justify-center rounded-full ${iconTone}`}>
        {icon}
      </span>
      <span>
        <span className="block text-xs text-ink-muted">{label}</span>
        <span className="block text-xl font-semibold text-ink tabular-nums">{value}</span>
      </span>
    </div>
  );
}

function Field({
  label,
  required = false,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-ink-soft">
        {label}
        {required ? <span className="text-danger"> *</span> : null}
      </span>
      {children}
    </label>
  );
}
