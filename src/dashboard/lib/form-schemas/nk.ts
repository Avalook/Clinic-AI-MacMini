// Form KHÁM NAM KHOA (`service_code` = "NK"), theo docs/spec-form-nam-khoa.md §5.
//
// FORM NÀY ĐANG TẮT TRONG DANH MỤC, và phải giữ như vậy cho tới khi có bác sĩ ký
// duyệt: `activate_clinical_form()` từ chối bật nếu chưa có dòng trong
// `clinical_form_approval` (ai duyệt, bản nào, tài liệu nào). Đừng lật cờ bằng
// một lệnh UPDATE — xem 20260804000019.
//
// BA NHÁNH, KHÔNG PHẢI MỘT (spec §3). Phòng khám khám nam khoa rộng hơn vô sinh:
// `service_type.NAM_KHOA` đặt lịch độc lập, và nhóm thuốc L9 có Tadalafil +
// Avanafil. Nên `nhanh` chọn ở đầu và các section dùng `parent` để ẩn/hiện:
//
//     HM    hiếm muộn / vô sinh nam
//     RLTD  rối loạn cương / xuất tinh
//     SKSS  sức khoẻ sinh sản / tiền hôn nhân
//
// KHÔNG CÓ NGƯỠNG WHO NÀO TRONG FILE NÀY (spec §7.3). Ngưỡng nằm ở bảng
// `semen_reference_range` và cờ bất thường do `andrology_service.flag_semen`
// tính rồi trả về. WHO đã đổi ngưỡng qua ba ấn bản; nhốt số vào đây là mất luôn
// câu trả lời cho "kết quả năm ngoái được đọc theo ngưỡng nào".
//
// IIEF-5 CHƯA CÓ TRONG FORM, CÓ CHỦ Ý. Đó là bộ câu hỏi có bản quyền/giấy phép
// (spec §9.4). Backend đã có `score_iief5` để chấm khi phòng khám xác nhận được
// quyền dùng — hoặc khi bác sĩ soạn bộ câu hỏi thay thế. Chép nguyên văn 5 câu
// vào đây là quyết định pháp lý, không phải quyết định kỹ thuật.

import type { FormField, FormSchema } from "./types";

const KHONG_CO = [
  { value: "khong", label: "Không" },
  { value: "co", label: "Có" },
];
const KHONG_CO_KHONGRO = [
  ...KHONG_CO,
  { value: "khong_ro", label: "Không rõ" },
];
const HAI_BEN = [
  { value: "khong", label: "Không" },
  { value: "t", label: "Trái" },
  { value: "p", label: "Phải" },
  { value: "hai_ben", label: "Hai bên" },
];

/** Chỉ hiện ở nhánh hiếm muộn. */
const CHI_HM = { key: "nhanh", equals: "HM" } as const;
/** Chỉ hiện ở nhánh rối loạn tình dục. */
const CHI_RLTD = { key: "nhanh", equals: "RLTD" } as const;

// ── Tinh dịch đồ ───────────────────────────────────────────────────────────
//
// Chín thông số gốc của phòng khám + ba thông số WHO 2021 mà phiếu giấy thiếu.
// Hai cột lần 1 / lần 2: AUA yêu cầu làm ≥2 lần cách nhau ~1 tháng khi kết quả
// bất thường, và một con số đơn lẻ không đủ để kết luận điều gì.
const TDD: { key: string; label: string; unit?: string }[] = [
  { key: "tdd_the_tich", label: "Thể tích", unit: "mL" },
  { key: "tdd_ph", label: "pH" },
  { key: "tdd_nong_do", label: "Nồng độ tinh trùng", unit: "triệu/mL" },
  { key: "tdd_tong_so", label: "Tổng số tinh trùng", unit: "triệu" },
  { key: "tdd_di_dong_tong", label: "Tổng độ di động", unit: "%" },
  { key: "tdd_pr", label: "Tiến tới (PR)", unit: "%" },
  { key: "tdd_np", label: "Di động không tiến tới (NP)", unit: "%" },
  { key: "tdd_im", label: "Bất động (IM)", unit: "%" },
  { key: "tdd_song", label: "Tỷ lệ sống", unit: "%" },
  { key: "tdd_kruger", label: "Hình dạng bình thường (Kruger)", unit: "%" },
  { key: "tdd_bach_cau", label: "Bạch cầu", unit: "triệu/mL" },
];

