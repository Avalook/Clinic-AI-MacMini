// Gom các mục của phiếu khám theo GIAI ĐOẠN LÂM SÀNG.
//
// VÌ SAO. Phiếu chuyên khoa dài: Hiếm muộn 21 mục, Phụ khoa 13, Nội tiết 12.
// Bản trước đổ cả phiếu vào hai cột kiểu XẾP GẠCH (`columns:2`) — mục tự rơi
// vào cột nào còn chỗ, nên thứ tự mắt đọc nhảy lung tung: mục 1 ở trên cùng bên
// trái, mục 7 lại nằm trên cùng bên phải. Tuyền 16/09/2026: "các cái form điền
// của bác sĩ nó chưa khoa học lắm, tách ra cho dễ nhìn đã".
//
// Sáu giai đoạn dưới đây là đúng trình tự suy luận lâm sàng, và khớp cấu trúc
// hồ sơ khám trong Notion *Kế hoạch v1.0.0* (Hành chính & tiền sử → Khám → Cận
// lâm sàng & chuyên khoa → Chẩn đoán & xử trí). Bác sĩ đi từ trên xuống dưới là
// đi đúng thứ tự họ nghĩ.
//
// PHÂN BẰNG TÊN MỤC, không thêm trường mới vào năm schema. Thêm trường là sửa
// năm tệp dài và mỗi mục mới lại phải nhớ khai; còn tên mục thì bác sĩ vốn đã
// đặt theo đúng giai đoạn ("Tiền sử…", "Khám…", "Cận lâm sàng —…"). Bài kiểm
// `giai-doan.test.mts` chạy trên CẢ NĂM phiếu thật, nên mục nào rơi vào "Khác"
// là đỏ ngay — không có chuyện một mục mới lặng lẽ trôi xuống cuối phiếu.

import type { FormSection } from "./types";

export type MaGiaiDoan =
  | "LY_DO"
  | "TIEN_SU"
  | "KHAM"
  | "CAN_LAM_SANG"
  | "CHAN_DOAN"
  | "THEO_DOI"
  | "KHAC";

export const GIAI_DOAN: readonly { ma: MaGiaiDoan; ten: string }[] = [
  { ma: "LY_DO", ten: "Lý do khám & bệnh sử" },
  { ma: "TIEN_SU", ten: "Tiền sử" },
  { ma: "KHAM", ten: "Khám" },
  { ma: "CAN_LAM_SANG", ten: "Cận lâm sàng" },
  { ma: "CHAN_DOAN", ten: "Chẩn đoán & xử trí" },
  { ma: "THEO_DOI", ten: "Theo dõi & dặn dò" },
  // Lưới an toàn — không bao giờ được dùng tới. Có bài kiểm canh.
  { ma: "KHAC", ten: "Khác" },
];

function boDau(s: string): string {
  return s
    .replace(/Đ/g, "D")
    .replace(/đ/g, "d")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

/** Mục này thuộc giai đoạn nào. THỨ TỰ KIỂM QUAN TRỌNG — xem từng dòng. */
export function giaiDoanCua(title: string): MaGiaiDoan {
  const t = boDau(title);

  // Cận lâm sàng kiểm TRƯỚC "khám": "Điều kiện lấy mẫu tinh dịch" và "Nội tiết &
  // xét nghiệm máu" của phiếu Nam khoa không mở đầu bằng "cận lâm sàng" nhưng
  // đúng là cận lâm sàng.
  if (
    t.startsWith("can lam sang") ||
    t.startsWith("tinh dich do") ||
    t.startsWith("dieu kien lay mau") ||
    t.startsWith("noi tiet & xet nghiem") ||
    t.startsWith("hinh anh")
  ) {
    return "CAN_LAM_SANG";
  }
  // "Tiền sử" kiểm TRƯỚC "Lý do": không có mục nào vừa là cả hai, nhưng "Tiền sử
  // trị hiếm muộn" chứa chữ "tri" và không được phép rơi vào nhánh điều trị.
  if (t.startsWith("tien su")) return "TIEN_SU";
  if (t.startsWith("ly do") || t.startsWith("benh su") || t.startsWith("hanh chinh")) {
    return "LY_DO";
  }
  if (t.startsWith("kham")) return "KHAM";
  if (
    t.startsWith("chan doan") ||
    t.startsWith("huong xu tri") ||
    t.startsWith("dieu tri") ||
    t.startsWith("ket luan")
  ) {
    return "CHAN_DOAN";
  }
  if (t.startsWith("theo doi") || t.startsWith("tai kham") || t.startsWith("loi dan")) {
    return "THEO_DOI";
  }
  return "KHAC";
}

export interface NhomGiaiDoan {
  ma: MaGiaiDoan;
  ten: string;
  /** Giữ NGUYÊN thứ tự mục trong schema — bác sĩ đã đặt thứ tự ấy có lý do. */
  muc: FormSection[];
}

/** Chia phiếu thành các giai đoạn, theo thứ tự lâm sàng, bỏ giai đoạn rỗng. */
export function chiaGiaiDoan(sections: readonly FormSection[]): NhomGiaiDoan[] {
  return GIAI_DOAN.map(({ ma, ten }) => ({
    ma,
    ten,
    muc: sections.filter((s) => giaiDoanCua(s.title) === ma),
  })).filter((g) => g.muc.length > 0);
}
