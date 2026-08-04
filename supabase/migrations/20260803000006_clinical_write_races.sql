-- Hai đường ghi lâm sàng đọc-rồi-ghi mà không khoá gì. Đóng lại.
--
-- BỐI CẢNH, KÈM MỘT ĐÍNH CHÍNH. Một rà soát trước đó nói rằng bấm "Lưu" hai lần
-- sẽ nhân đôi đơn thuốc. ĐIỀU ĐÓ SAI, và đã kiểm lại bằng mã nguồn:
-- clinical_record_service._replace_prescriptions xoá toàn bộ đơn của lượt khám
-- rồi ghi lại, tất cả trong CÙNG một transaction với phần bệnh án — nên lần bấm
-- thứ hai thay thế lần thứ nhất chứ không cộng thêm. Phiếu khám
-- (clinical_form_response) và bệnh án (clinical_record) cũng an toàn: cả hai
-- dùng ON CONFLICT ... DO UPDATE.
--
-- Nhưng hai chỗ thì thật sự hở, và cả hai đều cùng một hình dạng: ĐỌC xem đã có
-- chưa, rồi GHI nếu chưa — không có gì ngăn hai request cùng đọc "chưa có".
--
--   1. ultrasound_record. ultrasound_service.save_measurements() SELECT phiếu
--      của lượt khám, không thấy thì INSERT. Bảng KHÔNG có ràng buộc duy nhất
--      nào trên (visit_id), chỉ có index thường. Hai lần lưu gần nhau — bấm đúp,
--      hoặc điều dưỡng và bác sĩ siêu âm cùng lưu — tạo HAI phiếu siêu âm cho
--      một lượt khám. Không có lỗi nào báo. Lần đọc sau lấy phiếu nào là tuỳ thứ
--      tự trả về của database, tức số đo hiển thị có thể là bản cũ.
--
--   2. order_services(). Nó tránh trùng bằng `WHERE NOT EXISTS (SELECT 1 FROM
--      existing ...)`, đọc trong cùng câu lệnh nhưng KHÔNG có index duy nhất nào
--      đứng sau. Hai lần chỉ định cùng lúc đều thấy "chưa có" và đều ghi.
--
-- VÌ SAO KHÔNG DÙNG IDEMPOTENCY-KEY CHO HAI CHỖ NÀY. Khoá idempotency chặn
-- việc GỬI LẠI CÙNG MỘT REQUEST. Nó không chặn hai người, hai thiết bị, hai tab
-- cùng lưu — mà đó mới là chuyện xảy ra ở phòng siêu âm. Ràng buộc trong
-- database chặn cả hai, và chặn cả những đường ghi chưa được viết ra.

-- (Không dùng `\set` — đó là lệnh psql, `supabase db push` không hiểu.
--  Xem chú thích trong 20260803000004.)

-- ---------------------------------------------------------------------------
-- 1. ultrasound_record: một phiếu cho mỗi (lượt khám × loại siêu âm)
-- ---------------------------------------------------------------------------
-- Dọn trùng TRƯỚC khi tạo ràng buộc, nếu không CREATE UNIQUE INDEX đổ và cả
-- migration dừng. Giữ bản ghi MỚI NHẤT theo performed_at: nó là lần nhập gần
-- nhất, tức thứ mà người dùng tin là đang có hiệu lực.
--
-- Không xoá, chỉ gộp: các bản cũ được ghi lại vào event_log trước khi biến mất,
-- vì một số đo siêu âm bị xoá mà không để lại vết là chuyện không được phép xảy
-- ra trong hồ sơ lâm sàng.

DO $dedupe$
DECLARE
    v_dupes int;
