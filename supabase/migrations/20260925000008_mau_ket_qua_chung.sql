-- MẪU KẾT QUẢ CHUNG — nhập tự do (Tuyền 24/09/2026: "ở siêu âm, thủ thuật… nếu
-- form nào mà tài liệu tôi đưa chưa có thì cũng phải có ô để họ nhập").
--
-- 18 mẫu kết quả hiện có đều là siêu âm / xét nghiệm. Dịch vụ không có mẫu
-- riêng (Laser, Biofeedback, ghế ĐTT, nhiều thủ thuật…) mở phiếu ra chỉ có mẫu
-- sai loại để chọn. Mẫu CHUNG: ba ô đoạn văn — mô tả/kết quả, kết luận, đề nghị.
-- `mau_cho_dich_vu` chọn sẵn nó khi dịch vụ không có mẫu gắn / mẫu gợi ý.
--
-- Chạy lại được.

INSERT INTO public.ket_qua_mau (clinic_id, ma, nhom, ten)
SELECT c.id, 'CHUNG', 'Chung', 'Kết quả chung (nhập tự do)'
  FROM public.clinic c
ON CONFLICT (clinic_id, ma) DO NOTHING;

INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT c.id, 'KQ_CHUNG', 1, 'Kết quả chung (nhập tự do)', 'Chung',
       $khung$[
         {"ma": "ket_qua", "ten": "Mô tả / kết quả",
          "block": [{"ma": "noi_dung", "ten": "Mô tả / kết quả", "kieu": "doan_van"}]},
         {"ma": "ket_luan", "ten": "Kết luận",
          "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van"}]},
         {"ma": "de_nghi", "ten": "Đề nghị",
          "block": [{"ma": "de_nghi", "ten": "Đề nghị", "kieu": "doan_van"}]}
       ]$khung$::jsonb,
       'PUBLISHED', NULL, now()
  FROM public.clinic c
 WHERE NOT EXISTS (SELECT 1 FROM public.form_definition d
                    WHERE d.clinic_id = c.id AND d.form_id = 'KQ_CHUNG');
