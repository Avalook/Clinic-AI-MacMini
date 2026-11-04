-- Ô phụ tá chọn sẵn nó hỗ trợ Ô BÁC SĨ nào (Tuyền chốt 04/11/2026).
--
-- "Nhân viên đi theo bác sĩ là làm cho bác sĩ đó": điều dưỡng / thư ký (hoặc bất
-- kỳ ai) được xếp vào ô phụ tá thì mọi chỉ định họ bấm tính cho bác sĩ đang đứng
-- ô bác sĩ mà ô ấy hỗ trợ, cùng ngày cùng ca — không còn ô chọn bác sĩ ở phòng.
-- Thay cho `lan` (20261001250000): làn chỉ ghi được bằng migration, không màn nào
-- đặt, nên tầng 4 Hào Nam chưa từng ghép được (đo prod 03/11: 0 lần).
--
-- Bất biến ép ở Postgres (SO-LUAT Phần 6): ô được hỗ trợ phải là ô BÁC SĨ đang
-- dùng, CÙNG phòng; ô bác sĩ không hỗ trợ ai. Ô bác sĩ đổi nhóm / đổi phòng / tắt
-- → các ô phụ tá của nó thành "chưa gắn" (không chặn người sửa).

ALTER TABLE public.vi_tri_lam_viec
    ADD COLUMN IF NOT EXISTS ho_tro_code text;

COMMENT ON COLUMN public.vi_tri_lam_viec.ho_tro_code IS
    'Ô phụ tá: mã ô BÁC SĨ cùng phòng mà ô này hỗ trợ. NULL = ô bác sĩ, hoặc ô nhân viên không đi theo bác sĩ nào.';

ALTER TABLE public.vi_tri_lam_viec
    DROP CONSTRAINT IF EXISTS vi_tri_ho_tro_fk;
ALTER TABLE public.vi_tri_lam_viec
    ADD CONSTRAINT vi_tri_ho_tro_fk
    FOREIGN KEY (clinic_id, ho_tro_code)
    REFERENCES public.vi_tri_lam_viec (clinic_id, code)
    ON UPDATE CASCADE;

CREATE OR REPLACE FUNCTION public.vi_tri_kiem_ho_tro()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
DECLARE
    dich record;
BEGIN
    IF NEW.nhom_nghe = 'BAC_SI' THEN
        NEW.ho_tro_code := NULL;
        RETURN NEW;
    END IF;
    -- Ô phụ tá chuyển phòng mà không chọn lại → bỏ gắn (ô bác sĩ cũ ở phòng khác).
    IF TG_OP = 'UPDATE'
       AND NEW.room_id IS DISTINCT FROM OLD.room_id
       AND NEW.ho_tro_code IS NOT DISTINCT FROM OLD.ho_tro_code THEN
        NEW.ho_tro_code := NULL;
    END IF;
    -- Chỉ kiểm khi ô hỗ trợ VỪA được đặt / đổi: tắt hàng loạt (ô bác sĩ tắt
    -- trước ô phụ tá trong cùng một lệnh) không bị chặn — ô phụ tá của ô bác
    -- sĩ vừa tắt được trigger AFTER bên dưới bỏ gắn.
    IF NEW.ho_tro_code IS NULL
       OR (TG_OP = 'UPDATE' AND NEW.ho_tro_code IS NOT DISTINCT FROM OLD.ho_tro_code) THEN
        RETURN NEW;
    END IF;
    SELECT code, nhom_nghe, room_id, is_active INTO dich
      FROM public.vi_tri_lam_viec
     WHERE clinic_id = NEW.clinic_id AND code = NEW.ho_tro_code;
    IF NOT FOUND OR dich.nhom_nghe <> 'BAC_SI' OR NOT dich.is_active
       OR NEW.room_id IS NULL OR dich.room_id IS DISTINCT FROM NEW.room_id THEN
        RAISE EXCEPTION 'Ô phụ tá chỉ hỗ trợ được một ô bác sĩ đang dùng, cùng phòng.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_vi_tri_kiem_ho_tro ON public.vi_tri_lam_viec;
