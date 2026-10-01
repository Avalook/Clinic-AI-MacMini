/** Chia danh sách lượt để URL không vượt giới hạn proxy / trình duyệt. */
export function chiaLoLamThem(ids: readonly string[], moiLo = 250): string[][] {
  const sach = [...new Set(ids.filter(Boolean))];
  const lo: string[][] = [];
  for (let i = 0; i < sach.length; i += moiLo) lo.push(sach.slice(i, i + moiLo));
  return lo;
}