const tddFields: FormField[] = TDD.flatMap((p) => [
  {
    key: `${p.key}_l1`,
    label: `${p.label} — lần 1`,
    type: "number" as const,
    unit: p.unit,
  },
  {
    key: `${p.key}_l2`,
    label: `${p.label} — lần 2`,
    type: "number" as const,
    unit: p.unit,
  },
]);

export const nkSchema: FormSchema = {
  service_code: "NK",
  title: "Khám Nam khoa",
  sections: [
    // ── 5.0 ──────────────────────────────────────────────────────────────
    {
      title: "Lý do khám & nhánh",
      fields: [
        {
          key: "nhanh",
          label: "Nhánh khám",
          type: "radio",
          fullWidth: true,
          options: [
            { value: "HM", label: "Hiếm muộn – vô sinh nam" },
            { value: "RLTD", label: "Rối loạn tình dục" },
            { value: "SKSS", label: "Sức khoẻ sinh sản / tiền hôn nhân" },
          ],
        },
        {
          key: "ly_do",
          label: "Lý do khám",
          type: "checkbox_group",
          fullWidth: true,
          options: [
            { value: "chua_co_con", label: "Chưa có con" },
            { value: "rl_cuong", label: "Rối loạn cương" },
            { value: "xuat_tinh_som", label: "Xuất tinh sớm" },
            { value: "giam_ham_muon", label: "Giảm ham muốn" },
            { value: "tdd_bat_thuong", label: "Tinh dịch đồ bất thường" },
            { value: "dau_sung_biu", label: "Đau / sưng bìu" },
            { value: "viem_nhiem", label: "Viêm nhiễm" },
            { value: "tien_hon_nhan", label: "Khám tiền hôn nhân" },
            { value: "vo_dang_dieu_tri", label: "Vợ đang điều trị HMVS" },
          ],
        },
        { key: "ly_do_khac", label: "Lý do khác", type: "text", fullWidth: true },
        {
          // Bật ô này KHÔNG tự mở hồ sơ cho người vợ. Chia sẻ dữ liệu giữa hai
          // bệnh nhân phải có bản đồng ý riêng, có chữ ký — xem §6.5 và
          // `clinical_data_consent`. Ô này chỉ nói "ca này thuộc luồng cặp đôi".
          key: "lien_ket_hmvs",
          label: "Thuộc hồ sơ cặp đôi HMVS",
          type: "checkbox",
          fullWidth: true,
        },
      ],
    },

    // ── 5.1 ──────────────────────────────────────────────────────────────
    {
      title: "Tiền sử sinh sản",
      fields: [
        {
          key: "ts_thoi_gian_mong_con",
          label: "Thời gian mong con",
          type: "number",
          unit: "tháng",
          parent: CHI_HM,
        },
        {
          key: "ts_co_con",
          label: "Đã có con",
          type: "radio",
          options: [
            { value: "chua", label: "Chưa" },
            { value: "voi_ban_doi", label: "Có với bạn đời hiện tại" },
            { value: "voi_nguoi_khac", label: "Có với người khác" },
          ],
        },
        { key: "ts_so_con", label: "Số con", type: "number" },
        {
          key: "ts_tan_suat_qh",
          label: "Tần suất giao hợp",
          type: "radio",
          options: [
            { value: "duoi_1", label: "< 1 lần/tuần" },
            { value: "1_2", label: "1–2 lần/tuần" },
            { value: "3_4", label: "3–4 lần/tuần" },
            { value: "tren_4", label: "> 4 lần/tuần" },
          ],
          parent: CHI_HM,
        },
        {
          key: "ts_dung_boi_tron",
          label: "Dùng chất bôi trơn",
          type: "checkbox",
          parent: CHI_HM,
        },
        {
          key: "ts_dieu_tri_hm",
          label: "Đã điều trị hiếm muộn",
          type: "checkbox_group",
          fullWidth: true,
          options: [
            { value: "chua", label: "Chưa" },
            { value: "thuoc", label: "Thuốc" },
            { value: "iui", label: "IUI" },
            { value: "ivf", label: "IVF / ICSI" },
            { value: "phau_thuat", label: "Phẫu thuật" },
          ],
          parent: CHI_HM,
        },
      ],
    },

    // ── 5.2 ──────────────────────────────────────────────────────────────
    {
      title: "Tiền sử bệnh & phơi nhiễm",
      fields: [
        {
          key: "ts_benh_sinh_duc_tiet_nieu",
          label: "Bệnh lý sinh dục / tiết niệu",
          type: "textarea",
          fullWidth: true,
        },
        {
          key: "ts_phau_thuat",
          label: "Phẫu thuật vùng bìu / bẹn / tuyến tiền liệt",
          type: "textarea",
          fullWidth: true,
        },
        {
          key: "ts_quai_bi",
          label: "Quai bị có biến chứng",
          type: "radio",
          options: KHONG_CO_KHONGRO,
        },
        {
          key: "ts_tinh_hoan_an",
          label: "Tinh hoàn ẩn / xuống bìu muộn",
          type: "radio",
          options: HAI_BEN,
        },
        {
          key: "ts_xoan_chan_thuong",
          label: "Xoắn tinh hoàn / chấn thương bìu",
          type: "radio",
          options: KHONG_CO,
        },
        {
          key: "ts_thoat_vi_ben",
          label: "Mổ thoát vị bẹn",
          type: "radio",
          options: KHONG_CO,
        },
        {
          key: "ts_hoa_xa_tri",
          label: "Hoá trị / xạ trị",
          type: "radio",
          options: KHONG_CO,
        },
        {
          key: "ts_hoa_xa_tri_ct",
          label: "Chi tiết hoá / xạ trị",
          type: "conditional",
          fullWidth: true,
          parent: { key: "ts_hoa_xa_tri", equals: "co" },
        },
        {
          // Testosterone ngoại sinh gây vô tinh. Bỏ sót dòng này là chẩn đoán
          // nhầm thành vô tinh không do tắc — một chẩn đoán đổi hẳn hướng điều
          // trị, và ngưng thuốc thì phần lớn hồi phục.
          key: "ts_testosterone_ngoai",
          label: "Đang / đã dùng testosterone, steroid đồng hoá",
          type: "radio",
          fullWidth: true,
          options: [
            { value: "khong", label: "Không" },
            { value: "dang_dung", label: "Đang dùng" },
            { value: "ngung_duoi_6", label: "Đã ngưng < 6 tháng" },
            { value: "ngung_tren_6", label: "Đã ngưng ≥ 6 tháng" },
          ],
        },
        {
          key: "ts_thuoc_dang_dung",
          label: "Thuốc đang dùng",
          type: "textarea",
          fullWidth: true,
        },
        {
          key: "ts_nghe_nghiep",
          label: "Nghề nghiệp / tiếp xúc hoá chất / nhiệt độ cao",
          type: "textarea",
          fullWidth: true,
        },
        {
          key: "ts_thuoc_la",
          label: "Hút thuốc",
          type: "radio",
          options: [
            { value: "khong", label: "Không" },
            { value: "da_bo", label: "Đã bỏ" },
            { value: "dang_hut", label: "Đang hút" },
          ],
        },
        {
          key: "ts_ruou",
          label: "Rượu bia",
          type: "radio",
          options: [
            { value: "khong", label: "Không" },
            { value: "thinh_thoang", label: "Thỉnh thoảng" },
            { value: "thuong_xuyen", label: "Thường xuyên" },
          ],
        },
        {
          key: "ts_benh_toan_than",
          label: "Bệnh toàn thân",
          type: "checkbox_group",
          fullWidth: true,
          options: [
            { value: "dtd", label: "Đái tháo đường" },
            { value: "tha", label: "Tăng huyết áp" },
            { value: "mo_mau", label: "Rối loạn mỡ máu" },
            { value: "tuyen_giap", label: "Bệnh tuyến giáp" },
            { value: "beo_phi", label: "Béo phì" },
          ],
        },
        {
          key: "ts_nhiem_trung",
          label: "Nhiễm trùng",
          type: "checkbox_group",
          fullWidth: true,
          options: [
            { value: "lao", label: "Lao" },
            { value: "lqdtd", label: "Bệnh lây qua đường tình dục" },
            { value: "viem_mao_tinh", label: "Viêm mào tinh" },
          ],
        },
        { key: "ts_di_ung", label: "Dị ứng thuốc", type: "text", fullWidth: true },
      ],
    },

    // ── 5.3 ──────────────────────────────────────────────────────────────
    //
    // KHÔNG CÓ IIEF-5 Ở ĐÂY. Xem ghi chú đầu file: bộ câu hỏi có bản quyền, và
    // quyết định dùng nó là quyết định pháp lý của phòng khám. Các mục dưới đây
    // là câu hỏi lâm sàng thông thường, không thuộc bộ nào.
    {
      title: "Tiền sử tình dục",
      fields: [
        {
          key: "td_xuat_tinh",
          label: "Kiểu xuất tinh",
          type: "radio",
          fullWidth: true,
          options: [
            { value: "binh_thuong", label: "Bình thường" },
            { value: "som", label: "Sớm" },
            { value: "muon", label: "Muộn" },
            { value: "khong_xuat_tinh", label: "Không xuất tinh" },
            { value: "nghi_nguoc_dong", label: "Nghi ngược dòng" },
          ],
          parent: CHI_RLTD,
        },
        {
          key: "td_ielt",
          label: "Thời gian đến khi xuất tinh (ước tính)",
          type: "number",
          unit: "phút",
          parent: CHI_RLTD,
        },
        {
          key: "td_ham_muon",
          label: "Ham muốn tình dục",
          type: "radio",
          options: [
            { value: "binh_thuong", label: "Bình thường" },
            { value: "giam", label: "Giảm" },
            { value: "tang", label: "Tăng" },
          ],
          parent: CHI_RLTD,
        },
        {
          // Còn cương buổi sáng thì hướng tâm lý nhiều hơn thực thể. Một dòng,
          // và nó đổi hẳn hướng hỏi tiếp.
          key: "td_cuong_sang",
          label: "Cương buổi sáng",
          type: "radio",
          options: [
            { value: "con", label: "Còn" },
            { value: "giam", label: "Giảm" },
            { value: "mat", label: "Mất" },
          ],
          parent: CHI_RLTD,
        },
      ],
    },

    // ── 5.4 ──────────────────────────────────────────────────────────────
    {
      title: "Khám toàn thân",
      fields: [
        { key: "kls_chieu_cao", label: "Chiều cao", type: "number", unit: "cm" },
        { key: "kls_can_nang", label: "Cân nặng", type: "number", unit: "kg" },
        // BMI KHÔNG có ô nhập: backend tính từ chiều cao/cân nặng
        // (`andrology_service.compute_bmi`). Một ô nhập tay là một ô sẽ lệch với
        // hai số ngay bên cạnh nó.
        { key: "kls_huyet_ap", label: "Huyết áp", type: "text" },
        { key: "kls_mach", label: "Mạch", type: "number", unit: "lần/phút" },
        {
          key: "kls_nam_hoa",
          label: "Phát triển sinh dục thứ phát / nam hoá",
          type: "radio",
          options: [
            { value: "binh_thuong", label: "Bình thường" },
            { value: "kem", label: "Kém" },
            { value: "khong_danh_gia", label: "Không đánh giá" },
          ],
        },
        {
          key: "kls_vu_to",
          label: "Vú to nam giới",
          type: "radio",
          options: HAI_BEN,
        },
        {
          key: "kls_seo_bung_ben",
          label: "Sẹo mổ vùng bụng / bẹn",
          type: "text",
          fullWidth: true,
        },
      ],
    },

    // ── 5.5 ──────────────────────────────────────────────────────────────
    {
      title: "Khám dương vật / niệu đạo",
      fields: [
        {
          key: "kls_lo_tieu",
          label: "Vị trí lỗ tiểu",
          type: "radio",
          options: [
            { value: "binh_thuong", label: "Bình thường" },
            { value: "thap", label: "Lỗ tiểu thấp" },
            { value: "tren", label: "Lỗ tiểu trên" },
          ],
        },
        {
          key: "kls_bao_quy_dau",
          label: "Bao quy đầu",
          type: "radio",
          options: [
            { value: "binh_thuong", label: "Bình thường" },
            { value: "hep", label: "Hẹp" },
            { value: "dai", label: "Dài" },
            { value: "da_cat", label: "Đã cắt" },
          ],
        },
        {
          key: "kls_mang_xo_dv",
          label: "Mảng xơ cứng dương vật (Peyronie)",
          type: "radio",
          options: KHONG_CO,
        },
        {
          key: "kls_mang_xo_dv_ct",
          label: "Mô tả mảng xơ",
          type: "conditional",
          fullWidth: true,
          parent: { key: "kls_mang_xo_dv", equals: "co" },
        },
        {
          key: "kls_ton_thuong_dv",
          label: "Tổn thương / loét / dịch tiết niệu đạo",
          type: "radio",
          options: KHONG_CO,
        },
        {
          key: "kls_ton_thuong_dv_ct",
          label: "Mô tả tổn thương",
          type: "conditional",
          fullWidth: true,
          parent: { key: "kls_ton_thuong_dv", equals: "co" },
        },
      ],
    },
    {
      title: "Khám tinh hoàn & mào tinh",
      fields: [
        ...(["t", "p"] as const).flatMap((ben) => {
          const ten = ben === "t" ? "trái" : "phải";
          return [
            {
              key: `kls_th_vi_tri_${ben}`,
              label: `Vị trí tinh hoàn ${ten}`,
              type: "radio" as const,
              options: [
                { value: "trong_biu", label: "Trong bìu" },
                { value: "ong_ben", label: "Ống bẹn" },
                { value: "khong_so_thay", label: "Không sờ thấy" },
              ],
            },
            {
              key: `kls_th_the_tich_${ben}`,
              label: `Thể tích tinh hoàn ${ten}`,
              type: "number" as const,
              unit: "mL",
            },
            {
              key: `kls_th_mat_do_${ben}`,
              label: `Mật độ tinh hoàn ${ten}`,
              type: "radio" as const,
              options: [
                { value: "chac", label: "Chắc" },
                { value: "mem", label: "Mềm" },
                { value: "cung", label: "Cứng" },
              ],
            },
            {
              key: `kls_mao_tinh_${ben}`,
              label: `Mào tinh ${ten}`,
              type: "radio" as const,
              options: [
                { value: "binh_thuong", label: "Bình thường" },
                { value: "cang_gian", label: "Căng giãn" },
                { value: "chai_cung", label: "Chai cứng" },
                { value: "nang", label: "Nang / spermatocele" },
                { value: "khong_so_thay", label: "Không sờ thấy" },
              ],
            },
            {
              // "Không sờ thấy" hai bên là cửa vào chỉ định CFTR (nghi CBAVD).
              // Backend đọc đúng ô này trong `suggest_genetic_tests`.
              key: `kls_ong_dan_tinh_${ben}`,
              label: `Ống dẫn tinh ${ten}`,
              type: "radio" as const,
              options: [
                { value: "binh_thuong", label: "Sờ thấy bình thường" },
                { value: "khong_so_thay", label: "Không sờ thấy" },
                { value: "not_sau_that", label: "Nốt sau thắt" },
                { value: "bat_thuong_khac", label: "Bất thường khác" },
              ],
            },
            {
              key: `kls_gtmt_${ben}`,
              label: `Giãn tĩnh mạch tinh ${ten}`,
              type: "radio" as const,
              options: [
                { value: "0", label: "0 — dưới lâm sàng" },
                { value: "I", label: "I — chỉ sờ thấy khi Valsalva" },
                { value: "II", label: "II — sờ thấy không cần Valsalva" },
                { value: "III", label: "III — nhìn thấy bằng mắt" },
              ],
            },
          ];
        }),
        {
          // Một số mL không kèm cách đo thì không so sánh được giữa hai lần
          // khám, và cũng không so được giữa hai bác sĩ.
          key: "kls_th_pp_do",
          label: "Phương pháp đo thể tích tinh hoàn",
          type: "radio",
          fullWidth: true,
          options: [
            { value: "prader", label: "Thước Prader" },
            { value: "sieu_am", label: "Siêu âm" },
            { value: "uoc_luong", label: "Ước lượng" },
          ],
        },
        {
          key: "kls_th_khoi_bat_thuong",
          label: "Khối bất thường ở tinh hoàn",
          type: "radio",
          options: KHONG_CO,
        },
        {
          key: "kls_th_khoi_bat_thuong_ct",
          label: "Mô tả khối",
          type: "conditional",
          fullWidth: true,
          parent: { key: "kls_th_khoi_bat_thuong", equals: "co" },
        },
        {
          key: "kls_dre",
          label: "Thăm trực tràng",
          type: "radio",
          fullWidth: true,
          options: [
            { value: "khong_lam", label: "Không làm" },
            { value: "binh_thuong", label: "Bình thường" },
            { value: "nang_duong_giua", label: "Nang đường giữa" },
            { value: "gian_tui_tinh", label: "Giãn túi tinh" },
          ],
        },
      ],
    },

    // ── 5.6 ──────────────────────────────────────────────────────────────
    {
      title: "Điều kiện lấy mẫu tinh dịch",
      fields: [
        {
          // Không có mấy dòng này thì con số bên dưới không diễn giải được:
          // kiêng 1 ngày và kiêng 7 ngày cho ra hai kết quả khác hẳn.
          key: "tdd_kieng_xuat_tinh",
          label: "Số ngày kiêng xuất tinh",
          type: "number",
          unit: "ngày",
        },
        {
          key: "tdd_cach_lay_mau",
          label: "Cách lấy mẫu",
          type: "radio",
          options: [
            { value: "thu_dam_tai_cho", label: "Thủ dâm tại chỗ" },
            { value: "tai_nha", label: "Tại nhà" },
            { value: "bao_chuyen_dung", label: "Bao cao su chuyên dụng" },
          ],
        },
        {
          key: "tdd_thoi_gian_den_pt",
          label: "Thời gian từ lấy mẫu đến phân tích",
          type: "number",
          unit: "phút",
        },
        { key: "tdd_ly_giai", label: "Ly giải", type: "number", unit: "phút" },
        {
          key: "tdd_mat_mau",
          label: "Mất một phần mẫu",
          type: "radio",
          options: KHONG_CO,
        },
      ],
    },
    {
      title: "Tinh dịch đồ",
      fields: [
        ...tddFields,
        {
          key: "tdd_danh_gia",
          label: "Đánh giá của phòng xét nghiệm",
          type: "textarea",
          fullWidth: true,
        },
      ],
    },

    // ── 5.7 ──────────────────────────────────────────────────────────────
    {
      title: "Nội tiết & xét nghiệm máu",
      fields: [
        { key: "nt_fsh", label: "FSH", type: "number", unit: "mIU/mL" },
        { key: "nt_lh", label: "LH", type: "number", unit: "mIU/mL" },
        {
          key: "nt_testosterone",
          label: "Testosterone toàn phần",
          type: "number",
          unit: "nmol/L",
        },
        {
          // Testosterone dao động theo giờ. Không ghi giờ lấy máu thì một kết
          // quả thấp buổi chiều đọc thành suy sinh dục.
          key: "nt_gio_lay_mau",
          label: "Giờ lấy máu",
          type: "text",
          placeholder: "vd 08:15, lúc đói",
        },
        { key: "nt_prolactin", label: "Prolactin", type: "number" },
        { key: "nt_estradiol", label: "Estradiol", type: "number" },
        { key: "nt_shbg", label: "SHBG", type: "number" },
        { key: "nt_tsh", label: "TSH", type: "number" },
        { key: "nt_ft4", label: "FT4", type: "number" },
        { key: "sh_glucose", label: "Đường huyết đói", type: "number" },
        { key: "sh_hba1c", label: "HbA1c", type: "number", unit: "%" },
        { key: "sh_mo_mau", label: "Bộ mỡ máu", type: "text", fullWidth: true },
      ],
    },

    // ── 5.8 ──────────────────────────────────────────────────────────────
    //
    // AUA nói KHÔNG làm siêu âm bìu thường quy lần khám đầu, và KHÔNG làm DFI
    // thường quy. Nên đây là chỗ GHI KẾT QUẢ đã có, không phải chỗ chỉ định.
    // Gợi ý xét nghiệm di truyền do backend tính kèm lý do; bác sĩ tự tick.
    {
      title: "Hình ảnh & di truyền (ghi kết quả đã có)",
      fields: [
        {
          key: "cls_sa_biu",
          label: "Siêu âm bìu / Doppler",
          type: "textarea",
          fullWidth: true,
          placeholder:
            "Thể tích T/P, echo, vi vôi hoá, đường kính TM, trào ngược khi Valsalva",
        },
        {
          key: "cls_trus",
          label: "Siêu âm qua trực tràng / MRI chậu",
          type: "textarea",
          fullWidth: true,
        },
        { key: "cls_sa_than", label: "Siêu âm thận", type: "text", fullWidth: true },
        { key: "cls_karyotype", label: "Nhiễm sắc thể đồ", type: "text" },
        { key: "cls_y_microdel", label: "Mất đoạn nhỏ NST Y", type: "text" },
        { key: "cls_cftr", label: "CFTR + alen 5T", type: "text" },
        { key: "cls_dfi", label: "Phân mảnh DNA tinh trùng (DFI)", type: "text" },
      ],
    },

    // ── 5.9 – 5.11 ───────────────────────────────────────────────────────
    {
      title: "Chẩn đoán & hướng xử trí",
      fields: [
        { key: "chan_doan", label: "Chẩn đoán", type: "textarea", fullWidth: true },
        {
          key: "dieu_tri",
          label: "Hướng xử trí / điều trị",
          type: "textarea",
          fullWidth: true,
        },
        {
          key: "tai_kham",
          label: "Hẹn tái khám",
          type: "date",
        },
        {
          key: "theo_doi",
          label: "Nội dung theo dõi",
          type: "textarea",
          fullWidth: true,
        },
      ],
    },
  ],
};
