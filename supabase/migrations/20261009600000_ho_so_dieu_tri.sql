-- HỒ SƠ ĐIỀU TRỊ — khung trung tính cho lượt Điều trị (Tuyền chốt 09/10/2026).
--
-- Lượt Điều trị (6 loại DT_*) mở Bàn khám phải hiện đủ bốn khối mà KHÔNG mở
-- phiếu của bảy loại khám (bản nháp đầu dùng khung THU_THUAT → bản in ghi "Phiếu
-- thủ thuật", `phieu_kham_luot.form_id` ghi THU_THUAT trên lượt Điều trị: sai với
-- người đọc và với mọi chỗ gom theo phiếu). Khung này chỉ có hành chính, C, D, E,
-- F, G — không A/B (khối 1 là phần điều trị). Phiếu chỉ sinh dòng khi bác sĩ ghi.
--
-- Cùng dữ liệu với src/clinicai/phieu_kham/dinh_nghia/HO_SO_DIEU_TRI.json (test
-- `test_ho_so_dieu_tri_migration_trung_json`). v1 PUBLISHED, `xuat_ban_boi` trống
-- như bảy phiếu (20260924000008). Đã có bản nào thì không đè. Chạy lại được.

INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT c.id, 'HO_SO_DIEU_TRI', 1, 'Hồ sơ điều trị', 'PHIEU_KHAM', $khung$[{"ma": "HANH_CHINH", "ten": "Hành chính & sinh hiệu", "lien_ket": {"loai": "mang_sang", "truong": ["patient.name", "patient.birth_year", "patient.code", "encounter.date", "vitals.blood_pressure", "vitals.pulse", "vitals.weight", "vitals.height", "vitals.temperature", "vitals.spo2", "vitals.bmi", "vitals.respiratory_rate", "vitals.pain_score"]}, "block": []}, {"ma": "C", "ten": "C. Chỉ định cận lâm sàng", "block": [], "lien_ket": {"loai": "chi_dinh_cls", "rang_buoc": "service_order_id"}}, {"ma": "D", "ten": "D. Chẩn đoán và xử lý", "block": [{"ma": "dt_conclusion", "ten": "Đánh giá / kết luận", "kieu": "doan_van"}, {"ma": "dt_plan", "ten": "Xử trí / kế hoạch tiếp theo", "kieu": "doan_van"}]}, {"ma": "E", "ten": "E. Chỉ định điều trị", "block": [{"ma": "dt_treatment_other", "ten": "Điều trị khác / thuốc ngoài danh mục", "kieu": "doan_van", "goi_y": "Nhập tự do nếu chưa có trong danh mục", "khoa_tu": "name"}, {"ma": "dt_treatment_note", "ten": "Lời dặn điều trị chung", "kieu": "doan_van", "goi_y": "Lời dặn chung cho bệnh nhân", "khoa_tu": "name"}], "lien_ket": {"loai": "don_thuoc", "rang_buoc": "prescription.drug_catalog_id"}}, {"ma": "F", "ten": "F. Chỉ định thủ thuật", "block": [], "lien_ket": {"loai": "chi_dinh_thu_thuat", "rang_buoc": "service_order_id"}}, {"ma": "G", "ten": "G. Theo dõi và tái khám", "block": [{"ma": "dt_follow_date", "ten": "Ngày tái khám / buổi kế tiếp", "kieu": "ngay"}, {"ma": "dt_follow", "ten": "Theo dõi sau điều trị", "kieu": "doan_van"}, {"ma": "dt_advice", "ten": "Lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM public.clinic c
 WHERE NOT EXISTS (SELECT 1 FROM public.form_definition d
                    WHERE d.clinic_id = c.id AND d.form_id = 'HO_SO_DIEU_TRI');
