-- Lịch trực đang nói sai: 390 dòng ghi BÁC SĨ đứng ở TRẠM PHỤ.
--
-- Mở màn "Sửa lịch làm việc" trên bản thật hôm nay sẽ thấy những dòng như
--   "BS THÀNH · Phụ BS (khám + thuốc) / Chạy ngoài"
--   "BS THIỆP · Phụ BS (khám + thuốc) + đánh SÂ"
-- Bác sĩ tự phụ chính mình. Không ai xếp ca như thế cả.
--
-- GỐC. File Excel "BẢNG LÀM VIỆC" có mỗi trạm phụ một cột, và Ô ĐẦU CỘT ghi
-- TRẠM ẤY PHỤC VỤ BÁC SĨ NÀO; các ô dưới mới là người thật đứng ở đó. Bản nạp
-- lịch (fixtures/lich_lam_viec_tuan_mau.sql) đọc cả cột thành người, nên ô đầu
-- cột biến thành một ca trực của bác sĩ.
--
-- ĐO TRƯỚC KHI SỬA (prod 08/08/2026, work_roster 2340 dòng):
--   · bác sĩ ở trạm KHÁC 'LICH_KHAM'            : 390 dòng
--   · trong đó sort = 0                          : 390  ← toàn bộ
--   · bác sĩ ở trạm phụ mà sort <> 0             : 0    ← không có ngoại lệ
--   · mỗi ô (ngày, ca, trạm) có bao nhiêu bác sĩ : đúng 1, cả 390 ô
--   · ô có bác sĩ mà KHÔNG có người phụ thật     : 0    ← không mất ai
--   · tổng số ca 'Lịch khám'                     : 390  ← khớp 1-1
--
-- Khớp 1-1 với số ca khám là thứ chốt hạ: cứ mỗi ca bác sĩ ngồi khám thì sinh
-- đúng một dòng phụ ma. Đó là một cột bị đọc nhầm, không phải người làm hai việc.
--
-- KHÔNG XOÁ TRẮNG. "Trạm này hôm nay phục vụ bác sĩ nào" là thông tin THẬT và
-- có ích — điều dưỡng cần biết mình đứng với ai. Nên chuyển nó sang một cột nói
-- đúng nghĩa, rồi mới bỏ dòng ma đi.

ALTER TABLE public.work_roster
    ADD COLUMN IF NOT EXISTS bac_si_phu_trach_id uuid
        REFERENCES public.staff(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.work_roster.bac_si_phu_trach_id IS
    'Ca trực này phục vụ bác sĩ nào (trạm phụ). NULL = không gắn với bác sĩ cụ thể.';

CREATE INDEX IF NOT EXISTS idx_work_roster_bac_si_phu_trach
    ON public.work_roster (bac_si_phu_trach_id)
    WHERE bac_si_phu_trach_id IS NOT NULL;

DO $$
DECLARE
    v_ma          integer;
    v_ngoai_le    integer;
    v_o_mat_nguoi integer;
    v_chuyen      integer;
    v_xoa         integer;
BEGIN
    -- Đếm lại NGAY TẠI ĐÂY thay vì tin con số ghi trong chú thích. Migration
    -- này chạy trên máy khác, tháng khác, và có thể sau khi ai đó đã sửa tay.
    SELECT count(*) INTO v_ma
      FROM public.work_roster r JOIN public.staff s ON s.id = r.staff_id
     WHERE r.station <> 'LICH_KHAM' AND s.primary_department = 'DOCTOR';

    IF v_ma = 0 THEN
        RAISE NOTICE 'Không có dòng ma nào — bỏ qua.';
        RETURN;
    END IF;

    -- Nếu có bác sĩ ở trạm phụ mà sort <> 0 thì giả thuyết "ô đầu cột" SAI ở
    -- dữ liệu này, và xoá đi là xoá ca trực có thật của người ta. Dừng lại.
    SELECT count(*) INTO v_ngoai_le
      FROM public.work_roster r JOIN public.staff s ON s.id = r.staff_id
     WHERE r.station <> 'LICH_KHAM' AND s.primary_department = 'DOCTOR'
       AND r.sort <> 0;
    IF v_ngoai_le > 0 THEN
        RAISE EXCEPTION
            'Có % dòng bác sĩ ở trạm phụ với sort <> 0. Đây KHÔNG phải ô đầu cột — '
            'dừng lại thay vì xoá nhầm ca trực thật.', v_ngoai_le;
    END IF;

    -- Ô nào chỉ có bác sĩ mà không có người phụ nào thì xoá là mất trắng cả ô.
    SELECT count(*) INTO v_o_mat_nguoi
      FROM (SELECT r.clinic_id, r.work_date, r.shift, r.station
              FROM public.work_roster r JOIN public.staff s ON s.id = r.staff_id
             WHERE r.station <> 'LICH_KHAM' AND s.primary_department = 'DOCTOR') o
     WHERE NOT EXISTS (
        SELECT 1 FROM public.work_roster r2 JOIN public.staff s2 ON s2.id = r2.staff_id
         WHERE r2.clinic_id = o.clinic_id AND r2.work_date = o.work_date
           AND r2.shift = o.shift AND r2.station = o.station
           AND s2.primary_department <> 'DOCTOR');
    IF v_o_mat_nguoi > 0 THEN
        RAISE EXCEPTION
            '% ô có bác sĩ nhưng không có người phụ nào. Xoá sẽ làm trống hẳn ô đó.',
            v_o_mat_nguoi;
    END IF;

    -- CHUYỂN NGHĨA: người phụ thật nhận tên bác sĩ mà ô của họ phục vụ.
    WITH header AS (
        SELECT r.clinic_id, r.work_date, r.shift, r.station, r.staff_id AS bac_si_id
          FROM public.work_roster r JOIN public.staff s ON s.id = r.staff_id
         WHERE r.station <> 'LICH_KHAM' AND s.primary_department = 'DOCTOR'
    )
    UPDATE public.work_roster r
       SET bac_si_phu_trach_id = h.bac_si_id
      FROM header h, public.staff s
     WHERE s.id = r.staff_id
       AND s.primary_department <> 'DOCTOR'
       AND r.clinic_id = h.clinic_id AND r.work_date = h.work_date
       AND r.shift = h.shift AND r.station = h.station;
    GET DIAGNOSTICS v_chuyen = ROW_COUNT;

    DELETE FROM public.work_roster r
     USING public.staff s
     WHERE s.id = r.staff_id
       AND r.station <> 'LICH_KHAM'
       AND s.primary_department = 'DOCTOR';
    GET DIAGNOSTICS v_xoa = ROW_COUNT;

    RAISE NOTICE 'Lịch trực: chuyển % dòng sang bac_si_phu_trach_id, xoá % dòng ma.',
        v_chuyen, v_xoa;
END $$;
