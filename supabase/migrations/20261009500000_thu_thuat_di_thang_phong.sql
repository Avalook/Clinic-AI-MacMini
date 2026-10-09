-- THỦ THUẬT đi thẳng phòng, KHÔNG qua tư vấn (Tuyền chốt 09/10/2026).
--
-- Lượt Thủ thuật (như 6 loại Điều trị DT_*) không qua bác sĩ tư vấn: check-in có
-- chỉ định mang sang thì vào thẳng phòng dịch vụ; không có thì vào hàng bác sĩ
-- chính (`luot_kham_rules.duong_sau_check_in`, đích PRIMARY). Phí khám KHÔNG tự
-- cộng — chỉ khi tick dịch vụ khám con (`bill_service.khong_tu_cong_phi_kham`).
--
-- Đảo lại phần THU_THUAT của 20261001230000 (không sửa migration ấy). SAN_CHAU
-- và mọi loại khám khác GIỮ NGUYÊN. Công tắc vẫn ở Cài đặt → Dây nối (cột "Đi
-- thẳng phòng"): quản lý đổi lại được trên màn.
--
-- Lượt đang mở giữ đường đã xếp lúc check-in (`encounter_flow.route_decision`);
-- lượt cũ đã qua TƯ VẤN vẫn giữ dòng phí khám (vế route_decision ở bill_service).
--
-- Chạy lại được: chỉ chạm dòng còn lệch; in số dòng đã đổi.

DO $$
DECLARE
    so_dong integer;
BEGIN
    WITH sua AS (
        UPDATE public.service_type
           SET di_thang_phong = true,
               qua_tu_van = false
         WHERE code = 'THU_THUAT'
           AND (NOT coalesce(di_thang_phong, false) OR coalesce(qua_tu_van, true))
        RETURNING id
    )
    SELECT count(*) INTO so_dong FROM sua;
    RAISE NOTICE 'Thủ thuật đi thẳng phòng: % dòng service_type đã đổi', so_dong;
END
$$;
