"use client";

// Sức chứa + khoảng ca của cả lưới đặt chỗ trong MỘT ngày — hỏi máy chủ MỘT lần.
//
// VÌ SAO LÀ HOOK DÙNG CHUNG. `CinemaSlotPicker` có hai chỗ gọi (biểu mẫu khách
// mới — ô vãng lai — và `AppointmentBooking`). Ngày 14/08/2026 bản vá lưới
// ngoài-ca-trực chỉ truyền dữ liệu cho MỘT chỗ gọi — đúng cái Tuyền không dùng.
// Nên phần "hỏi ở đâu, đọc trường nào" gom về đây.
//
// VÌ SAO HỎI MÁY CHỦ (29/09/2026). Bản trước (`dung-khoang-ca.ts`) gọi
// `/appointments/quote` TỪNG bác sĩ chỉ để lấy `shift_windows`, còn số ghế thì
// lưới tự cộng từ danh sách lịch và so với trần CHUNG của phòng khám — lệch với
// trigger mỗi khi có luật riêng theo bác sĩ × giờ. Nay một lượt gọi
// `/api/appointments/luoi-ngay` trả cả khoảng ca lẫn số ghế từng khung của mọi
// hàng, tính bằng đúng hàm trigger dùng.

import { useEffect, useState } from "react";

import { useDoiCa } from "../dung-doi-ca";
import type { SucChuaNgay } from "../../../lib/suc-chua-luoi";

export interface SucChuaTai {
  /** null = đang tải (hoặc chưa có ngày). */
  data: SucChuaNgay | null;
  /** true = máy chủ không trả lời được — lưới phải nói thẳng, không đoán. */
  loi: boolean;
}

export function useSucChuaNgay(
  date: string | null | undefined,
  doctorIds: (string | null | undefined)[],
  opts: { boQuaLichId?: string; lamMoi?: number } = {},
): SucChuaTai {
  // Khoá theo NỘI DUNG, không theo tham chiếu mảng: mảng được dựng mới mỗi lần
  // render, để nguyên trong deps là gọi lại vô hạn.
  const ids = [...new Set(doctorIds.filter((x): x is string => !!x))].sort().join(",");
  const boQua = opts.boQuaLichId ?? "";
  const lamMoi = opts.lamMoi ?? 0;
  // Ca trực đổi → khung giờ phủ của từng bác sĩ đổi theo — hỏi lại.
  const doiCa = useDoiCa();
  const [kq, setKq] = useState<{ date: string; data: SucChuaNgay | null; loi: boolean }>({
    date: "",
    data: null,
    loi: false,
  });

  useEffect(() => {
    if (!date) return;
    const ctrl = new AbortController();
    const q = new URLSearchParams({ date });
    if (ids) q.set("doctor_ids", ids);
    if (boQua) q.set("bo_qua_lich_id", boQua);
    fetch(`/api/appointments/luoi-ngay?${q.toString()}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? (r.json() as Promise<SucChuaNgay>) : Promise.reject(r.status)))
      .then((j) => setKq({ date, data: j, loi: false }))
      .catch(() => {
        if (!ctrl.signal.aborted) setKq({ date, data: null, loi: true });
      });
    return () => ctrl.abort();
  }, [date, ids, boQua, lamMoi, doiCa]);

  // Số của NGÀY KHÁC thì không bao giờ vẽ. Cùng ngày mà đang tải lại (vừa đặt
  // xong, đổi bác sĩ) thì giữ số cũ cho khỏi nháy — máy chủ vẫn chốt cứng.
  if (!date || kq.date !== date) return { data: null, loi: false };
  return { data: kq.data, loi: kq.loi };
}
