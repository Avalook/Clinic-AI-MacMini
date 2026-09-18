// LUẬT CHÈN CHỖ TRONG HÀNG ĐỢI — thuần, không chạm mạng.
//
// Tách khỏi hook để `node --test` nạp được: bài kiểm không chạy qua bundler nên
// không hiểu alias `@/`, mà hook thì phải import React. Cùng lý do với
// `lib/khach-moi-cu.ts`.

/** Thả `id` ngay TRƯỚC `dich` trong hàng đang hiện (dich = null → xuống cuối).
 *
 *  Trả về cặp (người đứng SAU chỗ thả, người đứng TRƯỚC chỗ thả) đúng như
 *  `POST /queue/keo` đòi. `null` = đích không còn trong hàng (vừa được gọi vào
 *  khám) — lúc ấy không ghi gì, để người dùng kéo lại trên hàng mới. */
export function choTruoc(
  dsIds: string[],
  id: string,
  dich: string | null,
): { sau: string | null; truoc: string | null } | null {
  const con = dsIds.filter((x) => x !== id);
  if (dich === null) return { sau: con.at(-1) ?? null, truoc: null };
  const i = con.indexOf(dich);
  if (i < 0) return null;
  return { sau: i > 0 ? con[i - 1]! : null, truoc: con[i]! };
}
