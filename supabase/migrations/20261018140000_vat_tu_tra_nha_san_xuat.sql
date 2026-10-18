-- Trả vật tư cho nhà sản xuất là xuất kho riêng, cần lưu đối tác và lý do.
ALTER TABLE public.vat_tu_phieu
    ADD COLUMN IF NOT EXISTS nha_cung_cap text;

ALTER TABLE public.vat_tu_phieu
    DROP CONSTRAINT IF EXISTS vat_tu_phieu_loai_check;

ALTER TABLE public.vat_tu_phieu
    ADD CONSTRAINT vat_tu_phieu_loai_check
    CHECK (loai IN (
        'NHAP', 'XUAT_PHONG', 'TRA_KHO', 'CHUYEN_PHONG', 'KIEM',
        'DIEU_CHINH', 'HUY', 'TRA_NCC', 'HOAN'
    ));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname='vat_tu_phieu_tra_ncc_check'
          AND conrelid='public.vat_tu_phieu'::regclass
    ) THEN
        ALTER TABLE public.vat_tu_phieu
            ADD CONSTRAINT vat_tu_phieu_tra_ncc_check
            CHECK (
                (loai = 'TRA_NCC') = (nha_cung_cap IS NOT NULL)
                AND (loai <> 'TRA_NCC'
                     OR length(btrim(nha_cung_cap)) BETWEEN 2 AND 200)
                AND (loai <> 'TRA_NCC'
                     OR length(btrim(coalesce(ghi_chu, ''))) >= 3)
            );
    END IF;
END $$;

CREATE OR REPLACE FUNCTION public.vat_tu_txn_cong_ton() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE t record; p record; x record;
BEGIN
    SELECT * INTO p FROM public.vat_tu_phieu WHERE id=NEW.phieu_id AND clinic_id=NEW.clinic_id;
    SELECT * INTO t FROM public.vat_tu_ton WHERE id=NEW.ton_id AND clinic_id=NEW.clinic_id FOR UPDATE;
    IF t.id IS NULL OR p.id IS NULL OR t.location_id<>p.location_id OR t.vat_tu_id<>NEW.vat_tu_id THEN
        RAISE EXCEPTION 'Dòng sổ vật tư sai phiếu/nơi chứa/mặt hàng' USING ERRCODE='check_violation';
    END IF;
    IF p.giao_dich<>pg_current_xact_id() THEN
        RAISE EXCEPTION 'Phiếu đã lưu — không thêm dòng, lập phiếu mới' USING ERRCODE='check_violation';
    END IF;
    IF p.loai='KIEM' AND (NEW.so_luong<>0 OR NEW.thuc_te IS NULL) THEN
        RAISE EXCEPTION 'Kiểm đếm chưa điều chỉnh tồn' USING ERRCODE='check_violation';
    END IF;
    IF (p.loai='HOAN') <> (NEW.dao_txn_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Dòng đảo phải trỏ dòng gốc' USING ERRCODE='check_violation';
    END IF;
    IF NEW.dao_txn_id IS NOT NULL THEN
        SELECT * INTO x FROM public.vat_tu_txn WHERE id=NEW.dao_txn_id AND clinic_id=NEW.clinic_id;
        IF x.id IS NULL OR x.phieu_id<>p.dao_phieu_id OR x.ton_id<>NEW.ton_id
           OR x.so_luong<>-NEW.so_luong OR x.gia_nhap<>NEW.gia_nhap THEN
            RAISE EXCEPTION 'Phiếu đảo phải đối ứng đúng dòng gốc' USING ERRCODE='check_violation';
        END IF;
    END IF;
    NEW.ton_may := t.so_luong;
    IF (p.loai='NHAP' AND NEW.so_luong<=0)
       OR (p.loai IN ('HUY','TRA_NCC') AND NEW.so_luong>=0)
       OR (p.loai='DIEU_CHINH' AND (NEW.thuc_te IS NULL OR NEW.so_luong<>NEW.thuc_te-NEW.ton_may)) THEN
        RAISE EXCEPTION 'Dòng sổ không đúng loại phiếu/đếm thực tế' USING ERRCODE='check_violation';
    END IF;
    UPDATE public.vat_tu_ton SET so_luong=so_luong+NEW.so_luong
      WHERE id=NEW.ton_id AND clinic_id=NEW.clinic_id;
    RETURN NEW;
END $$;
