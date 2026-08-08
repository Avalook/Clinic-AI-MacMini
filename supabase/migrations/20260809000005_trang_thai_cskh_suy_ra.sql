-- Trạng thái khách hàng là một HÀM CỦA DỮ LIỆU, không phải một cột ai đó bấm.
--
-- Màn Quản lý khách hàng hôm nay hiện "Đã đặt lịch" cho gần như mọi khách, và
-- ba cột Tương tác gần nhất / Bước tiếp theo / Hạn xử lý là "—". Nguồn của nó
-- là `cskh_action` — bảng có 0 dòng, và hai câu INSERT duy nhất ghi vào đó còn
-- không có cột `step` lẫn `deadline_at`.
--
-- VÌ SAO LÀ VIEW, KHÔNG PHẢI BẢNG VIỆC SINH SẴN.
--
-- Dự án không có bộ hẹn giờ (recall_job_service.py:24-30 tự khai: không
-- apscheduler, không croniter, không repeat_every). Một bảng việc mà không có
-- cron thì việc chỉ ra đời khi có người mở màn — và từ giây đó nó là BẢN SAO
-- của sự thật, tự do lệch: lịch bị huỷ mà việc "gọi nhắc hẹn" vẫn nằm đó, kết
-- quả xét nghiệm về rồi mà việc "chờ kết quả" vẫn mở.
--
-- Đó đúng là bệnh `cskh_action` đang mắc. View thì không lệch được: xoá một
-- cuộc gọi thì trạng thái tự lùi về đúng chỗ.
--
-- ĐÁNH ĐỔI PHẢI NÓI RA: view không giữ được "ai nhận việc này". Cột PHỤ TRÁCH
-- hiện NGƯỜI TƯƠNG TÁC GẦN NHẤT. Vẫn hơn hôm nay (`created_by_text` là chuỗi
-- tên tự do nhập từ Notion — không giao việc được, không lọc theo người được).
-- Khi thật sự cần nhận việc thì thêm một bảng mỏng, không cần bảng việc đầy đủ.


-- ── Luật là dữ liệu, không phải hằng số ────────────────────────────────────
--
-- "Gọi xác nhận trước 7 ngày" là con số của Dr4Women. Phòng khám khác đếm khác,
-- và chính Dr4Women cũng sẽ đổi. Ghim vào SQL thì mỗi lần đổi là một lần deploy.
CREATE TABLE IF NOT EXISTS public.luat_cskh (
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    loai_viec    text NOT NULL,
    bat          boolean NOT NULL DEFAULT true,
    so_ngay      integer NOT NULL DEFAULT 1 CHECK (so_ngay BETWEEN 0 AND 365),
    -- Chỉ dùng cho việc có KHOẢNG (gọi lại sau khi huỷ: từ ngày 1 tới ngày 14).
    cua_so_ngay  integer CHECK (cua_so_ngay IS NULL OR cua_so_ngay BETWEEN 1 AND 365),
    nhan         text NOT NULL,
    PRIMARY KEY (clinic_id, loai_viec)
);

COMMENT ON TABLE public.luat_cskh IS
    'Số ngày và NHÃN của từng loại việc CSKH. View đọc cả hai, nên phòng khám '
    'đổi con số VÀ đổi chữ hiển thị mà không cần deploy lại.';

ALTER TABLE public.luat_cskh ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'luat_cskh'
           AND policyname = 'luat_cskh_select_own_clinic'
    ) THEN
        CREATE POLICY luat_cskh_select_own_clinic ON public.luat_cskh
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

GRANT SELECT ON public.luat_cskh TO authenticated;

