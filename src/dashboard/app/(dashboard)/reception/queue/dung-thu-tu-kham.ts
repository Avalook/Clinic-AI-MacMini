"use client";

// THỨ TỰ KHÁM — MỘT HÀNG CHUNG CHO CẢ PHÒNG KHÁM (Tuyền chốt 16/09/2026).
//
// *"hàng chung cho cả phòng khám khi vào check-in… lúc gọi khám thì đặt ở phòng
// bác sĩ nào thì đến phòng bác sĩ ấy"*. Trước đó màn này chia hàng theo từng bác
// sĩ, nên một khách vừa xong thủ thuật quay lại sẽ chen vào giữa hàng của bác sĩ
// mình — trong khi luật quầy là xếp theo GIỜ THỰC: ai check-in lại lúc nào thì
// đứng sau người đang chờ lúc ấy.
//
// Hook này KHÔNG tự xếp gì cả: thứ tự (`call_order`) và mốc mới đều do FastAPI
// tính (GET /queue, POST /queue/keo) — cùng nguồn với bảng gọi số.

import { useCallback, useEffect, useState } from "react";

import { homNayVn } from "@/lib/validation";

export interface DongThuTu {
  /** = appointment_id, khoá để ghép với hàng việc tiếp nhận. */
  id: string;
  queue_number: string | null;
  checked_in_at: string | null;
  call_order: number;
}

const LAM_MOI_MS = 30_000;

export interface ThuTuKham {
  /** appointment_id → thứ tự gọi (1, 2, 3…). Rỗng khi chưa tải được. */
  thuTu: Map<string, number>;
  dangGhi: boolean;
  loi: string | null;
  /** Đặt `id` vào giữa `sau` và `truoc` (null = đầu/cuối hàng). */
  keo: (id: string, sau: string | null, truoc: string | null) => Promise<void>;
}

export function useThuTuKham(): ThuTuKham {
  const [thuTu, setThuTu] = useState<Map<string, number>>(new Map());
  const [dangGhi, setDangGhi] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const tai = useCallback(async () => {
    const res = await fetch(`/api/queue?date=${homNayVn()}`, { cache: "no-store" });
    const json = (await res.json().catch(() => ({}))) as {
      rows?: DongThuTu[];
      error?: string;
    };
    if (!res.ok) {
      // Đọc hỏng thì GIỮ thứ tự cũ: xoá sạch nghĩa là cả hàng đợi nhảy về xếp
      // theo giờ check-in, và người vừa được kéo lên trước tụt lại chỗ cũ.
      setLoi(json.error ?? "Không tải được thứ tự khám.");
      return;
    }
    setLoi(null);
    setThuTu(new Map((json.rows ?? []).map((r) => [r.id, r.call_order])));
  }, []);

  useEffect(() => {
    let huy = false;
    const chay = () => {
      if (!huy) void tai();
    };
    chay();
    const t = setInterval(chay, LAM_MOI_MS);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [tai]);

  const keo = useCallback(
    async (id: string, sau: string | null, truoc: string | null) => {
      if (sau === id || truoc === id) return;
      setDangGhi(true);
      const res = await fetch("/api/queue/keo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          appointment_id: id,
          sau_appointment_id: sau,
          truoc_appointment_id: truoc,
        }),
      });
      const json = (await res.json().catch(() => ({}))) as { error?: string };
      setDangGhi(false);
      if (!res.ok) setLoi(json.error ?? "Không đổi được thứ tự.");
      await tai();
    },
    [tai],
  );

  return { thuTu, dangGhi, loi, keo };
}
