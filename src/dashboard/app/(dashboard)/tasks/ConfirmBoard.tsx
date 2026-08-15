"use client";

// CSKH "Tình trạng lịch hẹn": MỘT bảng (các cột trạng thái chung trong 1 khung)
// bên trái; click tên KH → panel "Thông tin khách hàng" hiện BÊN CẠNH (ngang).
// Panel có 2 nút: Xác nhận (cskh_confirm) / Không xác nhận → sửa tại chỗ.
// CCCD KHÔNG hiển thị/sửa (D-identity).

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Check, Pencil, X, Ban, CalendarClock } from "lucide-react";
import { fmtTimeOrNone, vnLocalToUtcISO, nowMs } from "../../../lib/datetime";
import {
  todayVn,
  clinicHoursForDate,
  clinicHoursError,
  currentWeekStartVn,
  shiftWeek,
  weekDates,
  dayLabel,
  fmtDayMonth,
} from "../../../lib/roster";
import { digitsOnly, phoneError, daysInMonth, unaccentVi } from "../../../lib/validation";
import { INPUT, LABEL } from "../form-ui";
import {
  LY_DO_HUY,
  LY_DO_HUY_THU_TU,
  nhanLyDoHuy,
} from "../../../lib/ly-do-huy";
import Time24Input from "../Time24Input";
import StatusBadge from "../StatusBadge";
import { useBookingPolicy } from "../BookingPolicyContext";

export interface Opt {
  id: string;
  label: string;
}

export interface ApptRow {
  id: string;
  slot_start: string;
  status: string;
  booking_channel: string | null;
  cancellation_reason?: string | null;
  ly_do_huy_ma?: string | null;
  cancelled_at?: string | null;
  patient: {
    clinic_patient_id: string;
    full_name: string;
    patient_code: string;
    phone_primary: string | null;
    phone_secondary: string | null;
    date_of_birth: string | null;
    location_id: string | null;
    gender: string | null;
    ethnicity: string | null;
    nationality: string | null;
    occupation: string | null;
    patient_objection: string | null;
    address: string | null;
    guardian_name: string | null;
  } | null;
  doctor: { full_name: string } | null;
  service: { name: string } | null;
}

// Board "Tình trạng lịch hẹn" — dạng LỊCH theo NGÀY (thay 4 cột trạng thái cũ):
// cột Ngày · Giờ · Bệnh nhân · Dịch vụ · Bác sĩ · Trạng thái; lọc theo KỲ + TRẠNG THÁI.
const STATUS_GROUPS: { key: string; label: string; statuses: string[] }[] = [
  { key: "all", label: "Tất cả", statuses: [] },
  { key: "pending", label: "Chờ xác nhận", statuses: ["SCHEDULED"] },
  { key: "confirmed", label: "Đã xác nhận", statuses: ["CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"] },
  { key: "done", label: "Đã khám xong", statuses: ["COMPLETED"] },
  { key: "off", label: "Huỷ / Từ chối", statuses: ["CANCELLED", "DOCTOR_DECLINED", "NO_SHOW"] },
];
const PERIODS: { key: string; label: string }[] = [
  { key: "all", label: "Tất cả" },
  { key: "today", label: "Hôm nay" },
  { key: "week", label: "Tuần này" },
  { key: "next", label: "Tuần sau" },
  { key: "month", label: "Tháng này" },
];

interface Form {
  full_name: string;
  date_of_birth: string;
  phone_primary: string;
  phone_secondary: string;
  location_id: string;
  gender: string;
  ethnicity: string;
  nationality: string;
  occupation: string;
  patient_objection: string;
  address: string;
  guardian_name: string;
}

