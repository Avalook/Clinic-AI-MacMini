-- Bấm nhầm thì phải hoàn tác được — nhưng KHÔNG được xoá dấu vết.
--
-- QUANG 10/08/2026: *"thêm khả năng nhấn vào nút tròn của các sự kiện để hoàn
-- tác (tất nhiên là log không được xoá, mà là hoàn tác lại tác vụ đó) để phòng
-- trường hợp người ta ấn nhầm"*.
--
-- Hai vế ấy nghe như mâu thuẫn, và chính chỗ ấy quyết định thiết kế.
--
-- `tuong_tac_cskh` là sổ CHỈ THÊM. Docstring của service viết rõ từ đầu: *"một
-- cuộc gọi đã xảy ra thì đã xảy ra, và bản ghi sai được sửa bằng cách ghi thêm
-- một dòng nói rõ, không phải bằng cách viết lại quá khứ"*. Một cú DELETE ở đây
-- là xoá bằng chứng ai đã chạm tới bệnh nhân lúc mấy giờ.
--
-- Nhưng "ấn nhầm" là chuyện có thật, và hậu quả của nó KHÔNG nằm ở dòng sổ — nó
-- nằm ở chỗ dòng sổ ấy ĐÓNG một việc. `v_viec_cskh` đóng nhánh bằng
-- `NOT EXISTS(... loai = 'XAC_NHAN_LICH')`; bấm nhầm một cái là việc "gọi xác
-- nhận lịch" biến mất khỏi hàng đợi, và không ai gọi cho khách ấy nữa.
--
-- NÊN: dòng Ở LẠI, chỉ THÔI ĐƯỢC TÍNH. Hai cột `huy_luc` / `huy_boi_staff_id`
-- nói "lần chạm này đã được hoàn tác, lúc nào, bởi ai" — và view bỏ qua nó.
-- Lịch sử vẫn đọc được đủ: đã bấm, rồi đã rút lại, cả hai đều có tên người.
--
-- KHÔNG dùng một dòng "phủ định" thêm vào sổ (kiểu bút toán đảo). Nghe thì
-- thuần khiết hơn, nhưng mọi câu `NOT EXISTS` trong view sẽ phải đếm cặp
-- ghi/huỷ để biết cái nào còn hiệu lực — mười nhánh, mỗi nhánh một câu con, và
-- chỉ cần một nhánh quên là một trạng thái sai âm thầm. Một lá cờ đọc được bằng
-- `IS NULL` thì mười nhánh nói cùng một câu.

ALTER TABLE public.tuong_tac_cskh
    ADD COLUMN IF NOT EXISTS huy_luc timestamptz,
    ADD COLUMN IF NOT EXISTS huy_boi_staff_id uuid
        REFERENCES public.staff(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.tuong_tac_cskh.huy_luc IS
    'Lần chạm này đã được hoàn tác lúc nào. Dòng KHÔNG bị xoá — nó chỉ thôi '
    'được tính vào v_viec_cskh. NULL = còn hiệu lực.';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'tuong_tac_huy_du_doi'
    ) THEN
        -- Hoàn tác mà không biết ai hoàn thì không truy lại được — cùng khuôn
        -- với `hen_goi_lai_dong_du_doi` và `work_roster`.
        ALTER TABLE public.tuong_tac_cskh
            ADD CONSTRAINT tuong_tac_huy_du_doi
            CHECK ((huy_luc IS NULL) = (huy_boi_staff_id IS NULL));
    END IF;
END $$;

-- Chỉ mục cho đúng câu view hỏi: "còn dòng nào CÒN HIỆU LỰC của lịch hẹn này
-- với loại ấy không".
CREATE INDEX IF NOT EXISTS idx_tuong_tac_con_hieu_luc
    ON public.tuong_tac_cskh (appointment_id, loai)
    WHERE huy_luc IS NULL;

