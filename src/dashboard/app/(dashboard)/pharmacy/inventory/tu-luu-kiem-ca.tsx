"use client";

// TỰ LƯU NHÁP PHIẾU KIỂM KÊ CA (Tuyền 20/11/2026: "đang nhập dở ở kiểm kê mà sang
// tab khác thì nó mất"). Móc React mỏng quanh hàng đợi chung (`lib/use-tu-luu`:
// tuần tự, gộp phím gõ, lưu nốt khi rời màn / ẩn tab, `keepalive` khi đóng tab, tự
// thử lại khi rớt mạng). Phần quyết định — dòng gửi, một đường ghi, xả trước khi
// đổi phiếu — ở `gui-dem.ts`, test bằng hàng đợi thật.

import { useCallback, useEffect, useRef } from "react";

import type { TrangThaiLuu } from "@/lib/tu-luu";
import { useTuLuu } from "@/lib/use-tu-luu";

import {
  doiPhieu,
  luuTay,
  taoGuiDem,
  TRAN_KEEPALIVE,
  type DongGui,
  type ManDem,
} from "./gui-dem";

/** 1,5 giây sau phím cuối — như các màn tự lưu khác. */
const CHO_LUU_MS = 1_500;

export function useTuLuuKiemCa<P>({
  man,
  tat,
  url,
  daLuu,
  tuChoi,
}: {
  /** Trạng thái MỚI NHẤT của màn (render này) — hàng đợi đọc lúc gửi. */
  man: ManDem | null;
  /** Không quyền ghi / chưa có phiếu / phiếu đã chốt. */
  tat: boolean;
  url: (phieuId: string) => string;
  /** Máy chủ trả phiếu sau khi lưu. KHÔNG nạp lại ô nhập (đè phím đang gõ). */
  daLuu: (phieuId: string, phieu: P) => void;
  /** 409: phiếu đã chốt / đổi ở máy khác → màn báo `cau` và nạp lại phiếu. */
  tuChoi: (phieuId: string, cau: string) => void;
}) {
  const thuCong = useRef(false);
  // 409 → bỏ phần chưa lưu (thôi hỏi "Rời trang?" mãi) rồi màn nạp lại. Hẹn sau
  // một nhịp: hàng đợi đang xử lý chính kết quả lỗi này.
  const lamSachRef = useRef<() => void>(() => {});
  const gui = useCallback(
    (keepalive: boolean) =>
      taoGuiDem({
        doc: () => man,
        laThuCong: () => thuCong.current,
        post: async (pid: string, dong: DongGui[], ka: boolean) => {
          const body = JSON.stringify({ dong });
          const r = await fetch(url(pid), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body,
            keepalive: ka && body.length < TRAN_KEEPALIVE,
          }).catch(() => null);
          return r ? { status: r.status, data: await r.json().catch(() => null) } : null;
        },
        daLuu: (pid, p) => daLuu(pid, p as P),
        tuChoi: (pid, cau) =>
          setTimeout(() => {
            lamSachRef.current();
            tuChoi(pid, cau);
          }),
      })(keepalive),
    [man, url, daLuu, tuChoi],
  );
  const tl = useTuLuu({ gui, choMs: CHO_LUU_MS, tat });
  const { danhDau, luuNgay, lamSach } = tl;
  useEffect(() => {
    lamSachRef.current = lamSach;
  }, [lamSach]);
  return {
    trangThai: tl.trangThai,
    /** Có phím gõ mới — hẹn tự lưu. */
    danhDau,
    /** "Lưu nháp" / trước "Chốt": cùng hàng đợi, không POST riêng. */
    luuTay: useCallback(
      () => luuTay({ danhDau, luuNgay }, (b) => (thuCong.current = b)),
      [danhDau, luuNgay],
    ),
    /** Xả phần chưa lưu rồi mới đổi ca / ngày / phiếu; xả hỏng → không đổi, `false`. */
    doiPhieu: useCallback(
      (lam: () => void | Promise<void>) => doiPhieu({ danhDau, luuNgay }, lam),
      [danhDau, luuNgay],
    ),
  };
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
