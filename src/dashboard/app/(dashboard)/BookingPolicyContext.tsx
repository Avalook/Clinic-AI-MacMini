"use client";

// Luật đặt lịch của phòng khám, đọc một lần ở layout (server) rồi phát cho mọi
// màn phía dưới (C.3).
//
// Vì sao context chứ không phải prop: <AppointmentBooking> được sáu nơi dựng
// lên — PatientBooking, QuickBookingModal, AppointmentEditModal, PatientListView
// và hai page. Kéo prop qua sáu tầng trung gian nghĩa là lần sau ai thêm chỗ
// dựng thứ bảy sẽ quên, và cái quên đó không gây lỗi biên dịch nào — nó chỉ vẽ
// lưới sai giờ.
//
// `null` = chưa đọc được luật, KHÔNG PHẢI "dùng 15 phút đi". Xem booking-policy.ts.

import { createContext, useContext } from "react";
import type { BookingPolicy } from "../../lib/booking-policy";

const BookingPolicyContext = createContext<BookingPolicy | null>(null);

export function BookingPolicyProvider({
  policy,
  children,
}: {
  policy: BookingPolicy | null;
  children: React.ReactNode;
}) {
  return (
    <BookingPolicyContext.Provider value={policy}>
      {children}
    </BookingPolicyContext.Provider>
  );
}

/** Luật cho lần render này, hoặc `null` khi backend không trả lời. */
export function useBookingPolicy(): BookingPolicy | null {
  return useContext(BookingPolicyContext);
}
