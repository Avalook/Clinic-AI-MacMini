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

const chuan = (s: string | null | undefined): string => (s ?? "").normalize("NFC").trim().toLowerCase();

/** Dòng đơn KHÔNG có lô gợi ý, nhưng kho có lô của thuốc ấy tính theo đơn vị khác
 *  đơn kê (vd lô "hộp", đơn "gói"): nói thẳng hệ quả — giao được, kho KHÔNG tự
 *  trừ. Không có lô nào như vậy → null (giữ câu "kho chưa có lô"). Hàm thuần. */
export function cauKhoCoLoKhacDonVi(
  loBiLoai: readonly LoBiLoai[] | undefined,
  tenThuoc: string,
): string | null {
  const khac = (loBiLoai ?? []).filter((b) => b.ly_do === "KHAC_DON_VI");
  if (khac.length === 0) return null;
  const theoLo =
    [...new Set(khac.map((b) => b.don_vi_lo?.trim()).filter((x): x is string => !!x))].join(", ") ||
    "đơn vị khác";
  const theoKe = khac[0]?.don_vi_ke?.trim() || "đơn vị khác";
  return `Kho có ${tenThuoc} nhưng tính theo ${theoLo}, còn đơn này theo ${theoKe} — thu tiền và giao vẫn được, nhưng kho KHÔNG tự trừ (khác đơn vị). Nhập lô theo ${theoKe} hoặc báo quản lý.`;
}

/** Lúc NHẬP: đơn vị nhập khác đơn vị BÁN của thuốc → cảnh báo (không chặn). Lô
 *  nhập theo "hộp" mà thuốc bán theo "gói" thì mỗi lần bán kho không trừ được.
 *  Thiếu một trong hai đơn vị → null. Hàm thuần. */
export function canhBaoNhapKhacDonViBan(
  donViNhap: string | null | undefined,
  donViBan: string | null | undefined,
): string | null {
  const nhap = chuan(donViNhap);
  const ban = chuan(donViBan);
  if (!nhap || !ban || nhap === ban) return null;
  return `Thuốc này bán theo “${donViBan?.trim()}”, nhập theo “${donViNhap?.trim()}”: khi bán, kho KHÔNG tự trừ (khác đơn vị). Nhập theo “${donViBan?.trim()}” hoặc báo quản lý trước.`;
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
