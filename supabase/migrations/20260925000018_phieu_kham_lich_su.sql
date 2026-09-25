-- LỊCH SỬ SỬA PHIẾU KHÁM (Tuyền 25/09/2026 — P4A): "bỏ khoá hồ sơ → lịch sử sửa".
--
-- Hoàn tất khám đã KHÔNG khoá phiếu (23/09). Phần còn thiếu là biết AI sửa, LÚC
-- NÀO, ô nào, giá trị TRƯỚC và SAU.
--
-- Ghi bằng TRIGGER trên `phieu_kham_luot`, không ghi ở Python: đường ghi nào vào
-- bảng phiếu cũng để lại vết, kể cả đường thêm sau này. Trigger chạy dưới khoá
-- dòng của chính lệnh UPDATE phiếu → hai lần lưu cùng phiếu nối tiếp nhau, không
-- có kẽ tranh chấp khi gộp.
--
-- GỘP: phiếu tự lưu mỗi 1,5 giây khi gõ. Ghi từng lần là hàng trăm dòng rác cho
-- một lần khám. Cùng một người sửa cùng một phiếu trong 10 phút kể từ lần lưu
-- gần nhất → gộp vào dòng lịch sử đang mở: `truoc` giữ giá trị TRƯỚC lần đầu,
-- `sau` lấy giá trị mới nhất. Ô sửa rồi trả lại y như cũ thì bỏ khỏi dòng; dòng
-- không còn ô nào thì xoá.
--
-- Chỉ lưu Ô ĐỔI (khoá → {gia_tri, nguon}), không chụp cả phiếu.
-- "Sửa sau Hoàn tất" tính lúc đọc (so `sua_luc` với `visit.exam_completed_at`).
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.phieu_kham_lich_su (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    phieu_id      uuid NOT NULL REFERENCES public.phieu_kham_luot (id) ON DELETE CASCADE,
    visit_id      uuid NOT NULL,
    form_id       text NOT NULL,
    sua_boi       uuid REFERENCES public.staff (id),
    bat_dau       timestamptz NOT NULL DEFAULT now(),
    sua_luc       timestamptz NOT NULL DEFAULT now(),
    tu_revision   integer NOT NULL,
    den_revision  integer NOT NULL,
    -- {khoá_ô: {gia_tri, nguon} | null} — null = ô chưa có trước đó / đã xoá.
    truoc         jsonb NOT NULL DEFAULT '{}'::jsonb,
    sau           jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_phieu_kham_lich_su_phieu
    ON public.phieu_kham_lich_su (phieu_id, sua_luc DESC);
CREATE INDEX IF NOT EXISTS ix_phieu_kham_lich_su_luot
    ON public.phieu_kham_lich_su (clinic_id, visit_id, sua_luc DESC);

COMMENT ON TABLE public.phieu_kham_lich_su IS
'Lịch sử sửa phiếu khám: ai, lúc nào, ô nào, trước → sau. Trigger ghi; cùng người trong 10 phút thì gộp (P4A, 25/09/2026).';

ALTER TABLE public.phieu_kham_lich_su ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS phieu_kham_lich_su_select_own_clinic ON public.phieu_kham_lich_su;
CREATE POLICY phieu_kham_lich_su_select_own_clinic ON public.phieu_kham_lich_su
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.phieu_kham_lich_su TO service_role;


CREATE OR REPLACE FUNCTION public.ghi_lich_su_phieu_kham()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    cu       jsonb := CASE WHEN TG_OP = 'INSERT' THEN '{}'::jsonb ELSE OLD.du_lieu END;
    doi_truoc jsonb := '{}'::jsonb;
    doi_sau   jsonb := '{}'::jsonb;
    k        text;
    mo       public.phieu_kham_lich_su%ROWTYPE;
    g_truoc  jsonb;
    g_sau    jsonb;
BEGIN
    -- Ô đổi = khoá có ở một trong hai bên mà giá trị khác nhau.
    FOR k IN
        SELECT key FROM jsonb_each(cu)
        UNION
        SELECT key FROM jsonb_each(NEW.du_lieu)
    LOOP
        IF (cu -> k) IS DISTINCT FROM (NEW.du_lieu -> k) THEN
            doi_truoc := doi_truoc || jsonb_build_object(k, cu -> k);
            doi_sau   := doi_sau   || jsonb_build_object(k, NEW.du_lieu -> k);
        END IF;
    END LOOP;
    IF doi_sau = '{}'::jsonb THEN
        RETURN NULL;
    END IF;

    SELECT * INTO mo
      FROM public.phieu_kham_lich_su
     WHERE phieu_id = NEW.id
     ORDER BY sua_luc DESC
     LIMIT 1;

    IF FOUND
       AND mo.sua_boi IS NOT DISTINCT FROM NEW.sua_boi
       AND mo.sua_luc > now() - interval '10 minutes' THEN
        -- Gộp: `truoc` giữ giá trị có từ trước (ô đã có trong dòng thì giữ),
        -- `sau` lấy mới nhất.
        g_truoc := doi_truoc || mo.truoc;
        g_sau   := mo.sau || doi_sau;
        -- Ô sửa rồi trả về như cũ → bỏ khỏi dòng.
        FOR k IN SELECT key FROM jsonb_each(g_sau) LOOP
            IF (g_truoc -> k) IS NOT DISTINCT FROM (g_sau -> k) THEN
                g_truoc := g_truoc - k;
                g_sau   := g_sau - k;
            END IF;
        END LOOP;
        IF g_sau = '{}'::jsonb THEN
            DELETE FROM public.phieu_kham_lich_su WHERE id = mo.id;
        ELSE
            UPDATE public.phieu_kham_lich_su
               SET truoc = g_truoc, sau = g_sau,
                   sua_luc = now(), den_revision = NEW.revision
             WHERE id = mo.id;
        END IF;
    ELSE
        INSERT INTO public.phieu_kham_lich_su
            (clinic_id, phieu_id, visit_id, form_id, sua_boi,
             tu_revision, den_revision, truoc, sau)
        VALUES
            (NEW.clinic_id, NEW.id, NEW.visit_id, NEW.form_id, NEW.sua_boi,
             CASE WHEN TG_OP = 'INSERT' THEN 0 ELSE OLD.revision END,
             NEW.revision, doi_truoc, doi_sau);
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_phieu_kham_lich_su ON public.phieu_kham_luot;
CREATE TRIGGER trg_phieu_kham_lich_su
    AFTER INSERT OR UPDATE OF du_lieu ON public.phieu_kham_luot
    FOR EACH ROW
    EXECUTE FUNCTION public.ghi_lich_su_phieu_kham();
