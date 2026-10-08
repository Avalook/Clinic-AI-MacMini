"use client";

// Chip liệu trình cho MỘT LÔ lượt đang hiện (08/10/2026) — phòng dịch vụ, tiếp
// đón, hàng chờ bàn khám. Một lần gọi `/api/lieu-trinh/chip?luot=…` cho cả danh
// sách (không gọi từng dòng); gọi lại khi tập lượt đổi hoặc bảng liệu trình đổi
// (gắn / gỡ buổi, trả trước phủ buổi). Chỉ THÊM chữ lên dòng có sẵn — không đổi
// lọc / đếm / sắp xếp của màn nào.
//
// Không đọc được (403 với tài khoản không có quyền xem liệu trình, mất mạng) →
// `null`: màn vẽ như chưa có chip, không báo lỗi đè lên việc chính.

import { useCallback, useEffect, useState } from "react";

import { khoaLuot, type ChipLieuTrinh } from "@/lib/lieu-trinh";

import { useNgheBang } from "../dung-nghe-bang";

export function useChipLieuTrinh(visitIds: readonly (string | null | undefined)[]): ChipLieuTrinh | null {
  const khoa = khoaLuot(visitIds);
  const [chip, setChip] = useState<{ khoa: string; data: ChipLieuTrinh } | null>(null);
  const [lan, setLan] = useState(0);

  useEffect(() => {
    if (!khoa) return;
    let huy = false;
    void fetch(`/api/lieu-trinh/chip?luot=${encodeURIComponent(khoa)}`, { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<ChipLieuTrinh>) : null))
      .catch(() => null)
      .then((d) => {
        if (!huy && d) setChip({ khoa, data: d });
      });
    return () => {
      huy = true;
    };
  }, [khoa, lan]);

  const napLai = useCallback(() => setLan((n) => n + 1), []);
  useNgheBang(["lieu_trinh", "lieu_trinh_buoi"], napLai);

  return khoa && chip ? chip.data : null;
}
