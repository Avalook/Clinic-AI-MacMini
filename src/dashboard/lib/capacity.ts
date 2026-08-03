// Kiểu dùng chung cho phần sức chứa. FILE NÀY GẦN NHƯ ĐÃ RỖNG, CÓ CHỦ Ý.
//
// Nó từng dài 240 dòng và giữ hai thứ, cả hai đều đã đi chỗ khác:
//
// 1. LUẬT SỨC CHỨA (evaluateBudget, cellState, resolveBudget, usageOf,
//    vnBlockOf, isBlocking). Đã chuyển sang services/capacity_service.py để chỉ
//    còn một nơi quyết định. Bản TS ở lại thêm một thời gian, không ai import,
//    biên dịch sạch, và chờ người tiếp theo autocomplete nhầm vào nó.
//
// 2. BẢNG PHÚT VIẾT CỨNG (suggestLoad). Gỡ ở 20260803000005 — cùng lúc với
//    booking_service.suggest_load(). Đây là phần đáng nói.
//
// VÌ SAO suggestLoad PHẢI BIẾN MẤT
//
// Nó trả về: khách mới 15 phút, tái khám 5 phút, siêu âm cộng thêm 12 hoặc 8.
// Bốn con số không đến từ phép đo nào — được gõ vào một lần, rồi trở thành cơ sở
// để tô màu mọi ô lịch và để cảnh báo "khung sắp đầy". Nếu BS Thành thật sự mất
// 22 phút cho một khách mới lúc 18:00 thứ Ba, hệ thống vẫn báo còn trống, đều
// đặn, mỗi ngày, và không có gì trong mã nói cho ai biết nó đang đoán.
//
// MÔ HÌNH THAY THẾ — hai việc khác hẳn nhau, tách hẳn ra:
//
//   GIỚI HẠN đặt lịch  Là SỐ CHỖ mỗi khung giờ. Trưởng ca và Quản lý đặt con số
//                      này ở /settings/booking-policy, đặt riêng cho từng bác sĩ
//                      hoặc từng khung (booking_override). Đây là QUYẾT ĐỊNH của
//                      con người, và trigger trong database thi hành nó.
//
//   THỜI LƯỢNG khám    Là SỐ LIỆU ĐO ĐƯỢC, không ai đặt. Bàn khám bấm "Bắt đầu"
//                      và "Hoàn tất" mỗi ca — hai mốc đó đã nằm trong work_item
//                      từ lâu, chỉ là chưa ai đọc. View v_consultation_duration
//                      và v_consultation_duration_stats (migration
//                      20260803000005) biến chúng thành trung vị / p90 theo
//                      (bác sĩ × dịch vụ × loại khách × thứ × giờ VN).
//
// Số liệu đó phục vụ hai việc: ngay bây giờ, cho Trưởng ca thấy con số thật khi
// họ chỉnh số chỗ; về sau, làm tập huấn luyện để hệ thống tự đề xuất số chỗ theo
// khung giờ thay vì chờ người ngồi đoán.
//
// thanh_min / sono_min trên `appointment` vẫn còn, nhưng từ đây chỉ nhận giá trị
// người dùng NHẬP TAY (CSKH biết ca này lâu hơn thường lệ) và NULL khi không ai
// ước lượng. Không còn hàm nào tự điền chúng.

/** Khách khám lần đầu hay tái khám. Ảnh hưởng thống kê, không còn ảnh hưởng
 *  một bảng phút nào. */
export type PatientKind = "NEW" | "RETURN";
