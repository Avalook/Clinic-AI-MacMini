// Config form KHÁM NAM KHOA (service_code "NK").
//
// ⚠️ //TODO-BS-REVIEW (QUAN TRỌNG): docx KHÔNG có Heading-3 "Khám Nam khoa" riêng.
// Nội dung nam khoa trong docx chỉ NẰM TRONG section Hiếm muộn-Vô sinh (tiền sử chồng,
// khám nam khoa, tinh dịch đồ, hình ảnh nam). Form NK dưới đây được LẮP từ đúng các
// field nam-khoa đó (KHÔNG bịa field mới) + các mục Lý do/Bệnh sử/Chẩn đoán/Điều trị
// dạng chung. Cần bác sĩ duyệt / cung cấp spec NK riêng trước khi dùng thật.

import type { FormSchema } from "./types";

const TDD_PARAMS: { key: string; label: string }[] = [
  { key: "tdd_the_tich", label: "Thể tích (mL)" },
  { key: "tdd_ph", label: "pH" },
  { key: "tdd_nong_do", label: "Nồng độ tinh trùng (triệu/mL)" },
  { key: "tdd_tong_so", label: "Tổng số tinh trùng (triệu)" },
  { key: "tdd_tien_toi", label: "Tiến tới (PR %)" },
  { key: "tdd_bat_dong", label: "Bất động (IM %)" },
  { key: "tdd_hinh_dang", label: "Hình dạng bình thường (Kruger %)" },
  { key: "tdd_bach_cau", label: "Bạch cầu (triệu/mL)" },
  { key: "tdd_danh_gia", label: "Đánh giá (WHO 2021)" },
];
const tddFields = TDD_PARAMS.flatMap((p) => [
  { key: `${p.key}_l1`, label: `${p.label} — lần 1`, type: "text" as const },
  { key: `${p.key}_l2`, label: `${p.label} — lần 2`, type: "text" as const },
]);

export const nkSchema: FormSchema = {
  service_code: "NK",
  title: "Khám Nam khoa",
  sections: [
    {
      // //TODO-BS-REVIEW: lý do/bệnh sử chung — docx không có mục NK riêng.
      title: "Lý do khám & bệnh sử",
      fields: [
        { key: "ly_do", label: "Lý do khám bệnh", type: "textarea", fullWidth: true },
        { key: "benh_su", label: "Quá trình bệnh lý hiện tại", type: "textarea", fullWidth: true },
      ],
    },
    {
      // Nguồn: "Tiền sử Sản khoa (chồng)" trong section HMVS của docx.
      title: "Tiền sử (nam)",
      fields: [
        { key: "con_truoc", label: "Tiền sử có con trước", type: "text", fullWidth: true },
        { key: "benh_sd_tn", label: "Bệnh lý sinh dục / tiết niệu", type: "text", fullWidth: true },
        { key: "pt_biu_ben_tlt", label: "Phẫu thuật vùng bìu / bẹn / tuyến tiền liệt", type: "text", fullWidth: true },
        { key: "quai_bi", label: "Tiền sử quai bị có biến chứng", type: "text", fullWidth: true },
        { key: "nghe_nghiep", label: "Nghề nghiệp / tiếp xúc hóa chất / nhiệt độ cao", type: "text", fullWidth: true },
      ],
    },
    {
      // Nguồn: "Khám nam khoa" trong section HMVS của docx.
      title: "Khám nam khoa",
      fields: [
        { key: "tinh_hoan", label: "Tinh hoàn T/P (thể tích, mật độ)", type: "text", fullWidth: true },
        { key: "mao_tinh", label: "Mào tinh / ống dẫn tinh", type: "text" },
        { key: "gian_tm_tinh", label: "Giãn tĩnh mạch tinh (độ)", type: "text" },
        { key: "duong_vat_nieu_dao", label: "Dương vật / niệu đạo", type: "text" },
      ],
    },
    {
      // Nguồn: "Tinh dịch đồ (Chồng)" trong section HMVS (2 lần đo).
      title: "Tinh dịch đồ",
      fields: tddFields,
    },
    {
      // Nguồn: hình ảnh/di truyền nam trong CLS section HMVS.
      title: "Cận lâm sàng (nam)",
      fields: [
        { key: "cls_sa_tinh_hoan", label: "Siêu âm tinh hoàn / Doppler", type: "text" },
        { key: "cls_y_microdel", label: "Y-chromosome microdeletion", type: "text" },
        { key: "cls_karyotype", label: "Nhiễm sắc thể đồ (Karyotype) – nếu chỉ định", type: "text" },
      ],
    },
    {
      // //TODO-BS-REVIEW: chẩn đoán/điều trị chung — docx không có mục NK riêng.
      title: "Chẩn đoán & điều trị",
      fields: [
        { key: "chan_doan", label: "Chẩn đoán", type: "textarea", fullWidth: true },
        { key: "dieu_tri", label: "Hướng xử trí / điều trị", type: "textarea", fullWidth: true },
      ],
    },
  ],
};
