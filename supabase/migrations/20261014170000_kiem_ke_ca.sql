-- G6 — KIỂM KÊ ĐẦU / CUỐI CA Ở QUẦY (Tuyền 14/10/2026).
--
-- Hai bảng, KHÔNG đổi cách tồn được tính và KHÔNG tự sửa tồn:
--   1. `kiem_ke_ca`      — một phiếu kiểm của một cơ sở · ngày · ca · loại
--                          (DAU / CUOI; DOT_XUAT kiểm bất kỳ lúc, nhiều phiếu).
--                          NHAP → CHOT. Hai người mở kiểm cùng ca = MỘT phiếu
--                          (UNIQUE từng phần ép Ở ĐÂY, không ở Python).
--   2. `kiem_ke_ca_dong` — số ĐẾM từng (thuốc, đơn vị) của phiếu; lúc CHỐT ghi
--                          tồn máy tại giờ chốt + lệch = đếm − tồn máy. Kiểm một
--                          phần: thuốc không có dòng thì không bị tính lệch.
-- "Điều chỉnh theo kiểm kê" là bước riêng ghi `ADJUST` vào sổ kho (ref_type
-- 'kiem_ke_ca'), có lý do, hoàn tác được — các cột `dieu_chinh_*` / `hoan_tac_*`
-- chỉ giữ dấu vết ai/lúc/lý do; số lượng nằm ở sổ kho.
--
-- Chạy lại nhiều lần được (ci-may áp hai lần): IF NOT EXISTS / DROP … IF EXISTS.

CREATE TABLE IF NOT EXISTS public.kiem_ke_ca (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id       uuid NOT NULL REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    ngay              date NOT NULL,
    ca                text NOT NULL CHECK (ca IN ('SANG', 'CHIEU', 'TOI')),
    loai              text NOT NULL CHECK (loai IN ('DAU', 'CUOI', 'DOT_XUAT')),
    trang_thai        text NOT NULL DEFAULT 'NHAP' CHECK (trang_thai IN ('NHAP', 'CHOT')),
    -- Chốt mà còn thuốc có tồn ở quầy chưa được đếm → kiểm một phần.
    mot_phan          boolean NOT NULL DEFAULT false,
    dung_so_ca_truoc  boolean NOT NULL DEFAULT false,
    ghi_chu           text,
    tao_boi           uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    tao_luc           timestamptz NOT NULL DEFAULT now(),
    chot_boi          uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    chot_luc          timestamptz,
    dieu_chinh_boi    uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    dieu_chinh_luc    timestamptz,
    dieu_chinh_ly_do  text,
    hoan_tac_boi      uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    hoan_tac_luc      timestamptz,
    CONSTRAINT kiem_ke_ca_chot_day_du CHECK (
        (trang_thai = 'CHOT') = (chot_luc IS NOT NULL AND chot_boi IS NOT NULL)),
    CONSTRAINT kiem_ke_ca_dieu_chinh_day_du CHECK (
        (dieu_chinh_luc IS NULL) = (dieu_chinh_boi IS NULL)
        AND (dieu_chinh_luc IS NULL OR (trang_thai = 'CHOT'
             AND length(btrim(coalesce(dieu_chinh_ly_do, ''))) > 0))),
    CONSTRAINT kiem_ke_ca_hoan_tac_sau_dieu_chinh CHECK (
        (hoan_tac_luc IS NULL) = (hoan_tac_boi IS NULL)
        AND (hoan_tac_luc IS NULL OR dieu_chinh_luc IS NOT NULL))
);

-- Đầu ca / cuối ca: một phiếu cho mỗi (cơ sở, ngày, ca, loại). Đột xuất: nhiều.
CREATE UNIQUE INDEX IF NOT EXISTS uq_kiem_ke_ca_dau_cuoi
    ON public.kiem_ke_ca (location_id, ngay, ca, loai)
    WHERE loai IN ('DAU', 'CUOI');

CREATE INDEX IF NOT EXISTS kiem_ke_ca_theo_ngay
    ON public.kiem_ke_ca (clinic_id, location_id, ngay DESC, ca);

