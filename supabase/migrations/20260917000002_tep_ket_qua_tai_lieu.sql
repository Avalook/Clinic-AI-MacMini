-- Tệp kết quả nhận thêm TÀI LIỆU Office (DOCX, XLSX) — tự kiểm 16/09/2026.
--
-- Tuyền: "check cả upload file video, ảnh đã khám, cả pdf, docx này kia thử
-- hết". Phiếu kết quả của đối tác và biên bản thủ thuật hay gửi dạng Word; từ
-- chối chúng thì người dùng chụp màn hình rồi gửi ảnh — mất chữ, không tìm được.
--
-- Chỉ nới ràng buộc loại tệp. Kiểu thật vẫn kiểm bằng nội dung ở máy chủ
-- (`media_service.sniff_ket_qua`), không bằng đuôi tên.

BEGIN;

DO $$
DECLARE
    ten text;
BEGIN
    FOR ten IN
        SELECT conname FROM pg_constraint
         WHERE conrelid = 'public.tep_ket_qua'::regclass AND contype = 'c'
           AND pg_get_constraintdef(oid) LIKE '%loai_tep%'
    LOOP
        EXECUTE format('ALTER TABLE public.tep_ket_qua DROP CONSTRAINT %I', ten);
    END LOOP;
END $$;

ALTER TABLE public.tep_ket_qua
    ADD CONSTRAINT tep_ket_qua_loai_tep_check
    CHECK (loai_tep IN ('ANH', 'VIDEO', 'PDF', 'TAI_LIEU'));

COMMIT;
