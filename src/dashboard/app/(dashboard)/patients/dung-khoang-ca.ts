"use client";

// Khoảng GIỜ THẬT của từng bác sĩ trực trong một ngày — cho sơ đồ chọn chỗ.
//
// VÌ SAO LÀ HOOK DÙNG CHUNG, KHÔNG CHÉP HAI LẦN.
//
// `CinemaSlotPicker` có BA chỗ gọi: hai trong biểu mẫu khách mới (một cho khách
// vãng lai, một cho đặt lịch đầy đủ) và một ở `AppointmentBooking`. Ngày
// 14/08/2026 tôi vá lưới ngoài-ca-trực và chỉ truyền dữ liệu cho MỘT trong ba —
// đúng cái lưới Tuyền không dùng. Bản vá xanh hết bài kiểm, deploy thành công,
// và lỗi vẫn y nguyên trên màn hình.
//
// Nên phần "hỏi ở đâu, đọc trường nào" gom về đây. Thêm chỗ gọi thứ tư thì nó
// chỉ việc gọi hook này; không còn gì để quên truyền.
//
// LẤY TỪ BACKEND, KHÔNG TỰ QUY ĐỔI. `/appointments/quote` trả `shift_windows`
// do `core/shifts.py` tính. Mốc "sáng kết thúc lúc 12:00" là quyết định của
// phòng khám và nằm ở đúng một hằng số; quy đổi lại ở frontend là dựng bản thứ
// hai của luật ấy.

import { useEffect, useState } from "react";

import { useDoiCa } from "../dung-doi-ca";

/** doctorId → các khoảng [phút bắt đầu, phút kết thúc) trong ngày. */
export type KhoangCa = Record<string, [number, number][]>;

export function useKhoangCa(
  date: string | null | undefined,
  dutyDoctorIds: string[] | null | undefined,
): KhoangCa {
  const [khoang, setKhoang] = useState<KhoangCa>({});
  // Khoá theo NỘI DUNG, không theo tham chiếu mảng: `dutyDoctorIds` được dựng
  // mới sau mỗi lần nạp, nên để nguyên mảng trong deps là gọi lại vô hạn.
  const khoaBacSi = (dutyDoctorIds ?? []).join(",");
  // Ca trực đổi → khung giờ phủ của từng bác sĩ đổi theo — hỏi lại.
  const doiCa = useDoiCa();

  useEffect(() => {
    if (!date || !khoaBacSi) return;
    const ids = khoaBacSi.split(",");
    const ctrl = new AbortController();
    void Promise.all(
      ids.map((id) =>
        fetch(
          `/api/appointments/quote?date=${encodeURIComponent(date)}` +
            `&doctor_id=${encodeURIComponent(id)}`,
          { signal: ctrl.signal },
        )
          .then((r) => (r.ok ? r.json() : null))
          .then(
            (j: { shift_windows?: [number, number][] } | null) =>
              [id, j?.shift_windows ?? []] as const,
          )
          // Hỏi hụt ⇒ mảng rỗng ⇒ `trongCa` hiểu là "chưa biết" và KHÔNG chặn.
          // Chặn dựa trên một điều chưa biết là khoá lịch của bác sĩ đang thật
          // sự đi làm; máy chủ vẫn còn chốt cứng ở dưới nên sai theo hướng này
          // chỉ mất một lần bấm.
          .catch(() => [id, [] as [number, number][]] as const),
      ),
    ).then((cap) => {
      if (ctrl.signal.aborted) return;
      setKhoang(Object.fromEntries(cap));
    });
    return () => ctrl.abort();
  }, [date, khoaBacSi, doiCa]);

  return khoang;
}
