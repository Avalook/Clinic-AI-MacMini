"use client";

import { useEffect } from "react";
import {
  DUONG_DANG_NHAP_HET_PHIEN,
  nenVeDangNhapKhiGap401,
} from "../lib/het-phien";

/**
 * Gác 401 cho MỌI lời gọi /api từ trình duyệt (02/10/2026).
 *
 * Hơn 130 chỗ gọi `fetch("/api/...")` tự xử lý lỗi riêng, nên không có chỗ nào
 * để vá một lần. Bọc `window.fetch` MỘT lần ở đây: nhận 401 từ /api của chính
 * mình → phiên đã chết (xem lib/het-phien.ts) → về /login?het_phien=1. Phản hồi
 * vẫn trả nguyên cho nơi gọi, nên code cũ không đổi hành vi.
 */
export function GacHetPhien() {
  useEffect(() => {
    const goc = window.fetch;
    let daChuyen = false;
    window.fetch = async (...args: Parameters<typeof fetch>) => {
      const res = await goc.apply(window, args);
      if (!daChuyen) {
        const input = args[0];
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (
          nenVeDangNhapKhiGap401({
            status: res.status,
            url,
            origin: window.location.origin,
            pathnameHienTai: window.location.pathname,
          })
        ) {
          daChuyen = true;
          window.location.assign(DUONG_DANG_NHAP_HET_PHIEN);
        }
      }
      return res;
    };
    return () => {
      window.fetch = goc;
    };
  }, []);
  return null;
}
