-- Tệp kết quả khám: ảnh siêu âm, video siêu âm, phiếu xét nghiệm.
--
-- DoD (Quang): *"Cần có chỗ upload kết quả siêu âm & xét nghiệm. Hình ảnh siêu
-- âm gồm ảnh + video. Cần gửi được cả video cho bệnh nhân."*
--
-- VÌ SAO KHÔNG DÙNG `ultrasound_record.image_refs`.
--
-- Cột đó là `text[]` — một mảng khoá tệp. Nó không mang được:
--   · KIỂU tệp (ảnh hay video — mà video cần đường phục vụ khác hẳn),
--   · KÍCH THƯỚC (không đếm được phòng khám đang dùng bao nhiêu đĩa),
--   · AI TẢI LÊN và LÚC NÀO,
--   · ĐÃ GỬI CHO KHÁCH CHƯA — đúng câu hỏi mà bước "Gọi trả kết quả" trên vùng
--     làm việc cần trả lời.
-- Và nó gắn cứng vào một bản ghi siêu âm ĐÃ CÓ. CSKH thì cầm một tệp trong tay
-- trước cả khi có bản ghi ấy — phiếu xét nghiệm từ đơn vị ngoài chẳng hạn.
--
-- Bảng này KHÔNG thay `image_refs`; nó phục vụ đường CSKH. Ảnh do kỹ thuật viên
-- gắn vào phiếu siêu âm vẫn đi đường cũ, và gộp hai đường lại là một việc riêng
-- cần một lần dọn dữ liệu, không phải một cột thêm vào.

CREATE TABLE IF NOT EXISTS public.tep_ket_qua (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    clinic_patient_id uuid NOT NULL
        REFERENCES public.patient(clinic_patient_id) ON DELETE CASCADE,
    -- Gắn với lần khám nào (nếu biết). Không bắt buộc: phiếu xét nghiệm từ đơn
    -- vị ngoài có thể về trước khi ai kịp nối nó vào một lịch cụ thể.
    appointment_id uuid REFERENCES public.appointment(id) ON DELETE SET NULL,

    -- KHOÁ TỆP TRÊN ĐĨA. Do hệ thống sinh (media_service.safe_path), không bao
    -- giờ lấy từ tên người tải lên: "../../../etc/passwd" là một tên tệp hợp lệ.
    khoa       text NOT NULL,
    -- Tên gốc — CHỈ để hiển thị, không bao giờ chạm đĩa.
    ten_hien_thi text,

    loai_tep   text NOT NULL CHECK (loai_tep IN ('ANH', 'VIDEO', 'PDF')),
    mime       text NOT NULL,
    so_byte    bigint NOT NULL CHECK (so_byte > 0),
    sha256     text NOT NULL,

    tai_len_boi_staff_id uuid NOT NULL
        REFERENCES public.staff(id) ON DELETE RESTRICT,
    tai_len_luc timestamptz NOT NULL DEFAULT now(),

    -- ĐÃ GỬI CHO KHÁCH CHƯA.
    --
    -- "Gửi" ở đây là NGƯỜI XÁC NHẬN ĐÃ GỬI, không phải hệ thống tự gửi:
    -- send_zalo.py luôn trả delivered=False, chưa nối kênh nào cả. Nhãn nút và
    -- tên cột phải nói đúng điều đó — nếu không, sáu tháng nữa sẽ có người tin
    -- rằng hệ thống tự gửi và không ai gọi cho khách nữa.
    gui_luc    timestamptz,
    gui_boi_staff_id uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    gui_kenh   text CHECK (gui_kenh IS NULL OR gui_kenh IN ('ZALO', 'SMS', 'TRUC_TIEP', 'EMAIL')),

    -- Ba nửa của một việc. Tách rời được thì sẽ có dòng "đã gửi" mà không biết
    -- ai gửi, gửi bằng gì — cùng khuôn với nhac_tai_kham và phan_hoi_khach.
    CONSTRAINT tep_ket_qua_gui_du_doi CHECK (
        (gui_luc IS NOT NULL) = (gui_boi_staff_id IS NOT NULL AND gui_kenh IS NOT NULL)
    ),
    -- Một khoá tệp chỉ được khai một lần. Hai dòng cùng khoá nghĩa là xoá một
    -- dòng sẽ để lại dòng kia trỏ vào tệp đã bị dọn.
    CONSTRAINT tep_ket_qua_khoa_duy_nhat UNIQUE (clinic_id, khoa)
);

COMMENT ON TABLE public.tep_ket_qua IS
    'Tệp kết quả CSKH tải lên (ảnh/video siêu âm, phiếu XN) và đã gửi cho khách chưa.';
COMMENT ON COLUMN public.tep_ket_qua.gui_luc IS
    'NGƯỜI xác nhận đã gửi, không phải hệ thống tự gửi — chưa nối kênh nào.';

CREATE INDEX IF NOT EXISTS idx_tep_ket_qua_khach
    ON public.tep_ket_qua (clinic_id, clinic_patient_id, tai_len_luc DESC);
-- Câu hỏi của bước "Gọi trả kết quả": còn tệp nào chưa gửi không.
CREATE INDEX IF NOT EXISTS idx_tep_ket_qua_chua_gui
    ON public.tep_ket_qua (clinic_id, clinic_patient_id)
    WHERE gui_luc IS NULL;

ALTER TABLE public.tep_ket_qua ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'tep_ket_qua'
           AND policyname = 'tep_ket_qua_select_own_clinic'
    ) THEN
        CREATE POLICY tep_ket_qua_select_own_clinic ON public.tep_ket_qua
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

-- Chỉ ĐỌC cho client. Ghi đi qua FastAPI: khoá tệp do hệ thống sinh, và người
-- tải lên lấy từ phiên đăng nhập.
GRANT SELECT ON public.tep_ket_qua TO authenticated;
