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

const NUA = "inline-flex h-6 items-center px-2 tabular-nums";

export default function SoLuot({
  booking,
  checkin,
  dang = "vien",
  bookingTruoc = false,
  className = "",
}: {
  booking?: number | null;
  checkin?: number | null;
  /** `vien` = viên ngang cho chỗ hẹp (đầu thẻ, tiêu đề); `tron` = vòng tròn
   *  to cho DANH SÁCH: số check-in to nền đặc, booking nhỏ ngay dưới. */
  dang?: "vien" | "tron";
  /** Chỉ cho `tron`: ô booking đứng TRƯỚC vòng check-in (danh sách Tiếp đón —
   *  bản mẫu Tuyền duyệt 27/09: booking có trước, check-in cấp sau). Mặc định
   *  giữ thứ tự cũ (vòng check-in trước). */
  bookingTruoc?: boolean;
  className?: string;
}) {
  if (booking == null && checkin == null) return null;
  if (dang === "tron") {
    const tieuDe = [
      checkin != null ? `Check-in ${checkin}` : "Chưa check-in",
      booking != null ? `Booking #${booking}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
    // Hai số KHÁC HÌNH + KHÁC MÀU, cùng cỡ to (Tuyền 27/09 tối): check-in là
    // vòng tròn xanh ngọc; booking — số người ta quan tâm hơn — là ô vuông bo
    // góc xanh dương đứng ngay bên phải.
    // CHƯA CHECK-IN mà đã có booking (danh sách Tiếp đón, 27/09 đợt 3): vòng
    // RỖNG nét đứt — chỗ số check-in sẽ được cấp, chưa có số. Hai số trống thì
    // đã thoát ở đầu hàm.
    const vong =
      checkin != null
        ? "bg-brand-600 text-emph font-semibold text-white"
        : booking != null
          ? "border-2 border-dashed border-line-strong bg-surface text-meta text-ink-faint"
          : "bg-surface-sunken text-emph font-semibold text-ink-muted";
    const oVong = (
      <span
        aria-hidden
        className={`grid size-10 place-items-center rounded-full tabular-nums ${vong}`}
      >
        {checkin ?? "—"}
      </span>
    );
    const oBooking =
      booking != null ? (
        <span
          aria-hidden
          className="grid h-10 min-w-10 place-items-center rounded-control bg-info px-1.5 text-emph font-semibold tabular-nums text-white"
        >
          #{booking}
        </span>
      ) : null;
    return (
      <span title={tieuDe} aria-label={tieuDe} className={`flex shrink-0 items-center gap-1 ${className}`}>
        {bookingTruoc ? oBooking : oVong}
        {bookingTruoc ? oVong : oBooking}
      </span>
    );
  }
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
      className={`inline-flex shrink-0 overflow-hidden whitespace-nowrap rounded-chip text-meta ${className}`}
    >
      {booking != null ? (
        <span aria-hidden className={`${NUA} bg-surface-sunken text-ink-muted`}>
          #{booking}
        </span>
      ) : null}
      {checkin != null ? (
        <span aria-hidden className={`${NUA} bg-brand-600 font-semibold text-white`}>
          {checkin}
        </span>
      ) : null}
    </span>
  );
}
