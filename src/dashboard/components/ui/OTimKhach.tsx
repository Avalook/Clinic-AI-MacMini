"use client";

// Ô TÌM KHÁCH của cột hàng chờ — MỘT ô cho phòng dịch vụ `/phong/[ma]` và bàn
// đối tác `/doi-tac` (Tuyền 16/10/2026: "sao để mỗi chỗ một kiểu"). Chỉ vẽ ô;
// so khớp tên / mã / số ở `lib/tim-khach-phong` (`khopTimKhach`).

import { Search } from "lucide-react";

export default function OTimKhach({
  value,
  onChange,
  nhan = "Tìm khách",
}: {
  value: string;
  onChange: (v: string) => void;
  /** Nhãn cho trình đọc màn hình. */
  nhan?: string;
}) {
  return (
    <label className="flex h-10 w-full items-center gap-2 rounded-control border border-line bg-surface px-3 focus-within:border-brand-500">
      <Search aria-hidden className="size-4 shrink-0 text-ink-muted" />
      <span className="sr-only">{nhan}</span>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Tìm tên, mã khách hoặc số"
        className="min-w-0 flex-1 bg-transparent text-body text-ink outline-none placeholder:text-ink-faint"
      />
    </label>
  );
}
