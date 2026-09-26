-- DANH MỤC DỊCH VỤ THEO KIOTVIET (Tuyền chốt 25–26/09/2026 — lát 1 của bản
-- giao diện mẫu). Nguồn chuẩn = file KiotViet phòng khám đưa
-- (DanhSachSanPham_KV21092026-171729) + phiếu chỉ định giấy v.17-08-2026; bảng
-- ghép `~/Downloads/Dr4women-bang-ghep-danh-muc.json`. Xung đột → theo file
-- chuẩn, nhưng MỞ cho quản lý sửa lại ở Bảng giá.
--
-- MÃ CHUẨN = mã phòng khám (mã SP KiotViet), cột mới `service_price.ma_kiotviet`,
-- duy nhất theo phòng khám. `service_code` (CLS_*) GIỮ làm khoá ẩn: chỉ định cũ
-- trên prod không bị viết lại.
--   * 39 mã cũ: gắn mã KV, đổi tên theo KV, giá theo KV.
--   * 45 dịch vụ mới (có trên KV, chưa có trên hệ thống — kể cả phần tách từ một
--     mã cũ ra nhiều: HPV, soi BTC, laser, thai 3D/6D, monitoring): mã
--     `KV_<mã SP>`, phòng làm theo nhóm KV (phần tách: theo phòng của mã cũ).
--   * Nhóm "Phí khám" (11 mã KV): KHÔNG ở đây — ghép với loại khám ở lát 2.
--   * Mã chỉ hệ thống có / chỉ phiếu giấy có: giữ nguyên.
--
-- GIÁ: KV > 0 → giá KV. KV 0đ → giá VIẾT TAY trên phiếu giấy của đúng dòng ấy
-- (HPV 900k, PCR 1,1tr); không có → mã cũ GIỮ giá đang có (ThinPrep 650k), mã
-- mới để TRỐNG = "chưa có giá" (quầy thu chặn, quản lý điền). KHÔNG BAO GIỜ nạp
-- 0đ — nạp 0 là thu 0 đồng.
--
-- Đối chiếu prod 26/09 trước khi ghi: mọi lần sửa giá CLS_* đều là migration/
-- script (17/09, 24/09); hai dòng có dấu sửa tay (Biofeedback cơ bản, chụp phim
-- ngoài) KHÔNG nằm trong phần ghép.
--
-- Chạy lại được. Migration chỉ gọi hàm khi đã có nhân sự (DB thật); seed.sql
-- gọi sau khi nạp dữ liệu mẫu.

ALTER TABLE public.service_price ADD COLUMN IF NOT EXISTS ma_kiotviet text;
CREATE UNIQUE INDEX IF NOT EXISTS uq_service_price_ma_kiotviet
    ON public.service_price (clinic_id, ma_kiotviet) WHERE ma_kiotviet IS NOT NULL;
COMMENT ON COLUMN public.service_price.ma_kiotviet IS
'Mã phòng khám (mã SP KiotViet) — mã chuẩn để tra/nhập/hiển thị (26/09/2026). service_code giữ làm khoá ẩn.';

CREATE OR REPLACE FUNCTION public.chuan_hoa_danh_muc_dich_vu_kiotviet()
RETURNS TABLE (gan_ma integer, them_moi integer)
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE
  n_gan integer := 0;
  n_moi integer := 0;
