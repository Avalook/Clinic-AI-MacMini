"use client";

// THANH TÌM + LỌC TRÊN CÙNG màn Tiếp đón (09/10/2026, lời phòng khám: "đưa phần
// tìm kiếm lên vị trí trên cùng và bổ sung bộ lọc đã check-in / chưa check-in").
// Một ô tìm + ba tab lọc CẢ bảng Lịch hẹn lẫn danh sách tiếp đón bên dưới —
// trước đây chúng nằm dưới bảng Lịch hẹn và chỉ lọc danh sách. Chỉ vẽ + giữ chữ;
// phép lọc là hàm thuần ở `lib/tiep-don.ts` (`locTiepDon`, `locLichHen`).

import { Search } from "lucide-react";
import Link from "next/link";

import { buttonClass } from "@/components/ui/Button";
import ThanhTab from "@/components/ui/ThanhTab";
import { hrefThemKhach } from "@/lib/lien-ket-lich";
import type { LocTiepDon, TabTiepDon } from "@/lib/tiep-don";

export default function ThanhLocTiepDon({
  loc,
  onDoi,
  dem,
  themKhachDuoc,
}: {
  loc: LocTiepDon;
  onDoi: (loc: LocTiepDon) => void;
  /** Số đếm của danh sách tiếp đón hôm nay (máy chủ). Không có → tab không số. */
  dem: { tat_ca: number; chua_den: number; da_den: number } | null;
  themKhachDuoc: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-card border border-line bg-surface p-3 shadow-card">
      <label className="flex min-h-10 min-w-48 flex-1 basis-full items-center gap-2 rounded-control border border-line bg-surface px-3 text-ink-muted focus-within:border-brand-500 sm:basis-auto">
        <Search size={15} aria-hidden />
        <span className="sr-only">Tìm tên, SĐT, mã khách, số booking</span>
        <input
          type="search"
          value={loc.tim}
          onChange={(e) => onDoi({ ...loc, tim: e.target.value })}
          placeholder="Tìm tên, SĐT, mã khách, #booking"
          className="min-w-0 flex-1 bg-transparent text-body text-ink outline-none placeholder:text-ink-faint"
        />
      </label>
      <ThanhTab<TabTiepDon>
        nhan="Lọc lịch hẹn và danh sách tiếp đón"
        muc={[
          { ma: "tat_ca", nhan: "Tất cả", dem: dem?.tat_ca },
          { ma: "chua_den", nhan: "Chưa check-in", dem: dem?.chua_den },
          { ma: "da_den", nhan: "Đã check-in", dem: dem?.da_den },
        ]}
        chon={loc.tab}
        onChon={(tab) => onDoi({ ...loc, tab })}
      />
      {themKhachDuoc ? (
        <Link href={hrefThemKhach()} className={`${buttonClass("primary", "lg")} sm:ml-auto`}>
          + Thêm khách hàng
        </Link>
      ) : null}
    </div>
  );
}
