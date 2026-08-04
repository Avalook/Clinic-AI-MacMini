-- KÝ BỆNH ÁN, CHO PHÉP GỬI, VÀ ĐÍNH CHÍNH — ba việc, ba trạng thái, một chiều.
--
-- Quyết định của Quang (2026-08-04), trả lời ba câu hỏi trước khi viết:
--   1. CHỈ BÁC SĨ được ký. Bác sĩ siêu âm ký kết quả siêu âm CỦA MÌNH, không ký
--      bệnh án khám. Thư ký Y khoa nhập hộ được nhưng KHÔNG đứng tên ký.
--   2. KÝ và CHO PHÉP GỬI là HAI BƯỚC. Lý do của Quang: bệnh án nguy hiểm thì
--      phải cảnh báo CSKH chưa được gửi — nên bác sĩ ký xong vẫn còn một nút
--      nữa mới mở đường cho CSKH.
--   3. Đính chính bản ĐÃ GỬI thì tạo việc thông báo lại cho CSKH. Làm luôn.
--
-- Danh mục node đã mô tả đúng hai bước này từ trước:
--   THEODOI-02  Duyệt nội dung/kết quả được phép trả   (DOCTOR)
--   THEODOI-03  Thông báo người bệnh                    (CSKH)
--
-- VÌ SAO "CHO PHÉP GỬI" PHẢI LÀ MỘT BẢNG RIÊNG, KHÔNG PHẢI MỘT CỘT TRÊN visit.
--
-- Trigger `visit_finalized_block_update` chặn MỌI update lên `visit` sau khi
-- status = FINALIZED, trừ đúng đường FINALIZED → AMENDED. Đó là khoá hồ sơ theo
-- TT13/2011/TT-BYT và nó đúng. Nhưng nó cũng có nghĩa là sau khi bác sĩ ký,
-- KHÔNG cột nào trên `visit` ghi được nữa — kể cả một cột "đã cho phép gửi".
--
-- Nên bước thứ hai sống ở bảng riêng. Nó cũng đúng về mặt ý nghĩa: chữ ký là
-- hành vi chuyên môn (thuộc bệnh án), còn cho phép gửi là hành vi truyền thông
-- (thuộc quy trình) — hai thứ có thể thu hồi độc lập.

-- ---------------------------------------------------------------------------
-- 1. Cho phép gửi kết quả cho bệnh nhân
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.clinical_release (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id      uuid NOT NULL,
    released_by   uuid NOT NULL,
    released_at   timestamptz NOT NULL DEFAULT now(),
    note          text,
    -- Thu hồi khi hồ sơ bị đính chính. Append-only: không xoá dòng cũ, vì
    -- "đã từng cho phép gửi" là một sự thật đã xảy ra, và nếu bản cũ đã tới tay
    -- bệnh nhân thì việc thu hồi KHÔNG làm điều đó chưa từng xảy ra.
    revoked_at    timestamptz,
    revoked_by    uuid,
    revoke_reason text,
    CONSTRAINT clinical_release_revoke_needs_reason
        CHECK (revoked_at IS NULL
               OR nullif(btrim(coalesce(revoke_reason, '')), '') IS NOT NULL)
);

COMMENT ON TABLE public.clinical_release IS
    'Bác sĩ CHO PHÉP gửi kết quả cho bệnh nhân — bước hai, sau khi ký. Bảng '
    'riêng vì visit bị khoá sau FINALIZED. Append-only: thu hồi = ghi '
    'revoked_at, không xoá.';

CREATE INDEX IF NOT EXISTS idx_clinical_release_visit
    ON public.clinical_release (clinic_id, visit_id) WHERE revoked_at IS NULL;

-- Mỗi lượt khám chỉ có MỘT lần cho phép đang hiệu lực. Hai dòng cùng lúc nghĩa
-- là không ai biết bản nào được phép gửi.
CREATE UNIQUE INDEX IF NOT EXISTS uq_clinical_release_active
    ON public.clinical_release (visit_id) WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------------------
-- 2. Chữ ký cho kết quả siêu âm
-- ---------------------------------------------------------------------------
-- Bác sĩ siêu âm ký kết quả của mình. Đây là một đối tượng KHÁC bệnh án khám:
-- một lượt khám có thể có bệnh án do bác sĩ A ký và kết quả siêu âm do bác sĩ B
-- ký, và trộn hai chữ ký làm một sẽ ghi sai người chịu trách nhiệm chuyên môn.

ALTER TABLE public.ultrasound_record
    ADD COLUMN IF NOT EXISTS signed_by uuid REFERENCES public.staff(id),
    ADD COLUMN IF NOT EXISTS signed_at timestamptz;

COMMENT ON COLUMN public.ultrasound_record.signed_by IS
    'Bác sĩ siêu âm đã ký kết quả này. NULL = còn là bản nháp.';

ALTER TABLE public.ultrasound_record
    DROP CONSTRAINT IF EXISTS ultrasound_signed_pair;
