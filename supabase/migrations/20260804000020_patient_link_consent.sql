-- ĐỒNG Ý CHIA SẺ HỒ SƠ GIỮA HAI BỆNH NHÂN — cho MỌI dịch vụ khám.
--
-- docs/spec-form-nam-khoa.md §6.5 nêu vấn đề ở bối cảnh hiếm muộn: hồ sơ nam
-- khoa thuộc người chồng, nhưng luồng HMVS nhìn cả hai vợ chồng. Quang yêu cầu
-- làm đủ cho tất cả dịch vụ khám, không riêng nam khoa — và đúng là như vậy:
-- cùng câu hỏi xuất hiện với sản khoa (tiền sử di truyền của chồng), với nội
-- tiết, với bất kỳ hồ sơ nào của người này được đọc trong buổi khám người kia.
--
-- MỘT ĐIỂM PHẢI NÓI RÕ VÌ NÓ ĐỔI CẢ CÁCH LÀM.
--
-- Spec viết "RLS phải chặn vợ đọc hồ sơ NK". Rà lại thì tiền đề đó KHÔNG đúng
-- với hệ thống hôm nay: `auth.users` có 0 tài khoản không phải nhân viên —
-- BỆNH NHÂN KHÔNG ĐĂNG NHẬP. `authenticated` trong mọi policy hiện tại nghĩa
-- là NHÂN VIÊN phòng khám.
--
-- Nên rủi ro thật không phải "vợ đọc trộm", mà là: khi bác sĩ mở hồ sơ hiếm
-- muộn của người vợ, hệ thống có tự kéo dữ liệu nam khoa của người chồng vào
-- màn hình đó không — và có in nó lên phiếu kết quả của người vợ không. Đó là
-- việc của TẦNG ỨNG DỤNG khi ghép dữ liệu, không phải của RLS.
--
-- Hai bảng dưới đây là thứ tầng ứng dụng phải hỏi trước khi ghép.

-- ---------------------------------------------------------------------------
-- 1. Liên kết hai bệnh nhân
-- ---------------------------------------------------------------------------
-- Chưa có liên kết nào trong hệ thống — không cột partner/spouse/couple nào tồn
-- tại. Đồng ý mà không có liên kết thì không nói được "đồng ý cho AI xem".

