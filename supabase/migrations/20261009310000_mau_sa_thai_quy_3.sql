-- MẪU MỚI "Kết quả siêu âm thai quý III" (Tuyền 09/10/2026).
--
-- Nguồn: PDF "Kết quả siêu âm thai quý III.pdf" của phòng khám; cấu trúc chép
-- từ mẫu SA_THAI_QUY_23 (mã ô, kiểu ô, câu bình thường điền sẵn). Năm mục:
-- Mô tả hình ảnh · Tham số sinh học · Phần phụ thai nhi · Hình ảnh khác · Kết
-- luận. KHÔNG có Đề nghị (PDF không có). Số đo không điền sẵn (an toàn lâm
-- sàng, như v3); câu "bình thường" của PDF điền sẵn như mẫu quý II–III. Khung
-- giống hệt `mau_ket_qua_v3.json` → "SA_THAI_QUY_3".
--
--   1. Danh mục `SA_THAI_QUY_3` + form `KQ_SA_THAI_QUY_3` bản 1 cho mọi phòng
--      khám (đã có bản nào thì không đụng — sửa nội dung là việc của màn).
--   2. GẮN THÊM cho đúng các dịch vụ đang gắn `SA_THAI_QUY_23` (chép
--      `result_mode`). Quý II–III VẪN là mẫu chọn sẵn: cột mới
--      `dich_vu_mau_ket_qua.thu_tu` — mẫu gắn thêm mang thu_tu lớn hơn, đứng sau
--      (`mau_goi_y.mau_cho_cac_dich_vu` xếp thu_tu rồi mới tên). Xếp theo tên
--      thôi thì "…quý III" đứng TRƯỚC "…quý II - III" (collation en_US bỏ qua
--      " - ") và giành chỗ mặc định. Bác sĩ đổi sang quý III ở ô chọn mẫu của
--      phiếu kết quả.
--
-- HÀM gắn để seed.sql gọi lại: trên DB dựng mới migration chạy TRƯỚC khi bảng
-- giá có dịch vụ, mẫu quý II–III gắn trong seed (`gan_mau_ket_qua_theo_kiotviet`).
-- Chạy lại được: ON CONFLICT / NOT EXISTS.

ALTER TABLE public.dich_vu_mau_ket_qua
    ADD COLUMN IF NOT EXISTS thu_tu smallint NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.dich_vu_mau_ket_qua.thu_tu IS
'Thứ tự mẫu của một dịch vụ — nhỏ đứng trước và được chọn sẵn; bằng nhau thì theo tên. 0 = như cũ (09/10/2026).';

INSERT INTO public.ket_qua_mau (clinic_id, ma, nhom, ten)
SELECT c.id, 'SA_THAI_QUY_3',
       coalesce((SELECT k.nhom FROM public.ket_qua_mau k
                  WHERE k.clinic_id = c.id AND k.ma = 'SA_THAI_QUY_23'),
                'Siêu âm Sản khoa'),
       'Kết quả siêu âm thai quý III'
  FROM public.clinic c
ON CONFLICT (clinic_id, ma) DO NOTHING;

INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai,
     xuat_ban_boi, xuat_ban_luc)
