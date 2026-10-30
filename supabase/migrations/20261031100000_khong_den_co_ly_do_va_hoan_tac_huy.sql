-- KHÔNG ĐẾN CÓ LÝ DO + HOÀN TÁC HUỶ / KHÔNG ĐẾN (30/10/2026).
--
-- Nhân sự báo "huỷ lịch không có chỗ ghi lý do". Ở nút "Không đến" thì đúng
-- thật: bấm là ghi luôn, không lý do, và KHÔNG có đường quay lại — trái luật
-- "mọi thao tác nhân viên bấm phải hoàn tác được" (Tuyền 01/10/2026). Huỷ lịch
-- có lý do nhưng cũng không hoàn tác được.
--
-- 1. LÝ DO KHÔNG ĐẾN DÙNG CHUNG CỘT với lý do huỷ (`ly_do_huy_ma` +
--    `cancellation_reason`), thêm ba mã riêng của khâu "tới giờ mà khách không
--    tới". `KHAC` dùng chung (ràng buộc "Khác thì phải viết" áp luôn). Danh mục
--    vẫn MỘT nguồn: `LY_DO_HUY` (booking_service.py) = `lib/ly-do-huy.ts` = CHECK
--    dưới đây — bài chống lệch `test_ly_do_huy_drift.py`.
--
--    KHÔNG ép "không đến phải có lý do" ở database (khác `appointment_huy_phai_
--    co_ly_do`): đây không phải bất biến có tranh chấp, và dữ liệu thử / mô
--    phỏng chèn thẳng NO_SHOW. Máy chủ bắt chọn lý do ở `_build_patch`.
--
-- 2. TRẠNG THÁI TRƯỚC KHI HUỶ — để hoàn tác trả lịch về ĐÚNG chỗ cũ (lịch cũ
--    SCHEDULED vẫn về SCHEDULED). NULL (dữ liệu trước hôm nay) → về CONFIRMED,
--    trạng thái mọi lịch mới đặt.
--
-- 3. VẾT HOÀN TÁC — mỗi lần mở lại một dòng, chỉ thêm: lý do cũ RỜI trạng thái
--    hiện hành của lịch nhưng nằm lại đây, cùng ai mở lại, lúc nào.
--
-- Chạy lại được.

ALTER TABLE public.appointment
    DROP CONSTRAINT IF EXISTS appointment_ly_do_huy_ma_check;

ALTER TABLE public.appointment
    ADD CONSTRAINT appointment_ly_do_huy_ma_check
    CHECK (ly_do_huy_ma IS NULL
           OR ly_do_huy_ma IN ('BAO_KHI_XAC_NHAN',
                               'BAO_KHI_NHAC_HEN',
                               'BAO_VAO_GIO_KHAM',
                               'DAT_TRUNG',
                               'BAC_SI_DOI_LICH',
                               'KHONG_LIEN_LAC_DUOC',
                               'KHACH_BAO_BAN',
                               'QUEN_LICH',
                               'KHAC'));

COMMENT ON COLUMN public.appointment.ly_do_huy_ma IS
    'Mã lý do HUỶ hoặc KHÔNG ĐẾN (cùng cột, phân biệt bằng status). Huỷ: ba mã '
    'BAO_* là BA THỜI ĐIỂM khách báo không đến; DAT_TRUNG dọn lịch trùng; '
    'BAC_SI_DOI_LICH phòng khám huỷ vì ca bác sĩ đổi. Không đến: '
    'KHONG_LIEN_LAC_DUOC, KHACH_BAO_BAN, QUEN_LICH. KHAC = tự viết (cả hai). '
    'Danh mục phải khớp LY_DO_HUY ở booking_service.py và lib/ly-do-huy.ts.';

ALTER TABLE public.appointment
    ADD COLUMN IF NOT EXISTS trang_thai_truoc_huy text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'appointment_trang_thai_truoc_huy_hop_le'
    ) THEN
        ALTER TABLE public.appointment
            ADD CONSTRAINT appointment_trang_thai_truoc_huy_hop_le
            CHECK (trang_thai_truoc_huy IS NULL
                   OR trang_thai_truoc_huy IN ('SCHEDULED', 'CSKH_CONFIRMED',
                                               'CONFIRMED', 'CHECKED_IN'));
    END IF;
END $$;

COMMENT ON COLUMN public.appointment.trang_thai_truoc_huy IS
    'Trạng thái của lịch NGAY TRƯỚC lần huỷ / không đến gần nhất — hoàn tác trả '
    'về đây. NULL = huỷ trước 31/10/2026 (hoàn tác về CONFIRMED) hoặc chưa huỷ.';

CREATE TABLE IF NOT EXISTS public.appointment_hoan_tac_huy (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id             uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    appointment_id        uuid NOT NULL REFERENCES public.appointment (id)
                              ON DELETE CASCADE,
    tu_trang_thai         text NOT NULL CHECK (tu_trang_thai IN ('CANCELLED', 'NO_SHOW')),
    ve_trang_thai         text NOT NULL,
    -- Lý do của lần huỷ / không đến vừa rút lại — rời `appointment`, nằm lại đây.
    ly_do_huy_ma          text,
    ly_do_chu             text,
    huy_luc               timestamptz,
    huy_boi_staff_id      uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    hoan_tac_boi_staff_id uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    hoan_tac_luc          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_appointment_hoan_tac_huy_lich
    ON public.appointment_hoan_tac_huy (clinic_id, appointment_id, hoan_tac_luc);

COMMENT ON TABLE public.appointment_hoan_tac_huy IS
'Mỗi lần mở lại một lịch đã huỷ / không đến (hoàn tác): từ trạng thái nào về '
'trạng thái nào, lý do cũ, ai hoàn tác, lúc nào (30/10/2026). Chỉ thêm.';

ALTER TABLE public.appointment_hoan_tac_huy ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS appointment_hoan_tac_huy_select_own_clinic
    ON public.appointment_hoan_tac_huy;
CREATE POLICY appointment_hoan_tac_huy_select_own_clinic
    ON public.appointment_hoan_tac_huy
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.appointment_hoan_tac_huy TO service_role;
