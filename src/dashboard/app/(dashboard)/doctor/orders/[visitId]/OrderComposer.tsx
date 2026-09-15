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
import { useCallback, useEffect, useState, useTransition } from "react";

import StatusChip from "@/components/ui/StatusChip";
import { SU_KIEN_BANG } from "@/lib/nhip-lam-moi";
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

/** Chỉ định thư ký nhập, chờ bác sĩ duyệt (GET …/service-orders/draft). */
interface DraftService {
  service_code: string;
  name: string | null;
  unit_price: number | null;
  node_code: string | null;
}
interface ServiceOrderDraft {
  id: string;
  version: number;
  updated_at: string;
  recorded_by: string;
  recorded_by_name: string | null;
  services: DraftService[];
}
interface DraftState {
  draft: ServiceOrderDraft | null;
  /** Vai người đang xem, do backend nói: bác sĩ duyệt/bỏ, thư ký nhập nháp. */
  vai: "BAC_SI" | "THU_KY";
}

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
  const [draftState, setDraftState] = useState<DraftState | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const laThuKy = draftState?.vai === "THU_KY";
  // Dịch vụ ĐÃ TÍCH cho lượt (Tuyền chốt 15/09/2026: chỉ định là danh sách bác
  // sĩ tích — tích gì làm nấy, bỏ tích là bỏ dịch vụ).
  const [daTich, setDaTich] = useState<
    {
      service_code: string;
      name: string | null;
      node_code: string;
      status: string;
      lan?: number;
    }[]
  >([]);
  const [dangBo, setDangBo] = useState<string | null>(null);
  const draft = draftState?.draft ?? null;

  // BẢN NHÁP ĐỌC LẠI THEO THỜI GIAN THỰC. Thư ký nhập ở màn của mình, bác sĩ
  // thấy ngay ở màn này: dùng chung kênh SSE của phòng khám (RealtimeRefresher
  // phát SU_KIEN_BANG kèm tên bảng), không mở kết nối riêng cho từng màn.
  const [draftEpoch, setDraftEpoch] = useState(0);
  const loadDraft = useCallback(() => setDraftEpoch((n) => n + 1), []);

  useEffect(() => {
    let on = true;
    fetch(`/api/visits/${visitId}/service-orders/draft`, { cache: "no-store" })
      .then((res) => (res.ok ? (res.json() as Promise<DraftState>) : null))
      .then((state) => {
        if (on && state) setDraftState(state);
      })
      .catch(() => {
        // Mất kết nối thì giữ bản đang hiện; lần phát tin kế tiếp sẽ đọc lại.
      });
    return () => {
      on = false;
    };
    fetch(`/api/visits/${visitId}/service-orders/current`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((body: { items?: typeof daTich } | null) => {
        if (on && body?.items) setDaTich(body.items);
      })
      .catch(() => {});
  }, [visitId, draftEpoch]);

  async function boTich(code: string, ten: string) {
    // Huỷ chỉ định bắt buộc lý do (Tuyền chốt 15/09/2026).
    const lyDo = window.prompt(`Lý do bỏ "${ten}" khỏi chỉ định của khách?`)?.trim();
    if (!lyDo) return;
    setError(null);
    setDangBo(code);
    const res = await fetch(`/api/visits/${visitId}/service-orders/remove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service_code: code, ly_do: lyDo }),
    });
    setDangBo(null);
    if (!res.ok) {
      setError(await readError(res, "Không bỏ được dịch vụ."));
      return;
    }
    loadDraft();
    router.refresh();
  }

  useEffect(() => {
    const changed = (ev: Event) => {
      const table = (ev as CustomEvent<string>).detail;
      if (table === "service_order_draft" || table === "work_item") loadDraft();
    };
    window.addEventListener(SU_KIEN_BANG, changed);
    window.addEventListener("focus", loadDraft);
    return () => {
      window.removeEventListener(SU_KIEN_BANG, changed);
      window.removeEventListener("focus", loadDraft);
    };
  }, [loadDraft]);

  async function readError(res: Response, fallback: string): Promise<string> {
    const body = (await res.json().catch(() => null)) as { error?: string } | null;
    return body?.error ?? fallback;
  }

  async function approveDraft() {
    if (!draft) return;
    setError(null);
    setDone(null);
    setDraftBusy(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/service-orders/draft/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Phiên bản ĐANG HIỆN trên màn: thư ký sửa sau đó thì backend từ chối.
        body: JSON.stringify({ expected_version: draft.version }),
      });
      if (!res.ok) {
        setError(await readError(res, `Không duyệt được chỉ định (HTTP ${res.status})`));
        return;
      }
      const rooms = (await res.json()) as { node_code: string; service_count: number }[];
      setDone(
        `Đã duyệt ${draft.services.length} dịch vụ thư ký nhập, gửi tới ${rooms.length} phòng.`,
      );
      startTransition(() => router.refresh());
    } finally {
      setDraftBusy(false);
      loadDraft();
    }
  }

  async function discardDraft() {
    if (!draft) return;
    const reason = laThuKy
      ? null
      : window.prompt("Lý do bỏ chỉ định nháp (thư ký sẽ thấy):")?.trim();
    if (!laThuKy && !reason) return;
    setError(null);
    setDone(null);
    setDraftBusy(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/service-orders/draft/discard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_version: draft.version, reason }),
      });
      if (!res.ok) {
        setError(await readError(res, `Không bỏ được chỉ định nháp (HTTP ${res.status})`));
        return;
      }
      setDone("Đã bỏ chỉ định nháp.");
    } finally {
      setDraftBusy(false);
      loadDraft();
    }
  }

  async function removeFromDraft(code: string) {
    if (!draft) return;
    setError(null);
    setDraftBusy(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/service-orders/draft`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_codes: draft.services
            .map((service) => service.service_code)
            .filter((serviceCode) => serviceCode !== code),
          expected_version: draft.version,
        }),
      });
      if (!res.ok) {
        setError(await readError(res, `Không sửa được chỉ định nháp (HTTP ${res.status})`));
      }
    } finally {
      setDraftBusy(false);
      loadDraft();
    }
  }

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
    if (laThuKy) {
      // Thư ký nhập theo lời bác sĩ đọc: vào bản nháp, bác sĩ duyệt mới gửi phòng.
      const res = await fetch(`/api/visits/${visitId}/service-orders/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_codes: [...chosen] }),
      });
      if (!res.ok) {
        setError(await readError(res, `Không lưu được chỉ định nháp (HTTP ${res.status})`));
        return;
      }
      const saved = (await res.json()) as ServiceOrderDraft | null;
      setDraftState({ draft: saved, vai: "THU_KY" });
      setDone(`Đã nhập ${chosen.size} dịch vụ vào nháp — chờ bác sĩ duyệt.`);
      setChosen(new Set());
      setDupes([]);
      return;
    }
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
              <h2 className="text-sm font-semibold text-ink">Đã chỉ định</h2>
              <span className="ml-auto text-xs text-ink-muted">{daTich.length} dịch vụ</span>
            </header>
            <ul className="divide-y divide-line p-2">
              {daTich.length === 0 && (
                <li className="px-2 py-2 text-xs text-ink-muted">
                  Chưa tích dịch vụ nào cho lượt này.
                </li>
              )}
              {daTich.map((d) => {
                const ten = d.name ?? d.service_code;
                const boDuoc = !laThuKy && d.status === "PENDING";
                return (
                  <li key={`${d.node_code}-${d.lan ?? 1}-${d.service_code}`} className="flex items-center gap-2 px-2 py-1.5">
                    <input
                      type="checkbox"
                      checked
                      disabled={!boDuoc || dangBo === d.service_code}
                      onChange={() => void boTich(d.service_code, ten)}
                      aria-label={`Bỏ tích ${ten}`}
                    />
                    <span className="min-w-0 flex-1 truncate text-sm text-ink">
                      {ten}
                      {(d.lan ?? 1) > 1 ? ` (lần ${d.lan})` : ""}
                    </span>
                    {d.status !== "PENDING" && (
                      <span className="text-label text-ink-muted">
                        {d.status === "COMPLETED" ? "đã làm" : "đang làm"}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
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

          {draft ? (
            <section className="rounded-card border border-warning bg-warning-bg shadow-card">
              <header className="flex items-center justify-between gap-2 border-b border-warning/40 px-4 py-3">
                <h2 className="text-sm font-semibold text-warning">
                  Chỉ định chờ bác sĩ duyệt
                </h2>
                <span className="rounded-chip bg-surface px-2 py-1 text-xs font-semibold text-warning tabular-nums">
                  {draft.services.length}
                </span>
              </header>
              <div className="p-4">
                <p className="text-xs text-warning">
                  {draft.recorded_by_name ?? "Thư ký"} nhập · bản {draft.version} ·{" "}
                  {new Date(draft.updated_at).toLocaleTimeString("vi-VN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
                <ul className="mt-2 space-y-2 text-xs">
                  {draft.services.map((service) => (
                    <li key={service.service_code} className="flex items-center gap-2">
                      <span className="min-w-0 flex-1 text-ink">
                        {service.name ?? service.service_code}
                      </span>
                      <span className="shrink-0 text-ink-muted tabular-nums">
                        {money(service.unit_price)}
                      </span>
                      {laThuKy ? (
                        <button
                          type="button"
                          disabled={draftBusy}
                          onClick={() => void removeFromDraft(service.service_code)}
                          className="shrink-0 rounded-control px-1.5 text-ink-muted hover:text-danger disabled:opacity-50"
                          aria-label={`Bỏ ${service.name ?? service.service_code} khỏi nháp`}
                        >
                          ×
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs leading-5 text-warning">
                  Chưa gửi tới phòng thực hiện, trưởng ca hay thu ngân cho tới khi
                  bác sĩ duyệt.
                </p>
                {laThuKy ? (
                  <button
                    type="button"
                    disabled={draftBusy}
                    onClick={() => void discardDraft()}
                    className="mt-3 w-full rounded-control border border-line bg-surface px-3 py-2 text-sm font-medium text-ink-soft hover:bg-surface-muted disabled:opacity-50"
                  >
                    Bỏ cả bản nháp
                  </button>
                ) : (
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      disabled={draftBusy || pending}
                      onClick={() => void approveDraft()}
                      className="flex-1 rounded-control bg-brand-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
                    >
                      {draftBusy ? "Đang duyệt…" : "Duyệt & gửi phòng"}
                    </button>
                    <button
                      type="button"
                      disabled={draftBusy || pending}
                      onClick={() => void discardDraft()}
                      className="rounded-control border border-line bg-surface px-3 py-2.5 text-sm font-medium text-ink-soft hover:bg-surface-muted disabled:opacity-50"
                    >
                      Bỏ nháp
                    </button>
                  </div>
                )}
              </div>
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
                {pending ? "Đang gửi…" : laThuKy ? "Nhập nháp — chờ bác sĩ duyệt" : "Gửi chỉ định"}
              </button>
              <p className="mt-3 text-center text-xs leading-5 text-ink-faint">
                {laThuKy
                  ? "Bác sĩ thấy ngay trên màn của mình và duyệt mới gửi phòng."
                  : "Gửi chỉ định không tự đóng bước tại Bàn khám."}
              </p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
