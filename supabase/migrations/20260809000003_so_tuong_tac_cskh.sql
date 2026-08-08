-- Sổ tương tác CSKH — mỗi dòng là MỘT SỰ VIỆC ĐÃ XẢY RA.
--
-- MÀN "QUẢN LÝ KHÁCH HÀNG" ĐANG KHÔNG BIẾT GÌ CẢ. Ba cột "Tương tác gần nhất",
-- "Bước tiếp theo", "Hạn xử lý" hiển thị "—" cho mọi khách, và không phải vì
-- chưa ai gọi. Đo trên bản thật hôm nay: `cskh_action` có 0 dòng, và hai câu
-- INSERT duy nhất ghi vào bảng đó (cskh_service.py:121, clinical_sign_service
-- .py:445) đều KHÔNG có `step` lẫn `deadline_at` trong danh sách cột — tức là
-- hai cột ấy vĩnh viễn NULL kể cả khi bảng đầy.
--
-- Còn nút "📞 Gọi nhắc hẹn" thì là một thẻ `<a href="tel:…">`. Nó quay số, và
-- không để lại gì. Gọi xong không ai biết đã gọi; gọi lần hai không ai biết là
-- lần hai.
--
-- VÌ SAO KHÔNG DÙNG LẠI BA BẢNG ĐANG CÓ.
--
--   · `cskh_action` là hàng nhập khẩu từ Notion: `source_ref` UNIQUE NOT NULL,
--     người ghi là một chuỗi tên gõ tay (`created_by_text`). Không giao việc
--     được, không lọc theo người được.
--   · `cskh_log` là bản chụp một tháng từ file cũ — mỗi bệnh nhân một dòng với
--     hai chục cột phẳng, không phải một dòng cho mỗi lần gọi.
--   · `nhac_tai_kham` là VIỆC mời tái khám: mỗi việc chứa đúng MỘT cuộc gọi
--     (`nguoi_goi_staff_id`, `ket_qua`). Gọi lần hai thì ghi đè lần một.
--
-- Cái thiếu là một cuốn sổ CHỈ THÊM: gọi bao nhiêu lần thì bấy nhiêu dòng.
--
-- DÙNG LẠI BỘ TỪ ĐÃ CÓ, không đẻ bộ thứ ba. `ket_qua` lấy đúng bốn giá trị của
-- `cskh_log.ket_qua` và `nhac_tai_kham.ket_qua` (20260807000002/000005). Hai
-- bộ từ cho cùng một khái niệm là hai bản báo cáo không cộng lại được.

CREATE TABLE IF NOT EXISTS public.tuong_tac_cskh (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    clinic_patient_id uuid NOT NULL
        REFERENCES public.patient(clinic_patient_id) ON DELETE CASCADE,
    -- Gắn với lịch hẹn nào (nếu có). Việc "xác nhận lịch" và "nhắc hẹn" luôn
    -- nói về MỘT lịch cụ thể; thiếu cột này thì không phân biệt được đã gọi cho
    -- lịch tuần trước hay lịch tuần sau.
    appointment_id uuid REFERENCES public.appointment(id) ON DELETE SET NULL,

    loai  text NOT NULL CHECK (loai IN (
        'XAC_NHAN_LICH',   -- gọi trước ngày khám để hỏi khách có đến không
        'NHAC_HEN',        -- gọi nhắc khách đã xác nhận
        'CHECK_XN',        -- hỏi đơn vị xét nghiệm đã có kết quả chưa
        'TRA_KQ',          -- gọi trả kết quả cho khách
        'HOI_LY_DO_HUY',   -- gọi lại sau khi khách huỷ
        'HOI_THAM',        -- gọi hỏi thăm (sau thủ thuật, sau sinh…)
        'KHAC')),

    kenh  text NOT NULL CHECK (kenh IN (
        'GOI', 'ZALO', 'SMS', 'TRUC_TIEP', 'KHONG_LIEN_HE')),

    ket_qua text NOT NULL CHECK (ket_qua IN (
        'DA_LIEN_HE', 'CHUA_NGHE_MAY', 'CAN_BAC_SI', 'TU_CHOI', 'BO_QUA')),

    -- Khách có nói sẽ đến không. Chỉ có nghĩa với hai loại việc hỏi điều đó;
    -- NULL ở mọi loại khác, và ràng buộc bên dưới giữ cho nó đúng thế.
    khach_xac_nhan boolean,

    noi_dung text,

    -- LẤY TỪ PHIÊN ĐĂNG NHẬP, KHÔNG NHẬN TỪ CLIENT. `cskh_action` học bài này
    -- bằng cách khác: nó lưu người ghi thành một chuỗi tên tự do, và giờ không
    -- ai lọc được "những cuộc gọi của chị Điều".
    nhan_vien_staff_id uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,

    xay_ra_luc timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),

    -- "Bỏ qua" và "không liên hệ" là HAI NỬA CỦA MỘT VIỆC. Tách ra được thì sẽ
    -- có dòng ghi "đã gọi điện" mà kết quả là "bỏ qua". Khuôn lấy từ
    -- nhac_tai_kham (20260807000005).
    CONSTRAINT tuong_tac_bo_qua_thi_khong_lien_he
        CHECK ((ket_qua = 'BO_QUA') = (kenh = 'KHONG_LIEN_HE')),

    CONSTRAINT tuong_tac_xac_nhan_dung_cho
        CHECK (khach_xac_nhan IS NULL
               OR loai IN ('XAC_NHAN_LICH', 'NHAC_HEN')),

    -- Ba loại này luôn nói về một lịch hẹn cụ thể.
    CONSTRAINT tuong_tac_can_lich_hen
        CHECK (loai NOT IN ('XAC_NHAN_LICH', 'NHAC_HEN', 'HOI_LY_DO_HUY')
               OR appointment_id IS NOT NULL)
);

COMMENT ON TABLE public.tuong_tac_cskh IS
    'Sổ CHỈ THÊM: mỗi lần CSKH chạm tới khách là một dòng. Nguồn của cột '
    '"Tương tác gần nhất" và của dòng thời gian trên màn Quản lý khách hàng.';

CREATE INDEX IF NOT EXISTS idx_tuong_tac_khach
    ON public.tuong_tac_cskh (clinic_id, clinic_patient_id, xay_ra_luc DESC);

-- Câu hỏi nóng nhất của màn: "lịch này đã gọi xác nhận chưa". Trạng thái suy ra
-- từ sự VẮNG MẶT của một dòng, nên nó chạy trên mọi lượt tải trang.
CREATE INDEX IF NOT EXISTS idx_tuong_tac_theo_lich
    ON public.tuong_tac_cskh (clinic_id, appointment_id, loai)
    WHERE appointment_id IS NOT NULL;

ALTER TABLE public.tuong_tac_cskh ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'tuong_tac_cskh'
           AND policyname = 'tuong_tac_cskh_select_own_clinic'
    ) THEN
        CREATE POLICY tuong_tac_cskh_select_own_clinic
            ON public.tuong_tac_cskh
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

-- Chỉ ĐỌC cho client. Ghi đi qua FastAPI (ADR-0012): client tự ghi được nghĩa
-- là client tự khai được "đã gọi rồi" cho một cuộc gọi chưa hề xảy ra.
GRANT SELECT ON public.tuong_tac_cskh TO authenticated;
