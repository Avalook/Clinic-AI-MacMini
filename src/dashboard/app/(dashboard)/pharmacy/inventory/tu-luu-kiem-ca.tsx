"use client";

// TỰ LƯU NHÁP PHIẾU KIỂM KÊ CA (Tuyền 20/11/2026: "đang nhập dở ở kiểm kê mà sang
// tab khác thì nó mất"). Trước đây số đếm chỉ nằm trong state của màn cho tới khi
// bấm "Lưu nháp" — đổi tab Kho/Quầy, đổi màn là mất cả số lẫn GIỜ ĐẾM từng dòng.
//
// Dùng lại hàng đợi chung (`lib/use-tu-luu`): lưu tuần tự, gộp phím gõ, lưu nốt khi
// rời màn / ẩn tab, gửi `keepalive` khi đóng tab, tự thử lại khi rớt mạng. Mỗi bản
// gửi mang MÃ PHIẾU lúc gõ — đổi ca / ngày giữa chừng thì bản cũ vẫn về đúng phiếu
// cũ, không bao giờ đổ số của ca này sang phiếu ca khác.

import { useCallback, useRef } from "react";

import { LOI_MAT_KET_NOI, nenThuLai, type TrangThaiLuu } from "@/lib/tu-luu";
import { useTuLuu, type KetQuaGui } from "@/lib/use-tu-luu";

export interface DongGui {
  drug_catalog_id: string;
  don_vi: string;
  dem: string | null;
  dem_luc: string | null;
}

/** 1,5 giây sau phím cuối — như các màn tự lưu khác. */
const CHO_LUU_MS = 1_500;

export function useTuLuuKiemCa<P>({
  tat,
  url,
  daLuu,
}: {
  /** Không quyền ghi / chưa có phiếu / phiếu đã chốt. */
  tat: boolean;
  url: (phieuId: string) => string;
  /** Máy chủ trả phiếu sau khi lưu. KHÔNG nạp lại ô nhập: phím gõ trong lúc
   *  lần lưu đang bay sẽ bị đè. */
  daLuu: (phieuId: string, phieu: P) => void;
}) {
  const ban = useRef<{ pid: string; dong: DongGui[] } | null>(null);
  const gui = useCallback(
    async (keepalive: boolean): Promise<KetQuaGui> => {
      const b = ban.current;
      if (!b || b.dong.length === 0) return { ok: true };
      const r = await fetch(url(b.pid), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dong: b.dong }),
        keepalive,
      }).catch(() => null);
      if (!r) return { ok: false, loi: LOI_MAT_KET_NOI, thuLai: true };
      const d = (await r.json().catch(() => null)) as
        | (P & { message?: string; detail?: unknown })
        | null;
      if (!r.ok || !d) {
        const cau = d?.message ?? (typeof d?.detail === "string" ? d.detail : null);
        return { ok: false, loi: cau ?? "Không lưu được số đếm.", thuLai: nenThuLai(r.status) };
      }
      if (ban.current === b) ban.current = null;
      daLuu(b.pid, d);
      return { ok: true };
    },
    [url, daLuu],
  );
  const tl = useTuLuu({ gui, choMs: CHO_LUU_MS, tat });
  const { danhDau } = tl;
  const ghi = useCallback(
    (pid: string, dong: DongGui[]) => {
      ban.current = { pid, dong };
      danhDau();
    },
    [danhDau],
  );
  return { trangThai: tl.trangThai, luuNgay: tl.luuNgay, ghi };
}

function gioVn(d: Date): string {
  return d.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

/** Một dòng chữ cạnh nút "Lưu nháp" — không thêm nút (nút ấy vẫn là lưu ngay). */
export function ChuTuLuu({ tt }: { tt: TrangThaiLuu }) {
  if (tt.loi) {
    return (
      <span role="status" className="text-meta text-danger">
        Lưu lỗi{tt.tu_thu_lai ? " — đang tự thử lại" : ""}: {tt.loi}
      </span>
    );
  }
  const chu = tt.dang_luu
    ? "Đang lưu…"
    : tt.chua_luu
      ? "Chưa lưu — tự lưu sau khi ngừng gõ"
      : tt.luu_luc
        ? `Đã tự lưu ${gioVn(tt.luu_luc)}`
        : "Tự lưu khi gõ";
  return (
    <span role="status" className="text-meta text-ink-muted">
      {chu}
    </span>
  );
}
