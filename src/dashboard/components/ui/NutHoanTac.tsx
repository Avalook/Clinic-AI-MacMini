"use client";

/**
 * Nút HOÀN TÁC — MỘT mặt cho mọi màn (Tuyền 01/10/2026: "cần nút HOÀN TÁC ở
 * tất cả các việc … không được để bất kể cái gì khoá hẳn").
 *
 * Chữ + biểu tượng, đặt ngay cạnh trạng thái đã làm ("Đã khám xong 10:42 ·
 * [↶ Hoàn tác]"). Nút KHÔNG tự quyết gì: bấm là gửi lệnh hoàn tác của máy chủ
 * (`goi`). Máy chủ thấy hoàn tác chạm ràng buộc nghiệp vụ thật (đã thu tiền,
 * khách đã về, kết quả đã duyệt) thì trả 409 kèm `chi_tiet.can_xac_nhan` và
 * câu hệ quả → nút mở hộp xác nhận (HopXacNhan) có ô lý do, gửi lại với
 * `{ xac_nhan: true, ly_do }`. Không `window.confirm`.
 */

import { useId, useState } from "react";
import { Undo2 } from "lucide-react";

import Button, { type ButtonSize, type ButtonVariant } from "@/components/ui/Button";
import HopXacNhan from "@/components/ui/HopXacNhan";

export type KetQuaHoanTac =
  | { ok: true }
  | { ok: false; loi: string; chiTiet?: Record<string, unknown> };

export interface DuLieuHoanTac {
  ly_do?: string;
  xac_nhan?: boolean;
}

/** Máy chủ đòi hỏi lại (409 CAN_XAC_NHAN)? — đọc cờ máy chủ gửi, không suy luật. */
export function canXacNhan(kq: KetQuaHoanTac): boolean {
  return !kq.ok && kq.chiTiet?.can_xac_nhan === true;
}

const LY_DO_TOI_THIEU = 5;

export default function NutHoanTac({
  goi,
  onXong,
  nhan = "Hoàn tác",
  tieuDe = "Hoàn tác thao tác này?",
  moTa,
  size = "sm",
  variant = "secondary",
  disabled = false,
  className = "",
  onDangHoi,
}: {
  /** Gửi lệnh hoàn tác của máy chủ. */
  goi: (duLieu: DuLieuHoanTac) => Promise<KetQuaHoanTac>;
  /** Hoàn tác xong — màn tải lại (SSE cũng tự tải). */
  onXong?: () => void;
  nhan?: string;
  /** Tiêu đề hộp xác nhận khi máy chủ hỏi lại. */
  tieuDe?: string;
  /** Mô tả việc sẽ rút lại — hiện trong title của nút (rê chuột). */
  moTa?: string;
  size?: ButtonSize;
  variant?: ButtonVariant;
  disabled?: boolean;
  className?: string;
  /** Hộp xác nhận mở / đóng — vd thông báo tự tắt thì dừng đồng hồ khi đang hỏi. */
  onDangHoi?: (dang: boolean) => void;
}) {
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [hoi, setHoi] = useState<string | null>(null);
  const [lyDo, setLyDo] = useState("");
  const idLyDo = useId();

  const gui = async (duLieu: DuLieuHoanTac) => {
    setDangGui(true);
    setLoi(null);
    const kq = await goi(duLieu);
    setDangGui(false);
    if (kq.ok) {
      setHoi(null);
      setLyDo("");
      onDangHoi?.(false);
      onXong?.();
      return;
    }
    if (canXacNhan(kq)) {
      setHoi(kq.loi);
      onDangHoi?.(true);
      return;
    }
    setLoi(kq.loi);
  };

  const duLyDo = lyDo.trim().length >= LY_DO_TOI_THIEU;

  return (
    <span className={`inline-flex flex-col items-start gap-1 ${className}`}>
      <Button
        type="button"
        size={size}
        variant={variant}
        disabled={disabled || dangGui}
        title={moTa}
        onClick={() => void gui({})}
      >
        <Undo2 className="size-3.5" aria-hidden="true" />
        {dangGui && hoi === null ? "Đang hoàn tác…" : nhan}
      </Button>
      {loi && hoi === null ? (
        <span role="alert" className="text-meta text-danger">
          {loi}
        </span>
      ) : null}
      <HopXacNhan
        mo={hoi !== null}
        tieuDe={tieuDe}
        nhanXacNhan="Hoàn tác"
        nhanDangChay="Đang hoàn tác…"
        dangChay={dangGui}
        khoa={!duLyDo}
        loi={loi}
        onXacNhan={() => void gui({ xac_nhan: true, ly_do: lyDo.trim() })}
        onDong={() => {
          setHoi(null);
          setLoi(null);
          onDangHoi?.(false);
        }}
      >
        <p>{hoi}</p>
        <label htmlFor={idLyDo} className="mt-3 block text-body text-ink-muted">
          Lý do hoàn tác (ít nhất {LY_DO_TOI_THIEU} ký tự — ghi vào lịch sử lượt khám)
          <textarea
            id={idLyDo}
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            rows={3}
            maxLength={500}
            disabled={dangGui}
            className="mt-1 block w-full rounded-control bg-surface px-3 py-2 text-body text-ink ring-1 ring-inset ring-line-strong focus:outline-none focus:ring-2 focus:ring-brand-600"
          />
        </label>
      </HopXacNhan>
    </span>
  );
}
