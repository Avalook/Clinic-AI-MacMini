"use client";

/**
 * TRẠNG THÁI TỰ LƯU — một dòng, dùng chung mọi màn tự lưu (đợt 3, 27/09/2026,
 * góp ý phòng khám B9 "save liên tục — có đảm bảo không?").
 *
 * Không có nút "Lưu" thường trực (Tuyền chốt). Thay vào đó người dùng LUÔN thấy
 * chữ của mình đang ở đâu:
 *
 *   Đang lưu…                     một lần lưu đang bay
 *   Đã lưu 10:32                  máy chủ đã có hết
 *   Chưa lưu — [Lưu ngay]         còn chữ chưa tới máy chủ (vừa gõ)
 *   Lưu lỗi — [Thử lại]           lần lưu gần nhất hỏng; câu lỗi ở dòng dưới
 *
 * Nút chỉ hiện khi CÓ việc để làm. Màu/cỡ theo token (DESIGN.md), nút là
 * `Button` cỡ sm. `aria-live` để trình đọc màn hình nghe được lúc lỗi.
 */

import type { TrangThaiLuu as TT } from "@/lib/tu-luu";

import Button from "./Button";

function gioVn(d: Date): string {
  return d.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function TrangThaiLuu({
  tt,
  onLuuNgay,
  chuaGo = "Tự lưu khi gõ",
  phu,
  className = "",
}: {
  tt: TT;
  onLuuNgay: () => void;
  /** Chữ khi chưa lưu lần nào trong phiên này. */
  chuaGo?: string;
  /** Chữ kèm sau "Đã lưu hh:mm" (vd "nháp, chưa phải kết quả"). */
  phu?: string;
  className?: string;
}) {
  let noiDung;
  if (tt.dang_luu) {
    noiDung = <span className="text-ink-muted">Đang lưu…</span>;
  } else if (tt.loi) {
    noiDung = (
      <>
        <span className="font-semibold text-danger">
          Lưu lỗi{tt.tu_thu_lai ? " — đang tự thử lại" : ""}
        </span>
        <Button size="sm" variant="danger" onClick={onLuuNgay}>
          Thử lại
        </Button>
        <span className="basis-full text-danger">{tt.loi}</span>
      </>
    );
  } else if (tt.chua_luu) {
    noiDung = (
      <>
        <span className="text-warning">Chưa lưu</span>
        <Button size="sm" variant="secondary" onClick={onLuuNgay}>
          Lưu ngay
        </Button>
      </>
    );
  } else {
    noiDung = (
      <span className="text-ink-muted">
        {tt.luu_luc ? `Đã lưu ${gioVn(tt.luu_luc)}` : chuaGo}
        {tt.luu_luc && phu ? ` · ${phu}` : ""}
      </span>
    );
  }
  return (
    <div
      aria-live="polite"
      className={`flex min-h-7 flex-wrap items-center gap-x-2 gap-y-1 text-meta ${className}`}
    >
      {noiDung}
    </div>
  );
}
