-- BỘ KHÁM NAM KHOA — danh mục dịch vụ, cửa duyệt form, và ngưỡng tinh dịch đồ.
--
-- Theo docs/spec-form-nam-khoa.md §6.1–6.3.
--
-- Form `NK` đang nằm trong danh mục với is_active = FALSE. Nó không được bật
-- cho tới khi có đủ ba thứ dưới đây — và việc bật phải đi qua một hàm, không
-- phải một lệnh UPDATE gõ tay.

-- ---------------------------------------------------------------------------
-- 6.1 · Dịch vụ nam khoa
-- ---------------------------------------------------------------------------
-- Node `DICHVU-TINHDICHDO` đã tồn tại và đang CHẾT: không dịch vụ nào trỏ vào
-- nó, nên không lượt khám nào đi qua bước đó bao giờ.
--
-- BỐN DỊCH VỤ DI TRUYỀN ĐỂ node_code = NULL, CÓ CHỦ Ý. Phòng khám chưa xác
-- nhận gửi mẫu đi đâu (spec §6.1: "hỏi"). `order_services()` sẽ từ chối kèm
-- TÊN dịch vụ — thà từ chối rõ ràng còn hơn tạo một việc ở phòng không ai chờ,
-- rồi bệnh nhân ngồi đợi một chỗ không tồn tại.
--
-- Giá để trống như 29 dịch vụ hiện có: bảng giá là việc của phòng khám, và
-- điền một con số bịa vào đó thì thu ngân sẽ thu đúng con số bịa ấy.

INSERT INTO public.service_price
    (clinic_id, service_code, name, "group", category, node_code, active)
SELECT c.id, v.code, v.name, 'dich_vu', 'Nam khoa', v.node, true
  FROM public.clinic c
  CROSS JOIN (VALUES
      ('CLS_TINH_DICH_DO',             'Tinh dịch đồ',
       'DICHVU-TINHDICHDO'),
      ('CLS_SIEU_AM_TINH_HOAN',        'Siêu âm tinh hoàn / Doppler',
       'DICHVU-SIEUAM'),
      ('CLS_XN_NOI_TIET_NAM',          'Xét nghiệm nội tiết nam (FSH/LH/Testosterone)',
       'DICHVU-LAYMAU-MAU'),
      ('CLS_NUOC_TIEU_SAU_XUAT_TINH',  'Nước tiểu sau xuất tinh',
       'DICHVU-LAYMAU-NUOCTIEU'),
      -- Bốn dòng dưới: chưa biết gửi đi đâu.
      ('CLS_KARYOTYPE',                'Nhiễm sắc thể đồ',            NULL),
      ('CLS_Y_MICRODELETION',          'Mất đoạn nhỏ NST Y',          NULL),
      ('CLS_CFTR',                     'CFTR + alen 5T',              NULL),
      ('CLS_DFI',                      'Phân mảnh DNA tinh trùng',    NULL)
  ) AS v(code, name, node)
-- Khoá duy nhất thật là (clinic_id, "group", service_code) — `group` nằm giữa.
-- Viết thiếu nó thì ON CONFLICT không suy ra được chỉ mục nào và câu lệnh đổ.
ON CONFLICT (clinic_id, "group", service_code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 6.2 · Cửa duyệt form
-- ---------------------------------------------------------------------------
-- Hôm nay bật một form lâm sàng chỉ cần `UPDATE ... SET is_active = TRUE`. Một
-- form khám là thứ bác sĩ ký tên vào; ai bật nó, bật bản nào, dựa trên tài liệu
-- nào — cả ba đều phải đọc lại được.
--
-- VÌ SAO CÓ `schema_version`. Form sẽ đổi. Một bản ghi duyệt không nói rõ duyệt
-- BẢN NÀO thì lần sửa thứ hai âm thầm thừa hưởng chữ ký của lần đầu.

CREATE TABLE IF NOT EXISTS public.clinical_form_approval (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    form_code      text NOT NULL,
    schema_version text NOT NULL,
    approved_by_staff_id uuid NOT NULL REFERENCES public.staff(id),
    approved_at    timestamptz NOT NULL DEFAULT now(),
    --: Mã/đường dẫn tài liệu bác sĩ đã ký. Không có nó thì "đã duyệt" chỉ là
    --: một dòng trong database, không truy được về người chịu trách nhiệm.
    source_document text NOT NULL,
    note           text,
    CONSTRAINT clinical_form_approval_doc_not_blank
        CHECK (btrim(source_document) <> ''),
    CONSTRAINT uq_clinical_form_approval
        UNIQUE (clinic_id, form_code, schema_version)
);

COMMENT ON TABLE public.clinical_form_approval IS
    'Ai duyệt form lâm sàng nào, bản nào, dựa trên tài liệu nào. Điều kiện để '
    'clinical_form_catalogue.is_active được bật — và chỉ bật qua hàm '
    'activate_clinical_form(), không lật cờ bằng tay.';

-- Bật form CHỈ khi đã có bản ghi duyệt tương ứng.
CREATE OR REPLACE FUNCTION public.activate_clinical_form(
    p_clinic_id uuid, p_form_code text, p_schema_version text)
RETURNS boolean
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_ok boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.clinical_form_approval
         WHERE clinic_id = p_clinic_id AND form_code = p_form_code
           AND schema_version = p_schema_version
    ) INTO v_ok;

    IF NOT v_ok THEN
        RAISE EXCEPTION
            'Form % bản % chưa có bản ghi duyệt — không bật được. Ghi vào '
            'clinical_form_approval trước (ai duyệt, tài liệu nào).',
            p_form_code, p_schema_version
            USING ERRCODE = 'check_violation';
    END IF;

    UPDATE public.clinical_form_catalogue
       SET is_active = TRUE, updated_at = now()
     WHERE clinic_id = p_clinic_id AND form_code = p_form_code;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không có form % trong danh mục', p_form_code;
    END IF;
    RETURN TRUE;
