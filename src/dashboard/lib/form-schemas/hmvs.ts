// Config form KHÁM HIẾM MUỘN - VÔ SINH (service_code "HMVS").
// Nguồn: section "Khám Hiếm muộn - Vô sinh" (Heading-3) trong docs/forms/handover_kham.docx.
// Field lấy ĐÚNG theo docx (bao gồm khám nam khoa + tinh dịch đồ chồng). KHÔNG bịa.
// Tinh dịch đồ có 2 cột "Kết quả lần 1 / lần 2" → 2 field _l1/_l2 mỗi thông số.

import type { FormSchema } from "./types";

const LY_DO = [
  { value: "chua_thai_12m", label: "Chưa có thai sau 12 tháng QHTD không tránh thai" },
  { value: "chua_thai_6m_35", label: "Chưa có thai sau 6 tháng (tuổi ≥ 35)" },
  { value: "vo_kinh_rl", label: "Vô kinh / rối loạn kinh nguyệt" },
  { value: "bat_thuong_tdd", label: "Bất thường tinh dịch đồ" },
  { value: "ts_pt_pk", label: "Tiền sử phẫu thuật phụ khoa" },
  { value: "say_thai_lt", label: "Tiền sử sẩy thai liên tiếp (≥ 2 lần)" },
  { value: "lac_nmtc", label: "Lạc nội mạc tử cung" },
  { value: "pcos", label: "Hội chứng buồng trứng đa nang (PCOS)" },
  { value: "tu_van_iui", label: "Tư vấn trước điều trị IUI" },
  { value: "tu_van_ivf", label: "Tư vấn trước điều trị IVF / ICSI" },
];

const TRI_HIEM_MUON = [
  { value: "chua_dt", label: "Chưa điều trị" },
  { value: "kich_trung", label: "Thuốc kích thích rụng trứng" },
  { value: "iui", label: "IUI" },
  { value: "ivf_icsi", label: "IVF/ICSI" },
  { value: "pt_noi_soi", label: "Phẫu thuật nội soi" },
  { value: "dt_lac_nm", label: "Điều trị lạc nội mạc" },
];

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

const GIA_DINH = [
  { value: "vo_sinh", label: "Vô sinh / hiếm muộn" },
  { value: "pcos", label: "PCOS" },
  { value: "man_kinh_som", label: "Mãn kinh sớm" },
  { value: "lac_nm", label: "Lạc nội mạc" },
  { value: "bat_thuong_nst", label: "Bất thường nhiễm sắc thể" },
  { value: "ung_thu_vu_bt", label: "Ung thư vú / buồng trứng" },
  { value: "dtd", label: "Đái tháo đường" },
  { value: "tim_mach_som", label: "Tim mạch sớm" },
];

const PP_DIEU_TRI = [
  { value: "oi", label: "Kích thích rụng trứng (OI) đơn thuần" },
  { value: "qh_tu_nhien", label: "Quan hệ tự nhiên theo lịch rụng trứng" },
  { value: "iui", label: "Bơm tinh trùng vào buồng tử cung (IUI)" },
  { value: "ivf", label: "Thụ tinh trong ống nghiệm (IVF)" },
  { value: "icsi", label: "Tiêm tinh trùng vào bào tương noãn (ICSI)" },
  { value: "fet", label: "Trữ lạnh phôi (FET)" },
  { value: "egg_freezing", label: "Trữ lạnh noãn (Egg Freezing)" },
  { value: "pgt", label: "Xét nghiệm di truyền tiền làm tổ (PGT-A/M/SR)" },
  { value: "xin_noan_tt_phoi", label: "Xin noãn / xin tinh trùng / xin phôi" },
  { value: "pt_noi_soi_art", label: "Phẫu thuật nội soi trước ART" },
  { value: "dt_nam_khoa", label: "Điều trị nam khoa trước IUI/IVF" },
  { value: "mang_thai_ho", label: "Mang thai hộ (nếu đủ điều kiện pháp lý)" },
];

const TU_VAN_HO_TRO = [
  { value: "axit_folic", label: "Axit folic / vitamin tổng hợp trước mang thai" },
  { value: "coq10", label: "Bổ sung CoQ10 (cải thiện chất lượng noãn / tinh trùng)" },
  { value: "omega3_vit", label: "Omega-3 / Vitamin D / Vitamin E" },
  { value: "tang_prolactin", label: "Điều trị tăng prolactin (Cabergoline)" },
  { value: "pcos", label: "Điều trị PCOS (Metformin, giảm cân)" },
  { value: "tuyen_giap", label: "Điều trị tuyến giáp (Levothyroxine)" },
  { value: "lac_nmtc", label: "Điều trị lạc nội mạc tử cung" },
  { value: "tu_van_tam_ly", label: "Tư vấn tâm lý / giảm stress" },
  { value: "loi_song", label: "Điều chỉnh lối sống (cân nặng, dinh dưỡng)" },
];

