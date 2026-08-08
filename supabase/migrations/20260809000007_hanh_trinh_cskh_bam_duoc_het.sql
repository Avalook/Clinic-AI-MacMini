-- CSKH bấm được TRỌN hành trình của khách — và chỗ ghi phản hồi (DoD mục 3).
--
-- Quang (08/08/2026): *"cskh đặt lịch rồi này, xong gọi xác nhận trước 7 ngày
-- này, gọi nhắc hẹn này, khách đến thì check-in cho khách này, hỏi đơn vị xét
-- nghiệm, gọi để trả kết quả, khách checkout, khách đã thanh toán, khách đã
-- mua thuốc… tất cả là các nút và thao tác được thật nhé, vì sản phẩm MVP này
-- là cskh thao tác được hết mà."*
--
-- Sổ tương tác hiện chỉ biết CUỘC GỌI. Bốn mốc mới là VIỆC XẢY RA TẠI QUẦY:
-- khách bước vào, khách rời đi, khách trả tiền, khách lấy thuốc. Chúng vào
-- cùng một sổ vì cùng một câu hỏi: "khách này đã đi tới đâu, ai ghi, mấy giờ".
--
-- Riêng check-in và check-out KHÔNG chỉ là dòng sổ: service sẽ chạy đúng hành
-- động thật trên lịch hẹn (checkin → mở lượt khám + vào hàng đợi; complete →
-- đóng trạng thái khám). Dòng sổ là dấu vết; trạng thái lịch là sự thật mà cả
-- hệ thống còn lại nhìn vào.

-- ── Bốn mốc quầy + một kết quả "ghi nhận" ──────────────────────────────────
ALTER TABLE public.tuong_tac_cskh
    DROP CONSTRAINT IF EXISTS tuong_tac_cskh_loai_check;
ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_cskh_loai_check CHECK (loai IN (
        'XAC_NHAN_LICH', 'NHAC_HEN', 'CHECK_XN', 'TRA_KQ',
        'HOI_LY_DO_HUY', 'HOI_THAM', 'KHAC',
        -- Mốc tại quầy (08/08/2026). KHÔNG phải cuộc gọi.
        'CHECK_IN', 'CHECK_OUT', 'THANH_TOAN', 'MUA_THUOC'));

ALTER TABLE public.tuong_tac_cskh
    DROP CONSTRAINT IF EXISTS tuong_tac_cskh_ket_qua_check;
ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_cskh_ket_qua_check CHECK (ket_qua IN (
        'DA_LIEN_HE', 'CHUA_NGHE_MAY', 'KHONG_LIEN_LAC_DUOC', 'HEN_GOI_LAI',
        'CAN_BAC_SI', 'TU_CHOI', 'BO_QUA',
        -- Mốc quầy không có "kết quả cuộc gọi" — nó chỉ có "đã xảy ra".
        -- Cho mốc mượn DA_LIEN_HE là bịa ra một cuộc gọi chưa từng có.
        'GHI_NHAN'));

-- Mốc quầy ⇔ GHI_NHAN ⇔ kênh trực tiếp. Ba mặt của cùng một sự việc; tách rời
-- được thì sẽ có dòng "gọi điện — ghi nhận" hoặc "check-in — chưa nghe máy".
ALTER TABLE public.tuong_tac_cskh
    DROP CONSTRAINT IF EXISTS tuong_tac_moc_quay_dung_bo;
ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_moc_quay_dung_bo CHECK (
        (loai IN ('CHECK_IN', 'CHECK_OUT', 'THANH_TOAN', 'MUA_THUOC'))
        = (ket_qua = 'GHI_NHAN')
    );
ALTER TABLE public.tuong_tac_cskh
    DROP CONSTRAINT IF EXISTS tuong_tac_moc_quay_truc_tiep;
ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_moc_quay_truc_tiep CHECK (
        ket_qua <> 'GHI_NHAN' OR kenh = 'TRUC_TIEP'
    );

