/**
 * BÁO LỖI CẠNH NÚT — đặt NGAY TRÊN hàng nút vừa bấm (đợt 3, 27/09/2026, góp
 * ý phòng khám B8: "hiện lý do cạnh nút Save… thay vì lý do ở xa khiến phải
 * lướt lại").
 *
 * Lỗi của một nút mà hiện ở đầu phiếu thì người bấm ở cuối phiếu không thấy —
 * họ tưởng nút không ăn. Luật: lỗi của hành động nằm cạnh hành động.
 *
 *   muc="loi"   (mặc định) role=alert, token danger — hành động KHÔNG thành.
 *   muc="nhac"  role=status, token warning — hành động ĐÃ thành, chỉ nhắc
 *               (vd "Còn 3 mục trống…" sau Hoàn tất phiếu — nhắc, không chặn).
 *
 * Không có nội dung thì không vẽ gì.
 */

import type { ReactNode } from "react";

export default function BaoLoiCanhNut({
  children,
  muc = "loi",
  className = "",
}: {
  children: ReactNode;
  muc?: "loi" | "nhac";
  className?: string;
}) {
  if (children == null || children === false || children === "") return null;
  const mau =
    muc === "loi"
      ? "border-danger bg-danger-bg text-danger"
      : "border-warning bg-warning-bg text-warning";
  return (
    <div
      role={muc === "loi" ? "alert" : "status"}
      className={`w-full rounded-control border px-3 py-2 text-body ${mau} ${className}`}
    >
      {children}
    </div>
  );
}
