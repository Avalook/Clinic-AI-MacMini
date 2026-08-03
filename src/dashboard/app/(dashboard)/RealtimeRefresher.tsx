"use client";

// Realtime TOÀN APP — gắn 1 lần ở (dashboard)/layout. Subscribe MỌI bảng động
// (dữ liệu thay đổi khi vận hành) trên CÙNG 1 kênh websocket; bất kỳ INSERT/UPDATE/
// DELETE nào → debounce → router.refresh() để Server Component nạp lại + PostgREST
// lo join. Nhờ vậy mọi trang tự cập nhật tức thì, không cần chờ poll.
//
// QUAN TRỌNG: realtime chỉ chạy khi bảng đã nằm trong publication `supabase_realtime`
// (xem SQL bàn giao). Bảng nào chưa bật thì lưới an toàn `poll` ~25s vẫn đồng bộ.
// debounce gộp 1 chuỗi thay đổi (vd tạo lượt khám đụng nhiều bảng) thành 1 refresh.

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowser } from "../../lib/supabase-browser";

const DEBOUNCE_MS = 1200;
const POLL_MS = 25_000;

// Bảng ĐỘNG (bỏ qua bảng tra cứu tĩnh: province/ward/service_type/service_price/
// drug_catalog/booking_channel/clinic_location — không đổi lúc vận hành).
const DEFAULT_TABLES = [
  "appointment",
  "visit",
  "patient",
  "work_roster",
  "staff_task",
  "work_item",
  "work_item_event",
  "payment",
  "prescription",
  "service_log",
  "lab_result",
  "cskh_action",
  "cskh_log",
  "clinical_record",
  "ultrasound_record",
  "clinical_form_response",
  "patient_medical_profile",
  "pregnancy",
  "work_session",
  "staff",
];

export default function RealtimeRefresher({
  tables = DEFAULT_TABLES,
}: {
  tables?: string[];
}) {
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const supabase = getSupabaseBrowser();
    const bump = () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => router.refresh(), DEBOUNCE_MS);
    };

    let channel = supabase.channel("global-realtime-refresh");
    for (const table of tables) {
      channel = channel.on(
        "postgres_changes",
        { event: "*", schema: "public", table },
        bump,
      );
    }
    channel.subscribe();

    // Lưới an toàn: nếu websocket rớt hoặc bảng nào chưa bật replication thì vẫn
    // đồng bộ chậm nhất ~25s. Realtime lo phần tức thì.
    const poll = setInterval(() => router.refresh(), POLL_MS);

    return () => {
      if (timer.current) clearTimeout(timer.current);
      clearInterval(poll);
      void supabase.removeChannel(channel);
    };
  }, [router, tables]);

  return null;
}
