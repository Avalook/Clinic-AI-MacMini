-- GIÁ TẠM (Tuyền chốt 27/09/2026, câu Q2): phí khám Nội tiết 500.000 · Thủ
-- thuật 300.000 · Sàn chậu chuyên sâu 300.000 là GIÁ GIẢ ĐỊNH (không có mã
-- KiotViet tương ứng — 20260926000003 giữ nguyên) — "cho phép quản lý điều
-- chỉnh sau".
--
-- Cờ DỮ LIỆU `gia_tam`: màn Bảng giá hiện chip "Giá tạm — cần xác nhận"; quản
-- lý sửa (hoặc lưu lại) đơn giá thì máy chủ tự bỏ cờ (PriceListService.update).
-- KHÔNG đổi số giá. Khoá theo MÃ dòng tiền khám, không theo tên có dấu.
--
-- Chạy lại được.

ALTER TABLE public.service_price
    ADD COLUMN IF NOT EXISTS gia_tam boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.service_price.gia_tam IS
    'Giá giả định chờ phòng khám xác nhận (27/09/2026). Sửa / lưu lại đơn giá ở '
    'Bảng giá thì tự bỏ cờ.';

UPDATE public.service_price
   SET gia_tam = true, updated_at = now()
 WHERE "group" = 'dich_vu'
   AND service_code IN ('KHAM_NOI_TIET_TINH_DUC', 'KHAM_THU_THUAT', 'KHAM_SAN_CHAU')
   AND NOT gia_tam;
