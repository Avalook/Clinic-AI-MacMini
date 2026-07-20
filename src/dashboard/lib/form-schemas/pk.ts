// Config form KHÁM PHỤ KHOA (service_code "PK").
// VERIFY khớp section "Khám Phụ khoa" trong docs/forms/handover_kham.docx (Heading-3).
// Sửa so với bản pilot cũ cho khớp docx: bỏ field tự thêm (đau bụng kinh radio,
// chu_ky tinh chất…), thêm Thống kinh + các trường tiền sử PK + Cận lâm sàng có cấu
// trúc (bảng XN trong docx) + khám chuyên khoa theo đúng docx. KHÔNG bịa field.

import type { FormSchema } from "./types";

const TAIKHAM_XN = [
  { value: "HM", label: "Hormone" },
  { value: "SH", label: "Sinh hóa" },
  { value: "SA", label: "Siêu âm" },
  { value: "DXA", label: "DXA" },
  { value: "PS", label: "Pap smear" },
];

export const pkSchema: FormSchema = {
  service_code: "PK",
  title: "Khám Phụ khoa",
  sections: [
    {
      title: "Lý do khám bệnh",
      fields: [{ key: "ly_do", label: "Lý do khám bệnh", type: "textarea", fullWidth: true }],
    },
    {
      title: "Bệnh sử",
      fields: [
        { key: "benh_su", label: "Quá trình bệnh lý hiện tại", type: "textarea", fullWidth: true },
      ],
    },
    {
      title: "Tiền sử bệnh",
      fields: [
        { key: "ts_ban_than", label: "Bản thân", type: "textarea", fullWidth: true },
        { key: "ts_gia_dinh", label: "Gia đình", type: "textarea", fullWidth: true },
      ],
    },
    {
      title: "Tiền sử phụ khoa",
      fields: [
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
        {
          key: "thong_kinh_do",
          label: "Thống kinh — độ",
          type: "conditional",
          parent: { key: "thong_kinh", equals: "co" },
        },
        { key: "lmp", label: "Kinh lần cuối (LMP)", type: "date" },
        { key: "tuoi_lay_chong", label: "Lấy chồng năm", type: "number", unit: "tuổi" },
        { key: "tranh_thai", label: "Biện pháp tránh thai đã/đang dùng", type: "text" },
        { key: "tg_quan_he_khong_tranh_thai", label: "Thời gian quan hệ không tránh thai", type: "text" },
        { key: "benh_pk_dang_dieu_tri", label: "Các bệnh phụ khoa đang điều trị", type: "text" },
        { key: "phau_thuat_pk", label: "Phẫu thuật phụ khoa", type: "text" },
        { key: "para", label: "Tiền sử sản khoa (PARA)", type: "text" },
      ],
    },
    {
      title: "Khám lâm sàng tổng quát",
      fields: [
        { key: "nhip_tim", label: "Nhịp tim", type: "number", unit: "l/p" },
        { key: "nhiet_do", label: "Nhiệt độ", type: "number", unit: "°C" },
        { key: "huyet_ap", label: "Huyết áp", type: "text", unit: "mmHg", placeholder: "vd 120/80" },
        { key: "nhip_tho", label: "Nhịp thở", type: "number", unit: "l/p" },
        { key: "can_nang", label: "Cân nặng", type: "number", unit: "kg" },
        // docx ghi "BMT" — nhiều khả năng là BMI. //TODO-BS-REVIEW: xác nhận BMT≡BMI.
        { key: "bmt", label: "BMT", type: "text" },
        { key: "da_niem_mac", label: "Da niêm mạc", type: "text" },
        { key: "tuyen_giap", label: "Tuyến giáp", type: "text" },
        { key: "vu", label: "Vú", type: "text" },
      ],
    },
    {
      // docx: dưới "Khám chuyên khoa" liệt kê "Khám trong" → dấu hiệu sinh dục thứ phát
      // (môi lớn/bé/âm vật/âm hộ/màng trinh/TSM) rồi "Khám ngoài" → âm đạo/CTC/tử cung…
      // //TODO docx mơ hồ: nhãn trong/ngoài có vẻ HOÁN ĐỔI so với lâm sàng — GIỮ NGUYÊN theo docx.
      title: "Khám chuyên khoa — Khám trong (dấu hiệu sinh dục thứ phát)",
      fields: [
        { key: "moi_lon", label: "Môi lớn", type: "text" },
        { key: "moi_be", label: "Môi bé", type: "text" },
        { key: "am_vat", label: "Âm vật", type: "text" },
        { key: "am_ho", label: "Âm hộ", type: "text" },
        { key: "mang_trinh", label: "Màng trinh", type: "text" },
        { key: "tang_sinh_mon", label: "Tầng sinh môn", type: "text" },
      ],
    },
    {
      title: "Khám chuyên khoa — Khám ngoài",
      fields: [
        { key: "am_dao", label: "Âm đạo", type: "text" },
        { key: "co_tu_cung", label: "Cổ tử cung", type: "text" },
        { key: "than_tu_cung", label: "Thân tử cung", type: "text" },
        { key: "phan_phu", label: "Phần phụ", type: "text" },
        { key: "tui_cung", label: "Các túi cùng", type: "text" },
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
        { key: "cls_niem_mac_tc", label: "Niêm mạc tử cung (mm)", type: "text" },
        { key: "cls_co_tc", label: "Cơ tử cung", type: "text" },
        { key: "cls_nang_noan_afc", label: "Nang noãn / AFC (số nang 2-10mm)", type: "text" },
        { key: "cls_pap_thinprep", label: "PAP smear / Thin-prep", type: "text" },
        { key: "cls_hpv", label: "HPV test", type: "text" },
        { key: "cls_sinh_thiet_ctc", label: "Sinh thiết CTC", type: "text" },
        { key: "cls_sinh_thiet_nmtc", label: "Sinh thiết NM tử cung (nếu chỉ định)", type: "text" },
        { key: "cls_mammo_sa_vu", label: "Mammography / SA vú", type: "text" },
        { key: "cls_dxa", label: "Đo mật độ xương DXA (T-score)", type: "text" },
      ],
    },
    {
      title: "Chẩn đoán",
      fields: [{ key: "chan_doan", label: "Chẩn đoán", type: "textarea", fullWidth: true }],
    },
    {
      title: "Điều trị",
      fields: [{ key: "dieu_tri", label: "Điều trị", type: "textarea", fullWidth: true }],
    },
    {
      title: "Theo dõi và tái khám",
      fields: [
        { key: "tai_kham_ngay", label: "Ngày tái khám", type: "date" },
        {
          key: "tai_kham_xn",
          label: "Xét nghiệm cần kiểm tra lại",
          type: "checkbox_group",
          options: TAIKHAM_XN,
          fullWidth: true,
        },
      ],
    },
  ],
};
