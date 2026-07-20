// Điều hướng TUẦN (← tuần trước · tuần này · tuần sau →) cho 1 bảng. Mỗi bảng
// dùng THAM SỐ RIÊNG (`param`, vd weekAppt / weekRoster) nên bấm nút bảng nào CHỈ
// đổi tuần bảng đó; `others` giữ nguyên tham số của bảng kia. Chỉ là Link → Server.

import Link from "next/link";
import {
  shiftWeek,
  weekDates,
  fmtDayMonth,
  currentWeekStartVn,
} from "../../lib/roster";

const BTN =
  "rounded-md border border-[#f3cfe0] px-2.5 py-1 text-xs font-medium text-[#9d2463] transition-colors hover:bg-[#fdf2f8]";

export default function WeekNav({
  week,
  basePath,
  param,
  others = {},
}: {
  week: string;
  basePath: string;
  /** Tên tham số tuần của RIÊNG bảng này (vd "weekAppt" / "weekRoster"). */
  param: string;
  /** Tham số tuần của bảng KIA — giữ nguyên khi đổi tuần bảng này. */
  others?: Record<string, string>;
}) {
  const dates = weekDates(week);
  const label = `${fmtDayMonth(dates[0])} – ${fmtDayMonth(dates[6])}`;
  const cur = currentWeekStartVn();
  const href = (w: string) => {
    const sp = new URLSearchParams(others);
    sp.set(param, w);
    return `${basePath}?${sp.toString()}`;
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Link href={href(shiftWeek(week, -1))} className={BTN}>
        ← Tuần trước
      </Link>
      <span className="text-xs font-medium text-[#171717]">
        Tuần {label}
        {week === cur && <span className="text-[#c084a8]"> · tuần này</span>}
      </span>
      <Link href={href(shiftWeek(week, 1))} className={BTN}>
        Tuần sau →
      </Link>
      {week !== cur && (
        <Link href={href(cur)} className={BTN}>
          Về tuần này
        </Link>
      )}
    </div>
  );
}
