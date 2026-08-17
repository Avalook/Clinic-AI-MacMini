"use client";

// Đồng hồ đếm ngược tới giờ khám — và LUẬT DỪNG của nó (Tuyền 17/08/2026:
// "có bị vô hạn thời gian không, có code logic để dừng khi đến hạn không?").
//
// Ba điều kiện dừng, mỗi cái một lý do:
//   1. Chỉ đếm khi lịch CHƯA-TỚI (SCHEDULED / CSKH_CONFIRMED / CONFIRMED).
//      Khách đã check-in thì đồng hồ của họ là ĐỒNG HỒ CHỜ KHÁM (WaitClock ở
//      board Lễ tân) — hai câu hỏi khác nhau, không đếm chồng.
//   2. TỚI GIỜ LÀ TẮT HẲN: interval tự clear ngay trong tick khi chạm mốc —
//      không đếm âm, không "còn -3 giờ" vô hạn. Chuyện "quá giờ mà chưa đến"
//      đã có dòng đỏ ⚠ quá-giờ-hẹn lo (server tính), đồng hồ không giành việc.
//   3. Unmount / đổi lượt là clear — không rò interval.
//
// Nhịp 30 giây: đơn vị hiển thị nhỏ nhất là PHÚT, tick mỗi giây chỉ đốt pin.
// Đặt sáng khám chiều thì nó nói "còn 4 giờ 12 phút" — không ai phải chờ
// luật gọi-trước-7-ngày cả: luật ấy là tên BƯỚC gọi xác nhận, còn đồng hồ
// đo tới đúng giờ hẹn của chính lịch này.

import { useEffect, useRef, useState } from "react";
import { chipClass } from "@/components/ui/Chip";

const TRANG_THAI_DEM = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"];

/** "còn 3 ngày" · "còn 4g 12p" · "còn 8p" — đơn vị to dần theo khoảng cách,
 *  người đọc lướt là biết mức gấp. */
function nhan(conMs: number): string {
  const phut = Math.ceil(conMs / 60_000);
  if (phut >= 2 * 24 * 60) return `còn ${Math.floor(phut / (24 * 60))} ngày`;
  if (phut >= 60) {
    const g = Math.floor(phut / 60);
    const p = phut % 60;
    return p > 0 ? `còn ${g}g ${p}p` : `còn ${g}g`;
  }
  return `còn ${phut}p`;
}

export default function DemNguocKham({
  slotStart,
  status,
}: {
  slotStart: string | null | undefined;
  status: string | null | undefined;
}) {
  // null tới khi mount ở client — server không có "bây giờ" (tránh lệch hydration).
  const [nowMs, setNowMs] = useState<number | null>(null);
  const interval = useRef<ReturnType<typeof setInterval> | null>(null);

  const moc = slotStart ? Date.parse(slotStart) : Number.NaN;
  const duocDem =
    Number.isFinite(moc) && TRANG_THAI_DEM.includes(status ?? "");

  useEffect(() => {
    if (!duocDem) return;
    const tick = () => {
      setNowMs(Date.now());
      // ĐIỀU KIỆN DỪNG — chạm mốc là interval tự tắt, không đếm âm.
      if (Date.now() >= moc && interval.current) {
        clearInterval(interval.current);
        interval.current = null;
      }
    };
    const first = setTimeout(tick, 0); // tick đầu qua callback, không setState đồng bộ trong effect
    interval.current = setInterval(tick, 30_000);
    return () => {
      clearTimeout(first);
      if (interval.current) clearInterval(interval.current);
      interval.current = null;
    };
  }, [duocDem, moc]);

  if (!duocDem || nowMs === null) return null;
  const conMs = moc - nowMs;
  if (conMs <= 0) return null; // tới giờ: im — dòng ⚠ quá-giờ (server) tiếp quản

  // Dưới 2 giờ là lúc phải để mắt — đổi tông cho bắt mắt hơn.
  return (
    <span
      className={`${chipClass(conMs < 2 * 3_600_000 ? "warning" : "brand")} tabular-nums`}
      title="Thời gian còn lại tới giờ hẹn"
    >
      ⏳ {nhan(conMs)}
    </span>
  );
}
