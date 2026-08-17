"use client";

// Chuông "ca trực vừa đổi" — cho dữ liệu client-fetch, thứ router.refresh()
// không với tới.
//
// router.refresh() chỉ vẽ lại SERVER component. Hai lưới đặt chỗ (BookingHub
// và CinemaSlotPicker trong form Thêm khách mới) lại sống bằng dữ liệu
// TRÌNH DUYỆT tự hỏi (/api/appointments/quote, /api/roster) và giữ cache —
// nên quản lý xoá một ca xong, màn CSKH cảnh báo đã nhảy mà lưới đặt lịch
// vẫn vẽ ca cũ cho tới khi người dùng đổi ngày hoặc F5 (Tuyền nghiệm thu
// 17/08/2026). Máy chủ vẫn chặn cứng lúc đặt thật nên không đặt nhầm được —
// đây là chuyện lớp vẽ nói dối, không phải lỗ nghiệp vụ.
//
// Cách chữa: RealtimeRefresher — nơi DUY NHẤT đang nghe SSE — thấy
// `work_roster` đổi thì rung chuông này (CustomEvent trên window, không mở
// thêm kết nối nào). Component nào cache dữ liệu phụ thuộc ca trực thì gọi
// `useDoiCa()` và bỏ số nó trả về vào deps của effect fetch: chuông rung →
// số nhảy → effect tự hỏi lại. Cùng vai với `bookingSeq` nhưng cho một
// nguồn thay đổi khác.

import { useEffect, useState } from "react";

/** Tên sự kiện — RealtimeRefresher là NGƯỜI RUNG duy nhất. */
export const SU_KIEN_DOI_CA = "clinicai:doi-ca";

/** Số lần ca trực đổi từ khi mount — bỏ vào deps của effect fetch là đủ. */
export function useDoiCa(): number {
  const [seq, setSeq] = useState(0);
  useEffect(() => {
    const rung = () => setSeq((s) => s + 1);
    window.addEventListener(SU_KIEN_DOI_CA, rung);
    return () => window.removeEventListener(SU_KIEN_DOI_CA, rung);
  }, []);
  return seq;
}