CREATE TRIGGER trg_vi_tri_kiem_ho_tro
    BEFORE INSERT OR UPDATE ON public.vi_tri_lam_viec
    FOR EACH ROW EXECUTE FUNCTION public.vi_tri_kiem_ho_tro();

CREATE OR REPLACE FUNCTION public.vi_tri_bo_ho_tro_khi_doi_bac_si()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    IF OLD.nhom_nghe = 'BAC_SI'
       AND (NEW.nhom_nghe <> 'BAC_SI' OR NOT NEW.is_active
            OR NEW.room_id IS DISTINCT FROM OLD.room_id) THEN
        UPDATE public.vi_tri_lam_viec
           SET ho_tro_code = NULL
         WHERE clinic_id = NEW.clinic_id AND ho_tro_code = NEW.code;
    END IF;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_vi_tri_bo_ho_tro ON public.vi_tri_lam_viec;
CREATE TRIGGER trg_vi_tri_bo_ho_tro
    AFTER UPDATE OF nhom_nghe, is_active, room_id ON public.vi_tri_lam_viec
    FOR EACH ROW EXECUTE FUNCTION public.vi_tri_bo_ho_tro_khi_doi_bac_si();

-- Hàng "Bs siêu âm 3" tầng 4 Hào Nam tạo nhầm nhóm Điều dưỡng (prod 03/11): BS
-- Tiến đứng đó không được coi là bác sĩ. Sửa trước khi ghép sẵn bên dưới.
UPDATE public.vi_tri_lam_viec
   SET nhom_nghe = 'BAC_SI'
 WHERE code = 'VT-7f0233c1' AND ten = 'Bs siêu âm 3' AND nhom_nghe = 'DIEU_DUONG';

-- Ghép sẵn cho phòng khám / phòng dịch vụ đang dùng: cùng làn (đúng một ô bác
-- sĩ) → ô ấy; không thì ô bác sĩ gần nhất PHÍA TRÊN theo thứ tự lịch; không có
-- thì ô bác sĩ duy nhất của phòng. Phòng không có bác sĩ (quầy, thu ngân, hỏi
-- bệnh…) để trống — đó là ô nhân viên. Diễn tập trên bản sao prod 04/11: 24 ô.
WITH bs AS (
    SELECT v.clinic_id, v.code, v.room_id, v.lan, v.sort
      FROM public.vi_tri_lam_viec v
     WHERE v.is_active AND v.nhom_nghe = 'BAC_SI' AND v.room_id IS NOT NULL
), pt AS (
    SELECT v.id, v.clinic_id, v.room_id, v.lan, v.sort
      FROM public.vi_tri_lam_viec v
      JOIN public.clinic_room r ON r.id = v.room_id AND r.is_active
     WHERE v.is_active AND v.nhom_nghe <> 'BAC_SI' AND v.ho_tro_code IS NULL
       AND (r.node_code LIKE 'KHAM-%' OR r.node_code LIKE 'DICHVU-%')
), ghep AS (
    SELECT pt.id,
           coalesce(
               (SELECT min(b.code) FROM bs b
                 WHERE b.clinic_id = pt.clinic_id AND b.room_id = pt.room_id
                   AND pt.lan IS NOT NULL AND b.lan = pt.lan
                HAVING count(*) = 1),
               (SELECT b.code FROM bs b
                 WHERE b.clinic_id = pt.clinic_id AND b.room_id = pt.room_id
                   AND b.sort <= pt.sort
                 ORDER BY b.sort DESC, b.code DESC LIMIT 1),
               (SELECT min(b.code) FROM bs b
                 WHERE b.clinic_id = pt.clinic_id AND b.room_id = pt.room_id
                HAVING count(*) = 1)
           ) AS ho_tro
      FROM pt
)
UPDATE public.vi_tri_lam_viec v
   SET ho_tro_code = g.ho_tro
  FROM ghep g
 WHERE v.id = g.id AND g.ho_tro IS NOT NULL;
