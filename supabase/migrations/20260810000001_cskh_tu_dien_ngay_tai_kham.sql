-- CSKH tự điền ngày tái khám — và hai mốc gọi sinh ra từ đó.
--
-- VÌ SAO. Hôm nay việc gọi nhắc tái khám lượt 1 CHỈ sinh ra từ một chỗ:
-- `soap_plan #>> '{tai_kham,ngay}'` của một phiếu khám ĐÃ CHỐT (FINALIZED /
-- AMENDED) — xem sinh_viec_nhac_tai_kham() ở 20260807000005. Nghĩa là chừng
-- nào bác sĩ chưa gõ ngày tái khám vào phiếu và chưa chốt phiếu, thì:
--
--   · không có dòng nào trong `nhac_tai_kham`,
--   · nên không có việc nào trong v_trang_thai_cskh,
--   · nên màn Quản lý khách hàng KHÔNG hề biết người này cần gọi lại.
--
-- Mà CSKH thì biết: khách vừa nói qua điện thoại "tháng sau em quay lại". Câu
-- ấy hiện không có chỗ nào để ghi xuống, nên nó nằm trong đầu người trực và
-- mất khi đổi ca. Đây là chỗ Quang chỉ vào ngày 09/08/2026 (ô đỏ dưới "Phản
-- hồi của khách"): "nhắc tái khám CSKH tự điền vào giai đoạn này, cũng đếm
-- thời gian và trước 7 ngày, trước 1 ngày nhớ có action để alo họ".
--
-- HAI MỐC, KHÔNG PHẢI MỘT.
--   T−7 → gọi MỜI ĐẶT LỊCH  (lượt 1, cùng nghĩa với lượt 1 tự sinh)
--   T−1 → gọi NHẮC ĐI KHÁM  (lượt 2)
--
-- Lượt 2 tự sinh hiện đặt `han_goi = ngay_hen` (gọi sáng ngày hẹn) và luôn gắn
-- một lịch hẹn. Việc CSKH tự điền thì CHƯA có lịch hẹn nào — đó chính là lý do
-- phải gọi mời đặt. Nên hai thứ phải nới ra:
--   1. `nhac_tai_kham_luot2_can_lich` không còn đúng cho nguồn CSKH_NHAP;
--   2. phải phân biệt được việc nào do máy suy ra, việc nào do người gõ —
--      không phân biệt thì lần sau không ai biết con số đến từ đâu.

ALTER TABLE public.nhac_tai_kham
    ADD COLUMN IF NOT EXISTS nguon text NOT NULL DEFAULT 'PHIEU_KHAM';

ALTER TABLE public.nhac_tai_kham
    ADD COLUMN IF NOT EXISTS tao_boi_staff_id uuid
        REFERENCES public.staff (id) ON DELETE SET NULL;

-- Ghi chú của CHÍNH lời hẹn ("khách nói tháng sau quay lại khám lại tuyến
-- giáp"), tách khỏi `ghi_chu` — cột kia là ghi chú của CUỘC GỌI và bị ghi đè
-- khi CSKH ghi kết quả. Gộp hai thứ vào một ô là mất lý do vì sao có việc này.
ALTER TABLE public.nhac_tai_kham
    ADD COLUMN IF NOT EXISTS ly_do text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'nhac_tai_kham_nguon_check'
    ) THEN
        ALTER TABLE public.nhac_tai_kham
            ADD CONSTRAINT nhac_tai_kham_nguon_check
            CHECK (nguon IN ('PHIEU_KHAM', 'CSKH_NHAP'));
    END IF;
END $$;

-- NỚI RÀNG BUỘC LƯỢT 2, KHÔNG BỎ NÓ.
--
-- Việc do máy suy ra từ một lịch hẹn thì VẪN phải có lịch hẹn — bỏ hẳn ràng
-- buộc là mở cửa cho những dòng lượt-2 mồ côi mà không ai phát hiện. Chỉ nguồn
-- CSKH_NHAP mới được phép chưa có lịch, và đó là đúng định nghĩa của nó.
ALTER TABLE public.nhac_tai_kham
    DROP CONSTRAINT IF EXISTS nhac_tai_kham_luot2_can_lich;

ALTER TABLE public.nhac_tai_kham
    ADD CONSTRAINT nhac_tai_kham_luot2_can_lich
    CHECK (luot_goi <> 2
           OR appointment_id IS NOT NULL
           OR nguon = 'CSKH_NHAP');

-- Chỉ nguồn CSKH_NHAP mới ghi được người tạo — việc máy suy ra thì không có
-- ai "tạo" nó, và để trống ở đó là đúng chứ không phải thiếu dữ liệu.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'nhac_tai_kham_nguoi_tao_dung_nguon'
    ) THEN
        ALTER TABLE public.nhac_tai_kham
            ADD CONSTRAINT nhac_tai_kham_nguoi_tao_dung_nguon
            CHECK (tao_boi_staff_id IS NULL OR nguon = 'CSKH_NHAP');
    END IF;
END $$;

COMMENT ON COLUMN public.nhac_tai_kham.nguon IS
    'PHIEU_KHAM = máy suy từ soap_plan.tai_kham.ngay của phiếu đã chốt; '
    'CSKH_NHAP = CSKH gõ tay ngày tái khám ở vùng làm việc khách hàng.';
COMMENT ON COLUMN public.nhac_tai_kham.ly_do IS
    'Vì sao có lời hẹn tái khám này (CSKH gõ). Khác ghi_chu — cột kia là ghi '
    'chú của CUỘC GỌI và bị ghi đè khi ghi kết quả.';

-- ---------------------------------------------------------------------------
-- Nhãn cho hai loại việc, để màn CSKH gọi tên chúng
-- ---------------------------------------------------------------------------
-- `v_trang_thai_cskh` JOIN `luat_cskh` để lấy nhãn: thiếu dòng luật là việc
-- KHÔNG hiện ra chút nào (INNER JOIN). Hai loại này đã có từ 20260809000005,
-- nhưng phòng khám mới cài đặt thì chưa — nên bổ sung cho đủ, idempotent.
INSERT INTO public.luat_cskh (clinic_id, loai_viec, nhan, so_ngay, bat)
SELECT c.id, v.loai_viec, v.nhan, v.so_ngay, true
  FROM public.clinic c
 CROSS JOIN (VALUES
        ('MOI_TAI_KHAM', 'Mời tái khám', 7),
        ('NHAC_DI_KHAM', 'Nhắc đi khám', 1)
     ) AS v(loai_viec, nhan, so_ngay)
ON CONFLICT DO NOTHING;
