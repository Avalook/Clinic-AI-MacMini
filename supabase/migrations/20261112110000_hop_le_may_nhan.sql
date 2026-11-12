-- Tờ kết quả MÁY NHẬN (Gmail / Drive) Hợp lệ ngay, không người xác nhận (Tuyền 12/11/2026:
-- bỏ hẳn bước "Xác nhận kết quả đối tác", về luật 23/09 "không cần nút xác nhận").
--
-- Ràng buộc cũ đòi HOP_LE (và THU_HOI — thu hồi giữ người xác nhận) có
-- `xac_nhan_boi_staff_id`. Nới ĐÚNG MỘT chỗ: được thiếu người xác nhận khi tờ do máy
-- nhận (`tai_len_boi_staff_id` NULL VÀ `nguon` DRIVE/GMAIL — cùng điều kiện ràng buộc
-- `nguon` đã có). Tờ người tải giữ nguyên luật. Các nhánh khác chép y nguyên
-- 20260920000005. Không đổi dòng nào.

ALTER TABLE public.tep_ket_qua DROP CONSTRAINT IF EXISTS chk_tep_ket_qua_xac_nhan;
ALTER TABLE public.tep_ket_qua ADD CONSTRAINT chk_tep_ket_qua_xac_nhan CHECK (
    (xac_nhan_trang_thai IS NULL AND xac_nhan_luc IS NULL
     AND xac_nhan_boi_staff_id IS NULL AND xac_nhan_ly_do IS NULL
     AND thu_hoi_luc IS NULL AND thu_hoi_boi_staff_id IS NULL AND thu_hoi_ly_do IS NULL)
    OR (xac_nhan_trang_thai = 'CHO_XAC_NHAN' AND xac_nhan_luc IS NULL
        AND xac_nhan_boi_staff_id IS NULL
        AND thu_hoi_luc IS NULL AND thu_hoi_boi_staff_id IS NULL)
    OR (xac_nhan_trang_thai = 'HOP_LE' AND xac_nhan_luc IS NOT NULL
        AND (xac_nhan_boi_staff_id IS NOT NULL
             OR (tai_len_boi_staff_id IS NULL AND nguon IN ('DRIVE', 'GMAIL')))
        AND thu_hoi_luc IS NULL AND thu_hoi_boi_staff_id IS NULL)
    OR (xac_nhan_trang_thai = 'TU_CHOI' AND xac_nhan_luc IS NOT NULL
        AND xac_nhan_boi_staff_id IS NOT NULL
        AND xac_nhan_ly_do IS NOT NULL AND length(btrim(xac_nhan_ly_do)) > 0
        AND thu_hoi_luc IS NULL AND thu_hoi_boi_staff_id IS NULL)
    OR (xac_nhan_trang_thai = 'THU_HOI' AND xac_nhan_luc IS NOT NULL
        AND (xac_nhan_boi_staff_id IS NOT NULL
             OR (tai_len_boi_staff_id IS NULL AND nguon IN ('DRIVE', 'GMAIL')))
        AND thu_hoi_luc IS NOT NULL AND thu_hoi_boi_staff_id IS NOT NULL
        AND thu_hoi_ly_do IS NOT NULL AND length(btrim(thu_hoi_ly_do)) > 0)
);

-- Tờ máy nhận ĐANG chờ xác nhận ⇒ Hợp lệ (không còn màn nào để xác nhận). CHỈ thư từ
-- 11/11 (ngày bật tự nhận Gmail) + tờ Drive: thư cũ hơn để lệnh bù `gmail_bu_cu` (đã trả
-- ngoài hệ thống) — nếu đổi luôn ở đây, CSKH sẽ có hàng trăm việc "Kết quả chưa gửi" cho
-- kết quả đã trả nếu lệnh bù chưa chạy. KHÔNG đánh "đã gửi": CSKH gửi như thường.
UPDATE public.tep_ket_qua k
   SET xac_nhan_trang_thai = 'HOP_LE', xac_nhan_luc = now(),
       xac_nhan_ly_do = 'Tự động — bỏ bước xác nhận kết quả đối tác (12/11/2026)'
 WHERE k.xac_nhan_trang_thai = 'CHO_XAC_NHAN' AND k.da_xoa_luc IS NULL
   AND k.tai_len_boi_staff_id IS NULL AND k.nguon IN ('DRIVE', 'GMAIL')
   AND (k.nguon = 'DRIVE' OR EXISTS (
        SELECT 1 FROM public.drive_tep t
         WHERE t.tep_ket_qua_id = k.id AND t.clinic_id = k.clinic_id
           AND (t.email_nhan_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date >= '2026-11-11'));
