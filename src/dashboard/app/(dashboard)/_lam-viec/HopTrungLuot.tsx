"use client";

// Máy chủ báo KHACH_DANG_CO_LUOT lúc check-in → hỏi lại trước khi tạo lượt thứ
// hai (ca 01/11/2026: lịch dư bị check-in khi khách đang khám ở lượt trước). Câu
// hỏi do máy chủ viết; ở đây chỉ vẽ và gửi lại kèm `dong_y_trung_luot`.

import HopXacNhan from "@/components/ui/HopXacNhan";

export interface LoiCheckIn {
  error?: string;
  chi_tiet?: { ma?: unknown };
}

export function laTrungLuot(body: LoiCheckIn | null | undefined): boolean {
  return body?.chi_tiet?.ma === "KHACH_DANG_CO_LUOT";
}

export default function HopTrungLuot({
  cau,
  dangChay,
  onXacNhan,
  onDong,
}: {
  /** Câu máy chủ viết; rỗng = đóng hộp. */
  cau: string | null;
  dangChay: boolean;
  onXacNhan: () => void;
  onDong: () => void;
}) {
  return (
    <HopXacNhan
      mo={cau !== null}
      tieuDe="Khách đang có lượt khám mở"
      nhanXacNhan="Vẫn check-in"
      nhanDangChay="Đang check-in…"
      dangChay={dangChay}
      onXacNhan={onXacNhan}
      onDong={onDong}
    >
      {cau}
    </HopXacNhan>
  );
}
