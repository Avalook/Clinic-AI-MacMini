-- Luật "dịch vụ này, khách mới thì phải khám bác sĩ kia".
--
-- YÊU CẦU GỐC (Dr4Women): nội tiết và hiếm muộn/vô sinh — mọi khách MỚI của
-- dịch vụ đó phải qua BS Thành khám lần đầu. Sản khoa, nam khoa, phụ khoa thì
-- không bắt buộc.
--
-- KHÔNG GHI CỨNG TÊN AI. Quang chốt: quản lý tự thiết lập, để phòng khám khác
-- dùng hệ thống này cũng khai được luật của họ. Đã có một lần seed ghi cứng
-- `full_name = 'TS.BS. Phan Chí Thành'` (20260805000006) — nó khớp 0 dòng ở
-- mọi nơi kể cả chính Dr4Women, vì lúc migration chạy tên trong database còn
-- là 'BS Thành'. Luật ghi theo tên người là luật sẽ im lặng biến mất.
--
-- VÌ SAO KHÔNG DÙNG LẠI `visit_gate_rule`.
--
-- Bảng ấy có đúng ba ô cần (service_type_id, patient_kind, required_staff_id)
-- nên nhìn qua rất giống. Nhưng nó là luật ĐIỀU PHỐI: thi hành lúc chuyển
-- phòng, và mang theo blocked_node_codes / required_node_codes /
-- only_when_other_staff — ba cột vô nghĩa ở thời điểm CSKH đang chọn bác sĩ
-- trên điện thoại. Nhét hai thời điểm thi hành vào một bảng nghĩa là một nửa
-- số cột luôn rỗng, và người đọc sau không biết dòng nào dành cho ai.
--
-- Quan trọng hơn: `visit_gate_rule` chặn SAU KHI khách đã tới phòng khám. Yêu
-- cầu ở đây là chặn LÚC ĐẶT LỊCH — sớm hơn hẳn, và đó mới là lúc sửa được mà
-- không ai phải đi về.

CREATE TABLE IF NOT EXISTS public.luat_bac_si_bat_buoc (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    service_type_id   uuid NOT NULL REFERENCES public.service_type(id) ON DELETE CASCADE,
    required_staff_id uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,

    -- CÁCH TÍNH "KHÁCH MỚI" — do quản lý chọn, không phải tôi quyết.
    --
    --   CHUA_TUNG   chưa từng khám xong dịch vụ này lần nào. Chặt nhất.
    --   DOT_MOI     không có đợt chăm sóc đang mở của dịch vụ này. Mặc định.
    --               Hợp với cách phòng khám nghĩ: cùng một dịch vụ nhưng VẤN ĐỀ
    --               khác thì là một chặng chăm sóc mới, và `care_episode` đã mô
    --               hình hoá đúng điều đó (kể cả lý do đóng 'new_problem').
    --   QUA_N_THANG chưa khám dịch vụ này trong `so_thang` tháng gần đây.
    --
    -- Ba cách cho ba câu trả lời khác nhau với cùng một người: chị đã khám nội
    -- tiết năm ngoái, đợt đã đóng, nay quay lại. CHUA_TUNG nói "cũ", DOT_MOI
    -- nói "mới", QUA_N_THANG tuỳ con số. Không có đáp án đúng phổ quát — nên
    -- nó là cấu hình, không phải hằng số.
    cach_tinh        text NOT NULL DEFAULT 'DOT_MOI'
                     CHECK (cach_tinh IN ('CHUA_TUNG', 'DOT_MOI', 'QUA_N_THANG')),
    so_thang         integer CHECK (so_thang IS NULL OR (so_thang BETWEEN 1 AND 120)),

    -- CHẶN hay chỉ CẢNH BÁO. Phòng khám mới bật luật lần đầu thường muốn nhìn
    -- xem nó bắt đúng không trước khi để nó từ chối khách.
    chan_han         boolean NOT NULL DEFAULT true,

    is_active        boolean NOT NULL DEFAULT true,
    ghi_chu          text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    -- QUA_N_THANG mà không có số tháng là một luật không tính được. Bắt khai
    -- ngay ở đây thay vì để nó im lặng thành "không bao giờ khớp".
    CONSTRAINT luat_bs_so_thang_khi_can
        CHECK (cach_tinh <> 'QUA_N_THANG' OR so_thang IS NOT NULL),

    -- Một dịch vụ chỉ có MỘT luật đang bật. Hai luật cùng dịch vụ mà khác bác
    -- sĩ thì câu "ai phải khám" có hai đáp án, và thứ tự áp dụng sẽ thành thứ
    -- tự dòng trong bảng — tức là ngẫu nhiên.
    CONSTRAINT uq_luat_bs_moi_dich_vu
        UNIQUE (clinic_id, service_type_id)
);

