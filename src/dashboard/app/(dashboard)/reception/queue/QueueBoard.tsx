"use client";

import {
  ArrowDownAZ,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Filter,
  History,
  IdCard,
  MapPin,
  Monitor,
  Phone,
  Search,
  ShieldCheck,
  UserRoundX,
  UsersRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

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
  examMinutes,
  NHAN_LY_DO_GOI,
  type WorklistItem,
} from "@/lib/worklist";

type QueueTab = "all" | "priority" | "verify";
type ArrivalFilter = "all" | "appointment" | "walk-in";
// "goi" = thứ tự gọi thật của phòng khám (backend tính). Đứng đầu danh sách
// và là MẶC ĐỊNH: đây là thứ tự mà bảng tivi đang hiện cho người ngồi chờ, nên
// quầy phải nhìn cùng một thứ. Hai lựa chọn kia giữ lại vì có lúc cần soi khác
// đi ("ai chờ lâu nhất" khi xử lý phàn nàn, "số thứ tự" khi khách hỏi theo vé).
type SortMode = "goi" | "wait" | "queue";
type KernelCommand = "start" | "complete";


function time(value: string | null): string {
  return value
    ? new Date(value).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
}

function initials(name: string | null): string {
  if (!name) return "BN";
  const words = name.trim().split(/\s+/);
  return words
    .slice(-2)
    .map((word) => word[0]?.toLocaleUpperCase("vi-VN") ?? "")
    .join("");
}

/** HAI bước, và cả hai đều có dữ liệu thật đứng sau.
 *
 * Bản trước có năm bước, ba trong số đó không bao giờ đổi trạng thái vì không
 * có dữ liệu: "Đã gán quầy — chưa có dữ liệu quầy", "Gọi bệnh nhân — chưa có
 * mốc gọi số", "Hoàn tất tiếp nhận". Ba vòng tròn xám vĩnh viễn không kể được
 * điều gì, chỉ dạy người dùng bỏ qua cả thanh trạng thái.
 */
/** HAI NÚT TRÒN LÀ HAI HÀNH ĐỘNG — bấm là làm, bấm lại là hoàn tác.
 *
 *  Tuyền 20/08/2026: *"click nút tròn được cơ chế như của CSKH, click là làm mà
 *  click lại là undo"*. Trước đây thanh này chỉ là chỉ-báo, còn hành động nằm ở
 *  hai nút chữ tận cột phải — người dùng nhìn thấy tiến trình ở một chỗ rồi phải
 *  đi bấm ở chỗ khác.
 *
 *  MỖI NÚT MỞ MỘT ĐỒNG HỒ KHÁC NHAU, và đó là lý do chúng không gộp được:
 *      Check-in      → mốc của BUỔI KHÁM, mở đồng hồ CHỜ
 *      Gọi vào khám  → mở đồng hồ KHÁM, và đóng đồng hồ chờ
 *
 *  `detail` in ĐÚNG GIỜ chứ không in "Đã gọi": người ngồi quầy cần con số để
 *  trả lời "chị đợi thêm mấy phút", một chữ "đã" không giúp được gì. */
