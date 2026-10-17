/** Chỉ trình bày/tìm cục bộ; máy chủ quyết số nào hợp lệ và nơi nào cần che. */
const MA_HAI_SO = new Set([
  "20", "27", "30", "31", "32", "33", "34", "36", "39", "40", "41", "43",
  "44", "45", "46", "47", "48", "49", "51", "52", "53", "54", "55", "56",
  "57", "58", "60", "61", "62", "63", "64", "65", "66", "81", "82", "84",
  "86", "90", "91", "92", "93", "94", "95", "98",
]);

function chuoi(sdt: unknown): string | null {
  return typeof sdt === "string" || typeof sdt === "number"
    ? String(sdt) || null
    : null;
}

function tachQuocTe(s: string): [string, string] | null {
  if (!/^\+[1-9][0-9]{7,14}$/.test(s)) return null;
  const n = s[1] === "1" || s[1] === "7" ? 1 : MA_HAI_SO.has(s.slice(1, 3)) ? 2 : 3;
  return [s.slice(0, n + 1), s.slice(n + 1)];
}

export function dinhDangSdt(sdt: unknown): string | null {
  const goc = chuoi(sdt);
  if (goc === null) return null;
  const s = goc.replace(/\s+/g, "");
  if (/^\d{10}$/.test(s)) return `${s.slice(0, 4)} ${s.slice(4, 7)} ${s.slice(7)}`;
  const qt = tachQuocTe(s);
  if (!qt) return goc;
  const [ma, so] = qt;
  return `${ma} ${so.slice(0, -7)} ${so.slice(-7, -4)} ${so.slice(-4)}`.replace(/ +/g, " ");
}

export function cheSdt(sdt: unknown): string | null {
  const goc = chuoi(sdt);
  if (goc === null) return null;
  // Payload đã che được giữ nguyên: nơi gọi có thể nhận sẵn sdt_che từ API.
  if (goc.includes("•") || goc.includes("*")) return goc;
  const s = goc.replace(/\s+/g, "");
  if (/^\d{10}$/.test(s)) return `${s.slice(0, 4)} ••• ${s.slice(-3)}`;
  const qt = tachQuocTe(s);
  if (!qt) return goc;
  const [ma, so] = qt;
  return `${ma} ${so.slice(0, Math.max(0, so.length - 7))} ••• ${so.slice(-4)}`.replace(/ +/g, " ");
}

function chuSo(sdt: unknown): string {
  const s = chuoi(sdt);
  if (!s || s.length > 256 || !/^[+0-9\s().-]+$/.test(s)) return "";
  let so = s.replace(/[^0-9]/g, "");
  if (so.startsWith("00")) so = so.slice(2);
  if (/^84[35789][0-9]{0,8}$/.test(so)) so = `0${so.slice(2)}`;
  return so;
}

export function soSdtKhop(q: unknown, sdt: unknown): boolean {
  const tim = chuSo(q);
  return tim.length >= 3 && chuSo(sdt).includes(tim);
}
