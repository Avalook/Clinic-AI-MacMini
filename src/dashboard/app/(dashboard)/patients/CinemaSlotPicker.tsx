"use client";

// Lưới đặt chỗ kiểu "rạp chiếu phim" dùng chung cho CSKH + Lễ tân: mỗi bác sĩ
// TRỰC CA hôm đó là 1 nhóm 3 HÀNG — BN1 + BN2 (chỗ đặt hẹn kênh thường) và
// hàng thứ 3 màu XANH "đặt vào đây" dành riêng khách vãng lai (WALK_IN); mỗi
// cột = 1 khung 15 phút trong giờ mở cửa PK. Luật 2+1 nằm ở lib/slot-capacity
// (server chặn cứng, đây là hiển thị đồng bộ).
//   mode="regular" (CSKH/QL/Trưởng ca đặt hẹn): bấm được BN1/BN2; hàng Ưu tiên
//     (chỗ 3, xanh) chỉ bấm được khi allowPriority=true (đặt như WALK_IN).
//   mode="walkin"  (Lễ tân xếp khách vãng lai): chỉ bấm được hàng xanh.
// dutyDoctorIds lọc bác sĩ trực (từ Lịch làm việc); ngày chưa phân trực →
// fallback hiện tất cả + dòng ghi chú. KHÔNG tự fetch/POST — parent truyền
// data + nhận callback như trước.

import { useMemo } from "react";
import { vnLocalToUtcISO, nowMs, slotRange } from "../../../lib/datetime";
import { clinicHoursForDate } from "../../../lib/roster";
import {
  buildSlotUsage,
  usageAt,
  REGULAR_CAP,
  type SlotApptLite,
} from "../../../lib/slot-capacity";
import type { Option } from "./AppointmentBooking";

// Cùng bộ phút với Time24Input của màn đặt lịch.
const MINUTES = ["00", "15", "30", "45"];

export type PickerMode = "regular" | "walkin";

