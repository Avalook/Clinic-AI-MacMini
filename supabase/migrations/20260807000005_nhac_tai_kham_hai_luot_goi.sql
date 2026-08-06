-- Nhắc tái khám: VIỆC CÓ THẬT, hai lượt gọi.
--
-- Luật Quang mô tả: bác sĩ hẹn bệnh nhân quay lại, hệ thống phải tự sinh việc
-- cho CSKH gọi HAI lần — lần một trước hẹn 5–7 ngày, lần hai vào sáng ngày hẹn.
--
-- HÔM NAY KHÔNG CÓ GÌ SINH RA VIỆC. Danh sách ở màn /nhac-tai-kham là một câu
-- SQL tính lại mỗi lần có người mở trang: không job, không cron, không trigger,
-- không một dòng nào trong database mang tên người phụ trách và hạn phải gọi.
-- Không ai mở trang thì không ai biết có người cần gọi; trưởng ca không đối
-- soát được cuối ngày; và "ai đã gọi lần một, ai còn thiếu lần hai" là câu
-- không trả lời được.
--
-- HAI LƯỢT LÀ HAI VIỆC KHÁC NHAU, KHÔNG PHẢI MỘT VIỆC GỌI HAI LẦN:
--
--   Lượt 1 — bác sĩ dặn quay lại ngày X, khách CHƯA đặt lịch.
--            Gọi trước 5–7 ngày, để MỜI ĐẶT LỊCH.
--   Lượt 2 — khách ĐÃ có lịch hẹn hôm nay.
--            Gọi buổi sáng, để NHẮC ĐI KHÁM.
--
-- Đó cũng đúng chỗ hệ thống đang hở: danh sách nhắc tái khám LOẠI BỎ người đã
-- có lịch hẹn, còn màn /cskh-tasks lại bắt đầu từ NGÀY MAI. Người đã nhận lời
-- và có hẹn hôm nay — nhóm cần nhắc nhất — không nằm trong màn nào cả.
--
-- VÌ SAO BẢNG RIÊNG, KHÔNG DÙNG `follow_up_case`:
-- bảng ấy đang được màn đối soát check-out đọc như "theo dõi sau khám" của một
-- bước khám cụ thể (qua `origin_work_item_id`). Nhét việc gọi nhắc vào đó sẽ
-- làm mục ④ của màn check-out hiện những dòng không thuộc về nó.

CREATE TABLE IF NOT EXISTS public.nhac_tai_kham (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id          uuid NOT NULL REFERENCES public.clinic (id)
                            ON DELETE RESTRICT,
    clinic_patient_id  uuid NOT NULL REFERENCES public.patient (clinic_patient_id)
                            ON DELETE RESTRICT,

    -- 1 = gọi trước hẹn 5–7 ngày, 2 = gọi sáng ngày hẹn.
    luot_goi           smallint NOT NULL,

    -- Ngày bệnh nhân được hẹn quay lại (lượt 1) hoặc ngày có lịch (lượt 2).
    ngay_hen           date NOT NULL,
    -- Ngày PHẢI GỌI. Lượt 1 = ngay_hen − 7; lượt 2 = chính ngay_hen.
    han_goi            date NOT NULL,

    -- Lượt 2 luôn gắn với một lịch hẹn; lượt 1 gắn với lượt khám đã sinh ra lời
    -- dặn tái khám. Không bắt buộc cả hai — nguồn có thể đã bị đóng lại.
    appointment_id     uuid REFERENCES public.appointment (id) ON DELETE SET NULL,
    nguon_visit_id     uuid REFERENCES public.visit (visit_id) ON DELETE SET NULL,

    trang_thai         text NOT NULL DEFAULT 'CHO_GOI',
    ket_qua            text,
    ghi_chu            text,
    nguoi_goi_staff_id uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    goi_luc            timestamptz,
    dong_luc           timestamptz,

    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT nhac_tai_kham_luot_check
        CHECK (luot_goi IN (1, 2)),
    CONSTRAINT nhac_tai_kham_trang_thai_check
        CHECK (trang_thai IN ('CHO_GOI', 'DA_GOI', 'KHONG_CAN')),
    -- Cùng bốn giá trị mà `cskh_log.ket_qua` canh (20260807000002) — hai bảng
    -- nói về cùng một cuộc gọi thì phải cùng một bộ từ.
    CONSTRAINT nhac_tai_kham_ket_qua_check
        CHECK (ket_qua IS NULL OR ket_qua IN
               ('DA_LIEN_HE', 'CHUA_NGHE_MAY', 'CAN_BAC_SI', 'TU_CHOI')),
    -- ĐÃ GỌI THÌ PHẢI BIẾT AI GỌI, LÚC NÀO, KẾT QUẢ RA SAO — và ngược lại.
    -- Ràng buộc hai chiều: nó chặn được cả "ghi đã gọi mà trống dấu vết" lẫn
    -- "có dấu vết mà trạng thái vẫn chờ gọi".
    CONSTRAINT nhac_tai_kham_goi_thi_co_dau_vet
        CHECK ((trang_thai = 'DA_GOI')
               = (goi_luc IS NOT NULL
                  AND nguoi_goi_staff_id IS NOT NULL
                  AND ket_qua IS NOT NULL)),
    CONSTRAINT nhac_tai_kham_dong_khi_ket_thuc
        CHECK ((trang_thai IN ('DA_GOI', 'KHONG_CAN'))
               = (dong_luc IS NOT NULL)),
    CONSTRAINT nhac_tai_kham_luot2_can_lich
        CHECK (luot_goi <> 2 OR appointment_id IS NOT NULL)
);

