// Config form KHÁM NỘI TIẾT (service_code "NT").
// Nguồn: section "Khám Nội tiết" (Heading-3) trong docs/forms/handover_kham.docx.
// Field lấy ĐÚNG theo docx — KHÔNG bịa. Chỗ mơ hồ đánh dấu //TODO.

import type { FormSchema } from "./types";

const NOI_TIET_TS = [
  { value: "dtd", label: "Đái tháo đường" },
  { value: "tuyen_giap", label: "Tuyến giáp" },
  { value: "tuyen_thuong_than", label: "Tuyến thượng thận" },
  { value: "pcos", label: "PCOS" },
  { value: "loang_xuong", label: "Loãng xương" },
  { value: "tim_mach", label: "Tim mạch" },
  { value: "ung_thu", label: "Ung thư vú / phụ khoa" },
  { value: "huyet_khoi", label: "Huyết khối tĩnh mạch" },
  { value: "tha", label: "Tăng huyết áp" },
  { value: "roi_loan_mo_mau", label: "Rối loạn mỡ máu" },
];

const GIA_DINH = [
  { value: "man_kinh_som", label: "Mãn kinh sớm" },
  { value: "loang_xuong", label: "Loãng xương" },
  { value: "ung_thu_vu_bt", label: "Ung thư vú / buồng trứng" },
  { value: "tim_mach_som", label: "Tim mạch sớm" },
  { value: "dtd", label: "ĐTĐ" },
];

const DIEU_TRI_HO_TRO = [
  { value: "canxi_vitd", label: "Bổ sung Canxi + Vitamin D" },
  { value: "bisphosphonate", label: "Bisphosphonate (loãng xương)" },
  { value: "omega3", label: "Omega-3" },
  { value: "chong_tram_cam", label: "Chống trầm cảm / lo âu" },
  { value: "duong_am_ad", label: "Dưỡng ẩm âm đạo tại chỗ" },
  { value: "loi_song", label: "Điều chỉnh lối sống" },
  { value: "tu_van_tam_ly", label: "Tư vấn tâm lý" },
];

const TAIKHAM_XN = [
  { value: "HM", label: "Hormone" },
  { value: "SH", label: "Sinh hóa" },
  { value: "SA", label: "Siêu âm" },
  { value: "DXA", label: "DXA" },
  { value: "PS", label: "Pap smear" },
];

