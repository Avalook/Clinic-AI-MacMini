-- G4c · KHOÁ SỔ THEO CA (Tuyền chốt A, 14/10/2026).
-- Trước: báo cáo ca/ngày tính lại từ dữ liệu sống mỗi lần mở — huỷ phiếu hôm sau
-- trừ LÙI vào ngày thu cũ; báo cáo hôm qua in ra 10tr, hôm nay mở lại còn 9,2tr.
-- Nay ca đã CHỐT giữ đúng số lúc chốt (`so_lieu` chụp lại); huỷ phiếu / hoàn tác
-- của ca ấy SAU giờ chốt tính vào ca đang làm ("điều chỉnh ca trước").
-- Không khoá cứng: Quản lý MỞ KHOÁ được (bắt lý do, giữ dấu) rồi chốt lại.
--
-- Một lần chốt CÒN HIỆU LỰC cho mỗi (phòng khám, cơ sở, ngày, ca) — ép ở Postgres
-- (chỉ mục duy nhất một phần): hai người bấm "Chốt ca" cùng lúc thì người sau nhận
-- lỗi trùng, không có hai bản số. `tu_luc`/`den_luc` = khung giờ ca lúc chốt (bảng
-- ca trong cài đặt có thể đổi sau — sổ giữ khung đã dùng).

CREATE TABLE IF NOT EXISTS public.chot_so_ca (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    location_id uuid NOT NULL REFERENCES public.clinic_location (id) ON DELETE RESTRICT,
    ngay        date NOT NULL,
    ca          text NOT NULL CHECK (ca IN ('SANG', 'CHIEU', 'TOI')),
    tu_luc      timestamptz NOT NULL,
    den_luc     timestamptz NOT NULL,
    chot_luc    timestamptz NOT NULL DEFAULT now(),
    chot_boi    uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    so_lieu     jsonb NOT NULL,
    ghi_chu     text CHECK (ghi_chu IS NULL OR length(ghi_chu) <= 500),
    mo_luc      timestamptz,
    mo_boi      uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    ly_do_mo    text,
    CONSTRAINT chot_so_ca_khung_hop_le CHECK (den_luc > tu_luc),
    CONSTRAINT chot_so_ca_mo_di_cung CHECK (
        (mo_luc IS NULL) = (mo_boi IS NULL)
        AND (mo_luc IS NULL) = (ly_do_mo IS NULL)),
    CONSTRAINT chot_so_ca_ly_do_mo CHECK (
        ly_do_mo IS NULL OR length(btrim(ly_do_mo)) BETWEEN 3 AND 500)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chot_so_ca_con_hieu_luc
    ON public.chot_so_ca (clinic_id, location_id, ngay, ca)
    WHERE mo_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_chot_so_ca_khung
    ON public.chot_so_ca (clinic_id, location_id, tu_luc)
    WHERE mo_luc IS NULL;

COMMENT ON TABLE public.chot_so_ca IS
'Khoá sổ theo ca (14/10/2026): số liệu báo cáo ca chụp lúc chốt; thao tác sau '
'chốt tính vào ca đang làm. Mở khoá = Quản lý + lý do (không xoá, không sửa số).';

-- Không xoá; chỉ một lần UPDATE: mở khoá (điền mo_*), các cột khác bất biến.
CREATE OR REPLACE FUNCTION public.chot_so_ca_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'chot_so_ca: sổ chốt ca không xoá — mở khoá kèm lý do'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.mo_luc IS NOT NULL
       OR NEW.mo_luc IS NULL
       OR NEW.id <> OLD.id OR NEW.clinic_id <> OLD.clinic_id
       OR NEW.location_id <> OLD.location_id OR NEW.ngay <> OLD.ngay
       OR NEW.ca <> OLD.ca OR NEW.tu_luc <> OLD.tu_luc OR NEW.den_luc <> OLD.den_luc
       OR NEW.chot_luc <> OLD.chot_luc OR NEW.chot_boi <> OLD.chot_boi
       OR NEW.so_lieu <> OLD.so_lieu
       OR NEW.ghi_chu IS DISTINCT FROM OLD.ghi_chu THEN
        RAISE EXCEPTION 'chot_so_ca: chỉ được mở khoá một lần, số đã chốt không sửa'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_chot_so_ca_guard ON public.chot_so_ca;
CREATE TRIGGER trg_chot_so_ca_guard
    BEFORE UPDATE OR DELETE ON public.chot_so_ca
    FOR EACH ROW EXECUTE FUNCTION public.chot_so_ca_guard();

DROP TRIGGER IF EXISTS trg_notify_chot_so_ca ON public.chot_so_ca;
CREATE TRIGGER trg_notify_chot_so_ca
    AFTER INSERT OR UPDATE ON public.chot_so_ca
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

ALTER TABLE public.chot_so_ca ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS chot_so_ca_select_own_clinic ON public.chot_so_ca;
CREATE POLICY chot_so_ca_select_own_clinic ON public.chot_so_ca
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.chot_so_ca TO service_role;
