"use client";

// Trình bày THUẦN (đọc data đã có) cho board "Trạng thái BN buổi khám" của Lễ tân:
//   - ProgressStepper: thanh tiến trình ngang map visit.status qua các mốc.
//   - WaitClock: chip đếm thời gian chờ kể từ check-in, ĐỔI MÀU theo ngưỡng.
// KHÔNG ghi DB, KHÔNG đụng enum/visit.status — chỉ render từ props.

import { useEffect, useState } from "react";
import { Check } from "lucide-react";

// ── Ngưỡng đổi màu đồng hồ chờ (PHÚT kể từ check-in) — cấu hình DUY NHẤT ở đây ──
const WAIT_GREEN_MAX = 10; // < 10p  → xanh
const WAIT_YELLOW_MAX = 20; // 10–20p → vàng;  > 20p → đỏ

// Thanh tiến trình kiểu Grab — 3 MỐC: Đang khám → Khám xong → Đã thanh toán.
// "Đến mốc nào tích xanh mốc ấy" (reached) suy từ visit.status + appointment.status:
//   • Đang khám      → visit IN_PROGRESS (BN đã vào khám).
//   • Khám xong      → appointment COMPLETED (bác sĩ "Lưu & Khám xong"). LƯU Ý:
//     dashboard KHÔNG tự set visit.FINALIZED, nên "khám xong" PHẢI đọc từ
//     appointment, không phải visit — nếu không mốc này không bao giờ xanh.
//   • Đã thanh toán  → bảng payment: khi mọi khâu PHẢI thu (dịch vụ + thuốc nếu có
//     đơn) đã có dòng PAID → `paid=true` → tích xanh. Chưa thu xong thì hiện "đang
//     tới" (nhấn pulse) chờ thu ngân.
const MILESTONES: { key: string; label: string }[] = [
  { key: "dang_kham", label: "Đang khám" },
  { key: "kham_xong", label: "Khám xong" },
  { key: "thanh_toan", label: "Đã thanh toán" },
];

// Số mốc đã đạt (tích xanh). OPEN=0 (chờ khám), IN_PROGRESS=1, khám xong=2,
// đã thanh toán=3 (paid từ bảng payment — thu ngân chốt đủ khâu).
export function reachedCount(
  visitStatus: string,
  apptStatus: string | null,
  paid: boolean,
): number {
  const done =
    apptStatus === "COMPLETED" ||
    visitStatus === "FINALIZED" ||
    visitStatus === "AMENDED";
  if (paid && done) return 3; // chỉ tích thanh toán khi đã khám xong
  if (done) return 2; // khám xong
  // Khám dở: dừng ở mốc "đang khám", KHÔNG tích "khám xong".
  //
  // Không có nhánh này thì INCOMPLETE rơi xuống `return 0` và thanh tiến trình
  // lùi về "mới check-in" cho một người đã đi được nửa buổi — trông như hệ
  // thống quên mất họ.
  if (visitStatus === "IN_PROGRESS" || visitStatus === "INCOMPLETE") return 1;
  return 0; // OPEN — mới check-in, đang chờ khám
}

export function ProgressStepper({
  visitStatus,
  apptStatus,
  paid = false,
}: {
  visitStatus: string;
  apptStatus: string | null;
  paid?: boolean;
}) {
  const reached = reachedCount(visitStatus, apptStatus, paid);

  return (
    <div className="flex items-start">
      {MILESTONES.map((m, i) => {
        let state: "done" | "current" | "upcoming";
        if (i < reached) state = "done";
        else if (i === reached) state = "current";
        else state = "upcoming";

        // Node tròn kiểu Grab: done = xanh đặc + ✓; current = viền nhấn (pulse);
        // upcoming = viền nhạt.
        const node =
          state === "done"
            ? "bg-success border-success text-white"
            : state === "current"
              ? "bg-white border-brand-600 ring-4 ring-brand-600/15 animate-pulse motion-reduce:animate-none"
              : "bg-white border-line";
        const txt =
          state === "done"
            ? "text-success font-medium"
            : state === "current"
              ? "text-brand-600 font-semibold"
              : "text-ink-faint";

        return (
          <div key={m.key} className="flex flex-1 items-start">
            <div
              className="flex w-full min-w-0 flex-col items-center gap-1"
              title={m.label}
            >
              <div className="flex w-full items-center">
                {/* nửa đoạn nối TRÁI (ẩn ở mốc đầu) — xanh khi mốc trước đã done */}
                <span
                  className={`h-0.5 flex-1 ${i === 0 ? "opacity-0" : i <= reached ? "bg-success" : "bg-line"}`}
                />
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${node}`}
                >
                  {state === "done" ? (
                    <Check size={13} strokeWidth={3} />
                  ) : state === "current" ? (
                    <span className="h-2 w-2 rounded-full bg-brand-600" />
                  ) : null}
                </span>
                {/* nửa đoạn nối PHẢI (ẩn ở mốc cuối) — xanh khi mốc này đã done */}
                <span
                  className={`h-0.5 flex-1 ${i === MILESTONES.length - 1 ? "opacity-0" : i < reached ? "bg-success" : "bg-line"}`}
                />
              </div>
              <span className={`whitespace-nowrap text-[11px] leading-none ${txt}`}>
                {m.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function WaitClock({
  checkedInAt,
  active,
}: {
  /** visit.checked_in_at — mốc bắt đầu đếm. */
  checkedInAt: string | null;
  /** Chỉ đếm khi BN đang chờ/đang khám (OPEN/IN_PROGRESS). Đã xong → ngừng. */
  active: boolean;
}) {
  // null cho tới khi mount ở client → tránh hydration mismatch (server không có "now").
  const [nowMs, setNowMs] = useState<number | null>(null);

  useEffect(() => {
    if (!checkedInAt || !active) return;
    const tick = () => setNowMs(Date.now());
    // tick đầu qua setTimeout(0) (callback, không phải thân effect) để tránh
    // setState đồng bộ trong effect; interval lo các tick sau.
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id); // cleanup khi unmount / đổi props
    };
  }, [checkedInAt, active]);

  if (!checkedInAt) return <span className="text-[11px] text-ink-faint">—</span>;
  if (!active) return <span className="text-[11px] text-ink-faint">—</span>;
  if (nowMs === null) return <span className="text-[11px] text-ink-faint">…</span>;

  const totalSec = Math.max(0, Math.floor((nowMs - new Date(checkedInAt).getTime()) / 1000));
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  const cls =
    min < WAIT_GREEN_MAX
      ? "bg-success-bg text-success"
      : min < WAIT_YELLOW_MAX
        ? "bg-warning-bg text-warning"
        : "bg-danger-bg text-danger";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums ${cls}`}
      title={`Chờ ${min} phút kể từ check-in`}
    >
      ⏱ {min}:{String(sec).padStart(2, "0")}
    </span>
  );
}
