-- LUẬT THỨ TỰ BẮT BUỘC — "phải qua đây trước khi được đi tiếp".
--
-- Yêu cầu của Quang: *"đặt lịch để bác sĩ Thành là người mà khách nào đến cũng
-- gặp đầu tiên rồi mới được chỉ định gặp bác sĩ khác"*.
--
-- BA CÁCH LÀM, CHỈ MỘT CÁCH ĐÚNG.
--
--   1. `if (doctor == 'Thành')` trong code → phòng khám thứ hai phải sửa code.
--      Không bán được.
--   2. Thêm cột `is_gatekeeper` vào `staff` → khách sau muốn "điều dưỡng sàng
--      lọc trước khi gặp bác sĩ" lại phải thêm cột nữa. Mỗi khách một cột.
--   3. Khai thành LUẬT có phạm vi tenant → ba khách hàng, ba luật khác nhau,
--      cùng một dòng code. Đây là cách này.
--
-- MỘT KHUÔN, HAI TÌNH HUỐNG THẬT.
--
--   Dr4Women : phải xong KHÁM (do BS Thành) trước khi sang bước khám của bác
--              sĩ KHÁC.  → required_staff_id = Thành, only_when_other_staff
--   Nơi khác : phải xong SINH HIỆU (ai cũng được) trước khi gặp bác sĩ.
--              → required_staff_id = NULL, only_when_other_staff = false
--
-- Bốn ô: ÁP CHO AI · BẮT BUỘC QUA · CHẶN CÁI GÌ · AI BỎ QUA ĐƯỢC.
--
-- Ô thứ tư không phải phần phụ. Phòng khám thật luôn có ca ngoại lệ; hệ thống
-- nào không cho ngoại lệ sẽ bị vượt mặt bằng giấy tay, và lúc đó nó mất luôn
-- khả năng biết chuyện gì đã xảy ra. Nên ngoại lệ được PHÉP, nhưng bắt ghi lý
-- do và sinh event.

CREATE TABLE IF NOT EXISTS public.visit_gate_rule (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    -- NULL = áp cho mọi cơ sở của phòng khám này.
    location_id uuid REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    name       text NOT NULL,

    -- ── ÁP CHO AI ────────────────────────────────────────────────────────
    -- NULL = mọi bệnh nhân. 'NEW' = khách mới, 'RETURN' = tái khám. Cùng bộ
    -- giá trị với appointment.patient_kind, không đẻ thêm từ vựng mới.
    patient_kind    text,
    -- NULL = mọi dịch vụ.
    service_type_id uuid REFERENCES public.service_type(id) ON DELETE RESTRICT,

    -- ── BẮT BUỘC QUA ─────────────────────────────────────────────────────
    required_node_code text NOT NULL,
    -- NULL = ai làm cũng được. Có giá trị = phải đúng người này làm.
    required_staff_id  uuid REFERENCES public.staff(id) ON DELETE RESTRICT,

    -- ── CHẶN CÁI GÌ ──────────────────────────────────────────────────────
    -- Các bước bị khoá cho tới khi bước bắt buộc xong.
    blocked_node_codes text[] NOT NULL,
    -- true = chỉ chặn khi người phụ trách KHÁC với required_staff_id.
    --
    -- Đây là ô làm nên tình huống của Dr4Women: bước bị chặn (khám) TRÙNG với
    -- bước bắt buộc (cũng là khám). Không có ô này thì luật tự chặn chính nó và
    -- không ai đi được bước nào.
    only_when_other_staff boolean NOT NULL DEFAULT false,

    -- ── AI BỎ QUA ĐƯỢC ───────────────────────────────────────────────────
    -- Vai được phép bỏ qua, kèm lý do. Rỗng = không ai bỏ qua được.
    override_roles text[] NOT NULL DEFAULT ARRAY['TRUONG_CA', 'MANAGEMENT'],

    is_active  boolean NOT NULL DEFAULT true,
    note       text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT visit_gate_rule_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT visit_gate_rule_patient_kind
        CHECK (patient_kind IS NULL OR patient_kind IN ('NEW', 'RETURN')),
    CONSTRAINT visit_gate_rule_has_blocked
        CHECK (array_length(blocked_node_codes, 1) >= 1),
    -- only_when_other_staff chỉ có nghĩa khi đã chỉ đích danh người phải làm.
    CONSTRAINT visit_gate_rule_other_staff_needs_staff
        CHECK (NOT only_when_other_staff OR required_staff_id IS NOT NULL),
    CONSTRAINT visit_gate_rule_required_node_fk
        FOREIGN KEY (clinic_id, required_node_code)
        REFERENCES public.node_definition (clinic_id, code) ON DELETE RESTRICT
);