CREATE TABLE IF NOT EXISTS public.patient_link (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    patient_a  uuid NOT NULL,
    patient_b  uuid NOT NULL,
    relation   text NOT NULL,
    created_by uuid NOT NULL REFERENCES public.staff(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    note       text,
    CONSTRAINT patient_link_relation
        CHECK (relation IN ('SPOUSE', 'PARTNER', 'FAMILY')),
    -- Một người không liên kết với chính mình.
    CONSTRAINT patient_link_two_people CHECK (patient_a <> patient_b)
);

-- Liên kết ĐỐI XỨNG, lưu MỘT dòng. Chuẩn hoá thứ tự bằng least/greatest để
-- (A,B) và (B,A) không thành hai dòng nói cùng một điều — hai dòng thì gỡ một
-- cái vẫn còn cái kia, và "đã gỡ liên kết" trở thành nửa đúng.
CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_link_pair
    ON public.patient_link (clinic_id, least(patient_a, patient_b),
                            greatest(patient_a, patient_b));

COMMENT ON TABLE public.patient_link IS
    'Hai bệnh nhân có quan hệ (vợ/chồng, bạn đời, gia đình). Đối xứng, lưu một '
    'dòng. Chỉ là LIÊN KẾT — không tự cho phép đọc hồ sơ của nhau.';

-- ---------------------------------------------------------------------------
-- 2. Đồng ý chia sẻ
-- ---------------------------------------------------------------------------
-- LIÊN KẾT KHÔNG PHẢI ĐỒNG Ý. Hai vợ chồng cùng đi khám hiếm muộn vẫn là hai
-- người bệnh với hai hồ sơ riêng; chồng có quyền không cho vợ biết kết quả tinh
-- dịch đồ, và hệ thống phải giữ được quyền đó.

CREATE TABLE IF NOT EXISTS public.clinical_data_consent (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    --: Hồ sơ của AI được chia sẻ.
    subject_patient_id uuid NOT NULL,
    --: Chia sẻ cho AI xem (một bệnh nhân khác, đã có patient_link).
    grantee_patient_id uuid NOT NULL,
    --: Mã form được chia sẻ, hoặc 'ALL'. Danh sách chứ không phải một cờ: chồng
    --: có thể cho vợ xem hồ sơ hiếm muộn chung mà không cho xem hồ sơ nam khoa.
    form_codes    text[] NOT NULL,
    granted_at    timestamptz NOT NULL DEFAULT now(),
    granted_by_staff_id uuid NOT NULL REFERENCES public.staff(id),
    --: Bằng chứng ngoài hệ thống: bản đồng ý có chữ ký. Không có nó thì "đã
    --: đồng ý" chỉ là một dòng trong database do nhân viên tự gõ.
    source_document text NOT NULL,
    --: Thu hồi được, và thu hồi là GHI THÊM chứ không xoá — "đã từng đồng ý"
    --: là một sự thật đã xảy ra, và nếu dữ liệu đã được đọc thì việc thu hồi
    --: không làm điều đó chưa từng xảy ra.
    revoked_at    timestamptz,
    revoked_by    uuid REFERENCES public.staff(id),
    revoke_reason text,
    CONSTRAINT clinical_data_consent_two_people
        CHECK (subject_patient_id <> grantee_patient_id),
    CONSTRAINT clinical_data_consent_has_scope
        CHECK (array_length(form_codes, 1) >= 1),
    CONSTRAINT clinical_data_consent_doc_not_blank
        CHECK (btrim(source_document) <> ''),
    CONSTRAINT clinical_data_consent_revoke_needs_reason
        CHECK (revoked_at IS NULL
               OR nullif(btrim(coalesce(revoke_reason, '')), '') IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_clinical_data_consent_live
    ON public.clinical_data_consent
       (clinic_id, subject_patient_id, grantee_patient_id)
    WHERE revoked_at IS NULL;

COMMENT ON TABLE public.clinical_data_consent IS
    'Bệnh nhân A đồng ý cho bệnh nhân B xem những form nào của mình. Áp cho MỌI '
    'dịch vụ khám, không riêng nam khoa. Liên kết (patient_link) KHÔNG tự cho '
    'phép đọc — phải có dòng ở đây.';

-- Một cặp chỉ có MỘT đồng ý đang hiệu lực. Hai dòng cùng lúc nghĩa là không ai
-- biết phạm vi nào đang áp.
CREATE UNIQUE INDEX IF NOT EXISTS uq_clinical_data_consent_active
    ON public.clinical_data_consent (subject_patient_id, grantee_patient_id)
    WHERE revoked_at IS NULL;

-- Đồng ý chỉ có nghĩa khi hai người ĐÃ được liên kết. Không có liên kết mà vẫn
-- ghi đồng ý là mở đường chia sẻ hồ sơ cho một người lạ.
CREATE OR REPLACE FUNCTION public.clinical_data_consent_needs_link()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.patient_link l
         WHERE l.clinic_id = NEW.clinic_id
           AND least(l.patient_a, l.patient_b)
               = least(NEW.subject_patient_id, NEW.grantee_patient_id)
           AND greatest(l.patient_a, l.patient_b)
               = greatest(NEW.subject_patient_id, NEW.grantee_patient_id)
    ) THEN
        RAISE EXCEPTION
            'Hai bệnh nhân này chưa được liên kết — tạo patient_link trước khi '
            'ghi đồng ý chia sẻ.'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_clinical_data_consent_link
    ON public.clinical_data_consent;
CREATE TRIGGER trg_clinical_data_consent_link
    BEFORE INSERT OR UPDATE OF subject_patient_id, grantee_patient_id
    ON public.clinical_data_consent
    FOR EACH ROW EXECUTE FUNCTION public.clinical_data_consent_needs_link();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE public.patient_link ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinical_data_consent ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS patient_link_select ON public.patient_link;
CREATE POLICY patient_link_select ON public.patient_link
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- Bản đồng ý chỉ vai LÂM SÀNG đọc — nó nói ai được xem hồ sơ của ai, và bản
-- thân nó là thông tin nhạy cảm.
DROP POLICY IF EXISTS clinical_data_consent_select ON public.clinical_data_consent;
CREATE POLICY clinical_data_consent_select ON public.clinical_data_consent
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinical_clinic_ids()));

GRANT SELECT ON public.patient_link TO authenticated;
GRANT SELECT ON public.clinical_data_consent TO authenticated;

DO $verify$
BEGIN
    PERFORM 1 FROM public.patient_link LIMIT 1;
    PERFORM 1 FROM public.clinical_data_consent LIMIT 1;
    RAISE NOTICE
        'liên kết + đồng ý chia sẻ: schema sẵn sàng (chưa có liên kết nào)';
END
$verify$;
