// PHIÊN ĐĂNG NHẬP ĐÃ CHẾT → về /login kèm lời giải thích, không để người dùng kẹt.
//
// ── VÌ SAO CÓ FILE NÀY (02/10/2026) ─────────────────────────────────────────
// Mỗi đêm 03:30 staging nạp lại từ bản sao prod (scripts/staging-nap-ban-sao.sh)
// và `TRUNCATE auth.users CASCADE` xoá sạch auth.sessions / auth.refresh_tokens.
// Sáng ra trình duyệt vẫn cầm cookie phiên cũ → GoTrue: "Invalid Refresh Token:
// Refresh Token Not Found". Trang đang mở gọi /api nhận 401 mà giao diện KHÔNG
// đi đâu cả — người dùng tưởng staging hỏng. Prod cũng có thể gặp (đổi mật khẩu,
// thu hồi phiên, GoTrue mất dữ liệu) nên vá ở ứng dụng, không chỉ ở script nạp.
//
// Hai nửa, cùng dùng các hàm thuần ở đây (test được, không cần trình duyệt):
//   * proxy.ts — request TRANG mà có cookie phiên nhưng không ra người dùng →
//     xoá cookie rồi chuyển /login?het_phien=1.
//   * components/GacHetPhien.tsx — fetch từ trình duyệt tới /api của mình nhận
//     401 → chuyển /login?het_phien=1.

export const THAM_SO_HET_PHIEN = "het_phien";
export const DUONG_DANG_NHAP_HET_PHIEN = `/login?${THAM_SO_HET_PHIEN}=1`;

/** Trang công khai — khớp PUBLIC_PATHS của proxy.ts; ở đây không chuyển hướng. */
const TRANG_KHONG_GAC = ["/login", "/auth", "/forgot-password", "/reset-password"];

export function laTrangCongKhai(pathname: string): boolean {
  return TRANG_KHONG_GAC.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

interface LoiXacThuc {
  name?: string;
  status?: number;
}

/** Lỗi do mạng / GoTrue đang bận — KHÔNG có nghĩa là phiên chết. */
function loiTamThoi(loi: LoiXacThuc | null | undefined): boolean {
  if (!loi) return false;
  if (loi.name === "AuthRetryableFetchError") return true;
  return typeof loi.status === "number" && (loi.status === 0 || loi.status >= 500);
}

export type KetQuaKhongCoNguoiDung = "het_phien" | "chua_dang_nhap";

/**
 * Proxy không ra được người dùng. Có cookie phiên mà vẫn không ra → phiên đã
 * chết (refresh token không còn, session bị xoá…) → phải xoá cookie và nói rõ.
 * Chưa có cookie (chưa từng đăng nhập) hoặc lỗi tạm thời (mạng/GoTrue bận) →
 * giữ hành vi cũ: chỉ về /login, không xoá gì, không báo "hết phiên".
 */
export function phanLoaiKhongCoNguoiDung(
  loi: LoiXacThuc | null | undefined,
  coCookiePhien: boolean,
): KetQuaKhongCoNguoiDung {
  if (!coCookiePhien || loiTamThoi(loi)) return "chua_dang_nhap";
  return "het_phien";
}

/** Tên cookie phiên (kể cả các mảnh `.0`, `.1` khi token dài, và code-verifier). */
export function laCookiePhien(ten: string, goc: string): boolean {
  return ten === goc || ten.startsWith(`${goc}.`) || ten === `${goc}-code-verifier`;
}

export function cookiePhienCanXoa(tenCacCookie: string[], goc: string): string[] {
  return tenCacCookie.filter((t) => laCookiePhien(t, goc));
}

/**
 * Phía trình duyệt: có nên chuyển về /login không? Chỉ khi /api của CHÍNH MÌNH
 * (cùng origin, đường dẫn bắt đầu `/api/`) trả 401 và đang không ở trang công
 * khai (tránh vòng lặp).
 */
export function nenVeDangNhapKhiGap401(opts: {
  status: number;
  url: string;
  origin: string;
  pathnameHienTai: string;
}): boolean {
  if (opts.status !== 401) return false;
  let u: URL;
  try {
    u = new URL(opts.url, opts.origin);
  } catch {
    return false;
  }
  if (u.origin !== opts.origin) return false;
  if (!u.pathname.startsWith("/api/")) return false;
  return !laTrangCongKhai(opts.pathnameHienTai);
}