SELECT k.clinic_id, 'KQ_SA_THAI_QUY_3', 1, k.ten,
       coalesce((SELECT d.nhom FROM public.form_definition d
                  WHERE d.clinic_id = k.clinic_id
                    AND d.form_id = 'KQ_SA_THAI_QUY_23'
                    AND d.trang_thai = 'PUBLISHED'), k.nhom),
       $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "01", "don_vi": "thai"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh (theo quý I)", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "goi_y": "chu kỳ/phút", "don_vi": "chu kỳ/phút"}, {"ma": "ngoi_thai", "ten": "Ngôi thai", "kieu": "text"}]}, {"ma": "tham_so_sinh_hoc", "ten": "Tham số sinh học", "block": [{"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh (BPD)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "khoang_cach_hai_ho_mat", "ten": "Khoảng cách 2 hố mắt (BOD)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "xuong_song_mui", "ten": "Xương sống mũi (NBL)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu (HC)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng (AC)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi (FL)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "chieu_dai_xuong_canh_tay", "ten": "Chiều dài xương cánh tay (HL)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "dong_mach_ron", "ten": "Động mạch rốn (MPI)", "kieu": "text", "goi_y": "__ ~ __ %"}, {"ma": "dong_mach_nao_giua", "ten": "Động mạch não giữa (UPI)", "kieu": "text", "goi_y": "__ ~ __ %"}, {"ma": "chi_so_nuoc_oi", "ten": "Chỉ số nước ối (AFI)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "cpr", "ten": "CPR", "kieu": "text", "goi_y": "__ ~ __ %"}, {"ma": "bpp", "ten": "BPP", "kieu": "text", "goi_y": "điểm", "don_vi": "điểm"}, {"ma": "tieu_nao", "ten": "Hình ảnh tiểu não (Cere)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "ho_sau", "ten": "Kích thước hố sau (CM)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "nao_that_ben", "ten": "Não thất bên (VP)", "kieu": "text", "goi_y": "mm", "don_vi": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính", "kieu": "text", "goi_y": "grams", "don_vi": "grams"}]}, {"ma": "phan_phu_thai_nhi", "ten": "Phần phụ thai nhi", "block": [{"ma": "nhau_thai", "ten": "Nhau thai", "kieu": "text", "mac_dinh": "Không thấy máu tụ sau nhau. Độ dày bình thường."}, {"ma": "day_ron", "ten": "Dây rốn", "kieu": "text", "mac_dinh": "2 động mạch, 1 tĩnh mạch, đúng vị trí, hiện tại chưa thấy bất thường."}, {"ma": "rau_bam", "ten": "Rau bám", "kieu": "text"}, {"ma": "nuoc_oi", "ten": "Nước ối", "kieu": "text", "mac_dinh": "chưa thấy bất thường"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Khảo sát Doppler chưa thấy bất thường."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường ở tuần thai này."}]}]$khung$::jsonb,
       'PUBLISHED', NULL, now()
  FROM public.ket_qua_mau k
 WHERE k.ma = 'SA_THAI_QUY_3'
   AND NOT EXISTS (SELECT 1 FROM public.form_definition d
                    WHERE d.clinic_id = k.clinic_id
                      AND d.form_id = 'KQ_SA_THAI_QUY_3');

CREATE OR REPLACE FUNCTION public.gan_mau_sa_thai_quy_3()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE n integer;
BEGIN
  INSERT INTO dich_vu_mau_ket_qua
      (clinic_id, service_code, mau, result_mode, thu_tu)
  SELECT g.clinic_id, g.service_code, 'SA_THAI_QUY_3', g.result_mode,
         -- Đứng SAU mọi mẫu đang gắn của dịch vụ ấy.
         (SELECT max(x.thu_tu) + 1 FROM dich_vu_mau_ket_qua x
           WHERE x.clinic_id = g.clinic_id AND x.service_code = g.service_code)
    FROM dich_vu_mau_ket_qua g
    JOIN ket_qua_mau k ON k.clinic_id = g.clinic_id AND k.ma = 'SA_THAI_QUY_3'
   WHERE g.mau = 'SA_THAI_QUY_23'
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$fn$;

COMMENT ON FUNCTION public.gan_mau_sa_thai_quy_3() IS
'Gắn thêm mẫu SA_THAI_QUY_3 cho mọi dịch vụ đang gắn SA_THAI_QUY_23, đứng sau (thu_tu) — quý II–III vẫn chọn sẵn. Chạy lại được; seed.sql gọi lại sau khi gắn mẫu v3 (09/10/2026).';

SELECT public.gan_mau_sa_thai_quy_3();
