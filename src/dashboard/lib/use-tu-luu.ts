"use client";

// Móc React cho hàng đợi tự lưu (`lib/tu-luu.ts`). Một màn gọi:
//
//   const tl = useTuLuu({ gui, choMs: 1500 });
//   onChange → cập nhật ref dữ liệu → tl.danhDau()
//   <TrangThaiLuu tt={tl.trangThai} onLuuNgay={tl.luuNgay} />
//   Hoàn tất → if (!(await tl.luuNgay())) báo lỗi, không gửi
//
// Móc lo phần "không mất chữ" mà từng màn trước tự làm (và làm thiếu):
//   · rời màn (đổi khách, đóng khung) → lưu nốt, không xoá hẹn im lặng;
//   · đóng tab / tải lại khi còn chưa lưu → trình duyệt hỏi "Rời trang?", đồng
//     thời bắn lưu ngay; trang chết thật thì gửi `keepalive`;
//   · ẩn tab (điện thoại chuyển app) → lưu ngay, vì trình duyệt có thể giết trang;
//   · mạng về lại (`online`) → lưu ngay phần đang lỗi.
//
// `gui` đọc BẢN MỚI NHẤT từ ref của màn (ghi ref trong sự kiện gõ), không nhận
// dữ liệu qua tham số.

import { useCallback, useEffect, useState } from "react";

import { HangDoiLuu, TRANG_THAI_DAU, type KetQuaGui, type TrangThaiLuu } from "./tu-luu";

export type { KetQuaGui, TrangThaiLuu } from "./tu-luu";

export interface TuLuu {
  trangThai: TrangThaiLuu;
  /** Có thay đổi mới — hẹn lưu sau khoảng lặng. */
  danhDau: () => void;
  /** Lưu ngay và đợi. true = máy chủ đã có hết. */
  luuNgay: () => Promise<boolean>;
  /** Vừa nạp lại bản máy chủ — bỏ phần chưa lưu, không gửi. */
  lamSach: () => void;
}

export function useTuLuu({
  gui,
  choMs,
  tat = false,
}: {
  gui: (keepalive: boolean) => Promise<KetQuaGui>;
  choMs: number;
  /** Chỉ đọc: không hỏi khi rời trang, không gửi gì. */
  tat?: boolean;
}): TuLuu {
  const [trangThai, setTrangThai] = useState<TrangThaiLuu>(TRANG_THAI_DAU);
  const [hangDoi] = useState(() => new HangDoiLuu({ gui, choMs, onDoi: setTrangThai }));
  // Closure `gui` mới nhất (visit, phiếu, revision… của lần render này). Khi
  // màn bị gỡ, hàng đợi giữ closure CUỐI — lưu nốt đúng lượt cũ.
  useEffect(() => {
    hangDoi.datGui(gui);
  }, [hangDoi, gui]);

  useEffect(() => {
    if (tat) return;
    const hoiRoi = (e: BeforeUnloadEvent) => {
      const t = hangDoi.trangThai;
      if (!t.chua_luu) return;
      // Trình duyệt hiện hộp "Rời trang?" — trong lúc người đọc, lưu luôn.
      void hangDoi.luuNgay();
      e.preventDefault();
      e.returnValue = "";
    };
    const khiAn = () => {
      if (document.visibilityState === "hidden" && hangDoi.trangThai.chua_luu) {
        void hangDoi.luuNgay();
      }
    };
    const khiChet = () => hangDoi.guiKhiRoiTrang();
    const coMang = () => {
      if (hangDoi.trangThai.chua_luu) void hangDoi.luuNgay();
    };
    window.addEventListener("beforeunload", hoiRoi);
    window.addEventListener("pagehide", khiChet);
    window.addEventListener("online", coMang);
    document.addEventListener("visibilitychange", khiAn);
    return () => {
      window.removeEventListener("beforeunload", hoiRoi);
      window.removeEventListener("pagehide", khiChet);
      window.removeEventListener("online", coMang);
      document.removeEventListener("visibilitychange", khiAn);
    };
  }, [hangDoi, tat]);

  // Rời màn (đổi khách → key đổi → màn này bị gỡ): LƯU NỐT chứ không xoá hẹn.
  // `gui` trong ref vẫn là closure của lượt cũ, nên ghi đúng chỗ.
  useEffect(
    () => () => {
      void hangDoi.luuNgay();
    },
    [hangDoi],
  );

  const danhDau = useCallback(() => {
    if (!tat) hangDoi.danhDau();
  }, [hangDoi, tat]);
  const luuNgay = useCallback(() => hangDoi.luuNgay(), [hangDoi]);
  const lamSach = useCallback(() => hangDoi.lamSach(), [hangDoi]);

  return { trangThai, danhDau, luuNgay, lamSach };
}
