"use client";

// THẺ KHÁCH TRONG HÀNG CHỜ + ĐẦU NHÓM — MỘT bộ cho phòng dịch vụ
// (`HangChoKhachPhong`) và bàn đối tác `/doi-tac` (Tuyền 16/10/2026: "bê form
// sang, sao để mỗi chỗ một kiểu, sửa khó hơn"). Sửa thẻ ở đây là cả hai đổi.
//
// Một khách một dòng gọn: số check-in · tên (★ ưu tiên) · #số booking · dòng
// phụ ("N chỉ định · …") · giờ bên phải. Chỉ vẽ — nhóm nào, chữ gì là chỗ gọi
// truyền vào (từ dữ liệu máy chủ). Bàn XN (`/ban-xet-nghiem`) dùng `xuongDong`:
// cột 22rem + chip trạng thái dài từng cắt tên còn "Kh…".

import type { ReactNode } from "react";
import { Star } from "lucide-react";

import SoLuot from "@/components/ui/SoLuot";
import { sdtDoc } from "@/lib/sdt";

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
  sdt = null,
  uuTien = false,
  soBooking = null,
  phu,
  phuDo = false,
  gio,
  dangChon,
  mo = false,
  phai,
  xuongDong = false,
  onChon,
}: {
  /** Thay chữ giờ bên phải bằng thứ khác (bàn XN: chip trạng thái). Không truyền =
   *  như cũ (`gio`). */
  phai?: ReactNode;
  /** Cột hẹp (bàn XN 22rem, chip dài): tên được xuống dòng, không cắt "Kh…";
   *  SĐT · #booking · dòng phụ · `phai` dồn xuống dòng dưới, tự xuống hàng khi
   *  chật. Không truyền = một dòng gọn như cũ (phòng dịch vụ, /doi-tac). */
  xuongDong?: boolean;
  /** Số check-in (hoặc số thứ tự) trong vòng tròn. */
  so: string | number | null;
  ten: string;
  /** SĐT hiện ngay cạnh tên (27/10/2026). */
  sdt?: string | null;
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
  const sao = uuTien ? (
    <Star className="size-3.5 shrink-0 fill-warning text-warning" aria-label="Ưu tiên" />
  ) : null;
  const soDt = sdtDoc(sdt) ? (
    <span className="shrink-0 text-label tabular-nums text-ink-muted">{sdtDoc(sdt)}</span>
  ) : null;
  const mauTen = uuTien ? "text-danger" : "text-ink";
  if (xuongDong) {
    return (
      <li>
        <button
          type="button"
          onClick={onChon}
          aria-pressed={dangChon}
          className={`flex w-full items-start gap-2 rounded-control border px-2 py-1.5 text-left ${
            dangChon ? "border-brand-500 bg-brand-50" : "border-line bg-surface"
          } ${mo ? "opacity-70" : ""}`}
        >
          <span
            title="Số check-in"
            className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-sunken text-meta font-bold text-ink"
          >
            {so ?? "—"}
          </span>
          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="flex items-start gap-1">
              {sao}
              <span className={`min-w-0 break-words text-sm font-semibold ${mauTen}`}>{ten}</span>
            </span>
            <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
              {soDt}
              <SoLuot booking={soBooking} className="shrink-0" />
              {phu ? (
                <span className={`min-w-0 break-words text-label ${phuDo ? "text-danger" : "text-ink-muted"}`}>
                  {phu}
                </span>
              ) : null}
              {phai ?? (gio ? <span className="shrink-0 text-label text-ink-muted">{gio}</span> : null)}
            </span>
          </span>
        </button>
      </li>
    );
  }
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
            {sao}
            <span className={`truncate text-sm font-semibold ${mauTen}`}>{ten}</span>
            {soDt}
            <SoLuot booking={soBooking} className="shrink-0" />
          </span>
          <span className={`block truncate text-label ${phuDo ? "text-danger" : "text-ink-muted"}`}>{phu}</span>
        </span>
        {phai ?? <span className="shrink-0 text-right text-label text-ink-muted">{gio}</span>}
      </button>
    </li>
  );
}
