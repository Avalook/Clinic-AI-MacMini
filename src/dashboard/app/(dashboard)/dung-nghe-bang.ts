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
// `RealtimeRefresher` phát tin "không rõ" (`t: null`) nên màn tự bắt kịp.
//
// THEO MỘT LƯỢT (16/11/2026). Tin mang id lượt (`v`, `lib/tin-theo-luot`). Màn vẽ
// dữ liệu của MỘT lượt truyền `{ luot: visitId }` để bỏ tin của lượt khác — đo prod
// 13–16/11, thiếu lọc này một lượt ghi bất kỳ kéo theo ~15 GET từ các phiếu đang
// mở. Màn DANH SÁCH (bàn khám, phòng, hành trình…) thì KHÔNG truyền: nó cần mọi lượt.

import { useEffect, useRef, useSyncExternalStore } from "react";

import { taoMotLuot } from "../../lib/mot-luot";
import {
  NHIP_NGHE_TIN,
  SU_KIEN_BANG,
  taoNhipLamMoi,
  trangThaiDong,
  type TrangThaiDong,
} from "../../lib/nhip-lam-moi";
import { canHoiLai, type TinBang } from "../../lib/tin-theo-luot";

/**
 * Gọi `khiDoi` (đã gộp nhịp 250ms, lệch ngẫu nhiên 0–400ms) khi một trong các
 * `bang` đổi, hoặc khi có tin không rõ bảng (`null`). Tên bảng là tên trong
 * Postgres — bảng ấy phải có trigger `trg_notify_*`, nếu không thì nghe mãi cũng im.
 *
 * MỘT LƯỢT MỘT LÚC (14/10/2026). `khiDoi` trả lời hứa (vd. `() => tai()` với `tai`
 * là hàm async) thì hook chờ nó xong mới chạy lượt kế: tin tới trong lúc đang tải
 * chỉ để lại ĐÚNG MỘT lượt nối đuôi — không mở lượt thứ hai song song. Trả `void`
 * (vd. tăng một bộ đếm cho effect) thì hành vi y như cũ; muốn gộp lượt tải ở
 * trường hợp ấy thì gộp ở chỗ đọc (`lib/doc-gop`).
 *
 * `luot`: id lượt màn đang vẽ — tin của lượt KHÁC bị bỏ; tin không mang id lượt
 * (bảng không có cột lượt) hoặc không rõ thì vẫn hỏi lại (`canHoiLai`).
 */
export function useNgheBang(
  bang: readonly string[],
  khiDoi: () => void | Promise<unknown>,
  { luot }: { luot?: string | null } = {},
): void {
  // Qua ref: đổi khách đang xem không phải gỡ/gắn lại tay nghe.
  const luotRef = useRef(luot);
  useEffect(() => {
    luotRef.current = luot;
  }, [luot]);
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
    const motLuot = taoMotLuot();
    const nhip = taoNhipLamMoi({
      lamMoi: () => {
        motLuot(async () => {
          await khiDoiRef.current();
        }).catch((loi) => console.error("[nghe-bang] lượt tải lại lỗi:", loi));
      },
      dangAn: () => document.visibilityState === "hidden",
      hen: (fn, ms) => setTimeout(fn, ms),
      huy: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
      ...NHIP_NGHE_TIN,
    });
    const nghe = (ev: Event) => {
      const tin = (ev as CustomEvent<TinBang | null>).detail;
      if (canHoiLai(tin, can, luotRef.current)) nhip.nhan();
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
