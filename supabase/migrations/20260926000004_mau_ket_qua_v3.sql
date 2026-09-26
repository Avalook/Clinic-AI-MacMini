-- 17 MẪU KẾT QUẢ v3 THEO PDF GỐC (Tuyền 26/09/2026 — lát 3 bản giao diện mẫu).
-- Nguồn: bản giao diện mẫu Tuyền duyệt (dựng từ 17 PDF phòng khám). Sinh bằng
-- scripts/phieu-kham/dung-mau-ket-qua-v3.py → src/clinicai/phieu_kham/
-- mau_ket_qua_v3.json (cùng dữ liệu). Mẫu dựng theo chi-dinh.html (Gemini)
-- như BI-RADS/TIRADS KHÔNG còn trong v3; XN_TONG_QUAT (không có PDF) giữ nguyên.
--
-- Lưu theo `ma`. Mục dạng BẢNG khai `cot` — giá trị ô là {ma_cột: giá trị}.
-- Số đo, âm/dương, xét nghiệm gửi ngoài KHÔNG điền sẵn (an toàn lâm sàng).
--
-- Chỉ thay bản do HỆ THỐNG xuất bản (xuat_ban_boi NULL): phòng khám đã tự xuất
-- bản thì không đè. Bản cũ → RETIRED; phiếu đã điền ghim bản cũ vẫn đọc đúng.
-- Sau đó GẮN mẫu vào dịch vụ theo mã phòng khám (KiotViet) của PDF — bảng gắn
-- trước giờ rỗng (chờ người duyệt); Tuyền duyệt 26/09: theo nguồn chuẩn.
-- Chạy lại được.

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_THAI_SOM' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "01 thai"}, {"ma": "chieu_dai_dau_mong", "ten": "Chiều dài đầu mông (CRL)", "kieu": "text", "goi_y": "mm"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "mac_dinh": "dương tính"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không thấy tụ dịch dưới màng nuôi."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hình ảnh 01 thai trong buồng tử cung, tương đương ?? tuần ?? ngày. Tim thai dương tính."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_THAI_SOM'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_THAI_SOM',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_THAI_SOM'),
       'Kết quả siêu âm thai sớm (dưới 11 tuần)', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "01 thai"}, {"ma": "chieu_dai_dau_mong", "ten": "Chiều dài đầu mông (CRL)", "kieu": "text", "goi_y": "mm"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "mac_dinh": "dương tính"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không thấy tụ dịch dưới màng nuôi."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hình ảnh 01 thai trong buồng tử cung, tương đương ?? tuần ?? ngày. Tim thai dương tính."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_THAI_QUY_1' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh_tham_so_sinh_hoc", "ten": "Mô tả hình ảnh / Tham số sinh học", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "01 thai"}, {"ma": "chieu_dai_dau_mong", "ten": "Chiều dài đầu mông (CRL)", "kieu": "text", "goi_y": "mm"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "do_mo_da_gay", "ten": "Độ mờ da gáy (NT)", "kieu": "text", "goi_y": "mm"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "goi_y": "chu kỳ/phút"}, {"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh (BPD)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu (HC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng (AC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi (FL)", "kieu": "text", "goi_y": "mm"}, {"ma": "do_dai_xuong_mui", "ten": "Độ dài xương mũi (NBL)", "kieu": "text", "goi_y": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính", "kieu": "text", "goi_y": "± grams"}]}, {"ma": "hinh_thai_thai_nhi", "ten": "Hình thái thai nhi", "block": [{"ma": "dau_mat_co", "ten": "Đầu mặt cổ", "kieu": "doan_van", "mac_dinh": "Đường giữa cân đối. Đám rối mạch mạc lấp đầy não thất bên. Hố sau bình thường. Không có khuyết hàm trên."}, {"ma": "nguc_bung_va_tu_chi", "ten": "Ngực - bụng và tứ chi", "kieu": "text", "mac_dinh": "Lồng ngực cân đối. Mỏm tim quay trái. Thành bụng liên tục. Đủ 4 chi."}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Nhau thai bám rộng. Khảo sát Doppler không thấy bất thường."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hình ảnh 01 thai trong buồng tử cung, tương đương ?? tuần ?? ngày. Tim thai dương tính, cử động thai tốt."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_THAI_QUY_1'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_THAI_QUY_1',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_THAI_QUY_1'),
       'Kết quả siêu âm thai quý I', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh_tham_so_sinh_hoc", "ten": "Mô tả hình ảnh / Tham số sinh học", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "01 thai"}, {"ma": "chieu_dai_dau_mong", "ten": "Chiều dài đầu mông (CRL)", "kieu": "text", "goi_y": "mm"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "do_mo_da_gay", "ten": "Độ mờ da gáy (NT)", "kieu": "text", "goi_y": "mm"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "goi_y": "chu kỳ/phút"}, {"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh (BPD)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu (HC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng (AC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi (FL)", "kieu": "text", "goi_y": "mm"}, {"ma": "do_dai_xuong_mui", "ten": "Độ dài xương mũi (NBL)", "kieu": "text", "goi_y": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính", "kieu": "text", "goi_y": "± grams"}]}, {"ma": "hinh_thai_thai_nhi", "ten": "Hình thái thai nhi", "block": [{"ma": "dau_mat_co", "ten": "Đầu mặt cổ", "kieu": "doan_van", "mac_dinh": "Đường giữa cân đối. Đám rối mạch mạc lấp đầy não thất bên. Hố sau bình thường. Không có khuyết hàm trên."}, {"ma": "nguc_bung_va_tu_chi", "ten": "Ngực - bụng và tứ chi", "kieu": "text", "mac_dinh": "Lồng ngực cân đối. Mỏm tim quay trái. Thành bụng liên tục. Đủ 4 chi."}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Nhau thai bám rộng. Khảo sát Doppler không thấy bất thường."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hình ảnh 01 thai trong buồng tử cung, tương đương ?? tuần ?? ngày. Tim thai dương tính, cử động thai tốt."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_THAI_QUY_23' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh_tham_so_sinh_hoc", "ten": "Mô tả hình ảnh / Tham số sinh học", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "01 thai"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh (theo quý I)", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "goi_y": "chu kỳ/phút"}, {"ma": "ngoi_thai", "ten": "Ngôi thai", "kieu": "text"}, {"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh (BPD)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu (HC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng (AC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi (FL)", "kieu": "text", "goi_y": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính", "kieu": "text", "goi_y": "± grams"}]}, {"ma": "hinh_thai_thai_nhi", "ten": "Hình thái thai nhi — chỉ số", "block": [{"ma": "kich_thuoc_nao_that_ben", "ten": "Kích thước não thất bên (Vp)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "duong_kinh_tieu_nao", "ten": "Đường kính tiểu não (Cerebellum)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "ho_sau", "ten": "Hố sau (CM)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "duong_kinh_hai_hoc_mat", "ten": "Đường kính hai hốc mắt (BOD)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "do_dai_xuong_mui", "ten": "Độ dài xương mũi (NBL)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "do_dai_xuong_canh_tay", "ten": "Độ dài xương cánh tay (HL)", "kieu": "text", "mac_dinh": "bình thường"}]}, {"ma": "hinh_thai_thai_nhi_2", "ten": "Hình thái thai nhi — mô tả", "block": [{"ma": "dau_mat_co", "ten": "Đầu mặt cổ", "kieu": "doan_van", "mac_dinh": "Hai bán cầu đại não cân đối. Hộp vách trong suốt rõ. Xương vòm sọ liên tục. Môi trên liên tục. Nhãn cầu cân đối, thủy tinh thể rõ."}, {"ma": "tim_va_long_nguc", "ten": "Tim và lồng ngực", "kieu": "doan_van", "mac_dinh": "Lồng ngực cân đối. Mỏm tim quay trái, đủ 4 buồng tim, đại động mạch bắt chéo."}, {"ma": "o_bung", "ten": "Ổ bụng", "kieu": "text", "mac_dinh": "Bóng dạ dày rõ. Quan sát thấy thận hai bên."}, {"ma": "tu_chi", "ten": "Tứ chi", "kieu": "text", "mac_dinh": "Đủ 4 chi. Bàn tay tư thế nắm. Sơ bộ chưa thấy bất thường trục chi."}]}, {"ma": "phan_phu_thai_nhi", "ten": "Phần phụ thai nhi", "block": [{"ma": "nhau_thai", "ten": "Nhau thai", "kieu": "text", "mac_dinh": "Không thấy máu tụ sau nhau. Độ dày bình thường."}, {"ma": "day_ron", "ten": "Dây rốn", "kieu": "text", "mac_dinh": "2 động mạch, 1 tĩnh mạch, hiện tại chưa thấy bất thường."}, {"ma": "nuoc_oi", "ten": "Nước ối", "kieu": "text", "mac_dinh": "chưa thấy bất thường"}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Khảo sát Doppler chưa thấy bất thường."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hình ảnh 01 thai trong buồng tử cung. Tim thai dương tính, cử động thai tốt."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_THAI_QUY_23'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_THAI_QUY_23',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_THAI_QUY_23'),
       'Kết quả siêu âm thai quý II - III', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh_tham_so_sinh_hoc", "ten": "Mô tả hình ảnh / Tham số sinh học", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "01 thai"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh (theo quý I)", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "goi_y": "chu kỳ/phút"}, {"ma": "ngoi_thai", "ten": "Ngôi thai", "kieu": "text"}, {"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh (BPD)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu (HC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng (AC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi (FL)", "kieu": "text", "goi_y": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính", "kieu": "text", "goi_y": "± grams"}]}, {"ma": "hinh_thai_thai_nhi", "ten": "Hình thái thai nhi — chỉ số", "block": [{"ma": "kich_thuoc_nao_that_ben", "ten": "Kích thước não thất bên (Vp)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "duong_kinh_tieu_nao", "ten": "Đường kính tiểu não (Cerebellum)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "ho_sau", "ten": "Hố sau (CM)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "duong_kinh_hai_hoc_mat", "ten": "Đường kính hai hốc mắt (BOD)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "do_dai_xuong_mui", "ten": "Độ dài xương mũi (NBL)", "kieu": "text", "mac_dinh": "bình thường"}, {"ma": "do_dai_xuong_canh_tay", "ten": "Độ dài xương cánh tay (HL)", "kieu": "text", "mac_dinh": "bình thường"}]}, {"ma": "hinh_thai_thai_nhi_2", "ten": "Hình thái thai nhi — mô tả", "block": [{"ma": "dau_mat_co", "ten": "Đầu mặt cổ", "kieu": "doan_van", "mac_dinh": "Hai bán cầu đại não cân đối. Hộp vách trong suốt rõ. Xương vòm sọ liên tục. Môi trên liên tục. Nhãn cầu cân đối, thủy tinh thể rõ."}, {"ma": "tim_va_long_nguc", "ten": "Tim và lồng ngực", "kieu": "doan_van", "mac_dinh": "Lồng ngực cân đối. Mỏm tim quay trái, đủ 4 buồng tim, đại động mạch bắt chéo."}, {"ma": "o_bung", "ten": "Ổ bụng", "kieu": "text", "mac_dinh": "Bóng dạ dày rõ. Quan sát thấy thận hai bên."}, {"ma": "tu_chi", "ten": "Tứ chi", "kieu": "text", "mac_dinh": "Đủ 4 chi. Bàn tay tư thế nắm. Sơ bộ chưa thấy bất thường trục chi."}]}, {"ma": "phan_phu_thai_nhi", "ten": "Phần phụ thai nhi", "block": [{"ma": "nhau_thai", "ten": "Nhau thai", "kieu": "text", "mac_dinh": "Không thấy máu tụ sau nhau. Độ dày bình thường."}, {"ma": "day_ron", "ten": "Dây rốn", "kieu": "text", "mac_dinh": "2 động mạch, 1 tĩnh mạch, hiện tại chưa thấy bất thường."}, {"ma": "nuoc_oi", "ten": "Nước ối", "kieu": "text", "mac_dinh": "chưa thấy bất thường"}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Khảo sát Doppler chưa thấy bất thường."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hình ảnh 01 thai trong buồng tử cung. Tim thai dương tính, cử động thai tốt."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_SONG_THAI_QUY_1' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "02 thai."}]}, {"ma": "tham_so_sinh_hoc", "ten": "Tham số sinh học (Biometries)", "block": [{"ma": "chieu_dai_dau_mong", "ten": "Chiều dài đầu mông — Crown-rump Length – CRL", "kieu": "text", "goi_y": "mm"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính — Gestational Age – GA", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh — Estimated Date of Delivery – EDD", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai — Fetal Heart Rate - FHR", "kieu": "text", "goi_y": "chu kỳ/phút"}, {"ma": "do_mo_da_gay", "ten": "Độ mờ da gáy — Nuchal Translucency - NT", "kieu": "text", "goi_y": "mm"}, {"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh — Biparietal Diameter - BPD", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu — Head Circumference - HC", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng — Abdominal Circumference - AC", "kieu": "text", "goi_y": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi — Femur Length - FL", "kieu": "text", "goi_y": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính — Estimated Fetal Weight - EFW (Hadlock4)", "kieu": "text", "goi_y": "gram ± 200 grams"}], "cot": [{"ma": "thai_a", "ten": "Thai A"}, {"ma": "thai_b", "ten": "Thai B"}]}, {"ma": "hinh_thai_thai_nhi", "ten": "Hình thái thai nhi (Fetal morphology)", "block": [{"ma": "dau_mat_co", "ten": "Đầu mặt cổ", "kieu": "doan_van"}, {"ma": "vung_lung_nguc_bung_va_tu_chi", "ten": "Vùng lưng, ngực - bụng và tứ chi", "kieu": "doan_van"}], "cot": [{"ma": "thai_a", "ten": "Thai A"}, {"ma": "thai_b", "ten": "Thai B"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Nhau thai bám rộng."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_SONG_THAI_QUY_1'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_SONG_THAI_QUY_1',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_SONG_THAI_QUY_1'),
       'Kết quả siêu âm song thai quý I', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "02 thai."}]}, {"ma": "tham_so_sinh_hoc", "ten": "Tham số sinh học (Biometries)", "block": [{"ma": "chieu_dai_dau_mong", "ten": "Chiều dài đầu mông — Crown-rump Length – CRL", "kieu": "text", "goi_y": "mm"}, {"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính — Gestational Age – GA", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh — Estimated Date of Delivery – EDD", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai — Fetal Heart Rate - FHR", "kieu": "text", "goi_y": "chu kỳ/phút"}, {"ma": "do_mo_da_gay", "ten": "Độ mờ da gáy — Nuchal Translucency - NT", "kieu": "text", "goi_y": "mm"}, {"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh — Biparietal Diameter - BPD", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu — Head Circumference - HC", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng — Abdominal Circumference - AC", "kieu": "text", "goi_y": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi — Femur Length - FL", "kieu": "text", "goi_y": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính — Estimated Fetal Weight - EFW (Hadlock4)", "kieu": "text", "goi_y": "gram ± 200 grams"}], "cot": [{"ma": "thai_a", "ten": "Thai A"}, {"ma": "thai_b", "ten": "Thai B"}]}, {"ma": "hinh_thai_thai_nhi", "ten": "Hình thái thai nhi (Fetal morphology)", "block": [{"ma": "dau_mat_co", "ten": "Đầu mặt cổ", "kieu": "doan_van"}, {"ma": "vung_lung_nguc_bung_va_tu_chi", "ten": "Vùng lưng, ngực - bụng và tứ chi", "kieu": "doan_van"}], "cot": [{"ma": "thai_a", "ten": "Thai A"}, {"ma": "thai_b", "ten": "Thai B"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Nhau thai bám rộng."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_SONG_THAI_QUY_23' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "02 thai"}]}, {"ma": "tham_so_sinh_hoc", "ten": "Tham số sinh học", "block": [{"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh (theo quý I)", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "goi_y": "chu kỳ/phút"}, {"ma": "trac_do_sinh_vat_ly", "ten": "Trắc đồ sinh vật lý (BPP)", "kieu": "text", "goi_y": "điểm"}, {"ma": "ngoi_thai", "ten": "Ngôi thai", "kieu": "text"}, {"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh (BPD)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu (HC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng (AC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi (FL)", "kieu": "text", "goi_y": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính", "kieu": "text", "goi_y": "gram ± 300 grams"}, {"ma": "kich_thuoc_nao_that_ben", "ten": "Kích thước não thất bên (Vp)", "kieu": "text"}, {"ma": "duong_kinh_tieu_nao", "ten": "Đường kính tiểu não (Cerebellum)", "kieu": "text"}, {"ma": "ho_sau", "ten": "Hố sau (CM)", "kieu": "text"}, {"ma": "duong_kinh_hai_hoc_mat", "ten": "Đường kính hai hốc mắt (BOD)", "kieu": "text"}, {"ma": "do_dai_xuong_mui", "ten": "Độ dài xương mũi (NBL)", "kieu": "text"}, {"ma": "do_dai_xuong_canh_tay", "ten": "Độ dài xương cánh tay (HL)", "kieu": "text"}, {"ma": "do_dai_ban_chan", "ten": "Độ dài bàn chân (Foot)", "kieu": "text"}], "cot": [{"ma": "thai_a", "ten": "Thai A"}, {"ma": "thai_b", "ten": "Thai B"}]}, {"ma": "hinh_thai_thai_nhi", "ten": "Hình thái thai nhi", "block": [{"ma": "dau_mat_co_hai_thai", "ten": "Đầu mặt cổ hai thai", "kieu": "text", "mac_dinh": "Chưa thấy bất thường"}, {"ma": "tim_va_long_nguc", "ten": "Tim và lồng ngực", "kieu": "text", "mac_dinh": "Chưa thấy bất thường"}, {"ma": "o_bung", "ten": "Ổ bụng", "kieu": "text", "mac_dinh": "Chưa thấy bất thường"}, {"ma": "tu_chi", "ten": "Tứ chi", "kieu": "text", "mac_dinh": "Chưa thấy bất thường"}]}, {"ma": "phan_phu_thai_nhi", "ten": "Phần phụ thai nhi", "block": [{"ma": "nhau_thai", "ten": "Nhau thai", "kieu": "text", "mac_dinh": "Không thấy máu tụ sau nhau. Độ dày bình thường."}, {"ma": "day_ron_hai_thai", "ten": "Dây rốn hai thai", "kieu": "text", "mac_dinh": "2 động mạch, 1 tĩnh mạch, hiện tại chưa thấy bất thường."}, {"ma": "nuoc_oi", "ten": "Nước ối", "kieu": "text", "mac_dinh": "chưa thấy bất thường"}, {"ma": "khao_sat_doppler", "ten": "Khảo sát Doppler", "kieu": "text", "mac_dinh": "Sơ bộ chưa thấy bất thường"}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "…."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường ở tuần thai này."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_SONG_THAI_QUY_23'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_SONG_THAI_QUY_23',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_SONG_THAI_QUY_23'),
       'Kết quả siêu âm song thai quý II - III', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "so_luong_thai_trong_buong_tu_cung", "ten": "Số lượng thai trong buồng tử cung", "kieu": "text", "mac_dinh": "02 thai"}]}, {"ma": "tham_so_sinh_hoc", "ten": "Tham số sinh học", "block": [{"ma": "tuoi_thai_uoc_tinh", "ten": "Tuổi thai ước tính (GA)", "kieu": "text", "goi_y": "tuần + ngày"}, {"ma": "du_kien_sinh", "ten": "Dự kiến sinh (theo quý I)", "kieu": "text", "goi_y": "ngày"}, {"ma": "tim_thai", "ten": "Tim thai (FHR)", "kieu": "text", "goi_y": "chu kỳ/phút"}, {"ma": "trac_do_sinh_vat_ly", "ten": "Trắc đồ sinh vật lý (BPP)", "kieu": "text", "goi_y": "điểm"}, {"ma": "ngoi_thai", "ten": "Ngôi thai", "kieu": "text"}, {"ma": "duong_kinh_luong_dinh", "ten": "Đường kính lưỡng đỉnh (BPD)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_dau", "ten": "Chu vi vòng đầu (HC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chu_vi_vong_bung", "ten": "Chu vi vòng bụng (AC)", "kieu": "text", "goi_y": "mm"}, {"ma": "chieu_dai_xuong_dui", "ten": "Chiều dài xương đùi (FL)", "kieu": "text", "goi_y": "mm"}, {"ma": "can_nang_uoc_tinh", "ten": "Cân nặng ước tính", "kieu": "text", "goi_y": "gram ± 300 grams"}, {"ma": "kich_thuoc_nao_that_ben", "ten": "Kích thước não thất bên (Vp)", "kieu": "text"}, {"ma": "duong_kinh_tieu_nao", "ten": "Đường kính tiểu não (Cerebellum)", "kieu": "text"}, {"ma": "ho_sau", "ten": "Hố sau (CM)", "kieu": "text"}, {"ma": "duong_kinh_hai_hoc_mat", "ten": "Đường kính hai hốc mắt (BOD)", "kieu": "text"}, {"ma": "do_dai_xuong_mui", "ten": "Độ dài xương mũi (NBL)", "kieu": "text"}, {"ma": "do_dai_xuong_canh_tay", "ten": "Độ dài xương cánh tay (HL)", "kieu": "text"}, {"ma": "do_dai_ban_chan", "ten": "Độ dài bàn chân (Foot)", "kieu": "text"}], "cot": [{"ma": "thai_a", "ten": "Thai A"}, {"ma": "thai_b", "ten": "Thai B"}]}, {"ma": "hinh_thai_thai_nhi", "ten": "Hình thái thai nhi", "block": [{"ma": "dau_mat_co_hai_thai", "ten": "Đầu mặt cổ hai thai", "kieu": "text", "mac_dinh": "Chưa thấy bất thường"}, {"ma": "tim_va_long_nguc", "ten": "Tim và lồng ngực", "kieu": "text", "mac_dinh": "Chưa thấy bất thường"}, {"ma": "o_bung", "ten": "Ổ bụng", "kieu": "text", "mac_dinh": "Chưa thấy bất thường"}, {"ma": "tu_chi", "ten": "Tứ chi", "kieu": "text", "mac_dinh": "Chưa thấy bất thường"}]}, {"ma": "phan_phu_thai_nhi", "ten": "Phần phụ thai nhi", "block": [{"ma": "nhau_thai", "ten": "Nhau thai", "kieu": "text", "mac_dinh": "Không thấy máu tụ sau nhau. Độ dày bình thường."}, {"ma": "day_ron_hai_thai", "ten": "Dây rốn hai thai", "kieu": "text", "mac_dinh": "2 động mạch, 1 tĩnh mạch, hiện tại chưa thấy bất thường."}, {"ma": "nuoc_oi", "ten": "Nước ối", "kieu": "text", "mac_dinh": "chưa thấy bất thường"}, {"ma": "khao_sat_doppler", "ten": "Khảo sát Doppler", "kieu": "text", "mac_dinh": "Sơ bộ chưa thấy bất thường"}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "…."}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường ở tuần thai này."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_TC_BT' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "buong_trung_trai", "ten": "Buồng trứng trái", "kieu": "text", "mac_dinh": "Sơ bộ chưa thấy bất thường"}, {"ma": "buong_trung_phai", "ten": "Buồng trứng phải", "kieu": "text", "mac_dinh": "Sơ bộ chưa thấy bất thường"}, {"ma": "hinh_thai_tu_cung", "ten": "Hình thái tử cung", "kieu": "text", "mac_dinh": "Bình thường"}, {"ma": "tu_the_tu_cung", "ten": "Tư thế tử cung", "kieu": "text", "mac_dinh": "Ngả trước"}, {"ma": "co_tu_cung", "ten": "Cơ tử cung", "kieu": "text", "mac_dinh": "tương đối đồng nhất. không thấy khối bất thường."}, {"ma": "niem_mac_tu_cung", "ten": "Niêm mạc tử cung", "kieu": "text", "goi_y": "mm"}, {"ma": "tui_cung_douglas", "ten": "Túi cùng Douglas", "kieu": "text", "mac_dinh": "Không có dịch"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường hình ảnh tử cung phần phụ."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_TC_BT'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_TC_BT',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_TC_BT'),
       'Kết quả siêu âm tử cung buồng trứng', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "buong_trung_trai", "ten": "Buồng trứng trái", "kieu": "text", "mac_dinh": "Sơ bộ chưa thấy bất thường"}, {"ma": "buong_trung_phai", "ten": "Buồng trứng phải", "kieu": "text", "mac_dinh": "Sơ bộ chưa thấy bất thường"}, {"ma": "hinh_thai_tu_cung", "ten": "Hình thái tử cung", "kieu": "text", "mac_dinh": "Bình thường"}, {"ma": "tu_the_tu_cung", "ten": "Tư thế tử cung", "kieu": "text", "mac_dinh": "Ngả trước"}, {"ma": "co_tu_cung", "ten": "Cơ tử cung", "kieu": "text", "mac_dinh": "tương đối đồng nhất. không thấy khối bất thường."}, {"ma": "niem_mac_tu_cung", "ten": "Niêm mạc tử cung", "kieu": "text", "goi_y": "mm"}, {"ma": "tui_cung_douglas", "ten": "Túi cùng Douglas", "kieu": "text", "mac_dinh": "Không có dịch"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường hình ảnh tử cung phần phụ."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_TC_PP' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "tu_cung_tu_the", "ten": "Tử cung tư thế", "kieu": "text", "mac_dinh": "ngả trước"}, {"ma": "hinh_thai_tu_cung", "ten": "Hình thái tử cung", "kieu": "text", "mac_dinh": "Bình thường, kích thước không to."}, {"ma": "co_tu_cung", "ten": "Cơ tử cung", "kieu": "text", "mac_dinh": "tương đối đồng nhất. không thấy khối bất thường."}, {"ma": "niem_mac_tu_cung", "ten": "Niêm mạc tử cung", "kieu": "text", "goi_y": "mm"}, {"ma": "buong_trung_phai", "ten": "Buồng trứng phải", "kieu": "text"}, {"ma": "buong_trung_trai", "ten": "Buồng trứng trái", "kieu": "text"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Túi cùng Douglas không có dịch"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường hình ảnh tử cung phần phụ."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_TC_PP'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_TC_PP',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_TC_PP'),
       'Kết quả siêu âm tử cung phần phụ', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "tu_cung_tu_the", "ten": "Tử cung tư thế", "kieu": "text", "mac_dinh": "ngả trước"}, {"ma": "hinh_thai_tu_cung", "ten": "Hình thái tử cung", "kieu": "text", "mac_dinh": "Bình thường, kích thước không to."}, {"ma": "co_tu_cung", "ten": "Cơ tử cung", "kieu": "text", "mac_dinh": "tương đối đồng nhất. không thấy khối bất thường."}, {"ma": "niem_mac_tu_cung", "ten": "Niêm mạc tử cung", "kieu": "text", "goi_y": "mm"}, {"ma": "buong_trung_phai", "ten": "Buồng trứng phải", "kieu": "text"}, {"ma": "buong_trung_trai", "ten": "Buồng trứng trái", "kieu": "text"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Túi cùng Douglas không có dịch"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường hình ảnh tử cung phần phụ."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_VU' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh_tuyen_vu", "ten": "Mô tả hình ảnh tuyến vú", "block": [{"ma": "nhu_mo", "ten": "Nhu mô", "kieu": "text"}, {"ma": "tuoi_mau", "ten": "Tưới máu", "kieu": "text"}], "cot": [{"ma": "ben_trai", "ten": "Bên trái"}, {"ma": "ben_phai", "ten": "Bên phải"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường hình ảnh tuyến vú."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_VU'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_VU',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_VU'),
       'Kết quả siêu âm tuyến vú', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh_tuyen_vu", "ten": "Mô tả hình ảnh tuyến vú", "block": [{"ma": "nhu_mo", "ten": "Nhu mô", "kieu": "text"}, {"ma": "tuoi_mau", "ten": "Tưới máu", "kieu": "text"}], "cot": [{"ma": "ben_trai", "ten": "Bên trái"}, {"ma": "ben_phai", "ten": "Bên phải"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường hình ảnh tuyến vú."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_GIAP' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh_tuyen_giap", "ten": "Mô tả hình ảnh tuyến giáp", "block": [{"ma": "nhu_mo", "ten": "Nhu mô", "kieu": "text"}, {"ma": "tuoi_mau", "ten": "Tưới máu", "kieu": "text"}], "cot": [{"ma": "thuy_trai", "ten": "Thùy trái"}, {"ma": "thuy_phai", "ten": "Thùy phải"}]}, {"ma": "eo_tuyen", "ten": "Eo tuyến", "block": [{"ma": "eo_tuyen", "ten": "Eo tuyến", "kieu": "text", "mac_dinh": "Nhu mô đều, không thấy khối khu trú"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường hình ảnh tuyến giáp."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_GIAP'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_GIAP',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_GIAP'),
       'Kết quả siêu âm tuyến giáp', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh_tuyen_giap", "ten": "Mô tả hình ảnh tuyến giáp", "block": [{"ma": "nhu_mo", "ten": "Nhu mô", "kieu": "text"}, {"ma": "tuoi_mau", "ten": "Tưới máu", "kieu": "text"}], "cot": [{"ma": "thuy_trai", "ten": "Thùy trái"}, {"ma": "thuy_phai", "ten": "Thùy phải"}]}, {"ma": "eo_tuyen", "ten": "Eo tuyến", "block": [{"ma": "eo_tuyen", "ten": "Eo tuyến", "kieu": "text", "mac_dinh": "Nhu mô đều, không thấy khối khu trú"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường hình ảnh tuyến giáp."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_OBUNG' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "gan", "ten": "Gan", "kieu": "doan_van", "mac_dinh": "Kích thước bình thường, nhu mô đều, không có hình khối khu trú bất thường. Tĩnh mạch cửa không giãn, không có huyết khối. Đường mật trong và ngoài gan không giãn."}, {"ma": "tui_mat", "ten": "Túi mật", "kieu": "text", "mac_dinh": "Không giãn, thành mỏng, dịch mật trong, không có sỏi."}, {"ma": "tuy", "ten": "Tụy", "kieu": "text", "mac_dinh": "Kích thước bình thường, nhu mô đều, ống tụy không giãn."}, {"ma": "lach", "ten": "Lách", "kieu": "text", "mac_dinh": "Kích thước bình thường, nhu mô đều, không có khối."}, {"ma": "than_phai", "ten": "Thận phải", "kieu": "doan_van", "mac_dinh": "Kích thước bình thường, nhu mô đều và dày bình thường. Đài bể thận không giãn, niệu quản không giãn, không có sỏi."}, {"ma": "than_trai", "ten": "Thận trái", "kieu": "doan_van", "mac_dinh": "Kích thước bình thường, nhu mô đều và dày bình thường. Đài bể thận không giãn, niệu quản không giãn, không có sỏi."}, {"ma": "bang_quang", "ten": "Bàng quang", "kieu": "text", "mac_dinh": "Thành mỏng, không có sỏi."}, {"ma": "tieu_khung", "ten": "Tiểu khung", "kieu": "text", "mac_dinh": "Không thấy khối bất thường"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường trên hình ảnh siêu âm ổ bụng."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_OBUNG'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_OBUNG',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_OBUNG'),
       'Kết quả siêu âm ổ bụng', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "gan", "ten": "Gan", "kieu": "doan_van", "mac_dinh": "Kích thước bình thường, nhu mô đều, không có hình khối khu trú bất thường. Tĩnh mạch cửa không giãn, không có huyết khối. Đường mật trong và ngoài gan không giãn."}, {"ma": "tui_mat", "ten": "Túi mật", "kieu": "text", "mac_dinh": "Không giãn, thành mỏng, dịch mật trong, không có sỏi."}, {"ma": "tuy", "ten": "Tụy", "kieu": "text", "mac_dinh": "Kích thước bình thường, nhu mô đều, ống tụy không giãn."}, {"ma": "lach", "ten": "Lách", "kieu": "text", "mac_dinh": "Kích thước bình thường, nhu mô đều, không có khối."}, {"ma": "than_phai", "ten": "Thận phải", "kieu": "doan_van", "mac_dinh": "Kích thước bình thường, nhu mô đều và dày bình thường. Đài bể thận không giãn, niệu quản không giãn, không có sỏi."}, {"ma": "than_trai", "ten": "Thận trái", "kieu": "doan_van", "mac_dinh": "Kích thước bình thường, nhu mô đều và dày bình thường. Đài bể thận không giãn, niệu quản không giãn, không có sỏi."}, {"ma": "bang_quang", "ten": "Bàng quang", "kieu": "text", "mac_dinh": "Thành mỏng, không có sỏi."}, {"ma": "tieu_khung", "ten": "Tiểu khung", "kieu": "text", "mac_dinh": "Không thấy khối bất thường"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "Không"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại không thấy bất thường trên hình ảnh siêu âm ổ bụng."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_TINH_HOAN' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "kich_thuoc", "ten": "Kích thước", "kieu": "text"}, {"ma": "mao_tinh_hoan", "ten": "Mào tinh hoàn", "kieu": "text"}, {"ma": "nhu_mo_tinh_hoan", "ten": "Nhu mô tinh hoàn", "kieu": "text"}, {"ma": "duong_kinh_tinh_mach_thung_tinh_truoc_ng", "ten": "Đường kính tĩnh mạch thừng tinh trước nghiệm pháp Valsalva", "kieu": "text", "goi_y": "mm"}, {"ma": "sau_nghiem_phap", "ten": "… sau nghiệm pháp", "kieu": "text", "goi_y": "mm"}, {"ma": "dong_trao_nguoc", "ten": "Dòng trào ngược", "kieu": "text"}], "cot": [{"ma": "tinh_hoan_trai", "ten": "Tinh hoàn trái"}, {"ma": "tinh_hoan_phai", "ten": "Tinh hoàn phải"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "…"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hình ảnh siêu âm tinh hoàn hai bên hiện tại không thấy bất thường."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_TINH_HOAN'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_TINH_HOAN',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_TINH_HOAN'),
       'Kết quả siêu âm tinh hoàn', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "kich_thuoc", "ten": "Kích thước", "kieu": "text"}, {"ma": "mao_tinh_hoan", "ten": "Mào tinh hoàn", "kieu": "text"}, {"ma": "nhu_mo_tinh_hoan", "ten": "Nhu mô tinh hoàn", "kieu": "text"}, {"ma": "duong_kinh_tinh_mach_thung_tinh_truoc_ng", "ten": "Đường kính tĩnh mạch thừng tinh trước nghiệm pháp Valsalva", "kieu": "text", "goi_y": "mm"}, {"ma": "sau_nghiem_phap", "ten": "… sau nghiệm pháp", "kieu": "text", "goi_y": "mm"}, {"ma": "dong_trao_nguoc", "ten": "Dòng trào ngược", "kieu": "text"}], "cot": [{"ma": "tinh_hoan_trai", "ten": "Tinh hoàn trái"}, {"ma": "tinh_hoan_phai", "ten": "Tinh hoàn phải"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "…"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hình ảnh siêu âm tinh hoàn hai bên hiện tại không thấy bất thường."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_MACH_CANH' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "dong_mach_canh_chung", "ten": "Động mạch cảnh chung (CCA)", "kieu": "text"}, {"ma": "hanh_canh", "ten": "Hành cảnh", "kieu": "text"}, {"ma": "dong_mach_canh_trong", "ten": "Động mạch cảnh trong (ICA)", "kieu": "text"}, {"ma": "dong_mach_dot_song", "ten": "Động mạch đốt sống (VA)", "kieu": "text"}, {"ma": "ghi_nhan_them", "ten": "Ghi nhận thêm", "kieu": "doan_van"}], "cot": [{"ma": "ben_trai", "ten": "Bên trái"}, {"ma": "ben_phai", "ten": "Bên phải"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "…."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_MACH_CANH'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_MACH_CANH',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_MACH_CANH'),
       'Kết quả siêu âm động mạch cảnh', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "dong_mach_canh_chung", "ten": "Động mạch cảnh chung (CCA)", "kieu": "text"}, {"ma": "hanh_canh", "ten": "Hành cảnh", "kieu": "text"}, {"ma": "dong_mach_canh_trong", "ten": "Động mạch cảnh trong (ICA)", "kieu": "text"}, {"ma": "dong_mach_dot_song", "ten": "Động mạch đốt sống (VA)", "kieu": "text"}, {"ma": "ghi_nhan_them", "ten": "Ghi nhận thêm", "kieu": "doan_van"}], "cot": [{"ma": "ben_trai", "ten": "Bên trái"}, {"ma": "ben_phai", "ten": "Bên phải"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "…."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_MACH_THAN' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "doan_goc", "ten": "Đoạn gốc", "kieu": "text", "goi_y": "PSV cm/s | EDV cm/s | RI"}, {"ma": "doan_ron_than", "ten": "Đoạn rốn thận", "kieu": "text", "goi_y": "PSV cm/s | EDV cm/s | RI"}, {"ma": "doan_nhu_mo", "ten": "Đoạn nhu mô", "kieu": "text", "goi_y": "PSV cm/s | EDV cm/s | RI"}, {"ma": "mo_ta_thanh_mach", "ten": "Mô tả thành mạch", "kieu": "doan_van"}], "cot": [{"ma": "dong_mach_than_trai", "ten": "Động mạch thận trái"}, {"ma": "dong_mach_than_phai", "ten": "Động mạch thận phải"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "…"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại hình ảnh phổ sóng và tốc độ dòng chảy hệ thống động mạch thận hai bên trong giới hạn bình thường."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_MACH_THAN'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_MACH_THAN',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_MACH_THAN'),
       'Kết quả siêu âm động mạch thận', cu.nhom, $khung$[{"ma": "mo_ta_hinh_anh", "ten": "Mô tả hình ảnh", "block": [{"ma": "doan_goc", "ten": "Đoạn gốc", "kieu": "text", "goi_y": "PSV cm/s | EDV cm/s | RI"}, {"ma": "doan_ron_than", "ten": "Đoạn rốn thận", "kieu": "text", "goi_y": "PSV cm/s | EDV cm/s | RI"}, {"ma": "doan_nhu_mo", "ten": "Đoạn nhu mô", "kieu": "text", "goi_y": "PSV cm/s | EDV cm/s | RI"}, {"ma": "mo_ta_thanh_mach", "ten": "Mô tả thành mạch", "kieu": "doan_van"}], "cot": [{"ma": "dong_mach_than_trai", "ten": "Động mạch thận trái"}, {"ma": "dong_mach_than_phai", "ten": "Động mạch thận phải"}]}, {"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "block": [{"ma": "hinh_anh_khac", "ten": "Hình ảnh khác", "kieu": "doan_van", "mac_dinh": "…"}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van", "mac_dinh": "Hiện tại hình ảnh phổ sóng và tốc độ dòng chảy hệ thống động mạch thận hai bên trong giới hạn bình thường."}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SA_DOPPLER_AM_VAT' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "sieu_am_am_vat", "ten": "Siêu âm âm vật", "block": [{"ma": "cau_truc", "ten": "Cấu trúc", "kieu": "doan_van", "mac_dinh": "Không thấy bất thường cấu trúc quy đầu âm vật, thân âm vật, hành tiền đình và thể hang âm vật"}, {"ma": "kich_thuoc_vat_hang_hai_ben", "ten": "Kích thước vật hang hai bên — Bên phải / Bên trái", "kieu": "text", "goi_y": "__x__ mm"}, {"ma": "kich_thuoc_vat_xop_hai_ben", "ten": "Kích thước vật xốp hai bên — Bên phải / Bên trái", "kieu": "text", "goi_y": "__x__ mm"}, {"ma": "kich_thuoc_than_am_vat", "ten": "Kích thước thân âm vật", "kieu": "text", "goi_y": "__x__ mm"}]}, {"ma": "dm_vat_hang", "ten": "ĐM vật hang", "block": [{"ma": "vmax", "ten": "Vmax", "kieu": "text", "goi_y": "cm/s"}, {"ma": "ri", "ten": "RI", "kieu": "text"}, {"ma": "pho_doppler", "ten": "Phổ Doppler", "kieu": "text"}], "cot": [{"ma": "ben_phai", "ten": "Bên phải"}, {"ma": "ben_trai", "ten": "Bên trái"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SA_DOPPLER_AM_VAT'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SA_DOPPLER_AM_VAT',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SA_DOPPLER_AM_VAT'),
       'Siêu âm Doppler âm vật', cu.nhom, $khung$[{"ma": "sieu_am_am_vat", "ten": "Siêu âm âm vật", "block": [{"ma": "cau_truc", "ten": "Cấu trúc", "kieu": "doan_van", "mac_dinh": "Không thấy bất thường cấu trúc quy đầu âm vật, thân âm vật, hành tiền đình và thể hang âm vật"}, {"ma": "kich_thuoc_vat_hang_hai_ben", "ten": "Kích thước vật hang hai bên — Bên phải / Bên trái", "kieu": "text", "goi_y": "__x__ mm"}, {"ma": "kich_thuoc_vat_xop_hai_ben", "ten": "Kích thước vật xốp hai bên — Bên phải / Bên trái", "kieu": "text", "goi_y": "__x__ mm"}, {"ma": "kich_thuoc_than_am_vat", "ten": "Kích thước thân âm vật", "kieu": "text", "goi_y": "__x__ mm"}]}, {"ma": "dm_vat_hang", "ten": "ĐM vật hang", "block": [{"ma": "vmax", "ten": "Vmax", "kieu": "text", "goi_y": "cm/s"}, {"ma": "ri", "ten": "RI", "kieu": "text"}, {"ma": "pho_doppler", "ten": "Phổ Doppler", "kieu": "text"}], "cot": [{"ma": "ben_phai", "ten": "Bên phải"}, {"ma": "ben_trai", "ten": "Bên trái"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SOI_AM_HO' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "o", "ten": "(không có tiêu đề mục)", "block": [{"ma": "quy_dau_am_vat", "ten": "Quy đầu âm vật", "kieu": "text"}, {"ma": "tien_dinh_am_ho", "ten": "Tiền đình âm hộ", "kieu": "text"}, {"ma": "test_ran", "ten": "Test rặn", "kieu": "text"}, {"ma": "co_luc_am_dao_theo_oxford_cai_tien", "ten": "Cơ lực âm đạo theo Oxford cải tiến", "kieu": "text", "goi_y": "Độ"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SOI_AM_HO'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SOI_AM_HO',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SOI_AM_HO'),
       'Phiếu soi âm hộ', cu.nhom, $khung$[{"ma": "o", "ten": "(không có tiêu đề mục)", "block": [{"ma": "quy_dau_am_vat", "ten": "Quy đầu âm vật", "kieu": "text"}, {"ma": "tien_dinh_am_ho", "ten": "Tiền đình âm hộ", "kieu": "text"}, {"ma": "test_ran", "ten": "Test rặn", "kieu": "text"}, {"ma": "co_luc_am_dao_theo_oxford_cai_tien", "ten": "Cơ lực âm đạo theo Oxford cải tiến", "kieu": "text", "goi_y": "Độ"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_XN_HPV' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "ket_qua", "ten": "Kết quả", "block": [{"ma": "hpv_type_16", "ten": "HPV type 16", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "hpv_type_18", "ten": "HPV type 18", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "18_type_hpv_nguy_co_cao_khac", "ten": "18 type HPV nguy cơ cao khác", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "hpv_type_6", "ten": "HPV type 6", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "hpv_type_11", "ten": "HPV type 11", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "18_type_hpv_nguy_co_thap_khac", "ten": "18 type HPV nguy cơ thấp khác", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_XN_HPV'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_XN_HPV',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_XN_HPV'),
       'KẾT QUẢ XÉT NGHIỆM HPV GENOTYPE (TrueMedicine — đối tác)', cu.nhom, $khung$[{"ma": "ket_qua", "ten": "Kết quả", "block": [{"ma": "hpv_type_16", "ten": "HPV type 16", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "hpv_type_18", "ten": "HPV type 18", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "18_type_hpv_nguy_co_cao_khac", "ten": "18 type HPV nguy cơ cao khác", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "hpv_type_6", "ten": "HPV type 6", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "hpv_type_11", "ten": "HPV type 11", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "18_type_hpv_nguy_co_thap_khac", "ten": "18 type HPV nguy cơ thấp khác", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}]}, {"ma": "ket_luan", "ten": "Kết luận", "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_XN_PCR_STDS' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "ket_qua_13_tac_nhan", "ten": "Kết quả (13 tác nhân — tham chiếu: Âm tính)", "block": [{"ma": "neisseria_gonorrhoeae", "ten": "Neisseria gonorrhoeae (Lậu cầu)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "chlamydia_trachomatis", "ten": "Chlamydia trachomatis (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "mycoplasma_hominis", "ten": "Mycoplasma hominis (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "mycoplasma_genitalium", "ten": "Mycoplasma genitalium (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "ureaplasma_urealyticum", "ten": "Ureaplasma urealyticum (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "ureaplasma_parvum", "ten": "Ureaplasma parvum (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "gardnerella_vaginalis", "ten": "Gardnerella vaginalis (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "treponema_pallidum", "ten": "Treponema pallidum (Giang mai)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "herpes_simplex_virus_1", "ten": "Herpes simplex virus 1 (Viêm loét sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "herpes_simplex_virus_2", "ten": "Herpes simplex virus 2 (Viêm loét sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "trichomonas_vaginalis", "ten": "Trichomonas vaginalis (Trùng roi)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "candida_albicans", "ten": "Candida albicans (Nấm)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "haemophilus_ducreyi", "ten": "Haemophilus ducreyi", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_XN_PCR_STDS'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_XN_PCR_STDS',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_XN_PCR_STDS'),
       'PHIẾU KẾT QUẢ XÉT NGHIỆM — PCR chẩn đoán 13 tác nhân gây bệnh đường tình dục (TrueMedicine — đối tác)', cu.nhom, $khung$[{"ma": "ket_qua_13_tac_nhan", "ten": "Kết quả (13 tác nhân — tham chiếu: Âm tính)", "block": [{"ma": "neisseria_gonorrhoeae", "ten": "Neisseria gonorrhoeae (Lậu cầu)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "chlamydia_trachomatis", "ten": "Chlamydia trachomatis (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "mycoplasma_hominis", "ten": "Mycoplasma hominis (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "mycoplasma_genitalium", "ten": "Mycoplasma genitalium (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "ureaplasma_urealyticum", "ten": "Ureaplasma urealyticum (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "ureaplasma_parvum", "ten": "Ureaplasma parvum (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "gardnerella_vaginalis", "ten": "Gardnerella vaginalis (Viêm nhiễm sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "treponema_pallidum", "ten": "Treponema pallidum (Giang mai)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "herpes_simplex_virus_1", "ten": "Herpes simplex virus 1 (Viêm loét sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "herpes_simplex_virus_2", "ten": "Herpes simplex virus 2 (Viêm loét sinh dục)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "trichomonas_vaginalis", "ten": "Trichomonas vaginalis (Trùng roi)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "candida_albicans", "ten": "Candida albicans (Nấm)", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}, {"ma": "haemophilus_ducreyi", "ten": "Haemophilus ducreyi", "kieu": "chon", "chon": ["Âm tính", "Dương tính"]}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;

-- Gắn mẫu ↔ dịch vụ theo mã phòng khám. Dịch vụ đã có mẫu gắn tay thì vẫn thêm
-- (nhiều mẫu cho một dịch vụ là chuyện thường: SA TC-BT / TC-PP, combo siêu âm).
-- HÀM để seed.sql gọi lại: trên DB dựng mới migration chạy TRƯỚC khi dịch vụ có mã
-- phòng khám (chuan_hoa_danh_muc_dich_vu_kiotviet chạy trong seed).
CREATE OR REPLACE FUNCTION public.gan_mau_ket_qua_theo_kiotviet()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE n integer;
BEGIN
  INSERT INTO public.dich_vu_mau_ket_qua (clinic_id, service_code, mau)
  SELECT p.clinic_id, p.service_code, g.mau
    FROM (VALUES
    ('SA_THAI_SOM', 'SP000008'),
  ('SA_THAI_SOM', 'SP000132'),
  ('SA_THAI_QUY_1', 'SP000098'),
  ('SA_THAI_QUY_1', 'SP000008'),
  ('SA_THAI_QUY_1', 'SP000078'),
  ('SA_THAI_QUY_23', 'SP000009'),
  ('SA_THAI_QUY_23', 'SP000078'),
  ('SA_THAI_QUY_23', 'SP000010'),
  ('SA_SONG_THAI_QUY_1', 'SP000132'),
  ('SA_SONG_THAI_QUY_23', 'SP000084'),
  ('SA_SONG_THAI_QUY_23', 'SP000085'),
  ('SA_TC_BT', 'SP000013'),
  ('SA_TC_BT', 'SP000014'),
  ('SA_TC_BT', 'SP000080'),
  ('SA_TC_PP', 'SP000013'),
  ('SA_TC_PP', 'SP000014'),
  ('SA_TC_PP', 'SP000080'),
  ('SA_VU', 'SP000015'),
  ('SA_VU', 'SP000080'),
  ('SA_GIAP', 'SP000017'),
  ('SA_GIAP', 'SP000080'),
  ('SA_OBUNG', 'SP000016'),
  ('SA_OBUNG', 'SP000080'),
  ('SA_TINH_HOAN', 'SP000019'),
  ('SA_MACH_CANH', 'SP000018'),
  ('SA_MACH_CANH', 'SP000080'),
  ('SA_MACH_THAN', 'SP000099'),
  ('SA_DOPPLER_AM_VAT', 'SP000125'),
  ('SOI_AM_HO', 'SP000163'),
  ('XN_HPV', 'SP000028'),
  ('XN_HPV', 'SP000170'),
  ('XN_PCR_STDS', 'SP000171')
    ) AS g(mau, ma_kv)
    JOIN public.service_price p
      ON p.ma_kiotviet = g.ma_kv AND p."group" = 'dich_vu'
    JOIN public.ket_qua_mau k ON k.clinic_id = p.clinic_id AND k.ma = g.mau
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$fn$;

SELECT public.gan_mau_ket_qua_theo_kiotviet();
