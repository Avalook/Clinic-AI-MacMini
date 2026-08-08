-- Ai được xếp vào vị trí nào.
--
-- Quang (08/08/2026): *"đã chọn nhân viên rồi thì vị trí chỉ ở phạm vi của họ
-- chứ không chọn sang khả năng của người khác được, ví dụ lễ tân chỉ chọn được
-- lịch làm việc và vị trí của lễ tân, không vào bác sĩ được."*
--
-- HÔM NAY KHÔNG CÓ GÌ CHẶN CẢ. `stationsForRole` trong lib/roster.ts chỉ lọc ở
-- trình duyệt, và luật của nó gọn tới mức vô nghĩa: bác sĩ → đúng một trạm, MỌI
-- VAI CÒN LẠI → mười một trạm còn lại. Nên lễ tân chọn được "Máy trong E10 +
-- VLTL/thủ thuật". Còn backend (`RosterService.add_shift`) thì không đọc chức
-- danh của người được xếp lấy một lần — gọi thẳng API là xếp được bất kỳ ai vào
-- bất kỳ đâu.
--
-- VÌ SAO LÀ BẢNG, KHÔNG PHẢI MẢNG TRONG CODE.
--
-- Vì luật gọn trong code SAI so với đời thật, và sai theo hướng tốn tiền. Đo
-- trên bản thật: lễ tân của Dr4Women đi LẤY MÁU 234 ca và phụ khám 182 ca. Ghi
-- cứng "lễ tân chỉ được ngồi quầy" là tuần sau quản lý không xếp nổi lịch.
-- Phòng khám khác lại có ranh giới khác hẳn. Đây là dữ liệu của từng phòng
-- khám, không phải hằng số của phần mềm.
--
-- GIEO TỪ CHÍNH LỊCH TRỰC CỦA HỌ, không phải từ tôi đoán. Ma trận khởi đầu =
-- "những gì phòng khám đã thật sự làm suốt sáu tháng qua". Phải chạy SAU
-- 20260809000001 (dọn 390 ca trực ma), nếu không nó sẽ học thuộc luôn cái sai
-- và phong cho bác sĩ quyền đứng ở trạm phụ.

CREATE TABLE IF NOT EXISTS public.vai_duoc_vao_tram (
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    tram_ma    text NOT NULL,
    vai        text NOT NULL,
    is_active  boolean NOT NULL DEFAULT true,
    -- Vì sao dòng này có mặt. Phân biệt "đo được từ lịch cũ" với "người thêm
    -- tay" là thứ giữ cho lần rà sau không xoá nhầm một ngoại lệ có chủ ý.
    ghi_chu    text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, tram_ma, vai)
);

COMMENT ON TABLE public.vai_duoc_vao_tram IS
    'Chức danh nào được xếp vào vị trí nào. Thi hành ở RosterService.add_shift.';
COMMENT ON COLUMN public.vai_duoc_vao_tram.tram_ma IS
    'Mã trạm — cùng bộ mã với STATIONS trong src/dashboard/lib/roster.ts. '
    'Chưa có bảng danh mục trạm nên KHÔNG có khoá ngoại; đổi mã ở một nơi thì '
    'phải đổi ở nơi kia.';

ALTER TABLE public.vai_duoc_vao_tram ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'vai_duoc_vao_tram'
           AND policyname = 'vai_duoc_vao_tram_select_own_clinic'
    ) THEN
        CREATE POLICY vai_duoc_vao_tram_select_own_clinic
            ON public.vai_duoc_vao_tram
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

-- Chính sách chỉ LỌC dòng. Thiếu GRANT thì bảng vô hình và màn xếp lịch sẽ báo
-- "chưa khai vị trí nào" dù bảng đầy — đúng cái bẫy đã sập ở roster_week.
GRANT SELECT ON public.vai_duoc_vao_tram TO authenticated;


