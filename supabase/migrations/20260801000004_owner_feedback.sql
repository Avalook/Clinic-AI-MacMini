-- Chỗ chủ sản phẩm báo lỗi bằng ảnh + lời, để lần sau đọc lại mà sửa.
--
-- Hiện tại vòng phản hồi là: Quang bấm, thấy sai, mô tả bằng chữ trong khung
-- chat, tôi đoán lại ngữ cảnh. Mất ngữ cảnh ở mỗi bước — không biết đang ở màn
-- nào, đăng nhập vai gì, lúc đó hệ đang ra sao. Bảng này giữ lại đúng những thứ
-- đó cùng với ảnh chụp, để lần sau mở ra là biết hỏng ở đâu.
--
-- KHÔNG CÓ clinic_id, cố ý: đây là phản hồi về PHẦN MỀM, không phải dữ liệu
-- lâm sàng của một phòng khám. Gắn clinic_id vào sẽ khiến gate đếm bảng tenant
-- tăng lên và ngụ ý nó thuộc về dữ liệu bệnh nhân, mà nó không.

CREATE TABLE IF NOT EXISTS public.owner_feedback (
    id           uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at   timestamptz DEFAULT now() NOT NULL,

    -- Ngữ cảnh tự thu, không bắt người dùng gõ lại.
    page_url     text,
    role_at_time text,
    staff_name   text,

    -- Nội dung
    comment      text NOT NULL,
    severity     text NOT NULL DEFAULT 'nhan_xet',
    image_path   text,          -- đường dẫn file trên đĩa, NULL nếu không có ảnh

    -- Vòng đời: chủ báo → tôi đọc → tôi sửa.
    status       text NOT NULL DEFAULT 'moi',
    resolved_at  timestamptz,
    resolved_note text,

    CONSTRAINT owner_feedback_pkey PRIMARY KEY (id),
    CONSTRAINT owner_feedback_has_comment CHECK (btrim(comment) <> ''),
    CONSTRAINT owner_feedback_severity_known
        CHECK (severity IN ('chan_dung', 'lam_sai', 'kho_hieu', 'nhan_xet')),
    CONSTRAINT owner_feedback_status_known
        CHECK (status IN ('moi', 'dang_sua', 'da_sua', 'bo_qua'))
);

COMMENT ON TABLE public.owner_feedback IS
  'Phản hồi của chủ sản phẩm khi dùng thử. Đọc bằng scripts/read-feedback.sh.';
COMMENT ON COLUMN public.owner_feedback.severity IS
  'chan_dung = không dùng tiếp được · lam_sai = chạy nhưng kết quả sai · '
  'kho_hieu = nhìn không hiểu màn này nói gì · nhan_xet = góp ý';

CREATE INDEX IF NOT EXISTS idx_owner_feedback_moi
    ON public.owner_feedback (created_at DESC) WHERE status = 'moi';

-- Không mở cho anon. Console chỉ chạy ở dev/staging và ghi bằng service role.
ALTER TABLE public.owner_feedback ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.owner_feedback FROM anon;
GRANT SELECT, INSERT, UPDATE ON public.owner_feedback TO service_role;
