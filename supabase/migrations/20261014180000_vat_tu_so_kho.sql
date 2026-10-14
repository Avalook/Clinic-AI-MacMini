-- G8a: sổ riêng, không chạm thuốc hay vật tư đã thu tiền.
CREATE TABLE IF NOT EXISTS public.vat_tu_phieu (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id uuid NOT NULL REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    ma_phieu text NOT NULL,
    loai text NOT NULL CHECK (loai IN ('NHAP','XUAT_PHONG','TRA_KHO','CHUYEN_PHONG','KIEM','DIEU_CHINH','HUY','HOAN')),
    khoa_gui text NOT NULL CHECK (length(btrim(khoa_gui)) BETWEEN 1 AND 200),
    tao_boi uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    tao_luc timestamptz NOT NULL DEFAULT now(),
    giao_dich xid8 NOT NULL DEFAULT pg_current_xact_id(),
    ghi_chu text,
    dao_phieu_id uuid REFERENCES public.vat_tu_phieu(id) ON DELETE RESTRICT,
    CONSTRAINT vat_tu_phieu_khoa UNIQUE (clinic_id, location_id, khoa_gui),
    CONSTRAINT vat_tu_phieu_ma UNIQUE (clinic_id, ma_phieu),
    CONSTRAINT vat_tu_phieu_dao UNIQUE (clinic_id, dao_phieu_id),
    CHECK ((loai='HOAN') = (dao_phieu_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS public.vat_tu_ton (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id uuid NOT NULL REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    vat_tu_id uuid NOT NULL REFERENCES public.service_price(id) ON DELETE RESTRICT,
    room_id uuid REFERENCES public.clinic_room(id) ON DELETE RESTRICT,
    so_luong numeric(18,3) NOT NULL DEFAULT 0 CHECK (so_luong NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)),
    ton_toi_thieu numeric(18,3) NOT NULL DEFAULT 0 CHECK (ton_toi_thieu >= 0 AND ton_toi_thieu NOT IN ('NaN'::numeric, 'Infinity'::numeric)),
    CONSTRAINT vat_tu_ton_noi UNIQUE NULLS NOT DISTINCT (clinic_id, location_id, vat_tu_id, room_id)
);

CREATE TABLE IF NOT EXISTS public.vat_tu_txn (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    phieu_id uuid NOT NULL REFERENCES public.vat_tu_phieu(id) ON DELETE RESTRICT,
    ton_id uuid NOT NULL REFERENCES public.vat_tu_ton(id) ON DELETE RESTRICT,
    vat_tu_id uuid NOT NULL REFERENCES public.service_price(id) ON DELETE RESTRICT,
    so_luong numeric(18,3) NOT NULL CHECK (so_luong NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)),
    ton_may numeric(18,3) NOT NULL,
    thuc_te numeric(18,3) CHECK (thuc_te >= 0 AND thuc_te NOT IN ('NaN'::numeric, 'Infinity'::numeric)),
    gia_nhap numeric(18,0) NOT NULL DEFAULT 0 CHECK (gia_nhap >= 0 AND gia_nhap NOT IN ('NaN'::numeric, 'Infinity'::numeric)),
    tao_luc timestamptz NOT NULL DEFAULT now(),
    dao_txn_id uuid REFERENCES public.vat_tu_txn(id) ON DELETE RESTRICT,
    CONSTRAINT vat_tu_txn_dao UNIQUE (clinic_id, dao_txn_id)
);
CREATE INDEX IF NOT EXISTS vat_tu_txn_the_kho ON public.vat_tu_txn(clinic_id, ton_id, tao_luc, id);
CREATE INDEX IF NOT EXISTS vat_tu_txn_phieu ON public.vat_tu_txn(clinic_id, phieu_id);

CREATE OR REPLACE FUNCTION public.vat_tu_chi_them() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Sổ vật tư chỉ thêm — lập phiếu đảo để hoàn tác' USING ERRCODE='check_violation';
END $$;

CREATE OR REPLACE FUNCTION public.vat_tu_ton_gac() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Không xoá tồn vật tư' USING ERRCODE='check_violation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.clinic_location WHERE id=NEW.location_id AND clinic_id=NEW.clinic_id)
       OR NOT EXISTS (SELECT 1 FROM public.service_price WHERE id=NEW.vat_tu_id AND clinic_id=NEW.clinic_id AND "group"='vat_tu')
       OR (NEW.room_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.clinic_room
           WHERE id=NEW.room_id AND clinic_id=NEW.clinic_id AND location_id=NEW.location_id)) THEN
        RAISE EXCEPTION 'Nơi chứa/mặt hàng không thuộc cơ sở và phòng khám' USING ERRCODE='check_violation';
    END IF;
    IF TG_OP='INSERT' AND NEW.so_luong<>0 THEN
        RAISE EXCEPTION 'Tồn ban đầu bằng 0 — ghi sổ để điều chỉnh' USING ERRCODE='check_violation';
    END IF;
    IF TG_OP='UPDATE' THEN
        IF (NEW.clinic_id,NEW.location_id,NEW.vat_tu_id,NEW.room_id) IS DISTINCT FROM
           (OLD.clinic_id,OLD.location_id,OLD.vat_tu_id,OLD.room_id)
           OR (NEW.so_luong IS DISTINCT FROM OLD.so_luong AND pg_trigger_depth()<2) THEN
            RAISE EXCEPTION 'Không sửa nơi chứa/tồn trực tiếp — ghi sổ vật tư' USING ERRCODE='check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION public.vat_tu_phieu_gac() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.clinic_location WHERE id=NEW.location_id AND clinic_id=NEW.clinic_id)
       OR NOT EXISTS (SELECT 1 FROM public.clinic_membership WHERE clinic_id=NEW.clinic_id AND staff_id=NEW.tao_boi AND is_active) THEN
        RAISE EXCEPTION 'Phiếu vật tư sai cơ sở/người tạo' USING ERRCODE='check_violation';
    END IF;
    IF NEW.dao_phieu_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.vat_tu_phieu WHERE id=NEW.dao_phieu_id AND clinic_id=NEW.clinic_id
          AND location_id=NEW.location_id AND loai<>'HOAN') THEN
        RAISE EXCEPTION 'Không đảo phiếu khác cơ sở hoặc phiếu đảo' USING ERRCODE='check_violation';
    END IF;
    RETURN NEW;
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
       OR (p.loai='HUY' AND NEW.so_luong>=0)
       OR (p.loai='DIEU_CHINH' AND (NEW.thuc_te IS NULL OR NEW.so_luong<>NEW.thuc_te-NEW.ton_may)) THEN
        RAISE EXCEPTION 'Dòng sổ không đúng loại phiếu/đếm thực tế' USING ERRCODE='check_violation';
    END IF;
    UPDATE public.vat_tu_ton SET so_luong=so_luong+NEW.so_luong
      WHERE id=NEW.ton_id AND clinic_id=NEW.clinic_id;
    RETURN NEW;
