"use client";

// Nghe ké dòng SSE chung — cho màn TỰ FETCH, thứ router.refresh() không với tới.
//
// VÌ SAO CÓ (27/09/2026). Bốn màn — chuông thông báo, trưởng ca, check-out,
// và (bản cũ) lịch hẹn — từng tự mở `supabase.channel(...).on("postgres_changes")`.
// Đường ấy đã chết từ 06/08: Supabase Realtime cần một replication slot với
// plugin wal2json, và Postgres của mình từ chối ("library wal2json may not be
// used as an output plugin"). Kết quả đo trên prod 27/09: ~8.600 dòng ERROR mỗi
// ngày trong log database, và bốn màn ấy chưa từng nhận một tin tức thời nào —
// chúng sống bằng nhịp dự phòng của riêng mình.
//
// Tin thật của hệ thống đi LISTEN/NOTIFY → FastAPI SSE → `RealtimeRefresher`,
// và `RealtimeRefresher` phát lại MỖI tin thành `SU_KIEN_BANG` trên window.
// Hook này là cách nghe tin ấy mà KHÔNG mở thêm kết nối nào (xem
// `tests/dong-su-kien-boundary.test.mts` — mỗi EventSource thêm là một trong sáu
// kết nối HTTP/1.1 của trình duyệt bị giữ vĩnh viễn).
//
// Gộp nhịp qua `taoNhipLamMoi` — cùng luật với cả trang: một thao tác đụng vài
// bảng thành MỘT lượt hỏi lại, và tab đang ẩn không hỏi gì cả. Lúc tab hiện lại,
// `RealtimeRefresher` phát `null` ("không rõ bảng nào") nên màn tự bắt kịp.

import { useEffect, useRef, useSyncExternalStore } from "react";

import {
  SU_KIEN_BANG,
  taoNhipLamMoi,
  trangThaiDong,
  type TrangThaiDong,
} from "../../lib/nhip-lam-moi";

/**
 * Gọi `khiDoi` (đã gộp nhịp 250ms) khi một trong các `bang` đổi, hoặc khi có
 * tin không rõ bảng (`null`). Tên bảng là tên trong Postgres — bảng ấy phải có
 * trigger `trg_notify_*`, nếu không thì nghe mãi cũng im.
 */
export function useNgheBang(bang: readonly string[], khiDoi: () => void): void {
  // Qua ref: `khiDoi` thường là hàm khai trong thân component, mỗi lượt render
  // một bản mới. Đưa thẳng vào deps là gỡ/gắn lại tay nghe ở mỗi lượt render.
  const khiDoiRef = useRef(khiDoi);
  useEffect(() => {
    khiDoiRef.current = khiDoi;
  }, [khiDoi]);

  // Khoá bằng chuỗi: mảng khai tại chỗ là một mảng mới mỗi lượt render.
  const khoa = bang.join(",");

  useEffect(() => {
    const can = new Set(khoa.split(","));
    const nhip = taoNhipLamMoi({
      lamMoi: () => khiDoiRef.current(),
      dangAn: () => document.visibilityState === "hidden",
      hen: (fn, ms) => setTimeout(fn, ms),
      huy: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
    });
    const nghe = (ev: Event) => {
      const t = (ev as CustomEvent<string | null>).detail;
      if (t === null || can.has(t)) nhip.nhan();
    };
    window.addEventListener(SU_KIEN_BANG, nghe);
    return () => {
      window.removeEventListener(SU_KIEN_BANG, nghe);
      nhip.dung();
    };
  }, [khoa]);
}

/** Tình trạng dòng SSE chung — cho chỉ báo "cập nhật liên tục / mất kết nối".
 *  Máy chủ luôn vẽ `dang-noi`; trình duyệt nhận giá trị thật sau khi hydrate. */
export function useTrangThaiDong(): TrangThaiDong {
  return useSyncExternalStore(
    trangThaiDong.nghe,
    trangThaiDong.doc,
    () => "dang-noi",
  );
}
