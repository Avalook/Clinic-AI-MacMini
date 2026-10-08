/** Chỉ cho đi tiếp tới đường TRONG trang (`/…`), không `//host` hay `https:` —
 *  `?next=` lấy từ URL nên không được thành cửa chuyển hướng ra ngoài. */
export function duongVeAnToan(next: string | null | undefined): string {
  const v = (next ?? "").trim();
  if (!v.startsWith("/") || v.startsWith("//") || v.startsWith("/\\")) return "/home";
  if (v.startsWith("/chon-co-so")) return "/home";
  return v;
}
