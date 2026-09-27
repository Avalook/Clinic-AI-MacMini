/**
 * Số BOOKING + số CHECK-IN của một lượt — đứng cạnh tên khách ở MỌI khâu khám
 * (Tuyền 27/09/2026: tiếp đón, đo sinh hiệu, tư vấn, bàn khám, phòng dịch vụ,
 * quầy thu, nhà thuốc, xem lượt).
 *
 *   · Booking  — `appointment.so_booking`, cấp LÚC ĐẶT (thứ tự đặt trong ngày).
 *   · Check-in — `appointment.so_tiep_don`, quầy cấp LÚC CHECK-IN (số gọi).
 *
 * Một component để mọi màn cùng chữ, cùng thứ tự, cùng màu — trước đây mỗi màn
 * tự viết ("#12", "Số 5", "Đặt #12 · "…) và có màn tự đếm số của riêng nó.
 * Số nào chưa có thì ẩn chip ấy (khách vãng lai chưa check-in…); cả hai trống
 * thì không vẽ gì.
 */

import Chip from "./Chip";

export default function SoLuot({
  booking,
  checkin,
  className = "",
}: {
  booking?: number | null;
  checkin?: number | null;
  className?: string;
}) {
  if (booking == null && checkin == null) return null;
  return (
    <span className={`inline-flex flex-wrap items-center gap-1 ${className}`}>
      {booking != null ? (
        <Chip tone="neutral" title="Số booking — thứ tự đặt lịch trong ngày">
          Booking #{booking}
        </Chip>
      ) : null}
      {checkin != null ? (
        <Chip tone="brand" title="Số check-in — số quầy tiếp đón gọi">
          Check-in {checkin}
        </Chip>
      ) : null}
    </span>
  );
}
