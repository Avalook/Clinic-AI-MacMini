-- Đính chính tạo phiên bản mới; giữ nguyên phiếu và snapshot đã chốt.
-- Diễn tập: thực thi lại migration phải không đổi dữ liệu hoặc lỗi.
-- Rollback ứng dụng: giữ schema và dữ liệu phiên bản; không DROP cột hay bản sửa.
-- Ứng dụng cũ chưa biết phiên bản không được mở lại ghi kiểm kê sau rollback;
-- khôi phục bản ứng dụng đã biết phiên bản để tiếp tục, không xoá lịch sử.
ALTER TABLE public.kiem_ke_ca
    ADD COLUMN IF NOT EXISTS phieu_truoc_id uuid REFERENCES public.kiem_ke_ca(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS phien_ban integer NOT NULL DEFAULT 1 CHECK (phien_ban > 0),
    ADD COLUMN IF NOT EXISTS moc_ton_luc timestamptz,
    ADD COLUMN IF NOT EXISTS ly_do_sua text;
ALTER TABLE public.kiem_ke_ca DROP CONSTRAINT IF EXISTS kiem_ke_ca_sua_day_du;
ALTER TABLE public.kiem_ke_ca
    ADD CONSTRAINT kiem_ke_ca_sua_day_du CHECK (
        (phieu_truoc_id IS NULL AND phien_ban = 1 AND ly_do_sua IS NULL)
        OR (phieu_truoc_id IS NOT NULL AND phien_ban > 1
            AND length(btrim(coalesce(ly_do_sua, ''))) BETWEEN 1 AND 1000));

DROP INDEX IF EXISTS public.uq_kiem_ke_ca_dau_cuoi;
CREATE UNIQUE INDEX IF NOT EXISTS uq_kiem_ke_ca_dau_cuoi
    ON public.kiem_ke_ca (location_id, ngay, ca, loai)
    WHERE loai IN ('DAU', 'CUOI') AND phieu_truoc_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_kiem_ke_ca_mot_ban_sua
    ON public.kiem_ke_ca (phieu_truoc_id) WHERE phieu_truoc_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.kiem_ke_ca_phien_ban_hop_le()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p public.kiem_ke_ca;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.phieu_truoc_id, NEW.phien_ban, NEW.ly_do_sua)
            IS DISTINCT FROM (OLD.phieu_truoc_id, OLD.phien_ban, OLD.ly_do_sua) THEN
            RAISE EXCEPTION 'Không sửa liên kết hoặc lý do phiên bản kiểm kê'
                USING ERRCODE = '23514';
        END IF;
        IF OLD.trang_thai = 'CHOT' AND NEW.moc_ton_luc IS DISTINCT FROM OLD.moc_ton_luc THEN
            RAISE EXCEPTION 'Không sửa mốc tồn của phiếu đã chốt' USING ERRCODE = '23514';
        END IF;
        IF OLD.dieu_chinh_luc IS NULL AND NEW.dieu_chinh_luc IS NOT NULL
           AND EXISTS (SELECT 1 FROM public.kiem_ke_ca WHERE phieu_truoc_id = NEW.id) THEN
            RAISE EXCEPTION 'Phiếu đã có bản sửa, không điều chỉnh bản cũ'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.phieu_truoc_id IS NULL THEN RETURN NEW; END IF;
    SELECT * INTO p FROM public.kiem_ke_ca WHERE id = NEW.phieu_truoc_id FOR UPDATE;
    IF p.id IS NULL OR p.trang_thai <> 'CHOT'
       OR (NEW.clinic_id, NEW.location_id, NEW.ngay, NEW.ca, NEW.loai, NEW.phien_ban)
            IS DISTINCT FROM (p.clinic_id, p.location_id, p.ngay, p.ca, p.loai, p.phien_ban + 1)
       OR (p.dieu_chinh_luc IS NOT NULL AND p.hoan_tac_luc IS NULL) THEN
        RAISE EXCEPTION 'Phiên bản sửa phải nối phiếu đã chốt cùng ca và đã hoàn tác điều chỉnh'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS kiem_ke_ca_phien_ban_hop_le ON public.kiem_ke_ca;
CREATE TRIGGER kiem_ke_ca_phien_ban_hop_le BEFORE INSERT OR UPDATE ON public.kiem_ke_ca
    FOR EACH ROW EXECUTE FUNCTION public.kiem_ke_ca_phien_ban_hop_le();
NOTIFY pgrst, 'reload schema';
