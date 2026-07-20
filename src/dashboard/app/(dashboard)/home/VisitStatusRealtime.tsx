"use client";

// "Cập nhật liên tục" cho bảng "Trạng thái BN buổi khám hôm nay" (Lễ tân).
// Subscribe thay đổi trên CẢ ``visit`` VÀ ``appointment`` → debounce →
// ``router.refresh()`` để server component nạp lại + PostgREST lo join.
// QUAN TRỌNG: mốc "Khám xong" đọc từ ``appointment.status = COMPLETED`` (bác sĩ
// "Lưu & Khám xong" cập nhật bảng appointment, KHÔNG đụng visit) — nếu chỉ nghe
// ``visit`` thì board không tự tích "Khám xong" tới khi tải lại tay. Pill báo kênh sống.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowser } from "../../../lib/supabase-browser";

const REFRESH_DEBOUNCE_MS = 1500;

export default function VisitStatusRealtime() {
  const router = useRouter();
  const [eventCount, setEventCount] = useState(0);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const supabase = getSupabaseBrowser();
    const bump = () => {
      setEventCount((c) => c + 1);
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      refreshTimer.current = setTimeout(() => {
        router.refresh();
      }, REFRESH_DEBOUNCE_MS);
    };
    const channel = supabase
      .channel("visit-status-changes")
      // visit: tạo lượt khám, đổi OPEN/IN_PROGRESS/FINALIZED.
      .on("postgres_changes", { event: "*", schema: "public", table: "visit" }, bump)
      // appointment: bác sĩ "Lưu & Khám xong" → status COMPLETED (nguồn mốc "Khám xong").
      .on("postgres_changes", { event: "*", schema: "public", table: "appointment" }, bump)
      // payment: thu ngân chốt thu → nguồn mốc "Đã thanh toán".
      .on("postgres_changes", { event: "*", schema: "public", table: "payment" }, bump)
      .subscribe();
    // Lưới an toàn: nếu realtime của bảng nào CHƯA bật replication thì vẫn đồng bộ
    // chậm nhất ~30s (re-fetch server component). Realtime lo cập nhật tức thời.
    const poll = setInterval(() => router.refresh(), 30_000);
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      clearInterval(poll);
      void supabase.removeChannel(channel);
    };
  }, [router]);

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-[#71717a]">
      <span className="inline-flex h-1.5 w-1.5 animate-pulse rounded-full bg-green-500 motion-reduce:animate-none" />
      Cập nhật liên tục
      {eventCount > 0 && (
        <span className="rounded bg-green-100 px-1.5 py-0.5 font-medium text-green-800">
          +{eventCount}
        </span>
      )}
    </span>
  );
}
