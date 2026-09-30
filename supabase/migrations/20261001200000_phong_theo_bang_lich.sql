-- PHÒNG · TẦNG · VỊ TRÍ THEO BẢNG LỊCH LÀM VIỆC (Tuyền gửi bảng tuần 28/09–04/10/2026).
--
-- Bảng của phòng khám (cột Tầng | Phòng | Vị trí nhân sự) lệch cấu trúc trên
-- hệ thống: "Kho thuốc" ở Tầng 1 trong khi bảng ghi "Quầy thuốc" Tầng 2; thủ
-- thuật ở "Tầng 3" trong khi bảng ghi Tầng 1; hai phòng siêu âm trong khi bảng
-- chỉ có MỘT "Phòng siêu âm 2 máy" (BS 1 · ĐD 1 · BS 2 · ĐD 2)…
--
-- Migration này đưa tên phòng, tầng, tên vị trí, thứ tự về đúng bảng:
--
--   1. Phòng (tìm theo `code`, KHÔNG theo tên): đổi tên + tầng + thứ tự.
--      Đo sinh hiệu, Lấy mẫu, Bác sĩ tư vấn, Phòng đối tác giữ tên và tầng.
--   2. GỘP HAI PHÒNG SIÊU ÂM: giữ KN-SA1 ("Phòng siêu âm 2 máy", Tầng 4).
--      Vị trí T1_SA_* (BS/ĐD/Thư ký 1) chuyển sang KN-SA1; KN-SA1 nhận đủ
--      node của KN-SA-T1. Việc CÒN MỞ đang giữ KN-SA-T1 CHUYỂN THẲNG BẰNG
--      MIGRATION NÀY, MỘT LẦN (không qua lệnh xếp phòng, không phát sự kiện —
--      khách không đổi chỗ thật, chỉ là hai tên của cùng một phòng máy):
--        * service_order.room_id của chỉ định chưa xong (không phải performed /
--          not_performed / cancelled) — tăng routing_revision + version để màn
--          đang mở không ghi đè bằng bản cũ;
--        * service_order.phong_du_kien_id của chỉ định chưa xong;
--        * queue_entry (hàng ROOM) còn sống (không done / left / cancelled);
--        * work_item còn mở (PENDING / IN_PROGRESS);
--        * visit.current_room_id của lượt chưa đóng;
--        * ky_nang.phong_ids (kỹ năng "Phụ SA" trỏ phòng cũ → phòng giữ lại);
--        * dispatch_threshold: KN-SA1 chưa có ngưỡng riêng thì chép của KN-SA-T1.
--      Lịch sử (chỉ định đã xong, lần làm `service_execution_attempt`, hàng chờ
--      đã xong) GIỮ trỏ KN-SA-T1 — phòng chỉ TẮT, không xoá.
--      Sau đó KN-SA-T1: is_active = false, accepting = false, show_on_tv = false.
--   3. T4_BIO_DD sang Phòng Sàn chậu (kỹ năng "Bio" thêm phòng Sàn chậu).
--   4. Vị trí: tên (`ten` + `ten_ngan` = chữ trong bảng), chữ `tang` / `phong`
--      khớp phòng mới, thứ tự = thứ tự dòng của bảng. Vị trí thư ký không có
--      trong bảng nhưng GIỮ (mỗi bác sĩ có ĐD / thư ký riêng), đứng cuối phòng
--      (riêng phòng siêu âm: BS 1 · ĐD 1 · TK 1 · BS 2 · ĐD 2 · TK 2).
--
-- CHỈ tenant có các mã phòng ấy (mọi câu lọc theo `clinic_id` + `code`).
-- CHẠY LẠI ĐƯỢC: câu cập nhật chỉ ghi dòng còn khác; chuyển phòng chỉ đụng
-- dòng còn trỏ KN-SA-T1; chèn node dùng ON CONFLICT DO NOTHING.
-- Một khối DO duy nhất — áp bằng runner nào cũng nguyên khối.

DO $migration$
DECLARE
    c record;
    n integer;
