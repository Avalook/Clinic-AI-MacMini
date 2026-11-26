"use client";

// Hỏi máy chủ số ngày dùng / ngày hết / gợi ý SL / câu in cho các dòng đang kê
// (PR E). Màn không tự tính — chỉ gửi ô đang gõ, nhận kết quả, chờ 400 ms sau lần
// gõ cuối để khỏi hỏi dồn.

import { useEffect, useMemo, useState } from "react";

import type { KetQuaTinh } from "@/lib/cach-dung";
import type { DongThuoc } from "@/lib/phieu-kham";

export function useTinhCachDung(
  visitId: string | undefined,
  dong: DongThuoc[],
  kinh: { kinh_lan_cuoi: string; chu_ky: string },
  /** Mốc chu kỳ bác sĩ sửa tay theo vị trí dòng (khung "Tính ngày uống theo kỳ kinh"). */
  moc: Record<number, { tu_ngay: number; den_ngay: number }> = {},
): KetQuaTinh | null {
  const [traLoi, setTraLoi] = useState<{ goi: string; kq: KetQuaTinh } | null>(null);
  const goi = useMemo(
    () =>
      JSON.stringify({
        visit_id: visitId,
        kinh_lan_cuoi: kinh.kinh_lan_cuoi || null,
        chu_ky: kinh.chu_ky || null,
        dong: dong.map((d, i) => ({
          drug_catalog_id: d.drug_catalog_id,
          so_luong: d.so_luong,
          don_vi: d.don_vi,
          ct: d.drug_catalog_id ? (d.cach_dung_ct ?? null) : null,
          chu: d.cach_dung,
          ...(moc[i] ?? {}),
        })),
      }),
    [visitId, dong, kinh.kinh_lan_cuoi, kinh.chu_ky, moc],
  );
  useEffect(() => {
    if (!visitId || dong.length === 0) return;
    let bo = false;
    const t = setTimeout(async () => {
      try {
        const r = await fetch("/api/thuoc/cach-dung-tinh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: goi,
        });
        if (bo || !r.ok) return;
        const kq = (await r.json()) as KetQuaTinh;
        if (!bo) setTraLoi({ goi, kq });
      } catch {
        // Mất mạng: không hiện đề xuất cho gói chưa tính. Lần gõ sau hỏi lại.
      }
    }, 400);
    return () => {
      bo = true;
      clearTimeout(t);
    };
  }, [goi, visitId, dong.length]);
  return traLoi?.goi === goi ? traLoi.kq : null;
}
