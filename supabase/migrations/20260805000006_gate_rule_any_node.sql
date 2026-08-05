-- Bước bắt buộc là MỘT TẬP, không phải một bước.
--
-- 20260804000014 dựng `visit_gate_rule` với `required_node_code text NOT NULL`
-- — đúng một bước. Đi khai luật thật của Dr4Women thì nó không diễn đạt nổi.
--
-- LUẬT CẦN KHAI: *"khách nào đến cũng gặp BS Thành đầu tiên rồi mới được chỉ
-- định gặp bác sĩ khác"*. Mà BS Phan Chí Thành phụ trách CẢ NĂM chuyên khoa
-- (KHAM-SANKHOA · KHAM-PHUKHOA · KHAM-NOITIET · KHAM-HIEMMUON-VOSINH ·
-- KHAM-NAMKHOA), nên "đã gặp Thành" có năm hình dạng khác nhau.
--
-- HAI CÁCH KHAI BẰNG SCHEMA CŨ, VÀ CẢ HAI ĐỀU SAI:
--
--   một luật mỗi chuyên khoa   CHẶN THỪA. Khám Phụ khoa với Thành xong, chuyển
--                              sang Nội tiết bác sĩ khác vẫn bị chặn vì luật
--                              Nội tiết đòi "xong Nội tiết với Thành". Đó đúng
--                              là ca mà luật muốn CHO PHÉP — "rồi mới được chỉ
--                              định gặp bác sĩ khác".
--   một luật duy nhất          chỉ phủ được 1 trong 5 chuyên khoa; bốn đường
--                              còn lại đi thẳng, luật thành trang trí.
--
-- Nên đổi thành mảng: "đã xong BẤT KỲ bước nào trong tập này, do đúng người
-- ấy" — một luật, phủ đủ năm đường.
--
-- ĐỔI ĐƯỢC VÌ BẢNG ĐANG 0 DÒNG. Cơ chế dựng xong hôm qua nhưng chưa ai khai
-- luật nào, nên không có dữ liệu để migrate và không có hành vi nào đang chạy
-- để làm gãy. Sửa sau khi đã có luật thật thì phải vừa đổi cột vừa dịch dữ
-- liệu, giữa lúc chốt đang chặn người ở quầy.

DO $doi_cot$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'visit_gate_rule'
           AND column_name = 'required_node_code'
    ) THEN
        -- Bảng rỗng, nhưng vẫn dịch dữ liệu thay vì DROP thẳng: nếu môi trường
        -- nào đó đã kịp khai một luật thì nó chuyển thành mảng một phần tử,
        -- giữ nguyên nghĩa.
        ALTER TABLE public.visit_gate_rule
            ADD COLUMN IF NOT EXISTS required_node_codes text[];
        UPDATE public.visit_gate_rule
           SET required_node_codes = ARRAY[required_node_code]
         WHERE required_node_codes IS NULL;
        ALTER TABLE public.visit_gate_rule
            ALTER COLUMN required_node_codes SET NOT NULL;
        ALTER TABLE public.visit_gate_rule DROP COLUMN required_node_code;
    END IF;
END
$doi_cot$;

-- Mảng rỗng = luật không đòi gì, tức là luật không chặn gì. `coalesce` vì
-- `array_length` của mảng rỗng trả NULL, và CHECK cho NULL đi qua — xem
-- 20260804000021, cùng cái bẫy.
ALTER TABLE public.visit_gate_rule
    DROP CONSTRAINT IF EXISTS visit_gate_rule_has_required;
ALTER TABLE public.visit_gate_rule
    ADD CONSTRAINT visit_gate_rule_has_required
    CHECK (coalesce(array_length(required_node_codes, 1), 0) >= 1);

COMMENT ON COLUMN public.visit_gate_rule.required_node_codes IS
    'Đã xong BẤT KỲ bước nào trong tập này (do required_staff_id, nếu có khai) '
    'thì luật coi là đã qua cổng. Mảng chứ không phải một bước, vì một người '
    'gác cổng có thể phụ trách nhiều chuyên khoa.';

