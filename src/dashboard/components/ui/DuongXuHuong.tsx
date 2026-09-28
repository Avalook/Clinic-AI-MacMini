/**
 * Đường xu hướng nhỏ (sparkline) dưới một con số — kiểu ô số liệu của Stripe
 * (Tuyền chốt Trang chủ "bảng A + thống kê B", 27/09/2026).
 *
 * Chỉ vẽ: dãy số do backend đưa, không tự suy ra gì. Màu theo `currentColor`
 * để nơi dùng chọn token (text-success / text-warning…), không có mã màu ở đây.
 */

export default function DuongXuHuong({
  so,
  className = "",
}: {
  so: readonly number[];
  className?: string;
}) {
  if (so.length < 2) return null;
  const lon = Math.max(...so);
  const nho = Math.min(...so);
  const bien = lon - nho || 1;
  // Hệ toạ độ 100×24 kéo giãn theo khung; nét giữ độ dày nhờ non-scaling-stroke.
  const d = so
    .map((v, i) => {
      const x = (i / (so.length - 1)) * 100;
      const y = 22 - ((v - nho) / bien) * 20;
      return `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 24"
      preserveAspectRatio="none"
      aria-hidden
      className={`h-7 w-full ${className}`}
    >
      <path
        d={d}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