-- SINH VIỆC PHẢI LẶP LẠI ĐƯỢC MÀ KHÔNG ĐẺ THÊM. Khoá này là thứ cho phép chạy
-- hàm sinh việc mười lần một ngày mà vẫn ra đúng một việc cho mỗi người, mỗi
-- ngày hẹn, mỗi lượt.
CREATE UNIQUE INDEX IF NOT EXISTS uq_nhac_tai_kham_viec
    ON public.nhac_tai_kham (clinic_id, clinic_patient_id, ngay_hen, luot_goi);

-- Câu hỏi của mỗi buổi sáng: "hôm nay phải gọi ai".
CREATE INDEX IF NOT EXISTS idx_nhac_tai_kham_hang_doi
    ON public.nhac_tai_kham (clinic_id, trang_thai, han_goi);

COMMENT ON TABLE public.nhac_tai_kham IS
    'Việc gọi nhắc tái khám. Hai lượt: 1 = trước hẹn 5–7 ngày (mời đặt lịch), '
    '2 = sáng ngày hẹn (nhắc đi khám). Sinh bằng sinh_viec_nhac_tai_kham() '
    '(20260807000005).';

ALTER TABLE public.nhac_tai_kham ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE tablename = 'nhac_tai_kham'
           AND policyname = 'nhac_tai_kham_select_own_clinic'
    ) THEN
        -- ĐỌC theo phòng khám, GHI đi qua FastAPI (service_role) như mọi bảng
        -- nghiệp vụ khác trong dự án này.
        CREATE POLICY nhac_tai_kham_select_own_clinic
            ON public.nhac_tai_kham FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

GRANT SELECT ON public.nhac_tai_kham TO authenticated;
GRANT ALL ON public.nhac_tai_kham TO service_role;

-- ---------------------------------------------------------------------------
-- Sinh việc — chạy lại bao nhiêu lần cũng như một
-- ---------------------------------------------------------------------------
-- Trả về số việc MỚI tạo của từng lượt. Gọi được từ endpoint, từ cron, hoặc
-- ngay lúc CSKH mở màn hình. Chưa có bộ hẹn giờ nào trong dự án, nên đường
-- chắc chắn nhất hôm nay là mở màn hình — và hàm này viết sao cho ngày mai cắm
-- cron vào không phải đổi gì.

CREATE OR REPLACE FUNCTION public.sinh_viec_nhac_tai_kham(
    p_clinic_id uuid,
    p_ngay      date DEFAULT NULL
)
RETURNS TABLE (luot1_moi integer, luot2_moi integer)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_ngay  date;
    v_l1    integer;
    v_l2    integer;
