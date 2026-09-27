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

// 27/09/2026 tối (Tuyền chốt): hai số GHÉP THÀNH MỘT VIÊN "#5 | 13" — nửa trái
// xám là booking (giữ dấu #), nửa phải xanh đậm là check-in (số gọi, cần nổi).
// Chữ đầy đủ nằm ở title + nhãn cho trình đọc màn hình.

const NUA = "inline-flex h-5 items-center px-2 tabular-nums";

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
  const nhan = [
    booking != null ? `Booking #${booking}` : null,
    checkin != null ? `Check-in ${checkin}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <span
      title={nhan}
      aria-label={nhan}
      className={`inline-flex shrink-0 overflow-hidden whitespace-nowrap rounded-chip text-label ${className}`}
    >
      {booking != null ? (
        <span aria-hidden className={`${NUA} bg-surface-sunken text-ink-muted`}>
          #{booking}
        </span>
      ) : null}
      {checkin != null ? (
        <span aria-hidden className={`${NUA} bg-brand-50 font-semibold text-brand-700`}>
          {checkin}
        </span>
      ) : null}
    </span>
  );
}
