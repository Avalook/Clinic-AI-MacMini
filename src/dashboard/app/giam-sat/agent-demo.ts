// DỮ LIỆU GIẢ LẬP cho dashboard Agent giám sát — mở `/ops?tab=agent&demo=1`.
// Chỉ để xem giao diện khi máy local / staging chưa có khách. Không gọi máy chủ,
// không ghi gì. Số liệu dựng theo một ngày thứ Sáu đông vừa ở Kim Ngưu.

const bayGio = new Date();
const luc = (gio: number, phut: number) => {
  const d = new Date(bayGio);
  d.setHours(gio, phut, 0, 0);
  return d.toISOString();
};

export const DEMO_TONG_QUAN = {
  van_hanh: {
    dang_trong_phong_kham: 23,
    dang_cho: 9,
    dang_lam: 11,
    cho_qua_nguong: 3,
    cho_lau_nhat_phut: 47,
    check_in_hom_nay: 58,
    da_ve_hom_nay: 35,
    check_in_hom_qua_cung_gio: 52,
    theo_gio: [
      { gio: 7, so: 3 },
      { gio: 8, so: 9 },
      { gio: 9, so: 12 },
      { gio: 10, so: 10 },
      { gio: 11, so: 6 },
      { gio: 12, so: 2 },
      { gio: 13, so: 4 },
      { gio: 14, so: 7 },
      { gio: 15, so: 5 },
      { gio: 16, so: 0 },
      { gio: 17, so: 0 },
      { gio: 18, so: 0 },
      { gio: 19, so: 0 },
      { gio: 20, so: 0 },
    ],
  },
  phong: [
    { id: "p1", ma: "TD", ten: "Quầy tiếp đón", tang: 1, dang_lam: 2, dang_cho: 1, cho_lau_nhat: 4, nguong_phut: 15, nguong_nguoi: 6, trang_thai: "ok", nhan_khach: true },
    { id: "p2", ma: "SH", ten: "Đo sinh hiệu", tang: 1, dang_lam: 1, dang_cho: 0, cho_lau_nhat: 0, nguong_phut: 15, nguong_nguoi: 5, trang_thai: "ok", nhan_khach: true },
    { id: "p3", ma: "LM", ten: "Lấy mẫu", tang: 1, dang_lam: 1, dang_cho: 2, cho_lau_nhat: 12, nguong_phut: 20, nguong_nguoi: 6, trang_thai: "ok", nhan_khach: true },
    { id: "p4", ma: "TT", ten: "Quầy thuốc", tang: 1, dang_lam: 1, dang_cho: 1, cho_lau_nhat: 6, nguong_phut: 20, nguong_nguoi: 6, trang_thai: "ok", nhan_khach: true },
    { id: "p5", ma: "NT", ten: "Phòng Nội tiết", tang: 2, dang_lam: 1, dang_cho: 2, cho_lau_nhat: 18, nguong_phut: 20, nguong_nguoi: 4, trang_thai: "ok", nhan_khach: true },
    { id: "p6", ma: "SC", ten: "Phòng Sàn chậu", tang: 2, dang_lam: 1, dang_cho: 1, cho_lau_nhat: 9, nguong_phut: 20, nguong_nguoi: 4, trang_thai: "ok", nhan_khach: true },
    { id: "p7", ma: "SA2", ten: "Siêu âm tầng 2", tang: 2, dang_lam: 1, dang_cho: 5, cho_lau_nhat: 31, nguong_phut: 20, nguong_nguoi: 4, trang_thai: "critical", nhan_khach: true },
    { id: "p8", ma: "SSA", ten: "Sản / Siêu âm", tang: 2, dang_lam: 1, dang_cho: 3, cho_lau_nhat: 24, nguong_phut: 20, nguong_nguoi: 4, trang_thai: "warning", nhan_khach: true },
    { id: "p9", ma: "TTH", ten: "Phòng thủ thuật", tang: 3, dang_lam: 1, dang_cho: 1, cho_lau_nhat: 47, nguong_phut: 30, nguong_nguoi: 3, trang_thai: "warning", nhan_khach: true },
    { id: "p10", ma: "TNG", ten: "Thủ thuật ngoài giờ", tang: 3, dang_lam: 0, dang_cho: 0, cho_lau_nhat: 0, nguong_phut: 30, nguong_nguoi: 3, trang_thai: "ok", nhan_khach: false },
    { id: "p11", ma: "SA3", ten: "Siêu âm tầng 3", tang: 3, dang_lam: 1, dang_cho: 0, cho_lau_nhat: 0, nguong_phut: 20, nguong_nguoi: 4, trang_thai: "ok", nhan_khach: true },
    { id: "p12", ma: "DT", ten: "Đối tác bên ngoài", tang: null, dang_lam: 0, dang_cho: 2, cho_lau_nhat: 15, nguong_phut: 60, nguong_nguoi: 10, trang_thai: "ok", nhan_khach: true },
  ],
  he_thong: {
    su_kien_on: true,
    su_kien_ly_do: [] as string[],
    loi_moi: 1,
    loi_24h: 3,
    canh_bao: [
      { ma: "LUOT_TREO", muc: "warning", noi_dung: "2 lượt khám từ hôm trước chưa đóng (check-out)." },
    ],
  },
  agent: { critical: 2, warning: 4, vong_cuoi: luc(bayGio.getHours(), Math.max(0, bayGio.getMinutes() - 1)) },
} as const;