CREATE TABLE IF NOT EXISTS public.kiem_ke_ca_dong (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    kiem_ke_ca_id    uuid NOT NULL REFERENCES public.kiem_ke_ca(id) ON DELETE CASCADE,
    drug_catalog_id  uuid NOT NULL,
    -- Đơn vị lô ở dạng so khớp (lower(btrim)) — không cộng hộp với viên.
    don_vi           text NOT NULL CHECK (length(btrim(don_vi)) > 0),
    dem              numeric(14, 3) NOT NULL CHECK (dem >= 0),
    -- Điền lúc CHỐT: tồn máy ở quầy tại giờ chốt, lệch = đếm − tồn máy.
    ton_may          numeric(14, 3),
    lech             numeric(14, 3),
    -- Thuốc đã giao mà chưa gắn lô lúc chốt: làm tồn máy cao hơn kệ thật, KHÔNG
    -- phải lệch đếm — hiện riêng để người rà thấy.
    giao_chua_gan_lo numeric(14, 3),
    CONSTRAINT kiem_ke_ca_dong_thuoc_fkey FOREIGN KEY (drug_catalog_id, clinic_id)
        REFERENCES public.drug_catalog (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT uq_kiem_ke_ca_dong UNIQUE (kiem_ke_ca_id, drug_catalog_id, don_vi),
    CONSTRAINT kiem_ke_ca_dong_lech_dung CHECK (
        (ton_may IS NULL) = (lech IS NULL)
        AND (lech IS NULL OR lech = dem - ton_may))
);

CREATE INDEX IF NOT EXISTS kiem_ke_ca_dong_theo_phieu
    ON public.kiem_ke_ca_dong (clinic_id, kiem_ke_ca_id);

-- Phiếu đã CHỐT không đổi (đếm, thuốc, người chốt); chỉ cột điều chỉnh / hoàn tác
-- đi tiếp. Dòng của phiếu đã chốt không thêm / sửa / xoá.
CREATE OR REPLACE FUNCTION public.kiem_ke_ca_bat_doi()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.trang_thai = 'CHOT' AND (
        NEW.trang_thai IS DISTINCT FROM OLD.trang_thai
        OR NEW.clinic_id IS DISTINCT FROM OLD.clinic_id
        OR NEW.location_id IS DISTINCT FROM OLD.location_id
        OR NEW.ngay IS DISTINCT FROM OLD.ngay
        OR NEW.ca IS DISTINCT FROM OLD.ca
        OR NEW.loai IS DISTINCT FROM OLD.loai
        OR NEW.mot_phan IS DISTINCT FROM OLD.mot_phan
        OR NEW.chot_boi IS DISTINCT FROM OLD.chot_boi
        OR NEW.chot_luc IS DISTINCT FROM OLD.chot_luc
        OR NEW.tao_boi IS DISTINCT FROM OLD.tao_boi
        OR NEW.tao_luc IS DISTINCT FROM OLD.tao_luc) THEN
        RAISE EXCEPTION 'Phiếu kiểm kê đã chốt, không sửa được'
            USING ERRCODE = '23514', CONSTRAINT = 'kiem_ke_ca_bat_doi';
    END IF;
    IF OLD.dieu_chinh_luc IS NOT NULL AND (
        NEW.dieu_chinh_luc IS DISTINCT FROM OLD.dieu_chinh_luc
        OR NEW.dieu_chinh_boi IS DISTINCT FROM OLD.dieu_chinh_boi
        OR NEW.dieu_chinh_ly_do IS DISTINCT FROM OLD.dieu_chinh_ly_do) THEN
        RAISE EXCEPTION 'Điều chỉnh theo kiểm kê đã ghi, chỉ hoàn tác được'
            USING ERRCODE = '23514', CONSTRAINT = 'kiem_ke_ca_bat_doi';
    END IF;
    IF OLD.hoan_tac_luc IS NOT NULL AND (
        NEW.hoan_tac_luc IS DISTINCT FROM OLD.hoan_tac_luc
        OR NEW.hoan_tac_boi IS DISTINCT FROM OLD.hoan_tac_boi) THEN
        RAISE EXCEPTION 'Phiếu đã hoàn tác điều chỉnh'
            USING ERRCODE = '23514', CONSTRAINT = 'kiem_ke_ca_bat_doi';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS kiem_ke_ca_bat_doi ON public.kiem_ke_ca;
CREATE TRIGGER kiem_ke_ca_bat_doi
    BEFORE UPDATE ON public.kiem_ke_ca
    FOR EACH ROW EXECUTE FUNCTION public.kiem_ke_ca_bat_doi();

CREATE OR REPLACE FUNCTION public.kiem_ke_ca_dong_phieu_da_chot()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    tt text;
BEGIN
    SELECT trang_thai INTO tt FROM public.kiem_ke_ca
     WHERE id = COALESCE(NEW.kiem_ke_ca_id, OLD.kiem_ke_ca_id);
    -- Xoá cả phiếu (CASCADE) thì phiếu không còn: để qua. Lúc CHỐT, service ghi
    -- tồn máy / lệch vào dòng TRƯỚC khi đổi trạng thái phiếu nên vẫn là NHAP.
    IF tt = 'CHOT' THEN
        RAISE EXCEPTION 'Phiếu kiểm kê đã chốt, không sửa dòng'
            USING ERRCODE = '23514', CONSTRAINT = 'kiem_ke_ca_dong_phieu_da_chot';
    END IF;
    RETURN COALESCE(NEW, OLD);
END
$$;

DROP TRIGGER IF EXISTS kiem_ke_ca_dong_phieu_da_chot ON public.kiem_ke_ca_dong;
CREATE TRIGGER kiem_ke_ca_dong_phieu_da_chot
    BEFORE INSERT OR UPDATE OR DELETE ON public.kiem_ke_ca_dong
    FOR EACH ROW EXECUTE FUNCTION public.kiem_ke_ca_dong_phieu_da_chot();

COMMENT ON TABLE public.kiem_ke_ca IS
    'Phiếu kiểm kê thuốc ở QUẦY theo ca (G6, 14/10/2026): DAU/CUOI một phiếu mỗi ca, DOT_XUAT bất kỳ lúc; NHAP→CHOT; chốt không tự sửa tồn — điều chỉnh là bước riêng (ADJUST, ref_type kiem_ke_ca), hoàn tác được.';
COMMENT ON TABLE public.kiem_ke_ca_dong IS
    'Số đếm từng (thuốc, đơn vị); lúc chốt ghi tồn máy tại giờ chốt và lệch = đếm − tồn máy.';

-- ── RLS — đọc trong phòng khám của mình, ghi qua FastAPI ────────────────
ALTER TABLE public.kiem_ke_ca ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kiem_ke_ca_dong ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS kiem_ke_ca_select_own_clinic ON public.kiem_ke_ca;
CREATE POLICY kiem_ke_ca_select_own_clinic
    ON public.kiem_ke_ca FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS kiem_ke_ca_dong_select_own_clinic ON public.kiem_ke_ca_dong;
CREATE POLICY kiem_ke_ca_dong_select_own_clinic
    ON public.kiem_ke_ca_dong FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT, INSERT, UPDATE ON public.kiem_ke_ca TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.kiem_ke_ca_dong TO service_role;
GRANT SELECT ON public.kiem_ke_ca, public.kiem_ke_ca_dong TO authenticated;

-- Chuông lệch kiểm kê: cùng người nhận mặc định với chuông hạn lô, quản lý chỉnh
-- được ở màn Dây nối chuông (dữ liệu, không viết cứng).
INSERT INTO public.day_nhan_thong_bao (clinic_id, su_kien, vai, bac_si_chinh, bat)
SELECT id, 'pharmacy.stocktake_mismatch', ARRAY['PHARMACIST','MANAGEMENT','TRUONG_CA'], false, true
  FROM public.clinic
ON CONFLICT (clinic_id, su_kien) DO NOTHING;

-- Bảng đổi thì màn Kho thuốc làm mới tức thời (kênh LISTEN/NOTIFY của mình).
DROP TRIGGER IF EXISTS trg_notify_kiem_ke_ca ON public.kiem_ke_ca;
CREATE TRIGGER trg_notify_kiem_ke_ca
    AFTER INSERT OR UPDATE OR DELETE ON public.kiem_ke_ca
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

NOTIFY pgrst, 'reload schema';
