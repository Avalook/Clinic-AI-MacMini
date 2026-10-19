"use client";

// THẺ DỊCH VỤ (khung phải) — MỘT khuôn cho phòng dịch vụ `/phong/[ma]`
// (`KhachTrongPhong`) và bàn đối tác `/doi-tac` (Tuyền 16/10/2026: "bê form
// sang, sao để mỗi chỗ một kiểu, sửa khó hơn"). Sửa đầu thẻ ở đây là cả hai đổi.
//
// Đầu thẻ (bản mẫu `manPhong`, 27/09/2026): "Số N", tên dịch vụ, rồi
// "mã phòng khám · giá · mốc"; dòng dưới là khách. Bên phải: [In phiếu] (mọi
// trạng thái — trang in tự lo phiếu nháp / chỉ có ảnh) + nút chính của chỗ gọi.
// Thân thẻ (ô tệp, phiếu, khối đối tác…) là `children`. Chỉ vẽ — chữ mốc, nút
// nào hiện là chỗ gọi quyết theo dữ liệu máy chủ.

import type { ReactNode } from "react";

import NutInPhieu from "@/components/ui/NutInPhieu";

export default function TheDichVu({
  id,
  nhan,
  so,
  ten,
  moc,
  khach,
  maKhach,
  phuKhach = null,
  duoiKhach = null,
  inHref = null,
  nut = null,
  children,
}: {
  id?: string;
  /** aria-label của thẻ. */
  nhan: string;
  /** Số thứ tự / số check-in — null thì bỏ dòng "Số". */
  so: string | number | null;
  ten: string;
  /** Các mẩu "mã · giá · mốc" — mẩu rỗng tự bỏ. */
  moc: (string | null | undefined | false)[];
  khach: string;
  maKhach: string | null;
  /** Chữ thêm sau mã khách (vd " · BS chỉ định: …"). */
  phuKhach?: string | null;
  /** Dưới dòng khách (chip nhận chéo, "Mẫu gửi đối tác"…). */
  duoiKhach?: ReactNode;
  /** Đường in phiếu kết quả; null = không có nút In. */
  inHref?: string | null;
  /** Nút chính bên phải, cạnh [In phiếu]. */
  nut?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section id={id} aria-label={nhan} className="min-w-0 space-y-4 rounded-card bg-surface p-4 shadow-card">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {so !== null ? (
            <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">Số {so}</p>
          ) : null}
          <h2 className="text-title font-semibold text-ink">{ten}</h2>
          <p className="text-meta tabular-nums text-ink-muted">{moc.filter(Boolean).join(" · ")}</p>
          <p className="mt-1 text-body text-ink">
            <b className="text-emph font-semibold">{khach}</b>
            <span className="text-ink-muted">
              {maKhach ? ` · ${maKhach}` : ""}
              {phuKhach ?? ""}
            </span>
          </p>
          {duoiKhach}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {inHref ? <NutInPhieu href={inHref} size="lg" /> : null}
          {nut}
        </div>
      </header>
      {children}
    </section>
  );
}