export default function ConfirmBoard({
  rows,
  locations,
  doctors = [],
  canManage = false,
}: {
  rows: ApptRow[];
  locations: Opt[];
  /** Bác sĩ để PHÂN LẠI lịch bị từ chối (chỉ cần khi canManage). */
  doctors?: Opt[];
  /** CSKH/Quản lý: được Hủy lịch + Phân lại bác sĩ. */
  canManage?: boolean;
}) {
  const router = useRouter();
  // Giờ mở cửa để chặn đổi lịch ra ngoài giờ — đọc từ cấu hình phòng khám,
  // không còn là hằng số trong lib/roster.ts.
  const policy = useBookingPolicy();
  const [selId, setSelId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCancel, setShowCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [maLyDo, setMaLyDo] = useState("");
  // Đổi lịch (theo yêu cầu khách): ngày/giờ mới + tuỳ chọn đổi bác sĩ.
  const [showResched, setShowResched] = useState(false);
  const [reschedDate, setReschedDate] = useState("");
  const [reschedTime, setReschedTime] = useState("");
  const [reschedDoc, setReschedDoc] = useState("");
  const [reschedDocQ, setReschedDocQ] = useState("");
  const [reschedDocOpen, setReschedDocOpen] = useState(false);
  const filteredDoctors = useMemo(() => {
    const t = unaccentVi(reschedDocQ.trim());
    if (!t) return doctors;
    return doctors.filter((d) => unaccentVi(d.label).includes(t));
  }, [reschedDocQ, doctors]);

  const sel = rows.find((r) => r.id === selId) ?? null;
  const locName = (id: string | null) =>
    locations.find((l) => l.id === id)?.label ?? "—";
  // Còn "sống" → hủy / đổi lịch được (gồm CSKH đã xác nhận, chờ bác sĩ).
  const LIVE = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"];
  // Giới hạn giờ đổi lịch theo giờ mở cửa của ngày mới.
  const rCh =
    reschedDate && policy ? clinicHoursForDate(reschedDate, policy.hours) : null;
  const rMinHour = rCh ? Number(rCh.open.slice(0, 2)) : 0;
  const rMaxHour = rCh ? Number(rCh.close.slice(0, 2)) - 1 : 23;

  function select(a: ApptRow) {
    setSelId(a.id);
    setEditing(false);
    setError(null);
    setShowCancel(false);
    setCancelReason("");
    setShowResched(false);
    setReschedDate("");
    setReschedTime("");
    setReschedDoc("");
    setReschedDocQ("");
  }
  function close() {
    setSelId(null);
    setEditing(false);
    setError(null);
    setShowCancel(false);
    setShowResched(false);
  }

  function startEdit() {
    if (!sel?.patient) return;
    const p = sel.patient;
    setForm({
      full_name: p.full_name ?? "",
      date_of_birth: p.date_of_birth ?? "",
      phone_primary: p.phone_primary ?? "",
      phone_secondary: p.phone_secondary ?? "",
      location_id: p.location_id ?? locations[0]?.id ?? "",
      gender: p.gender ?? "",
      ethnicity: p.ethnicity ?? "",
      nationality: p.nationality ?? "",
      occupation: p.occupation ?? "",
      patient_objection: p.patient_objection ?? "",
      address: p.address ?? "",
      guardian_name: p.guardian_name ?? "",
    });
    setEditing(true);
    setError(null);
  }

  async function patchAppt(payload: Record<string, unknown>, errMsg: string) {
    if (!sel) return;
    setBusy(true);
    setError(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: sel.id, ...payload }),
    });
    setBusy(false);
    if (!res.ok) {
      setError((await res.json()).error ?? errMsg);
      return;
    }
    setShowCancel(false);
    setShowResched(false);
    router.refresh();
  }

  async function confirm() {
    await patchAppt({ action: "cskh_confirm" }, "Lỗi xác nhận.");
  }
  async function cancelAppt() {
    await patchAppt(
      { action: "cancel", ly_do_huy_ma: maLyDo, cancellation_reason: cancelReason },
      "Lỗi hủy lịch.",
    );
  }
  async function reschedule() {
    if (!reschedDate || !reschedTime) {
      setError("Chọn ngày và giờ mới.");
      return;
    }
    const start = new Date(vnLocalToUtcISO(reschedDate, reschedTime));
    if (start.getTime() < nowMs()) {
      setError("Không thể đổi sang ngày/giờ trong quá khứ.");
      return;
    }
    const chErr = policy
        ? clinicHoursError(reschedDate, reschedTime, policy.hours)
        : "Chưa đọc được giờ mở cửa của phòng khám.";
    if (chErr) {
      setError(chErr);
      return;
    }
    const end = new Date(start.getTime() + 30 * 60_000);
    const payload: Record<string, unknown> = {
      action: "reschedule",
      slot_start: start.toISOString(),
      slot_end: end.toISOString(),
    };
    if (reschedDoc) payload.doctor_id = reschedDoc; // rỗng = giữ bác sĩ hiện tại
    await patchAppt(payload, "Lỗi đổi lịch.");
  }

  async function save() {
    if (!sel || !form) return;
    const ve = phoneError(form.phone_primary) || phoneError(form.phone_secondary);
    if (ve) return setError(ve);
    setBusy(true);
    setError(null);
    const res = await fetch("/api/patients", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: sel.patient?.clinic_patient_id,
        ...form,
      }),
    });
    setBusy(false);
    if (!res.ok) return setError((await res.json()).error ?? "Lỗi lưu.");
    setEditing(false);
    router.refresh();
  }

  const set = (k: keyof Form, v: string) =>
    setForm((f) => (f ? { ...f, [k]: v } : f));

  // ---- Lọc theo KỲ (tuần này/sau, tháng) + TRẠNG THÁI; sắp theo giờ ----
  // Mặc định "Tất cả" để KHÔNG ẩn lịch tuần/tháng khác (CSKH không sót lịch cần
  // xác nhận); người dùng tự lọc Tuần này/Tuần sau/Tháng nếu muốn gọn.
  const [period, setPeriod] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const vnDate = (iso: string) =>
    new Date(new Date(iso).getTime() + 7 * 3_600_000).toISOString().slice(0, 10);
  const today = todayVn();
  const wk = weekDates(currentWeekStartVn());
  const nwk = weekDates(shiftWeek(currentWeekStartVn(), 1));
  const monthStart = today.slice(0, 7) + "-01";
  const monthEnd =
    today.slice(0, 7) +
    "-" +
    String(
      daysInMonth(Number(today.slice(5, 7)), Number(today.slice(0, 4))),
    ).padStart(2, "0");
  const RANGE: Record<string, [string, string] | null> = {
    all: null,
    today: [today, today],
    week: [wk[0], wk[6]],
    next: [nwk[0], nwk[6]],
    month: [monthStart, monthEnd],
  };
  const statusGroup = STATUS_GROUPS.find((g) => g.key === statusFilter);
  const range = RANGE[period];
  const filtered = rows
    .filter((r) => {
      const d = vnDate(r.slot_start);
      if (range && (d < range[0] || d > range[1])) return false;
      if (
        statusGroup &&
        statusGroup.statuses.length &&
        !statusGroup.statuses.includes(r.status)
      )
        return false;
      return true;
    })
    .sort((a, b) => a.slot_start.localeCompare(b.slot_start));

  return (
    <>
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
      {/* LỊCH theo NGÀY (thay 4 cột trạng thái): Ngày · Giờ · BN · Dịch vụ · Bác
          sĩ · Trạng thái. Lọc KỲ + TRẠNG THÁI; bấm dòng → panel chi tiết bên phải. */}
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={
                "rounded-full px-3 py-1 text-xs font-medium transition-colors " +
                (period === p.key
                  ? "bg-brand-600 text-white"
                  : "border border-brand-100 bg-surface text-brand-800 hover:bg-brand-50")
              }
            >
              {p.label}
            </button>
          ))}
          <span className="px-0.5 text-line-strong">·</span>
          {STATUS_GROUPS.map((g) => (
            <button
              key={g.key}
              onClick={() => setStatusFilter(g.key)}
              className={
                "rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors " +
                (statusFilter === g.key
                  ? "bg-brand-800 text-white"
                  : "border border-brand-100 bg-surface text-brand-800 hover:bg-brand-50")
              }
            >
              {g.label}
            </button>
          ))}
        </div>

        {/* Khung kéo co dãn + cuộn: bảng co thì CUỘN, không vỡ cấu trúc. */}
        <div className="max-h-[80vh] min-h-[200px] max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
          <table className="w-full min-w-max border-collapse text-xs">
            <thead className="sticky top-0 z-10 bg-brand-100 text-left text-label font-semibold uppercase tracking-wide text-brand-800">
              <tr>
                <th className="border-b border-hairline px-2 py-1.5 min-w-24">Ngày</th>
                <th className="border-b border-hairline px-2 py-1.5 min-w-15">Giờ</th>
                <th className="border-b border-hairline px-2 py-1.5 min-w-45">Bệnh nhân</th>
                <th className="border-b border-hairline px-2 py-1.5 min-w-30">Dịch vụ</th>
                <th className="border-b border-hairline px-2 py-1.5 min-w-28">Bác sĩ</th>
                <th className="border-b border-brand-100 px-2 py-1.5 min-w-[110px]">Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-xs text-ink-faint">
                    Không có lịch trong kỳ / trạng thái đã chọn.
                  </td>
                </tr>
              ) : (
                filtered.map((a, i) => {
                  const d = vnDate(a.slot_start);
                  const newDay = i === 0 || vnDate(filtered[i - 1].slot_start) !== d;
                  const active = selId === a.id;
                  return (
                    <tr
                      key={a.id}
                      onClick={() => select(a)}
                      className={
                        "cursor-pointer border-b border-brand-100 " +
                        (active
                          ? "bg-brand-100"
                          : (i % 2 ? "bg-brand-50" : "bg-surface") +
                            " hover:bg-brand-50")
                      }
                    >
                      <td className="px-2 py-1.5 whitespace-nowrap font-medium text-brand-800">
                        {newDay ? `${dayLabel(d)} · ${fmtDayMonth(d)}` : ""}
                      </td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-ink">
                        {fmtTimeOrNone(a.slot_start)}
                      </td>
                      <td className="px-2 py-1.5 text-ink">
                        <span className="block">{a.patient?.full_name ?? "—"}</span>
                        <span className="block font-mono text-label text-ink-muted">
                          {a.patient?.patient_code}
                          {a.patient?.phone_primary ? ` · ${a.patient.phone_primary}` : ""}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 text-ink-soft">
                        {a.service?.name ?? "—"}
                      </td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-ink-soft">
                        {a.doctor?.full_name ?? "—"}
                      </td>
                      <td className="px-2 py-1.5">
                        <StatusBadge status={a.status} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Panel chi tiết — BÊN CẠNH bảng (ngang); mobile thì xuống dưới */}
      {sel && (
        <aside className="w-full shrink-0 overflow-y-auto rounded-card border border-brand-100 bg-brand-50 p-4 shadow-card lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:w-[360px]">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-status-cancelled">
              Thông tin khách hàng
            </h3>
            <button
              onClick={close}
              aria-label="Đóng"
              className="rounded-md p-1 text-status-cancelled hover:bg-surface-sunken"
            >
              <X size={16} />
            </button>
          </div>

          {!editing ? (
            <>
              <dl className="space-y-1.5 text-sm">
                <Row label="Họ tên" value={sel.patient?.full_name} />
                <Row label="Ngày sinh" value={sel.patient?.date_of_birth} />
                <Row label="Giới tính" value={sel.patient?.gender} />
                <Row label="SĐT chính" value={sel.patient?.phone_primary} />
                <Row label="SĐT người nhà" value={sel.patient?.phone_secondary} />
                <Row label="Dân tộc" value={sel.patient?.ethnicity} />
                <Row label="Quốc tịch" value={sel.patient?.nationality} />
                <Row label="Nghề nghiệp" value={sel.patient?.occupation} />
                <Row label="Đối tượng" value={sel.patient?.patient_objection} />
                <Row label="Địa chỉ" value={sel.patient?.address} />
                <Row label="Cơ sở" value={locName(sel.patient?.location_id ?? null)} />
                <Row
                  label="Lịch hẹn"
                  value={`${fmtTimeOrNone(sel.slot_start)} · ${sel.service?.name ?? "—"}`}
                />
                <Row label="Bác sĩ" value={sel.doctor?.full_name} />
                {sel.status === "CANCELLED" &&
                  (sel.ly_do_huy_ma || sel.cancellation_reason) && (
                  <Row
                    label="Lý do hủy"
                    value={
                      [nhanLyDoHuy(sel.ly_do_huy_ma), sel.cancellation_reason]
                        .filter(Boolean)
                        .join(" — ") || "—"
                    }
                  />
                )}
                <div className="flex gap-2 pt-0.5">
                  <dt className="w-28 shrink-0 text-ink-muted">Trạng thái</dt>
                  <dd>
                    <StatusBadge status={sel.status} />
                  </dd>
                </div>
              </dl>

              {error && <p className="mt-2 text-xs text-danger">{error}</p>}

              <div className="mt-4 flex flex-wrap gap-2">
                {sel.status === "SCHEDULED" && (
                  <button
                    onClick={confirm}
                    disabled={busy}
                    className="inline-flex min-h-10 items-center gap-1 rounded-control bg-success px-4 text-sm font-semibold text-white hover:bg-success disabled:opacity-50"
                  >
                    <Check size={15} /> Xác nhận
                  </button>
                )}
                <button
                  onClick={startEdit}
                  disabled={busy}
                  className="inline-flex min-h-10 items-center gap-1 rounded-control border border-line bg-surface px-4 text-sm font-medium text-ink-soft hover:bg-surface-sunken disabled:opacity-50"
                >
                  <Pencil size={14} />
                  {sel.status === "SCHEDULED" ? "Không xác nhận / Sửa" : "Sửa"}
                </button>

                {/* Đổi lịch (CSKH/QL) — theo yêu cầu khách, lịch còn "sống" */}
                {canManage && LIVE.includes(sel.status) && (
                  <button
                    onClick={() => {
                      setShowResched((v) => !v);
                      setShowCancel(false);
                    }}
                    disabled={busy}
                    className="inline-flex min-h-10 items-center gap-1 rounded-control border border-status-assigned bg-surface px-4 text-sm font-medium text-status-assigned hover:bg-status-assigned-bg disabled:opacity-50"
                  >
                    <CalendarClock size={14} /> Đổi lịch
                  </button>
                )}

                {/* Hủy lịch (CSKH/QL) — lịch còn "sống" */}
                {canManage && LIVE.includes(sel.status) && (
                  <button
                    onClick={() => {
                      setShowCancel((v) => !v);
                      setShowResched(false);
                    }}
                    disabled={busy}
                    className="inline-flex min-h-10 items-center gap-1 rounded-control border border-danger bg-surface px-4 text-sm font-medium text-danger hover:bg-danger-bg disabled:opacity-50"
                  >
                    <Ban size={14} /> Hủy lịch
                  </button>
                )}
              </div>

              {/* Form lý do hủy (ẩn/hiện) */}
              {canManage && showCancel && LIVE.includes(sel.status) && (
                <div className="mt-3 space-y-2 rounded-control border border-danger bg-surface p-3">
                  {/* Cùng danh mục với màn Quản lý khách hàng — một nguồn ở
                      lib/ly-do-huy.ts, có bài kiểm chống lệch với backend.
                      Chép tay lần thứ hai là hai màn gọi cùng một lần huỷ bằng
                      hai tên. */}
                  <label className={LABEL}>Lý do hủy</label>
                  <select
                    className={INPUT}
                    value={maLyDo}
                    onChange={(e) => setMaLyDo(e.target.value)}
                  >
                    <option value="">— Chọn lý do —</option>
                    {LY_DO_HUY_THU_TU.map((ma) => (
                      <option key={ma} value={ma}>
                        {LY_DO_HUY[ma]}
                      </option>
                    ))}
                  </select>
                  {maLyDo === "KHAC" && (
                    <input
                      className={INPUT}
                      value={cancelReason}
                      onChange={(e) => setCancelReason(e.target.value)}
                      placeholder="Khách nói gì?"
                    />
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={cancelAppt}
                      disabled={
                        busy || !maLyDo || (maLyDo === "KHAC" && !cancelReason.trim())
                      }
                      className="min-h-10 rounded-control bg-danger px-4 text-sm font-semibold text-white hover:bg-danger disabled:opacity-50"
                    >
                      {busy ? "Đang hủy…" : "Xác nhận hủy"}
                    </button>
                    <button
                      onClick={() => setShowCancel(false)}
                      className="min-h-10 rounded-control border border-line bg-surface px-4 text-sm text-ink-soft hover:bg-surface-sunken"
                    >
                      Thôi
                    </button>
                  </div>
                </div>
              )}

              {/* Đổi lịch (CSKH/QL) — đổi ngày/giờ (+ tuỳ chọn bác sĩ) */}
              {canManage && showResched && LIVE.includes(sel.status) && (
                <div className="mt-3 space-y-2 rounded-control border border-status-assigned bg-surface p-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className={LABEL}>Ngày mới</label>
                      <input
                        type="date"
                        min={todayVn()}
                        className={INPUT}
                        value={reschedDate}
                        onChange={(e) => setReschedDate(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className={LABEL}>Giờ mới</label>
                      <Time24Input
                        value={reschedTime}
                        onChange={setReschedTime}
                        minHour={rMinHour}
                        maxHour={rMaxHour}
                      />
                    </div>
                  </div>
                  <div>
                    <label className={LABEL}>Bác sĩ (tuỳ chọn)</label>
                    <div className="relative">
                      <input
                        value={reschedDocQ}
                        onChange={(e) => {
                          setReschedDocQ(e.target.value);
                          setReschedDoc(""); // xóa chọn cũ khi gõ đè
                          setReschedDocOpen(true);
                        }}
                        onFocus={() => setReschedDocOpen(true)}
                        onBlur={() => setTimeout(() => setReschedDocOpen(false), 150)}
                        placeholder="Tìm bác sĩ… (bỏ trống để giữ hiện tại)"
                        className={INPUT}
                        autoComplete="off"
                      />
                      {reschedDocOpen && (
                        <ul className="absolute z-30 mt-1 max-h-52 w-full overflow-auto rounded-control border border-line bg-surface shadow-panel">
                          <li
                            onMouseDown={() => {
                              setReschedDoc("");
                              setReschedDocQ("");
                              setReschedDocOpen(false);
                            }}
                            className="cursor-pointer px-3 py-2 text-sm text-ink-muted hover:bg-brand-50"
                          >
                            — Giữ bác sĩ hiện tại —
                          </li>
                          {filteredDoctors.length === 0 ? (
                            <li className="px-3 py-2 text-sm text-ink-faint">
                              Không tìm thấy bác sĩ
                            </li>
                          ) : (
                            filteredDoctors.map((d) => (
                              <li
                                key={d.id}
                                onMouseDown={() => {
                                  setReschedDoc(d.id);
                                  setReschedDocQ(d.label);
                                  setReschedDocOpen(false);
                                }}
                                className={
                                  "cursor-pointer px-3 py-2 text-sm hover:bg-brand-50 " +
                                  (d.id === reschedDoc
                                    ? "bg-brand-100 font-medium text-brand-800"
                                    : "text-ink")
                                }
                              >
                                {d.label}
                              </li>
                            ))
                          )}
                        </ul>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={reschedule}
                    disabled={busy}
                    className="inline-flex min-h-10 items-center gap-1 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    <CalendarClock size={14} /> {busy ? "Đang đổi…" : "Xác nhận đổi lịch"}
                  </button>
                </div>
              )}
            </>
          ) : (
            form && (
              <div className="space-y-2">
                <div>
                  <label className={LABEL}>Họ tên</label>
                  <input
                    className={INPUT}
                    value={form.full_name}
                    onChange={(e) => set("full_name", e.target.value)}
                  />
                </div>
                <div>
                  <label className={LABEL}>Ngày sinh</label>
                  <input
                    type="date"
                    className={INPUT}
                    value={form.date_of_birth}
                    onChange={(e) => set("date_of_birth", e.target.value)}
                  />
                </div>
                <div>
                  <label className={LABEL}>SĐT chính</label>
                  <input
                    className={INPUT}
                    inputMode="numeric"
                    maxLength={10}
                    placeholder="10 chữ số"
                    value={form.phone_primary}
                    onChange={(e) => set("phone_primary", digitsOnly(e.target.value).slice(0, 10))}
                  />
                </div>
                <div>
                  <label className={LABEL}>SĐT người nhà</label>
                  <input
                    className={INPUT}
                    inputMode="numeric"
                    maxLength={10}
                    placeholder="10 chữ số"
                    value={form.phone_secondary}
                    onChange={(e) => set("phone_secondary", digitsOnly(e.target.value).slice(0, 10))}
                  />
                </div>
                <div>
                  <label className={LABEL}>Cơ sở</label>
                  <select
                    className={INPUT}
                    value={form.location_id}
                    onChange={(e) => set("location_id", e.target.value)}
                  >
                    {locations.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={LABEL}>Giới tính</label>
                  <select
                    className={INPUT}
                    value={form.gender}
                    onChange={(e) => set("gender", e.target.value)}
                  >
                    <option value="">— Chọn —</option>
                    <option value="Nữ">Nữ</option>
                    <option value="Nam">Nam</option>
                    <option value="Khác">Khác</option>
                  </select>
                </div>
                <div>
                  <label className={LABEL}>Dân tộc</label>
                  <input
                    className={INPUT}
                    value={form.ethnicity}
                    onChange={(e) => set("ethnicity", e.target.value)}
                  />
                </div>
                <div>
                  <label className={LABEL}>Quốc tịch</label>
                  <input
                    className={INPUT}
                    value={form.nationality}
                    onChange={(e) => set("nationality", e.target.value)}
                  />
                </div>
                <div>
                  <label className={LABEL}>Nghề nghiệp</label>
                  <input
                    className={INPUT}
                    value={form.occupation}
                    onChange={(e) => set("occupation", e.target.value)}
                  />
                </div>
                <div>
                  <label className={LABEL}>Đối tượng</label>
                  <input
                    className={INPUT}
                    value={form.patient_objection}
                    onChange={(e) => set("patient_objection", e.target.value)}
                    placeholder="DV / BHYT / ..."
                  />
                </div>
                <div>
                  <label className={LABEL}>Địa chỉ</label>
                  <input
                    className={INPUT}
                    value={form.address}
                    onChange={(e) => set("address", e.target.value)}
                    placeholder="Số nhà, đường, phường/xã, tỉnh/thành"
                  />
                </div>
                {error && <p className="text-xs text-danger">{error}</p>}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={save}
                    disabled={busy}
                    className="min-h-10 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    {busy ? "Đang lưu..." : "Lưu thông tin"}
                  </button>
                  <button
                    onClick={() => setEditing(false)}
                    disabled={busy}
                    className="min-h-10 rounded-control border border-line bg-surface px-4 text-sm text-ink-soft hover:bg-surface-sunken"
                  >
                    Huỷ
                  </button>
                </div>
              </div>
            )
          )}
        </aside>
      )}
    </div>
    </>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex gap-2">
      <dt className="w-28 shrink-0 text-ink-muted">{label}</dt>
      <dd className="min-w-0 break-words text-ink">{value || "—"}</dd>
    </div>
  );
}
