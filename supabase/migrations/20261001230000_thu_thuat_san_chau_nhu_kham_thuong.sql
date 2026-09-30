-- THỦ THUẬT + SÀN CHẬU CHUYÊN SÂU đi quy trình như 5 loại khám kia
-- (Tuyền chốt 30/09/2026: "giờ mình open rồi thì cả thủ thuật và sàn chậu
-- chuyên sâu cho nó như 5 dịch vụ kia đi, cũng quy trình như thế, open luôn,
-- không đo sinh hiệu cũng được không sao").
--
-- Trước bản này hai loại khám bật dây H2 "đi thẳng phòng"
-- (`service_type.di_thang_phong = true`, `qua_tu_van = false` —
-- 20260924000002, 20260925000006): check-in có chỉ định mang sang thì vào thẳng
-- phòng dịch vụ, không thì vào thẳng hàng bác sĩ chính, không qua tư vấn.
--
-- Nay y hệt HIEM_MUON / NAM_KHOA / NOI_TIET_TINH_DUC / PHU_KHOA / SAN_1:
--   check-in → hàng TƯ VẤN (chờ đo sinh hiệu nhưng KHÔNG khoá — bỏ qua được)
--   → bác sĩ chính → chỉ định → quầy thu → phòng.
-- Chỉ đổi DỮ LIỆU hai cờ: mọi chỗ rẽ nhánh (`luot_kham_rules.duong_sau_check_in`,
-- mang chỉ định sang, miễn tiền khám, bàn khám mở cho phòng thủ thuật) đọc hai
-- cờ này. Phiếu khám (THU_THUAT / SAN_CHAU), dịch vụ khám con (loai_kham_phi)
-- và phòng bác sĩ (hàng DOCTOR theo bác sĩ, không theo node) đã sẵn.
--
-- CÔNG TẮC GIỮ NGUYÊN: quản lý bật lại "đi thẳng phòng" ở Cài đặt → Dây nối
-- (`/settings/day-noi`, cột "Đi thẳng phòng") — cột và mọi nhánh code còn đó.
--
-- Lượt đang mở: đường đi đã xếp lúc check-in (`encounter_flow.route_decision`)
-- không bị đổi — lượt đi tiếp theo đường cũ; chỉ lượt check-in SAU bản này đi
-- đường mới.
--
-- Chạy lại được: chỉ chạm dòng còn lệch; in số dòng đã sửa.

DO $$
DECLARE
    so_dong integer;
BEGIN
    WITH sua AS (
        UPDATE public.service_type
           SET di_thang_phong = false,
               qua_tu_van = true
         WHERE code IN ('THU_THUAT', 'SAN_CHAU')
           AND (di_thang_phong OR NOT qua_tu_van)
        RETURNING id
    )
    SELECT count(*) INTO so_dong FROM sua;
    RAISE NOTICE 'Thủ thuật / Sàn chậu như khám thường: % dòng service_type đã sửa',
        so_dong;
END
$$;