-- Gieo cho MỌI phòng khám đang có. Không ghi cứng tên ai: 20260805000006 từng
-- seed theo `full_name = 'TS.BS. Phan Chí Thành'` và khớp 0 dòng ở mọi nơi.
INSERT INTO public.luat_cskh (clinic_id, loai_viec, so_ngay, cua_so_ngay, nhan)
SELECT c.id, t.loai, t.so_ngay, t.cua_so, t.nhan
  FROM public.clinic c
 CROSS JOIN (VALUES
     ('CHO_XAC_NHAN',   7,  NULL, 'Chờ xác nhận lịch'),
     ('NHAC_HEN_MAI',   1,  NULL, 'Nhắc hẹn ngày mai'),
     ('GOI_LAI',        0,  NULL, 'Cần gọi lại'),
     ('HOI_LY_DO_HUY',  1,  14,   'Hỏi lý do huỷ'),
     ('CHO_KQ_XN',      2,  NULL, 'Chờ kết quả xét nghiệm'),
     ('CHO_BAC_SI',     1,  NULL, 'Chờ bác sĩ duyệt kết quả'),
     ('KQ_CHUA_GUI',    1,  NULL, 'Có kết quả, chưa gửi'),
     ('HEN_GOI_LAI',    0,  NULL, 'Đã hẹn gọi lại'),
     ('MOI_TAI_KHAM',   0,  NULL, 'Mời tái khám'),
     ('NHAC_DI_KHAM',   0,  NULL, 'Nhắc đi khám hôm nay')
  ) AS t(loai, so_ngay, cua_so, nhan)
ON CONFLICT DO NOTHING;


-- ── Việc CSKH tự hẹn cho mình ──────────────────────────────────────────────
--
-- Chỗ đựng những việc hệ thống CHƯA suy được: "gọi hỏi thăm sau thủ thuật một
-- ngày", "chúc mừng đầy tháng sau sinh".
--
-- VÌ SAO PHẢI GÕ TAY, KHÔNG TỰ SINH. Đo trên bản thật: không cột nào chứa ngày
-- sinh con — `edd_date` là ngày DỰ sinh, và sinh sớm/muộn hai tuần nghĩa là gọi
-- chúc mừng đầy tháng vào tuần thứ hai hoặc tuần thứ sáu. Còn "thủ thuật" thì
-- chưa phải một khái niệm: các service_type thủ thuật đang is_active = false
-- sau 20260807000007.
--
-- Một nút để người gõ thì có việc THẬT. Một tab tự sinh từ ngày dự sinh thì có
-- việc SAI, và không ai biết nó sai cho tới khi gọi nhầm.
CREATE TABLE IF NOT EXISTS public.hen_goi_lai (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    clinic_patient_id uuid NOT NULL
        REFERENCES public.patient(clinic_patient_id) ON DELETE CASCADE,
    ngay_goi   date NOT NULL,
    ly_do      text NOT NULL,
    tao_boi_staff_id uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    dong_luc   timestamptz,
    dong_boi_staff_id uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),

    -- Đóng việc mà không biết ai đóng thì không truy lại được. Hai nửa đi cùng
    -- nhau, cùng khuôn với nhac_tai_kham.
    CONSTRAINT hen_goi_lai_dong_du_doi
        CHECK ((dong_luc IS NULL) = (dong_boi_staff_id IS NULL))
);

COMMENT ON TABLE public.hen_goi_lai IS
    'Việc CSKH tự hẹn: "gọi lại ngày…". Chỗ đựng những việc hệ chưa suy được.';

CREATE INDEX IF NOT EXISTS idx_hen_goi_lai_dang_mo
    ON public.hen_goi_lai (clinic_id, ngay_goi)
    WHERE dong_luc IS NULL;

ALTER TABLE public.hen_goi_lai ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'hen_goi_lai'
           AND policyname = 'hen_goi_lai_select_own_clinic'
    ) THEN
        CREATE POLICY hen_goi_lai_select_own_clinic ON public.hen_goi_lai
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

GRANT SELECT ON public.hen_goi_lai TO authenticated;


-- ── Chỉ mục nuôi view ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_appointment_cskh_song
    ON public.appointment (clinic_id, status, slot_start);
CREATE INDEX IF NOT EXISTS idx_appointment_da_huy
    ON public.appointment (clinic_id, cancelled_at)
    WHERE status = 'CANCELLED';


