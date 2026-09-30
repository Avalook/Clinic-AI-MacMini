"use client";

/**
 * Hộp xác nhận nổi (modal) cho hành động PHÁ HUỶ không hoàn tác từ giao diện
 * (30/09/2026 — màn Dọn dữ liệu thử). Khác `XacNhanTaiCho` (dải xác nhận ngay
 * dưới nút): ở đây người bấm phải ĐỌC một danh sách dài (tên khách, số dòng)
 * trước khi đồng ý, nên cần cả màn tập trung, và có thể đòi GÕ một chữ
 * (`goChu`) mới mở nút xác nhận — không dùng `window.confirm`.
 *
 * Esc / bấm nền / [Huỷ] đều đóng (trừ khi đang chạy).
 */

import { useEffect, useId, useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";

export default function HopXacNhan({
  mo,
  tieuDe,
  children,
  nhanXacNhan,
  goChu,
  dangChay = false,
  khoa = false,
  loi,
  onXacNhan,
  onDong,
}: {
  mo: boolean;
  tieuDe: string;
  children: ReactNode;
  /** Chữ trên nút xác nhận, vd "Xoá 3 khách". */
  nhanXacNhan: string;
  /** Có thì phải gõ đúng chữ này mới bấm được xác nhận. */
  goChu?: string;
  dangChay?: boolean;
  /** Khoá nút xác nhận (vd còn khách bị chặn) — lý do đặt ở `loi`. */
  khoa?: boolean;
  /** Câu lỗi hiện ngay trên nút (máy chủ từ chối…). */
  loi?: string | null;
  onXacNhan: () => void;
  onDong: () => void;
}) {
  const [chu, setChu] = useState("");
  const idTieuDe = useId();
  const idO = useId();

  useEffect(() => {
    if (!mo) return;
    const phim = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !dangChay) onDong();
    };
    window.addEventListener("keydown", phim);
    return () => window.removeEventListener("keydown", phim);
  }, [mo, dangChay, onDong]);

  if (!mo) return null;
  const duGo = !goChu || chu.trim() === goChu;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={idTieuDe}
      className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
    >
      <div
        aria-hidden
        className="absolute inset-0 bg-ink/30"
        onClick={() => {
          if (!dangChay) onDong();
        }}
      />
      <div className="relative flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-2xl bg-surface shadow-panel ring-1 ring-line sm:rounded-2xl">
        <h2 id={idTieuDe} className="border-b border-line px-4 py-3 text-title font-semibold text-ink">
          {tieuDe}
        </h2>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 text-body text-ink">{children}</div>
        <div className="space-y-2 border-t border-line px-4 py-3">
          {goChu ? (
            <label htmlFor={idO} className="block text-body text-ink-muted">
              Gõ <strong className="font-semibold text-ink">{goChu}</strong> để xác nhận
              <input
                id={idO}
                value={chu}
                onChange={(e) => setChu(e.target.value)}
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                disabled={dangChay}
                className="mt-1 block h-10 w-full rounded-control bg-surface px-3 text-body text-ink ring-1 ring-inset ring-line-strong focus:outline-none focus:ring-2 focus:ring-brand-600 md:h-8"
              />
            </label>
          ) : null}
          {loi ? (
            <p role="alert" className="text-body text-danger">
              {loi}
            </p>
          ) : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onDong} disabled={dangChay}>
              Huỷ
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={onXacNhan}
              disabled={!duGo || dangChay || khoa}
            >
              {dangChay ? "Đang xoá…" : nhanXacNhan}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
