// Quét tem ở quầy thuốc: nói ĐÚNG lý do lô không dùng được cho dòng đơn.
// Máy chủ trả `lo_bi_loai` (xem `ban_thuoc_service.ly_do_lo_bi_loai`); ở đây chỉ
// chọn chữ — không luật chọn lô nào.

/** Lô của thuốc BỊ LOẠI khỏi gợi ý của dòng đơn + lý do (máy chủ trả, chỉ để
 *  giải thích khi quét tem — không đổi luật chọn lô). */
export interface LoBiLoai {
  drug_batch_id: string;
  batch_code: string;
  ly_do: "KHAC_DON_VI" | "KHAC_CO_SO" | string;
  don_vi_lo: string | null;
  don_vi_ke: string | null;
}

/** Câu nói ĐÚNG lý do lô vừa quét không dùng được cho dòng đơn này. Không có
 *  lý do nào từ máy chủ thì rơi về câu chung. Hàm thuần — chỉ chọn chữ. */
export function cauLoKhongDungDuoc(
  loBiLoai: readonly LoBiLoai[] | undefined,
  loId: string | undefined,
  tenThuoc: string,
): string {
  const lo = loId ? loBiLoai?.find((b) => b.drug_batch_id === loId) : undefined;
  if (lo?.ly_do === "KHAC_DON_VI") {
    const theoLo = lo.don_vi_lo?.trim() || "đơn vị khác";
    const theoKe = lo.don_vi_ke?.trim() || "đơn vị khác";
    return `Lô ${lo.batch_code} tính theo ${theoLo}, đơn kê theo ${theoKe} — chưa giao theo lô được; giao không lô hoặc nhờ quản lý chỉnh đơn vị.`;
  }
  if (lo?.ly_do === "KHAC_CO_SO") {
    return `Lô ${lo.batch_code} thuộc kho cơ sở khác với đơn này — không dùng được cho dòng này.`;
  }
  return `Không có lô còn bán được của ${tenThuoc} dùng cho dòng đơn này.`;
}
