-- MỘT NGÀY ĐIỀU PHỐI — để bảng Trưởng ca có gì mà nhìn (Tuyền 16/09/2026).
--
-- ĐỘC LẬP, KHÔNG nối đuôi `demo_clinic_day.sql`. Fixture kia KHÔNG chạy lại
-- được nữa: nó mở đầu bằng `DELETE FROM visit`, mà `visit` là bảng chỉ-ghi-thêm
-- (trigger `prevent_hard_delete`), nên lần chạy thứ hai dừng ngay ở dòng dọn.
-- Nó cũng không xếp ai vào phòng nào, nên sơ đồ phòng trắng trơn.
--
-- Fixture này dùng lại BỆNH NHÂN đã có (mã DEMO-*) và làm bốn việc:
--   1. ĐÓNG lượt khám của những NGÀY TRƯỚC còn bỏ ngỏ. Chúng là rác của các
--      lần thử cũ, và chúng làm hỏng mọi con số: một lượt check-in từ thứ Hai
--      chưa đóng hiện ra ở hàng đợi hôm nay với "chờ 7350 phút".
--   2. TẠO lượt khám cho HÔM NAY, rải qua các bước khác nhau.
--   3. XẾP PHÒNG cho lượt hôm nay theo đúng bước mỗi người đang đứng.
--   4. Thêm CHỈ ĐỊNH của bác sĩ cho vài lượt, đủ trạng thái khác nhau, để khối
--      "Bác sĩ chỉ định gì" ở panel điều phối có nội dung thật.
--
-- GIẢ HOÀN TOÀN, chỉ nạp vào local/staging. Chạy lại được.
--
--   docker exec -i clinicai_thu_db psql -U postgres -d postgres \
--     < supabase/fixtures/ngay_dieu_phoi_demo.sql

\set ON_ERROR_STOP on

DO $dp$
DECLARE
    v_clinic uuid := 'a0000000-0000-4000-8000-000000000001';
    v_letan  uuid;
    v_bs_a   uuid;
    v_bs_sa  uuid;
    r        record;
    v_room   uuid;
    v_loc    uuid;
    v_svc    uuid;
    v_appt   uuid;
    v_visit  uuid;
    v_wi     uuid;
    v_buoc   text;
    v_n      integer := 0;
