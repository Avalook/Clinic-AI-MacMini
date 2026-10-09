-- Liệu trình: "tính lại" LUÔN báo tin cho màn (bấm thử staging 09/10/2026).
--
-- Lỗi: bàn khám bấm [Xong] một buổi → thẻ chỉ định "Đã làm xong" nhưng dải lộ
-- trình vẫn "Đã làm 0/6 · Buổi 1 chưa làm" tới khi tải lại trang. Gốc:
-- `lieu_trinh_tinh_lai` chạm dòng `lieu_trinh` để trigger báo tin, nhưng
-- `lieu_trinh_truoc_khi_ghi` thấy KẾ HOẠCH không đổi (số buổi, đơn giá, trạng
-- thái…) thì `RETURN NULL` — UPDATE bị bỏ, `notify_row_change` không chạy. Số
-- "đã làm" suy từ chỉ định, không nằm trên dòng `lieu_trinh`, nên mọi màn nghe
-- bảng `lieu_trinh` (bàn khám, quầy, khung khách CSKH) không biết gì.
--
-- Sửa: phát đúng tin của `notify_row_change` (tên bảng + phòng khám, không dữ
-- liệu hàng) ngay trong hàm tính lại — không đổi luật bỏ UPDATE vô ích.

CREATE OR REPLACE FUNCTION public.lieu_trinh_tinh_lai(p_clinic uuid, p_lt uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    PERFORM public.lieu_trinh_phu_lai(p_clinic, p_lt);
    UPDATE public.lieu_trinh SET hanh_dong = 'TU_DONG', sua_boi = NULL
     WHERE clinic_id = p_clinic AND id = p_lt;
    PERFORM pg_notify(
        'clinicai_changes',
        json_build_object('t', 'lieu_trinh', 'c', p_clinic)::text
    );
END $$;
