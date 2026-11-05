-- XÉT NGHIỆM ĐỐI TÁC — khoá ngoại `clinic_id → clinic` còn thiếu (CI máy 05/11:
-- supabase/tests/multi_tenant_foundation.sql đòi MỌI cột clinic_id có FK tới clinic).
--
-- `doi_tac_dich_vu` và `mau_xet_nghiem` chỉ có FK GHÉP (doi_tac_id, clinic_id) →
-- doi_tac — đủ chống lệch phòng khám với đối tác, nhưng luật nền đa phòng khám đòi
-- thêm FK trần tới clinic (một luật cho mọi bảng). Migration mới, không sửa migration
-- cũ (DB thử local đã áp bản cũ). Chạy lại được.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'doi_tac_dich_vu_clinic_fk') THEN
        ALTER TABLE public.doi_tac_dich_vu
            ADD CONSTRAINT doi_tac_dich_vu_clinic_fk FOREIGN KEY (clinic_id)
            REFERENCES public.clinic (id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'mau_xet_nghiem_clinic_fk') THEN
        ALTER TABLE public.mau_xet_nghiem
            ADD CONSTRAINT mau_xet_nghiem_clinic_fk FOREIGN KEY (clinic_id)
            REFERENCES public.clinic (id) ON DELETE RESTRICT;
    END IF;
END $$;
