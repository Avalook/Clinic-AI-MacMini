-- Một lần chạm phải nói được nó ĐÓNG trạng thái nào.
--
-- VÌ SAO. Timeline trạng thái ở màn Quản lý khách hàng tích xanh một node khi
-- tìm thấy dòng tương tác "ứng với" node ấy. Cách dò hiện nay là theo cột
-- `loai` — và nó KHÔNG phân biệt được, vì nhiều trạng thái khác hẳn nhau lại
-- ghi chung một loại:
--
--   loai = 'KHAC'     ← "chờ phản hồi chuyên môn", "đã trả kết quả",
--                       "không cần follow up"  (ba trạng thái, một loại)
--   loai = 'NHAC_HEN' ← "cần nhắc hẹn" và "KNM/KLLD/Hẹn GLS"
--
-- Hệ quả đo được: bấm "Đã hỏi bác sĩ" thì node "Đã trả kết quả" cũng tích xanh
-- theo, còn "Không cần follow up" thì không tích cái nào. Người trực đọc timeline
-- ra một câu chuyện sai về chính khách đang ngồi trước mặt.
--
-- Dò bằng cách so chuỗi trong `noi_dung` đã cân nhắc và loại: CSKH gõ ghi chú
-- riêng là mất dấu ngay, và một tính năng chỉ đúng khi người dùng không gõ gì
-- là một tính năng sẽ hỏng trong tuần đầu.
--
-- Nên: ghi thẳng MÃ TRẠNG THÁI mà thao tác này đóng lại. Một cột, không suy
-- diễn, không so chuỗi.

ALTER TABLE public.tuong_tac_cskh
    ADD COLUMN IF NOT EXISTS trang_thai_ma text;

COMMENT ON COLUMN public.tuong_tac_cskh.trang_thai_ma IS
    'Mã trạng thái mà lần chạm này xử lý (CHO_XAC_NHAN, DA_CHECKIN, CHO_KQ_XN…). '
    'NULL = dòng ghi tự do hoặc dòng có trước 20260810000002. Timeline tích xanh '
    'theo cột này, KHÔNG theo `loai` — nhiều trạng thái dùng chung một loại.';

-- Câu hỏi của màn hình: "khách này đã xử lý những trạng thái nào rồi".
CREATE INDEX IF NOT EXISTS idx_tuong_tac_trang_thai
    ON public.tuong_tac_cskh (clinic_patient_id, trang_thai_ma)
    WHERE trang_thai_ma IS NOT NULL;
