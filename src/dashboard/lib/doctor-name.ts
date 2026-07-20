// Tên hiển thị bác sĩ. Dữ liệu staff.full_name ĐÃ kèm học hàm/chức danh ngành y
// (vd "TS.BS. Phan Chí Thành", "BSNT. ...", "Ths. ...", "BSCKI. ...", "BS. ...")
// — xem seed migrations/seed/053_doctor_full_names.sql. Nếu cứ prepend "BS." thì
// ra "BS. TS.BS. ..." (TRÙNG chữ BS — feedback PM 23/6). Helper: chỉ thêm "BS."
// khi tên CHƯA có học hàm; đã có thì giữ NGUYÊN (hiển thị đủ tên).
//
// Nhận diện học hàm = chuỗi ĐẦU tên gồm 1+ token chức danh (GS/PGS/TS/ThS/BS/
// BSNT/BSCKx/CN/DS/ĐD/TL) nối nhau bằng dấu chấm hoặc cách.
const HAS_TITLE = /^(?:(?:GS|PGS|TS|Th\.?S|BSNT|BSCK[I]+|BS|CN|DS|ĐD|TL)\.?\s*)+/i;

/** Tên bác sĩ để hiển thị: thêm "BS. " CHỈ KHI tên trần (chưa có học hàm).
 *  Tên rỗng → "" (caller tự quyết fallback "Chưa phân bác sĩ"/"—"). */
export function doctorName(raw: string | null | undefined): string {
  const n = (raw ?? "").trim();
  if (!n) return "";
  return HAS_TITLE.test(n) ? n : `BS. ${n}`;
}