BEGIN
    WITH gan (cls, ma, ten, gia) AS (VALUES
      ('CLS_DO_MAT_DO_XUONG', 'SP000134', 'Đo mật độ xương', 200000::numeric),
      ('CLS_NUOC_TIEU', 'SP000025', 'Tổng phân tích nước tiểu', 50000::numeric),
      ('CLS_SOI_CO_TU_CUNG', 'SP000076', 'Soi cổ tử cung', 400000::numeric),
      ('CLS_SOI_AM_HO', 'SP000163', 'Soi âm hộ', 250000::numeric),
      ('CLS_SIEU_AM_DAU_DO_DO_DAI_CTC', 'SP000012', 'Siêu âm đầu dò độ dài CTC', 50000::numeric),
      ('CLS_SIEU_AM_2D_TC_BT', 'SP000013', 'Siêu âm 2D tử cung buồng trứng', 250000::numeric),
      ('CLS_SIEU_AM_4D_TC_BT', 'SP000014', 'Siêu âm 4D tử cung buồng trứng', 350000::numeric),
      ('CLS_SIEU_AM_BOM_NUOC_TU_CUNG', 'SP000090', 'SA bơm nước buồng tử cung', 800000::numeric),
      ('CLS_SIEU_AM_KHOP', 'SP000121', 'Siêu âm khớp 1 bên (gối, vai, háng…)', 150000::numeric),
      ('CLS_SIEU_AM_O_BUNG', 'SP000016', 'Siêu âm ổ bụng', 250000::numeric),
      ('CLS_SIEU_AM_VU', 'SP000015', 'Siêu âm tuyến vú hai bên', 200000::numeric),
      ('CLS_SIEU_AM_TUYEN_GIAP', 'SP000017', 'Siêu âm tuyến giáp', 200000::numeric),
      ('CLS_SIEU_AM_DOPPLER_MACH_CANH', 'SP000018', 'Siêu âm Doppler hệ động mạch cảnh và sống nền hai bên', 400000::numeric),
      ('CLS_SIEU_AM_DOPPLER_DM_THAN', 'SP000099', 'Siêu âm Doppler động mạch thận hai bên', 400000::numeric),
      ('CLS_SIEU_AM_DOPPLER_AM_VAT', 'SP000125', 'Siêu âm âm vật', 150000::numeric),
      ('CLS_SIEU_AM_4D_SAN_CHAU', 'SP000150', 'Siêu âm 4D sàn chậu (20 phút)', 500000::numeric),
      ('CLS_SIEU_AM_TINH_HOAN', 'SP000019', 'Siêu âm Doppler tinh hoàn hai bên', 350000::numeric),
      ('CLS_DAT_VONG_NOI_TIET', 'SP000100', 'Đặt vòng nội tiết Mirena', 5000000::numeric),
      ('CLS_THAO_VONG', 'SP000020', 'Tháo vòng tránh thai', 350000::numeric),
      ('CLS_CAY_QUE_TRANH_THAI', 'SP000023', 'Cấy que tránh thai', 2600000::numeric),
      ('CLS_THAO_QUE_TRANH_THAI', 'SP000024', 'Tháo que thánh thai', 700000::numeric),
      ('CLS_HUT_BUONG_TU_CUNG', 'SP000091', 'Hút BTC', 2000000::numeric),
      ('CLS_TACH_BAO_QUY_DAU_AV', 'SP000156', 'Cắt/ tách bao quy đầu âm vật', 7000000::numeric),
      ('CLS_BIOFEEDBACK', 'SP000146', 'Tập máy Bio điều trị (chưa bao gồm đầu dò)', 900000::numeric),
      ('CLS_NONG_BAO_QUY_DAU_AV', 'SP000162', 'Nong tách dính âm hộ, âm vật', 1700000::numeric),
      ('CLS_GHE_DTT', 'SP000158', 'Ghế điện từ trường', 3000000::numeric),
      ('CLS_PCR_12_VK', 'SP000171', '13 bệnh lây STD', 1100000::numeric),
      ('CLS_THINPREP', 'SP000027', 'Thinprep sàng lọc tế bào ung thử cổ tử cung', NULL::numeric),
      ('CLS_KHAM_SAN_CHAU', 'SP000006', 'Tư vấn phụ khoa chuyên sâu (TMK, TD, sàn chậu…)', 300000::numeric),
      ('CLS_DO_CO_LUC_AM_DAO', 'SP000145', 'Đo trương lực cơ sàn chậu máy Bio (ko bao gồm đầu dò)', 300000::numeric),
      ('CLS_CHAY_MONITORING', 'SP000026', 'Monitor sản khoa đơn thai', 200000::numeric),
      ('CLS_HPV', 'SP000028', 'HPV định type PCR (40 type)', 900000::numeric),
      ('CLS_SIEU_AM_3D_THAI_12_TUAN', 'SP000008', 'Siêu âm 2D thai <12 tuần', 250000::numeric),
      ('CLS_SIEU_AM_3D_THAI_12_TUAN_2', 'SP000078', 'Siêu âm 3D thai > 12 tuần', 300000::numeric),
      ('CLS_SIEU_AM_THAI_6D', 'SP000010', 'Siêu âm 6D sàng lọc hình thái', 400000::numeric),
      ('CLS_SIEU_AM_DOPPLER_DUONG_VAT', 'SP000108', 'Siêu âm Doppler dương vật', 300000::numeric),
      ('CLS_SOI_BUONG_TU_CUNG', 'SP000055', 'Soi buồng tử cung chẩn đoán', 6000000::numeric),
      ('CLS_LASER_TRE_HOA', 'SP000215', 'Laser trẻ hoá tiền đình và âm đạo', 7000000::numeric),
      ('CLS_LASER_ST_SSD', 'SP000168', 'Laser điều trị bệnh lý (SSD, són tiểu…) 2 thành', 15000000::numeric)
    )
    UPDATE public.service_price p
       SET ma_kiotviet = g.ma,
           name = g.ten,
           unit_price = coalesce(g.gia, p.unit_price),
           updated_at = now()
      FROM gan g
     WHERE p."group" = 'dich_vu' AND p.service_code = g.cls
       AND (p.ma_kiotviet IS DISTINCT FROM g.ma OR p.name IS DISTINCT FROM g.ten
            OR p.unit_price IS DISTINCT FROM coalesce(g.gia, p.unit_price));
    GET DIAGNOSTICS n_gan = ROW_COUNT;

    WITH moi (ma, ten, gia, node, cls_cha) AS (VALUES
      ('SP000214', 'Đặt bóng chống dính buồng tử cung', 800000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000173', 'NIPT basic', NULL::numeric, 'DICHVU-LAYMAU-MAU', NULL),
      ('SP000172', 'Liên cầu B', NULL::numeric, 'DICHVU-LAYMAU-AMDAO', NULL),
      ('SP000151', 'Tiêm HA Gspot', 15000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000140', 'Bơm PRP niêm mạc tử cung (TPC)', 8000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000137', 'Sinh thiết vú, hạch dưới siêu âm (đã bao gồm giải phẫu bệnh)', 4500000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000136', 'Bơm PRP niêm mạc tử cung (RG)', 8000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000135', 'Massage vú', 200000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000133', 'Cắt đốt u sinh dục', 3500000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000127', 'Siêu âm tuyến tiền liệt', 250000::numeric, 'DICHVU-SIEUAM', NULL),
      ('SP000126', 'Nạo ống cổ tử cung và làm giải phẫu bệnh', 1000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000116', 'Cắt đốt sùi mào gà', 5000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000115', 'Khoét chóp CTC', 5000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000114', 'Bơm IUI', 4000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000109', 'Nong bao quy đầu dương vật', 1000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000107', 'Siêu âm Doppler động tĩnh mạch chi dưới hai bên', 400000::numeric, 'DICHVU-SIEUAM', NULL),
      ('SP000104', 'Đặt vòng nâng cổ tử cung Pessary', 4500000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000103', 'NIPT Basic plus', NULL::numeric, 'DICHVU-LAYMAU-MAU', NULL),
      ('SP000102', 'Siêu âm bơm nước', 800000::numeric, 'DICHVU-SIEUAM', NULL),
      ('SP000101', 'NIPT Trisure Procare / Geneva plus', NULL::numeric, 'DICHVU-LAYMAU-MAU', NULL),
      ('SP000093', 'Cắt LEEP cổ tử cung', 5000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000092', 'Giải phẫu bệnh', 600000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000089', 'Gentis 9 bệnh gen lặn', NULL::numeric, 'DICHVU-LAYMAU-MAU', NULL),
      ('SP000088', 'XN gen BrCa', 2500000::numeric, 'DICHVU-LAYMAU-MAU', NULL),
      ('SP000087', 'NIPT trisure / Geneva', NULL::numeric, 'DICHVU-LAYMAU-MAU', NULL),
      ('SP000086', 'NIPT Geneva 7', NULL::numeric, 'DICHVU-LAYMAU-MAU', NULL),
      ('SP000080', 'Siêu âm COMBO PHỤ KHOA BỤNG VÚ GIÁP MẠCH CẢNH', 900000::numeric, 'DICHVU-SIEUAM', NULL),
      ('SP000075', 'Sinh thiết CTC, âm hộ, âm đạo (bấm ST + làm giải phẫu bệnh) (5 ngày)', 1000000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000074', 'Xoắn lấy polyp CTC AH, ÂĐ < 1cm', 1500000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000022', 'Đốt điện cổ tử cung lộ tuyến', 4500000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000021', 'Đặt vòng tránh thai', 500000::numeric, 'DICHVU-THUTHUAT', NULL),
      ('SP000011', 'Siêu âm Doppler thai nhi', 300000::numeric, 'DICHVU-SIEUAM', NULL),
      ('SP000081', 'Monitor Sản khoa song thai - đa thai', 300000::numeric, NULL, 'CLS_CHAY_MONITORING'),
      ('SP000169', 'HPV định type PCR 16 type', NULL::numeric, 'DICHVU-SANGLOC-COTUCUNG', 'CLS_HPV'),
      ('SP000170', 'Combo HPV 40 + thinprep', NULL::numeric, 'DICHVU-SANGLOC-COTUCUNG', 'CLS_HPV'),
      ('SP000132', 'Siêu âm 3D song thai thai nhỏ', 300000::numeric, NULL, 'CLS_SIEU_AM_3D_THAI_12_TUAN'),
      ('SP000009', 'Siêu âm 2D thai >12 tuần', 300000::numeric, NULL, 'CLS_SIEU_AM_3D_THAI_12_TUAN_2'),
      ('SP000084', 'Siêu âm 3D thai > 12 tuần (Song thai)', 400000::numeric, NULL, 'CLS_SIEU_AM_3D_THAI_12_TUAN_2'),
      ('SP000098', 'Siêu âm 6D thai 12 tuần', 400000::numeric, NULL, 'CLS_SIEU_AM_THAI_6D'),
      ('SP000085', 'Siêu âm 6D song thai', 700000::numeric, NULL, 'CLS_SIEU_AM_THAI_6D'),
      ('SP000129', 'Siêu âm dương vật', 250000::numeric, NULL, 'CLS_SIEU_AM_DOPPLER_DUONG_VAT'),
      ('SP000056', 'Soi buồng tử cung cắt dính', 11000000::numeric, NULL, 'CLS_SOI_BUONG_TU_CUNG'),
      ('SP000057', 'Soi buồng tử cung cắt dính từ lần thứ 6', 7000000::numeric, NULL, 'CLS_SOI_BUONG_TU_CUNG'),
      ('SP000165', 'Laser trẻ hoá tiền đình', 4500000::numeric, NULL, 'CLS_LASER_TRE_HOA'),
      ('SP000167', 'Laser điều trị bệnh lý (SSD, són tiểu..) (1 thành)', 10000000::numeric, NULL, 'CLS_LASER_ST_SSD')    )
    INSERT INTO public.service_price
        (clinic_id, service_code, name, "group", unit_price, active, category,
         node_code, ma_kiotviet)
    SELECT c.id, 'KV_' || m.ma, m.ten, 'dich_vu', m.gia, true,
           'KiotViet 26/09/2026' || CASE WHEN m.gia IS NULL
                THEN ' · CHƯA CÓ GIÁ — quản lý điền ở Bảng giá' ELSE '' END,
           coalesce(m.node, cha.node_code), m.ma
      FROM public.clinic c
     CROSS JOIN moi m
      LEFT JOIN public.service_price cha
        ON cha.clinic_id = c.id AND cha."group" = 'dich_vu'
       AND cha.service_code = m.cls_cha
     WHERE EXISTS (SELECT 1 FROM public.service_price p
                    WHERE p.clinic_id = c.id AND p."group" = 'dich_vu'
                      AND p.service_code LIKE 'CLS\_%')
    ON CONFLICT (clinic_id, "group", service_code) DO NOTHING;
    GET DIAGNOSTICS n_moi = ROW_COUNT;

    RETURN QUERY SELECT n_gan, n_moi;
END;
$fn$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.staff) THEN
    PERFORM public.chuan_hoa_danh_muc_dich_vu_kiotviet();
  END IF;
END;
$$;