COMMENT ON TABLE public.visit_gate_rule IS
    'Luật thứ tự bắt buộc: phải xong bước A (có thể do đúng người A'') trước '
    'khi được sang bước B. Theo từng phòng khám — mỗi tenant khai luật của '
    'mình, không ai đụng ai.';

CREATE INDEX IF NOT EXISTS idx_visit_gate_rule_live
    ON public.visit_gate_rule (clinic_id, location_id) WHERE is_active;

-- Mã trong `blocked_node_codes` không khoá ngoại được (mảng), nên kiểm bằng
-- trigger. Gõ sai một mã ở đây thì luật lặng lẽ không chặn gì — đúng loại hỏng
-- tệ nhất với một luật an toàn.
CREATE OR REPLACE FUNCTION public.visit_gate_rule_nodes_exist()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    bad text;
BEGIN
    SELECT c INTO bad
      FROM unnest(NEW.blocked_node_codes) AS c
     WHERE NOT EXISTS (
         SELECT 1 FROM public.node_definition n
          WHERE n.clinic_id = NEW.clinic_id AND n.code = c
     )
     LIMIT 1;
    IF bad IS NOT NULL THEN
        RAISE EXCEPTION 'Bước "%" chưa được khai trong phòng khám này', bad
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_visit_gate_rule_nodes ON public.visit_gate_rule;
CREATE TRIGGER trg_visit_gate_rule_nodes
    BEFORE INSERT OR UPDATE OF blocked_node_codes ON public.visit_gate_rule
    FOR EACH ROW EXECUTE FUNCTION public.visit_gate_rule_nodes_exist();

-- ---------------------------------------------------------------------------
-- Nhật ký bỏ qua
-- ---------------------------------------------------------------------------
-- Bỏ qua một chốt an toàn là việc phải đọc lại được: ai, lúc nào, vì sao, cho
-- bệnh nhân nào. Ghi riêng chứ không chỉ nằm lẫn trong event_log — để hỏi
-- "tháng này luật nào bị bỏ qua nhiều nhất" chỉ là một câu SELECT.

CREATE TABLE IF NOT EXISTS public.visit_gate_override (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    rule_id    uuid NOT NULL REFERENCES public.visit_gate_rule(id) ON DELETE RESTRICT,
    visit_id   uuid NOT NULL,
    to_node_code text NOT NULL,
    reason     text NOT NULL,
    by_staff_id uuid NOT NULL REFERENCES public.staff(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT visit_gate_override_reason_not_blank CHECK (btrim(reason) <> '')
);

CREATE INDEX IF NOT EXISTS idx_visit_gate_override_rule
    ON public.visit_gate_override (clinic_id, rule_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE public.visit_gate_rule ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.visit_gate_override ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS visit_gate_rule_select ON public.visit_gate_rule;
CREATE POLICY visit_gate_rule_select ON public.visit_gate_rule
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- Khai luật là việc của QUẢN LÝ phòng khám. Trưởng ca bỏ qua được một lần (có
-- ghi lý do) nhưng không sửa được luật — hai quyền khác nhau, và gộp lại thì
-- "ngoại lệ" biến thành "đổi luật" mà không ai thấy.
DROP POLICY IF EXISTS visit_gate_rule_write ON public.visit_gate_rule;
CREATE POLICY visit_gate_rule_write ON public.visit_gate_rule
    FOR ALL TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT'])))
    WITH CHECK (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT'])));

DROP POLICY IF EXISTS visit_gate_override_select ON public.visit_gate_override;
CREATE POLICY visit_gate_override_select ON public.visit_gate_override
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS visit_gate_override_write ON public.visit_gate_override;
CREATE POLICY visit_gate_override_write ON public.visit_gate_override
    FOR INSERT TO authenticated
    WITH CHECK (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['TRUONG_CA', 'MANAGEMENT'])));

GRANT SELECT ON public.visit_gate_rule TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.visit_gate_rule TO authenticated;
GRANT SELECT, INSERT ON public.visit_gate_override TO authenticated;

DO $verify$
BEGIN
    PERFORM 1 FROM public.visit_gate_rule LIMIT 1;
    PERFORM 1 FROM public.visit_gate_override LIMIT 1;
    RAISE NOTICE 'luật thứ tự bắt buộc: schema sẵn sàng (chưa khai luật nào)';
END
$verify$;