function receptionSteps(
  item: WorklistItem,
  tay: {
    checkIn: () => void;
    boCheckIn: () => void;
    goiVao: () => void;
    boGoiVao: () => void;
    dangGui: boolean;
  } | null,
): Step[] {
  const daCheckIn = Boolean(item.checked_in_at);
  const daGoi = Boolean(item.exam_started_at);
  const cho = waitedMinutes(item);
  const kham = examMinutes(item);
  return [
    {
      label: "Check-in",
      state: daCheckIn ? "done" : "current",
      detail: daCheckIn
        ? `${time(item.checked_in_at)}${daGoi ? ` · chờ ${cho}′` : ""}`
        : "Chưa đến",
      onClick: tay
        ? daCheckIn
          ? tay.boCheckIn
          : tay.checkIn
        : undefined,
      actionLabel: daCheckIn
        ? "Hoàn tác check-in — khách chưa đến"
        : "Check-in — khách đã đến",
      busy: tay?.dangGui,
    },
    {
      label: "Gọi vào khám",
      state: daGoi ? "done" : daCheckIn ? "current" : "upcoming",
      detail: daGoi
        ? `${time(item.exam_started_at ?? null)}${kham !== null ? ` · khám ${kham}′` : ""}`
        : daCheckIn
          ? `đang chờ ${cho}′`
          : "Chưa gọi",
      // Chưa check-in thì không bấm được: gọi vào khám một người chưa tới là
      // một mốc giờ khám cho người không có mặt. Backend cũng từ chối, nhưng
      // chặn ở đây để người dùng không phải học điều đó bằng một câu lỗi.
      onClick: tay && daCheckIn ? (daGoi ? tay.boGoiVao : tay.goiVao) : undefined,
      actionLabel: daGoi
        ? "Hoàn tác — khách chưa vào khám"
        : "Gọi vào khám — bắt đầu tính giờ khám",
      busy: tay?.dangGui,
    },
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
      className={`w-full border-b border-line px-3 py-3 text-left transition-colors last:border-b-0 ${
        selected
          ? "rounded-control border border-brand-500 bg-surface-selected shadow-card"
          : "hover:bg-surface-sunken"
      }`}
    >
      <span className="grid grid-cols-[42px_minmax(0,1fr)_44px] items-start gap-2">
        <span className="rounded-control border border-line bg-surface-sunken px-1 py-2 text-center text-sm font-semibold text-ink">
          {item.queue_number ?? "—"}
        </span>
        <span className="min-w-0">
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="truncate text-sm font-semibold text-ink">
              {item.patient.full_name ?? "Chưa rõ tên"}
            </span>
            {item.is_priority_slot ? <PriorityChip priority="P0" /> : null}
          </span>
          <span className="block truncate text-xs text-ink-muted">
            {patientLine(item.patient) || item.patient.patient_code || "Chưa đủ thông tin"}
          </span>
          <span className="mt-2 flex items-center justify-between gap-2 text-label">
            <StatusChip
              tone={STATUS_PRESENTATION[tone].token as StatusTone}
              label={STATUS_PRESENTATION[tone].label}
            />
            {/* LÝ DO XẾP HÀNG, không phải kênh đặt lịch.
                "Đặt hẹn / Đến trực tiếp" chỉ nói khách đặt kiểu gì; còn thứ
                người ngồi quầy cần là VÌ SAO người này đứng ở đây — nhất là khi
                ai đó vượt lên trước người tới sớm hơn. Backend đã tính sẵn lý
                do cùng lúc với thứ tự (`_classify` sinh cả hai trong một hàm,
                cố ý, để câu giải thích không bao giờ lệch với thứ tự thật).
                Chưa có lý do thì lùi về kênh đặt lịch như cũ. */}
            <span className="truncate text-ink-muted">
              {item.call_reason
                ? (NHAN_LY_DO_GOI[item.call_reason] ?? item.call_reason)
                : item.booking_channel === "WALK_IN"
                  ? "Đến trực tiếp"
                  : "Đặt hẹn"}
              {item.promoted_over ? ` · vượt ${item.promoted_over}` : ""}
            </span>
          </span>
        </span>
        <span
          className={`pt-1 text-right text-xs font-semibold tabular-nums ${
            late !== null && late > 0 ? "text-status-overdue" : "text-warning"
          }`}
        >
          {late !== null && late > 0 ? `${late}′ quá` : `${waited}′`}
        </span>
      </span>
    </button>
  );
}

