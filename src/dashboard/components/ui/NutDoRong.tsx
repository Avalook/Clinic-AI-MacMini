"use client";

/**
 * Nút "Thu gọn / Mở rộng" cỡ bảng (Tuyền 03/11/2026): đặt ở GÓC DƯỚI bảng, không
 * chen vào hàng nút lọc phía trên. Mỗi màn nhớ lựa chọn của người xem trên máy
 * này (localStorage) — chỉ là tiện ích hiển thị, mất thì về mặc định.
 */

import { useSyncExternalStore } from "react";
import ThanhTab from "./ThanhTab";

export type DoRong = "gon" | "rong";

const nghe = new Set<() => void>();

function doc(khoa: string): DoRong | null {
  try {
    const v = localStorage.getItem(`do-rong:${khoa}`);
    return v === "gon" || v === "rong" ? v : null;
  } catch {
    return null; // trình duyệt chặn lưu → dùng mặc định
  }
}

export function useDoRong(khoa: string, macDinh: DoRong): [DoRong, (d: DoRong) => void] {
  const doRong = useSyncExternalStore(
    (f) => {
      nghe.add(f);
      return () => nghe.delete(f);
    },
    () => doc(khoa) ?? macDinh,
    () => macDinh,
  );
  const doi = (d: DoRong) => {
    try {
      localStorage.setItem(`do-rong:${khoa}`, d);
    } catch {
      /* không lưu được: lần xem này giữ mặc định */
    }
    nghe.forEach((f) => f());
  };
  return [doRong, doi];
}

export default function NutDoRong({ doRong, onDoi }: { doRong: DoRong; onDoi: (d: DoRong) => void }) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 print:hidden">
      <span className="text-meta text-ink-muted">Cỡ bảng (màn to thì chọn Mở rộng để thấy hết cột)</span>
      <ThanhTab<DoRong>
        nhan="Cỡ bảng"
        chon={doRong}
        onChon={onDoi}
        muc={[{ ma: "gon", nhan: "Thu gọn" }, { ma: "rong", nhan: "Mở rộng" }]}
      />
    </div>
  );
}
