"use client";

// Lưới đặt chỗ kiểu "rạp chiếu phim" dùng chung cho CSKH + Lễ tân: mỗi bác sĩ
// TRỰC CA hôm đó là 1 nhóm 3 HÀNG — BN1 + BN2 (chỗ đặt hẹn kênh thường) và
// hàng thứ 3 màu XANH "đặt vào đây" dành riêng khách vãng lai (WALK_IN); mỗi
// cột = 1 khung 15 phút trong giờ mở cửa PK. Luật 2+1 nằm ở lib/slot-capacity
// (server chặn cứng, đây là hiển thị đồng bộ).
//   mode="regular" (CSKH/QL/Trưởng ca đặt hẹn): bấm được BN1/BN2; hàng Đến
//     trực tiếp (xanh) chỉ bấm được khi choChonGheTrucTiep=true (lưu WALK_IN).
//   mode="walkin"  (Lễ tân xếp khách vãng lai): chỉ bấm được hàng xanh.
// dutyDoctorIds lọc bác sĩ trực (từ Lịch làm việc); ngày chưa phân trực →
// fallback hiện tất cả + dòng ghi chú. KHÔNG tự fetch/POST — parent truyền
// data + nhận callback như trước.

import { useMemo } from "react";
import { vnLocalToUtcISO, nowMs, slotRange } from "../../../lib/datetime";
import { clinicHoursForDate } from "../../../lib/roster";
import { trongKhungNhanLich } from "../../../lib/khung-nhan-lich";
import {
  buildSlotUsage,
  usageAt,
  type SlotApptLite,
  type SlotUsage,
} from "../../../lib/slot-capacity";
import { useBookingPolicy } from "../BookingPolicyContext";
import type { Option } from "./AppointmentBooking";

const EMPTY_USAGE = new Map<string, SlotUsage>();

/** Phút này có nằm trong ca trực không.
 *
 *  Nửa mở `[lo, hi)` — cùng quy ước với mọi khoảng phút khác trong hệ thống,
 *  và cùng quy ước với `covers()` bên backend. Một khung bắt đầu đúng 12:00
 *  thuộc ca CHIỀU, không thuộc ca SÁNG.
 */
function trongCa(windows: [number, number][] | undefined, phut: number): boolean {
  // Không biết ca của người này ⇒ không chặn. Xem ghi chú ở prop shiftWindows.
  if (!windows || windows.length === 0) return true;
  return windows.some(([lo, hi]) => phut >= lo && phut < hi);
}

export type PickerMode = "regular" | "walkin";

