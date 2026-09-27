"use client";

// Bàn tư vấn: công tắc "Thông tin cơ bản" (Tuyền chốt 25/09/2026 — bản giao diện
// mẫu). Mặc định ĐÓNG: bác sĩ tư vấn chỉ có một ô chữ to. Mở ra là các trường
// khai thác & khám — CÙNG một bản ghi với khối 1 của bác sĩ chính (đồng bộ hai
// chiều, không copy; lưu theo từng ô nên hai bác sĩ sửa hai ô khác nhau không đè).
//
// Bản mẫu `manTuVan` (M/app.js:711-721, `.tv-mo`/`.tv-cong` M/style.css:382-393):
// gạt · tên + câu phụ · chip "N ô đã điền" (ẩn khi 0) · chip "đồng bộ bác sĩ chính".
// Phần thân GIỮ trong cây khi đóng (ẩn bằng class) để phiếu đã nạp đếm được số ô
// đã điền ngay cả lúc công tắc đang đóng.

import { useState, type ReactNode } from "react";

import Chip from "@/components/ui/Chip";
import CongTac from "@/components/ui/CongTac";

export default function CongTacThongTinCoBan({
  tenPhieu,
  soDien = 0,
  children,
}: {
  tenPhieu?: string;
  /** Số ô đã điền của phần thông tin cơ bản (phiếu tự báo lên). */
  soDien?: number;
  children: ReactNode;
}) {
  const [mo, setMo] = useState(false);
  return (
    <section className="overflow-hidden rounded-card border border-hairline bg-surface">
      <div className="flex flex-wrap items-center gap-3 px-4 py-2">
        <CongTac bat={mo} nhan={`Thông tin cơ bản: ${mo ? "đang mở" : "đang đóng"}`} onDoi={setMo} />
        <div className="min-w-48 flex-1">
          <p className="text-emph font-semibold text-ink">
            Thông tin cơ bản{tenPhieu ? ` — ${tenPhieu}` : ""}
          </p>
          <p className="text-meta text-ink-muted">
            {mo
              ? "Đang mở · điền ô nào thì bác sĩ chính thấy ngay ô đó"
              : "Tuỳ chọn — bật để điền khai thác & khám"}
          </p>
        </div>
        {soDien > 0 ? <Chip tone="success">{soDien} ô đã điền</Chip> : null}
        <Chip tone="brand">đồng bộ bác sĩ chính</Chip>
      </div>
      <div className={mo ? "border-t border-hairline p-4" : "hidden"}>{children}</div>
    </section>
  );
}