END
$function$;

-- ---------------------------------------------------------------------------
-- 6.3 · Ngưỡng tham chiếu tinh dịch đồ
-- ---------------------------------------------------------------------------
-- BẢNG, KHÔNG PHẢI HẰNG SỐ TRONG CODE. WHO đã đổi ngưỡng qua ba ấn bản; nhốt
-- số vào TSX thì lần sau phải sửa code — và mất luôn câu trả lời cho "kết quả
-- năm ngoái được đọc theo ngưỡng nào".
--
-- `effective_from` là thứ giữ lịch sử đó: ngưỡng mới thêm dòng mới, dòng cũ ở
-- lại và vẫn giải thích được các kết quả đã đọc theo nó.

CREATE TABLE IF NOT EXISTS public.semen_reference_range (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    parameter      text NOT NULL,
    label          text NOT NULL,
    lower_limit    numeric NOT NULL,
    unit           text NOT NULL,
    source         text NOT NULL,
    effective_from date NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_semen_reference_range
        UNIQUE (clinic_id, parameter, effective_from)
);

COMMENT ON TABLE public.semen_reference_range IS
    'Ngưỡng dưới của tinh dịch đồ theo ấn bản WHO. Bảng chứ không phải hằng số: '
    'WHO đổi ngưỡng qua từng ấn bản, và mỗi kết quả phải đọc được theo đúng '
    'ngưỡng đang hiệu lực lúc đó.';

INSERT INTO public.semen_reference_range
    (clinic_id, parameter, label, lower_limit, unit, source, effective_from)
SELECT c.id, v.p, v.l, v.n, v.u, 'WHO_2021', DATE '2021-07-01'
  FROM public.clinic c
  CROSS JOIN (VALUES
      ('volume_ml',            'Thể tích',                  1.4,  'mL'),
      ('concentration_m_ml',   'Nồng độ tinh trùng',        16,   'triệu/mL'),
      ('total_count_m',        'Tổng số tinh trùng',        39,   'triệu'),
      ('total_motility_pct',   'Tổng di động',              42,   '%'),
      ('progressive_pct',      'Di động tiến tới',          30,   '%'),
      ('vitality_pct',         'Tỷ lệ sống',                54,   '%'),
      ('normal_forms_pct',     'Hình dạng bình thường',     4,    '%')
  ) AS v(p, l, n, u)
ON CONFLICT ON CONSTRAINT uq_semen_reference_range DO NOTHING;

-- ---------------------------------------------------------------------------
-- RLS — đọc cho vai lâm sàng, ghi chỉ backend (ADR-0012)
-- ---------------------------------------------------------------------------

ALTER TABLE public.clinical_form_approval ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.semen_reference_range  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clinical_form_approval_select ON public.clinical_form_approval;
CREATE POLICY clinical_form_approval_select ON public.clinical_form_approval
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS semen_reference_range_select ON public.semen_reference_range;
CREATE POLICY semen_reference_range_select ON public.semen_reference_range
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT ON public.clinical_form_approval TO authenticated;
GRANT SELECT ON public.semen_reference_range TO authenticated;

DO $verify$
DECLARE
    v_dv int;
    v_null int;
    v_ng int;
    v_nk boolean;
BEGIN
    SELECT count(*), count(*) FILTER (WHERE node_code IS NULL)
      INTO v_dv, v_null
      FROM public.service_price WHERE category = 'Nam khoa';
    SELECT count(*) INTO v_ng FROM public.semen_reference_range;
    SELECT is_active INTO v_nk
      FROM public.clinical_form_catalogue WHERE form_code = 'NK' LIMIT 1;

    IF v_nk IS TRUE THEN
        RAISE EXCEPTION 'Form NK đã bị bật mà chưa qua activate_clinical_form()';
    END IF;
    RAISE NOTICE
        'nam khoa: % dịch vụ (% chưa rõ nơi thực hiện) · % ngưỡng WHO 2021 · '
        'form NK vẫn TẮT, đúng như phải thế', v_dv, v_null, v_ng;
END
$verify$;
