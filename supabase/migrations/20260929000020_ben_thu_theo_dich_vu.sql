-- BÊN THU THUỘC TỪNG DỊCH VỤ + PHÂN LOẠI THU HỘ THEO KIOTVIET (Tuyền 29/09/2026).
--
-- Trước đây `service_price.billing_owner` bị SUY RA từ phòng làm (node có
-- `lam_ben_ngoai` → EXTERNAL_PARTNER, migration 20260928000091 + mỗi lần đổi
-- phòng làm ở màn Bảng giá). Tuyền chốt: bên thu là thuộc tính CỦA DỊCH VỤ —
-- quản lý chọn tay ở Bảng giá ("Phòng khám thu / Thu hộ đối tác"); suy từ phòng
-- làm CHỈ là mặc định khi tạo mới hoặc khi dòng chưa được chọn tay.
--
-- 1. Cờ `billing_owner_chon_tay`: true = đã chọn tay → không logic suy-từ-phòng
--    nào được ghi đè (`PriceListService.update` đọc cờ này). Mặc định false
--    cho mọi dòng cũ: hành vi cũ giữ nguyên tới khi có người chọn.
-- 2. Phân loại theo file KiotViet (nhóm "XN thu hộ" = của đối tác), CHỈ 4 mã:
--      SP000092 Giải phẫu bệnh                              → EXTERNAL_PARTNER
--      SP000075 Sinh thiết CTC, âm hộ, âm đạo + GPB         → EXTERNAL_PARTNER
--      SP000025 Tổng phân tích nước tiểu (nhóm "Xét nghiệm") → CLINIC
--      SP000076 Soi cổ tử cung (nhóm "Thủ thuật")           → CLINIC
--    Mọi mã khác GIỮ NGUYÊN (XN máu, CFTR, Karyotype, dịch âm đạo, hình ảnh
--    ngoài… chờ Tuyền chốt sau). Đánh dấu chọn tay để việc đổi phòng làm về
--    sau không lật lại quyết định này.
--
-- Chạy lại được: cột IF NOT EXISTS, UPDATE chỉ chạm dòng còn lệch.

ALTER TABLE public.service_price
    ADD COLUMN IF NOT EXISTS billing_owner_chon_tay boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.service_price.billing_owner_chon_tay IS
    'true = quản lý (hoặc migration theo quyết định của Tuyền) đã CHỌN TAY bên '
    'thu cho dịch vụ này; suy từ phòng làm (lam_ben_ngoai) chỉ là mặc định khi '
    'chưa chọn tay và KHÔNG được ghi đè (Tuyền 29/09/2026).';

-- Hàm (không phải UPDATE trần) vì DB DỰNG MỚI nạp danh mục KiotViet SAU
-- migration (`supabase/seed.sql` gọi `chuan_hoa_danh_muc_dich_vu_kiotviet()`):
-- `scripts/dev-up.sh` chạy lại file này sau seed. Prod / DB đã có dữ liệu: áp
-- một lần như mọi migration. Trả số dòng đã đổi.
CREATE OR REPLACE FUNCTION public.ap_ben_thu_theo_kiotviet()
RETURNS integer
LANGUAGE sql
AS $$
    WITH doi AS (
        UPDATE public.service_price s
           SET billing_owner = v.ben,
               billing_owner_chon_tay = true,
               updated_at = now()
          FROM (VALUES
               ('SP000092', 'EXTERNAL_PARTNER'),
               ('SP000075', 'EXTERNAL_PARTNER'),
               ('SP000025', 'CLINIC'),
               ('SP000076', 'CLINIC')
             ) AS v(ma_kv, ben)
         WHERE s.ma_kiotviet = v.ma_kv
           AND s."group" = 'dich_vu'
           AND (s.billing_owner IS DISTINCT FROM v.ben
                OR NOT s.billing_owner_chon_tay)
        RETURNING 1)
    SELECT count(*)::integer FROM doi;
$$;

COMMENT ON FUNCTION public.ap_ben_thu_theo_kiotviet() IS
    'Phân loại thu hộ theo file KiotViet (Tuyền 29/09/2026): SP000092, SP000075 '
    '→ EXTERNAL_PARTNER; SP000025, SP000076 → CLINIC; đánh dấu chọn tay. Chỉ '
    'chạm 4 mã ấy, chạy lại được.';

-- Hàm ghi dữ liệu: không mở cho PostgREST (/rest/v1/rpc) — chỉ migration/seed.
REVOKE ALL ON FUNCTION public.ap_ben_thu_theo_kiotviet() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION public.ap_ben_thu_theo_kiotviet() FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION public.ap_ben_thu_theo_kiotviet() FROM authenticated;
    END IF;
END $$;

SELECT public.ap_ben_thu_theo_kiotviet();

COMMENT ON COLUMN public.service_price.billing_owner IS
    'CLINIC = phòng khám thu; EXTERNAL_PARTNER = thu hộ đối tác (không cộng vào '
    'hoá đơn phòng khám). Thuộc TỪNG DỊCH VỤ — 29/09/2026: SP000092, SP000075 '
    'thu hộ đối tác; SP000025, SP000076 phòng khám thu (file KiotViet, nhóm '
    '"XN thu hộ"); mã khác chờ chốt.';
