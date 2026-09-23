-- Quản lý có MỌI KHỐI, trừ khối cần chứng chỉ hành nghề (24/09/2026).
--
-- Tuyền chốt: "quản lý quyền cao nhất — có module đó thì mọi quyền của nó có
-- cả", không tách đọc với sửa. Nhóm mẫu MANAGEMENT trước đây liệt kê tay các
-- khối VẬN HÀNH và bỏ ngoài bốn khối chuyên môn không cần chứng chỉ. Nay thêm:
--
--   tu_van            clinical.intake.perform
--   kham              clinical.consult.perform
--   ghi_benh_an       clinical.record.write
--   xac_nhan_ket_qua  result.file.confirm
--
-- Hai khối ký chuyên môn (hoan_tat_kham, duyet_ket_qua) KHÔNG thêm: chúng đòi
-- chứng chỉ hành nghề, và lệnh cấp quyền vẫn từ chối cấp cho người không có vai
-- lâm sàng.
--
-- Đi cùng: cửa đọc nội dung y khoa ở backend hỏi QUYỀN (permissions/y_khoa.py)
-- thay cho danh sách vai — ai có một khối khám / kết quả là đọc được.

UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['tu_van', 'kham', 'ghi_benh_an',
                                             'xac_nhan_ket_qua']) AS k)
 WHERE p.ma = 'MANAGEMENT' AND p.he_thong
   AND NOT (p.khoi @> ARRAY['tu_van', 'kham', 'ghi_benh_an', 'xac_nhan_ket_qua']);

-- Người đang làm nhận các khối mới theo nhóm (ai đã bị thu thì giữ nguyên).
SELECT public.cap_quyen_cho_moi_thanh_vien();
