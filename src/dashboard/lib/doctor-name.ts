// Tên hiển thị bác sĩ. Dữ liệu staff.full_name ĐÃ kèm học hàm/chức danh ngành y
// (vd "TS.BS. Phan Chí Thành", "BSNT. ...", "Ths. ...", "BSCKI. ...", "BS. ...")
// — xem seed migrations/seed/053_doctor_full_names.sql. Nếu cứ prepend "BS." thì
// ra "BS. TS.BS. ..." (TRÙNG chữ BS — feedback PM 23/6). Helper: chỉ thêm "BS."
// khi tên CHƯA có học hàm; đã có thì giữ NGUYÊN (hiển thị đủ tên).
//
// Nhận diện học hàm = chuỗi ĐẦU tên gồm 1+ token chức danh (GS/PGS/TS/ThS/BS/
// BSNT/BSCKx/CN/DS/ĐD/TL) nối nhau bằng dấu chấm hoặc cách.
const HAS_TITLE = /^(?:(?:GS|PGS|TS|Th\.?S|BSNT|BSSA|BSCK[I]+|BS|CN|DS|ĐD|TL)\.?\s*)+/i;

// VIẾT TẮT ĐƯỢC TRẢI RA THÀNH CHỮ BỆNH NHÂN ĐỌC ĐƯỢC (Quang chốt 09/08/2026).
//
// "BSNT. Nguyễn Khánh Linh" trên màn hình CSKH và trên tin nhắn gửi khách là
// một chuỗi chỉ người trong ngành đọc được. Khách đọc "Bác sĩ nội tiết Nguyễn
// Khánh Linh" thì biết ngay mình được xếp cho ai.
//
// CHỈ ĐỔI CHỮ HIỂN THỊ. `staff.full_name` trong database giữ nguyên — đây là
// một phép chiếu ở tầng giao diện, nên đổi lại hoặc thêm viết tắt mới không
// cần đụng tới dữ liệu.
//
// ⚠️ MỘT ĐIỂM CẦN QUANG XÁC NHẬN, ĐÃ BÁO: trong ngành y "BSNT" thường là BÁC SĨ
// NỘI TRÚ. Ở Dr4Women hiện có 6 người mang tiền tố này, trong đó
// "BSNT. Nguyễn Hữu Giáp" dùng tài khoản `bacsisieuamgiap@dr4women.vn` — tức là
// bác sĩ SIÊU ÂM. Nếu tiền tố trong database đang là "nội trú" thì bảng này
// đang gắn sai chuyên khoa cho họ trước mặt khách. Sửa đúng chỗ là sửa
// `staff.full_name` (fixtures/ten_day_du_bac_si.sql), không phải bảng này.
const TRAI_VIET_TAT: [RegExp, string][] = [
  [/^BSNT\.?\s+/i, "Bác sĩ nội tiết "],
  [/^BSSA\.?\s+/i, "Bác sĩ siêu âm "],
];

/** Tên bác sĩ để hiển thị: thêm "BS. " CHỈ KHI tên trần (chưa có học hàm),
 *  và trải các viết tắt chuyên khoa thành chữ đầy đủ.
 *  Tên rỗng → "" (caller tự quyết fallback "Chưa phân bác sĩ"/"—"). */
export function doctorName(raw: string | null | undefined): string {
  const n = (raw ?? "").trim();
  if (!n) return "";
  for (const [mau, thay] of TRAI_VIET_TAT) {
    if (mau.test(n)) return n.replace(mau, thay);
  }
  return HAS_TITLE.test(n) ? n : `BS. ${n}`;
}
