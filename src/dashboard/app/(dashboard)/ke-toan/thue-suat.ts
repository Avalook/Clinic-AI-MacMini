// Chữ hiển thị cho thuế suất GTGT (G5b/C2). CHỈ là nhãn — việc chuẩn hoá, ưu tiên
// (dòng > mặt hàng > nhóm) và tách thuế làm ở máy chủ (`thue_gtgt.py`).

export const TEN_NHOM_HANG: Record<string, string> = {
  DICH_VU: "Dịch vụ", THUOC: "Thuốc", VAT_TU: "Vật tư",
};

/** Mã thuế suất của máy chủ ("8", "8.5", "KCT", "KKKNT", "Nhiều") → chữ cho người đọc;
 *  trống → "". Chữ lạ giữ nguyên (máy chủ có thể thêm mã mới). */
export function tenThueSuat(ma: string | null | undefined): string {
  if (!ma) return "";
  if (ma === "KCT") return "Không chịu thuế";
  if (ma === "KKKNT") return "Không kê khai nộp thuế";
  if (/^\d/.test(ma)) return `${ma.replace(".", ",")}%`;
  return ma;
}

/** Nguồn thuế suất của một dòng hoá đơn (máy chủ trả `thue_nguon`). */
export const TEN_NGUON_THUE: Record<string, string> = {
  dong: "sửa tay", mat_hang: "theo mặt hàng", nhom: "theo nhóm",
};

/** Các mức hay dùng (mã máy chủ, nhãn). Mức khác nhập % tự do — máy chủ vẫn là nơi chuẩn hoá. */
export const MUC_THUE: [string, string][] = [
  ["0", "0%"], ["5", "5%"], ["8", "8%"], ["10", "10%"],
  ["KCT", "Không chịu thuế (KCT)"], ["KKKNT", "Không kê khai nộp thuế (KKKNT)"],
];
