"use client";

// Điều chỉnh khung giờ & số ca khám theo Bác sĩ / Ngày / Khung giờ (C.4 UI).
// Sử dụng chuẩn form-ui (INPUT, LABEL, BTN, CARD).

import { useState } from "react";
import { useRouter } from "next/navigation";
import { INPUT, LABEL, BTN, BTN_GHOST, CARD, TBL_WRAP, TBL_HEAD, TBL_ROW } from "../form-ui";
import { Calendar, User, Clock, CheckCircle2, AlertCircle } from "lucide-react";
import { slotRange } from "../../../lib/datetime";
import type { BookingPolicy } from "../../../lib/booking-policy";

export interface DoctorOpt {
  id: string;
  name: string;
}

export default function OverridePolicyCard({
  doctors,
  policy,
}: {
  doctors: DoctorOpt[];
  /** Luật đặt lịch của phòng khám — để nhãn khung giờ hiển thị đúng độ dài
   *  thực (clinic.settings.booking.slot_minutes) thay vì đoán 15 phút. */
  policy: BookingPolicy | null;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<"doctor" | "slot">("slot");

  // Form states - Slot Override
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("");
  const [dateRangeMode, setDateRangeMode] = useState<"today" | "week" | "month" | "custom">("today");
  const [fromDate, setFromDate] = useState<string>(
    new Date().toISOString().split("T")[0],
  );
  const [toDate, setToDate] = useState<string>(
    new Date().toISOString().split("T")[0],
  );
  const [slotTime, setSlotTime] = useState<string>("18:00");
  const [slotRegularCap, setSlotRegularCap] = useState<number>(5);
  const [slotWalkinCap, setSlotWalkinCap] = useState<number>(1);
  const [reason, setReason] = useState<string>("");

  // Form states - Doctor Capacity Override
  const [docOverrideCap, setDocOverrideCap] = useState<number>(4);

  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  // Quick preset helper
  function applyPreset(mode: "today" | "week" | "month" | "custom") {
    setDateRangeMode(mode);
    const now = new Date();
    const todayStr = now.toISOString().split("T")[0];

    if (mode === "today") {
      setFromDate(todayStr);
      setToDate(todayStr);
    } else if (mode === "week") {
      const dayOfWeek = now.getDay() || 7;
      const monday = new Date(now);
      monday.setDate(now.getDate() - dayOfWeek + 1);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      setFromDate(monday.toISOString().split("T")[0]);
      setToDate(sunday.toISOString().split("T")[0]);
    } else if (mode === "month") {
      const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
      const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
      setFromDate(firstDay.toISOString().split("T")[0]);
      setToDate(lastDay.toISOString().split("T")[0]);
    }
  }

  async function saveSlotOverride() {
    if (!fromDate || !toDate) {
      setMsg({ kind: "err", text: "Vui lòng chọn từ ngày và đến ngày." });
      return;
    }
    setBusy(true);
    setMsg(null);

    try {
      const res = await fetch("/api/booking-overrides/slot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doctor_id: selectedDoctorId || null,
          date_start: fromDate,
          date_end: toDate,
          hour_start: parseInt(slotTime.split(":")[0], 10),
          hour_end: parseInt(slotTime.split(":")[0], 10) + 1,
          regular_cap: slotRegularCap,
          walkin_cap: slotWalkinCap,
          reason: reason || "Điều chỉnh khung giờ",
        }),
      });

      const data = (await res.json()) as { ok?: boolean; error?: string };
      setBusy(false);

      if (!res.ok || !data.ok) {
        setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
        return;
      }

      const [y1, m1, d1] = fromDate.split("-").map(Number);
      const [y2, m2, d2] = toDate.split("-").map(Number);
      const now = new Date();
      const todayYmd = now.toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" });

      const displaySlot = slotRange(slotTime, policy?.slotMinutes ?? 15);
      let successText = "";
      if (fromDate === toDate) {
        const fullDateStr = `Ngày ${d1} tháng ${m1} năm ${y1}`;
        if (fromDate === todayYmd) {
          successText = `Đã áp dụng điều chỉnh ${slotRegularCap} khách đặt online và ${slotWalkinCap} ca khách đến trực tiếp cho khung ${displaySlot} ngày hôm nay (${fullDateStr}).`;
        } else {
          successText = `Đã áp dụng điều chỉnh ${slotRegularCap} khách đặt online và ${slotWalkinCap} ca khách đến trực tiếp cho khung ${displaySlot} (${fullDateStr}).`;
        }
      } else {
        const d1Formatted = `${String(d1).padStart(2, "0")}/${String(m1).padStart(2, "0")}/${y1}`;
        const d2Formatted = `${String(d2).padStart(2, "0")}/${String(m2).padStart(2, "0")}/${y2}`;
        successText = `Đã áp dụng điều chỉnh ${slotRegularCap} khách đặt online và ${slotWalkinCap} ca khách đến trực tiếp cho khung ${displaySlot} từ ngày ${d1Formatted} đến ngày ${d2Formatted}.`;
      }

      setMsg({
        kind: "ok",
        text: successText,
      });
      router.refresh();
    } catch {
      setBusy(false);
      setMsg({ kind: "err", text: "Không kết nối được máy chủ" });
    }
  }

  async function saveDoctorOverride() {
    if (!selectedDoctorId) {
      setMsg({ kind: "err", text: "Vui lòng chọn bác sĩ." });
      return;
    }
    setBusy(true);
    setMsg(null);

    try {
      const res = await fetch("/api/booking-overrides/doctor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doctor_id: selectedDoctorId,
          regular_cap: docOverrideCap,
          reason: reason || "Điều chỉnh công suất bác sĩ",
        }),
      });

      const data = (await res.json()) as { ok?: boolean; error?: string };
      setBusy(false);

      if (!res.ok || !data.ok) {
        setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
        return;
      }

      setMsg({
        kind: "ok",
        text: `Đã điều chỉnh công suất riêng cho bác sĩ (${docOverrideCap} ca/khung).`,
      });
      router.refresh();
    } catch {
      setBusy(false);
      setMsg({ kind: "err", text: "Không kết nối được máy chủ" });
    }
  }

  return (
    <div className={CARD}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
        <div>
          <h2 className="text-base font-semibold text-ink">
            Điều chỉnh khung giờ & số ca khám theo Bác sĩ
          </h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            Tùy chỉnh số ca khám riêng cho từng bác sĩ hoặc từng khung giờ cụ thể (VD: 18:00 - 18:15 tăng lên 5 ca).
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex rounded-lg border border-line bg-surface-muted p-1 text-xs">
          <button
            type="button"
            onClick={() => setTab("slot")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-colors ${
              tab === "slot"
                ? "bg-white text-ink shadow-sm"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            <Clock size={14} />
            Theo Khung giờ & Ngày
          </button>
          <button
            type="button"
            onClick={() => setTab("doctor")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-colors ${
              tab === "doctor"
                ? "bg-white text-ink shadow-sm"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            <User size={14} />
            Theo Bác sĩ
          </button>
        </div>
      </div>

      {tab === "slot" ? (
        <div className="mt-4 space-y-4">
          {/* Preset Buttons */}
          <div>
            <label className={LABEL}>Phạm vi áp dụng</label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => applyPreset("today")}
                className={dateRangeMode === "today" ? BTN : BTN_GHOST}
              >
                Hôm nay
              </button>
              <button
                type="button"
                onClick={() => applyPreset("week")}
                className={dateRangeMode === "week" ? BTN : BTN_GHOST}
              >
                Tuần này
              </button>
              <button
                type="button"
                onClick={() => applyPreset("month")}
                className={dateRangeMode === "month" ? BTN : BTN_GHOST}
              >
                Tháng này
              </button>
              <button
                type="button"
                onClick={() => applyPreset("custom")}
                className={dateRangeMode === "custom" ? BTN : BTN_GHOST}
              >
                Tùy chọn ngày
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className={LABEL}>Từ ngày</label>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => {
                  setDateRangeMode("custom");
                  setFromDate(e.target.value);
                }}
                className={INPUT}
              />
            </div>

            <div>
              <label className={LABEL}>Đến ngày</label>
              <input
                type="date"
                value={toDate}
                onChange={(e) => {
                  setDateRangeMode("custom");
                  setToDate(e.target.value);
                }}
                className={INPUT}
              />
            </div>

            <div>
              <label className={LABEL}>Khung giờ cụ thể</label>
              <input
                type="time"
                value={slotTime}
                onChange={(e) => setSlotTime(e.target.value)}
                className={INPUT}
              />
            </div>

            <div>
              <label className={LABEL}>Bác sĩ (để trống = tất cả)</label>
              <select
                value={selectedDoctorId}
                onChange={(e) => setSelectedDoctorId(e.target.value)}
                className={INPUT}
              >
                <option value="">-- Tất cả bác sĩ --</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className={LABEL}>Số ca đặt trước (Hẹn)</label>
              <input
                type="number"
                min={1}
                max={50}
                value={slotRegularCap}
                onChange={(e) => setSlotRegularCap(Number(e.target.value))}
                className={INPUT}
              />
            </div>

            <div>
              <label className={LABEL}>Số ca vãng lai</label>
              <input
                type="number"
                min={0}
                max={50}
                value={slotWalkinCap}
                onChange={(e) => setSlotWalkinCap(Number(e.target.value))}
                className={INPUT}
              />
            </div>

            <div>
              <label className={LABEL}>Ghi chú / Lý do</label>
              <input
                type="text"
                placeholder="VD: BS khám tăng cường giờ cao điểm"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className={INPUT}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button onClick={saveSlotOverride} disabled={busy} className={BTN}>
              {busy ? "Đang áp dụng..." : "Áp dụng điều chỉnh khung giờ"}
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className={LABEL}>Chọn Bác sĩ</label>
              <select
                value={selectedDoctorId}
                onChange={(e) => setSelectedDoctorId(e.target.value)}
                className={INPUT}
              >
                <option value="">-- Chọn bác sĩ --</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className={LABEL}>Số ca / khung giờ riêng</label>
              <input
                type="number"
                min={1}
                max={50}
                value={docOverrideCap}
                onChange={(e) => setDocOverrideCap(Number(e.target.value))}
                className={INPUT}
              />
            </div>

            <div>
              <label className={LABEL}>Ghi chú / Lý do</label>
              <input
                type="text"
                placeholder="VD: BS khám nhanh / kinh nghiệm lâu năm"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className={INPUT}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button onClick={saveDoctorOverride} disabled={busy} className={BTN}>
              {busy ? "Đang lưu..." : "Lưu điều chỉnh theo bác sĩ"}
            </button>
          </div>
        </div>
      )}

      {msg && (
        <div
          className={`mt-4 flex items-center gap-2 rounded-lg p-3 text-sm ${
            msg.kind === "ok"
              ? "bg-success-bg text-success"
              : "bg-danger-bg text-danger"
          }`}
        >
          {msg.kind === "ok" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          <span>{msg.text}</span>
        </div>
      )}
    </div>
  );
}
