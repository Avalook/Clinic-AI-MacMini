-- PHẢN HỒI SAU DÙNG THUỐC (10/10/2026).
--
-- Khách: "CSKH ghi phản hồi sau dùng thuốc vào bước chăm sóc khách như đang làm.
-- Phản hồi nằm trong hồ sơ khách và quản lý khách hàng, bác sĩ mở hồ sơ là thấy."
--
-- Ghi vào CHÍNH sổ chăm sóc `tuong_tac_cskh` (không bảng mới): nó đã là nguồn của
-- "Tương tác gần nhất", dòng thời gian, hoàn tác (`huy_luc`) và tin NOTIFY
-- (`trg_notify_tuong_tac_cskh`). Thứ còn thiếu là MỘT cột: phản hồi nói về đơn
-- thuốc của LƯỢT nào — `appointment_id` không thay được (lượt vãng lai không có
-- lịch, và gắn lịch thì dòng này lọt vào `cham_cuoi` của v_trang_thai_cskh).
--
-- ON DELETE CASCADE chứ không SET NULL: ràng buộc dưới đây đòi phản hồi thuốc có
-- lượt, nên SET NULL sẽ chặn mọi lần xoá lượt (dọn khách thử). Nội dung bắt buộc
-- ép ở service, KHÔNG ở đây: bản che dữ liệu staging xoá `noi_dung` hằng đêm.

ALTER TABLE public.tuong_tac_cskh
    ADD COLUMN IF NOT EXISTS visit_id uuid
        REFERENCES public.visit(visit_id) ON DELETE CASCADE;

COMMENT ON COLUMN public.tuong_tac_cskh.visit_id IS
    'Lượt khám mà lần chạm nói tới — hiện chỉ PHAN_HOI_THUOC dùng (lượt có đơn).';

ALTER TABLE public.tuong_tac_cskh
    DROP CONSTRAINT IF EXISTS tuong_tac_cskh_loai_check;
ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_cskh_loai_check CHECK (loai IN (
        'XAC_NHAN_LICH', 'NHAC_HEN', 'CHECK_XN', 'TRA_KQ',
        'HOI_LY_DO_HUY', 'HOI_THAM', 'KHAC',
        'CHECK_IN', 'CHECK_OUT', 'THANH_TOAN', 'MUA_THUOC',
        'PHAN_HOI_THUOC'));

ALTER TABLE public.tuong_tac_cskh
    DROP CONSTRAINT IF EXISTS tuong_tac_phan_hoi_thuoc_co_luot;
ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_phan_hoi_thuoc_co_luot CHECK (
        loai <> 'PHAN_HOI_THUOC' OR visit_id IS NOT NULL
    );

CREATE INDEX IF NOT EXISTS idx_tuong_tac_theo_luot
    ON public.tuong_tac_cskh (clinic_id, visit_id)
    WHERE visit_id IS NOT NULL;
