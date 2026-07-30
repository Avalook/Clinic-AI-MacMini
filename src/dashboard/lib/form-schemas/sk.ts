// Config form KHÁM SẢN (service_code "SK").
// Nguồn: section "Khám Sản" (Heading-3) trong docs/forms/handover_kham.docx.
// Section Sản trong docx MỎNG (phần Khám chỉ có "Ổn định / Dấu hiệu cần lưu ý",
// Siêu âm không liệt kê field). → Bổ "Khám thai (khung tối thiểu)" theo chuẩn sản
// khoa, ĐÁNH DẤU //TODO-BS-REVIEW (ngoài docx, chờ bác sĩ duyệt). Field docx giữ nguyên.

import type { FormSchema } from "./types";

const NOI_KHOA = [
  { value: "dtd", label: "Đái tháo đường" },
  { value: "tuyen_giap", label: "Tuyến giáp" },
  { value: "pcos", label: "PCOS" },
  { value: "lac_nmtc", label: "Lạc nội mạc tử cung" },
  { value: "u_xo_tc", label: "U xơ tử cung" },
  { value: "tac_voi_trung", label: "Tắc vòi trứng" },
  { value: "loang_xuong", label: "Loãng xương" },
  { value: "tim_mach", label: "Tim mạch" },
  { value: "ung_thu_pk", label: "Ung thư phụ khoa" },
  { value: "huyet_khoi", label: "Huyết khối tĩnh mạch" },
  { value: "tha", label: "Tăng huyết áp" },
  { value: "roi_loan_mo_mau", label: "Rối loạn mỡ máu" },
];

export const skSchema: FormSchema = {
  service_code: "SK",
  title: "Khám Sản",
  sections: [
    {
      title: "Hành chính bổ sung",
      // docx: "Phần hành chính thêm mục Dự kiến sinh".
      fields: [{ key: "du_kien_sinh", label: "Dự kiến sinh", type: "date" }],
    },
    {
      title: "Lý do khám",
      fields: [
        {
          key: "ly_do",
          label: "Lý do khám",
          type: "checkbox_group",
          options: [
            { value: "kham_thai", label: "Khám thai" },
            { value: "ra_mau", label: "Ra máu" },
            { value: "dau_bung", label: "Đau bụng" },
          ],
          fullWidth: true,
        },
        { key: "ly_do_khac", label: "Khác", type: "text", fullWidth: true },
      ],
    },
    {
      title: "Bệnh sử",
      fields: [{ key: "benh_su", label: "Quá trình bệnh lý hiện tại", type: "textarea", fullWidth: true }],
    },
    {
      title: "Tiền sử phụ khoa",
      fields: [
        { key: "para", label: "PARA", type: "text" },
        { key: "menarche", label: "Tuổi lần đầu thấy kinh", type: "number", unit: "tuổi" },
        { key: "chu_ky", label: "Chu kì kinh nguyệt", type: "number", unit: "ngày" },
        { key: "so_ngay_hanh_kinh", label: "Số ngày hành kinh", type: "number", unit: "ngày" },
        { key: "luong_kinh", label: "Lượng kinh", type: "text" },
        {
          key: "thong_kinh",
          label: "Thống kinh",
          type: "radio",
          options: [
            { value: "co", label: "Có" },
            { value: "khong", label: "Không" },
          ],
        },
        { key: "thong_kinh_do", label: "Thống kinh — độ", type: "conditional", parent: { key: "thong_kinh", equals: "co" } },
        { key: "lmp", label: "Kinh lần cuối (LMP)", type: "date" },
        { key: "tuoi_lay_chong", label: "Lấy chồng năm", type: "number", unit: "tuổi" },
        { key: "tranh_thai", label: "Biện pháp tránh thai đã/đang dùng", type: "text" },
        { key: "benh_pk_dang_dieu_tri", label: "Các bệnh phụ khoa đang điều trị", type: "text" },
        { key: "phau_thuat_pk", label: "Phẫu thuật phụ khoa", type: "text" },
      ],
    },
    {
      title: "Tiền sử nội khoa, nội tiết",
      fields: [
        { key: "noi_khoa", label: "Tiền sử nội khoa, nội tiết", type: "checkbox_group", options: NOI_KHOA, fullWidth: true },
        { key: "noi_khoa_chi_tiet", label: "Chi tiết", type: "textarea", fullWidth: true },
        { key: "di_ung_thuoc", label: "Dị ứng thuốc", type: "text", fullWidth: true },
      ],
    },
    {
      title: "Tiền sử ngoại khoa",
      fields: [{ key: "ts_ngoai_khoa", label: "Tiền sử ngoại khoa", type: "textarea", fullWidth: true }],
    },
    {
      title: "Khám",
      fields: [
        {
          key: "kham_trang_thai",
          label: "Khám",
          type: "radio",
          options: [
            { value: "on_dinh", label: "Ổn định" },
            { value: "dau_hieu_luu_y", label: "Dấu hiệu cần lưu ý" },
          ],
        },
        { key: "dau_hieu_chi_tiet", label: "Dấu hiệu cần lưu ý — chi tiết", type: "conditional", parent: { key: "kham_trang_thai", equals: "dau_hieu_luu_y" } },
      ],
    },
    {
      title: "Cận lâm sàng — Xét nghiệm máu",
      fields: [
        { key: "cls_ctm", label: "CTM (HC, BC, TC, Hb, HCT)", type: "text" },
        { key: "cls_glucose", label: "Glucose máu đói", type: "text" },
        { key: "cls_hba1c", label: "HbA1c", type: "text" },
        { key: "cls_mo_mau", label: "Bộ mỡ máu (Chol, TG, LDL, HDL)", type: "text" },
        { key: "cls_gan", label: "Chức năng gan (AST, ALT, GGT)", type: "text" },
        { key: "cls_than", label: "Chức năng thận (Ure, Creatinin)", type: "text" },
        { key: "cls_nhom_mau", label: "Nhóm máu", type: "text" },
        { key: "cls_vgb", label: "Viêm gan B (HBsAg / Anti-HBs)", type: "text" },
        { key: "cls_hiv_gm", label: "HIV, Giang mai (VDRL/TPHA)", type: "text" },
        { key: "cls_rubella", label: "Rubella IgG / IgM", type: "text" },
        { key: "cls_dong_mau", label: "Đông máu cơ bản (PT, APTT, Fibrinogen)", type: "text" },
      ],
    },
    {
      title: "Cận lâm sàng — Siêu âm",
      // docx chỉ ghi tiêu đề "Siêu âm" không liệt kê field → 1 ô mô tả. //TODO docx mơ hồ.
      fields: [{ key: "cls_sieu_am", label: "Siêu âm (mô tả)", type: "textarea", fullWidth: true }],
    },
    {
      title: "Kết luận",
      fields: [{ key: "ket_luan", label: "Kết luận", type: "textarea", fullWidth: true }],
    },
    {
      title: "Lời dặn",
      fields: [{ key: "loi_dan", label: "Lời dặn", type: "textarea", fullWidth: true }],
    },
  ],
};
