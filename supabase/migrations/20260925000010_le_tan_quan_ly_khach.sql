-- Lễ tân có màn Quản lý khách hàng, ĐỦ QUYỀN (Tuyền 24/09/2026: "kéo nút quản lý
-- khách hàng full quyền thêm sang màn lễ tân nữa").
--
-- Màn ấy đổi / huỷ lịch hẹn → cần khối `quan_ly_lich` (booking.manage). Nhóm mẫu
-- Lễ tân đã có `dat_lich`; thêm `quan_ly_lich`. Khớp PRESET trong
-- permissions/catalogue.py (test_danh_muc_quyen_db so). Chạy lại được.

UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['quan_ly_lich']) AS k)
 WHERE p.ma = 'RECEPTION' AND p.he_thong
   AND NOT ('quan_ly_lich' = ANY (p.khoi));

-- Người đang làm nhận khối mới theo nhóm (ai đã bị quản lý thu thì giữ nguyên).
SELECT public.cap_quyen_cho_moi_thanh_vien();
