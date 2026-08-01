"use client";

/**
 * Order composer — clinical services come from the backend catalogue and are
 * grouped by their real performing room. Reference-design panels whose data is
 * not in this boundary remain visible as explicit empty states.
 */

import {
  AlertTriangle,
  Building2,
  Check,
  ClipboardList,
  Layers3,
  Search,
  Send,
  UserRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import StatusChip from "@/components/ui/StatusChip";
import { patientLine, type WorklistPatient } from "@/lib/worklist";

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

type Availability = "all" | "orderable" | "unavailable";

function money(value: number | null): string {
  return value == null ? "Chưa có giá" : `${value.toLocaleString("vi-VN")} đ`;
}

export default function OrderComposer({
  visitId,
  patient,
  catalogue,
}: {
  visitId: string;
  patient: WorklistPatient | null;
  catalogue: CatalogueEntry[];
}) {
  const router = useRouter();
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [selectedRoom, setSelectedRoom] = useState("all");
  const [availability, setAvailability] = useState<Availability>("all");
  const [dupes, setDupes] = useState<Duplicate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const allRooms = new Map<string, CatalogueEntry[]>();
  for (const service of catalogue) {
    const room = service.node_name ?? "Chưa cấu hình phòng thực hiện";
    allRooms.set(room, [...(allRooms.get(room) ?? []), service]);
  }

  const normalizedQuery = query.trim().toLocaleLowerCase("vi-VN");
  const filteredCatalogue = catalogue.filter((service) => {
    const room = service.node_name ?? "Chưa cấu hình phòng thực hiện";
    const matchesQuery =
      normalizedQuery.length === 0 ||
      `${service.name} ${service.service_code}`
        .toLocaleLowerCase("vi-VN")
        .includes(normalizedQuery);
    const matchesRoom = selectedRoom === "all" || room === selectedRoom;
    const matchesAvailability =
      availability === "all" ||
      (availability === "orderable" ? service.orderable : !service.orderable);
    return matchesQuery && matchesRoom && matchesAvailability;
  });

  const rooms = new Map<string, CatalogueEntry[]>();
  for (const service of filteredCatalogue) {
    const room = service.node_name ?? "Chưa cấu hình phòng thực hiện";
    rooms.set(room, [...(rooms.get(room) ?? []), service]);
  }

  const selected = catalogue.filter((service) =>
    chosen.has(service.service_code),
  );
  const subtotal = selected.reduce(
    (sum, service) => sum + (service.unit_price ?? 0),
    0,
  );
  const anyPriceMissing = selected.some((service) => service.unit_price == null);

  async function toggle(code: string) {
    const next = chosen.has(code)
      ? new Set([...chosen].filter((chosenCode) => chosenCode !== code))
      : new Set([...chosen, code]);
    setChosen(next);
    setDone(null);

    const codes = [...next];
    if (codes.length === 0) {
      setDupes([]);
      return;
    }
    const res = await fetch(
      `/api/visits/${visitId}/service-orders/duplicates`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_codes: codes }),
      },
    );
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
      const body = (await res.json().catch(() => null)) as {
        error?: string;
      } | null;
      setError(body?.error ?? `Không gửi được chỉ định (HTTP ${res.status})`);
      return;
    }
    const destinationRooms = (await res.json()) as {
      node_code: string;
      service_count: number;
    }[];
    setDone(
      `Đã gửi ${chosen.size} dịch vụ tới ${destinationRooms.length} phòng: ` +
        destinationRooms
          .map((room) => `${room.node_code} (${room.service_count})`)
          .join(", "),
    );
    setChosen(new Set());
    setDupes([]);
    startTransition(() => router.refresh());
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Ai đang được chỉ định. Không có tên thì phải kêu lên, không im lặng
          chuyển sang màu xám: chỉ định siêu âm cho một lượt khám vô danh là
          nhầm người, chứ không phải một ô trống trên giao diện. */}
      <section
        className={`flex flex-wrap items-center gap-4 rounded-card border px-4 py-3 shadow-card ${
          patient?.full_name
            ? "border-line bg-surface"
            : "border-danger bg-danger-bg"
        }`}
      >
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-sm font-semibold text-ink-soft">
          <UserRound className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p
            className={`truncate font-semibold ${
              patient?.full_name ? "text-ink" : "text-danger"
            }`}
          >
            {patient?.full_name ?? "Không đọc được người bệnh của lượt khám này"}
          </p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {patient
              ? [patientLine(patient), patient.patient_code]
                  .filter(Boolean)
                  .join(" · ")
              : "Kiểm tra lại lượt khám trước khi chỉ định."}
          </p>
        </div>
        <div className="border-l border-line pl-4 text-right">
          <p className="text-xs text-ink-faint">Bước hiện tại</p>
          <p className="text-sm font-medium text-brand-700">Tạo chỉ định dịch vụ</p>
        </div>
      </section>

      <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[minmax(180px,0.65fr)_minmax(0,1.7fr)_minmax(250px,0.85fr)]">
        <aside
          aria-label="Bối cảnh lượt khám"
          className="flex flex-col gap-3 xl:sticky xl:top-4"
        >
          <section className="rounded-card border border-line bg-surface shadow-card">
            <header className="flex items-center gap-2 border-b border-line px-4 py-3">
              <UserRound className="h-4 w-4 text-brand-600" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Thông tin lượt khám</h2>
            </header>
            <div className="space-y-3 p-4">
              <div>
                <p className="text-xs text-ink-faint">Người bệnh</p>
                <p className="mt-0.5 text-sm font-medium text-ink">
                  {patient?.full_name ?? "Không đọc được"}
                </p>
                {patient ? (
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {patientLine(patient)}
                  </p>
                ) : null}
              </div>
              <div>
                <p className="text-xs text-ink-faint">Mã bệnh nhân</p>
                <p className="mt-0.5 text-sm text-ink-soft">
                  {patient?.patient_code ?? "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-ink-faint">Mã lượt khám</p>
                <p className="mt-0.5 break-all text-sm text-ink-soft tabular-nums">
                  {visitId}
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-card border border-line bg-surface p-4 shadow-card">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-brand-600" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Kết quả khám phụ khoa</h2>
            </div>
            <p className="mt-3 rounded-control border border-dashed border-line bg-surface-muted px-3 py-5 text-center text-xs leading-5 text-ink-faint">
              Chưa có dữ liệu từ hồ sơ khám
            </p>
          </section>

          <section className="rounded-card border border-line bg-surface p-4 shadow-card">
            <div className="flex items-center gap-2">
              <Layers3 className="h-4 w-4 text-brand-600" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Bộ chỉ định</h2>
            </div>
            <p className="mt-3 rounded-control border border-dashed border-line bg-surface-muted px-3 py-5 text-center text-xs leading-5 text-ink-faint">
              Chưa cấu hình bộ chỉ định
            </p>
          </section>
        </aside>

        <section
          aria-label="Danh mục chỉ định"
          className="min-w-0 rounded-card border border-line bg-surface shadow-card"
        >
          <header className="border-b border-line px-4 py-3">
            <h2 className="font-semibold text-ink">Chỉ định dịch vụ</h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              Chọn dịch vụ từ danh mục đã được backend cấu hình.
            </p>
          </header>

          <div className="space-y-3 border-b border-line p-4">
            <label className="relative block">
              <span className="sr-only">Tìm kiếm dịch vụ</span>
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint"
                aria-hidden="true"
              />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm kiếm dịch vụ theo tên hoặc mã…"
                className="w-full rounded-control border border-line bg-surface py-2.5 pl-9 pr-4 text-sm text-ink placeholder:text-ink-faint focus:border-brand-500 focus:outline-none"
              />
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="sr-only" htmlFor="room-filter">
                Tất cả phòng thực hiện
              </label>
              <select
                id="room-filter"
                value={selectedRoom}
                onChange={(event) => setSelectedRoom(event.target.value)}
                className="rounded-control border border-line bg-surface px-3 py-2.5 text-sm text-ink-soft focus:border-brand-500 focus:outline-none"
              >
                <option value="all">Tất cả phòng thực hiện</option>
                {[...allRooms.keys()].map((room) => (
                  <option key={room} value={room}>
                    {room}
                  </option>
                ))}
              </select>
              <label className="sr-only" htmlFor="availability-filter">
                Tất cả trạng thái
              </label>
              <select
                id="availability-filter"
                value={availability}
                onChange={(event) =>
                  setAvailability(event.target.value as Availability)
                }
                className="rounded-control border border-line bg-surface px-3 py-2.5 text-sm text-ink-soft focus:border-brand-500 focus:outline-none"
              >
                <option value="all">Tất cả trạng thái</option>
                <option value="orderable">Có thể chỉ định</option>
                <option value="unavailable">Chưa gắn phòng</option>
              </select>
            </div>
          </div>

          <div className="border-b border-line p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Phòng thực hiện</h3>
              <span className="text-xs text-ink-faint">{catalogue.length} dịch vụ</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {[...allRooms.entries()].map(([room, services]) => {
                const active = selectedRoom === room;
                return (
                  <button
                    key={room}
                    type="button"
                    onClick={() => setSelectedRoom(active ? "all" : room)}
                    aria-pressed={active}
                    className={`min-w-0 rounded-control border p-3 text-left transition-colors ${
                      active
                        ? "border-brand-300 bg-brand-50"
                        : "border-line bg-surface hover:bg-surface-muted"
                    }`}
                  >
                    <Building2
                      className="mb-3 h-4 w-4 text-brand-600"
                      aria-hidden="true"
                    />
                    <span className="block truncate text-xs font-medium text-ink">
                      {room}
                    </span>
                    <span className="mt-1 block text-xs text-ink-faint">
                      {services.length} dịch vụ
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="border-b border-line px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-ink">Dịch vụ thường dùng</h3>
                <p className="mt-0.5 text-xs text-ink-faint">
                  Chưa có dữ liệu tần suất sử dụng; đang hiển thị toàn bộ danh mục.
                </p>
              </div>
              <span className="rounded-chip bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700">
                {filteredCatalogue.length} kết quả
              </span>
            </div>
          </div>

          {rooms.size === 0 ? (
            <p className="px-4 py-12 text-center text-sm text-ink-faint">
              Không tìm thấy dịch vụ phù hợp với bộ lọc.
            </p>
          ) : (
            <div className="divide-y divide-line">
              {[...rooms.entries()].map(([room, services]) => (
                <section key={room}>
                  <header className="flex items-center justify-between bg-surface-muted px-4 py-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      {room}
                    </h4>
                    <span className="text-xs text-ink-faint">{services.length}</span>
                  </header>
                  <ul className="divide-y divide-line">
                    {services.map((service) => {
                      const isChosen = chosen.has(service.service_code);
                      return (
                        <li key={service.service_code}>
                          <label
                            className={`flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                              service.orderable
                                ? "cursor-pointer hover:bg-brand-50"
                                : "cursor-not-allowed bg-surface-muted"
                            }`}
                          >
                            <input
                              type="checkbox"
                              className="peer sr-only"
                              disabled={!service.orderable}
                              checked={isChosen}
                              onChange={() => toggle(service.service_code)}
                            />
                            <span
                              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border peer-focus-visible:ring-2 peer-focus-visible:ring-brand-300 peer-focus-visible:ring-offset-2 ${
                                isChosen
                                  ? "border-brand-600 bg-brand-600 text-white"
                                  : "border-line-strong bg-surface text-transparent"
                              }`}
                            >
                              <Check className="h-3.5 w-3.5" aria-hidden="true" />
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate font-medium text-ink">
                                {service.name}
                              </span>
                              <span className="mt-0.5 block text-xs text-ink-faint tabular-nums">
                                {service.service_code}
                              </span>
                            </span>
                            {!service.orderable ? (
                              <StatusChip tone="blocked" label="Chưa gắn phòng" />
                            ) : (
                              <span
                                className={`shrink-0 text-right text-sm tabular-nums ${
                                  service.unit_price == null
                                    ? "text-warning"
                                    : "text-ink-soft"
                                }`}
                              >
                                {money(service.unit_price)}
                              </span>
                            )}
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </section>

        <aside
          aria-label="Trạng thái và tóm tắt chỉ định"
          className="flex flex-col gap-3 xl:sticky xl:top-4"
        >
          <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
            <header className="flex items-center gap-2 border-b border-line bg-surface-muted px-4 py-3">
              <AlertTriangle className="h-4 w-4 text-ink-muted" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Trạng thái gửi</h2>
            </header>
            <div className="p-4">
              <p className="text-sm font-medium text-ink-soft">
                Chưa đủ dữ liệu để xác định trạng thái chặn
              </p>
              <p className="mt-2 text-xs leading-5 text-ink-muted">
                Màn này chưa nhận dữ liệu xác nhận chi phí hoặc điều kiện chặn từ
                backend. Kiểm tra trùng vẫn chạy khi chọn dịch vụ.
              </p>
            </div>
          </section>

          {dupes.length > 0 ? (
            <section className="rounded-card border border-warning bg-warning-bg p-4 shadow-card">
              <div className="flex items-center gap-2 text-warning">
                <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                <h2 className="text-sm font-semibold">Cảnh báo trùng lặp</h2>
              </div>
              <p className="mt-2 text-xs font-medium text-warning">
                Đã chỉ định trùng trong 30 ngày
              </p>
              <ul className="mt-2 space-y-1 text-xs text-warning">
                {dupes.map((duplicate) => (
                  <li key={`${duplicate.service_code}-${duplicate.ordered_at}`}>
                    • {duplicate.name ?? duplicate.service_code} —{" "}
                    {new Date(duplicate.ordered_at).toLocaleDateString("vi-VN")}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="rounded-card border border-line bg-surface shadow-card">
            <header className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold text-ink">Tóm tắt chỉ định</h2>
              <span className="rounded-chip bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-700 tabular-nums">
                {selected.length}
              </span>
            </header>
            <div className="p-4">
              <p className="text-xs text-ink-faint">Dịch vụ đã chọn</p>
              {selected.length === 0 ? (
                <p className="py-6 text-center text-sm text-ink-faint">
                  Chưa chọn dịch vụ nào.
                </p>
              ) : (
                <ul className="mt-2 max-h-52 space-y-2 overflow-y-auto border-b border-line pb-3 text-xs">
                  {selected.map((service) => (
                    <li key={service.service_code} className="flex gap-2">
                      <span className="min-w-0 flex-1 text-ink-soft">{service.name}</span>
                      <span className="shrink-0 text-ink-muted tabular-nums">
                        {money(service.unit_price)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-muted">Tổng dịch vụ</dt>
                  <dd className="font-medium text-ink tabular-nums">{selected.length}</dd>
                </div>
                <div className="flex justify-between gap-3 border-t border-line pt-3">
                  <dt className="font-medium text-ink">Tạm tính</dt>
                  <dd className="font-semibold text-brand-700 tabular-nums">
                    {selected.length === 0
                      ? "—"
                      : anyPriceMissing
                        ? "Chưa đủ dữ liệu"
                        : money(subtotal)}
                  </dd>
                </div>
              </dl>

              {anyPriceMissing ? (
                <p className="mt-3 rounded-control bg-warning-bg px-3 py-2 text-xs leading-5 text-warning">
                  Một số dịch vụ chưa có giá trong bảng giá — tạm tính chưa đầy đủ.
                </p>
              ) : null}
              {error ? (
                <p className="mt-3 rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
                  {error}
                </p>
              ) : null}
              {done ? (
                <p className="mt-3 rounded-control bg-success-bg px-3 py-2 text-sm text-success">
                  {done}
                </p>
              ) : null}

              <button
                type="button"
                disabled={selected.length === 0 || pending}
                onClick={submit}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-4 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
                {pending ? "Đang gửi…" : "Gửi chỉ định"}
              </button>
              <p className="mt-3 text-center text-xs leading-5 text-ink-faint">
                Gửi chỉ định không tự đóng bước tại Bàn khám.
              </p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
