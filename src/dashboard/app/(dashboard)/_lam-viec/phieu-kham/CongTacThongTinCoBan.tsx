"use client";

// Bàn tư vấn: công tắc "Thông tin cơ bản" (Tuyền chốt 25/09/2026 — bản giao diện
// mẫu). Mặc định ĐÓNG: bác sĩ tư vấn chỉ có một ô chữ to. Mở ra là các trường
// khai thác & khám — CÙNG một bản ghi với khối 1 của bác sĩ chính (đồng bộ hai
// chiều, không copy; lưu theo từng ô nên hai bác sĩ sửa hai ô khác nhau không đè).

import { useState, type ReactNode } from "react";

import CongTac from "@/components/ui/CongTac";

export default function CongTacThongTinCoBan({
  tenPhieu,
  children,
}: {
  tenPhieu?: string;
  children: ReactNode;
}) {
  const [mo, setMo] = useState(false);
  return (
    <section className="space-y-3 rounded-card border border-hairline bg-surface p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-body font-medium text-ink">
            Thông tin cơ bản{tenPhieu ? ` — ${tenPhieu}` : ""}
          </p>
          <p className="text-meta text-ink-muted">
            {mo
              ? "Đang mở · điền ô nào thì bác sĩ chính thấy ngay ô đó"
              : "Tuỳ chọn — bật để điền khai thác & khám"}
          </p>
        </div>
        <CongTac bat={mo} nhan={`Thông tin cơ bản: ${mo ? "đang mở" : "đang đóng"}`} onDoi={setMo} />
      </div>
      {mo ? children : null}
    </section>
  );
}
