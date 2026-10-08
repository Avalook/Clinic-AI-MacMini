export interface DongCoLuaChon {
  id: string;
  loai: "kham" | "chi_dinh" | "phu_thu" | "vat_tu" | "lieu_trinh";
  order_id?: string | null;
  gia: number | null;
  chon: boolean;
  trong_lua_chon: boolean;
}

export function dongDangChon(
  dong: DongCoLuaChon,
  chon: ReadonlySet<string>,
  orderIdsCoTheDoi?: ReadonlySet<string>,
): boolean {
  if (dong.loai === "phu_thu" && dong.order_id) {
    return orderIdsCoTheDoi?.has(dong.order_id) === false ? dong.chon : chon.has(dong.order_id);
  }
  return dong.trong_lua_chon ? chon.has(dong.id) : dong.chon;
}

export function tongTheoLuaChon(
  dong: DongCoLuaChon[],
  chon: ReadonlySet<string>,
  orderIdsCoTheDoi?: ReadonlySet<string>,
): number {
  return dong
    .filter((d) => dongDangChon(d, chon, orderIdsCoTheDoi))
    .reduce((tong, d) => tong + (d.gia ?? 0), 0);
}

export function giaNhap(vao: string): number | null {
  const sach = vao.replaceAll(".", "").replaceAll(",", "").trim();
  if (!/^\d+$/.test(sach)) return null;
  const gia = Number(sach);
  return Number.isSafeInteger(gia) ? gia : null;
}

export function giaNhapBang(vao: string, hienTai: number | null): boolean {
  const gia = giaNhap(vao);
  return gia !== null && hienTai !== null && gia === hienTai;
}
