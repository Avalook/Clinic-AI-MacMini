"use client";

// CskhTasksView — Nhiệm vụ chăm sóc (Ảnh 2).
// 2 cột: danh sách công việc bên trái + chi tiết + form ghi nhận bên phải.
// Nút "Đã liên hệ", "Chưa nghe máy", "Cần BS hỗ trợ" → gọi API thật.

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CalendarCheck2,
  CalendarClock,
  CheckCircle2,
  Clock,
  ClipboardList,
  ExternalLink,
  Phone,
  PhoneOff,
  Search,
  Stethoscope,
  UserRoundX,
  UsersRound,
  Upload,
  Video,
  Send,
  MessageSquare,
} from "lucide-react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import { fmtDate, fmtDateTimeOrDate, fmtTimeOrNone, VN_TZ } from "@/lib/datetime";

// ── Types ──────────────────────────────────────────────────────────────────

export interface CskhTaskRow {
  id: string;
  sourceType: "appointment" | "cskh_action";
  sourceId: string;
  category: string;
  step: string;
  status: string;
  description: string | null;
  deadlineAt: string | null;
  createdAt: string | null;
  assignee: string | null;
  patientId: string | null;
  patientName: string;
  patientPhone: string | null;
  patientCode: string | null;
  resultText: string | null;
}

interface Props {
  tasks: CskhTaskRow[];
  stats: {
    todayDeadline: number;
    overSla: number;
    waitingResponse: number;
    done: number;
  };
}

// ── Constants ──────────────────────────────────────────────────────────────

type TaskTab = "all" | "today" | "sla" | "waiting" | "done";

const TABS: { key: TaskTab; label: string }[] = [
  { key: "all", label: "Tất cả khách hàng" },
  { key: "today", label: "Cần theo dõi" },
  { key: "sla", label: "Quá SLA" },
  { key: "waiting", label: "Nhiệm vụ hôm nay" },
];

const CATEGORY_LABEL: Record<string, string> = {
  NHAC_HEN: "Nhắc lịch ngày mai",
  XAC_NHAN_LICH: "Nhắc lịch trong tuần",
  PHAN_LAI_LICH: "Phân lại lịch bị từ chối",
  SAU_KHAM: "Theo dõi sau khám",
  TRA_KET_QUA: "Trả kết quả xét nghiệm",
  TAI_KHAM: "Đặt lịch tái khám",
  HUY_LICH: "Hủy lịch — gọi lại",
  CHAM_SOC: "Chăm sóc khách hàng",
  GOI_HOI_THAM: "Gọi hỏi thăm",
  CHUC_MUNG: "Chúc mừng đầy tháng",
};

const CONTACT_RESULTS = [
  { key: "CONTACTED", label: "Đã liên hệ", icon: Phone },
  { key: "NO_ANSWER", label: "Chưa nghe máy", icon: PhoneOff },
  { key: "NEED_DOCTOR", label: "Cần bác sĩ hỗ trợ", icon: Stethoscope },
] as const;

const CANCEL_REASONS = [
  "BN báo không đến được (trước 7 ngày)",
  "BN báo không đến (đã đặt lịch trước đó)",
  "Vào giờ khám mới báo không đến",
  "Lý do khác",
] as const;

function statusTone(status: string): StatusTone {
  if (status === "DONE" || status === "CLOSED" || status === "COMPLETED")
    return "completed";
  if (status === "WAITING" || status === "CSKH_CONFIRMED") return "assigned";
  if (status === "DOCTOR_DECLINED" || status === "CANCELLED") return "cancelled";
  if (status === "OVERDUE") return "overdue";
  return "ready";
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    // Hai trạng thái CŨ — lịch mới vào thẳng CONFIRMED từ 04/08/2026.
    SCHEDULED: "Chờ xác nhận (lịch cũ)",
    CSKH_CONFIRMED: "Đã xác nhận (lịch cũ)",
    CONFIRMED: "Đã đặt lịch",
    CHECKED_IN: "Đã đến",
    DOCTOR_DECLINED: "Bị từ chối",
    OPEN: "Đang xử lý",
    WAITING: "Chờ phản hồi",
    DONE: "Hoàn thành",
    CLOSED: "Đã đóng",
    IN_PROGRESS: "Đang xử lý",
  };
  return map[status] ?? status;
}