-- ---------------------------------------------------------------------------
-- Dựng lại `v_viec_cskh`: MỌI chỗ đọc sổ đều phải bỏ qua dòng đã hoàn tác
-- ---------------------------------------------------------------------------
-- Chép nguyên văn 20260810000008, thêm đúng `AND t.huy_luc IS NULL` vào bốn chỗ
-- đọc `tuong_tac_cskh`: `cham_cuoi` và ba câu `NOT EXISTS` (KQ_CHUA_GUI,
-- HOI_LY_DO_HUY, NHAC_HEN_MAI, CHO_XAC_NHAN).
--
-- Bỏ sót MỘT chỗ là một trạng thái không bao giờ mở lại được sau khi hoàn tác,
-- và nó hỏng trong im lặng — đúng loại lỗi mà file này sinh ra để chữa.
CREATE OR REPLACE VIEW public.v_viec_cskh
WITH (security_invoker = true) AS
WITH hom_nay AS (
    SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d
),
cham_cuoi AS (
    SELECT DISTINCT ON (t.appointment_id)
           t.appointment_id, t.ket_qua, t.xay_ra_luc
      FROM public.tuong_tac_cskh t
     WHERE t.appointment_id IS NOT NULL
       AND t.huy_luc IS NULL
     ORDER BY t.appointment_id, t.xay_ra_luc DESC
),
viec AS (
    SELECT a.clinic_id, a.clinic_patient_id, 'DA_CHECKIN' AS loai, 0 AS uu_tien,
           h.d AS han, a.id AS appointment_id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'DA_CHECKIN' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status = 'CHECKED_IN'

    UNION ALL

    SELECT r.clinic_id, r.clinic_patient_id, 'CHO_BAC_SI' AS loai, 1 AS uu_tien,
           (r.result_received_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               + l.so_ngay AS han, NULL::uuid AS appointment_id
      FROM public.lab_result r
      JOIN public.luat_cskh l ON l.clinic_id = r.clinic_id
                             AND l.loai_viec = 'CHO_BAC_SI' AND l.bat
     WHERE r.result_value IS NOT NULL
       AND r.requires_doctor_review AND r.reviewed_at IS NULL

    UNION ALL

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
                AND t.loai = 'TRA_KQ' AND t.xay_ra_luc >= r.created_at
                AND t.huy_luc IS NULL)

    UNION ALL

    SELECT r.clinic_id, r.clinic_patient_id, 'CHO_KQ_XN', 3,
           (coalesce(r.sample_collected_at, r.created_at)
                AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + l.so_ngay, NULL
      FROM public.lab_result r
      JOIN public.luat_cskh l ON l.clinic_id = r.clinic_id
                             AND l.loai_viec = 'CHO_KQ_XN' AND l.bat
     WHERE r.result_value IS NULL

    UNION ALL

    SELECT a.clinic_id, a.clinic_patient_id, 'GOI_LAI', 4,
           (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, a.id
      FROM public.appointment a
      JOIN cham_cuoi c ON c.appointment_id = a.id
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'GOI_LAI' AND l.bat
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                            'COMPLETED', 'CHECKED_IN')
       AND c.ket_qua IN ('CHUA_NGHE_MAY', 'KHONG_LIEN_LAC_DUOC', 'HEN_GOI_LAI')

    UNION ALL

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
              WHERE t.appointment_id = a.id AND t.loai = 'HOI_LY_DO_HUY'
                AND t.huy_luc IS NULL)

    UNION ALL

    SELECT g.clinic_id, g.clinic_patient_id, 'HEN_GOI_LAI', 6, g.ngay_goi, NULL
      FROM public.hen_goi_lai g
      JOIN public.luat_cskh l ON l.clinic_id = g.clinic_id
                             AND l.loai_viec = 'HEN_GOI_LAI' AND l.bat
     CROSS JOIN hom_nay h
     WHERE g.dong_luc IS NULL AND g.ngay_goi <= h.d

    UNION ALL

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
       AND (n.appointment_id IS NULL
            OR EXISTS (SELECT 1
                         FROM public.appointment a
                        WHERE a.id = n.appointment_id
                          AND a.status NOT IN ('CHECKED_IN', 'COMPLETED',
                                               'NO_SHOW', 'CANCELLED',
                                               'DOCTOR_DECLINED')))

    UNION ALL

    SELECT a.clinic_id, a.clinic_patient_id, 'NHAC_HEN_MAI', 8, h.d, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'NHAC_HEN_MAI' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                            'COMPLETED', 'CHECKED_IN')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = h.d + l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'NHAC_HEN'
                AND t.huy_luc IS NULL)

    UNION ALL

    SELECT a.clinic_id, a.clinic_patient_id, 'CHO_XAC_NHAN', 10,
           (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, a.id
      FROM public.appointment a
      JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                             AND l.loai_viec = 'CHO_XAC_NHAN' AND l.bat
     CROSS JOIN hom_nay h
     WHERE a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                            'COMPLETED', 'CHECKED_IN')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             BETWEEN h.d AND h.d + l.so_ngay
       AND NOT EXISTS (
             SELECT 1 FROM public.tuong_tac_cskh t
              WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH'
                AND t.huy_luc IS NULL)
)
SELECT v.clinic_id,
       v.clinic_patient_id,
       v.loai   AS trang_thai,
       l.nhan   AS nhan,
       v.uu_tien,
       v.han    AS han_xu_ly,
       (v.han < h.d) AS qua_han,
       v.appointment_id
  FROM viec v
  CROSS JOIN hom_nay h
  JOIN public.luat_cskh l
    ON l.clinic_id = v.clinic_id AND l.loai_viec = v.loai;

-- `da_xac_nhan` của v_trang_thai_cskh cũng đọc sổ; dòng đã hoàn tác không được
-- tính là "khách đã xác nhận".
CREATE OR REPLACE VIEW public.v_trang_thai_cskh
WITH (security_invoker = true) AS
WITH dem AS (
    SELECT clinic_id, clinic_patient_id,
           count(*) AS so_viec_mo,
           bool_or(qua_han) AS co_viec_qua_han
      FROM public.v_viec_cskh GROUP BY 1, 2
),
gap_nhat AS (
    SELECT DISTINCT ON (clinic_id, clinic_patient_id) *
      FROM public.v_viec_cskh
     ORDER BY clinic_id, clinic_patient_id, qua_han DESC, uu_tien, han_xu_ly
)
SELECT v.clinic_id,
       v.clinic_patient_id,
       v.trang_thai,
       v.nhan,
       v.han_xu_ly,
       v.qua_han,
       d.so_viec_mo,
       d.co_viec_qua_han,
       v.appointment_id,
       EXISTS (SELECT 1 FROM public.tuong_tac_cskh t
                WHERE t.appointment_id = v.appointment_id
                  AND t.khach_xac_nhan
                  AND t.huy_luc IS NULL) AS da_xac_nhan
  FROM gap_nhat v
  JOIN dem d ON d.clinic_id = v.clinic_id
            AND d.clinic_patient_id = v.clinic_patient_id;
