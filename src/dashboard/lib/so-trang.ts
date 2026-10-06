// Dãy số trang cho thanh "‹ 1 … 4 5 [6] 7 8 … 175 ›" — MỘT chỗ tính, thuần,
// có bài kiểm (`so-trang.test.mts`). Thanh vẽ ở `components/ui/ThanhSoTrang`.
//
// Luôn có trang đầu + trang cuối + `canh` trang mỗi bên trang đang xem. Khoảng
// hở đúng MỘT trang thì in luôn số ấy thay vì "…" ("1 2 3", không "1 … 3").
// `hep` = mục còn hiện trên màn hẹp (375px): chỉ trang đang xem ± 1, để thanh
// không tràn ngang (DESIGN.md §7 — ô bấm điện thoại 40px).

export type MucSoTrang =
  | { loai: "so"; so: number; hep: boolean }
  | { loai: "cach"; khoa: string; hep: false };

function soNguyenDuong(v: unknown): number | null {
  const n = typeof v === "number" ? v : Number.NaN;
  return Number.isInteger(n) && n >= 1 ? n : null;
}

/** Đầu vào rác (NaN, âm, số thực, không phải số) → coi như 1 trang / trang 1. */
export function cacSoTrang(trang: unknown, soTrang: unknown, canh = 2): MucSoTrang[] {
  const tong = soNguyenDuong(soTrang) ?? 1;
  const hien = Math.min(soNguyenDuong(trang) ?? 1, tong);
  const k = Math.max(0, Math.floor(canh));
  const chon = new Set<number>([1, tong]);
  for (let i = hien - k; i <= hien + k; i++) {
    if (i >= 1 && i <= tong) chon.add(i);
  }
  const day = [...chon].sort((a, b) => a - b);
  const ra: MucSoTrang[] = [];
  let truoc = 0;
  for (const so of day) {
    if (so - truoc === 2) {
      ra.push({ loai: "so", so: so - 1, hep: Math.abs(so - 1 - hien) <= 1 });
    } else if (so - truoc > 2) {
      ra.push({ loai: "cach", khoa: `cach-${truoc}`, hep: false });
    }
    ra.push({ loai: "so", so, hep: Math.abs(so - hien) <= 1 });
    truoc = so;
  }
  return ra;
}

/** "Hiển thị x–y trên N hồ sơ" — số đầu / cuối của trang (đếm từ 1). */
export function khoangDong(
  trang: number,
  motTrang: number,
  soDongTrang: number,
): { tu: number; den: number } {
  if (soDongTrang <= 0) return { tu: 0, den: 0 };
  const tu = (Math.max(1, trang) - 1) * Math.max(1, motTrang) + 1;
  return { tu, den: tu + soDongTrang - 1 };
}
