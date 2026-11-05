-- XÉT NGHIỆM ĐỐI TÁC — CHẶNG 3: MẪU, MÃ ỐNG, ĐÓNG VIỆC (kế hoạch 4.5, 5, 5c; ADR-0015).
--
-- 1. Mã ống cấp ở Postgres: bộ đếm theo phòng khám (`UPDATE … RETURNING` giữ khoá
--    dòng — hai người bấm cùng lúc không trùng số) + chữ số kiểm DAMM (cùng bảng
--    với `services/xet_nghiem/ma_mau.py`, test chéo 1.000 số). 572 → M005724.
-- 2. `mau_xet_nghiem` (một ống) + `mau_xet_nghiem_viec` (ống chứa việc nào). Một ống
--    một đối tác: ÉP bằng FK ghép (mau_id, doi_tac_id) và (service_order_id,
--    doi_tac_id) — không bằng `if` Python. Một việc chỉ thuộc MỘT mẫu còn hiệu lực.
--    Huỷ mẫu (NHAP_SAI / MAU_HONG) = đóng mẫu + gỡ việc, không xoá; lấy lại = mã MỚI.
-- 3. `xet_nghiem_dong` — "Đối tác đã tự trả khách" (5c): đóng việc có lý do; MỞ LẠI
--    = đóng bản ghi đóng (không xoá). Một việc một lần đóng còn hiệu lực.
-- 4. `xet_nghiem_viec`: "Gỡ cho qua" (soát #600 — không khoá cứng): thêm cột gỡ,
--    trigger cho ĐÓNG cho qua đúng một lần (khuôn doi_tac_thanh_toan).
-- Chạy lại được.

-- ── 1. Damm + bộ đếm + cấp mã ───────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.damm_chu_so_kiem(p_so text)
RETURNS integer LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    bang int[] := ARRAY[
        0,3,1,7,5,9,8,6,4,2,  7,0,9,2,1,5,4,8,6,3,  4,2,0,6,8,7,1,3,5,9,
        1,7,5,0,9,8,3,4,2,6,  6,1,2,3,0,4,5,9,7,8,  3,6,7,4,2,0,9,5,8,1,
        5,8,6,9,7,2,0,1,3,4,  8,9,4,5,3,6,2,0,1,7,  9,4,3,8,6,1,7,2,0,5,
        2,5,8,1,4,3,6,7,9,0];
    tg int := 0;
    i int;
BEGIN
    FOR i IN 1..length(p_so) LOOP
        tg := bang[tg * 10 + substr(p_so, i, 1)::int + 1];
    END LOOP;
    RETURN tg;
END $$;

CREATE TABLE IF NOT EXISTS public.mau_xet_nghiem_dem (
    clinic_id  uuid PRIMARY KEY REFERENCES public.clinic (id) ON DELETE RESTRICT,
    so_cuoi    integer NOT NULL DEFAULT 0 CHECK (so_cuoi >= 0)
);

CREATE OR REPLACE FUNCTION public.cap_ma_mau(p_clinic uuid, OUT so integer, OUT ma text)
LANGUAGE plpgsql AS $$
DECLARE than text;
BEGIN
    INSERT INTO public.mau_xet_nghiem_dem (clinic_id, so_cuoi) VALUES (p_clinic, 1)
    ON CONFLICT (clinic_id) DO UPDATE SET so_cuoi = mau_xet_nghiem_dem.so_cuoi + 1
    RETURNING so_cuoi INTO so;
    than := lpad(so::text, 5, '0');
    ma := 'M' || than || public.damm_chu_so_kiem(than)::text;
END $$;

-- ── 2. Mẫu ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.mau_xet_nghiem (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL,
    doi_tac_id       uuid NOT NULL,
    ma_mau           text NOT NULL,
    so_thu_tu        integer NOT NULL,
    lay_luc          timestamptz NOT NULL DEFAULT now(),
    lay_boi          uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    -- CHỤP lúc lấy mẫu (một ngày cụ thể, đếm mọi ngày — câu E).
    hen_tra_ngay     date,
    hen_tra_sua_luc  timestamptz,
    hen_tra_sua_boi  uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    hen_tra_sua_ly_do text,
    huy_luc          timestamptz,
    huy_boi          uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    huy_ly_do        text,
    huy_loai         text CHECK (huy_loai IS NULL OR huy_loai IN ('NHAP_SAI', 'MAU_HONG')),
    CONSTRAINT mau_xet_nghiem_doi_tac_fk FOREIGN KEY (doi_tac_id, clinic_id)
        REFERENCES public.doi_tac (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT mau_xet_nghiem_id_doi_tac UNIQUE (id, doi_tac_id),
    CONSTRAINT mau_xet_nghiem_ma_hop_le CHECK (ma_mau ~ '^M[0-9]{6,}$'),
    CONSTRAINT mau_xet_nghiem_huy_dau_vet CHECK (
        (huy_luc IS NULL AND huy_boi IS NULL AND huy_ly_do IS NULL AND huy_loai IS NULL)
        OR (huy_luc IS NOT NULL AND huy_boi IS NOT NULL AND huy_loai IS NOT NULL
            AND length(btrim(huy_ly_do)) BETWEEN 3 AND 2000)),
    CONSTRAINT mau_xet_nghiem_sua_hen_dau_vet CHECK (
        (hen_tra_sua_luc IS NULL) = (hen_tra_sua_boi IS NULL)
        AND (hen_tra_sua_luc IS NULL OR length(btrim(hen_tra_sua_ly_do)) BETWEEN 3 AND 2000))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mau_xet_nghiem_ma
    ON public.mau_xet_nghiem (clinic_id, ma_mau);

CREATE TABLE IF NOT EXISTS public.mau_xet_nghiem_viec (
    mau_id            uuid NOT NULL,
    service_order_id  uuid NOT NULL,
    doi_tac_id        uuid NOT NULL,
    clinic_id         uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    go_luc            timestamptz,
    go_boi            uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    go_ly_do          text,
    PRIMARY KEY (mau_id, service_order_id),
    -- MỘT ỐNG MỘT ĐỐI TÁC: hai khoá ngoại ghép cùng cột doi_tac_id.
    CONSTRAINT mau_viec_mau_fk FOREIGN KEY (mau_id, doi_tac_id)
        REFERENCES public.mau_xet_nghiem (id, doi_tac_id) ON DELETE RESTRICT,
    CONSTRAINT mau_viec_viec_fk FOREIGN KEY (service_order_id, doi_tac_id)
        REFERENCES public.xet_nghiem_viec (service_order_id, doi_tac_id) ON DELETE RESTRICT,
    CONSTRAINT mau_viec_go_dau_vet CHECK (
        (go_luc IS NULL AND go_boi IS NULL AND go_ly_do IS NULL)
        OR (go_luc IS NOT NULL AND go_boi IS NOT NULL
            AND length(btrim(go_ly_do)) BETWEEN 3 AND 2000))
);
-- Một việc chỉ thuộc MỘT mẫu còn hiệu lực (hai người lấy mẫu cùng việc: một thua).
CREATE UNIQUE INDEX IF NOT EXISTS ux_mau_viec_mot_mau
    ON public.mau_xet_nghiem_viec (clinic_id, service_order_id) WHERE go_luc IS NULL;

-- ── 3. Đóng việc (đối tác đã tự trả khách) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS public.xet_nghiem_dong (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    service_order_id  uuid NOT NULL REFERENCES public.xet_nghiem_viec (service_order_id)
                           ON DELETE RESTRICT,
    ly_do             text NOT NULL CHECK (length(btrim(ly_do)) BETWEEN 3 AND 2000),
    dong_luc          timestamptz NOT NULL DEFAULT now(),
    dong_boi          uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    mo_lai_luc        timestamptz,
    mo_lai_boi        uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    mo_lai_ly_do      text,
    CONSTRAINT xet_nghiem_dong_mo_lai_dau_vet CHECK (
        (mo_lai_luc IS NULL AND mo_lai_boi IS NULL AND mo_lai_ly_do IS NULL)
        OR (mo_lai_luc IS NOT NULL AND mo_lai_boi IS NOT NULL
            AND length(btrim(mo_lai_ly_do)) BETWEEN 3 AND 2000))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_xet_nghiem_dong_con_hieu_luc
    ON public.xet_nghiem_dong (clinic_id, service_order_id) WHERE mo_lai_luc IS NULL;

-- ── 4. Gỡ cho qua ───────────────────────────────────────────────────────────
ALTER TABLE public.xet_nghiem_viec
    ADD COLUMN IF NOT EXISTS cho_lay_mau_go_luc   timestamptz,
    ADD COLUMN IF NOT EXISTS cho_lay_mau_go_boi   uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS cho_lay_mau_go_ly_do text;
ALTER TABLE public.xet_nghiem_viec DROP CONSTRAINT IF EXISTS xet_nghiem_viec_go_cho_qua_dau_vet;
ALTER TABLE public.xet_nghiem_viec ADD CONSTRAINT xet_nghiem_viec_go_cho_qua_dau_vet CHECK (
    (cho_lay_mau_go_luc IS NULL AND cho_lay_mau_go_boi IS NULL AND cho_lay_mau_go_ly_do IS NULL)
    OR (cho_lay_mau_truoc_luc IS NOT NULL AND cho_lay_mau_go_luc IS NOT NULL
        AND cho_lay_mau_go_boi IS NOT NULL
        AND length(btrim(cho_lay_mau_go_ly_do)) BETWEEN 3 AND 2000));

CREATE OR REPLACE FUNCTION public.xet_nghiem_viec_chi_cho_qua()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'xet_nghiem_viec: không xoá'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.service_order_id, NEW.clinic_id, NEW.doi_tac_id,
        NEW.gia_goi_y_luc_chi_dinh, NEW.tao_luc)
       IS DISTINCT FROM
       (OLD.service_order_id, OLD.clinic_id, OLD.doi_tac_id,
        OLD.gia_goi_y_luc_chi_dinh, OLD.tao_luc)
       -- cho qua: đặt đúng một lần
       OR (OLD.cho_lay_mau_truoc_luc IS NOT NULL
           AND (NEW.cho_lay_mau_truoc_luc, NEW.cho_lay_mau_truoc_boi,
                NEW.cho_lay_mau_truoc_ly_do)
               IS DISTINCT FROM
               (OLD.cho_lay_mau_truoc_luc, OLD.cho_lay_mau_truoc_boi,
                OLD.cho_lay_mau_truoc_ly_do))
       -- gỡ cho qua: đóng đúng một lần
       OR (OLD.cho_lay_mau_go_luc IS NOT NULL
           AND (NEW.cho_lay_mau_go_luc, NEW.cho_lay_mau_go_boi, NEW.cho_lay_mau_go_ly_do)
               IS DISTINCT FROM
               (OLD.cho_lay_mau_go_luc, OLD.cho_lay_mau_go_boi, OLD.cho_lay_mau_go_ly_do))
    THEN
        RAISE EXCEPTION 'xet_nghiem_viec: bản chụp không sửa được'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;

-- ── Bất biến: không xoá; nội dung mẫu / việc trong ống / đóng chỉ ĐÓNG một lần ──
CREATE OR REPLACE FUNCTION public.mau_xet_nghiem_chi_dong()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '%: không xoá — huỷ / gỡ / mở lại kèm lý do', TG_TABLE_NAME
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF TG_TABLE_NAME = 'mau_xet_nghiem' THEN
        IF (NEW.clinic_id, NEW.doi_tac_id, NEW.ma_mau, NEW.so_thu_tu, NEW.lay_luc,
            NEW.lay_boi) IS DISTINCT FROM
           (OLD.clinic_id, OLD.doi_tac_id, OLD.ma_mau, OLD.so_thu_tu, OLD.lay_luc,
            OLD.lay_boi)
           OR (OLD.huy_luc IS NOT NULL AND NEW IS DISTINCT FROM OLD) THEN
            RAISE EXCEPTION 'mau_xet_nghiem: chỉ được sửa hẹn trả (có lý do) hoặc huỷ một lần'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    ELSIF TG_TABLE_NAME = 'mau_xet_nghiem_viec' THEN
        IF (NEW.mau_id, NEW.service_order_id, NEW.doi_tac_id, NEW.clinic_id)
           IS DISTINCT FROM (OLD.mau_id, OLD.service_order_id, OLD.doi_tac_id, OLD.clinic_id)
           OR OLD.go_luc IS NOT NULL THEN
            RAISE EXCEPTION 'mau_xet_nghiem_viec: chỉ được gỡ một lần'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    ELSIF TG_TABLE_NAME = 'xet_nghiem_dong' THEN
        IF (NEW.clinic_id, NEW.service_order_id, NEW.ly_do, NEW.dong_luc, NEW.dong_boi)
           IS DISTINCT FROM
           (OLD.clinic_id, OLD.service_order_id, OLD.ly_do, OLD.dong_luc, OLD.dong_boi)
           OR OLD.mo_lai_luc IS NOT NULL THEN
            RAISE EXCEPTION 'xet_nghiem_dong: chỉ được mở lại một lần'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;
    RETURN NEW;
END $$;

DO $$
DECLARE b text;
BEGIN
    FOREACH b IN ARRAY ARRAY['mau_xet_nghiem', 'mau_xet_nghiem_viec', 'xet_nghiem_dong'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I', 'trg_' || b || '_chi_dong', b);
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION public.mau_xet_nghiem_chi_dong()',
            'trg_' || b || '_chi_dong', b);
    END LOOP;
    FOREACH b IN ARRAY ARRAY['mau_xet_nghiem', 'mau_xet_nghiem_viec', 'xet_nghiem_dong',
                             'mau_xet_nghiem_dem'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', b);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', b || '_select_own_clinic', b);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO service_role '
            'USING (clinic_id IN (SELECT current_clinic_ids()))',
            b || '_select_own_clinic', b);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON public.%I TO service_role', b);
    END LOOP;
    FOREACH b IN ARRAY ARRAY['mau_xet_nghiem', 'mau_xet_nghiem_viec', 'xet_nghiem_dong']
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I', 'trg_notify_' || b, b);
        EXECUTE format(
            'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION public.notify_row_change()',
            'trg_notify_' || b, b);
    END LOOP;
END $$;
