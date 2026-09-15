// Cách xác minh đúng người bệnh khi check-in (Tuyền chốt 15/09/2026).
//
// Danh mục là LUẬT CỦA BACKEND — `CACH_XAC_MINH` ở booking_service.py và ràng
// buộc `visit_xac_minh_cach_hop_le` (20260915000009). File này chỉ giữ nhãn để
// hiện nút; test_booking_service.py canh ba mã ở đây khớp backend.
//
// KHÔNG CÓ MẶC ĐỊNH. Màn nào điền sẵn một cách là tạo ra bằng chứng giả cho
// những lượt không ai hỏi gì khách.

export const CACH_XAC_MINH = [
  { ma: "THONG_TIN_CA_NHAN", nhan: "Đối chiếu thông tin cá nhân" },
  { ma: "GIAY_TO_CO_ANH", nhan: "Kiểm giấy tờ có ảnh" },
  { ma: "NGUOI_NHA_XAC_NHAN", nhan: "Người nhà xác nhận" },
] as const;

export type MaXacMinh = (typeof CACH_XAC_MINH)[number]["ma"];
