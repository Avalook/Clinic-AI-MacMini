-- KNM / KLLD / Hẹn GLS là KẾT QUẢ CUỘC GỌI, không phải loại hẹn.
--
-- Dòng trong DoD viết "KNM/KLLD/Hẹn GLS → CSKH gọi điện xác nhận lịch hẹn",
-- và ba chữ viết tắt ấy xuất hiện 0 lần trong toàn bộ code lẫn database. Cả
-- một bản thiết kế đã suýt khai chúng thành ba loại hẹn mới với mốc thời gian
-- riêng — tức là ba tab luôn rỗng.
--
-- Quang giải nghĩa (08/08/2026):
--   KNM       = không nghe máy
--   KLLD      = không liên lạc được
--   Hẹn GLS   = hẹn gọi lại sau
--
-- Nên đây không phải trạng thái mới của LỊCH HẸN, mà là kết quả của LẦN GỌI
-- gần nhất. Việc "cần gọi lại" suy thẳng ra từ đó, không cần bảng nào cả.
--
-- Bộ từ cũ chỉ có `CHUA_NGHE_MAY` (= KNM). Hai cái còn lại khác hẳn:
--   · KLLD    máy không đổ chuông — số sai, thuê bao khoá, tắt máy. Gọi lại
--             lần nữa cũng thế; việc phải làm là TÌM SỐ KHÁC.
--   · Hẹn GLS khách BẮT MÁY và bảo gọi lại. Đây là hẹn, không phải thất bại.
-- Gộp cả ba vào "chưa nghe máy" thì báo cáo cuối tháng nói phòng khám gọi hụt
-- 30% khách, trong khi một phần ba số đó là khách chủ động hẹn giờ khác.

ALTER TABLE public.tuong_tac_cskh
    DROP CONSTRAINT IF EXISTS tuong_tac_cskh_ket_qua_check;

ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_cskh_ket_qua_check CHECK (ket_qua IN (
        'DA_LIEN_HE',
        'CHUA_NGHE_MAY',          -- KNM: đổ chuông, không ai bắt
        'KHONG_LIEN_LAC_DUOC',    -- KLLD: không đổ chuông / số không dùng được
        'HEN_GOI_LAI',            -- Hẹn GLS: khách bắt máy, hẹn giờ khác
        'CAN_BAC_SI',
        'TU_CHOI',
        'BO_QUA'));

COMMENT ON COLUMN public.tuong_tac_cskh.ket_qua IS
    'Kết quả lần chạm. CHUA_NGHE_MAY=KNM, KHONG_LIEN_LAC_DUOC=KLLD, '
    'HEN_GOI_LAI=hẹn gọi lại sau. Ba cái này sinh ra việc "cần gọi lại".';