export const DEMO_CHI_PHI = {
  hom_nay_usd: 0.3184,
  hom_nay_vnd: 8278,
  tran_ngay_usd: 2,
  con_lai_hom_nay_usd: 1.6816,
  ty_gia_vnd: 26000,
  so_ngay: 7,
  gan_day_bi_cat: false,
  theo_model: [
    { model: "claude-opus-5-5", lan_goi: 9, lan_loi: 0, vao: 41820, ra: 12960, doc_cache: 18000, ghi_cache: 6200, usd: 1.6247, thieu_gia: false },
    { model: "claude-haiku-5-5", lan_goi: 31, lan_loi: 1, vao: 52100, ra: 9400, doc_cache: 0, ghi_cache: 0, usd: 0.0099, thieu_gia: false },
  ],
  theo_ngay: [
    { ngay: "2026-10-09", lan_goi: 6, usd: 0.3184 },
    { ngay: "2026-10-08", lan_goi: 7, usd: 0.2911 },
    { ngay: "2026-10-07", lan_goi: 5, usd: 0.2406 },
    { ngay: "2026-10-06", lan_goi: 6, usd: 0.2735 },
    { ngay: "2026-10-05", lan_goi: 4, usd: 0.1802 },
    { ngay: "2026-10-04", lan_goi: 6, usd: 0.3012 },
    { ngay: "2026-10-03", lan_goi: 6, usd: 0.0296 },
  ],
  gan_day: [
    { luc: luc(12, 31), tinh_nang: "agent_tom_tat", model: "claude-opus-5-5", vao: 4620, ra: 1380, doc_cache: 2000, ghi_cache: 0, usd: 0.0469, thanh_cong: true, loi: null, thoi_gian_ms: 18400 },
    { luc: luc(11, 2), tinh_nang: "agent_tom_tat", model: "claude-opus-5-5", vao: 4410, ra: 1290, doc_cache: 2000, ghi_cache: 0, usd: 0.0438, thanh_cong: true, loi: null, thoi_gian_ms: 16900 },
  ],
  bang_gia: [
    { model: "claude-opus-5-5", vao: 4, ra: 20, doc_cache: 0.2, ghi_cache: 5 },
    { model: "claude-sonnet-5-5", vao: 2, ra: 10, doc_cache: 0.2, ghi_cache: 2.5 },
    { model: "claude-haiku-5-5", vao: 0.1, ra: 0.5, doc_cache: 0.01, ghi_cache: 0.125 },
  ],
  gia_ngay: "06/10/2026",
};

export const DEMO_TOM_TAT = {
  ngay: bayGio.toISOString().slice(0, 10),
  llm_bat: true,
  model: "claude-sonnet-5-5",
  gio_tu_dong: 18,
  tom_tat: {
    id: "demo",
    model: "claude-sonnet-5-5",
    tao_luc: luc(12, 31),
    tu_dong: false,
    noi_dung: `## Tình hình hôm nay
58 khách check-in, 35 đã về, 23 đang trong phòng khám. Cao điểm 9h (12 khách). Siêu âm tầng 2 là nút thắt chính: 5 người chờ, lâu nhất 31 phút.

## Điểm cần chú ý
- Siêu âm tầng 2 quá tải từ 10:40 · 5 chờ / ngưỡng 4, lâu nhất 31′ · Sản/Siêu âm cùng bước đang có 3 chờ, chưa ai điều sang.
- Khách số 41 chờ thủ thuật 47′ (ngưỡng 30′) · chưa có ghi nhận đã giải thích cho khách.
- 2 lượt từ hôm qua chưa check-out · có thể khách đã về mà quên đóng lượt.

## Đề xuất
- Trưởng ca cân 2 khách từ Siêu âm tầng 2 sang Siêu âm tầng 3 (đang rảnh) · xong khi SA2 về ≤ 4 người chờ.
- CSKH báo khách số 41 lý do chờ và giờ dự kiến · xong khi có tương tác CSKH ghi nhận.

## Luật giám sát cần xem lại
- "Phòng quá tải" và "Khách chờ quá ngưỡng" đang báo cùng một chuyện ở SA2 — nên gộp.

## Chưa biết
Không có dữ liệu khách đã được giải thích lý do chờ hay chưa.`,
  },
};

