// Chỗ ở ĐẦU thẻ mục phiếu khám (cùng dòng tiêu đề) cho nút thao tác của nội dung
// bên trong — `TheCon` cấp, `DanhMucChiDinh` đặt nút "Chỉ định N mục" vào bằng
// portal. Không có (null) thì nội dung tự vẽ nút ở chỗ cũ, cuối danh sách.
import { createContext } from "react";

export const ChoNutMuc = createContext<HTMLElement | null>(null);
