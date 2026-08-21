"use client";

// Ô chọn GIỜ 24h (HH:MM) — 2 dropdown: Giờ (00–23) + Phút (00,05,…,55). Thay cho
// <input type="time"> vì native hiển thị AM/PM theo locale máy (không ép 24h được).
// value = "HH:MM" hoặc ""; onChange trả "HH:MM" (phần chưa chọn mặc định "00").

import { useRef } from "react";
import { Clock } from "lucide-react";
import { INPUT } from "./form-ui";

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
const MINUTES = Array.from({ length: 12 }, (_, i) => String(i * 5).padStart(2, "0"));

export default function Time24Input({
  value,
  onChange,
  minHour = 0,
  maxHour = 23,
  minutesOptions,
  khungPhut,
}: {
  value: string;
  onChange: (v: string) => void;
  /** Giới hạn giờ theo giờ mở cửa PK (vd T2–T6 chỉ 17–22). */
  minHour?: number;
  maxHour?: number;
  minutesOptions?: string[];
  /**
   * Khung GIỜ NHẬN LỊCH của ngày đó: [[phútĐầu, phútCuối), …].
   *
   * `minHour`/`maxHour` chỉ cắt được HAI ĐẦU ngày — chúng không nói được
   * "nghỉ trưa 13:00–14:00", nên ô này vẫn mời 13:00 trong khi backend từ chối
   * (21/08/2026). Khung rỗng/không truyền = "chưa biết" ⇒ không lọc gì.
   */
  khungPhut?: [number, number][];
}) {
  const [h, m] = value ? value.split(":") : ["", ""];
  const phutHopLe = (phut: number) =>
    !khungPhut ||
    khungPhut.length === 0 ||
    khungPhut.some(([lo, hi]) => phut >= lo && phut < hi);
  const phutCoThe = minutesOptions ?? MINUTES;
  const hours = HOURS.filter((x) => {
    const n = Number(x);
    if (n < minHour || n > maxHour) return false;
    // Giờ nào KHÔNG còn phút hợp lệ nào thì bỏ hẳn khỏi dropdown — để lại một
    // lựa chọn mà mọi phút đều bị chặn là mời người dùng vào ngõ cụt.
    return phutCoThe.some((mm) => phutHopLe(n * 60 + Number(mm)));
  });
  const phutHienRa = phutCoThe.filter(
    (mm) => h === "" || phutHopLe(Number(h) * 60 + Number(mm)),
  );
  const emit = (nh: string, nm: string) =>
    onChange(!nh && !nm ? "" : `${nh || String(minHour).padStart(2, "0")}:${nm || "00"}`);
  // Icon đồng hồ → MỞ DROPDOWN GIỜ 24h (showPicker trên <select>). KHÔNG dùng
  // input type=time native vì native hiện AM/PM theo locale máy (không ép 24h được).
  const hourRef = useRef<HTMLSelectElement>(null);
  const openPicker = () => {
    try {
      hourRef.current?.showPicker?.();
    } catch {
      /* trình duyệt cũ không hỗ trợ showPicker — bỏ qua, vẫn bấm dropdown được */
    }
  };
  return (
    <div className="flex items-center gap-2">
      <select
        ref={hourRef}
        value={h ?? ""}
        onChange={(e) => emit(e.target.value, m ?? "")}
        className={INPUT}
        aria-label="Giờ (24h)"
      >
        <option value="">Giờ</option>
        {hours.map((x) => (
          <option key={x} value={x}>
            {x}
          </option>
        ))}
      </select>
      <span className="shrink-0 text-ink-faint">:</span>
      <select
        value={m ?? ""}
        onChange={(e) => emit(h ?? "", e.target.value)}
        className={INPUT}
        aria-label="Phút"
      >
        <option value="">Phút</option>
        {phutHienRa.map((x) => (
          <option key={x} value={x}>
            {x}
          </option>
        ))}
      </select>
      {/* Icon đồng hồ → mở dropdown giờ 24h (không AM/PM). */}
      <button
        type="button"
        onClick={openPicker}
        aria-label="Mở bảng chọn giờ"
        className="shrink-0 rounded-lg border border-line bg-white p-2 text-ink-muted hover:bg-surface-sunken"
      >
        <Clock size={16} />
      </button>
    </div>
  );
}
