-- XẾP VÀO PHÒNG HÔM NAY = TOÀN QUYỀN CỦA PHÒNG ẤY (Tuyền 28/09/2026).
--
-- "Được xếp vào phòng là chức năng và quyền hạn max rồi mà, lego phải thế chứ."
-- Lỗi thật: điều dưỡng được xếp đứng Phòng thủ thuật 1 bấm "Bắt đầu" bị báo
-- "Bạn chưa được cấp quyền Bắt đầu làm dịch vụ" — quyền phòng chỉ lấy từ lego
-- cấp theo KỸ NĂNG (Phụ SA → phòng siêu âm), lịch làm việc không mở gì.
--
-- `v_quyen_thuc_te` = quyền ĐÃ CẤP (`v_quyen_hieu_luc`, màn Phân quyền quản lý)
-- ∪ quyền THEO LỊCH HÔM NAY: ai có dòng lịch hôm nay (chưa bị từ chối) ở một
-- vị trí thuộc phòng P thì có trọn các khối của lego ứng với việc của phòng P.
-- Chỉ MỞ THÊM, không rút gì. Cửa hỏi quyền (`permissions/can.py`) đọc view này;
-- màn Phân quyền và suy vai vẫn đọc quyền đã cấp (không lẫn quyền theo lịch).
--
-- Bảng tra phòng → khối nằm trong `quyen_theo_lich_bang()`; khối của từng lego
-- CHÉP từ `permissions/catalogue.py` (MAN[...].khoi) — bài kiểm
-- `test_quyen_theo_lich_phong_db.py` so hai bên, lệch là đỏ.

CREATE OR REPLACE FUNCTION public.quyen_theo_lich_bang()
RETURNS TABLE (tien_to text, lego text, work_pack text, theo_phong boolean)
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT * FROM (VALUES
        -- Phòng dịch vụ: khối làm dịch vụ chỉ ở ĐÚNG phòng ấy (như lego 5).
        ('DICHVU-',     'phong',          'thuc_hien',      true),
        ('DICHVU-',     'phong',          'ket_qua',        false),
        ('DICHVU-',     'phong',          'ghi_benh_an',    false),
        ('DICHVU-',     'phong',          'duyet_ket_qua',  false),
        -- Phòng bác sĩ chính (Bàn khám).
        ('KHAM-',       'ban_kham',       'kham',           false),
        ('KHAM-',       'ban_kham',       'chi_dinh',       false),
        ('KHAM-',       'ban_kham',       'ghi_benh_an',    false),
        ('KHAM-',       'ban_kham',       'hoan_tat_kham',  false),
        ('KHAM-',       'ban_kham',       'ket_qua',        false),
        ('KHAM-',       'ban_kham',       'duyet_ket_qua',  false),
        -- Bác sĩ tư vấn.
        ('LUOTKHAM-02', 'tu_van',         'tu_van',         false),
        ('LUOTKHAM-02', 'tu_van',         'ghi_benh_an',    false),
        -- Đo sinh hiệu.
        ('LUOTKHAM-03', 'do_sinh_hieu',   'sinh_hieu',      false),
        -- Quầy lễ tân: tiếp đón + thu tiền (dịch vụ, thuốc).
        ('LUOTKHAM-01', 'tiep_don',       'tiep_don',       false),
        ('LUOTKHAM-01', 'thu_tien_dv',    'thu_tien_dv',    false),
        ('LUOTKHAM-01', 'thu_tien_dv',    'chon_dich_vu',   false),
        ('LUOTKHAM-01', 'thu_tien_dv',    'dieu_phoi',      false),
        ('LUOTKHAM-01', 'thu_tien_thuoc', 'thu_tien_thuoc', false),
        ('LUOTKHAM-14', 'tiep_don',       'tiep_don',       false),
        -- Kho thuốc: nhà thuốc + thu tiền thuốc.
        ('THUOC-',      'kho_thuoc',      'nha_thuoc',      false),
        ('THUOC-',      'kho_thuoc',      'xem_nha_thuoc',  false),
        ('THUOC-',      'thu_tien_thuoc', 'thu_tien_thuoc', false),
        ('DICHVU-THUOC', 'kho_thuoc',     'nha_thuoc',      false),
        ('DICHVU-THUOC', 'kho_thuoc',     'xem_nha_thuoc',  false)
    ) AS t(tien_to, lego, work_pack, theo_phong)
$fn$;

COMMENT ON FUNCTION public.quyen_theo_lich_bang() IS
'Phòng (theo mã việc của phòng) → khối lego được mở cho người xếp lịch ở phòng ấy hôm nay. Khối chép từ permissions/catalogue.py.';

CREATE OR REPLACE VIEW public.v_quyen_thuc_te AS
SELECT q.clinic_id, q.staff_id, q.capability, q.work_pack, q.scope_type, q.scope_id
  FROM public.v_quyen_hieu_luc q
UNION
SELECT l.clinic_id, l.staff_id, c.ma AS capability, c.work_pack,
       CASE WHEN l.theo_phong THEN 'ROOM' ELSE 'CLINIC' END AS scope_type,
       CASE WHEN l.theo_phong THEN l.room_id END AS scope_id
  FROM (
        SELECT DISTINCT w.clinic_id, w.staff_id, v.room_id, b.work_pack,
               b.theo_phong
          FROM public.work_roster w
          JOIN public.vi_tri_lam_viec v
            ON v.clinic_id = w.clinic_id AND v.code = w.station
           AND v.is_active AND v.room_id IS NOT NULL
          JOIN public.clinic_room r
            ON r.id = v.room_id AND r.clinic_id = v.clinic_id AND r.is_active
          JOIN public.clinic_room_node rn
            ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
          JOIN public.quyen_theo_lich_bang() b
            ON rn.node_code LIKE b.tien_to || '%'
         WHERE w.staff_id IS NOT NULL
           AND w.status <> 'REJECTED'
           AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
        UNION
        -- Phòng đối tác: người phòng khám đứng đó thao tác hộ đối tác.
        SELECT DISTINCT w.clinic_id, w.staff_id, v.room_id, 'doi_tac', false
          FROM public.work_roster w
          JOIN public.vi_tri_lam_viec v
            ON v.clinic_id = w.clinic_id AND v.code = w.station
           AND v.is_active AND v.room_id IS NOT NULL
          JOIN public.clinic_room r
            ON r.id = v.room_id AND r.clinic_id = v.clinic_id AND r.is_active
           AND r.la_doi_tac
         WHERE w.staff_id IS NOT NULL
           AND w.status <> 'REJECTED'
           AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
       ) l
  JOIN public.capability c ON c.work_pack = l.work_pack;

COMMENT ON VIEW public.v_quyen_thuc_te IS
'Quyền thực tế = quyền đã cấp ∪ quyền theo lịch hôm nay (xếp vào phòng = toàn quyền phòng ấy, 28/09/2026). Cửa hỏi quyền đọc view này.';

GRANT SELECT ON public.v_quyen_thuc_te TO authenticated, service_role;
