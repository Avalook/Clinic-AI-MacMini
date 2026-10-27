/** "0914378212" → "0914 378 212" (đọc qua điện thoại, dò bằng mắt dễ hơn).
 *  Không đủ 10 số thì trả nguyên văn; rỗng → null. */
export function sdtDoc(sdt: string | number | null | undefined): string | null {
  if (sdt === null || sdt === undefined || sdt === "") return null;
  const s = String(sdt).replace(/\s+/g, "");
  return /^\d{10}$/.test(s) ? `${s.slice(0, 4)} ${s.slice(4, 7)} ${s.slice(7)}` : String(sdt);
}
