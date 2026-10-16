"use client";

// THẺ KHÁCH TRONG HÀNG CHỜ + ĐẦU NHÓM — MỘT bộ cho phòng dịch vụ
// (`HangChoKhachPhong`) và bàn đối tác `/doi-tac` (Tuyền 16/10/2026: "bê form
// sang, sao để mỗi chỗ một kiểu, sửa khó hơn"). Sửa thẻ ở đây là cả hai đổi.
//
// Một khách một dòng gọn: số check-in · tên (★ ưu tiên) · #số booking · dòng
// phụ ("N chỉ định · …") · giờ bên phải. Chỉ vẽ — nhóm nào, chữ gì là chỗ gọi
// truyền vào (từ dữ liệu máy chủ).

import type { ReactNode } from "react";
import { Star } from "lucide-react";

import SoLuot from "@/components/ui/SoLuot";

/** Một nhóm của cột hàng chờ: "ĐANG CHỜ (3)" + danh sách thẻ. */
export function NhomHangCho({ ten, so, children }: { ten: string; so: number; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-1 px-1 text-label font-semibold uppercase tracking-wide text-ink-muted">
        {ten} ({so})
      </h3>
      <ul className="space-y-1">{children}</ul>
    </section>
  );
}

export default function TheKhachHangCho({
  so,
  ten,
  uuTien = false,
  soBooking = null,
  phu,
  phuDo = false,
  gio,
  dangChon,
  mo = false,
  onChon,
}: {
  /** Số check-in (hoặc số thứ tự) trong vòng tròn. */
  so: string | number | null;
  ten: string;
  uuTien?: boolean;
  soBooking?: number | null;
  /** Dòng phụ đã ghép sẵn ("2 chỉ định · …"). */
  phu: string;
  /** Dòng phụ màu đỏ (vd khách đã sang phòng khác). */
  phuDo?: boolean;
  /** Chữ giờ bên phải ("12 phút", "10:05"). */
  gio: string;
  dangChon: boolean;
  /** Nhóm đã xong — thẻ nhạt đi. */
  mo?: boolean;
  onChon: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onChon}
        aria-pressed={dangChon}
        className={`flex w-full items-center gap-2 rounded-control border px-2 py-1.5 text-left ${
          dangChon ? "border-brand-500 bg-brand-50" : "border-line bg-surface"
        } ${mo ? "opacity-70" : ""}`}
      >
        <span
          title="Số check-in"
          className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-sunken text-meta font-bold text-ink"
        >
          {so ?? "—"}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1">
            {uuTien ? (
              <Star className="size-3.5 shrink-0 fill-warning text-warning" aria-label="Ưu tiên" />
            ) : null}
            <span className={`truncate text-sm font-semibold ${uuTien ? "text-danger" : "text-ink"}`}>
              {ten}
            </span>
            <SoLuot booking={soBooking} className="shrink-0" />
          </span>
          <span className={`block truncate text-label ${phuDo ? "text-danger" : "text-ink-muted"}`}>{phu}</span>
        </span>
        <span className="shrink-0 text-right text-label text-ink-muted">{gio}</span>
      </button>
    </li>
  );
}
