"use client";

/**
 * Xác nhận TẠI CHỖ — thay `window.confirm` (luật giao diện 18/09: không thêm
 * `window.confirm` mới).
 *
 * `window.confirm` chặn cả trang, không theo token màu, trên điện thoại hiện
 * hộp hệ thống lạc tông, và trình duyệt có thể tự tắt nó sau vài lần. Bản này
 * là một dải nhỏ ngay dưới nút vừa bấm: câu hỏi + [đồng ý] + [Thôi]. Không
 * phủ màn, không khoá thao tác khác — đúng tinh thần "mở, không khoá".
 *
 * `children` (đợt 3, 27/09/2026): ô cần điền TRƯỚC khi đồng ý (vd lý do đóng
 * lượt) nằm ngay trong dải; `choDongY={false}` khoá nút đồng ý tới khi điền đủ.
 */

import type { ReactNode } from "react";

import Button from "./Button";

export default function XacNhanTaiCho({
  cau,
  nhanDongY,
  onDongY,
  onThoi,
  dangGui = false,
  choDongY = true,
  children,
}: {
  cau: string;
  nhanDongY: string;
  onDongY: () => void;
  onThoi: () => void;
  dangGui?: boolean;
  /** Nội dung phụ nằm GIỮA câu hỏi và hai nút (27/09/2026, đợt 3) — vd danh
   *  sách việc còn dở + ô lý do của Check-out. Chiếm trọn một dòng. */
  /** Nút đồng ý bấm được chưa (vd đã gõ lý do). */
  choDongY?: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      role="alertdialog"
      aria-label={cau}
      className="flex w-full flex-wrap items-center gap-2 rounded-control border border-line bg-surface-muted px-3 py-2"
    >
      <p className="min-w-0 flex-1 text-body text-ink">{cau}</p>
      {children ? <div className="w-full">{children}</div> : null}
      <Button
        variant="primary"
        onClick={onDongY}
        disabled={dangGui || !choDongY}
        autoFocus={!children}
      >
        {dangGui ? "Đang ghi…" : nhanDongY}
      </Button>
      <Button variant="ghost" onClick={onThoi} disabled={dangGui}>
        Thôi
      </Button>
    </div>
  );
}