-- ── Gieo: những gì phòng khám ĐÃ LÀM ───────────────────────────────────────
INSERT INTO public.vai_duoc_vao_tram (clinic_id, tram_ma, vai, ghi_chu)
SELECT DISTINCT r.clinic_id, r.station, s.primary_department,
       'suy từ lịch trực đã có'
  FROM public.work_roster r
  JOIN public.staff s ON s.id = r.staff_id
 WHERE s.primary_department IS NOT NULL
   AND s.primary_department <> 'DISPLAY'
ON CONFLICT DO NOTHING;


-- ── Bù tay: chỗ lịch cũ KHÔNG nói gì ───────────────────────────────────────
--
-- Ba nhóm dưới đây KHÔNG suy được từ dữ liệu, và bỏ trống thì hậu quả là quản
-- lý không xếp nổi ai vào đó nữa. Ghi rõ "thêm tay" để lần rà sau biết đây là
-- phỏng đoán, không phải phép đo.
--
--   · Bác sĩ siêu âm: 7 người, 0 ca trong lịch tháng 6 (sheet ấy không có cột
--     siêu âm). Không bù thì bảy bác sĩ biến mất khỏi mọi ô xếp lịch.
--   · Ba trạm ngoài giờ (SB chiều / Thủ thuật ngoài giờ / HSS): 0 ca trong lịch
--     mẫu, nhưng chúng có trong danh mục màn hình nên vẫn xếp được.
--   · CSKH và Thu ngân ở quầy lễ tân: cùng một cái bàn.
INSERT INTO public.vai_duoc_vao_tram (clinic_id, tram_ma, vai, ghi_chu)
SELECT c.id, t.tram, t.vai, 'thêm tay — lịch cũ không có dữ liệu'
  FROM public.clinic c
 CROSS JOIN (VALUES
        ('LICH_KHAM',           'ULTRASOUND_DOCTOR'),
        ('PHU_BS_SA',           'ULTRASOUND_DOCTOR'),
        ('MAY_TRONG',           'ULTRASOUND_DOCTOR'),
        ('MAY_NGOAI',           'ULTRASOUND_DOCTOR'),
        ('PHONG_NGOAI_MOR',     'ULTRASOUND_DOCTOR'),
        ('LE_TAN',              'CSKH'),
        ('LE_TAN',              'CASHIER'),
        ('SB_CHIEU',            'DOCTOR'),
        ('SB_CHIEU',            'ULTRASOUND_DOCTOR'),
        ('SB_CHIEU',            'NURSE_ULTRASOUND'),
        ('SB_CHIEU',            'TKYK'),
        ('THU_THUAT_NGOAI_GIO', 'DOCTOR'),
        ('THU_THUAT_NGOAI_GIO', 'ULTRASOUND_DOCTOR'),
        ('THU_THUAT_NGOAI_GIO', 'NURSE_ULTRASOUND'),
        ('THU_THUAT_NGOAI_GIO', 'TKYK'),
        ('HSS_THU_THUAT',       'DOCTOR'),
        ('HSS_THU_THUAT',       'ULTRASOUND_DOCTOR'),
        ('HSS_THU_THUAT',       'NURSE_ULTRASOUND'),
        ('HSS_THU_THUAT',       'TKYK')
     ) AS t(tram, vai)
ON CONFLICT DO NOTHING;

-- Trưởng ca trực thay được ở mọi trạm TRỪ bàn khám: đứng tên "Lịch khám (Bác
-- sĩ)" khi không phải bác sĩ chính là loại nhầm mà Quang bảo phải chặn.
INSERT INTO public.vai_duoc_vao_tram (clinic_id, tram_ma, vai, ghi_chu)
SELECT DISTINCT v.clinic_id, v.tram_ma, 'TRUONG_CA', 'thêm tay — trưởng ca trực thay'
  FROM public.vai_duoc_vao_tram v
 WHERE v.tram_ma <> 'LICH_KHAM'
ON CONFLICT DO NOTHING;

DO $$
DECLARE v_dong int; v_tram int;
BEGIN
    SELECT count(*), count(DISTINCT tram_ma) INTO v_dong, v_tram
      FROM public.vai_duoc_vao_tram;
    RAISE NOTICE 'Ma trận vị trí: % dòng trên % trạm.', v_dong, v_tram;
END $$;