-- Check-in/check-out luôn nói về MỘT lịch hẹn — chúng còn đổi trạng thái của
-- chính lịch đó. Thanh toán / mua thuốc thì không bắt buộc: khách có thể ghé
-- mua thuốc mà không có lịch nào đang mở.
ALTER TABLE public.tuong_tac_cskh
    DROP CONSTRAINT IF EXISTS tuong_tac_can_lich_hen;
ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_can_lich_hen CHECK (
        loai NOT IN ('XAC_NHAN_LICH', 'NHAC_HEN', 'HOI_LY_DO_HUY',
                     'CHECK_IN', 'CHECK_OUT')
        OR appointment_id IS NOT NULL
    );


-- ── Phản hồi / khiếu nại của khách (DoD mục 3) ─────────────────────────────
--
-- *"Có chỗ ghi lại phản hồi khách hàng sau khám, các vấn đề khách hàng claim,
-- tình trạng xử lý…"* — ba vế: NỘI DUNG, LOẠI, và VÒNG ĐỜI XỬ LÝ.
--
-- Không nhồi vào tuong_tac_cskh: sổ đó là dòng chảy một chiều của các lần
-- chạm, còn một khiếu nại là một VIỆC MỞ — nó có trạng thái, có người xử lý,
-- và ba tuần sau vẫn phải tìm lại được theo "cái nào chưa xong".
CREATE TABLE IF NOT EXISTS public.phan_hoi_khach (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    clinic_patient_id uuid NOT NULL
        REFERENCES public.patient(clinic_patient_id) ON DELETE CASCADE,

    loai text NOT NULL CHECK (loai IN (
        'KHEN',       -- khách khen — cũng đáng ghi: nó nói khâu nào đang đúng
        'GOP_Y',      -- góp ý nhẹ, không đòi hỏi xử lý gấp
        'KHIEU_NAI'   -- khách phàn nàn / claim — phải có người xử và chốt lại
    )),
    noi_dung text NOT NULL,

    trang_thai text NOT NULL DEFAULT 'MOI'
        CHECK (trang_thai IN ('MOI', 'DANG_XU_LY', 'DA_XU_LY')),
    -- Xử lý thế nào — bắt buộc khi đóng. "Đã xử lý" mà không nói xử lý ra sao
    -- thì ba tuần sau khách gọi lại và không ai biết lần trước đã hứa gì.
    huong_xu_ly text,

    nguoi_tiep_nhan_staff_id uuid NOT NULL
        REFERENCES public.staff(id) ON DELETE RESTRICT,
    xu_ly_boi_staff_id uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    xu_ly_luc  timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT phan_hoi_dong_du_doi CHECK (
        (trang_thai = 'DA_XU_LY')
        = (xu_ly_luc IS NOT NULL AND xu_ly_boi_staff_id IS NOT NULL
           AND huong_xu_ly IS NOT NULL)
    )
);

COMMENT ON TABLE public.phan_hoi_khach IS
    'Phản hồi / khiếu nại của khách và vòng đời xử lý (DoD CSKH mục 3).';

CREATE INDEX IF NOT EXISTS idx_phan_hoi_khach_mo
    ON public.phan_hoi_khach (clinic_id, trang_thai, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_phan_hoi_theo_khach
    ON public.phan_hoi_khach (clinic_id, clinic_patient_id, created_at DESC);

ALTER TABLE public.phan_hoi_khach ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'phan_hoi_khach'
           AND policyname = 'phan_hoi_khach_select_own_clinic'
    ) THEN
        CREATE POLICY phan_hoi_khach_select_own_clinic ON public.phan_hoi_khach
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

-- Chỉ ĐỌC cho client (ADR-0012). Ghi đi qua FastAPI: người ghi và người xử lý
-- lấy từ phiên đăng nhập, không nhận từ trình duyệt.
GRANT SELECT ON public.phan_hoi_khach TO authenticated;