END $$;

-- Kiểm nguyên phiếu lúc COMMIT: không thể chuyển một nửa hay đảo thiếu dòng.
CREATE OR REPLACE FUNCTION public.vat_tu_phieu_du_dong() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE p record; phieu uuid;
BEGIN
    IF TG_TABLE_NAME='vat_tu_txn' THEN
        phieu := NEW.phieu_id;
    ELSE
        phieu := NEW.id;
    END IF;
    SELECT * INTO p FROM public.vat_tu_phieu WHERE id=phieu AND clinic_id=NEW.clinic_id;
    IF NOT EXISTS (SELECT 1 FROM public.vat_tu_txn WHERE phieu_id=p.id AND clinic_id=p.clinic_id) THEN
        RAISE EXCEPTION 'Phiếu vật tư chưa có dòng' USING ERRCODE='check_violation';
    END IF;
    IF p.loai IN ('XUAT_PHONG','TRA_KHO','CHUYEN_PHONG') AND EXISTS (
        SELECT x.vat_tu_id FROM public.vat_tu_txn x JOIN public.vat_tu_ton t ON t.id=x.ton_id
        WHERE x.phieu_id=p.id AND x.clinic_id=p.clinic_id GROUP BY x.vat_tu_id
        HAVING sum(x.so_luong)<>0 OR min(x.so_luong)>=0 OR max(x.so_luong)<=0
           OR (p.loai='CHUYEN_PHONG' AND (bool_or(t.room_id IS NULL) OR count(DISTINCT t.room_id)<2))
           OR (p.loai='XUAT_PHONG' AND bool_or((x.so_luong<0 AND t.room_id IS NOT NULL) OR (x.so_luong>0 AND t.room_id IS NULL)))
           OR (p.loai='TRA_KHO' AND bool_or((x.so_luong>0 AND t.room_id IS NOT NULL) OR (x.so_luong<0 AND t.room_id IS NULL)))
    ) THEN
        RAISE EXCEPTION 'Phiếu chuyển phải đủ dòng đối ứng đúng nơi chứa' USING ERRCODE='check_violation';
    END IF;
    IF p.loai='HOAN' AND (SELECT count(*) FROM public.vat_tu_txn WHERE phieu_id=p.id AND clinic_id=p.clinic_id)
       <> (SELECT count(*) FROM public.vat_tu_txn WHERE phieu_id=p.dao_phieu_id AND clinic_id=p.clinic_id) THEN
        RAISE EXCEPTION 'Phiếu đảo phải đảo đủ dòng gốc' USING ERRCODE='check_violation';
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS vat_tu_ton_gac ON public.vat_tu_ton;
CREATE TRIGGER vat_tu_ton_gac BEFORE INSERT OR UPDATE OR DELETE ON public.vat_tu_ton FOR EACH ROW EXECUTE FUNCTION public.vat_tu_ton_gac();
DROP TRIGGER IF EXISTS vat_tu_phieu_gac ON public.vat_tu_phieu;
CREATE TRIGGER vat_tu_phieu_gac BEFORE INSERT ON public.vat_tu_phieu FOR EACH ROW EXECUTE FUNCTION public.vat_tu_phieu_gac();
DROP TRIGGER IF EXISTS vat_tu_phieu_chi_them ON public.vat_tu_phieu;
CREATE TRIGGER vat_tu_phieu_chi_them BEFORE UPDATE OR DELETE ON public.vat_tu_phieu FOR EACH ROW EXECUTE FUNCTION public.vat_tu_chi_them();
DROP TRIGGER IF EXISTS vat_tu_txn_chi_them ON public.vat_tu_txn;
CREATE TRIGGER vat_tu_txn_chi_them BEFORE UPDATE OR DELETE ON public.vat_tu_txn FOR EACH ROW EXECUTE FUNCTION public.vat_tu_chi_them();
DROP TRIGGER IF EXISTS vat_tu_txn_cong_ton ON public.vat_tu_txn;
CREATE TRIGGER vat_tu_txn_cong_ton BEFORE INSERT ON public.vat_tu_txn FOR EACH ROW EXECUTE FUNCTION public.vat_tu_txn_cong_ton();
DROP TRIGGER IF EXISTS vat_tu_phieu_du_dong ON public.vat_tu_phieu;
CREATE CONSTRAINT TRIGGER vat_tu_phieu_du_dong AFTER INSERT ON public.vat_tu_phieu
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.vat_tu_phieu_du_dong();
DROP TRIGGER IF EXISTS vat_tu_txn_du_dong ON public.vat_tu_txn;
CREATE CONSTRAINT TRIGGER vat_tu_txn_du_dong AFTER INSERT ON public.vat_tu_txn
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.vat_tu_phieu_du_dong();

DO $$
DECLARE ten text;
BEGIN
    FOREACH ten IN ARRAY ARRAY['vat_tu_phieu','vat_tu_ton','vat_tu_txn'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', ten);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', ten||'_select_own_clinic', ten);
        EXECUTE format('CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()))', ten||'_select_own_clinic', ten);
        EXECUTE format('GRANT SELECT ON public.%I TO authenticated', ten);
        EXECUTE format('GRANT SELECT, INSERT ON public.%I TO service_role', ten);
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I', 'trg_notify_'||ten, ten);
        EXECUTE format('CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.notify_row_change()', 'trg_notify_'||ten, ten);
    END LOOP;
END $$;
GRANT UPDATE ON public.vat_tu_ton TO service_role;
NOTIFY pgrst, 'reload schema';