COMMENT ON TABLE public.luat_bac_si_bat_buoc IS
    'Dịch vụ X + khách mới → bắt buộc bác sĩ Y. Thi hành LÚC ĐẶT LỊCH.';

CREATE INDEX IF NOT EXISTS idx_luat_bs_clinic
    ON public.luat_bac_si_bat_buoc (clinic_id) WHERE is_active;

ALTER TABLE public.luat_bac_si_bat_buoc ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'luat_bac_si_bat_buoc'
           AND policyname = 'luat_bac_si_bat_buoc_select_own_clinic'
    ) THEN
        CREATE POLICY luat_bac_si_bat_buoc_select_own_clinic
            ON public.luat_bac_si_bat_buoc
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

-- Chính sách chỉ LỌC dòng; thiếu GRANT thì bảng vô hình và màn cấu hình sẽ
-- luôn hiện "chưa có luật nào" dù vừa lưu xong.
GRANT SELECT ON public.luat_bac_si_bat_buoc TO authenticated;


-- ── Khách này có phải KHÁCH MỚI của dịch vụ này không ──────────────────────
--
-- Đặt ở SQL chứ không ở Python: cả đường đặt lịch lẫn màn cấu hình đều cần trả
-- lời cùng một câu, và hai bản cài đặt của cùng một định nghĩa là hai bản sẽ
-- lệch nhau.
CREATE OR REPLACE FUNCTION public.la_khach_moi_cua_dich_vu(
    p_clinic_id  uuid,
    p_patient_id uuid,
    p_service_id uuid,
    p_cach_tinh  text,
    p_so_thang   integer DEFAULT NULL
)
RETURNS boolean
LANGUAGE sql
STABLE
AS $function$
    SELECT CASE p_cach_tinh
        WHEN 'CHUA_TUNG' THEN NOT EXISTS (
            SELECT 1 FROM public.appointment a
             WHERE a.clinic_id = p_clinic_id
               AND a.clinic_patient_id = p_patient_id
               AND a.service_type_id = p_service_id
               AND a.status = 'COMPLETED'
        )
        WHEN 'DOT_MOI' THEN NOT EXISTS (
            SELECT 1 FROM public.care_episode e
             WHERE e.clinic_id = p_clinic_id
               AND e.clinic_patient_id = p_patient_id
               AND e.service_type_id = p_service_id
               AND e.status <> 'CLOSED'
        )
        WHEN 'QUA_N_THANG' THEN NOT EXISTS (
            SELECT 1 FROM public.appointment a
             WHERE a.clinic_id = p_clinic_id
               AND a.clinic_patient_id = p_patient_id
               AND a.service_type_id = p_service_id
               AND a.status = 'COMPLETED'
               AND a.slot_start >= now() - make_interval(months => p_so_thang)
        )
        ELSE false
    END
$function$;

COMMENT ON FUNCTION public.la_khach_moi_cua_dich_vu IS
    'Khách mới của một dịch vụ, theo cách tính do phòng khám chọn. '
    'Suy từ LỊCH SỬ, không đọc ô appointment.patient_kind do lễ tân gõ tay.';
