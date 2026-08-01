"use client";

import { CheckCircle2, ChevronRight, Search, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import StatusChip from "@/components/ui/StatusChip";
import { fmtDate, fmtDateTimeOrDate } from "@/lib/datetime";

export interface EpisodeRow {
  id: string;
  opened_at: string;
  last_visit_at: string | null;
  patient_name: string;
  patient_code: string | null;
  service_name: string;
}

function initials(name: string): string {
  return (
    name
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(-2)
      .map((part) => part[0]?.toLocaleUpperCase("vi-VN") ?? "")
      .join("") || "KH"
  );
}

export default function EpisodesBoard({ rows }: { rows: EpisodeRow[] }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    if (!needle) return rows;
    return rows.filter((row) =>
      [row.patient_name, row.patient_code, row.service_name]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("vi-VN")
        .includes(needle),
    );
  }, [query, rows]);
  const selected = filtered.find((row) => row.id === selectedId) ?? filtered[0] ?? null;

  async function act(id: string, action: "close" | "reopen") {
    if (busyId) return;
    setBusyId(id);
    setError(null);
    const response = await fetch("/api/episodes", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
    });
    const body = await response.json().catch(() => ({}));
    setBusyId(null);
    if (!response.ok) {
      setError(body.error ?? "Có lỗi xảy ra.");
      return;
    }
    router.refresh();
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface px-4 py-10 text-center">
        <CheckCircle2 className="mx-auto size-7 text-status-completed" aria-hidden="true" />
        <p className="mt-3 text-sm font-medium text-ink">Không có đợt khám chờ xác nhận</p>
        <p className="mt-1 text-xs text-ink-muted">
          Các đợt có trạng thái chờ đóng sẽ xuất hiện tại đây.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {error ? (
        <div className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">{error}</div>
      ) : null}
      <div className="grid items-start gap-3 xl:grid-cols-[minmax(240px,0.82fr)_minmax(360px,1.25fr)_minmax(250px,0.86fr)]">
        <section
          aria-label="Danh sách đợt chờ xác nhận"
          className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <header className="border-b border-line p-3">
            <h2 className="text-sm font-semibold text-ink">Danh sách đợt chờ xác nhận</h2>
            <p className="mt-0.5 text-xs text-ink-muted">{filtered.length} đợt khám</p>
            <label className="mt-3 flex min-h-10 items-center gap-2 rounded-control border border-line px-3 text-ink-muted focus-within:border-brand-500">
              <Search className="size-4" aria-hidden="true" />
              <span className="sr-only">Tìm bệnh nhân hoặc mã hồ sơ</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm bệnh nhân hoặc mã hồ sơ"
                className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
              />
            </label>
          </header>
          <div className="max-h-[580px] overflow-y-auto">
            {filtered.length > 0 ? (
              filtered.map((row) => {
                const active = selected?.id === row.id;
                return (
                  <button
                    key={row.id}
                    type="button"
                    onClick={() => setSelectedId(row.id)}
                    aria-current={active ? "true" : undefined}
                    className={`flex w-full items-start gap-2.5 border-b border-line px-3 py-3 text-left transition-colors last:border-b-0 ${
                      active
                        ? "border-l-2 border-l-brand-500 bg-surface-selected"
                        : "border-l-2 border-l-transparent hover:bg-surface-sunken"
                    }`}
                  >
                    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface-sunken text-xs font-semibold text-ink-soft">
                      {initials(row.patient_name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-ink">{row.patient_name}</span>
                      <span className="mt-0.5 block truncate font-mono text-xs text-ink-muted">
                        {row.patient_code ?? "Chưa có mã hồ sơ"}
                      </span>
                      <span className="mt-1 block truncate text-xs text-ink-soft">
                        {row.service_name}
                      </span>
                    </span>
                    <ChevronRight className="mt-1 size-4 shrink-0 text-ink-faint" aria-hidden="true" />
                  </button>
                );
              })
            ) : (
              <p className="px-4 py-12 text-center text-sm text-ink-muted">
                Không có đợt khám khớp từ khoá.
              </p>
            )}
          </div>
        </section>

        <section
          aria-label="Chi tiết đợt khám"
          className="rounded-card border border-line bg-surface p-4 shadow-card"
        >
          {selected ? (
            <>
              <div className="flex items-start gap-3 border-b border-line pb-4">
                <span className="grid size-12 shrink-0 place-items-center rounded-full bg-surface-sunken text-sm font-semibold text-ink-soft">
                  {initials(selected.patient_name)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-brand-700">Đợt khám chờ xác nhận</p>
                  <h2 className="mt-1 truncate text-lg font-semibold text-ink">{selected.patient_name}</h2>
                  <p className="mt-1 font-mono text-xs text-ink-muted">
                    {selected.patient_code ?? "Chưa có mã hồ sơ"}
                  </p>
                </div>
                <StatusChip tone="ready" label="Chờ xác nhận" />
              </div>
              <div className="space-y-4 py-4">
                <div className="rounded-control border border-line bg-surface-muted p-3">
                  <p className="text-xs text-ink-muted">Dịch vụ theo dõi</p>
                  <p className="mt-1 text-sm font-semibold text-ink">{selected.service_name}</p>
                </div>
                <dl className="grid gap-3 rounded-control border border-line p-3 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-xs text-ink-muted">Ngày mở đợt</dt>
                    <dd className="mt-1 font-medium text-ink">{fmtDate(selected.opened_at)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-muted">Lượt khám gần nhất</dt>
                    <dd className="mt-1 font-medium text-ink">
                      {selected.last_visit_at ? fmtDateTimeOrDate(selected.last_visit_at) : "Chưa có dữ liệu"}
                    </dd>
                  </div>
                </dl>
                <div className="rounded-control border border-dashed border-line-strong bg-surface-muted p-3 text-sm text-ink-muted">
                  Chỉ dữ liệu cần cho quyết định đóng đợt được hiển thị ở đây.
                </div>
              </div>
            </>
          ) : (
            <div className="grid min-h-72 place-items-center text-center">
              <div>
                <UserRound className="mx-auto size-7 text-ink-faint" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-ink">Chưa chọn đợt khám</p>
                <p className="mt-1 text-xs text-ink-muted">Chọn một dòng để xem chi tiết.</p>
              </div>
            </div>
          )}
        </section>

        <aside
          aria-label="Quyết định CSKH"
          className="rounded-card border border-line bg-surface p-4 shadow-card"
        >
          <h2 className="text-sm font-semibold text-ink">Quyết định CSKH</h2>
          {selected ? (
            <div className="mt-4 space-y-4">
              <div className="rounded-control border border-line bg-surface-muted p-3">
                <p className="text-sm font-medium text-ink">Xác nhận tình trạng theo dõi</p>
                <p className="mt-1 text-xs text-ink-muted">
                  Chỉ đóng khi đợt khám đã kết thúc; chọn còn theo dõi để giữ đợt mở.
                </p>
              </div>
              <button
                type="button"
                onClick={() => act(selected.id, "close")}
                disabled={busyId === selected.id}
                className="flex min-h-10 w-full items-center justify-center rounded-control bg-brand-600 px-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {busyId === selected.id ? "Đang xử lý…" : "Xác nhận đóng"}
              </button>
              <button
                type="button"
                onClick={() => act(selected.id, "reopen")}
                disabled={busyId === selected.id}
                className="flex min-h-10 w-full items-center justify-center rounded-control border border-line bg-surface px-3 text-sm font-semibold text-ink-soft hover:bg-surface-sunken disabled:opacity-50"
              >
                Còn theo dõi
              </button>
              <p className="text-xs text-ink-muted">
                Quyết định sẽ cập nhật trạng thái đợt khám và đưa dòng này ra khỏi danh sách chờ xác nhận.
              </p>
            </div>
          ) : (
            <p className="mt-3 text-sm text-ink-muted">Chọn một đợt khám để đưa ra quyết định.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