BEGIN
    v_ngay := coalesce(p_ngay,
                       (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date);

    -- ── LƯỢT 1 — bác sĩ dặn quay lại, khách chưa đặt lịch ──────────────────
    --
    -- Cửa sổ: ngày tái khám còn TỪ 0 TỚI 7 ngày nữa. Cận trên là 7 (đúng luật
    -- "gọi trước 5–7 ngày"); cận dưới là 0 chứ không phải 5, vì một việc chỉ
    -- sinh ra trong ba ngày rồi biến mất là một việc sẽ bị bỏ lỡ. Việc sinh
    -- sớm nhất có thể, `han_goi` nói ngày nên gọi, và nó nằm đó tới khi có
    -- người đóng.
    WITH benh_an AS (
        SELECT DISTINCT ON (v.clinic_patient_id)
               v.clinic_patient_id,
               v.visit_id,
               (cr.soap_plan #>> '{tai_kham,ngay}') AS ngay_text
          FROM public.visit v
          JOIN public.clinical_record cr
            ON cr.visit_id = v.visit_id AND cr.clinic_id = v.clinic_id
         WHERE v.clinic_id = p_clinic_id
           AND v.status IN ('FINALIZED', 'AMENDED')
           AND v.created_at >= (v_ngay - 183)::timestamptz
         ORDER BY v.clinic_patient_id, v.created_at DESC
    ),
    can_goi AS (
        SELECT b.clinic_patient_id,
               b.visit_id,
               b.ngay_text::date AS ngay_hen
          FROM benh_an b
         WHERE b.ngay_text ~ '^\d{4}-\d{2}-\d{2}$'
           AND b.ngay_text::date BETWEEN v_ngay AND v_ngay + 7
           -- Đã đặt lịch rồi thì không cần mời đặt nữa — lượt 2 sẽ lo họ.
           AND NOT EXISTS (
               SELECT 1 FROM public.appointment a
                WHERE a.clinic_id = p_clinic_id
                  AND a.clinic_patient_id = b.clinic_patient_id
                  AND a.slot_start >= v_ngay::timestamptz
                  AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED',
                                   'CONFIRMED', 'CHECKED_IN')
           )
    ),
    them1 AS (
        INSERT INTO public.nhac_tai_kham
            (clinic_id, clinic_patient_id, luot_goi, ngay_hen, han_goi,
             nguon_visit_id)
        SELECT p_clinic_id, c.clinic_patient_id, 1, c.ngay_hen,
               c.ngay_hen - 7, c.visit_id
          FROM can_goi c
        ON CONFLICT (clinic_id, clinic_patient_id, ngay_hen, luot_goi)
        DO NOTHING
        RETURNING 1
    )
    SELECT count(*)::integer INTO v_l1 FROM them1;

    -- ── LƯỢT 2 — đã có lịch hẹn HÔM NAY ────────────────────────────────────
    --
    -- Đây là nhóm không màn nào đang hiện: danh sách nhắc tái khám loại bỏ
    -- người đã đặt lịch, còn màn nhiệm vụ CSKH bắt đầu từ ngày mai.
    WITH lich_hom_nay AS (
        SELECT a.id, a.clinic_patient_id,
               (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay_hen
          FROM public.appointment a
         WHERE a.clinic_id = p_clinic_id
           AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = v_ngay
           AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
    ),
    them2 AS (
        INSERT INTO public.nhac_tai_kham
            (clinic_id, clinic_patient_id, luot_goi, ngay_hen, han_goi,
             appointment_id)
        SELECT p_clinic_id, l.clinic_patient_id, 2, l.ngay_hen, l.ngay_hen, l.id
          FROM lich_hom_nay l
        ON CONFLICT (clinic_id, clinic_patient_id, ngay_hen, luot_goi)
        DO NOTHING
        RETURNING 1
    )
    SELECT count(*)::integer INTO v_l2 FROM them2;

    RETURN QUERY SELECT v_l1, v_l2;
END;
$function$;

COMMENT ON FUNCTION public.sinh_viec_nhac_tai_kham(uuid, date) IS
    'Sinh việc gọi nhắc tái khám cho một ngày. Chạy lại bao nhiêu lần cũng ra '
    'cùng kết quả (ON CONFLICT DO NOTHING trên uq_nhac_tai_kham_viec).';

REVOKE ALL ON FUNCTION public.sinh_viec_nhac_tai_kham(uuid, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.sinh_viec_nhac_tai_kham(uuid, date)
    TO service_role;