export default function QueueBoard({ items }: { items: WorklistItem[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(items[0]?.id ?? null);
  const [tab, setTab] = useState<QueueTab>("all");
  const [query, setQuery] = useState("");
  const [arrival, setArrival] = useState<ArrivalFilter>("all");
  const [sort, setSort] = useState<SortMode>("goi");

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    const matching = items.filter((item) => {
      const matchesTab =
        tab === "all" ||
        (tab === "priority" && item.is_priority_slot) ||
        (tab === "verify" && item.node_code === "LUOTKHAM-02");
      const matchesArrival =
        arrival === "all" ||
        (arrival === "walk-in" && item.booking_channel === "WALK_IN") ||
        (arrival === "appointment" && item.booking_channel !== "WALK_IN");
      const haystack = [
        item.patient.full_name,
        item.patient.patient_code,
        item.queue_number,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("vi-VN");
      return matchesTab && matchesArrival && (!needle || haystack.includes(needle));
    });
    return [...matching].sort((a, b) => {
      if (sort === "goi") {
        // THỨ TỰ GỌI THẬT, do backend tính. Dòng không xếp được (không gắn
        // lịch hẹn) rơi xuống cuối thay vì trộn lẫn — chúng không có chỗ trong
        // hàng gọi, và đẩy chúng lên đầu bằng một số 0 mặc định là cách tệ
        // nhất để "xử lý" dữ liệu thiếu.
        const ra = a.call_order ?? Number.MAX_SAFE_INTEGER;
        const rb = b.call_order ?? Number.MAX_SAFE_INTEGER;
        if (ra !== rb) return ra - rb;
      }
      if (sort === "wait") return waitedMinutes(b) - waitedMinutes(a);
      return (a.queue_number ?? "").localeCompare(b.queue_number ?? "", "vi-VN", {
        numeric: true,
      });
    });
  }, [arrival, items, query, sort, tab]);

  const selected =
    filtered.find((item) => item.id === selectedId) ??
    filtered[0] ??
    null;

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
    <div className="grid items-start gap-3 xl:grid-cols-[minmax(280px,0.9fr)_minmax(380px,1.25fr)_minmax(240px,0.8fr)]">
      <section
        aria-label="Danh sách hàng đợi"
        className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
      >
        <header className="border-b border-line p-3">
          <h2 className="text-sm font-semibold text-ink">Danh sách hàng đợi</h2>
          <div className="mt-3 flex border-b border-line text-xs">
            {(
              [
                ["all", "Tất cả"],
                // TAB "ƯU TIÊN" ĐÃ ẨN. Nó lọc theo `is_priority_slot`, mà
                // KHÔNG đường ghi nào trong dashboard đặt cờ ấy — đo trên prod
                // 08/08/2026: 0/10 lịch hẹn có cờ. Nên tab luôn rỗng, và một
                // tab luôn rỗng dạy người dùng rằng "không có ca ưu tiên nào",
                // chứ không phải "tính năng chưa có".
                //
                // Ưu tiên là khái niệm CHƯA XÂY (Quang: "bỏ ưu tiên đi đã").
                // Giữ nguyên cột và `PriorityChip` làm chỗ nối cho sau này;
                // chỉ bỏ thứ hứa hẹn với người dùng một việc chưa làm được.
                ["verify", "Cần xác minh"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setTab(value)}
                aria-pressed={tab === value}
                className={`border-b-2 px-3 py-2 font-medium ${
                  tab === value
                    ? "border-brand-600 text-brand-700"
                    : "border-transparent text-ink-muted hover:text-ink"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="mt-3 flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
            <Search size={15} aria-hidden />
            <span className="sr-only">Tìm tên, mã BN hoặc số thứ tự</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm tên, mã BN hoặc số thứ tự"
              className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <label className="flex items-center gap-2 rounded-control border border-line px-2.5 py-2 text-xs text-ink-soft">
              <Filter size={14} aria-hidden />
              <span className="sr-only">Bộ lọc</span>
              <select
                value={arrival}
                onChange={(event) => setArrival(event.target.value as ArrivalFilter)}
                aria-label="Bộ lọc"
                className="min-w-0 flex-1 appearance-none bg-transparent outline-none"
              >
                <option value="all">Bộ lọc</option>
                <option value="appointment">Đặt hẹn</option>
                <option value="walk-in">Đến trực tiếp</option>
              </select>
              <ChevronDown size={13} aria-hidden />
            </label>
            <label className="flex items-center gap-2 rounded-control border border-line px-2.5 py-2 text-xs text-ink-soft">
              <ArrowDownAZ size={14} aria-hidden />
              <span className="sr-only">Sắp xếp</span>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as SortMode)}
                aria-label="Sắp xếp"
                className="min-w-0 flex-1 appearance-none bg-transparent outline-none"
              >
                <option value="goi">Sắp xếp: thứ tự gọi</option>
                <option value="wait">Sắp xếp: chờ lâu</option>
                <option value="queue">Sắp xếp: số thứ tự</option>
              </select>
              <ChevronDown size={13} aria-hidden />
            </label>
          </div>
        </header>

        <div className="grid grid-cols-[42px_minmax(0,1fr)_44px] gap-2 border-b border-line bg-surface-muted px-3 py-2 text-label font-medium uppercase tracking-wide text-ink-faint">
          <span>STT</span>
          <span>Người bệnh</span>
          <span className="text-right">Chờ</span>
        </div>
        <div className="max-h-[610px] overflow-y-auto px-1">
          {filtered.length > 0 ? (
            filtered.map((item) => (
              <Row
                key={item.id}
                item={item}
                selected={item.id === selected?.id}
                onSelect={() => setSelectedId(item.id)}
              />
            ))
          ) : (
            <p className="px-4 py-10 text-center text-sm text-ink-muted">
              Không có người bệnh khớp bộ lọc.
            </p>
          )}
        </div>
        <footer className="flex items-center justify-between border-t border-line px-3 py-3 text-xs text-ink-muted">
          <span>Hiển thị {filtered.length} trong {items.length} người bệnh</span>
          <button type="button" onClick={() => { setTab("all"); setArrival("all"); setQuery(""); }} className="text-brand-700 hover:underline">
            Xem tất cả
          </button>
        </footer>
      </section>

      {selected ? <PatientDetail item={selected} /> : null}
      {selected ? (
        <CounterPanel
          item={selected}
          items={items}
          onSkip={() => {
            // Chuyển sang người KẾ TIẾP trong danh sách đang hiển thị. Không
            // đụng dữ liệu: người bị bỏ qua vẫn ở nguyên trong hàng đợi, và
            // vẫn check-in được khi họ tới.
            const i = filtered.findIndex((x) => x.id === selected.id);
            const ke = filtered[i + 1] ?? filtered[0];
            if (ke) setSelectedId(ke.id);
          }}
        />
      ) : null}
    </div>
  );
}

/** Bộ hành động của hai nút tròn, dựng ở component cha để một chỗ giữ trạng
 *  thái "đang gửi" và một chỗ hiện câu lỗi — hai nút mà hai ô lỗi thì người
 *  dùng không biết cái nào vừa hỏng. */
function useMocQuay(item: WorklistItem) {
  const router = useRouter();
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function goi(duong: string, method: "POST" | "DELETE" | "PATCH", body?: unknown) {
    setDangGui(true);
    setLoi(null);
    try {
      const res = await fetch(duong, {
        method,
        headers: { "Content-Type": "application/json" },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      if (!res.ok) {
        // GIỮ NGUYÊN câu của backend: "bước Sinh hiệu đã bắt đầu" nói cho người
        // ngồi quầy biết đi hỏi ai; "không thực hiện được" thì không.
        const d = (await res.json().catch(() => null)) as
          | { error?: string; message?: string }
          | null;
        setLoi(d?.message ?? d?.error ?? `Không thực hiện được (HTTP ${res.status})`);
        return false;
      }
      router.refresh();
      return true;
    } finally {
      setDangGui(false);
    }
  }

  const apptId = item.appointment_id;
  const visitId = item.visit_id;
  return {
    loi,
    tay: {
      dangGui,
      checkIn: () => {
        if (apptId) void goi("/api/appointments", "PATCH", { id: apptId, action: "checkin" });
      },
      boCheckIn: () => {
        if (apptId)
          void goi("/api/appointments", "PATCH", { id: apptId, action: "undo_checkin" });
      },
      goiVao: () => {
        if (visitId) void goi(`/api/reception/goi-vao-kham/${visitId}`, "POST");
      },
      boGoiVao: () => {
        if (visitId) void goi(`/api/reception/goi-vao-kham/${visitId}`, "DELETE");
      },
    },
  };
}

function PatientDetail({ item }: { item: WorklistItem }) {
  const { loi: loiMoc, tay } = useMocQuay(item);
  const tone = resolveStatus(item);
  const waited = waitedMinutes(item);
  const targetMinutes = (() => {
    const from = item.checked_in_at ?? item.created_at;
    if (!from || !item.due_at) return null;
    return Math.max(
      0,
      Math.round((new Date(item.due_at).getTime() - new Date(from).getTime()) / 60000),
    );
  })();

  return (
    <section
      aria-label="Thông tin người bệnh"
      className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">Thông tin người bệnh</h2>
        <StatusChip
          tone={STATUS_PRESENTATION[tone].token as StatusTone}
          label={STATUS_PRESENTATION[tone].label}
        />
      </header>

      <div className="grid gap-4 border-b border-line p-4 md:grid-cols-[1.1fr_0.8fr_96px]">
        <div className="flex gap-3">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-line bg-surface-sunken text-base font-semibold text-ink-soft">
            {initials(item.patient.full_name)}
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-lg font-semibold text-ink">
              {item.patient.full_name ?? "Chưa rõ tên"}
            </h3>
            <p className="text-xs text-ink-muted">{patientLine(item.patient) || "—"}</p>
            <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-soft">
              <Phone size={13} aria-hidden /> {item.patient.phone_primary ?? "—"}
            </p>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-ink-soft">
              <IdCard size={13} aria-hidden /> Mã BN: {item.patient.patient_code ?? "—"}
            </p>
          </div>
        </div>
        <dl className="border-l border-line pl-4 text-xs">
          <Field label="Mã số" value={item.queue_number ?? "—"} />
          <Field label="Ngày sinh" value={item.patient.date_of_birth ? new Date(item.patient.date_of_birth).toLocaleDateString("vi-VN") : "—"} />
          <div className="mt-2 flex items-start gap-1.5 text-ink-muted">
            <MapPin size={13} className="mt-0.5 shrink-0" aria-hidden />
            <span>Địa chỉ: Chưa có trong dữ liệu hàng đợi</span>
          </div>
        </dl>
        <div className="rounded-control border border-line p-2 text-center">
          <p className="text-label text-ink-muted">SLA mục tiêu</p>
          <p className="mt-1 font-semibold text-ink">
            {targetMinutes === null ? "—" : `${targetMinutes} phút`}
          </p>
          <div className="my-2 h-1 overflow-hidden rounded-full bg-surface-sunken">
            <div
              className={`h-full ${waited > (targetMinutes ?? Number.POSITIVE_INFINITY) ? "bg-status-overdue" : "bg-warning"}`}
              style={{ width: `${Math.min(100, targetMinutes ? (waited / targetMinutes) * 100 : 0)}%` }}
            />
          </div>
          <p className="text-label text-ink-muted">Thời gian chờ</p>
          <p className="font-semibold text-warning">{waited} phút</p>
        </div>
      </div>

      <div className="grid gap-3 border-b border-line p-3 md:grid-cols-3">
        <InfoCard title="Lịch hẹn" icon={<Clock3 size={15} />}>
          <Field label="Ngày / giờ" value={item.slot_start ? new Date(item.slot_start).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" }) : "—"} />
          <Field label="Hình thức" value={item.booking_channel === "WALK_IN" ? "Đến trực tiếp" : "Đặt hẹn"} />
          <Field label="Bước" value={item.node_name ?? item.node_code} />
        </InfoCard>
        <InfoCard title="Thông tin hàng đợi" icon={<UsersRound size={15} />}>
          <Field label="Thời điểm đến" value={time(item.checked_in_at ?? item.created_at)} />
          <Field label="Vào hàng đợi lúc" value={time(item.created_at)} />
          <Field label="Bắt đầu xử lý" value={time(item.started_at)} />
        </InfoCard>
        <InfoCard title="Bảo hiểm y tế" icon={<ShieldCheck size={15} />}>
          <p className="rounded-control bg-surface-sunken px-2 py-2 text-xs text-ink-muted">
            Chưa có dữ liệu BHYT trong API hàng đợi.
          </p>
        </InfoCard>
      </div>

      <div className="border-b border-line p-4">
        <h3 className="mb-4 text-sm font-semibold text-ink">Trạng thái xử lý</h3>
        <Stepper steps={receptionSteps(item, tay)} />
        {loiMoc ? (
          <p className="mt-2 rounded-md bg-danger-bg px-2 py-1 text-label text-danger">
            {loiMoc}
          </p>
        ) : null}
      </div>

    </section>
  );
}

function CounterPanel({
  item,
  items,
  onSkip,
}: {
  item: WorklistItem;
  items: WorklistItem[];
  /** Bỏ qua lượt này, chuyển sang người tiếp theo trong hàng. */
  onSkip: () => void;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  /** Check-in cho khách đặt lịch trước.
   *
   * Đi qua ĐÚNG đường mà nút "Đã đến" ở Trang chủ đi — `PATCH /api/appointments`
   * với `action: "checkin"`. Không có đường riêng cho màn này: hai đường
   * check-in là hai luật cấp số thứ tự chờ ngày lệch nhau.
   */
  async function checkIn() {
    if (!item.appointment_id) return;
    setError(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: item.appointment_id, action: "checkin" }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      setError(body?.error ?? `Không check-in được (HTTP ${res.status})`);
      return;
    }
    startTransition(() => router.refresh());
  }

  async function issue(command: KernelCommand, reason?: string) {
    setError(null);
    const response = await fetch(`/api/work-items/${item.id}/commands/${command}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_version: item.version, reason }),
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null;
      setError(body?.error ?? `Không thực hiện được (HTTP ${response.status})`);
      return;
    }
    startTransition(() => router.refresh());
  }

  const canAct = item.actionable_by_me && !item.blocked;
  const finished = ["COMPLETED", "SKIPPED", "CANCELLED"].includes(item.status);
  const started = item.status === "IN_PROGRESS";

  return (
    <aside aria-label="Điều phối tại quầy" className="flex flex-col gap-3">
      <section className="rounded-card border border-line bg-surface p-3 shadow-card">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">Điều phối tại quầy</h2>
          <span className="text-xs text-brand-700">Dữ liệu thật</span>
        </div>
        <div className="mt-3 rounded-control border border-line p-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-ink">Hiện trạng quầy</h3>
            <span className="text-label text-warning">Chưa kết nối schema quầy</span>
          </div>
          <dl className="mt-3 grid grid-cols-4 divide-x divide-line text-center">
            {[
              ["Sức chứa", "—"],
              ["Đang phục vụ", items.filter((candidate) => candidate.status === "IN_PROGRESS").length],
              ["Đang chờ", items.filter((candidate) => candidate.status === "PENDING").length],
              ["Trống", "—"],
            ].map(([label, value]) => (
              <div key={label} className="px-1">
                <dt className="text-label text-ink-muted">{label}</dt>
                <dd className="mt-1 text-sm font-semibold text-ink">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="mt-3 rounded-control border border-line p-3">
          <h3 className="flex items-center gap-2 text-xs font-semibold text-ink">
            <Monitor size={15} className="text-brand-600" aria-hidden />
            Xem trước màn hình hiển thị
          </h3>
          {/* MỜI TÊN, KHÔNG MỜI SỐ.
              
              Ở quầy tiếp nhận, Lễ tân gọi tên người bệnh — số thứ tự chỉ để
              đối chiếu. Con số chiếm chỗ to nhất mà không phải thứ được đọc lên. */}
          <div className="mt-3 grid grid-cols-[1fr_62px] overflow-hidden rounded-control border border-brand-500 text-center">
            <div className="bg-surface px-2 py-3">
              <p className="text-label uppercase text-ink-muted">Mời</p>
              <p className="truncate text-2xl font-semibold text-ink">
                {item.patient.full_name ?? "—"}
              </p>
              {item.queue_number ? (
                <p className="text-label text-ink-muted">
                  số {item.queue_number}
                </p>
              ) : null}
            </div>
            <div className="border-l border-line bg-surface px-2 py-3">
              <p className="text-label uppercase text-ink-muted">Chờ</p>
              <p className="text-xl font-semibold text-ink">{waitedMinutes(item)}′</p>
            </div>
          </div>
        </div>

        <div className="mt-3 rounded-control border border-line p-3">
          <h3 className="flex items-center gap-2 text-xs font-semibold text-ink">
            <History size={15} className="text-brand-600" aria-hidden /> Nhật ký thao tác
          </h3>
          <ul className="mt-2 space-y-2 text-label text-ink-muted">
            <li className="grid grid-cols-[40px_1fr] gap-2">
              <span>{time(item.created_at)}</span><span>Đã vào hàng đợi tiếp nhận</span>
            </li>
            {item.started_at ? (
              <li className="grid grid-cols-[40px_1fr] gap-2">
                <span>{time(item.started_at)}</span><span>Đã bắt đầu xử lý</span>
              </li>
            ) : null}
          </ul>
        </div>

        <div className="mt-3 rounded-control border border-line p-3">
          <h3 className="text-xs font-semibold text-ink">Bước tiếp theo</h3>
          <p className="mt-2 flex items-center gap-2 text-xs text-ink-soft">
            <CheckCircle2 size={16} className="text-brand-600" aria-hidden />
            Sau khi xác nhận, kernel sẽ mở bước kế tiếp đủ điều kiện.
          </p>
        </div>
      </section>

      {error ? <p className="rounded-control bg-danger-bg px-3 py-2 text-xs text-danger">{error}</p> : null}

      {/* CHECK-IN — dành cho khách ĐẶT LỊCH TRƯỚC.
          
          Khách đến trực tiếp đã được check-in sẵn lúc tạo lịch (walk-in trong
          ngày tự vào thẳng trạng thái đã đến), nên nút này chỉ hiện khi thật sự
          còn việc để làm. */}
      {item.checked_in_at ? (
        <p className="rounded-control bg-success-bg px-3 py-2 text-xs text-success">
          Đã check-in lúc {time(item.checked_in_at)}
        </p>
      ) : (
        <button
          type="button"
          disabled={!item.appointment_id || pending}
          onClick={() => checkIn()}
          className="flex w-full items-center justify-center gap-2 rounded-control border border-brand-600 bg-surface px-4 py-2.5 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken disabled:text-ink-faint"
        >
          <CheckCircle2 size={17} />
          {pending ? "Đang lưu…" : "Check-in — khách đã đến"}
        </button>
      )}

      {/* CHƯA ĐẾN → GỌI NGƯỜI TIẾP THEO, không phải "đánh dấu vắng mặt".
          
          Người chưa có mặt lúc Lễ tân gọi vẫn Ở TRONG hàng đợi: họ chỉ bị bỏ
          qua lượt này để quầy phục vụ người khác. Đến sau vẫn check-in được, và
          LUẬT ĐẾN MUỘN tự áp dụng — check-in trong khung giờ của mình thì vẫn
          giữ suất đã đặt, ngoài khung thì xuống làn "đến sau", xếp theo giờ đến
          (services/queue_order.py).
          
          Vì thế KHÔNG có nút "vắng mặt" ở đây: đánh dấu vắng mặt là một kết
          luận, mà lúc này chưa ai kết luận được điều gì. */}
      <button
        type="button"
        onClick={onSkip}
        className="flex w-full items-center justify-center gap-2 rounded-control border border-line bg-surface px-4 py-2 text-xs font-medium text-ink-soft hover:bg-surface-sunken"
      >
        <UserRoundX size={15} /> Chưa đến — gọi người tiếp theo
      </button>
      {item.status === "PENDING" ? (
        <button
          type="button"
          disabled={!canAct || pending}
          onClick={() => issue("start")}
          className="flex w-full items-center justify-center gap-2 rounded-control border border-brand-600 bg-surface px-4 py-2.5 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken disabled:text-ink-faint"
        >
          {pending ? "Đang lưu…" : "Bắt đầu xử lý"}
        </button>
      ) : null}
      <button
        type="button"
        disabled={!canAct || !started || finished || pending}
        onClick={() => issue("complete")}
        className="flex w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-4 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
      >
        <CheckCircle2 size={19} />
        {pending ? "Đang lưu…" : "Xong tiếp nhận — mời vào khám"}
      </button>
    </aside>
  );
}

function InfoCard({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-control border border-line p-3">
      <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink">
        <span className="text-brand-600">{icon}</span>{title}
      </h3>
      <dl className="space-y-1.5 text-xs">{children}</dl>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}
