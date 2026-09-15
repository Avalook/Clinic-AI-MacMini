-- KẾT QUẢ XÉT NGHIỆM VỀ MUỘN: CSKH THEO DÕI, HẠN 3 NGÀY (15/09/2026).
--
-- Tuyền chốt: kết quả về muộn → CSKH theo dõi, hạn 3 ngày, có cảnh báo, tắt khi
-- xử lý xong. Việc `CHO_KQ_XN` của v_viec_cskh đã làm đúng hình dạng đó (hiện từ
-- lúc lấy mẫu, đỏ `qua_han` khi quá hạn, hết khi kết quả về) — chỉ con số gieo
-- sẵn là 2 ngày (20260809000005). Đổi mặc định thành 3 cho phòng khám CHƯA tự
-- chỉnh; phòng khám đã đặt số khác thì giữ số của họ.

UPDATE public.luat_cskh
   SET so_ngay = 3
 WHERE loai_viec = 'CHO_KQ_XN'
   AND so_ngay = 2;