ALTER TABLE public.ultrasound_record
    ADD CONSTRAINT ultrasound_signed_pair
    CHECK ((signed_by IS NULL) = (signed_at IS NULL));

-- Đã ký thì không sửa đè — cùng nguyên tắc với bệnh án. Muốn sửa thì đính chính.
CREATE OR REPLACE FUNCTION public.ultrasound_signed_block_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
    IF OLD.signed_at IS NOT NULL
       AND (NEW.findings   IS DISTINCT FROM OLD.findings
         OR NEW.impression IS DISTINCT FROM OLD.impression
         OR NEW.image_refs IS DISTINCT FROM OLD.image_refs)
    THEN
        RAISE EXCEPTION
            'Kết quả siêu âm % đã ký — sửa nội dung phải qua đường đính chính',
            OLD.ultrasound_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_ultrasound_signed_lock ON public.ultrasound_record;
CREATE TRIGGER trg_ultrasound_signed_lock
    BEFORE UPDATE ON public.ultrasound_record
    FOR EACH ROW EXECUTE FUNCTION public.ultrasound_signed_block_update();

-- ---------------------------------------------------------------------------
-- 3. Trạng thái hồ sơ, đọc được bằng một truy vấn
-- ---------------------------------------------------------------------------
-- Bốn trạng thái mà giao diện bác sĩ cần phân biệt, và chúng nằm rải ở ba chỗ
-- (visit.status, clinical_release, visit_amendment). View này gom lại để không
-- màn hình nào phải tự ghép — ghép sai một lần là một kết quả bị gửi sớm.

CREATE OR REPLACE VIEW public.v_clinical_status
WITH (security_invoker = true) AS
SELECT v.visit_id,
       v.clinic_id,
       v.clinic_patient_id,
       v.status                          AS visit_status,
       v.finalized_at,
       v.finalized_by,
       s.full_name                       AS signed_by_name,
       rel.released_at,
       rel.released_by,
       relstaff.full_name                AS released_by_name,
       -- Số lần đính chính. Bản đầu là 1; mỗi lần đính chính thêm một.
       1 + coalesce(am.n, 0)             AS version,
       am.last_at                        AS last_amended_at,
       CASE
         WHEN v.status = 'AMENDED'                  THEN 'AMENDED'
         WHEN rel.released_at IS NOT NULL           THEN 'RELEASED'
         WHEN v.status = 'FINALIZED'                THEN 'SIGNED'
         ELSE 'DRAFT'
       END                               AS clinical_state
  FROM public.visit v
  LEFT JOIN public.staff s ON s.id = v.finalized_by
  LEFT JOIN LATERAL (
      SELECT r.released_at, r.released_by
        FROM public.clinical_release r
       WHERE r.visit_id = v.visit_id AND r.revoked_at IS NULL
       LIMIT 1
  ) rel ON TRUE
  LEFT JOIN public.staff relstaff ON relstaff.id = rel.released_by
  LEFT JOIN LATERAL (
      SELECT count(*) AS n, max(a.amended_at) AS last_at
        FROM public.visit_amendment a
       WHERE a.visit_id = v.visit_id
  ) am ON TRUE;

COMMENT ON VIEW public.v_clinical_status IS
    'DRAFT → SIGNED → RELEASED, và AMENDED khi đã đính chính. Gom từ ba nguồn '
    '(visit.status, clinical_release, visit_amendment) để không màn hình nào '
    'phải tự ghép — ghép sai một lần là một kết quả bị gửi sớm.';

GRANT SELECT ON public.v_clinical_status TO authenticated;

-- ---------------------------------------------------------------------------
-- 4. RLS
-- ---------------------------------------------------------------------------

ALTER TABLE public.clinical_release ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clinical_release_select ON public.clinical_release;
CREATE POLICY clinical_release_select ON public.clinical_release
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- CHỈ BÁC SĨ được cho phép gửi. Quyết định của Quang: "chỉ bác sĩ được ký vì
-- bác sĩ làm mà". Quản lý KHÔNG có trong danh sách này — đây là trách nhiệm
-- chuyên môn, không phải quyền hành chính.
DROP POLICY IF EXISTS clinical_release_write ON public.clinical_release;
CREATE POLICY clinical_release_write ON public.clinical_release
    FOR ALL TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['DOCTOR', 'ULTRASOUND_DOCTOR'])))
    WITH CHECK (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['DOCTOR', 'ULTRASOUND_DOCTOR'])));

GRANT SELECT ON public.clinical_release TO authenticated;
GRANT INSERT, UPDATE ON public.clinical_release TO authenticated;

DO $verify$
BEGIN
    PERFORM 1 FROM public.v_clinical_status LIMIT 1;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'ultrasound_record'
                      AND column_name = 'signed_by') THEN
        RAISE EXCEPTION 'ultrasound_record.signed_by chưa được thêm';
    END IF;
    RAISE NOTICE 'ký / cho phép gửi / đính chính: schema sẵn sàng';
END
$verify$;
