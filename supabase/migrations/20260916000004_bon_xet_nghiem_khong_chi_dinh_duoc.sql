-- Bốn xét nghiệm nam khoa KHÔNG chỉ định được vì thiếu bước thực hiện.
--
-- Bảng chỉ định đọc danh mục bằng câu này (luot_kham_service.bang):
--
--     FROM service_price s JOIN node_definition n ON n.code = s.node_code
--     WHERE s.active AND s.node_code LIKE 'DICHVU-%'
--
-- `node_code` NULL thì phép nối rụng dòng ấy đi, im lặng. Đo 16/09/2026: 5
-- trong 39 dịch vụ đang active có node_code NULL, nên bác sĩ KHÔNG THỂ chỉ định
-- chúng — mà bốn trong số đó là xét nghiệm của chính phiếu Nam khoa vừa được
-- bật ngày hôm qua (20260916000002). Phiếu mở ra, điền được, rồi tới lúc chỉ
-- định thì dịch vụ không có trong danh sách.
--
-- Bước thực hiện gắn theo BỆNH PHẨM, không theo tên xét nghiệm:
--   · CFTR + alen 5T, mất đoạn nhỏ NST Y, nhiễm sắc thể đồ → lấy MÁU
--   · phân mảnh DNA tinh trùng                            → tinh dịch đồ
--
-- `CLS_KHAM_PHU_KHOA` cố ý ở lại NULL: khám phụ khoa là một LƯỢT KHÁM, không
-- phải dịch vụ ai đó thực hiện hộ — để nó trong danh sách chỉ định là mời bác
-- sĩ chỉ định chính việc mình đang làm.

BEGIN;

UPDATE public.service_price
   SET node_code = 'DICHVU-LAYMAU-MAU'
 WHERE node_code IS NULL
   AND service_code IN ('CLS_CFTR', 'CLS_Y_MICRODELETION', 'CLS_KARYOTYPE');

UPDATE public.service_price
   SET node_code = 'DICHVU-TINHDICHDO'
 WHERE node_code IS NULL
   AND service_code = 'CLS_DFI';

-- Chốt kiểm: chạy lại migration này không được đổi thêm gì, và sau khi chạy
-- thì đúng một dịch vụ active còn thiếu bước — khám phụ khoa.
DO $$
DECLARE
    con integer;
BEGIN
    SELECT count(*) INTO con
      FROM public.service_price
     WHERE active AND node_code IS NULL;
    IF con <> (SELECT count(*) FROM public.service_price
                WHERE active AND service_code = 'CLS_KHAM_PHU_KHOA') THEN
        RAISE EXCEPTION
            'Còn % dịch vụ active thiếu bước thực hiện — xem lại danh mục', con;
    END IF;
END $$;

COMMIT;