-- ---------------------------------------------------------------------------
-- Luật của Dr4Women
-- ---------------------------------------------------------------------------
-- Đây là DỮ LIỆU của một phòng khám, không phải luật của sản phẩm. Phòng khám
-- thứ hai khai luật khác ở cùng bảng này, hoặc không khai gì.
--
-- `only_when_other_staff` là ô làm nên tình huống này: bước bị chặn (khám)
-- TRÙNG với bước bắt buộc (cũng là khám). Không có ô đó thì luật tự chặn chính
-- nó — bệnh nhân không vào nổi phòng BS Thành để làm đúng cái việc luật đòi.
--
-- `override_roles` để mặc định (Trưởng ca + Quản lý): một chốt an toàn không
-- có đường vượt sẽ bị vượt bằng cách tắt nó đi, và lúc ấy không còn gì ghi lại
-- rằng đã có người vượt.

INSERT INTO public.visit_gate_rule
    (clinic_id, name, required_node_codes, required_staff_id,
     blocked_node_codes, only_when_other_staff, note)
SELECT c.id,
       'BS Thành khám trước',
       ARRAY['KHAM-SANKHOA', 'KHAM-PHUKHOA', 'KHAM-NOITIET',
             'KHAM-HIEMMUON-VOSINH', 'KHAM-NAMKHOA'],
       s.id,
       ARRAY['KHAM-SANKHOA', 'KHAM-PHUKHOA', 'KHAM-NOITIET',
             'KHAM-HIEMMUON-VOSINH', 'KHAM-NAMKHOA'],
       TRUE,
       'Khách nào đến cũng gặp BS Thành trước, rồi mới được chỉ định sang bác '
       'sĩ khác. Xong BẤT KỲ chuyên khoa nào với BS Thành là qua cổng — không '
       'phải xong đúng chuyên khoa của lần chỉ định tiếp theo.'
  FROM public.clinic c
  JOIN public.staff s ON s.full_name = 'TS.BS. Phan Chí Thành' AND s.is_active
 WHERE NOT EXISTS (
     SELECT 1 FROM public.visit_gate_rule g
      WHERE g.clinic_id = c.id AND g.name = 'BS Thành khám trước'
 );

DO $verify$
DECLARE
    v_luat record;
    v_so   int;
BEGIN
    SELECT count(*) INTO v_so FROM public.visit_gate_rule WHERE is_active;

    SELECT g.name, s.full_name AS nguoi_gac,
           array_length(g.required_node_codes, 1) AS so_buoc_bat_buoc,
           array_length(g.blocked_node_codes, 1)  AS so_buoc_bi_chan,
           g.only_when_other_staff
      INTO v_luat
      FROM public.visit_gate_rule g
      LEFT JOIN public.staff s ON s.id = g.required_staff_id
     WHERE g.name = 'BS Thành khám trước' LIMIT 1;

    IF v_luat IS NULL THEN
        RAISE EXCEPTION
            'Không khai được luật — không tìm thấy TS.BS. Phan Chí Thành đang '
            'hoạt động trong bảng staff';
    END IF;

    -- Không có ô này thì luật tự chặn chính nó: bệnh nhân không vào nổi phòng
    -- BS Thành. Kiểm tại chỗ vì hậu quả là phòng khám TẮC, giữa ca trực.
    IF NOT v_luat.only_when_other_staff THEN
        RAISE EXCEPTION 'only_when_other_staff phải TRUE, nếu không luật tự chặn chính nó';
    END IF;

    RAISE NOTICE
        'luật "%": người gác = % · qua cổng bằng % bước · chặn % bước · % luật '
        'đang bật', v_luat.name, v_luat.nguoi_gac, v_luat.so_buoc_bat_buoc,
        v_luat.so_buoc_bi_chan, v_so;
END
$verify$;