BEGIN
    SELECT count(*) INTO v_dupes
      FROM (
        SELECT clinic_id, visit_id, ultrasound_type
          FROM public.ultrasound_record
         WHERE visit_id IS NOT NULL
         GROUP BY clinic_id, visit_id, ultrasound_type
        HAVING count(*) > 1
      ) d;

    IF v_dupes = 0 THEN
        RAISE NOTICE 'ultrasound_record: không có trùng lặp';
        RETURN;
    END IF;

    RAISE NOTICE 'ultrasound_record: gộp % nhóm trùng', v_dupes;

    INSERT INTO public.event_log
        (clinic_id, event_type, aggregate_type, aggregate_id, payload,
         metadata, source, event_published)
    SELECT r.clinic_id,
           'ultrasound.duplicate_superseded',
           'ultrasound_record',
           r.ultrasound_id::text,
           jsonb_build_object(
               'visit_id', r.visit_id,
               'ultrasound_type', r.ultrasound_type,
               'performed_at', r.performed_at,
               'superseded_by', r.keep_id
           ),
           jsonb_build_object('origin', 'migration:20260803000006'),
           'migration:20260803000006',
           FALSE
      FROM (
        SELECT u.*,
               first_value(u.ultrasound_id) OVER w AS keep_id,
               row_number()          OVER w AS rn
          FROM public.ultrasound_record u
         WHERE u.visit_id IS NOT NULL
        WINDOW w AS (
            PARTITION BY u.clinic_id, u.visit_id, u.ultrasound_type
            ORDER BY u.performed_at DESC NULLS LAST, u.ultrasound_id DESC
        )
      ) r
     WHERE r.rn > 1;

    DELETE FROM public.ultrasound_record u
     USING (
        SELECT ultrasound_id,
               row_number() OVER (
                   PARTITION BY clinic_id, visit_id, ultrasound_type
                   ORDER BY performed_at DESC NULLS LAST, ultrasound_id DESC
               ) AS rn
          FROM public.ultrasound_record
         WHERE visit_id IS NOT NULL
     ) d
     WHERE d.ultrasound_id = u.ultrasound_id AND d.rn > 1;
END
$dedupe$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ultrasound_visit_type
    ON public.ultrasound_record (clinic_id, visit_id, ultrasound_type)
    WHERE visit_id IS NOT NULL;

COMMENT ON INDEX public.uq_ultrasound_visit_type IS
    'Một phiếu siêu âm cho mỗi (phòng khám × lượt khám × loại). Biến cuộc đua '
    'đọc-rồi-ghi trong ultrasound_service thành một lỗi ràng buộc mà service '
    'xử lý bằng ON CONFLICT, thay vì thành hai phiếu im lặng.';

-- ---------------------------------------------------------------------------
-- 2. order_services: khoá theo lượt khám trong lúc chỉ định
-- ---------------------------------------------------------------------------
-- Không dùng index duy nhất trên work_item(visit_id, node_code): một lượt khám
-- CÓ THỂ hợp lệ khi lặp lại cùng một bước (siêu âm hai lần trong một buổi), nên
-- ràng buộc đó sẽ chặn cả việc đúng. Thứ cần chặn hẹp hơn: hai lần chỉ định
-- CHẠY CHỒNG NHAU.
--
-- pg_advisory_xact_lock trên visit_id làm đúng việc đó và tự nhả khi transaction
-- kết thúc — cùng cơ chế check_in_appointment đã dùng để hai lễ tân không phát
-- trùng số thứ tự.

CREATE OR REPLACE FUNCTION public.order_services_lock_visit(p_visit_id uuid)
RETURNS void
LANGUAGE sql
AS $$
    -- hashtextextended cho 64-bit: hashtext (32-bit) đủ va chạm để hai lượt
    -- khám khác nhau thỉnh thoảng chờ nhau vô cớ.
    SELECT pg_advisory_xact_lock(hashtextextended(p_visit_id::text, 0));
$$;

COMMENT ON FUNCTION public.order_services_lock_visit(uuid) IS
    'Khoá theo lượt khám, tự nhả cuối transaction. Dùng ở đầu order_services() '
    'để hai lần chỉ định chồng nhau không cùng đọc "chưa có" rồi cùng ghi.';

REVOKE ALL ON FUNCTION public.order_services_lock_visit(uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.order_services_lock_visit(uuid) TO service_role;
