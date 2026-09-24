"use client";

/**
 * Xác nhận TẠI CHỖ — thay `window.confirm` (luật giao diện 18/09: không thêm
 * `window.confirm` mới).
 *
 * `window.confirm` chặn cả trang, không theo token màu, trên điện thoại hiện
 * hộp hệ thống lạc tông, và trình duyệt có thể tự tắt nó sau vài lần. Bản này
 * là một dải nhỏ ngay dưới nút vừa bấm: câu hỏi + [đồng ý] + [Thôi]. Không
 * phủ màn, không khoá thao tác khác — đúng tinh thần "mở, không khoá".
 */

import Button from "./Button";

export default function XacNhanTaiCho({
  cau,
  nhanDongY,
  onDongY,
  onThoi,
  dangGui = false,
}: {
  cau: string;
  nhanDongY: string;
  onDongY: () => void;
  onThoi: () => void;
  dangGui?: boolean;
}) {
  return (
    <div
      role="alertdialog"
      aria-label={cau}
      className="flex w-full flex-wrap items-center gap-2 rounded-control border border-line bg-surface-muted px-3 py-2"
    >
      <p className="min-w-0 flex-1 text-body text-ink">{cau}</p>
      <Button variant="primary" onClick={onDongY} disabled={dangGui} autoFocus>
        {dangGui ? "Đang ghi…" : nhanDongY}
      </Button>
      <Button variant="ghost" onClick={onThoi} disabled={dangGui}>
        Thôi
      </Button>
    </div>
  );
}
