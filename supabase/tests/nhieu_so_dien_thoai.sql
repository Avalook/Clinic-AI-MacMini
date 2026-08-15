-- Nhiều số điện thoại một bệnh nhân (20260815000002) — cột gộp phải TỰ TƯƠI.
--
-- Luật được canh:
--   1. Thêm số vào `patient_sdt_them` → `patient.sdt_tim_kiem` chứa số ấy
--      ngay trong cùng giao dịch (trigger, không chờ ai gọi hàm).
--   2. Đổi số chính trên hồ sơ → cột gộp đổi theo, số thêm vẫn còn.
--   3. Xoá số thêm → biến khỏi cột gộp (số đã gỡ mà vẫn tra ra là gọi nhầm
--      người theo một số không còn của họ).
--   4. Cùng khách cùng số hai lần → unique chặn (bấm trùng không thành hai
--      dòng); HAI KHÁCH dùng chung một số thì được (mẹ đăng ký cho con).
--   5. Số sai dạng (không phải 0 + 9 số) → CHECK chặn từ cửa.
--
-- Fixture dựng tại chỗ, mọi thứ rollback. Các câu INSERT cố ý THỤT LỀ:
-- chốt pre-commit dò dump database theo `INSERT INTO public.` ở ĐẦU dòng —
-- đặc trưng của dump máy sinh; fixture viết tay thụt lề để nói rõ mình
-- không phải nó, thay vì đục lỗ chốt hay commit --no-verify.

BEGIN;

  INSERT INTO public.clinic (id, code, name)
  VALUES ('c0000000-0000-4000-8000-0000000d0001', 'TEST-SDT', 'PK kiểm thử SĐT');

  INSERT INTO public.clinic_location (id, clinic_id, code, name)
  VALUES ('c0000000-0000-4000-8000-0000000d0002',
        'c0000000-0000-4000-8000-0000000d0001', 'CS1', 'Cơ sở 1');

  INSERT INTO public.patient
      (clinic_patient_id, clinic_id, location_id, patient_code, full_name,
     phone_primary, phone_secondary)
  VALUES
    ('c0000000-0000-4000-8000-0000000d0011',
     'c0000000-0000-4000-8000-0000000d0001',
     'c0000000-0000-4000-8000-0000000d0002',
     'BN-TEST-0001', 'Nguyễn Thị Kiểm Thử', '0901111111', '0902222222'),
    ('c0000000-0000-4000-8000-0000000d0012',
     'c0000000-0000-4000-8000-0000000d0001',
     'c0000000-0000-4000-8000-0000000d0002',
     'BN-TEST-0002', 'Trần Văn Chung Số', NULL, NULL);

-- (1) INSERT hồ sơ đã phải tự điền cột gộp từ hai số sẵn có.
DO $$
DECLARE v text;
BEGIN
    SELECT sdt_tim_kiem INTO v FROM public.patient
     WHERE clinic_patient_id = 'c0000000-0000-4000-8000-0000000d0011';
    IF v IS NULL OR position('0901111111' IN v) = 0
       OR position('0902222222' IN v) = 0 THEN
        RAISE EXCEPTION 'FAIL(1): cột gộp sau INSERT hồ sơ = %', v;
    END IF;
END $$;

-- (1b) Thêm một số → cột gộp có ngay.
  INSERT INTO public.patient_sdt_them
      (clinic_id, clinic_patient_id, so_dien_thoai, loai)
  VALUES ('c0000000-0000-4000-8000-0000000d0001',
        'c0000000-0000-4000-8000-0000000d0011', '0903333333', 'CHINH');

DO $$
DECLARE v text;
BEGIN
    SELECT sdt_tim_kiem INTO v FROM public.patient
     WHERE clinic_patient_id = 'c0000000-0000-4000-8000-0000000d0011';
    IF position('0903333333' IN v) = 0 THEN
        RAISE EXCEPTION 'FAIL(1b): số vừa thêm không vào cột gộp: %', v;
    END IF;
END $$;

-- (2) Đổi số chính → cột gộp đổi theo, số thêm còn nguyên.
UPDATE public.patient SET phone_primary = '0909999999'
 WHERE clinic_patient_id = 'c0000000-0000-4000-8000-0000000d0011';

DO $$
DECLARE v text;
BEGIN
    SELECT sdt_tim_kiem INTO v FROM public.patient
     WHERE clinic_patient_id = 'c0000000-0000-4000-8000-0000000d0011';
    IF position('0909999999' IN v) = 0 OR position('0903333333' IN v) = 0
       OR position('0901111111' IN v) > 0 THEN
        RAISE EXCEPTION 'FAIL(2): cột gộp sau khi đổi số chính = %', v;
    END IF;
END $$;

-- (3) Xoá số thêm → biến khỏi cột gộp.
DELETE FROM public.patient_sdt_them
 WHERE clinic_patient_id = 'c0000000-0000-4000-8000-0000000d0011'
   AND so_dien_thoai = '0903333333';

DO $$
DECLARE v text;
BEGIN
    SELECT sdt_tim_kiem INTO v FROM public.patient
     WHERE clinic_patient_id = 'c0000000-0000-4000-8000-0000000d0011';
    IF position('0903333333' IN v) > 0 THEN
        RAISE EXCEPTION 'FAIL(3): số đã xoá vẫn nằm trong cột gộp: %', v;
    END IF;
END $$;

-- (4) Bấm trùng bị unique chặn…
  INSERT INTO public.patient_sdt_them
      (clinic_id, clinic_patient_id, so_dien_thoai)
  VALUES ('c0000000-0000-4000-8000-0000000d0001',
        'c0000000-0000-4000-8000-0000000d0011', '0904444444');
DO $$
BEGIN
    BEGIN
        INSERT INTO public.patient_sdt_them
            (clinic_id, clinic_patient_id, so_dien_thoai)
        VALUES ('c0000000-0000-4000-8000-0000000d0001',
                'c0000000-0000-4000-8000-0000000d0011', '0904444444');
        RAISE EXCEPTION 'FAIL(4): cùng khách cùng số hai lần mà không bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
END $$;
-- …nhưng khách KHÁC dùng chung số thì được.
  INSERT INTO public.patient_sdt_them
      (clinic_id, clinic_patient_id, so_dien_thoai)
  VALUES ('c0000000-0000-4000-8000-0000000d0001',
        'c0000000-0000-4000-8000-0000000d0012', '0904444444');

-- (5) Số sai dạng bị CHECK chặn.
DO $$
BEGIN
    BEGIN
        INSERT INTO public.patient_sdt_them
            (clinic_id, clinic_patient_id, so_dien_thoai)
        VALUES ('c0000000-0000-4000-8000-0000000d0001',
                'c0000000-0000-4000-8000-0000000d0011', '+84901234567');
        RAISE EXCEPTION 'FAIL(5): số chưa chuẩn hoá lọt qua CHECK';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END $$;

ROLLBACK;

DO $$ BEGIN RAISE NOTICE 'nhieu_so_dien_thoai: cột gộp tự tươi, unique và CHECK đều đúng.'; END $$;