export default function CinemaSlotPicker({
  date,
  doctors,
  dutyDoctorIds,
  dutyDuKien = false,
  existingAppts,
  selectedDoctorId,
  selectedTime,
  mode = "regular",
  choChonGheTrucTiep = false,
  selectedKind,
  shiftWindows,
  onPick,
}: {
  date: string;
  doctors: Option[];
  /** Bác sĩ trực ca ngày này (từ work_roster LICH_KHAM). null/undefined = chưa
   *  nạp xong (hiện tất cả, không ghi chú); mảng RỖNG = ngày chưa phân trực
   *  (fallback tất cả + ghi chú). */
  dutyDoctorIds?: string[] | null;
  /** Tuần chứa ngày này chưa được quản lý bấm "Áp dụng tuần". Bác sĩ bên dưới
   *  vẫn là người đã được xếp thật, chỉ là chưa chốt nên giờ còn đổi. */
  dutyDuKien?: boolean;
  existingAppts: SlotApptLite[];
  selectedDoctorId: string;
  selectedTime: string;
  mode?: PickerMode;
  /** regular-mode: cho bấm CẢ hàng Đến trực tiếp, không chỉ BN1/BN2.
   *  Mặc định false → giữ nguyên hành vi cũ (AppointmentBooking không đổi). */
  choChonGheTrucTiep?: boolean;
  /** Loại ghế đang chọn — để tô "đang chọn" ĐÚNG hàng khi cả 2 loại bấm được.
   *  Bỏ trống → suy theo mode (walkin→"walkin", còn lại→"regular"). */
  selectedKind?: "regular" | "walkin";
  /** Khoảng PHÚT trong ngày mà mỗi bác sĩ thật sự trực, theo staff_id.
   *
   *  LẤY TỪ BACKEND (`/appointments/quote?doctor_id=…` → `shift_windows`),
   *  KHÔNG TỰ TÍNH. Ca SÁNG/CHIỀU chỉ là ba cái nhãn; chúng thành khoảng giờ
   *  bằng một luật duy nhất trong `core/shifts.py` (mốc 12:00 là quyết định
   *  của phòng khám, và nó nằm ở đúng một hằng số). Tính lại ở đây là dựng bản
   *  thứ hai của luật ấy, và bản thứ hai sẽ lệch vào ngày phòng khám đổi mốc.
   *
   *  `undefined` hoặc thiếu bác sĩ = chưa biết ⇒ KHÔNG chặn gì. Chặn dựa trên
   *  một điều chưa biết là khoá lịch của người đang thật sự đi làm — sai theo
   *  hướng đó tệ hơn hẳn. */
  shiftWindows?: Record<string, [number, number][]>;
  onPick: (doctorId: string, hhmm: string, kind: "regular" | "walkin") => void;
}) {
  // Luật của phòng khám đang đăng nhập — CÙNG một hàng clinic.settings mà
  // trigger enforce_slot_capacity đọc khi từ chối. `null` = chưa đọc được.
  const policy = useBookingPolicy();

  // Các cột giờ (HH:mm) nằm trong giờ mở cửa của NGÀY đã chọn.
  const slots = useMemo(() => {
    if (!date || !policy) return [] as string[];
    const ch = clinicHoursForDate(date, policy.hours);
    if (!ch) return [] as string[];
    const minHour = Number(ch.open.slice(0, 2));
    const maxHour = Number(ch.close.slice(0, 2)); // giờ đóng cửa = mốc loại trừ
    // GIỜ MỞ CỬA KHÔNG PHẢI GIỜ NHẬN LỊCH. Cửa mở 07:00–22:00 nhưng ba ca chỉ
    // phủ 08:00–21:30; ba khoảng còn lại — trước ca sáng, nghỉ trưa, sau ca tối
    // — backend TỪ CHỐI (21/08/2026). Mời rồi mới mắng là cách chắc nhất khiến
    // người trực mất niềm tin vào lưới, nên bỏ hẳn cột khỏi bảng.
    const weekday = new Date(`${date}T00:00:00`).getDay();
    const out: string[] = [];
    for (let h = minHour; h < maxHour; h++) {
      // Backend chỉ nhận độ dài khung chia hết 60' nên vòng này luôn kết thúc
      // đúng đầu giờ sau — không có cột nào tràn sang giờ kế tiếp.
      for (let m = 0; m < 60; m += policy.slotMinutes) {
        if (!trongKhungNhanLich(policy.khungNhanLich, weekday, h * 60 + m)) {
          continue;
        }
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
    // Nếu đã chọn bác sĩ cụ thể từ dropdown → chỉ hiện bác sĩ đó trong lưới.
    if (selectedDoctorId) {
      const picked = doctors.find((d) => d.id === selectedDoctorId);
      if (picked) return [picked];
    }
    // NGÀY CHƯA XẾP TRỰC THÌ KHÔNG BÀY TÊN BÁC SĨ NÀO.
    //
    // Quang 09/08/2026: *"chưa có phân bác sĩ thì hiện ra các ông bác sĩ làm
    // gì. rồi không chọn được đúng chứ?"*. Đúng — bản cũ trả về TOÀN BỘ danh
    // sách cho một ngày chưa ai được xếp ca, tức mời người dùng chọn một cái
    // tên không có cơ sở, rồi backend từ chối.
    //
    // `null` = CHƯA hỏi xong (khác `[]` = hỏi rồi, ngày này trống): lúc chưa
    // biết thì giữ nguyên danh sách, đừng nháy bảng.
    if (dutyDoctorIds == null) return doctors;
    if (dutyDoctorIds.length === 0) return [];
    const set = new Set(dutyDoctorIds);
    const filtered = doctors.filter((d) => set.has(d.id));
    // Lịch trực trỏ tới staff không còn trong combobox → đừng để bảng rỗng.
    return filtered.length > 0 ? filtered : doctors;
  }, [doctors, dutyDoctorIds, selectedDoctorId]);

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

  // Hàng \"Chưa phân bác sĩ\" chỉ cần khi CHƯA chọn bác sĩ cụ thể — lịch online
  // chưa phân BS vẫn phải hiện \"đã kín\" và bị giới hạn chỗ như một hàng riêng.
  // MỘT NGÀY CHỈ CÓ MỘT TRONG HAI HÌNH.
  //
  // Quang 09/08/2026: *"những ngày có lịch bác sĩ thì đương nhiên phải hiện ra
  // những lịch của bác sĩ ấy ở dạng bảng đó rồi, bỏ cái chưa phân bác sĩ là
  // được"* — và ngày chưa xếp trực thì *"vẫn sẽ hiện cái khung giờ ra… chỉ ghi
  // là chưa phân bác sĩ"*.
  //
  // Nên: có bác sĩ trực → CHỈ các bác sĩ ấy, KHÔNG kèm hàng "Chưa phân bác sĩ"
  // (bày cả hai là hỏi một câu đã có câu trả lời). Chưa xếp trực → ĐÚNG MỘT
  // hàng, và hàng ấy nói luôn phải làm gì tiếp.
  const rows: Option[] =
    dutyDoctors.length > 0
      ? dutyDoctors
      : [
          {
            id: "",
            label:
              "Chưa phân bác sĩ — chọn trước khung giờ để quản lý sắp xếp",
          },
        ];
  const now = nowMs();
  const walkinMode = mode === "walkin";
  const effSelectedKind = selectedKind ?? (walkinMode ? "walkin" : "regular");

  // Hàng con của mỗi bác sĩ: regularCap hàng "BN…" (đặt trước) + walkinCap
  // hàng "Đến trực tiếp" (lưu như WALK_IN).
  //
  // HÀNG NÀY TỪNG MANG NHÃN "ƯU TIÊN" — sai, và sai theo kiểu tốn tiền.
  // Vãng lai là NGƯỜI ĐẾN TRỰC TIẾP không báo trước (Quang, 08/08/2026): có thể
  // là khách mới tinh, có thể là khách cũ. Không liên quan gì tới "người quen
  // của bác sĩ". Gọi nó là "Ưu tiên" khiến CSKH xếp người quen vào đó, và khi
  // một khách thật bước vào quầy thì hết chỗ.
  //
  // Tệ hơn kể từ 07/08: khách CÓ HẸN đến muộn cũng chiếm một ghế vãng lai
  // (20260807000001). Nên ghế ấy vốn đã chật, không phải chỗ để dành cho ai.
  //
  // Ưu tiên là khái niệm CHƯA XÂY (Quang: "bỏ ưu tiên đi đã").
  const SUBROWS: { kind: "regular" | "walkin"; label: string; seatIdx: number }[] = [
    ...Array.from({ length: policy.regularCap }, (_, i) => ({
      kind: "regular" as const,
      label: `BN${i + 1}`,
      seatIdx: i,
    })),
    ...Array.from({ length: policy.walkinCap }, (_, i) => ({
      kind: "walkin" as const,
      label: policy.walkinCap > 1 ? `Trực tiếp ${i + 1}` : "Trực tiếp",
      seatIdx: i,
    })),
  ];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-label text-ink-muted">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded border border-brand-100 bg-white" />{" "}
          Chỗ hẹn trống ({policy.regularCap} chỗ/khung)
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded border border-success-bg bg-success-bg" />{" "}
          Chỗ đến trực tiếp còn trống
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded bg-brand-800" /> Đang chọn
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded bg-line" /> Đã kín / quá giờ
        </span>
      </div>
      {/* Câu cũ nói "đang hiện tất cả bác sĩ" — đúng với hành vi cũ, và hành vi
          ấy chính là thứ vừa bỏ. Nay ngày chưa xếp trực chỉ còn một hàng "Chưa
          phân bác sĩ", nên câu này phải nói đúng chuyện đang xảy ra. */}
      {noDuty && (
        <p className="rounded-lg border border-warning/30 bg-warning-bg px-3 py-1.5 text-label text-warning">
          Ngày này chưa xếp lịch trực bác sĩ. Cứ chọn khung giờ — quản lý sẽ xếp
          bác sĩ sau, ở màn Lịch làm việc.
        </p>
      )}
      {/* CÓ BÁC SĨ NHƯNG TUẦN CHƯA CHỐT — nói ra, đừng giấu người đã được xếp.
          Trước 10/08/2026 `/api/roster?date=` trả danh sách RỖNG cho mọi ngày
          thuộc một tuần chưa bấm "Áp dụng tuần", kể cả ngày đã có bác sĩ duyệt
          hẳn hoi. Nên màn Lịch làm việc của quản lý hiện "TS.BS. Phan Chí
          Thành" ngày 10/09 trong khi lưới đặt lịch cùng ngày nói "chưa xếp lịch
          trực" — hai màn đọc một bảng, nói hai điều ngược nhau, và CSKH đặt vào
          hàng "chưa phân bác sĩ" cho một ngày đã có người. */}
      {!noDuty && dutyDuKien && (
        <p className="rounded-lg border border-warning/30 bg-warning-bg px-3 py-1.5 text-label text-warning">
          Quản lý chưa bấm “Áp dụng tuần” cho tuần này — giờ trực bên dưới là dự
          kiến và còn có thể đổi. Đặt vẫn được; gọi xác nhận lại với khách sau
          khi tuần được chốt.
        </p>
      )}
      <div className="overflow-x-auto rounded-xl border border-brand-100">
        <table className="border-separate border-spacing-x-1 border-spacing-y-0.5 p-2">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-white px-2 text-left text-label font-medium text-ink-muted">
                Bác sĩ
              </th>
              <th className="sticky left-[110px] z-10 bg-white px-1 text-left text-label font-normal text-ink-faint">
                Chỗ
              </th>
              {slots.map((t) => (
                <th
                  key={t}
                  className="whitespace-nowrap px-0.5 text-label font-normal text-ink-faint"
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
                      "sticky left-[110px] z-10 whitespace-nowrap bg-white px-1 text-label " +
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
                    // NGOÀI CA TRỰC — luật cao hơn cả sức chứa.
                    //
                    // Lưới này trước đây chỉ lọc "bác sĩ nào CÓ ca hôm đó", rồi
                    // vẽ đủ mọi cột 07:00→23:00. Nên một bác sĩ chỉ trực CHIỀU
                    // vẫn được mời đặt lúc 07:00 — bấm được, tô xanh, rồi máy
                    // chủ từ chối: *"chỉ trực 12:00–23:00, không có mặt lúc
                    // 07:00"*. Hồ sơ bệnh nhân đã kịp tạo, chỉ lịch hẹn hỏng.
                    //
                    // Lưới bên màn Đặt lịch vốn đã làm đúng ("Ngoài ca trực").
                    // Hai lưới cùng một việc mà biết hai thứ khác nhau là chỗ
                    // lỗi này sinh ra.
                    const [gio, phut] = t.split(":");
                    const phutTrongNgay = Number(gio) * 60 + Number(phut);
                    const ngoaiCa = !trongCa(shiftWindows?.[d.id], phutTrongNgay);
                    const u = iso
                      ? usageAt(usage, d.id || null, bucketMs)
                      : { regular: 0, walkin: 0 };
                    // Ghế này đã có người? BN1 kín khi regular ≥ 1, BN2 khi ≥ 2…
                    const isTaken =
                      sub.kind === "regular"
                        ? u.regular > sub.seatIdx
                        : u.walkin > sub.seatIdx;
                    // Hàng được phép bấm: walkin-mode → chỉ hàng Đến trực tiếp;
                    // regular-mode → BN1/BN2, và cả hàng ấy nếu được cho phép.
                    const pickable = walkinMode
                      ? sub.kind === "walkin"
                      : sub.kind === "regular" || choChonGheTrucTiep;
                    // Ô "đang chọn" vẽ trên ghế TRỐNG ĐẦU TIÊN của hàng đúng loại,
                    // và chỉ ở hàng ĐÚNG loại đang chọn (tránh tô nhầm cả hai hàng).
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
                    const disabled = isPast || isTaken || !pickable || ngoaiCa;
                    const title = `${d.label} · ${slotRange(t, policy.slotMinutes)} · ${
                      sub.kind === "walkin" ? "chỗ đến trực tiếp" : sub.label
                    }${
                      ngoaiCa
                        ? " · ngoài ca trực của bác sĩ này"
                        : isTaken
                          ? " · đã kín"
                          : isPast
                            ? " · đã qua"
                          : !pickable
                            ? walkinMode
                              ? " · chỗ đặt hẹn (CSKH đặt)"
                              : " · chỗ đến trực tiếp (chỉ xem)"
                            : " · đặt vào đây"
                    }`;
                    const cls =
                      "h-6 w-full min-w-[3.75rem] rounded text-label font-medium transition " +
                      (isSelected
                        ? "bg-brand-800 text-white"
                        : ngoaiCa
                          ? "cursor-not-allowed border border-dashed border-line bg-surface-muted text-ink-faint"
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