const TAIKHAM = [
  { value: "hormone_d2d3", label: "Hormone (D2/D3)" },
  { value: "amh", label: "AMH" },
  { value: "tinh_dich_do", label: "Tinh dịch đồ" },
  { value: "sa_nang_noan", label: "Siêu âm theo dõi nang noãn" },
  { value: "progesterone_d21", label: "Progesterone D21" },
  { value: "nst_do", label: "Nhiễm sắc thể đồ" },
  { value: "pap_hpv", label: "PAP smear / HPV" },
  { value: "sinh_hoa_mau", label: "Sinh hóa máu" },
];

// 9 thông số tinh dịch đồ — mỗi cái 2 lần đo (lần 1 / lần 2).
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

export const hmvsSchema: FormSchema = {
  service_code: "HMVS",
  title: "Khám Hiếm muộn - Vô sinh",
  sections: [
    {
      title: "Lý do khám bệnh",
      fields: [
        { key: "ly_do", label: "Lý do khám bệnh", type: "checkbox_group", options: LY_DO, fullWidth: true },
        { key: "ly_do_khac", label: "Khác", type: "text", fullWidth: true },
      ],
    },
    {
      title: "Tiền sử Phụ khoa, Sản khoa (vợ)",
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
        { key: "tg_quan_he_khong_tranh_thai", label: "Thời gian quan hệ không tránh thai", type: "text" },
        { key: "benh_pk_dang_dieu_tri", label: "Các bệnh phụ khoa đang điều trị", type: "text" },
        { key: "phau_thuat_pk", label: "Phẫu thuật phụ khoa", type: "text" },
      ],
    },
    {
      title: "Tiền sử (chồng)",
      fields: [
        { key: "chong_con_truoc", label: "Tiền sử có con trước", type: "text", fullWidth: true },
        { key: "chong_benh_sd_tn", label: "Bệnh lý sinh dục / tiết niệu", type: "text", fullWidth: true },
        { key: "chong_pt_biu_ben_tlt", label: "Phẫu thuật vùng bìu / bẹn / tuyến tiền liệt", type: "text", fullWidth: true },
        { key: "chong_quai_bi", label: "Tiền sử quai bị có biến chứng", type: "text", fullWidth: true },
        { key: "chong_nghe_nghiep", label: "Nghề nghiệp / tiếp xúc hóa chất / nhiệt độ cao", type: "text", fullWidth: true },
      ],
    },
    {
      title: "Tiền sử trị hiếm muộn",
      fields: [
        { key: "tri_hiem_muon", label: "Tiền sử trị hiếm muộn", type: "checkbox_group", options: TRI_HIEM_MUON, fullWidth: true },
        { key: "iui_so_chu_ky", label: "IUI — số chu kỳ", type: "number" },
        { key: "ivf_so_chu_ky", label: "IVF/ICSI — số chu kỳ", type: "number" },
        { key: "tri_hiem_muon_chi_tiet", label: "Chi tiết", type: "textarea", fullWidth: true },
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
      title: "Tiền sử gia đình",
      fields: [
        { key: "gia_dinh", label: "Tiền sử gia đình", type: "checkbox_group", options: GIA_DINH, fullWidth: true },
        { key: "gia_dinh_khac", label: "Khác", type: "text", fullWidth: true },
      ],
    },
    {
      title: "Bệnh sử",
      fields: [{ key: "benh_su", label: "Quá trình bệnh lý hiện tại", type: "textarea", fullWidth: true }],
    },
    {
      title: "Khám lâm sàng tổng quát",
      fields: [
        { key: "nhip_tim", label: "Nhịp tim", type: "number", unit: "l/p" },
        { key: "nhiet_do", label: "Nhiệt độ", type: "number", unit: "°C" },
        { key: "huyet_ap", label: "Huyết áp", type: "text", unit: "mmHg", placeholder: "vd 120/80" },
        { key: "nhip_tho", label: "Nhịp thở", type: "number", unit: "l/p" },
        { key: "can_nang", label: "Cân nặng", type: "number", unit: "kg" },
        // docx ghi "BMT" — //TODO-BS-REVIEW: nhiều khả năng BMI.
        { key: "bmt", label: "BMT", type: "text" },
        { key: "da_niem_mac", label: "Da niêm mạc", type: "text" },
        { key: "tuyen_giap", label: "Tuyến giáp", type: "text" },
        { key: "vu", label: "Vú", type: "text" },
        { key: "cuong_androgen", label: "Dấu hiệu cường androgen", type: "text" },
      ],
    },
    {
      title: "Khám phụ khoa (vợ) — Khám ngoài",
      fields: [
        { key: "sinh_duc_thu_phat", label: "Dấu hiệu sinh dục thứ phát", type: "text" },
        { key: "long_mu", label: "Lông mu", type: "text" },
        { key: "moi_am_vat", label: "Môi lớn / môi bé / âm vật", type: "text" },
        { key: "am_ho_mang_trinh_tsm", label: "Âm hộ / màng trinh / tầng sinh môn", type: "text" },
      ],
    },
    {
      title: "Khám phụ khoa (vợ) — Khám trong",
      fields: [
        { key: "am_dao", label: "Âm đạo", type: "text" },
        { key: "co_tu_cung", label: "Cổ tử cung", type: "text" },
        { key: "than_tu_cung", label: "Thân tử cung (kích thước, tư thế, mật độ, di động)", type: "text", fullWidth: true },
        { key: "phan_phu", label: "Phần phụ T/P", type: "text" },
        { key: "tui_cung", label: "Các túi cùng", type: "text" },
      ],
    },
    {
      title: "Khám nam khoa",
      fields: [
        { key: "nk_tinh_hoan", label: "Tinh hoàn T/P (thể tích, mật độ)", type: "text", fullWidth: true },
        { key: "nk_mao_tinh", label: "Mào tinh / ống dẫn tinh", type: "text" },
        { key: "nk_gian_tm_tinh", label: "Giãn tĩnh mạch tinh (độ)", type: "text" },
        { key: "nk_duong_vat_nieu_dao", label: "Dương vật / niệu đạo", type: "text" },
      ],
    },
    {
      title: "Cận lâm sàng — A. Xét nghiệm máu / sinh hóa",
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
      title: "Cận lâm sàng — B. Nội tiết tố sinh sản (Vợ – D2/D3)",
      fields: [
        { key: "cls_fsh", label: "FSH (mIU/mL)", type: "text" },
        { key: "cls_lh", label: "LH (mIU/mL)", type: "text" },
        { key: "cls_e2", label: "Estradiol E2 (pg/mL)", type: "text" },
        { key: "cls_progesterone", label: "Progesterone (ng/mL)", type: "text" },
        { key: "cls_prolactin", label: "Prolactin (ng/mL)", type: "text" },
        { key: "cls_testosterone", label: "Testosterone tổng (ng/dL)", type: "text" },
        { key: "cls_dheas", label: "DHEA-S (µg/dL)", type: "text" },
        { key: "cls_amh", label: "AMH (ng/mL) – dự trữ buồng trứng", type: "text" },
        { key: "cls_inhibin_b", label: "Inhibin B (pg/mL)", type: "text" },
        { key: "cls_tsh_ft4", label: "TSH / FT4 (tuyến giáp)", type: "text" },
        { key: "cls_anti_tpo", label: "Anti-TPO (kháng thể kháng giáp)", type: "text" },
        { key: "cls_17ohp", label: "17-OHP (nghi ngờ tăng sản thượng thận)", type: "text" },
      ],
    },
    {
      title: "Cận lâm sàng — C. Tinh dịch đồ (Chồng)",
      fields: tddFields,
    },
    {
      title: "Cận lâm sàng — D. Hình ảnh học & thăm dò chức năng",
      fields: [
        { key: "cls_sa_pttc_vo", label: "Siêu âm PTTC (TA/DA) – VỢ", type: "text" },
        { key: "cls_hsg", label: "Chụp buồng tử cung – vòi trứng (HSG)", type: "text" },
        { key: "cls_noi_soi_btc", label: "Nội soi buồng tử cung", type: "text" },
        { key: "cls_noi_soi_o_bung", label: "Nội soi ổ bụng", type: "text" },
        { key: "cls_sa_tinh_hoan", label: "Siêu âm tinh hoàn / Doppler – CHỒNG", type: "text" },
        { key: "cls_pap_hpv", label: "PAP smear / HPV test", type: "text" },
        { key: "cls_karyotype", label: "Nhiễm sắc thể đồ (Karyotype) – nếu chỉ định", type: "text" },
        { key: "cls_y_microdel", label: "Y-chromosome microdeletion (Nam)", type: "text" },
        { key: "cls_dxa", label: "Đo mật độ xương DXA – nếu chỉ định", type: "text" },
      ],
    },
    {
      title: "Chẩn đoán",
      fields: [
        { key: "cd_nguyen_nhan_vo", label: "Nguyên nhân vợ", type: "text", fullWidth: true },
        { key: "cd_nguyen_nhan_chong", label: "Nguyên nhân chồng", type: "text", fullWidth: true },
        { key: "cd_nguyen_nhan_phoi_hop", label: "Nguyên nhân phối hợp", type: "text", fullWidth: true },
        { key: "cd_benh_kem", label: "Bệnh kèm theo", type: "text", fullWidth: true },
        { key: "cd_phan_biet", label: "Chẩn đoán phân biệt", type: "text", fullWidth: true },
        {
          key: "cd_phan_loai",
          label: "Phân loại hiếm muộn",
          type: "radio",
          options: [
            { value: "nguyen_phat", label: "Nguyên phát" },
            { value: "thu_phat", label: "Thứ phát" },
          ],
        },
        { key: "cd_thoi_gian_nam", label: "Thời gian (năm)", type: "number", unit: "năm" },
        {
          key: "cd_tien_luong",
          label: "Tiên lượng",
          type: "radio",
          options: [
            { value: "tot", label: "Tốt" },
            { value: "trung_binh", label: "Trung bình" },
            { value: "de_dat", label: "Dè dặt" },
            { value: "nang", label: "Nặng" },
          ],
        },
      ],
    },
    {
      title: "Hướng xử trí — A. Phương pháp điều trị được chỉ định",
      fields: [
        { key: "pp_dieu_tri", label: "Phương pháp điều trị", type: "checkbox_group", options: PP_DIEU_TRI, fullWidth: true },
      ],
    },
    {
      title: "Hướng xử trí — B. Phác đồ kích thích buồng trứng",
      fields: [
        // //TODO docx mơ hồ: phác đồ chọn 1 hay nhiều — tạm radio (lâm sàng thường 1). //TODO-BS-REVIEW.
        {
          key: "phac_do_kt",
          label: "Phác đồ kích thích buồng trứng",
          type: "radio",
          options: [
            { value: "dai_agonist", label: "Phác đồ dài (GnRH agonist)" },
            { value: "ngan_antagonist", label: "Phác đồ ngắn (GnRH antagonist)" },
            { value: "nhe_minimal", label: "Phác đồ nhẹ / minimal stimulation" },
            { value: "natural_cycle", label: "Natural cycle IVF" },
            { value: "ppos", label: "PPOS (Progestin-Primed)" },
            { value: "luteal", label: "Luteal phase stimulation" },
          ],
        },
        { key: "phac_do_thuoc", label: "Thuốc FSH/LH (tên, liều)", type: "text", fullWidth: true },
        { key: "ho_tro_hoang_the", label: "Hỗ trợ hoàng thể", type: "text", fullWidth: true },
      ],
    },
    {
      title: "Hướng xử trí — C. Tư vấn / hỗ trợ / điều trị bổ sung",
      fields: [
        { key: "tu_van_ho_tro", label: "Tư vấn – hỗ trợ – điều trị bổ sung", type: "checkbox_group", options: TU_VAN_HO_TRO, fullWidth: true },
        { key: "tu_van_khac", label: "Khác", type: "text", fullWidth: true },
        { key: "tu_van_chi_tiet", label: "Chi tiết", type: "textarea", fullWidth: true },
      ],
    },
    {
      title: "Hướng xử trí — D. Lối sống / dinh dưỡng / vận động",
      fields: [
        // docx là hướng dẫn cố định → để ô ghi chú. //TODO docx mơ hồ.
        { key: "loi_song_ghi_chu", label: "Lối sống – Dinh dưỡng – Vận động (ghi chú)", type: "textarea", fullWidth: true },
      ],
    },
    {
      title: "Theo dõi & Tái khám",
      fields: [
        { key: "tai_kham_ngay", label: "Ngày tái khám", type: "date" },
        { key: "chu_ky_dieu_tri_tiep", label: "Chu kỳ điều trị tiếp theo", type: "text" },
        { key: "tai_kham_xn", label: "Xét nghiệm / thăm dò cần kiểm tra lại", type: "checkbox_group", options: TAIKHAM, fullWidth: true },
        { key: "tai_kham_khac", label: "Khác", type: "text", fullWidth: true },
        { key: "ghi_chu_dac_biet", label: "Ghi chú đặc biệt", type: "textarea", fullWidth: true },
      ],
    },
  ],
};
