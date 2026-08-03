"use client";

// Điều chỉnh khung giờ & số ca khám theo Bác sĩ / Ngày / Khung giờ (C.4 UI).
// Sử dụng chuẩn form-ui (INPUT, LABEL, BTN, CARD).

import { useState } from "react";
import { VN_TZ } from "../../../lib/datetime";
import { useRouter } from "next/navigation";
import { INPUT, LABEL, BTN, BTN_GHOST, CARD, TBL_WRAP, TBL_HEAD, TBL_ROW } from "../form-ui";
import { User, Clock, CheckCircle2, AlertCircle } from "lucide-react";
import type {
  BookingPolicy,
  StandingRule,
  TempException,
} from "../../../lib/booking-policy";

export interface DoctorOpt {
  id: string;
  name: string;
}

const WEEKDAY_LABEL = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

function hhmm(minuteOfDay: number): string {
  const h = Math.floor(minuteOfDay / 60);
  const m = minuteOfDay % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function toMinutes(value: string): number {
  const [h, m] = value.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

export default function OverridePolicyCard({
  doctors,
  policy,
  standingRules,
  tempExceptions,
}: {
  doctors: DoctorOpt[];
  /** Luật đặt lịch của phòng khám — để nhãn khung giờ hiển thị đúng độ dài
   *  thực (clinic.settings.booking.slot_minutes) thay vì đoán 15 phút. */
  policy: BookingPolicy | null;
  /** Luật thường trực đang có hiệu lực. Không có danh sách này thì màn chỉ có
   *  ô nhập, và người dùng không thấy được thứ mình đang sửa. */
  standingRules: StandingRule[];
  /** Điều chỉnh tạm thời còn hạn — chúng ĐÈ LÊN luật thường trực, nên một
   *  ngoại lệ quên xoá làm luật vừa lưu trông như không chạy. */
  tempExceptions: TempException[];
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
  // Khung TỪ – ĐẾN. Mặc định 18:00–19:00 = trọn tiếng bận nhất của phòng khám.
  const [slotFrom, setSlotFrom] = useState<string>("18:00");
  const [slotTo, setSlotTo] = useState<string>("19:00");
  const [slotRegularCap, setSlotRegularCap] = useState<number>(5);
  const [slotWalkinCap, setSlotWalkinCap] = useState<number>(1);
  const [reason, setReason] = useState<string>("");

  // Form states - luật thường trực theo bác sĩ.
  //
  // KHUNG GIỜ, KHÔNG PHẢI MỘT CON SỐ CHO CẢ NGÀY. Bản trước chỉ có ô "số ca",
  // nên luật duy nhất viết được là "BS Thành, mọi khung, 9 ca" — trong khi luật
  // thật của phòng khám là 18:00 mười ca rồi 18:15 trở đi bốn ca. Và vì luật
  // cả-ngày phủ trọn 0–1440, lần lưu thứ hai luôn đụng luật cũ.
  const [docOverrideCap, setDocOverrideCap] = useState<number>(4);
  const [docWalkinCap, setDocWalkinCap] = useState<number>(1);
  const [docFrom, setDocFrom] = useState<string>("18:00");
  const [docTo, setDocTo] = useState<string>("18:15");
  const [docWeekday, setDocWeekday] = useState<string>("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const doctorName = new Map(doctors.map((d) => [d.id, d.name]));

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
    if (!policy) {
      setMsg({
        kind: "err",
        text: "Chưa đọc được luật đặt lịch — không xác định được độ dài khung.",
      });
      return;
    }
    setBusy(true);
    setMsg(null);

    // KHUNG TỪ – ĐẾN, nửa mở [từ, đến).
    //
    // Bản cũ gửi `hour_start = parseInt("18:15") = 18`, `hour_end = 19`: nó VỨT
    // BỎ PHÚT mà Trưởng ca vừa chọn, nên chọn 18:15 hay 18:45 đều tạo một luật
    // y hệt phủ trọn tiếng 18h. Không đặt được "18:00 nhận 10 ca, sau 18:15
    // nhận 4 ca", và mỗi lần thử lại sinh thêm một luật chồng lên luật cũ —
    // prod có ba dòng như vậy và luật nào thắng là ngẫu nhiên.
    //
    // Nửa mở, không phải nửa đóng: 18:00–19:00 phủ các khung 18:00, 18:15,
    // 18:30, 18:45 và DỪNG trước 19:00. Nếu bao gồm mốc cuối thì hai ngoại lệ
    // liền kề (18:00–19:00 và 19:00–20:00) sẽ đụng nhau ở đúng khung 19:00, và
    // ràng buộc EXCLUDE sẽ từ chối một thao tác hoàn toàn hợp lý.
    const minuteStart = toMinutes(slotFrom);
    // "24:00" không nhập được từ <input type="time">, nên 00:00 ở ô ĐẾN nghĩa là
    // hết ngày — chứ không phải một khung rỗng.
    const minuteEnd = slotTo === "00:00" ? 1440 : toMinutes(slotTo);

    if (minuteEnd <= minuteStart) {
      setBusy(false);
      setMsg({ kind: "err", text: "Giờ kết thúc phải sau giờ bắt đầu." });
      return;
    }

    try {
      const res = await fetch("/api/booking-overrides/slot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doctor_id: selectedDoctorId || null,
          date_start: fromDate,
          date_end: toDate,
          minute_start: minuteStart,
          minute_end: minuteEnd,
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
      const todayYmd = now.toLocaleDateString("en-CA", { timeZone: VN_TZ });

      // Hiện đúng khung người dùng vừa nhập. Trước đây chỗ này gọi
      // slotRange(mốc, độ_dài) và dán nhãn một khung đơn lên một ngoại lệ có thể
      // dài nhiều khung — nhãn nói một đằng, luật vừa ghi nói một nẻo.
      const displaySlot = `${slotFrom}–${slotTo}`;
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
    const minuteStart = toMinutes(docFrom);
    // "24:00" không nhập được từ <input type="time">, nên 00:00 ở ô ĐẾN nghĩa là
    // hết ngày — giống hệt quy ước ở tab khung giờ bên trên.
    const minuteEnd = docTo === "00:00" ? 1440 : toMinutes(docTo);
    if (minuteEnd <= minuteStart) {
      setMsg({ kind: "err", text: "Giờ kết thúc phải sau giờ bắt đầu." });
      return;
    }
    setBusy(true);
    setMsg(null);

    try {
      const res = await fetch("/api/booking-overrides/doctor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          // Để trống = luật cho MỌI bác sĩ. Bảng luật của phòng khám có cả hai
          // loại dòng ("BS Thành 18:00" và "các bác sĩ khác 18:00"), nên ô này
          // phải nói được cả hai.
          doctor_id: selectedDoctorId || null,
          weekday: docWeekday === "" ? null : Number(docWeekday),
          minute_start: minuteStart,
          minute_end: minuteEnd,
          regular_cap: docOverrideCap,
          walkin_cap: docWalkinCap,
          reason: reason || "Luật thường trực",
        }),
      });

      const data = (await res.json()) as {
        ok?: boolean;
        error?: string;
        replaced?: { action: string }[];
        shadowed_by?: { date_end: string }[];
      };
      setBusy(false);

      if (!res.ok || !data.ok) {
        setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
        return;
      }

      const who = selectedDoctorId
        ? (doctorName.get(selectedDoctorId) ?? "bác sĩ đã chọn")
        : "mọi bác sĩ";
      const when = docWeekday === "" ? "mọi ngày" : WEEKDAY_LABEL[Number(docWeekday)];
      // Luật cũ bị cắt là chuyện phải NÓI RA. Nó xảy ra mà không ai bấm nút
      // xoá, và bảng luật ngay bên dưới sẽ đổi theo — im lặng ở đây nghĩa là
      // người dùng phải tự phát hiện.
      const n = data.replaced?.length ?? 0;
      // "Đã lưu" mà lưới không đổi là cách nhanh nhất để người dùng kết luận
      // chức năng hỏng. Nếu còn một điều chỉnh tạm thời đè lên khung này thì
      // nói ngay, kèm ngày nó hết hạn.
      const shadow = data.shadowed_by ?? [];
      const shadowText =
        shadow.length > 0
          ? ` Lưu ý: khung này đang bị một điều chỉnh tạm thời đè lên (đến ${shadow
              .map((s) => s.date_end.split("-").reverse().join("/"))
              .join(", ")}) — xoá nó ở tab “Theo Khung giờ & Ngày” thì luật này mới có hiệu lực.`
          : "";
      setMsg({
        kind: "ok",
        text:
          `Đã áp dụng: ${who}, ${when}, khung ${docFrom}–${docTo} — ` +
          `${docOverrideCap} ca đặt trước, ${docWalkinCap} ca vãng lai.` +
          (n > 0 ? ` (${n} luật cũ phủ khung này đã được cắt lại.)` : "") +
          shadowText,
      });
      router.refresh();
    } catch {
      setBusy(false);
      setMsg({ kind: "err", text: "Không kết nối được máy chủ" });
    }
  }

  async function deleteOverride(kind: "doctor" | "slot", id: string) {
    setDeletingId(id);
    setMsg(null);
    try {
      const res = await fetch(`/api/booking-overrides/${kind}/${id}`, {
        method: "DELETE",
      });
      const data = (await res.json()) as { ok?: boolean; error?: string };
      setDeletingId(null);
      if (!res.ok || !data.ok) {
        setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
        return;
      }
      // Xoá KHÔNG để lại khoảng trống rỗng: khung đó rơi xuống tầng dưới. Nói
      // ra, vì "đã xoá" một mình dễ bị hiểu là khung ấy không còn đặt được.
      setMsg({
        kind: "ok",
        text:
          kind === "doctor"
            ? "Đã xoá luật. Khung giờ đó quay về số chỗ mặc định của phòng khám."
            : "Đã xoá điều chỉnh tạm thời. Khung giờ đó quay về luật thường trực.",
      });
      router.refresh();
    } catch {
      setDeletingId(null);
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

            {/* TỪ – ĐẾN, không phải một mốc.
                Bản trước chỉ có một ô giờ và ngoại lệ phủ đúng một khung, nên
                "18:00–19:30 nhận 5 ca" phải nhập thành sáu lần. Sáu lần nhập
                cho một ý định là sáu cơ hội nhập lệch nhau. */}
            <div>
              <label className={LABEL}>Từ giờ</label>
              <input
                type="time"
                step={300}
                value={slotFrom}
                onChange={(e) => setSlotFrom(e.target.value)}
                className={INPUT}
              />
            </div>

            <div>
              <label className={LABEL}>Đến giờ</label>
              <input
                type="time"
                step={300}
                value={slotTo}
                onChange={(e) => setSlotTo(e.target.value)}
                className={INPUT}
              />
              <p className="mt-1 text-xs text-ink-muted">
                Không bao gồm mốc cuối: 18:00–19:00 là các khung 18:00 tới 18:45.
              </p>
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

          {/* Ngoại lệ tạm thời ĐÈ LÊN luật thường trực. Không có danh sách này,
              một dòng quên xoá khiến mọi luật lưu sau đó trông như vô tác dụng
              — và không có màn nào trong hệ thống cho thấy nó tồn tại. */}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-ink">
              Điều chỉnh tạm thời còn hạn
            </h3>
            {tempExceptions.length === 0 ? (
              <p className="text-xs text-ink-muted">
                Không có — mọi khung đang chạy theo luật thường trực.
              </p>
            ) : (
              <div className={TBL_WRAP}>
                <table className="w-full text-sm">
                  <thead className={TBL_HEAD}>
                    <tr>
                      <th className="px-3 py-2 text-left">Bác sĩ</th>
                      <th className="px-3 py-2 text-left">Từ – đến ngày</th>
                      <th className="px-3 py-2 text-left">Khung giờ</th>
                      <th className="px-3 py-2 text-right">Đặt trước</th>
                      <th className="px-3 py-2 text-right">Vãng lai</th>
                      <th className="px-3 py-2 text-left">Lý do</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {tempExceptions.map((r) => (
                      <tr key={r.id} className={TBL_ROW}>
                        <td className="px-3 py-2">
                          {r.doctor_id
                            ? (doctorName.get(r.doctor_id) ?? "—")
                            : "Tất cả bác sĩ"}
                        </td>
                        <td className="px-3 py-2">
                          {r.date_start === r.date_end
                            ? r.date_start
                            : `${r.date_start} → ${r.date_end}`}
                        </td>
                        <td className="px-3 py-2">
                          {hhmm(r.minute_start)}–{hhmm(r.minute_end)}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {r.regular_cap ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {r.walkin_cap ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-ink-muted">{r.reason}</td>
                        <td className="px-3 py-2 text-right">
                          <button
                            type="button"
                            onClick={() => deleteOverride("slot", r.id)}
                            disabled={deletingId === r.id}
                            className={BTN_GHOST}
                          >
                            {deletingId === r.id ? "Đang xoá…" : "Xoá"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <p className="text-xs text-ink-muted">
            Luật <b>thường trực</b>: lặp lại mỗi ngày, không hết hạn. Lưu đè lên
            luật cũ phủ cùng khung — phần giờ không trùng vẫn giữ nguyên.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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

            <div>
              <label className={LABEL}>Áp dụng thứ</label>
              <select
                value={docWeekday}
                onChange={(e) => setDocWeekday(e.target.value)}
                className={INPUT}
              >
                <option value="">-- Mọi ngày --</option>
                {WEEKDAY_LABEL.map((w, i) => (
                  <option key={w} value={String(i)}>
                    {w}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className={LABEL}>Từ giờ</label>
              <input
                type="time"
                step={300}
                value={docFrom}
                onChange={(e) => setDocFrom(e.target.value)}
                className={INPUT}
              />
            </div>

            <div>
              <label className={LABEL}>Đến giờ</label>
              <input
                type="time"
                step={300}
                value={docTo}
                onChange={(e) => setDocTo(e.target.value)}
                className={INPUT}
              />
              <p className="mt-1 text-xs text-ink-muted">
                Không bao gồm mốc cuối: 18:00–18:15 là đúng một khung 18:00.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className={LABEL}>Số ca đặt trước / khung</label>
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
              <label className={LABEL}>Số ca vãng lai / khung</label>
              <input
                type="number"
                min={0}
                max={50}
                value={docWalkinCap}
                onChange={(e) => setDocWalkinCap(Number(e.target.value))}
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
              {busy ? "Đang lưu..." : "Lưu luật thường trực"}
            </button>
          </div>

          {/* Danh sách luật đang chạy. Đây là nửa còn lại của màn hình: không
              có nó, người dùng sửa một thứ mình không nhìn thấy. */}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-ink">
              Luật thường trực đang áp dụng
            </h3>
            {standingRules.length === 0 ? (
              <p className="text-xs text-ink-muted">
                Chưa có luật riêng — mọi khung dùng số chỗ mặc định của phòng khám
                ở thẻ trên.
              </p>
            ) : (
              <div className={TBL_WRAP}>
                <table className="w-full text-sm">
                  <thead className={TBL_HEAD}>
                    <tr>
                      <th className="px-3 py-2 text-left">Bác sĩ</th>
                      <th className="px-3 py-2 text-left">Thứ</th>
                      <th className="px-3 py-2 text-left">Khung giờ</th>
                      <th className="px-3 py-2 text-right">Đặt trước</th>
                      <th className="px-3 py-2 text-right">Vãng lai</th>
                      <th className="px-3 py-2 text-left">Lý do</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {standingRules.map((r) => (
                      <tr key={r.id} className={TBL_ROW}>
                        <td className="px-3 py-2">
                          {r.doctor_id
                            ? (doctorName.get(r.doctor_id) ?? "—")
                            : "Tất cả bác sĩ"}
                        </td>
                        <td className="px-3 py-2">
                          {r.weekday === null
                            ? "Mọi ngày"
                            : WEEKDAY_LABEL[r.weekday]}
                        </td>
                        <td className="px-3 py-2">
                          {r.minute_start === null || r.minute_end === null
                            ? "Cả ngày"
                            : `${hhmm(r.minute_start)}–${hhmm(r.minute_end)}`}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {r.regular_cap ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {r.walkin_cap ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-ink-muted">
                          {r.reason ?? ""}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <button
                            type="button"
                            onClick={() => deleteOverride("doctor", r.id)}
                            disabled={deletingId === r.id}
                            className={BTN_GHOST}
                          >
                            {deletingId === r.id ? "Đang xoá…" : "Xoá"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
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