BEGIN
    SELECT id INTO v_letan FROM staff WHERE full_name = 'Le tan local';
    SELECT id INTO v_bs_a  FROM staff WHERE full_name = 'BS A local';
    SELECT id INTO v_bs_sa FROM staff WHERE full_name = 'BS SA local';
    SELECT id INTO v_loc FROM clinic_location
     WHERE clinic_id = v_clinic AND is_active ORDER BY code LIMIT 1;
    SELECT id INTO v_svc FROM service_type
     WHERE clinic_id = v_clinic AND is_active ORDER BY code LIMIT 1;
    IF v_loc IS NULL OR v_svc IS NULL OR v_letan IS NULL THEN
        RAISE EXCEPTION 'thiếu fixture nền — chạy staff_logins.sql và local_data.sql trước';
    END IF;

    -- ── 1. Dọn lượt của ngày trước ──────────────────────────────────────────
    -- Đóng chứ không XOÁ: `visit` là một trong ba bảng cấm xoá cứng. Trạng thái
    -- INCOMPLETE + lý do là đúng đường mà màn check-out ghi khi khách về giữa
    -- chừng, nên dữ liệu vẫn đọc được và không ai tưởng nó biến mất.
    -- `finished_at` phải có khi việc về trạng thái cuối — ràng buộc
    -- `work_item_finished_when_terminal` canh đúng chuyện ấy, và nó có lý:
    -- một việc đã huỷ mà không có mốc kết thúc thì mọi phép đo thời gian sau
    -- này đếm nó như còn đang chạy.
    UPDATE work_item w
       SET status = 'CANCELLED', finished_at = now(),
           version = version + 1, updated_at = now()
      FROM visit v
     WHERE v.visit_id = w.visit_id
       AND v.clinic_id = v_clinic AND v.closed_at IS NULL
       AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date < current_date
       AND w.status IN ('PENDING', 'IN_PROGRESS');

    UPDATE visit
       SET closed_at = checked_in_at + interval '2 hours',
           closed_by_staff_id = v_letan,
           status = 'INCOMPLETE',
           -- Ràng buộc `visit_incomplete_can_ly_do` đòi lý do khi đóng dở —
           -- đúng luật màn check-out, và fixture không được phép lách nó.
           incomplete_reason = 'Dọn dữ liệu demo ngày trước',
           current_room_id = NULL,
           current_node_code = NULL,
           updated_at = now()
     WHERE clinic_id = v_clinic AND closed_at IS NULL
       AND (checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date < current_date;

    UPDATE appointment a
       SET status = 'COMPLETED', updated_at = now()
     WHERE a.clinic_id = v_clinic
       AND a.status = 'CHECKED_IN'
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date < current_date;

    -- ĐÓNG CẢ LƯỢT HÔM NAY DO CHÍNH FIXTURE NÀY TẠO (bệnh nhân mã DEMO-*).
    -- Không có bước này thì mỗi lần chạy lại đắp thêm một ngày làm việc nữa
    -- lên ngày cũ: 34 lượt thành 68 rồi 102, và mọi con số trên bảng điều phối
    -- thành vô nghĩa. Lượt của bệnh nhân THẬT (mã BN-*) không bị đụng.
    UPDATE work_item w
       SET status = 'CANCELLED', finished_at = now(),
           version = version + 1, updated_at = now()
      FROM visit v JOIN patient p
        ON p.clinic_patient_id = v.clinic_patient_id
     WHERE v.visit_id = w.visit_id AND v.clinic_id = v_clinic
       AND v.closed_at IS NULL AND p.patient_code LIKE 'DEMO-%'
       AND w.status IN ('PENDING', 'IN_PROGRESS');

    UPDATE visit v
       SET closed_at = now(), closed_by_staff_id = v_letan,
           status = 'INCOMPLETE',
           incomplete_reason = 'Dọn dữ liệu demo lần chạy trước',
           current_room_id = NULL, current_node_code = NULL, updated_at = now()
      FROM patient p
     WHERE p.clinic_patient_id = v.clinic_patient_id
       AND v.clinic_id = v_clinic AND v.closed_at IS NULL
       AND p.patient_code LIKE 'DEMO-%';

    -- HUỶ chứ không "hoàn thành": chỉ số `uq_appointment_patient_slot_live`
    -- coi mọi trạng thái khác CANCELLED/NO_SHOW/DOCTOR_DECLINED là còn sống,
    -- nên đánh COMPLETED rồi tạo lại đúng khung giờ ấy là đâm vào chính nó.
    UPDATE appointment a
       SET status = 'CANCELLED', cancelled_at = now(),
           ly_do_huy_ma = 'KHAC',
           -- Mã "KHAC" bắt buộc viết rõ lý do (ràng buộc
           -- `appointment_ly_do_khac_phai_viet`) — cùng luật màn huỷ lịch.
           cancellation_reason = 'Dọn dữ liệu demo lần chạy trước',
           updated_at = now()
      FROM patient p
     WHERE p.clinic_patient_id = a.clinic_patient_id
       AND a.clinic_id = v_clinic
       AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = current_date
       AND p.patient_code LIKE 'DEMO-%';

    -- ── 2. Lượt khám của HÔM NAY ────────────────────────────────────────────
    -- Dùng lại bệnh nhân DEMO-* đang có; mỗi người một lịch hẹn + một lượt đã
    -- check-in, giờ đến rải đều từ 7h30. `instantiate_visit_workflow` dựng
    -- chuỗi việc đúng như lúc lễ tân bấm check-in thật — không chèn tay
    -- work_item, để fixture không trôi khỏi quy trình thật.
    FOR r IN
        SELECT p.clinic_patient_id, row_number() OVER (ORDER BY p.patient_code) AS n
          FROM patient p
         WHERE p.clinic_id = v_clinic AND p.patient_code LIKE 'DEMO-%'
           AND NOT EXISTS (SELECT 1 FROM visit v
                            WHERE v.clinic_patient_id = p.clinic_patient_id
                              AND v.closed_at IS NULL)
         ORDER BY p.patient_code
         LIMIT 20
    LOOP
        v_appt := gen_random_uuid();
        INSERT INTO appointment (
            id, clinic_id, clinic_patient_id, location_id, service_type_id,
            doctor_id, slot_start, slot_end, status, booking_channel,
            is_walkin, is_priority_slot
        ) VALUES (
            v_appt, v_clinic, r.clinic_patient_id, v_loc, v_svc,
            CASE WHEN r.n % 3 = 0 THEN v_bs_sa ELSE v_bs_a END,
            date_trunc('day', now()) + interval '7 hours 30 minutes'
                + ((r.n - 1) * interval '15 minutes'),
            date_trunc('day', now()) + interval '7 hours 45 minutes'
                + ((r.n - 1) * interval '15 minutes'),
            'CHECKED_IN',
            -- ĐỀU LÀ LỊCH ĐẶT TRƯỚC. Trần vãng lai là 1 chỗ/khung (trigger
            -- `enforce_slot_capacity`), nên rải ca WALK_IN vào đây là fixture
            -- tự đâm vào chính luật sức chứa của hệ thống.
            'ONLINE',
            false,
            (r.n % 9 = 0)
        );

        INSERT INTO visit (clinic_id, clinic_patient_id, appointment_id,
                           attending_doctor_id, status, checked_in_at, checked_in_by)
        VALUES (v_clinic, r.clinic_patient_id, v_appt,
                CASE WHEN r.n % 3 = 0 THEN v_bs_sa ELSE v_bs_a END,
                CASE WHEN r.n <= 6 THEN 'IN_PROGRESS' ELSE 'OPEN' END,
                now() - ((60 - r.n * 2) * interval '1 minute'), v_letan)
        RETURNING visit_id INTO v_visit;

        PERFORM public.instantiate_visit_workflow(v_clinic, v_visit, v_letan, 'RECEPTION');

        -- Đẩy mỗi người đi một quãng khác nhau: qua tiếp nhận → qua xác minh →
        -- qua sinh hiệu → đang khám. Không thì cả bảng đứng chung một chỗ.
        FOR v_buoc IN
            SELECT * FROM unnest(ARRAY['LUOTKHAM-01', 'LUOTKHAM-02', 'LUOTKHAM-03']) AS b
        LOOP
            EXIT WHEN r.n > 16 AND v_buoc = 'LUOTKHAM-02';
            EXIT WHEN r.n > 11 AND v_buoc = 'LUOTKHAM-03';
            SELECT id INTO v_wi FROM work_item
             WHERE visit_id = v_visit AND node_code = v_buoc AND status <> 'CANCELLED';
            CONTINUE WHEN v_wi IS NULL;
            UPDATE work_item
               SET status = 'COMPLETED', started_at = now() - interval '20 minutes',
                   finished_at = now() - interval '10 minutes', version = version + 1
             WHERE id = v_wi;
            INSERT INTO work_item_event (clinic_id, work_item_id, command, to_status,
                                         actor_staff_id, actor_role)
            VALUES (v_clinic, v_wi, 'complete', 'COMPLETED', v_letan, 'RECEPTION');
        END LOOP;

        -- Sáu người đang được bác sĩ khám dở.
        IF r.n <= 6 THEN
            SELECT id INTO v_wi FROM work_item
             WHERE visit_id = v_visit AND node_code = 'LUOTKHAM-05' AND status <> 'CANCELLED';
            IF v_wi IS NOT NULL THEN
                UPDATE work_item SET status = 'IN_PROGRESS',
                       started_at = now() - interval '12 minutes', version = version + 1
                 WHERE id = v_wi;
                INSERT INTO work_item_event (clinic_id, work_item_id, command, to_status,
                                             actor_staff_id, actor_role)
                VALUES (v_clinic, v_wi, 'start', 'IN_PROGRESS', v_bs_a, 'DOCTOR');
                -- `round_no` = lượt khám thứ mấy trong ngày của bệnh nhân
                -- (bác sĩ khám → chỉ định → khám lại là lượt 2). Cột NOT NULL.
                -- `kind` PRIMARY đi đôi với `round_no = 1` (ràng buộc canh
                -- đúng cặp ấy): lượt khám đầu là PRIMARY, khám lại sau khi có
                -- kết quả là REVIEW.
                INSERT INTO consultation (clinic_id, visit_id, doctor_staff_id,
                                          status, round_no, kind)
                VALUES (v_clinic, v_visit, v_bs_a, 'in_progress', 1, 'PRIMARY')
                ON CONFLICT DO NOTHING;
            END IF;
        END IF;
    END LOOP;

    -- ── 2. Xếp phòng cho lượt HÔM NAY ───────────────────────────────────────
    -- Mỗi lượt đứng ở bước nào thì vào phòng phục vụ bước ấy; chia đều các
    -- phòng cùng bước để sơ đồ có chỗ đông chỗ vắng, chứ không dồn hết một chỗ.
    FOR r IN
        SELECT v.visit_id,
               w.node_code,
               row_number() OVER (PARTITION BY w.node_code ORDER BY v.checked_in_at) AS thu_tu
          FROM visit v
          JOIN LATERAL (
              SELECT w1.node_code
                FROM work_item w1
               WHERE w1.visit_id = v.visit_id
                 AND w1.status IN ('IN_PROGRESS', 'PENDING')
               ORDER BY (w1.status = 'IN_PROGRESS') DESC, w1.created_at
               LIMIT 1
          ) w ON TRUE
         WHERE v.clinic_id = v_clinic AND v.closed_at IS NULL
    LOOP
        SELECT id INTO v_room
          FROM (
              SELECT id, row_number() OVER (ORDER BY sort, code) AS n,
                     count(*) OVER () AS tong
                FROM clinic_room
               WHERE clinic_id = v_clinic AND is_active AND accepting
                 AND (node_code = r.node_code
                      OR id IN (SELECT room_id FROM clinic_room_node
                                 WHERE node_code = r.node_code))
          ) p
         WHERE n = ((r.thu_tu - 1) % tong) + 1;

        CONTINUE WHEN v_room IS NULL;

        UPDATE visit
           SET current_node_code = r.node_code,
               current_room_id = v_room,
               -- Giờ vào trạm rải ra 3–55 phút để cột "chờ" có cả xanh lẫn đỏ:
               -- một bảng mà ai cũng chờ đúng 5 phút thì không thử được ngưỡng.
               current_node_since = now() - ((3 + (v_n * 7) % 52) * interval '1 minute'),
               updated_at = now()
         WHERE visit_id = r.visit_id;
        v_n := v_n + 1;
    END LOOP;

    -- ── 3. Chỉ định của bác sĩ ──────────────────────────────────────────────
    DELETE FROM service_order
     WHERE clinic_id = v_clinic
       AND service_code IN ('SA-THAI', 'XN-MAU', 'TT-DOT');

    INSERT INTO service_order (
        clinic_id, visit_id, consultation_id, service_code, service_name,
        node_code, source, exec_status, recorded_by, authorized_by, authorized_at,
        room_id
    )
    SELECT v_clinic, c.visit_id, c.id, x.code, x.ten, x.node, 'VISIT_ORDER',
           x.trang_thai, v_bs_a,
           CASE WHEN x.trang_thai = 'draft' THEN NULL ELSE v_bs_a END,
           CASE WHEN x.trang_thai = 'draft' THEN NULL ELSE now() END,
           CASE WHEN x.trang_thai IN ('assigned', 'in_progress', 'performed')
                THEN (SELECT id FROM clinic_room
                       WHERE clinic_id = v_clinic AND code = x.phong)
                ELSE NULL END
      FROM (
          SELECT co.id, co.visit_id,
                 row_number() OVER (ORDER BY co.created_at) AS n
            FROM consultation co
            JOIN visit v ON v.visit_id = co.visit_id
           WHERE co.clinic_id = v_clinic AND v.closed_at IS NULL
      ) c
      JOIN (VALUES
          (1, 'SA-THAI', 'Siêu âm thai',        'DICHVU-SIEUAM',     'authorized',  'SA1'),
          (2, 'XN-MAU',  'Xét nghiệm máu',      'DICHVU-LAYMAU-MAU', 'assigned',    'XETNGHIEM'),
          (3, 'SA-THAI', 'Siêu âm thai',        'DICHVU-SIEUAM',     'in_progress', 'SA2'),
          (4, 'TT-DOT',  'Đốt viêm lộ tuyến',   'DICHVU-THUTHUAT',   'draft',       'THUTHUAT1'),
          (5, 'XN-MAU',  'Xét nghiệm máu',      'DICHVU-LAYMAU-MAU', 'performed',   'XETNGHIEM')
      ) AS x(n, code, ten, node, trang_thai, phong) ON x.n = c.n;

    RAISE NOTICE 'Đã xếp phòng cho % lượt khám hôm nay.', v_n;
END
$dp$;

\echo 'Phòng đang có người:'
SELECT r.floor AS tang, r.code, r.name,
       count(*) FILTER (WHERE v.status = 'IN_PROGRESS') AS dang_kham,
       count(*)                                         AS tong_o_phong
  FROM visit v JOIN clinic_room r ON r.id = v.current_room_id
 WHERE v.closed_at IS NULL
 GROUP BY 1, 2, 3 ORDER BY 1, 2;

\echo 'Chỉ định của bác sĩ:'
SELECT service_name, exec_status, count(*) FROM service_order GROUP BY 1, 2 ORDER BY 1;