export const DEMO_AGENT = {
  phien_ban: "giam-sat-rule-1",
  tat_het: false,
  bi_cat: false,
  tran: 200,
  thong_ke: [
    { loai: "khach_cho_qua_nguong", ten: "Khách đang chờ quá ngưỡng phòng", che_do: "shadow", dang_mo: 3, tong_14_ngay: 41, dung: 18, sai: 4, khong_ro: 2, do_dung: 0.82 },
    { loai: "phong_qua_tai", ten: "Phòng quá tải", che_do: "shadow", dang_mo: 1, tong_14_ngay: 16, dung: 6, sai: 5, khong_ro: 1, do_dung: 0.55 },
    { loai: "khach_chua_xep_buoc", ten: "Khách đã check-in chưa có bước nào", che_do: "shadow", dang_mo: 0, tong_14_ngay: 7, dung: 5, sai: 0, khong_ro: 0, do_dung: 1 },
    { loai: "khach_lang_im", ten: "Khách lặng im (không hàng chờ, không sự kiện)", che_do: "shadow", dang_mo: 1, tong_14_ngay: 12, dung: 7, sai: 2, khong_ro: 3, do_dung: 0.78 },
    { loai: "luot_khong_ro_co_so", ten: "Lượt không rõ cơ sở", che_do: "shadow", dang_mo: 0, tong_14_ngay: 2, dung: 2, sai: 0, khong_ro: 0, do_dung: 1 },
    { loai: "viec_qua_han", ten: "Việc trách nhiệm quá hạn", che_do: "tat", dang_mo: 1, tong_14_ngay: 3, dung: 1, sai: 0, khong_ro: 0, do_dung: 1 },
  ],
  nhan_dinh: [
    { id: "d1", loai: "phong_qua_tai", ten_loai: "Phòng quá tải", muc: "critical", noi_dung: "Siêu âm tầng 2: 5 người chờ, lâu nhất 31 phút (ngưỡng 4 người / 20 phút).", muc_bang_chung: "quan_sat", so_lan: 52, mo_luc: luc(10, 41), lan_cuoi: luc(11, 33), dong_luc: null, ly_do_dong: null, danh_gia: null, danh_gia_ghi_chu: null },
    { id: "d2", loai: "khach_cho_qua_nguong", ten_loai: "Khách đang chờ quá ngưỡng phòng", muc: "critical", noi_dung: "Khách số 41 chờ 47 phút tại Thực hiện thủ thuật (ngưỡng 30 phút).", muc_bang_chung: "quan_sat", so_lan: 17, mo_luc: luc(11, 16), lan_cuoi: luc(11, 33), dong_luc: null, ly_do_dong: null, danh_gia: "dung", danh_gia_ghi_chu: null },
    { id: "d3", loai: "khach_cho_qua_nguong", ten_loai: "Khách đang chờ quá ngưỡng phòng", muc: "warning", noi_dung: "Khách số 37 chờ 26 phút tại Siêu âm (ngưỡng 20 phút).", muc_bang_chung: "quan_sat", so_lan: 6, mo_luc: luc(11, 27), lan_cuoi: luc(11, 33), dong_luc: null, ly_do_dong: null, danh_gia: null, danh_gia_ghi_chu: null },
    { id: "d4", loai: "khach_lang_im", ten_loai: "Khách lặng im", muc: "warning", noi_dung: "Khách số 29 không ở hàng chờ nào và 38 phút chưa có sự kiện mới (cuối: payment.service_collected) — có thể bị quên, hoặc đã về mà chưa check-out.", muc_bang_chung: "suy_ra", so_lan: 8, mo_luc: luc(11, 25), lan_cuoi: luc(11, 33), dong_luc: null, ly_do_dong: null, danh_gia: null, danh_gia_ghi_chu: null },
    { id: "d5", loai: "khach_cho_qua_nguong", ten_loai: "Khách đang chờ quá ngưỡng phòng", muc: "warning", noi_dung: "Khách số 44 chờ 24 phút tại Sản / Siêu âm (ngưỡng 20 phút).", muc_bang_chung: "quan_sat", so_lan: 4, mo_luc: luc(11, 29), lan_cuoi: luc(11, 33), dong_luc: null, ly_do_dong: null, danh_gia: null, danh_gia_ghi_chu: null },
    { id: "d6", loai: "viec_qua_han", ten_loai: "Việc trách nhiệm quá hạn", muc: "warning", noi_dung: "Việc 'Đối soát tiền: dịch vụ đã thu nhưng không làm' quá hạn 35 phút, vẫn chưa xong.", muc_bang_chung: "quan_sat", so_lan: 35, mo_luc: luc(10, 58), lan_cuoi: luc(11, 33), dong_luc: null, ly_do_dong: null, danh_gia: null, danh_gia_ghi_chu: null },
    { id: "d7", loai: "khach_cho_qua_nguong", ten_loai: "Khách đang chờ quá ngưỡng phòng", muc: "warning", noi_dung: "Khách số 18 chờ 22 phút tại Lấy mẫu (ngưỡng 20 phút).", muc_bang_chung: "quan_sat", so_lan: 3, mo_luc: luc(9, 40), lan_cuoi: luc(9, 43), dong_luc: luc(9, 44), ly_do_dong: "HET", danh_gia: "dung", danh_gia_ghi_chu: null },
  ],
};
