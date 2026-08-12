-- Hai chỗ ClinicAI nói khác với cách phòng khám thật sự làm việc.
--
-- Nghiệm thu 12/08/2026, chạy quy trình CSKH thật trên staging theo bảng RACI
-- trong biên bản họp 8/5 và đối chiếu với bảng đặt lịch Excel của Dr4Women.
--
-- ════════════════════════════════════════════════════════════════════════════
-- (1) TỆP KẾT QUẢ CSKH TẢI LÊN KHÔNG SINH VIỆC NHẮC GỬI
-- ════════════════════════════════════════════════════════════════════════════
--
-- Luật "Có kết quả, chưa gửi" (`luat_cskh.KQ_CHUA_GUI`) có thật và chạy đúng —
-- nhưng nó đọc bảng `lab_result`, còn CSKH tải phiếu kết quả lên `tep_ket_qua`.
-- Hai bảng khác nhau, và `v_viec_cskh` không hề nhắc tới `tep_ket_qua` (đo được:
-- 0 lần xuất hiện trong định nghĩa view).
--
-- Tệ hơn: CSKH KHÔNG tạo được `lab_result` — các endpoint ghi vào bảng ấy gác
-- cho vai lâm sàng (PHYSICIAN_ROLES / CLINICAL_WRITE_ROLES). Nên với mọi kết
-- quả CSKH xử lý bằng cách tải tệp, KHÔNG có đường nào sinh ra lời nhắc.
--
-- Đo thật: tải một tệp lên → 201 → không việc nào xuất hiện → tệp nằm im với
-- `gui_luc IS NULL`. Khách có thể không bao giờ nhận được kết quả, và phòng
-- khám không có cách nào biết.
--
-- Đây là hình dạng lỗi lặp lại của dự án: LUẬT ĐÚNG, NỐI VÀO SAI NGUỒN.
--
-- ════════════════════════════════════════════════════════════════════════════
-- (2) SỐ KHÁM ĐÁNH THEO CẢ PHÒNG KHÁM, TRONG KHI PHÒNG KHÁM KHÁM THEO BÁC SĨ
-- ════════════════════════════════════════════════════════════════════════════
--
-- Bảng Excel Dr4Women đang dùng có mỗi bác sĩ một cột, và số khám chạy riêng
-- trong từng cột: BS Thành 1→18, BS Thiệp 1→13 cùng một buổi tối.
--
-- Hệ thống đánh một dãy duy nhất cho cả phòng khám mỗi ngày. Đo trên staging
-- ngày 11/08:
--     BSNT. Hoàng Đình      → 1
--     TS.BS. Phan Chí Thành → 2, 3
-- Bệnh nhân ĐẦU TIÊN của BS Thành tối đó được gọi là "số 2", còn trên phơi của
-- bác sĩ họ đứng thứ 1.
--
-- Nặng hơn vì màn hình TV GỌI TÊN, KHÔNG GỌI SỐ (Quang chốt 06/08) — chú thích
-- trong DisplayBoard ghi rõ số "vẫn hiện, nhưng nhỏ và ở dưới, ĐỂ ĐỐI CHIẾU".
-- Số khám tồn tại chỉ để đối chiếu với phơi giấy, và nó đang đối chiếu sai.
--
-- Không có ràng buộc hay index nào trên `queue_number` (đã kiểm), nên số trùng
-- giữa hai bác sĩ không phá vỡ gì. Số đã cấp cũng không bị đụng: hàm chỉ tính
-- max trong phạm vi mới, nên lần cấp tiếp theo của mỗi bác sĩ vẫn liền mạch.
--
-- ────────────────────────────────────────────────────────────────────────────
-- Ghi chú cho người đọc sau: phần thân view bên dưới là định nghĩa ĐANG CHẠY
-- (dạng chuẩn hoá do Postgres sinh ra, đã gồm mọi thay đổi của 20260810000009
-- và 20260811000001) CỘNG đúng MỘT nhánh mới. Lấy bản đang chạy thay vì dựng
-- lại từ 20260810000008 là để không đánh rơi thay đổi của hai migration sau.

BEGIN;