BEGIN
    -- ── 1. Phòng: tên + tầng + thứ tự theo bảng ────────────────────────────
    -- ten / tang NULL = giữ nguyên (phòng không có trong bảng).
    UPDATE public.clinic_room r
       SET name = coalesce(m.ten, r.name),
           floor = coalesce(m.tang, r.floor),
           sort = m.sort,
           updated_at = now()
      FROM (VALUES
        ('KN-TIEPDON',   'Quầy tiếp đón',        'Tầng 1', 10),
        ('KN-DOCHISO',   NULL,                   NULL,     20),
        ('KN-LAYMAU',    NULL,                   NULL,     30),
        ('KN-NOITIET',   'Phòng Nội tiết',       'Tầng 1', 40),
        ('KN-TUVAN',     NULL,                   NULL,     45),
        ('KN-THUTHUAT',  'Phòng thủ thuật',      'Tầng 1', 50),
        ('KN-TTNG',      'Thủ thuật ngoài giờ',  'Tầng 1', 60),
        ('KN-QUAYTHUOC', 'Quầy thuốc',           'Tầng 2', 70),
        ('KN-SANCHAU',   'Phòng Sàn chậu',       'Tầng 4', 80),
        ('KN-SA1',       'Phòng siêu âm 2 máy',  'Tầng 4', 90),
        ('KN-SAN-BIO',   'Phòng Sản / Siêu âm',  'Tầng 4', 100),
        ('KN-DOITAC',    NULL,                   NULL,     110)
      ) AS m(code, ten, tang, sort)
     WHERE r.code = m.code
       AND (r.name, r.floor, r.sort)
           IS DISTINCT FROM (coalesce(m.ten, r.name), coalesce(m.tang, r.floor), m.sort);

    -- ── 2. Gộp KN-SA-T1 vào KN-SA1 (từng tenant có cả hai mã) ───────────────
    FOR c IN
        SELECT cu.clinic_id, cu.id AS cu_id, moi.id AS moi_id
          FROM public.clinic_room cu
          JOIN public.clinic_room moi
            ON moi.clinic_id = cu.clinic_id AND moi.code = 'KN-SA1'
         WHERE cu.code = 'KN-SA-T1'
    LOOP
        -- Phòng giữ lại làm được mọi việc phòng cũ làm.
        INSERT INTO public.clinic_room_node (clinic_id, room_id, node_code)
        SELECT c.clinic_id, c.moi_id, rn.node_code
          FROM public.clinic_room_node rn
         WHERE rn.room_id = c.cu_id
        ON CONFLICT (room_id, node_code) DO NOTHING;

        UPDATE public.clinic_room
           SET is_active = true, accepting = true, updated_at = now()
         WHERE id = c.moi_id AND NOT (is_active AND accepting);

        -- Chỉ định chưa xong đang xếp ở phòng cũ.
        UPDATE public.service_order
           SET room_id = c.moi_id,
               routing_revision = routing_revision + 1,
               version = version + 1,
               updated_at = now()
         WHERE clinic_id = c.clinic_id
           AND room_id = c.cu_id
           AND exec_status NOT IN ('performed', 'not_performed', 'cancelled');
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'gộp siêu âm: % chỉ định còn mở KN-SA-T1 → KN-SA1', n;

        UPDATE public.service_order
           SET phong_du_kien_id = c.moi_id, updated_at = now()
         WHERE clinic_id = c.clinic_id
           AND phong_du_kien_id = c.cu_id
           AND exec_status NOT IN ('performed', 'not_performed', 'cancelled');

        UPDATE public.queue_entry
           SET room_id = c.moi_id, version = version + 1, updated_at = now()
         WHERE clinic_id = c.clinic_id
           AND room_id = c.cu_id
           AND status NOT IN ('done', 'left', 'cancelled');
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'gộp siêu âm: % hàng chờ còn sống → KN-SA1', n;

        UPDATE public.work_item
           SET room_id = c.moi_id, version = version + 1, updated_at = now()
         WHERE clinic_id = c.clinic_id
           AND room_id = c.cu_id
           AND status IN ('PENDING', 'IN_PROGRESS');

        UPDATE public.visit
           SET current_room_id = c.moi_id, updated_at = now()
         WHERE clinic_id = c.clinic_id
           AND current_room_id = c.cu_id
           AND closed_at IS NULL;

        UPDATE public.ky_nang
           SET phong_ids = ARRAY(
                   SELECT DISTINCT CASE WHEN p = c.cu_id THEN c.moi_id ELSE p END
                     FROM unnest(phong_ids) AS p
                    ORDER BY 1),
               updated_at = now()
         WHERE clinic_id = c.clinic_id
           AND c.cu_id = ANY (phong_ids);

        INSERT INTO public.dispatch_threshold
            (clinic_id, room_id, wait_minutes, max_waiting)
        SELECT d.clinic_id, c.moi_id, d.wait_minutes, d.max_waiting
          FROM public.dispatch_threshold d
         WHERE d.room_id = c.cu_id
           AND NOT EXISTS (SELECT 1 FROM public.dispatch_threshold x
                            WHERE x.room_id = c.moi_id);

        -- Vị trí của phòng cũ sang phòng giữ lại (tên / tầng / thứ tự ở mục 4).
        UPDATE public.vi_tri_lam_viec
           SET room_id = c.moi_id
         WHERE clinic_id = c.clinic_id
           AND code IN ('T1_SA_BS', 'T1_SA_DD', 'T1_SA_TK')
           AND room_id IS DISTINCT FROM c.moi_id;

        UPDATE public.clinic_room
           SET is_active = false, accepting = false, show_on_tv = false,
               updated_at = now()
         WHERE id = c.cu_id AND (is_active OR accepting OR show_on_tv);
    END LOOP;

    -- ── 3. Điều dưỡng Bio sang Phòng Sàn chậu ───────────────────────────────
    UPDATE public.vi_tri_lam_viec v
       SET room_id = r.id
      FROM public.clinic_room r
     WHERE r.clinic_id = v.clinic_id AND r.code = 'KN-SANCHAU'
       AND v.code = 'T4_BIO_DD'
       AND v.room_id IS DISTINCT FROM r.id;

    -- Kỹ năng "Bio" (phạm vi lego Phòng dịch vụ) có thêm Phòng Sàn chậu — chỉ
    -- THÊM, không bỏ phòng Sản / Siêu âm.
    UPDATE public.ky_nang k
       SET phong_ids = k.phong_ids || r.id, updated_at = now()
      FROM public.clinic_room r
     WHERE r.clinic_id = k.clinic_id AND r.code = 'KN-SANCHAU'
       AND k.ma = 'bio'
       AND NOT (r.id = ANY (k.phong_ids));

    -- ── 4. Vị trí: tên theo bảng, chữ tầng / phòng, thứ tự dòng ─────────────
    -- `phong` NULL = không tên phòng (Đo chỉ số, Lấy mẫu — bảng để trống).
    UPDATE public.vi_tri_lam_viec v
       SET ten = m.ten, ten_ngan = m.ten, tang = m.tang, phong = m.phong,
           sort = m.sort
      FROM (VALUES
        ('T1_LETAN',        'Lễ tân',                   'Tầng 1', 'Quầy tiếp đón',       10),
        ('T1_THUNGAN',      'Thu ngân',                 'Tầng 1', 'Quầy tiếp đón',       20),
        ('T1_DOCHISO',      'Đo chỉ số sức khoẻ (HA, MĐX, test nước tiểu), dịch cơ thể',
                                                        'Tầng 1', NULL,                  30),
        ('T1_LAYMAU',       'Lấy mẫu (máu)',            'Tầng 1', NULL,                  40),
        ('T1_BS_NOITIET',   'BS Nội tiết',              'Tầng 1', 'Phòng Nội tiết',      50),
        ('T1_HOIBENH',      'Hỏi bệnh ban đầu',         'Tầng 1', 'Phòng Nội tiết',      60),
        ('T1_TKYK',         'Thư ký y khoa',            'Tầng 1', 'Phòng Nội tiết',      70),
        ('T1_TT_BS',        'BS',                       'Tầng 1', 'Phòng thủ thuật',     80),
        ('T1_TT_DD',        'Điều dưỡng',               'Tầng 1', 'Phòng thủ thuật',     90),
        ('T1_TT_TK',        'Thư ký',                   'Tầng 1', 'Phòng thủ thuật',     95),
        ('T1_TTNG_BS',      'BS',                       'Tầng 1', 'Thủ thuật ngoài giờ', 100),
        ('T1_TTNG_DD1',     'Điều dưỡng 1',             'Tầng 1', 'Thủ thuật ngoài giờ', 110),
        ('T1_TTNG_DD2',     'Điều dưỡng 2',             'Tầng 1', 'Thủ thuật ngoài giờ', 120),
        ('T1_TTNG_TK',      'Thư ký',                   'Tầng 1', 'Thủ thuật ngoài giờ', 125),
        ('T2_XEPTHUOC',     'Xếp thuốc + Giải thích thuốc', 'Tầng 2', 'Quầy thuốc',      130),
        ('T2_TAODON',       'Tạo đơn thuốc + Thu ngân', 'Tầng 2', 'Quầy thuốc',          140),
        ('T4_SANCHAU_BS',   'BS Sàn chậu',              'Tầng 4', 'Phòng Sàn chậu',      150),
        ('T4_SANCHAU_BSTT', 'BS Thủ thuật (soi âm hộ/âm vật/CTC, nong/tách bao quy đầu âm vật)',
                                                        'Tầng 4', 'Phòng Sàn chậu',      160),
        ('T4_SANCHAU_DD',   'Điều dưỡng Sàn chậu (Thủ thuật)', 'Tầng 4', 'Phòng Sàn chậu', 170),
        ('T4_BIO_DD',       'Điều dưỡng Bio',           'Tầng 4', 'Phòng Sàn chậu',      180),
        ('T4_SANCHAU_TK',   'Thư ký Sàn chậu',          'Tầng 4', 'Phòng Sàn chậu',      185),
        ('T4_SANCHAU_TKTT', 'Thư ký Thủ thuật',         'Tầng 4', 'Phòng Sàn chậu',      187),
        ('T1_SA_BS',        'BS 1',                     'Tầng 4', 'Phòng siêu âm 2 máy', 190),
        ('T1_SA_DD',        'Điều dưỡng 1',             'Tầng 4', 'Phòng siêu âm 2 máy', 200),
        ('T1_SA_TK',        'Thư ký 1',                 'Tầng 4', 'Phòng siêu âm 2 máy', 205),
        ('T4_SA_BS1',       'BS 2',                     'Tầng 4', 'Phòng siêu âm 2 máy', 210),
        ('T4_SA_DD1',       'Điều dưỡng 2',             'Tầng 4', 'Phòng siêu âm 2 máy', 220),
        ('T4_SA_TK1',       'Thư ký 2',                 'Tầng 4', 'Phòng siêu âm 2 máy', 225),
        ('T4_SAN_BS',       'BS Sản / BS 3',            'Tầng 4', 'Phòng Sản / Siêu âm', 230),
        ('T4_SAN_DD',       'Điều dưỡng Sản / Điều dưỡng 3', 'Tầng 4', 'Phòng Sản / Siêu âm', 240),
        ('T4_SAN_TK',       'Thư ký Sản / Thư ký 3',    'Tầng 4', 'Phòng Sản / Siêu âm', 245)
      ) AS m(code, ten, tang, phong, sort)
     WHERE v.code = m.code
       -- chỉ tenant có bộ phòng theo bảng
       AND EXISTS (SELECT 1 FROM public.clinic_room r
                    WHERE r.clinic_id = v.clinic_id AND r.code = 'KN-SA1')
       AND (v.ten, v.ten_ngan, v.tang, v.phong, v.sort)
           IS DISTINCT FROM (m.ten, m.ten, m.tang, m.phong, m.sort);
END
$migration$;