export const ntSchema: FormSchema = {
  service_code: "NT",
  title: "Khám Nội tiết",
  sections: [
    {
      title: "Lý do khám bệnh",
      fields: [{ key: "ly_do", label: "Lý do khám bệnh", type: "textarea", fullWidth: true }],
    },
    {
      title: "Tiền sử phụ khoa và sản khoa",
      fields: [
        { key: "para", label: "PARA", type: "text" },
        { key: "menarche", label: "Tuổi lần đầu thấy kinh", type: "number", unit: "tuổi" },
        { key: "chu_ky", label: "Chu kì kinh nguyệt", type: "number", unit: "ngày" },
        { key: "tuoi_lay_chong", label: "Tuổi lấy chồng", type: "number", unit: "tuổi" },
        { key: "tranh_thai", label: "Biện pháp tránh thai đang dùng", type: "text" },
        { key: "benh_pk_dang_dieu_tri", label: "Các bệnh phụ khoa đang điều trị", type: "text" },
        { key: "phau_thuat_pk", label: "Phẫu thuật phụ khoa", type: "text" },
      ],
    },
    {
      title: "Tiền sử nội tiết",
      fields: [
        { key: "ts_noi_tiet", label: "Tiền sử nội tiết", type: "checkbox_group", options: NOI_TIET_TS, fullWidth: true },
        { key: "ts_noi_tiet_chi_tiet", label: "Chi tiết", type: "textarea", fullWidth: true },
        { key: "di_ung_thuoc", label: "Dị ứng thuốc", type: "text", fullWidth: true },
      ],
    },
    {
      title: "Tiền sử gia đình",
      fields: [
        { key: "ts_gia_dinh", label: "Tiền sử gia đình", type: "checkbox_group", options: GIA_DINH, fullWidth: true },
      ],
    },
    {
      title: "Bệnh sử",
      fields: [
        { key: "benh_su", label: "Quá trình bệnh lý hiện tại", type: "textarea", fullWidth: true },
        { key: "thuoc_dang_dung", label: "Thuốc đang sử dụng (tên, liều, thời gian)", type: "textarea", fullWidth: true },
      ],
    },
    {
      title: "Cận lâm sàng — Huyết học / Sinh hóa",
      fields: [
        { key: "cls_ctm", label: "CTM (HC, BC, TC, Hb, HCT)", type: "text" },
        { key: "cls_glucose", label: "Glucose máu đói", type: "text" },
        { key: "cls_hba1c", label: "HbA1c", type: "text" },
        { key: "cls_mo_mau", label: "Bộ mỡ máu (Chol, TG, LDL, HDL)", type: "text" },
        { key: "cls_gan", label: "Chức năng gan (AST, ALT, GGT)", type: "text" },
        { key: "cls_than", label: "Chức năng thận (Ure, Creatinin)", type: "text" },
        { key: "cls_dien_giai", label: "Điện giải đồ (Na, K, Ca, P)", type: "text" },
        { key: "cls_crp", label: "CRP / Procalcitonin (nếu cần)", type: "text" },
      ],
    },
    {
      title: "Cận lâm sàng — Nội tiết tố (Hormones)",
      fields: [
        { key: "cls_fsh", label: "FSH (mIU/mL)", type: "text" },
        { key: "cls_lh", label: "LH (mIU/mL)", type: "text" },
        { key: "cls_e2", label: "Estradiol E2 (pg/mL)", type: "text" },
        { key: "cls_progesterone", label: "Progesterone (ng/mL)", type: "text" },
        { key: "cls_testosterone", label: "Testosterone tổng (ng/dL)", type: "text" },
        { key: "cls_dheas", label: "DHEA-S (µg/dL)", type: "text" },
        { key: "cls_prolactin", label: "Prolactin (ng/mL)", type: "text" },
        { key: "cls_tsh_ft4", label: "TSH / FT4 (tuyến giáp)", type: "text" },
        { key: "cls_amh", label: "AMH (ng/mL) — nếu chỉ định", type: "text" },
        { key: "cls_inhibin_b", label: "Inhibin B (nếu chỉ định)", type: "text" },
      ],
    },
    {
      title: "Cận lâm sàng — Hình ảnh học & thăm dò chức năng",
      fields: [
        { key: "cls_sa_pttc", label: "Siêu âm PTTC (TA/DA)", type: "text" },
        { key: "cls_niem_mac_tc", label: "Nội mạc tử cung (mm)", type: "text" },
        { key: "cls_kt_buong_trung", label: "Kích thước buồng trứng T/P", type: "text" },
        { key: "cls_nang_noan_afc", label: "Nang noãn / AFC (số nang 2-10mm)", type: "text" },
        { key: "cls_pap_hpv", label: "PAP smear / HPV test", type: "text" },
        { key: "cls_mammo_sa_vu", label: "Mammography / SA vú", type: "text" },
        { key: "cls_dxa", label: "Đo mật độ xương DXA (T-score)", type: "text" },
        { key: "cls_ecg", label: "Điện tim (ECG)", type: "text" },
        { key: "cls_sinh_thiet_nmtc", label: "Sinh thiết NM tử cung (nếu chỉ định)", type: "text" },
      ],
    },
    {
      title: "Chẩn đoán",
      fields: [{ key: "chan_doan", label: "Chẩn đoán", type: "textarea", fullWidth: true }],
    },
    {
      title: "Hướng xử trí — Liệu pháp hormone mãn kinh (MHT)",
      fields: [
        {
          key: "mht_quyet_dinh",
          label: "Quyết định MHT",
          type: "radio",
          options: [
            { value: "chi_dinh", label: "Chỉ định MHT" },
            { value: "chong_chi_dinh", label: "Chống chỉ định MHT" },
            { value: "can_nhac", label: "Cần cân nhắc (relative CI)" },
          ],
        },
        // docx liệt kê các phác đồ dạng bullet sau "Phác đồ:" — //TODO docx mơ hồ:
        // có thể chọn nhiều hay 1? Hiện để radio (phác đồ thường chọn 1). //TODO-BS-REVIEW.
        {
          key: "mht_phac_do",
          label: "Phác đồ MHT",
          type: "radio",
          options: [
            { value: "estrogen_don", label: "Estrogen đơn thuần" },
            { value: "ep_lien_tuc", label: "Kết hợp E+P liên tục" },
            { value: "ep_chu_ky", label: "Kết hợp E+P chu kỳ" },
            { value: "tibolon", label: "Tibolon" },
            { value: "phytoestrogen", label: "Phythoestrogen" },
          ],
        },
        { key: "mht_ten_thuoc", label: "Tên thuốc / dạng dùng", type: "text", fullWidth: true },
        { key: "mht_lieu", label: "Liều lượng / cách dùng", type: "text", fullWidth: true },
      ],
    },
    {
      title: "Hướng xử trí — Điều trị hỗ trợ & lối sống",
      fields: [
        { key: "dieu_tri_ho_tro", label: "Điều trị hỗ trợ", type: "checkbox_group", options: DIEU_TRI_HO_TRO, fullWidth: true },
        { key: "dieu_tri_ho_tro_chi_tiet", label: "Chi tiết điều trị bổ sung", type: "textarea", fullWidth: true },
        // docx phần "Lối sống - Dinh dưỡng - Vận động" là hướng dẫn cố định; để ô ghi chú.
        // //TODO docx mơ hồ: là tư vấn in sẵn hay field nhập — tạm 1 textarea ghi chú.
        { key: "loi_song_ghi_chu", label: "Lối sống – Dinh dưỡng – Vận động (ghi chú)", type: "textarea", fullWidth: true },
      ],
    },
    {
      title: "Theo dõi và tái khám",
      fields: [
        { key: "tai_kham_ngay", label: "Ngày tái khám", type: "date" },
        { key: "tai_kham_xn", label: "Xét nghiệm cần kiểm tra lại", type: "checkbox_group", options: TAIKHAM_XN, fullWidth: true },
      ],
    },
  ],
};
