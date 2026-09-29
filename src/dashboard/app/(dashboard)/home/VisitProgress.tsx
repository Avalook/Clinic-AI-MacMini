"use client";

// Trình bày THUẦN (đọc data đã có) cho board "Trạng thái BN buổi khám" của Lễ tân:
//   - reachedCount: số mốc đã đạt (giữ cho test ranh giới; thanh 4 mốc
//     ProgressStepper đã thay bằng Hành trình khách dạng gọn 29/09/2026).
//   - WaitClock: chip đếm thời gian chờ kể từ check-in, ĐỔI MÀU theo ngưỡng.
// KHÔNG ghi DB, KHÔNG đụng enum/visit.status — chỉ render từ props.

import { useEffect, useState } from "react";
import { chipClass } from "@/components/ui/Chip";

// ── Ngưỡng đổi màu đồng hồ chờ (PHÚT kể từ check-in) — cấu hình DUY NHẤT ở đây ──
const WAIT_GREEN_MAX = 10; // < 10p  → xanh
const WAIT_YELLOW_MAX = 20; // 10–20p → vàng;  > 20p → đỏ

// Thanh tiến trình — 4 MỐC: Check-in → Đang khám → Khám xong → Đã thanh toán.
//
// CHECK-IN LÀ MỘT MỐC, KHÔNG PHẢI ĐIỀU KIỆN NGẦM (Quang chốt 06/08). Bản trước
// bắt đầu từ "Đang khám", nên người vừa tới quầy hiện ra với thanh tiến trình
// TRỐNG TRƠN — không phân biệt được với người chưa tới. Giờ mốc đầu tích xanh
// ngay khi Lễ tân bấm check-in, và dưới mỗi mốc là GIỜ mốc đó xảy ra.
//
// "Đến mốc nào tích xanh mốc ấy" (reached) suy từ visit.status + appointment.status:
//   • Check-in       → visit.checked_in_at có giá trị.
//   • Đang khám      → visit IN_PROGRESS (BN đã vào khám).
//   • Khám xong      → appointment COMPLETED (bác sĩ "Lưu & Khám xong"). LƯU Ý:
//     dashboard KHÔNG tự set visit.FINALIZED, nên "khám xong" PHẢI đọc từ
//     appointment, không phải visit — nếu không mốc này không bao giờ xanh.
//   • Đã thanh toán  → bảng payment: khi mọi khâu PHẢI thu (dịch vụ + thuốc nếu có
//     đơn) đã có dòng PAID → `paid=true` → tích xanh. Chưa thu xong thì hiện "đang
//     tới" (nhấn pulse) chờ thu ngân.
// Số mốc đã đạt (tích xanh). Chưa check-in=0, đã check-in=1, đang khám=2,
// khám xong=3, đã thanh toán=4 (paid từ bảng payment — thu ngân chốt đủ khâu).
export function reachedCount(
  visitStatus: string,
  apptStatus: string | null,
  paid: boolean,
  checkedIn = true,
  /** Đã bấm "Bắt đầu khám" chưa. `undefined` = không biết (giữ cách cũ). */
  examStarted?: boolean,
): number {
  const done =
    apptStatus === "COMPLETED" ||
    visitStatus === "FINALIZED" ||
    visitStatus === "AMENDED";
  if (paid && done) return 4; // chỉ tích thanh toán khi đã khám xong
  if (done) return 3; // khám xong
  // Khám dở: dừng ở mốc "đang khám", KHÔNG tích "khám xong".
  //
  // Không có nhánh này thì INCOMPLETE rơi xuống `return 0` và thanh tiến trình
  // lùi về "mới check-in" cho một người đã đi được nửa buổi — trông như hệ
  // thống quên mất họ.
  //
  // Luồng mới mở lượt IN_PROGRESS NGAY lúc check-in (17/09/2026), nên
  // IN_PROGRESS một mình không còn nghĩa là "đang khám": phải có mốc bắt đầu.
  if (visitStatus === "IN_PROGRESS" && examStarted === false) return checkedIn ? 1 : 0;
  if (visitStatus === "IN_PROGRESS" || visitStatus === "INCOMPLETE") return 2;
  // `checkedIn` mặc định true: mọi dòng trên board đều đã có lượt khám, mà lượt
  // khám chỉ mở khi check-in. Cờ này để một dòng THIẾU mốc check-in không lặng
  // lẽ tích xanh mốc đó.
  return checkedIn ? 1 : 0;
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

  if (!checkedInAt) return <span className="text-label text-ink-faint">—</span>;
  if (!active) return <span className="text-label text-ink-faint">—</span>;
  if (nowMs === null) return <span className="text-label text-ink-faint">…</span>;

  const totalSec = Math.max(0, Math.floor((nowMs - new Date(checkedInAt).getTime()) / 1000));
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  // Ngưỡng chờ đổi màu map thẳng vào tone chip: success → warning → danger.
  const tone =
    min < WAIT_GREEN_MAX
      ? ("success" as const)
      : min < WAIT_YELLOW_MAX
        ? ("warning" as const)
        : ("danger" as const);

  return (
    <span
      className={`${chipClass(tone)} tabular-nums`}
      title={`Chờ ${min} phút kể từ check-in`}
    >
      ⏱ {min}:{String(sec).padStart(2, "0")}
    </span>
  );
}
