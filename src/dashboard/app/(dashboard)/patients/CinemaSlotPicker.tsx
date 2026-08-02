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
  type SlotApptLite,
  type SlotUsage,
} from "../../../lib/slot-capacity";
import { useBookingPolicy } from "../BookingPolicyContext";
import type { Option } from "./AppointmentBooking";

const EMPTY_USAGE = new Map<string, SlotUsage>();

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
  // Luật của phòng khám đang đăng nhập — CÙNG một hàng clinic.settings mà
  // trigger enforce_slot_capacity đọc khi từ chối. `null` = chưa đọc được.
  const policy = useBookingPolicy();

  // Các cột giờ (HH:mm) nằm trong giờ mở cửa của NGÀY đã chọn.
  const slots = useMemo(() => {
    if (!date || !policy) return [] as string[];
    const ch = clinicHoursForDate(date);
    if (!ch) return [] as string[];
    const minHour = Number(ch.open.slice(0, 2));
    const maxHour = Number(ch.close.slice(0, 2)); // giờ đóng cửa = mốc loại trừ
    const out: string[] = [];
    for (let h = minHour; h < maxHour; h++) {
      // Backend chỉ nhận độ dài khung chia hết 60' nên vòng này luôn kết thúc
      // đúng đầu giờ sau — không có cột nào tràn sang giờ kế tiếp.
      for (let m = 0; m < 60; m += policy.slotMinutes) {
        out.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
      }
    }
    return out;
  }, [date, policy]);

  // Bảng chiếm chỗ (bác sĩ × khung): đếm riêng kênh thường vs vãng lai.
  const usage = useMemo(
    () => (policy ? buildSlotUsage(existingAppts, policy) : EMPTY_USAGE),
    [existingAppts, policy],
  );

  // Lọc bác sĩ theo ca trực; ngày chưa phân trực → hiện tất cả + ghi chú.
  const noDuty = Array.isArray(dutyDoctorIds) && dutyDoctorIds.length === 0;
  const dutyDoctors = useMemo(() => {
    if (!dutyDoctorIds || dutyDoctorIds.length === 0) return doctors;
    const set = new Set(dutyDoctorIds);
    const filtered = doctors.filter((d) => set.has(d.id));
    // Lịch trực trỏ tới staff không còn trong combobox → đừng để bảng rỗng.
    return filtered.length > 0 ? filtered : doctors;
  }, [doctors, dutyDoctorIds]);

  // Không đoán 15 phút / 2+1: vẽ lưới sai luật thì lễ tân bấm vào ô mà server
  // sẽ từ chối, và không hiểu vì sao. Thà nói thẳng là chưa đọc được.
  if (!policy) {
    return (
      <p className="rounded-lg border border-danger-bg bg-danger-bg px-3 py-2 text-sm text-danger">
        Chưa đọc được luật đặt lịch của phòng khám (độ dài khung, số chỗ) — chưa
        hiện được sơ đồ. Thử tải lại trang; còn lỗi thì báo kỹ thuật.
      </p>
    );
  }
  if (!date) {
    return (
      <p className="rounded-lg border border-line bg-surface-muted px-3 py-2 text-sm text-ink-muted">
        Chọn ngày khám để hiện sơ đồ chỗ trống.
      </p>
    );
  }
  if (slots.length === 0) {
    return (
      <p className="rounded-lg border border-line bg-surface-muted px-3 py-2 text-sm text-ink-muted">
        Ngày này phòng khám không có khung giờ mở cửa.
      </p>
    );
  }

  // LUÔN thêm hàng "Chưa phân bác sĩ": lịch online chưa phân BS vẫn phải hiện
  // "đã kín", và vẫn bị giới hạn chỗ như một hàng riêng.
  const rows: Option[] = [...dutyDoctors, { id: "", label: "Chưa phân bác sĩ" }];
  const now = nowMs();
  const walkinMode = mode === "walkin";
  const effSelectedKind = selectedKind ?? (walkinMode ? "walkin" : "regular");

  // Hàng con của mỗi bác sĩ: regularCap hàng "BN…" (kênh thường) + walkinCap
  // hàng "Ưu tiên" (lưu như WALK_IN để vào đúng ghế; trước gọi "Vãng lai").
  // Ở Dr4Women 2+1 nên vẫn là BN1/BN2/Ưu tiên như cũ; phòng khám khác cấu hình
  // khác thì lưới mọc/co theo, không cần deploy lại.
  const SUBROWS: { kind: "regular" | "walkin"; label: string; seatIdx: number }[] = [
    ...Array.from({ length: policy.regularCap }, (_, i) => ({
      kind: "regular" as const,
      label: `BN${i + 1}`,
      seatIdx: i,
    })),
    ...Array.from({ length: policy.walkinCap }, (_, i) => ({
      kind: "walkin" as const,
      label: policy.walkinCap > 1 ? `Ưu tiên ${i + 1}` : "Ưu tiên",
      seatIdx: i,
    })),
  ];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-muted">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded border border-brand-100 bg-white" />{" "}
          Chỗ hẹn trống ({policy.regularCap} chỗ/khung)
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
        <p className="rounded-lg border border-warning/30 bg-warning-bg px-3 py-1.5 text-[11px] text-warning">
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
                  {slotRange(t, policy.slotMinutes)}
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
                      sub.seatIdx ===
                        Math.min(
                          firstFreeSeat,
                          (sub.kind === "regular"
                            ? policy.regularCap
                            : policy.walkinCap) - 1,
                        );
                    const disabled = isPast || isTaken || !pickable;
                    const title = `${d.label} · ${slotRange(t, policy.slotMinutes)} · ${
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
                              ? "border border-success bg-success-bg text-success hover:bg-success-bg"
                              : "cursor-not-allowed border border-success-bg bg-success-bg text-success/70"
                            : pickable
                              ? "border border-brand-100 bg-white text-brand-800 hover:bg-brand-100"
                              : "cursor-not-allowed border border-line bg-surface-muted text-ink-faint");
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
