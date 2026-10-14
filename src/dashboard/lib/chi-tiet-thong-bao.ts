/** Chuông tự động nêu nguồn; chuông người thật giữ cách trình bày cũ. */
export function chiTietThongBao(t: {
  noi_dung: string;
  nguoi_goi: string | null;
  nhan_nguon?: string | null;
  chi_hoan_tac?: boolean;
}): string {
  const nguon = t.nhan_nguon
    ? `${t.nhan_nguon} · `
    : t.nguoi_goi && !t.chi_hoan_tac ? `${t.nguoi_goi} gọi · ` : "";
  return nguon + t.noi_dung;
}
