-- "Hỏi bệnh ban đầu": bác sĩ HAY điều dưỡng đều đứng được — theo đúng file Excel.
--
-- Migration 000008 xếp vị trí này vào nhóm BÁC SĨ vì bình thường BS Dương đứng.
-- Nhưng file Excel xếp lịch của PK Kim Ngưu, ngày 20/08, có điều dưỡng Thủy Tiên
-- đứng ô GỘP "Hỏi bệnh ban đầu + Thư ký y khoa". Ma trận vai↔vị trí từ chối ô ấy
-- lúc nạp lịch — hai lần, cho hai tuần tháng 9 dùng mẫu tuần đó.
--
-- Tuyền chốt 16/09/2026: "cứ theo excel đi". File là nguồn sự thật về ai đứng
-- đâu; luật phải khớp file, không phải file khớp luật.
--
-- Nhóm mới `CHUNG` thay vì đổi sang DIEU_DUONG: đổi sang điều dưỡng thì lại chặn
-- chính BS Dương, người đứng vị trí này gần như mọi buổi.

BEGIN;

ALTER TABLE public.vi_tri_lam_viec
    DROP CONSTRAINT IF EXISTS vi_tri_lam_viec_nhom_check;
ALTER TABLE public.vi_tri_lam_viec
    ADD CONSTRAINT vi_tri_lam_viec_nhom_check
    CHECK (nhom_nghe = ANY (ARRAY['BAC_SI', 'DIEU_DUONG', 'DOI_TAC', 'CHUNG']));

UPDATE public.vi_tri_lam_viec
   SET nhom_nghe = 'CHUNG'
 WHERE code = 'T1_HOIBENH' AND nhom_nghe <> 'CHUNG';

INSERT INTO
    public.vai_duoc_vao_tram (clinic_id, vai, tram_ma, is_active)
SELECT v.clinic_id, r.vai, v.code, TRUE
  FROM public.vi_tri_lam_viec v
 CROSS JOIN (VALUES
    ('DOCTOR'), ('ULTRASOUND_DOCTOR'), ('NURSE_ULTRASOUND'), ('RECEPTION'),
    ('TKYK'), ('CSKH'), ('TRUONG_CA'), ('CASHIER'), ('CASHIER_THUOC'),
    ('CASHIER_DV'), ('PHARMACIST'), ('MANAGEMENT')
 ) AS r(vai)
 WHERE v.nhom_nghe = 'CHUNG' AND v.is_active
 ON CONFLICT (clinic_id, tram_ma, vai) DO UPDATE SET is_active = TRUE;

COMMIT;
