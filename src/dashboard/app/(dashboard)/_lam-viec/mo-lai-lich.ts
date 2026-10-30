// HOÀN TÁC huỷ / không đến (30/10/2026) — ống dẫn cho toast "Hoàn tác" và nút
// Hoàn tác trên dòng (bảng Lịch hẹn, danh sách tiếp đón, khung khách).
//
// Không chứa luật nào: về trạng thái nào, ai được, khung còn chỗ không — máy
// chủ quyết (`BookingService.mo_lai`); câu từ chối hiện nguyên văn.

import type { KetQuaHoanTac } from "@/components/ui/NutHoanTac";
import { nhanLoi } from "@/lib/loi-api";

export async function moLaiLich(id: string): Promise<KetQuaHoanTac> {
  try {
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action: "reopen" }),
    });
    if (res.ok) return { ok: true };
    return { ok: false, loi: nhanLoi(await res.json().catch(() => null), "Không mở lại được lịch.") };
  } catch {
    return { ok: false, loi: "Mất kết nối — lịch CHƯA mở lại. Bấm lại." };
  }
}