-- ── (1) Việc nhắc gửi kết quả, đọc thêm nguồn `tep_ket_qua` ────────────────
CREATE OR REPLACE VIEW public.v_viec_cskh AS
 WITH hom_nay AS (
         SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date AS d
        ), cham_cuoi AS (
         SELECT DISTINCT ON (t.appointment_id) t.appointment_id,
            t.ket_qua,
            t.xay_ra_luc
           FROM tuong_tac_cskh t
          WHERE t.appointment_id IS NOT NULL AND t.huy_luc IS NULL
          ORDER BY t.appointment_id, t.xay_ra_luc DESC
        ), viec AS (
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'DA_CHECKIN'::text AS loai,
            0 AS uu_tien,
            h_1.d AS han,
            a.id AS appointment_id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'DA_CHECKIN'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE a.status = 'CHECKED_IN'::text
        UNION ALL
         SELECT r.clinic_id,
            r.clinic_patient_id,
            'CHO_BAC_SI'::text AS loai,
            1 AS uu_tien,
            (r.result_received_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay AS han,
            NULL::uuid AS appointment_id
           FROM lab_result r
             JOIN luat_cskh l_1 ON l_1.clinic_id = r.clinic_id AND l_1.loai_viec = 'CHO_BAC_SI'::text AND l_1.bat
          WHERE r.result_value IS NOT NULL AND r.requires_doctor_review AND r.reviewed_at IS NULL
        UNION ALL
         SELECT r.clinic_id,
            r.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (COALESCE(r.reviewed_at, r.result_received_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay,
            NULL::uuid AS uuid
           FROM lab_result r
             JOIN luat_cskh l_1 ON l_1.clinic_id = r.clinic_id AND l_1.loai_viec = 'KQ_CHUA_GUI'::text AND l_1.bat
          WHERE r.result_value IS NOT NULL AND (NOT r.requires_doctor_review OR r.reviewed_at IS NOT NULL) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.clinic_patient_id = r.clinic_patient_id AND t.loai = 'TRA_KQ'::text AND t.xay_ra_luc >= COALESCE(r.reviewed_at, r.result_received_at, r.created_at) AND t.huy_luc IS NULL))
        UNION ALL
         SELECT r.clinic_id,
            r.clinic_patient_id,
            'CHO_KQ_XN'::text AS text,
            3,
            (COALESCE(r.sample_collected_at, r.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay,
            NULL::uuid AS uuid
           FROM lab_result r
             JOIN luat_cskh l_1 ON l_1.clinic_id = r.clinic_id AND l_1.loai_viec = 'CHO_KQ_XN'::text AND l_1.bat
          WHERE r.result_value IS NULL
        UNION ALL
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'GOI_LAI'::text AS text,
            4,
            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date AS timezone,
            a.id
           FROM appointment a
             JOIN cham_cuoi c ON c.appointment_id = a.id
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'GOI_LAI'::text AND l_1.bat
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (c.ket_qua = ANY (ARRAY['CHUA_NGHE_MAY'::text, 'KHONG_LIEN_LAC_DUOC'::text, 'HEN_GOI_LAI'::text]))
        UNION ALL
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'HOI_LY_DO_HUY'::text AS text,
            5,
            (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay,
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'HOI_LY_DO_HUY'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE a.status = 'CANCELLED'::text AND a.cancelled_at IS NOT NULL AND (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date >= (h_1.d - COALESCE(l_1.cua_so_ngay, 14)) AND (a.cancelled_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date <= (h_1.d - l_1.so_ngay) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'HOI_LY_DO_HUY'::text AND t.huy_luc IS NULL))
        UNION ALL
         SELECT g.clinic_id,
            g.clinic_patient_id,
            'HEN_GOI_LAI'::text AS text,
            6,
            g.ngay_goi,
            NULL::uuid AS uuid
           FROM hen_goi_lai g
             JOIN luat_cskh l_1 ON l_1.clinic_id = g.clinic_id AND l_1.loai_viec = 'HEN_GOI_LAI'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE g.dong_luc IS NULL AND g.ngay_goi <= h_1.d
        UNION ALL
         SELECT n.clinic_id,
            n.clinic_patient_id,
                CASE n.luot_goi
                    WHEN 1 THEN 'MOI_TAI_KHAM'::text
                    ELSE 'NHAC_DI_KHAM'::text
                END AS "case",
                CASE n.luot_goi
                    WHEN 1 THEN 9
                    ELSE 7
                END AS "case",
            n.han_goi,
            n.appointment_id
           FROM nhac_tai_kham n
             JOIN luat_cskh l_1 ON l_1.clinic_id = n.clinic_id AND l_1.bat AND l_1.loai_viec =
                CASE n.luot_goi
                    WHEN 1 THEN 'MOI_TAI_KHAM'::text
                    ELSE 'NHAC_DI_KHAM'::text
                END
          WHERE n.trang_thai = 'CHO_GOI'::text AND (n.appointment_id IS NULL OR (EXISTS ( SELECT 1
                   FROM appointment a
                  WHERE a.id = n.appointment_id AND (a.status <> ALL (ARRAY['CHECKED_IN'::text, 'COMPLETED'::text, 'NO_SHOW'::text, 'CANCELLED'::text, 'DOCTOR_DECLINED'::text])))))
        UNION ALL
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'NHAC_HEN_MAI'::text AS text,
            8,
            h_1.d,
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'NHAC_HEN_MAI'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date = (h_1.d + l_1.so_ngay) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'NHAC_HEN'::text AND t.huy_luc IS NULL))
        UNION ALL
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'CHO_XAC_NHAN'::text AS text,
            10,
            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date AS timezone,
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'CHO_XAC_NHAN'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date >= h_1.d AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date <= (h_1.d + l_1.so_ngay) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH'::text AND t.huy_luc IS NULL))

        UNION ALL

        -- TỆP KẾT QUẢ CSKH TẢI LÊN MÀ CHƯA GỬI KHÁCH.
        --
        -- Nhánh `lab_result` phía trên đã có từ trước và chạy đúng — nhưng nó
        -- đọc BẢNG KHÁC với bảng CSKH thật sự dùng. CSKH tải phiếu kết quả lên
        -- `tep_ket_qua`; `lab_result` là kết quả xét nghiệm có cấu trúc, và các
        -- endpoint ghi vào đó gác cho vai lâm sàng — CSKH không tạo được.
        --
        -- Đo ngày 12/08/2026: tải một tệp lên, chưa gửi, và KHÔNG việc nào sinh
        -- ra. Tệp nằm im với `gui_luc IS NULL`, không gì nhắc ai cả. Nghĩa là
        -- khách có thể không bao giờ nhận được kết quả, và phòng khám không biết.
        --
        -- Điều kiện đóng việc là `gui_luc IS NOT NULL` — CSKH có nút "đã gửi"
        -- riêng cho tệp. KHÔNG dùng thêm `NOT EXISTS (TRA_KQ)` như nhánh
        -- lab_result: tệp có mốc gửi tường minh của chính nó, thêm một đường
        -- đóng thứ hai chỉ làm mờ câu hỏi "tệp này đã gửi chưa".
        SELECT k.clinic_id,
            k.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_kq.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_kq ON l_kq.clinic_id = k.clinic_id AND l_kq.loai_viec = 'KQ_CHUA_GUI'::text AND l_kq.bat
          WHERE k.gui_luc IS NULL
        )
 SELECT v.clinic_id,
    v.clinic_patient_id,
    v.loai AS trang_thai,
    l.nhan,
    v.uu_tien,
    v.han AS han_xu_ly,
    v.han < h.d AS qua_han,
    v.appointment_id
   FROM viec v
     CROSS JOIN hom_nay h
     JOIN luat_cskh l ON l.clinic_id = v.clinic_id AND l.loai_viec = v.loai;

-- ── (2) Số khám chạy riêng theo từng bác sĩ ────────────────────────────────
--
-- PHẢI SỬA HAI HÀM, KHÔNG PHẢI MỘT.
--
-- Cùng một luật đánh số được viết ở hai nơi: trigger `assign_appointment_queue_
-- number` và hàm `check_in_appointment`. Chỉ sửa trigger là KHÔNG ĐỦ, và đây
-- không phải suy đoán — đã đo: sửa xong trigger, check-in qua giao diện, BS Nam
-- vẫn nhận số 3 và 4 thay vì 1 và 2.
--
-- Vì check-in thật đi qua `check_in_appointment`: hàm này TỰ tính số rồi mới
-- UPDATE, nên khi trigger chạy thì `queue_number` đã có giá trị và trigger thoát
-- ngay ở dòng đầu. Trigger chỉ còn đỡ những đường ghi thẳng vào bảng.
--
-- Đây đúng hình dạng lỗi mà dự án gặp đi gặp lại: LUẬT ĐÚNG, KHÔNG NỐI VÀO
-- ĐƯỜNG THẬT. Lần này nó xuất hiện ngay bên trong chính bản sửa.

CREATE OR REPLACE FUNCTION public.check_in_appointment(
    p_appointment_id uuid, p_from_statuses text[]
)
 RETURNS TABLE(id uuid, queue_number text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    target      public.appointment%ROWTYPE;
    clinic_day  date;
    doctor_key  text;
    next_number integer;
BEGIN
    SELECT a.*
      INTO target
      FROM public.appointment AS a
     WHERE a.id = p_appointment_id
     FOR UPDATE;

    IF NOT FOUND OR NOT (target.status = ANY (p_from_statuses)) THEN
        RETURN;
    END IF;

    clinic_day := (target.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    doctor_key := coalesce(target.doctor_id::text, '~none~');

    -- Khoá theo ĐÚNG phạm vi đánh số (phòng khám, ngày, bác sĩ). Khoá rộng hơn
    -- phạm vi thì hai bác sĩ check-in cùng lúc phải chờ nhau mà chẳng vì gì.
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            'clinicai:queue:' || target.clinic_id::text || ':' || clinic_day::text
            || ':' || doctor_key, 0
        )
    );

    IF nullif(pg_catalog.btrim(target.queue_number), '') IS NULL THEN
        SELECT coalesce(max(a.queue_number::integer), 0) + 1
          INTO next_number
          FROM public.appointment AS a
         WHERE a.clinic_id = target.clinic_id
           AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = clinic_day
           AND coalesce(a.doctor_id::text, '~none~') = doctor_key
           AND a.queue_number ~ '^[0-9]+$';

        target.queue_number := next_number::text;
    END IF;

    UPDATE public.appointment AS a
       SET status = 'CHECKED_IN',
           queue_number = target.queue_number,
           updated_at = pg_catalog.now()
     WHERE a.id = target.id
     RETURNING a.id, a.queue_number
      INTO id, queue_number;

    RETURN NEXT;
END
$function$;

CREATE OR REPLACE FUNCTION public.assign_appointment_queue_number()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    clinic_day  date;
    doctor_key  text;
    next_number integer;
BEGIN
    IF NEW.status <> 'CHECKED_IN'
       OR nullif(pg_catalog.btrim(NEW.queue_number), '') IS NOT NULL THEN
        RETURN NEW;
    END IF;

    clinic_day := (NEW.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;

    -- Lịch CHƯA XẾP BÁC SĨ có dãy số riêng của nó, không trộn vào dãy của bất
    -- kỳ bác sĩ nào. Dùng '~none~' cho khớp cách `slot_seats_used` và
    -- `enforce_slot_capacity` đã so bác sĩ — một quy ước, ba chỗ dùng.
    doctor_key := coalesce(NEW.doctor_id::text, '~none~');

    -- Khoá theo ĐÚNG phạm vi đánh số. Khoá rộng hơn phạm vi thì hai bác sĩ
    -- check-in cùng lúc phải xếp hàng chờ nhau mà chẳng vì lý do gì.
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            'clinicai:queue:' || NEW.clinic_id::text || ':' || clinic_day::text
            || ':' || doctor_key, 0
        )
    );

    SELECT coalesce(max(a.queue_number::integer), 0) + 1
      INTO next_number
      FROM public.appointment AS a
     WHERE a.clinic_id = NEW.clinic_id
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = clinic_day
       AND coalesce(a.doctor_id::text, '~none~') = doctor_key
       AND a.queue_number ~ '^[0-9]+$'
       AND a.id IS DISTINCT FROM NEW.id;

    NEW.queue_number := next_number::text;
    RETURN NEW;
END
$function$;

COMMIT;
