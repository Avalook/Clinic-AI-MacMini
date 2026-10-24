-- Kiểm kê vật tư theo đầu/cuối ca tại từng phòng.
CREATE TABLE IF NOT EXISTS public.vat_tu_kiem_ke_ca (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id uuid NOT NULL REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    room_id uuid NOT NULL REFERENCES public.clinic_room(id) ON DELETE RESTRICT,
    ngay date NOT NULL,
    ca text NOT NULL CHECK (ca IN ('SANG', 'CHIEU', 'TOI')),
    loai text NOT NULL CHECK (loai IN ('DAU', 'CUOI', 'DOT_XUAT')),
    trang_thai text NOT NULL DEFAULT 'NHAP' CHECK (trang_thai IN ('NHAP', 'CHOT')),
    tao_boi uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    tao_luc timestamptz NOT NULL DEFAULT now(),
    chot_boi uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    chot_luc timestamptz,
    mot_phan boolean NOT NULL DEFAULT false,
    CONSTRAINT vat_tu_kiem_ke_ca_id_clinic UNIQUE (id, clinic_id),
    CONSTRAINT vat_tu_kiem_ke_ca_trang_thai CHECK (
        (trang_thai = 'NHAP' AND chot_boi IS NULL AND chot_luc IS NULL)
        OR (trang_thai = 'CHOT' AND chot_boi IS NOT NULL AND chot_luc IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_vat_tu_kiem_ke_ca_dau_cuoi
    ON public.vat_tu_kiem_ke_ca (clinic_id, location_id, room_id, ngay, ca, loai)
    WHERE loai IN ('DAU', 'CUOI');
CREATE INDEX IF NOT EXISTS vat_tu_kiem_ke_ca_theo_ngay
    ON public.vat_tu_kiem_ke_ca (clinic_id, location_id, room_id, ngay DESC, ca);

CREATE TABLE IF NOT EXISTS public.vat_tu_kiem_ke_ca_dong (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    kiem_ke_ca_id uuid NOT NULL,
    ton_id uuid NOT NULL REFERENCES public.vat_tu_ton(id) ON DELETE RESTRICT,
    vat_tu_id uuid NOT NULL REFERENCES public.service_price(id) ON DELETE RESTRICT,
    dem numeric(18,3) CHECK (
        dem >= 0 AND dem <= 1000000 AND dem NOT IN ('NaN'::numeric, 'Infinity'::numeric)
    ),
    ton_may numeric(18,3) CHECK (
        ton_may NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
    ),
    lech numeric(18,3) CHECK (
        lech NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
    ),
    CONSTRAINT vat_tu_kiem_ke_ca_dong_phieu_fkey
        FOREIGN KEY (kiem_ke_ca_id, clinic_id)
        REFERENCES public.vat_tu_kiem_ke_ca(id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT vat_tu_kiem_ke_ca_dong_phieu_ton UNIQUE (kiem_ke_ca_id, ton_id),
    CONSTRAINT vat_tu_kiem_ke_ca_dong_chot_day_du CHECK (
        (ton_may IS NULL AND lech IS NULL)
        OR (dem IS NOT NULL AND ton_may IS NOT NULL AND lech = dem - ton_may)
    )
);
CREATE INDEX IF NOT EXISTS vat_tu_kiem_ke_ca_dong_phieu
    ON public.vat_tu_kiem_ke_ca_dong (clinic_id, kiem_ke_ca_id);

CREATE OR REPLACE FUNCTION public.vat_tu_kiem_ke_ca_phieu_gac()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.trang_thai <> 'NHAP' OR NOT EXISTS (
            SELECT 1 FROM public.clinic_room r
             WHERE r.id = NEW.room_id AND r.clinic_id = NEW.clinic_id
               AND r.location_id = NEW.location_id
        ) OR NOT EXISTS (
            SELECT 1 FROM public.clinic_membership m
             WHERE m.clinic_id = NEW.clinic_id AND m.staff_id = NEW.tao_boi AND m.is_active
        ) THEN
            RAISE EXCEPTION 'Phiếu kiểm kê vật tư sai phòng/cơ sở/người lập'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.trang_thai = 'CHOT' THEN
        RAISE EXCEPTION 'Phiếu kiểm kê đã chốt — không thể sửa'
            USING ERRCODE = 'check_violation';
    END IF;
    IF (NEW.id, NEW.clinic_id, NEW.location_id, NEW.room_id, NEW.ngay, NEW.ca,
        NEW.loai, NEW.tao_boi, NEW.tao_luc)
       IS DISTINCT FROM
       (OLD.id, OLD.clinic_id, OLD.location_id, OLD.room_id, OLD.ngay, OLD.ca,
        OLD.loai, OLD.tao_boi, OLD.tao_luc) THEN
        RAISE EXCEPTION 'Không sửa phạm vi phiếu kiểm kê vật tư'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.trang_thai = 'CHOT' AND NOT EXISTS (
        SELECT 1 FROM public.vat_tu_kiem_ke_ca_dong d
         WHERE d.kiem_ke_ca_id = NEW.id AND d.clinic_id = NEW.clinic_id
           AND d.dem IS NOT NULL AND d.ton_may IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Phiếu kiểm kê cần ít nhất một dòng đã chụp tồn sổ'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION public.vat_tu_kiem_ke_ca_dong_gac()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p public.vat_tu_kiem_ke_ca; t public.vat_tu_ton;
BEGIN
    SELECT * INTO p FROM public.vat_tu_kiem_ke_ca
     WHERE id = COALESCE(NEW.kiem_ke_ca_id, OLD.kiem_ke_ca_id)
       AND clinic_id = COALESCE(NEW.clinic_id, OLD.clinic_id) FOR UPDATE;
    IF p.id IS NULL OR p.trang_thai <> 'NHAP' THEN
        RAISE EXCEPTION 'Phiếu kiểm kê đã chốt hoặc không tồn tại — không sửa dòng'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    SELECT * INTO t FROM public.vat_tu_ton
     WHERE id = NEW.ton_id AND clinic_id = NEW.clinic_id;
    IF t.id IS NULL OR t.location_id <> p.location_id
       OR t.room_id IS DISTINCT FROM p.room_id
       OR t.vat_tu_id <> NEW.vat_tu_id OR NOT EXISTS (
           SELECT 1 FROM public.service_price s
            WHERE s.id = NEW.vat_tu_id AND s.clinic_id = NEW.clinic_id
              AND s."group" = 'vat_tu'
       ) THEN
        RAISE EXCEPTION 'Dòng kiểm kê phải thuộc đúng vật tư và phòng'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS vat_tu_kiem_ke_ca_phieu_gac ON public.vat_tu_kiem_ke_ca;
CREATE TRIGGER vat_tu_kiem_ke_ca_phieu_gac
    BEFORE INSERT OR UPDATE ON public.vat_tu_kiem_ke_ca
    FOR EACH ROW EXECUTE FUNCTION public.vat_tu_kiem_ke_ca_phieu_gac();
DROP TRIGGER IF EXISTS vat_tu_kiem_ke_ca_dong_gac ON public.vat_tu_kiem_ke_ca_dong;
CREATE TRIGGER vat_tu_kiem_ke_ca_dong_gac
    BEFORE INSERT OR UPDATE OR DELETE ON public.vat_tu_kiem_ke_ca_dong
    FOR EACH ROW EXECUTE FUNCTION public.vat_tu_kiem_ke_ca_dong_gac();

ALTER TABLE public.vat_tu_kiem_ke_ca ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vat_tu_kiem_ke_ca_dong ENABLE ROW LEVEL SECURITY;
-- Dashboard đọc qua FastAPI để kiểm tra capability và phạm vi cơ sở/phòng;
-- authenticated không đọc trực tiếp sổ kiểm kê qua PostgREST.
DROP POLICY IF EXISTS vat_tu_kiem_ke_ca_select_own_clinic ON public.vat_tu_kiem_ke_ca;
DROP POLICY IF EXISTS vat_tu_kiem_ke_ca_dong_select_own_clinic
    ON public.vat_tu_kiem_ke_ca_dong;
REVOKE ALL ON public.vat_tu_kiem_ke_ca, public.vat_tu_kiem_ke_ca_dong
    FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.vat_tu_kiem_ke_ca TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vat_tu_kiem_ke_ca_dong TO service_role;

DROP TRIGGER IF EXISTS trg_notify_vat_tu_kiem_ke_ca ON public.vat_tu_kiem_ke_ca;
CREATE TRIGGER trg_notify_vat_tu_kiem_ke_ca
    AFTER INSERT OR UPDATE OR DELETE ON public.vat_tu_kiem_ke_ca
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
DROP TRIGGER IF EXISTS trg_notify_vat_tu_kiem_ke_ca_dong
    ON public.vat_tu_kiem_ke_ca_dong;
CREATE TRIGGER trg_notify_vat_tu_kiem_ke_ca_dong
    AFTER INSERT OR UPDATE OR DELETE ON public.vat_tu_kiem_ke_ca_dong
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

NOTIFY pgrst, 'reload schema';