export default function CinemaSlotPicker({
  date,
  doctors,
  dutyDoctorIds,
  existingAppts,
  selectedDoctorId,
  selectedTime,
  mode = "regular",
  allowPriority = false,
  selectedKind,
  onPick,
}: {
  date: string;
  doctors: Option[];
  /** Bác sĩ trực ca ngày này (từ work_roster LICH_KHAM). null/undefined = chưa
   *  nạp xong (hiện tất cả, không ghi chú); mảng RỖNG = ngày chưa phân trực
   *  (fallback tất cả + ghi chú). */
  dutyDoctorIds?: string[] | null;
  existingAppts: SlotApptLite[];
  selectedDoctorId: string;
  selectedTime: string;
  mode?: PickerMode;
  /** regular-mode: cho bấm CẢ hàng Ưu tiên (chỗ thứ 3), không chỉ BN1/BN2.
   *  Mặc định false → giữ nguyên hành vi cũ (AppointmentBooking không đổi). */
  allowPriority?: boolean;
  /** Loại ghế đang chọn — để tô "đang chọn" ĐÚNG hàng khi cả 2 loại bấm được.
   *  Bỏ trống → suy theo mode (walkin→"walkin", còn lại→"regular"). */
  selectedKind?: "regular" | "walkin";
  onPick: (doctorId: string, hhmm: string, kind: "regular" | "walkin") => void;
}) {
  // Các cột giờ (HH:mm) nằm trong giờ mở cửa của NGÀY đã chọn.
  const slots = useMemo(() => {
    if (!date) return [] as string[];
    const ch = clinicHoursForDate(date);
    if (!ch) return [] as string[];
    const minHour = Number(ch.open.slice(0, 2));
    const maxHour = Number(ch.close.slice(0, 2)); // giờ đóng cửa = mốc loại trừ
    const out: string[] = [];
    for (let h = minHour; h < maxHour; h++) {
      for (const m of MINUTES) {
        out.push(`${String(h).padStart(2, "0")}:${m}`);
      }
    }
    return out;
  }, [date]);

  // Bảng chiếm chỗ (bác sĩ × khung 15'): đếm riêng kênh thường vs vãng lai.
  const usage = useMemo(() => buildSlotUsage(existingAppts), [existingAppts]);

  // Lọc bác sĩ theo ca trực; ngày chưa phân trực → hiện tất cả + ghi chú.
  const noDuty = Array.isArray(dutyDoctorIds) && dutyDoctorIds.length === 0;
  const dutyDoctors = useMemo(() => {
    if (!dutyDoctorIds || dutyDoctorIds.length === 0) return doctors;
    const set = new Set(dutyDoctorIds);
    const filtered = doctors.filter((d) => set.has(d.id));
    // Lịch trực trỏ tới staff không còn trong combobox → đừng để bảng rỗng.
    return filtered.length > 0 ? filtered : doctors;
  }, [doctors, dutyDoctorIds]);

  if (!date) {
    return (
      <p className="rounded-lg border border-line bg-gray-50 px-3 py-2 text-sm text-ink-muted">
        Chọn ngày khám để hiện sơ đồ chỗ trống.
      </p>
    );
  }
  if (slots.length === 0) {
    return (
      <p className="rounded-lg border border-line bg-gray-50 px-3 py-2 text-sm text-ink-muted">
        Ngày này phòng khám không có khung giờ mở cửa.
      </p>
    );
  }

  // LUÔN thêm hàng "Chưa phân bác sĩ": lịch online chưa phân BS vẫn phải hiện
  // "đã kín", và vẫn bị luật 2+1 giới hạn như một hàng riêng.
  const rows: Option[] = [...dutyDoctors, { id: "", label: "Chưa phân bác sĩ" }];
  const now = nowMs();
  const walkinMode = mode === "walkin";
  const effSelectedKind = selectedKind ?? (walkinMode ? "walkin" : "regular");

  // 3 hàng con của mỗi bác sĩ: BN1, BN2 (kênh thường) + Ưu tiên (chỗ thứ 3, xanh —
  // lưu như WALK_IN để vào đúng ghế; trước gọi "Vãng lai").
  const SUBROWS: { kind: "regular" | "walkin"; label: string; seatIdx: number }[] = [
    { kind: "regular", label: "BN1", seatIdx: 0 },
    { kind: "regular", label: "BN2", seatIdx: 1 },
    { kind: "walkin", label: "Ưu tiên", seatIdx: 0 },
  ];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-muted">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded border border-brand-100 bg-white" />{" "}
          Chỗ hẹn trống (BN1/BN2)
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded border border-success-bg bg-success-bg" />{" "}
          Chỗ Ưu tiên trống
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded bg-brand-800" /> Đang chọn
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded bg-line" /> Đã kín / quá giờ
        </span>
      </div>
      {noDuty && (
        <p className="rounded-lg border border-[#fde68a] bg-[#fffbeb] px-3 py-1.5 text-[11px] text-warning">
          Ngày này chưa có lịch trực bác sĩ (Lịch làm việc) — đang hiện tất cả bác sĩ.
        </p>
      )}
      <div className="overflow-x-auto rounded-xl border border-brand-100">
        <table className="border-separate border-spacing-x-1 border-spacing-y-0.5 p-2">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-white px-2 text-left text-[11px] font-medium text-ink-muted">
                Bác sĩ
              </th>
              <th className="sticky left-[110px] z-10 bg-white px-1 text-left text-[10px] font-normal text-ink-faint">
                Chỗ
              </th>
              {slots.map((t) => (
                <th
                  key={t}
                  className="whitespace-nowrap px-0.5 text-[10px] font-normal text-ink-faint"
                >
                  {slotRange(t)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((d) =>
              SUBROWS.map((sub, si) => (
                <tr key={`${d.id || "none"}-${sub.kind}-${sub.seatIdx}`}>
                  {si === 0 && (
                    <td
                      rowSpan={SUBROWS.length}
                      className="sticky left-0 z-10 whitespace-nowrap bg-white px-2 align-middle text-xs font-medium text-ink"
                    >
                      {d.label}
                    </td>
                  )}
                  <td
                    className={
                      "sticky left-[110px] z-10 whitespace-nowrap bg-white px-1 text-[10px] " +
                      (sub.kind === "walkin" ? "text-success" : "text-ink-faint")
                    }
                  >
                    {sub.label}
                  </td>
                  {slots.map((t) => {
                    let iso = "";
                    try {
                      iso = vnLocalToUtcISO(date, t);
                    } catch {
                      iso = "";
                    }
                    const bucketMs = iso ? Date.parse(iso) : 0;
                    const isPast = iso ? bucketMs < now : false;
                    const u = iso
                      ? usageAt(usage, d.id || null, bucketMs)
                      : { regular: 0, walkin: 0 };
                    // Ghế này đã có người? BN1 kín khi regular ≥ 1, BN2 khi ≥ 2…
                    const isTaken =
                      sub.kind === "regular"
                        ? u.regular > sub.seatIdx
                        : u.walkin > sub.seatIdx;
                    // Hàng được phép bấm: walkin-mode → chỉ hàng Ưu tiên;
                    // regular-mode → BN1/BN2, và CẢ hàng Ưu tiên nếu allowPriority.
                    const pickable = walkinMode
                      ? sub.kind === "walkin"
                      : sub.kind === "regular" || allowPriority;
                    // Ô "đang chọn" vẽ trên ghế TRỐNG ĐẦU TIÊN của hàng đúng loại,
                    // và chỉ ở hàng ĐÚNG loại đang chọn (tránh tô nhầm cả BN lẫn Ưu tiên).
                    const firstFreeSeat =
                      sub.kind === "regular" ? u.regular : u.walkin;
                    const isSelected =
                      pickable &&
                      sub.kind === effSelectedKind &&
                      d.id === selectedDoctorId &&
                      t === selectedTime &&
                      !isTaken &&
                      sub.seatIdx === Math.min(firstFreeSeat, REGULAR_CAP - 1);
                    const disabled = isPast || isTaken || !pickable;
                    const title = `${d.label} · ${slotRange(t)} · ${
                      sub.kind === "walkin" ? "chỗ Ưu tiên" : sub.label
                    }${
                      isTaken
                        ? " · đã kín"
                        : isPast
                          ? " · đã qua"
                          : !pickable
                            ? walkinMode
                              ? " · chỗ đặt hẹn (CSKH đặt)"
                              : " · chỗ Ưu tiên (chỉ xem)"
                            : " · đặt vào đây"
                    }`;
                    const cls =
                      "h-6 w-full min-w-[3.75rem] rounded text-[10px] font-medium transition " +
                      (isSelected
                        ? "bg-brand-800 text-white"
                        : isPast || isTaken
                          ? "cursor-not-allowed bg-line text-ink-faint"
                          : sub.kind === "walkin"
                            ? pickable
                              ? "border border-[#86efac] bg-success-bg text-success hover:bg-success-bg"
                              : "cursor-not-allowed border border-[#d1fae5] bg-success-bg text-[#86efac]"
                            : pickable
                              ? "border border-brand-100 bg-white text-brand-800 hover:bg-brand-100"
                              : "cursor-not-allowed border border-[#f4e4ee] bg-brand-50 text-[#e3c1d6]");
                    return (
                      <td key={t} className="p-0">
                        <button
                          type="button"
                          disabled={disabled}
                          onClick={() => onPick(d.id, t, sub.kind)}
                          title={title}
                          className={cls}
                        >
                          {isSelected ? "✓" : isTaken ? "×" : ""}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