function deadlineDisplay(d: string | null): { text: string; overdue: boolean } {
  if (!d) return { text: "—", overdue: false };
  const now = new Date();
  const deadline = new Date(d);
  const diffMs = deadline.getTime() - now.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 0) {
    const overMin = -diffMin;
    if (overMin < 60) return { text: `Quá hạn ${overMin} phút`, overdue: true };
    const overHours = Math.floor(overMin / 60);
    if (overHours < 24) return { text: `Quá hạn ${overHours} giờ`, overdue: true };
    return { text: `Quá hạn ${Math.floor(overHours / 24)} ngày`, overdue: true };
  }
  if (diffMin < 60) return { text: `Còn ${diffMin} phút`, overdue: false };
  const hours = Math.floor(diffMin / 60);
  if (hours < 24) return { text: `${fmtTimeOrNone(d)} hôm nay`, overdue: false };
  return { text: fmtDate(d), overdue: false };
}

// ── Component ──────────────────────────────────────────────────────────────

export default function CskhTasksView({ tasks, stats }: Props) {
  const router = useRouter();
  const [tab, setTab] = useState<TaskTab>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(
    tasks[0]?.id ?? null,
  );

  // Contact result form state
  const [contactResult, setContactResult] = useState<string | null>(null);
  // Lỗi lưu phải HIỆN RA. Bản trước chỉ kiểm `res.ok` rồi bỏ qua nhánh sai.
  const [loi, setLoi] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [nextStep, setNextStep] = useState("GỌI_LẠI_SAU_2H");
  const [cancelReason, setCancelReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());

  const nowIso = new Date().toISOString();
  const todayStart = new Date(
    new Date().toLocaleDateString("en-CA", { timeZone: VN_TZ }) +
      "T00:00:00+07:00",
  ).toISOString();
  const todayEnd = new Date(
    new Date(todayStart).getTime() + 24 * 60 * 60 * 1000,
  ).toISOString();

  const visibleTasks = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return tasks.filter((t) => {
      if (doneIds.has(t.id)) return false;
      // tab filter
      if (tab === "today") {
        return t.deadlineAt && t.deadlineAt >= todayStart && t.deadlineAt < todayEnd;
      }
      if (tab === "sla") {
        return t.deadlineAt && t.deadlineAt < nowIso && t.status !== "DONE";
      }
      if (tab === "waiting") {
        return t.step === "CHỜ_PHẢN_HỒI" || t.status === "WAITING";
      }
      if (tab === "done") {
        return t.status === "DONE" || t.status === "CLOSED";
      }
      // search
      if (needle) {
        return [t.patientName, t.patientPhone, t.patientCode, t.description]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(needle);
      }
      return true;
    });
  }, [tasks, tab, query, doneIds, todayStart, todayEnd, nowIso]);

  const selected =
    visibleTasks.find((t) => t.id === selectedId) ?? visibleTasks[0] ?? null;

  // MỌI TỔ HỢP ĐỀU PHẢI GỬI MỘT THỨ GÌ ĐÓ.
  //
  // Bản trước là một chuỗi if/else-if không có else: với việc thuộc loại
  // "appointment" mà kết quả KHÁC "CONTACTED" — tức đúng hai trường hợp cần
  // ghi lại nhất, "Chưa nghe máy" và "Cần bác sĩ hỗ trợ" — không nhánh nào
  // chạy. Không request, không lỗi, mà `setContactResult(null)` và
  // `setNote("")` ở cuối vẫn chạy: form tự xoá trắng đúng như khi lưu thành
  // công. Người dùng tin là đã lưu; database không nhận gì.
  //
  // Luật đúng: "đã liên hệ được" với một lịch hẹn thì XÁC NHẬN lịch (việc của
  // nút này từ trước). Mọi kết quả khác là một LẦN GỌI đã xảy ra và phải được
  // ghi vào nhật ký CSKH — kể cả khi không ai bắt máy. Không bắt máy vẫn là
  // một việc đã làm.
  /** Ghi lại một cuộc gọi đã xảy ra, và xác nhận lịch NẾU lịch còn cần xác nhận.
   *
   * `cskh_confirm` chỉ nhận lịch ở trạng thái SCHEDULED (booking_service TRANSITIONS).
   * Từ 04/08/2026 mọi lịch mới đặt thẳng vào CONFIRMED — vòng gọi-xác-nhận đã bỏ —
   * nên gửi lệnh ấy cho một lịch mới là chắc chắn lỗi chuyển trạng thái. Nút "Đã
   * liên hệ" vì thế HỎNG với mọi lịch đặt sau ngày đó; chỉ 23 dòng SCHEDULED cũ
   * còn dùng được.
   *
   * Thứ đáng giá của cuộc gọi không phải là đổi trạng thái lịch — nó vốn đã chắc.
   * Thứ đáng giá là DẤU VẾT: đã gọi, lúc nào, kết quả ra sao. Nên luôn ghi nhật ký,
   * và chỉ đổi trạng thái khi lịch thật sự đang chờ xác nhận.
   */
  async function handleSaveResult() {
    if (!selected || !contactResult) return;
    setSaving(true);
    try {
      const canXacNhan =
        selected.sourceType === "appointment" &&
        contactResult === "CONTACTED" &&
        selected.status === "SCHEDULED";

      const res = canXacNhan
        ? await fetch("/api/appointments", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              id: selected.sourceId,
              action: "cskh_confirm",
            }),
          })
        : await fetch("/api/cskh-followup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              clinic_patient_id: selected.patientId,
              result: contactResult,
              note,
            }),
          });

      if (!res.ok) {
        // Im lặng nuốt lỗi là cách bản trước làm hỏng việc. Nói ra.
        const chi_tiet = await res
          .json()
          .then((d: { error?: string }) => d.error)
          .catch(() => null);
        setLoi(chi_tiet ?? "Không lưu được kết quả cuộc gọi. Thử lại giúp em.");
        return;
      }

      setLoi(null);
      setDoneIds((prev) => new Set(prev).add(selected.id));
      router.refresh();
      setContactResult(null);
      setNote("");
    } finally {
      setSaving(false);
    }
  }

  async function handleComplete() {
    if (!selected) return;
    setSaving(true);
    try {
      // Cùng lý do như handleSaveResult: chỉ lịch SCHEDULED mới xác nhận được.
      if (
        selected.sourceType === "appointment" &&
        selected.status === "SCHEDULED"
      ) {
        const res = await fetch("/api/appointments", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: selected.sourceId,
            action: "cskh_confirm",
          }),
        });
        if (!res.ok) {
          // Nhánh này trước đây không tồn tại: lỗi rơi vào im lặng và việc vẫn
          // trông như chưa làm, nên người dùng bấm lại mãi.
          setLoi("Không xác nhận được lịch hẹn. Thử lại giúp em.");
          return;
        }
        setLoi(null);
        setDoneIds((prev) => new Set(prev).add(selected.id));
        router.refresh();
      } else {
        const res = await fetch("/api/cskh-followup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            clinic_patient_id: selected.patientId,
            result: "COMPLETED",
            note,
          }),
        });
        if (!res.ok) {
          setLoi("Không đánh dấu hoàn tất được. Thử lại giúp em.");
          return;
        }
        setLoi(null);
        setDoneIds((prev) => new Set(prev).add(selected.id));
        router.refresh();
      }
    } finally {
      setSaving(false);
    }
  }

  const deadline = selected ? deadlineDisplay(selected.deadlineAt) : null;

  return (
    <div className="space-y-3">
      {/* Stat cards */}
      <StatRow>
        <StatCard
          label="Cần làm hôm nay"
          value={stats.todayDeadline}
          tone="brand"
          icon={<ClipboardList className="size-5" />}
        />
        <StatCard
          label="Quá SLA"
          value={stats.overSla}
          tone="danger"
          icon={<Clock className="size-5 text-danger" />}
        />
        <StatCard
          label="Chờ phản hồi"
          value={stats.waitingResponse}
          tone="warning"
          icon={<CalendarClock className="size-5 text-warning" />}
        />
        <StatCard
          label="Đã hoàn thành"
          value={stats.done}
          tone="success"
          icon={<CheckCircle2 className="size-5 text-success" />}
        />
      </StatRow>

      {/* Tabs */}
      <div className="flex overflow-x-auto border-b border-line text-sm">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`shrink-0 border-b-2 px-3 py-2.5 font-medium transition-colors ${
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Search & filter bar */}
      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-surface p-3 shadow-card">
        <label className="flex min-h-9 flex-1 items-center gap-2 rounded-xl border border-line px-3 text-ink-muted focus-within:border-brand-500">
          <Search className="size-4" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm công việc hoặc khách hàng"
            className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
      </div>

      {/* 2-column layout */}
      <div className="grid items-start gap-3 xl:grid-cols-[minmax(300px,1fr)_minmax(380px,1.1fr)]">
        {/* Left: Task list */}
        <section
          aria-label="Danh sách công việc"
          className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
        >
          <header className="border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">
              Danh sách công việc
            </h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              {visibleTasks.length} công việc
            </p>
          </header>

          {/* Table header */}
          <div className="grid grid-cols-[minmax(140px,1.2fr)_minmax(100px,0.8fr)_minmax(90px,0.65fr)_minmax(80px,0.55fr)_minmax(80px,0.55fr)] gap-2 border-b border-line bg-surface-muted px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
            <span>Công việc</span>
            <span>Khách hàng</span>
            <span>Trạng thái</span>
            <span>Hạn xử lý</span>
            <span>Phụ trách</span>
          </div>

          <div className="max-h-[560px] overflow-y-auto divide-y divide-line">
            {visibleTasks.length > 0 ? (
              visibleTasks.map((t) => {
                const active = selected?.id === t.id;
                const dl = deadlineDisplay(t.deadlineAt);
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setSelectedId(t.id)}
                    className={`grid w-full grid-cols-[minmax(140px,1.2fr)_minmax(100px,0.8fr)_minmax(90px,0.65fr)_minmax(80px,0.55fr)_minmax(80px,0.55fr)] items-center gap-2 px-3 py-3 text-left transition-colors ${
                      active
                        ? "border-l-2 border-l-brand-500 bg-brand-50/60"
                        : "border-l-2 border-l-transparent hover:bg-surface-sunken"
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        {t.category === "NHAC_HEN" && (
                          <CalendarCheck2 className="size-3.5 shrink-0 text-brand-600" />
                        )}
                        {t.category === "PHAN_LAI_LICH" && (
                          <UserRoundX className="size-3.5 shrink-0 text-danger" />
                        )}
                        {!["NHAC_HEN", "PHAN_LAI_LICH"].includes(t.category) && (
                          <Phone className="size-3.5 shrink-0 text-ink-muted" />
                        )}
                        <span className="truncate text-xs font-semibold text-ink">
                          {CATEGORY_LABEL[t.category] ?? t.category}
                        </span>
                      </div>
                      <span className="mt-0.5 block truncate text-[11px] text-ink-muted">
                        {t.description}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <span className="block truncate text-xs font-medium text-ink">
                        {t.patientName}
                      </span>
                    </div>
                    <div>
                      <StatusChip
                        tone={statusTone(t.status)}
                        label={statusLabel(t.status)}
                      />
                    </div>
                    <div>
                      <span
                        className={`text-xs font-semibold ${
                          dl.overdue
                            ? "rounded-md bg-danger-bg px-1.5 py-0.5 text-danger"
                            : "text-ink-muted"
                        }`}
                      >
                        {dl.text}
                      </span>
                    </div>
                    <div className="text-xs font-medium text-ink truncate">
                      {t.assignee ?? "—"}
                    </div>
                  </button>
                );
              })
            ) : (
              <p className="px-4 py-14 text-center text-sm text-ink-muted">
                Không có công việc khớp bộ lọc.
              </p>
            )}
          </div>
        </section>

        {/* Right: Detail panel */}
        {selected ? (
          <section
            aria-label="Chi tiết công việc"
            className="rounded-2xl border border-line bg-surface p-4 shadow-card space-y-4"
          >
            {/* Header with category tag and deadline */}
            <div className="flex items-start justify-between border-b border-line pb-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="inline-block rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-semibold text-brand-700">
                    {selected.category === "NHAC_HEN" ||
                    selected.category === "XAC_NHAN_LICH"
                      ? "Nhắc lịch"
                      : "Chăm sóc"}
                  </span>
                </div>
                <h2 className="mt-2 text-base font-bold text-ink">
                  {CATEGORY_LABEL[selected.category] ?? selected.category}
                </h2>
                <p className="mt-0.5 text-xs font-mono text-ink-muted">
                  {selected.sourceType === "appointment"
                    ? `APT-${selected.sourceId.slice(0, 8)}`
                    : `FU-${selected.sourceId.slice(0, 8)}`}
                </p>
              </div>
              {deadline && (
                <div className="text-right shrink-0">
                  <span
                    className={`inline-block rounded-lg px-2.5 py-1 text-xs font-bold ${
                      deadline.overdue
                        ? "bg-danger-bg text-danger"
                        : "bg-brand-50 text-brand-700"
                    }`}
                  >
                    {deadline.overdue ? "Quá hạn" : "Đến hạn"}
                  </span>
                  <p className="mt-1 text-xs text-ink-muted">
                    {deadline.text}
                  </p>
                </div>
              )}
            </div>

            {/* Patient info */}
            <div className="flex items-center gap-3 rounded-xl border border-line bg-surface-muted p-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
                {selected.patientName
                  .trim()
                  .split(/\s+/)
                  .slice(-2)
                  .map((w) => w[0]?.toUpperCase() ?? "")
                  .join("") || "KH"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold text-ink">
                  {selected.patientName}
                </p>
                <p className="text-xs text-ink-muted">
                  {selected.patientCode ?? "—"} ·{" "}
                  {selected.patientPhone ?? "Chưa có SĐT"}
                </p>
              </div>
              {selected.patientId && (
                <Link
                  href={`/customers?selected=${selected.patientId}`}
                  className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-[11px] font-medium text-brand-700 hover:bg-brand-50"
                >
                  <ExternalLink className="size-3" /> Mở hồ sơ
                </Link>
              )}
            </div>

            {/* Context info */}
            <dl className="grid gap-2 rounded-xl border border-line bg-surface-muted p-3 text-xs sm:grid-cols-2">
              <div>
                <dt className="text-ink-muted">Lý do</dt>
                <dd className="mt-0.5 font-medium text-ink">
                  {selected.description || "—"}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Lần liên hệ gần nhất</dt>
                <dd className="mt-0.5 font-medium text-ink">
                  {selected.createdAt
                    ? fmtDateTimeOrDate(selected.createdAt)
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Phụ trách</dt>
                <dd className="mt-0.5 font-medium text-ink">
                  {selected.assignee ?? "Chưa phân công"}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Trạng thái</dt>
                <dd className="mt-1">
                  <StatusChip
                    tone={statusTone(selected.status)}
                    label={statusLabel(selected.status)}
                  />
                </dd>
              </div>
            </dl>

            {/* Contact result buttons */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-ink">
                Kết quả liên hệ
              </h3>
              <div className="flex flex-wrap gap-2">
                {CONTACT_RESULTS.map((cr) => {
                  const Icon = cr.icon;
                  const active = contactResult === cr.key;
                  return (
                    <button
                      key={cr.key}
                      type="button"
                      onClick={() => setContactResult(cr.key)}
                      className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-all ${
                        active
                          ? "border-brand-600 bg-brand-50 text-brand-700 shadow-xs"
                          : "border-line bg-surface text-ink-soft hover:border-brand-300 hover:bg-brand-50"
                      }`}
                    >
                      <Icon className="size-3.5" />
                      {cr.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Upload Kết quả Siêu âm & Xét nghiệm (Hình ảnh + Video) */}
            <div className="space-y-1.5 rounded-xl border border-line bg-surface-muted p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-ink flex items-center gap-1.5">
                  <Upload className="size-3.5 text-brand-600" />
                  Upload kết quả siêu âm &amp; xét nghiệm (Ảnh + Video)
                </span>
                <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">
                  Tính năng sẽ ra mắt ở phiên bản tiếp theo
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-line bg-surface px-3 py-1.5 text-xs text-ink-muted cursor-not-allowed opacity-75"
                >
                  <Upload className="size-3.5" /> Thêm ảnh siêu âm
                </button>
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-line bg-surface px-3 py-1.5 text-xs text-ink-muted cursor-not-allowed opacity-75"
                >
                  <Video className="size-3.5" /> Thêm video siêu âm
                </button>
              </div>
            </div>

            {/* Gửi Zalo / SMS cho bệnh nhân */}
            <div className="space-y-1.5 rounded-xl border border-line bg-surface-muted p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-ink flex items-center gap-1.5">
                  <Send className="size-3.5 text-brand-600" />
                  Gửi thông báo qua Zalo / SMS
                </span>
                <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">
                  Tính năng sẽ ra mắt ở phiên bản tiếp theo
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink-muted cursor-not-allowed opacity-75"
                >
                  <MessageSquare className="size-3.5 text-blue-600" /> Gửi Zalo OA
                </button>
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink-muted cursor-not-allowed opacity-75"
                >
                  <Phone className="size-3.5 text-emerald-600" /> Gửi tin nhắn SMS
                </button>
              </div>
            </div>

            {/* Note */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-ink">Ghi chú</label>
              <textarea
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Ghi nhận phản hồi của khách hàng"
                className="w-full rounded-xl border border-line p-2.5 text-xs text-ink outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20"
              />
            </div>

            {/* Next step + cancel reason (conditional) */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-ink">
                  Bước tiếp theo
                </label>
                <select
                  value={nextStep}
                  onChange={(e) => setNextStep(e.target.value)}
                  className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-xs text-ink outline-none focus:border-brand-500"
                >
                  <option value="GỌI_LẠI_SAU_2H">Gọi lại sau 2 giờ</option>
                  <option value="GHI_NHAN_KET_QUA">
                    Ghi nhận kết quả liên hệ
                  </option>
                  <option value="CHON_BUOC_TIEP">Chọn bước tiếp theo</option>
                  <option value="DAT_LICH_TAI_KHAM">
                    Đặt lịch tái khám
                  </option>
                  <option value="GUI_KET_QUA">Gửi kết quả XN</option>
                </select>
              </div>
              {/* BA Ô TICK ĐÃ BỎ (08/08/2026).
                  Chúng không có `checked`, không có `onChange`, và không đi
                  vào lời gọi nào — thuần trang trí. Một ô tick bấm được nhưng
                  không lưu là lời hứa với người dùng rằng họ vừa ghi lại một
                  điều kiện; đến ca sau không ai tìm thấy nó. */}
            </div>

            {/* Cancel reason (shown for PHAN_LAI_LICH / HUY_LICH tasks) */}
            {(selected.category === "PHAN_LAI_LICH" ||
              selected.category === "HUY_LICH") && (
              <div className="space-y-1">
                <label className="text-xs font-semibold text-ink">
                  Lý do hủy lịch
                </label>
                <select
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-xs text-ink outline-none focus:border-brand-500"
                >
                  <option value="">Chọn lý do hoặc tự viết bên dưới</option>
                  {CANCEL_REASONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                {cancelReason === "Lý do khác" && (
                  <textarea
                    rows={2}
                    placeholder="Nhập lý do cụ thể..."
                    className="w-full rounded-xl border border-line p-2.5 text-xs text-ink outline-none focus:border-brand-500"
                  />
                )}
              </div>
            )}

            {/* Lỗi lưu — hiện ra chứ không nuốt. Không có dòng này thì một lần
                lưu hỏng trông y hệt một lần lưu được. */}
            {loi && (
              <p className="rounded-xl border border-danger bg-danger-bg px-3 py-2 text-xs text-danger">
                {loi}
              </p>
            )}

            {/* Action buttons */}
            <div className="flex gap-3 pt-2 border-t border-line">
              <button
                type="button"
                onClick={handleSaveResult}
                disabled={saving}
                className="flex-1 rounded-xl border border-line bg-surface px-3 py-2.5 text-xs font-semibold text-ink hover:bg-surface-sunken disabled:opacity-50"
              >
                {saving ? "Đang lưu..." : "Lưu nháp"}
              </button>
              <button
                type="button"
                onClick={handleComplete}
                disabled={saving}
                className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-3 py-2.5 text-xs font-bold text-white hover:bg-brand-700 disabled:opacity-50 shadow-sm"
              >
                <CheckCircle2 className="size-4" />
                {saving ? "Đang lưu..." : "Hoàn thành công việc"}
              </button>
            </div>
          </section>
        ) : (
          <section className="grid min-h-[400px] place-items-center rounded-2xl border border-line bg-surface shadow-card">
            <div className="text-center">
              <UsersRound
                className="mx-auto size-8 text-ink-faint"
                aria-hidden="true"
              />
              <p className="mt-3 text-sm font-medium text-ink">
                Chưa chọn công việc
              </p>
              <p className="mt-1 text-xs text-ink-muted">
                Chọn một dòng bên trái để xem chi tiết và xử lý.
              </p>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
