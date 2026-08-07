"use client";

// Nút CHỐT lịch trực của một tuần, và dải báo khi tuần còn là dự kiến.
//
// Vì sao cần: cho tới 08/08/2026 hệ thống chỉ biết "tuần có dòng lịch trực" hay
// "không có". Một tuần vừa xếp nháp và một tuần đã công bố trông hệt nhau — nên
// 26 tuần được trải sẵn từ mẫu tuần tháng 6 đã khiến màn đặt lịch nói chắc nịch
// ai trực ngày 12/12 trong khi phòng khám chưa hề quyết.
//
// Chưa áp dụng KHÔNG có nghĩa là "không ai đi làm". Sơ đồ đặt lịch vẫn nhận
// khách bình thường, chỉ là chưa chốt bác sĩ — giữ nguyên quyết định cũ rằng
// CSKH phải đặt trước được cả tháng.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarCheck, Info } from "lucide-react";

export default function ApDungTuan({
  weekStart,
  daApDung,
  laQuanLy,
  soCa,
}: {
  weekStart: string;
  daApDung: boolean;
  laQuanLy: boolean;
  /** Số ô lịch của tuần. 0 thì không có gì để áp dụng. */
  soCa: number;
}) {
  const router = useRouter();
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // Đổi dải NGAY khi máy chủ trả lời, không chờ trang render lại.
  //
  // `router.refresh()` phải đi một vòng ra server rồi mới có dữ liệu mới. Trong
  // khoảng đó dải vẫn vàng và nút vẫn còn — quản lý tưởng bấm hụt nên bấm lại.
  // Đo được lúc thử tay 08/08: bấm xong, chụp màn hình, vẫn thấy "dự kiến";
  // database thì đã ghi rồi.
  const [vuaApDung, setVuaApDung] = useState(false);

  async function apDung() {
    setDangGui(true);
    setLoi(null);
    const res = await fetch("/api/roster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apply_week: weekStart }),
    });
    setDangGui(false);
    if (!res.ok) {
      const chiTiet = await res
        .json()
        .then((d: { error?: string }) => d.error)
        .catch(() => null);
      setLoi(chiTiet ?? `Không áp dụng được (lỗi ${res.status}).`);
      return;
    }
    setVuaApDung(true);
    router.refresh();
  }

  if (daApDung || vuaApDung) {
    return (
      <p className="flex items-center gap-2 rounded-control bg-success-bg px-3 py-2 text-xs text-success">
        <CalendarCheck className="size-4 shrink-0" aria-hidden="true" />
        Tuần này đã áp dụng. Đặt lịch chọn được bác sĩ theo đúng ca trực.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 rounded-control bg-warning-bg px-3 py-2 text-xs text-warning">
        <Info className="size-4 shrink-0" aria-hidden="true" />
        <span>
          <strong>Lịch dự kiến — chưa áp dụng.</strong> Khách vẫn đặt được, nhưng
          màn đặt lịch chưa chốt bác sĩ nào trực. Bấm áp dụng khi lịch đã chắc.
        </span>
        {laQuanLy && soCa > 0 && (
          <button
            type="button"
            onClick={apDung}
            disabled={dangGui}
            className="ml-auto rounded-control bg-brand-600 px-3 py-1.5 text-xs font-medium text-surface transition-colors hover:bg-brand-700 disabled:opacity-50"
          >
            {dangGui ? "Đang áp dụng…" : `Áp dụng tuần (${soCa} ca)`}
          </button>
        )}
        {laQuanLy && soCa === 0 && (
          <span className="ml-auto text-ink-muted">
            Chưa xếp ca nào — xếp lịch trước rồi mới áp dụng được.
          </span>
        )}
      </div>
      {loi && (
        <p className="rounded-control bg-danger-bg px-3 py-2 text-xs text-danger">
          {loi}
        </p>
      )}
    </div>
  );
}
