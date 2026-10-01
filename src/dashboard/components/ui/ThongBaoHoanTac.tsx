"use client";

/**
 * Thông báo sau thao tác kèm nút Hoàn tác — "Đã khám xong · [↶ Hoàn tác]"
 * (Tuyền 01/10/2026). Hiện ở đáy màn vài giây rồi tự tắt; bấm Hoàn tác thì
 * gửi đúng lệnh hoàn tác của máy chủ (qua `NutHoanTac`, kể cả hỏi xác nhận).
 *
 * Màn giữ MỘT state `{ cau, goi }` (hoặc null) và đặt nó ngay khi lệnh gốc
 * thành công. Đổi `cau` / `goi` (thao tác mới) là đồng hồ đếm lại.
 */

import { useEffect, useState } from "react";
import { CheckCircle2, X } from "lucide-react";

import NutHoanTac, { type DuLieuHoanTac, type KetQuaHoanTac } from "@/components/ui/NutHoanTac";

export interface ThongBao {
  /** Câu đã làm, vd "Đã khám xong — Nguyễn Thị A". */
  cau: string;
  /** Lệnh hoàn tác của máy chủ cho đúng thao tác vừa làm. */
  goi: (duLieu: DuLieuHoanTac) => Promise<KetQuaHoanTac>;
}

/** Mặc định 10 giây — đủ để thấy mình bấm nhầm. */
const GIU_MS = 10_000;

export default function ThongBaoHoanTac({
  thongBao,
  onDong,
  onHoanTacXong,
  giuMs = GIU_MS,
}: {
  thongBao: ThongBao | null;
  onDong: () => void;
  onHoanTacXong?: () => void;
  giuMs?: number;
}) {
  // Đang hỏi xác nhận (hộp lý do mở) thì KHÔNG tự tắt — tắt là mất hộp.
  const [dangHoi, setDangHoi] = useState(false);
  useEffect(() => {
    if (!thongBao || dangHoi) return;
    const t = window.setTimeout(onDong, giuMs);
    return () => window.clearTimeout(t);
  }, [thongBao, onDong, giuMs, dangHoi]);

  if (!thongBao) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-4 bottom-4 z-40 mx-auto flex max-w-lg flex-wrap items-center gap-2 rounded-card bg-surface px-4 py-3 shadow-panel ring-1 ring-line sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2"
    >
      <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden="true" />
      <span className="min-w-0 flex-1 text-body text-ink">{thongBao.cau}</span>
      <NutHoanTac
        goi={thongBao.goi}
        onDangHoi={setDangHoi}
        onXong={() => {
          onDong();
          onHoanTacXong?.();
        }}
      />
      <button
        type="button"
        onClick={onDong}
        aria-label="Đóng thông báo"
        className="grid size-7 place-items-center rounded-control text-ink-muted hover:bg-surface-sunken"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </div>
  );
}