-- ── Trạng thái ─────────────────────────────────────────────────────────────
--
-- MỘT DÒNG CHO MỖI KHÁCH: việc gấp nhất đang mở. Khách không có việc nào ra
-- 'KHONG_CO_VIEC' — một nhãn THẬT, thay cho "Đã đặt lịch" mà màn hiện cho gần
-- như tất cả mọi người hôm nay.
--
-- `security_invoker` để chính sách của các bảng nền áp dụng theo người đăng
-- nhập. Thiếu cờ này thì view chạy bằng quyền của người TẠO nó và trả dữ liệu
-- của mọi phòng khám — rò rỉ im lặng, không lỗi nào báo.
CREATE OR REPLACE VIEW public.v_trang_thai_cskh
WITH (security_invoker = true) AS
WITH hom_nay AS (
    SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d
),
-- Lần chạm gần nhất của mỗi lịch hẹn — nuôi trạng thái "cần gọi lại".
cham_cuoi AS (
    SELECT DISTINCT ON (t.appointment_id)
           t.appointment_id, t.ket_qua, t.xay_ra_luc
      FROM public.tuong_tac_cskh t
     WHERE t.appointment_id IS NOT NULL
     ORDER BY t.appointment_id, t.xay_ra_luc DESC
),
viec AS (
    -- ① Chờ bác sĩ duyệt kết quả. Cổng an toàn đã có sẵn trong lab.py lần đầu
    --    được hiện thành một dòng việc thay vì một nút bấm vào là 403.
    SELECT r.clinic_id, r.clinic_patient_id, 'CHO_BAC_SI' AS loai, 1 AS uu_tien,
           (r.result_received_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               + l.so_ngay AS han, NULL::uuid AS appointment_id
      FROM public.lab_result r
      JOIN public.luat_cskh l ON l.clinic_id = r.clinic_id
                             AND l.loai_viec = 'CHO_BAC_SI' AND l.bat
     WHERE r.result_value IS NOT NULL
       AND r.requires_doctor_review AND r.reviewed_at IS NULL

    UNION ALL

    -- ② Có kết quả, chưa gọi trả cho khách.
    SELECT r.clinic_id, r.clinic_patient_id, 'KQ_CHUA_GUI', 2,
           (coalesce(r.reviewed_at, r.result_received_at)
                AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + l.so_ngay, NULL
      FROM public.lab_result r
      JOIN public.luat_cskh l ON l.clinic_id = r.clinic_id
                             AND l.loai_viec = 'KQ_CHUA_GUI' AND l.bat
     WHERE r.result_value IS NOT NULL
       AND (NOT r.requires_doctor_review OR r.reviewed_at IS NOT NULL)
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.clinic_patient_id = r.clinic_patient_id
                AND t.loai = 'TRA_KQ' AND t.xay_ra_luc >= r.created_at)

    UNION ALL

    -- ③ Đã lấy mẫu, chưa có kết quả → hỏi đơn vị xét nghiệm.
    SELECT r.clinic_id, r.clinic_patient_id, 'CHO_KQ_XN', 3,
           (coalesce(r.sample_collected_at, r.created_at)
                AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + l.so_ngay, NULL
      FROM public.lab_result r
      JOIN public.luat_cskh l ON l.clinic_id = r.clinic_id
                             AND l.loai_viec = 'CHO_KQ_XN' AND l.bat
     WHERE r.result_value IS NULL

    UNION ALL

    -- ④ CẦN GỌI LẠI — đây chính là "KNM/KLLD/Hẹn GLS" trong DoD.
    --    Không phải loại hẹn mới: là kết quả của lần gọi gần nhất.
    SELECT a.clinic_id, a.clinic_patient_id, 'GOI_LAI', 4,
           (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, a.id
      FROM public.appointment a
      JOIN cham_cuoi c ON c.appointment_id = a.id
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'GOI_LAI' AND l.bat
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED', 'COMPLETED')
       AND c.ket_qua IN ('CHUA_NGHE_MAY', 'KHONG_LIEN_LAC_DUOC', 'HEN_GOI_LAI')

    UNION ALL

    -- ⑤ Đã huỷ → gọi lại hỏi lý do, trong khoảng 1–14 ngày sau khi huỷ.
    SELECT a.clinic_id, a.clinic_patient_id, 'HOI_LY_DO_HUY', 5,
           (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + l.so_ngay, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'HOI_LY_DO_HUY' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status = 'CANCELLED' AND a.cancelled_at IS NOT NULL
       AND (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             BETWEEN h.d - coalesce(l.cua_so_ngay, 14) AND h.d - l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'HOI_LY_DO_HUY')

    UNION ALL

    -- ⑥ CSKH tự hẹn gọi lại — chỗ đựng việc hệ chưa suy được.
    SELECT g.clinic_id, g.clinic_patient_id, 'HEN_GOI_LAI', 6, g.ngay_goi, NULL
      FROM public.hen_goi_lai g
      JOIN public.luat_cskh l ON l.clinic_id = g.clinic_id
                             AND l.loai_viec = 'HEN_GOI_LAI' AND l.bat
     CROSS JOIN hom_nay h
     WHERE g.dong_luc IS NULL AND g.ngay_goi <= h.d

    UNION ALL

    -- ⑦⑧ Hai lượt nhắc tái khám. ĐỌC bảng cũ thay vì gộp nó vào đây: nó lo một
    --     nghiệp vụ khác (mời tái khám, nguồn từ soap_plan), và trả nó ra cùng
    --     danh sách này là đủ để CSKH không phải mở hai màn.
    SELECT n.clinic_id, n.clinic_patient_id,
           CASE n.luot_goi WHEN 1 THEN 'MOI_TAI_KHAM' ELSE 'NHAC_DI_KHAM' END,
           CASE n.luot_goi WHEN 1 THEN 9 ELSE 7 END,
           n.han_goi, n.appointment_id
      FROM public.nhac_tai_kham n
      JOIN public.luat_cskh l
        ON l.clinic_id = n.clinic_id AND l.bat
       AND l.loai_viec = CASE n.luot_goi WHEN 1 THEN 'MOI_TAI_KHAM'
                                         ELSE 'NHAC_DI_KHAM' END
     WHERE n.trang_thai = 'CHO_GOI'

    UNION ALL

    -- ⑧ Nhắc hẹn ngày mai. SINH CHO MỌI LỊCH NGÀY MAI, không lọc theo "đã xác
    --    nhận" (Quang chốt 08/08). Lọc cứng thì ngày bật tính năng chưa ai có
    --    dòng xác nhận nào và hàng chờ rỗng sạch tuần đầu — CSKH sẽ kết luận
    --    màn hỏng. Ai đã xác nhận thì hiện thành NHÃN trên dòng.
    SELECT a.clinic_id, a.clinic_patient_id, 'NHAC_HEN_MAI', 8,
           h.d, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'NHAC_HEN_MAI' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED', 'COMPLETED')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = h.d + l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'NHAC_HEN')

    UNION ALL

    -- ⑨ Chờ xác nhận lịch — lịch trong vòng N ngày tới mà chưa ai gọi xác nhận.
    --    Suy từ sự VẮNG MẶT của một cuộc gọi, KHÔNG từ appointment.status: lịch
    --    mới vào thẳng CONFIRMED (booking_service.py), nên status không bao giờ
    --    nói được "đã gọi cho khách chưa".
    SELECT a.clinic_id, a.clinic_patient_id, 'CHO_XAC_NHAN', 10,
           (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'CHO_XAC_NHAN' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED', 'COMPLETED')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             BETWEEN h.d AND h.d + l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH')
),
gap_nhat AS (
    SELECT DISTINCT ON (clinic_id, clinic_patient_id) *
      FROM viec ORDER BY clinic_id, clinic_patient_id, uu_tien, han
)
SELECT v.clinic_id,
       v.clinic_patient_id,
       v.loai            AS trang_thai,
       l.nhan            AS nhan,
       v.han             AS han_xu_ly,
       (v.han < h.d)     AS qua_han,
       v.appointment_id,
       -- Khách đã nói sẽ đến chưa. Nhãn trên dòng, không phải bộ lọc.
       EXISTS (SELECT 1 FROM public.tuong_tac_cskh t
                WHERE t.appointment_id = v.appointment_id
                  AND t.khach_xac_nhan) AS da_xac_nhan
  FROM gap_nhat v
  JOIN public.luat_cskh l
    ON l.clinic_id = v.clinic_id AND l.loai_viec = v.loai
 CROSS JOIN hom_nay h;

COMMENT ON VIEW public.v_trang_thai_cskh IS
    'Việc gấp nhất đang mở của mỗi khách. Suy lại từ dữ liệu mỗi lần đọc — '
    'xoá một cuộc gọi thì trạng thái tự lùi về đúng chỗ.';

GRANT SELECT ON public.v_trang_thai_cskh TO authenticated;
