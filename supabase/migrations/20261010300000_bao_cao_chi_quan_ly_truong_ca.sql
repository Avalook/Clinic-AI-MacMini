-- LEGO BÁO CÁO CHỈ CÒN QUẢN LÝ + TRƯỞNG CA (Tuyền 09/10/2026).
--
-- "Mở full lego" (20260930900000) cấp khối `bao_cao` (quyền `report.view`) cho
-- MỌI nhân sự nội bộ → ai cũng xem được /reports mọi ngày, mọi ca, mọi cơ sở.
-- Chốt mới: Quản lý + Trưởng ca giữ như cũ; nhân viên khác chỉ xem báo cáo CA
-- MÌNH TRỰC hôm nay ở /bao-cao-ca — quyền ấy suy từ lịch trực, không qua lego,
-- nên migration này KHÔNG cấp gì thêm.
--
-- 1. THU dòng cấp quyền của khối `bao_cao` mà HỆ THỐNG tạo (`granted_by IS
--    NULL`: migration mở full — ly_do 'Mở full lego (Tuyền 30/09/2026)' — và
--    preset chép khi thêm nhân sự — 'Cấp theo preset khi thêm nhân sự'), của
--    người KHÔNG đang giữ vai Quản lý / Trưởng ca ở phòng khám ấy.
--    KHÔNG đụng dòng có người cấp (`granted_by` có người: Quản lý bật lego
--    Báo cáo / thêm nhanh preset trên /phan-quyen) — đó là quyết định có chủ ý.
--    Thu = đóng dòng (`revoked_at`), không xoá. Ràng buộc `capability_grant_thu_hoi`
--    đòi người thu: migration không có người bấm nên ghi chính người bị thu,
--    `ly_do` nối thêm câu nói rõ là migration này thu.
-- 2. `quyen_preset` (nhóm dựng sẵn) của mọi vai trừ Quản lý / Trưởng ca bỏ
--    `bao_cao` → tài khoản tạo mới không có. Khớp `PRESET` ở
--    `permissions/catalogue.py` (`test_nhom_dung_san_khop_voi_hang_so_trong_ma`).
--    Nhóm Quản lý / Trưởng ca chắc chắn có `bao_cao`. Nhóm do quản lý tự tạo
--    (`he_thong = false`) để nguyên.
--
-- Chạy lại được: lần hai không còn dòng nào khớp.

UPDATE public.capability_grant g
   SET revoked_at = now(),
       revoked_by = g.staff_id,
       ly_do = coalesce(g.ly_do || ' · ', '')
               || 'Thu 09/10/2026: báo cáo chỉ Quản lý + Trưởng ca'
               || ' (migration 20261010300000)'
 WHERE g.revoked_at IS NULL
   AND g.granted_by IS NULL
   AND g.capability IN (SELECT c.ma FROM public.capability c
                         WHERE c.work_pack = 'bao_cao')
   AND NOT EXISTS (
         SELECT 1 FROM public.clinic_membership m
          WHERE m.clinic_id = g.clinic_id AND m.staff_id = g.staff_id
            AND m.is_active AND m.role IN ('MANAGEMENT', 'TRUONG_CA'));

UPDATE public.quyen_preset p
   SET khoi = array_remove(p.khoi, 'bao_cao'), sua_luc = now()
 WHERE p.he_thong
   AND p.ma NOT IN ('MANAGEMENT', 'TRUONG_CA')
   AND 'bao_cao' = ANY (p.khoi);

UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['bao_cao']) AS k),
       sua_luc = now()
 WHERE p.he_thong
   AND p.ma IN ('MANAGEMENT', 'TRUONG_CA')
   AND NOT ('bao_cao' = ANY (p.khoi));
