-- Chụp chiếu gửi ra ngoài (MRI vú, chụp tử cung–vòi trứng, chụp vú ép) là việc
-- ĐỐI TÁC làm trọn — phòng khám không có phòng nào làm bước DICHVU-HINHANH-NGOAI.
--
-- Trước bản này cờ `doi_tac_lay_mau` của ba dịch vụ đều tắt, nên bàn đối tác chỉ
-- thấy chúng SAU khi "đã thực hiện" — mà không phòng nào của phòng khám thực
-- hiện được, nên chỉ định nằm "đã duyệt" mãi và đối tác không bao giờ thấy.
-- Bắt được khi dựng luồng demo 17/09 (Tuyền: "chỉ định sang cho bên đối tác họ
-- nhận"). Bật cờ = hiện lên bàn đối tác ngay khi bác sĩ duyệt.
UPDATE public.service_price
   SET doi_tac_lay_mau = TRUE, updated_at = now()
 WHERE node_code = 'DICHVU-HINHANH-NGOAI'
   AND NOT doi_tac_lay_mau;
