-- Nhật ký thao tác: giải TÊN lúc đọc, không chép tên vào nhật ký.
--
-- Màn "Lịch sử thao tác" mở đầu bằng đúng câu "tra cứu ai đã thực hiện thay
-- đổi", rồi ba cột chính đều không nói được điều đó:
--
--     Người thực hiện   "api:booking"              đáng lẽ: Diệu Hoa (CSKH)
--     Đối tượng         "slot_hold · 2ae31328"     đáng lẽ: tên bệnh nhân
--     Hành động         "slot_hold.created"        đáng lẽ: "Giữ chỗ"
--
-- Ba cột, ba nguyên nhân khác nhau. View này lo hai cột đầu; cột thứ ba là
-- bảng nhãn ở backend (services/audit_labels.py).
--
-- DANH TÍNH ĐÃ ĐƯỢC GHI ĐÚNG TỪ ĐẦU. `record_event` (services/audit.py) nhét
-- `clinic_staff_id` vào `metadata`, và 199/205 dòng trên prod có nó. Màn hình
-- lại đi đọc `payload.staff_name` — một khoá KHÔNG đường ghi nào đặt vào, 0/205
-- dòng — rồi rơi xuống nhánh dự phòng `?? source`, in ra tên đường ghi. Vì
-- `source` là NOT NULL nên nhánh "Hệ thống" phía sau là code chết: 100% dòng
-- hiện tên route. Đây là lỗi TẦNG ĐỌC, không phải tầng ghi.
--
-- VÌ SAO KHÔNG "SỬA CHO NHANH" BẰNG CÁCH NHÉT TÊN VÀO PAYLOAD. Ba lý do, và
-- lý do thứ hai là thứ không lùi được:
--
--   1. Trái đúng nguyên tắc `audit.py` tự đặt ra: định danh, không phải nội
--      dung. Bảng này mở cho vai vận hành đọc.
--   2. `event_log` CHỈ GHI THÊM — ba trigger no_update/no_delete/no_truncate
--      đang bật. Tên chép vào đó ĐÓNG BĂNG VĨNH VIỄN: nhân viên đổi tên, hoặc
--      bệnh nhân yêu cầu xoá dữ liệu, đều không sửa được một dòng nào.
--   3. `lib/event-log-redaction.ts` đã liệt `patientname` vào danh sách nhạy
--      cảm — hệ thống đã tự quyết là tên không nằm trong log.
--
-- Nên tên phải giải lúc ĐỌC, bằng JOIN. Đây cũng là cách `v_dispatch_history`
-- (20260804000003) đang làm và chạy tốt ở màn Trưởng ca.
--
-- CÁI KHÔNG CỨU ĐƯỢC, nói thẳng: 20/24 dòng `slot_hold` cũ mất bệnh nhân vĩnh
-- viễn — không phải payload thiếu khoá, mà dữ liệu CHƯA TỪNG TỒN TẠI: hàm
-- `hold()` không nhận bệnh nhân và bảng `slot_hold` không có cột nào trỏ tới
-- bệnh nhân. Sửa tầng ghi chỉ cứu được dòng MỚI.

CREATE OR REPLACE VIEW public.v_audit_log
WITH (security_invoker = true) AS
SELECT
    e.event_id,
    e.clinic_id,
    e.occurred_at,
    e.event_type,
    e.aggregate_type,
    e.aggregate_id,
    e.payload,

    -- ── Ai đã làm ──────────────────────────────────────────────────────────
    --
    -- HAI NHÁNH NỐI TIẾP, và thứ tự có lý do. `clinic_staff_id` là khoá chính,
    -- phủ 199/205 dòng. Nhánh phụ qua `auth_user_id` chỉ phủ 9/57 nhân sự (số
    -- người đã liên kết tài khoản đăng nhập) — vừa đủ cứu hai dòng dispatch cũ
    -- ghi thiếu khoá, nhưng KHÔNG được dùng làm đường chính.
    coalesce(s1.id, s2.id)                          AS actor_staff_id,
    coalesce(s1.full_name, s2.full_name)            AS actor_name,
    -- `actor_role` là tên khoá lệch mà `clinical_sign_service` từng dùng. Giữ
    -- nhánh này để dòng cũ đọc được; đường ghi đã sửa về tên chuẩn.
    coalesce(e.metadata ->> 'clinic_role',
             e.metadata ->> 'actor_role')           AS actor_role,
    -- NULL nghĩa là HỆ THỐNG, không phải "không rõ ai": migration, seed, worker
    -- và các kênh ngoài sinh event không có người đứng sau. Bốn dòng như vậy
    -- trên prod, và hiện "Hệ thống" cho chúng là ĐÚNG chứ không phải lỗi.

    -- Nguồn thao tác là thông tin có ích — nó chỉ không được đứng THAY tên
    -- người. Trả về như một cột riêng.
    e.source                                        AS nguon_thao_tac,

    -- ── Việc này về ai ─────────────────────────────────────────────────────
    --
    -- Bốn đường tra, xếp theo độ phủ giảm dần. Không đường nào đọc nội dung
    -- lâm sàng — chỉ lần ra ĐỊNH DANH bệnh nhân rồi lấy tên.
    coalesce(
        nullif(e.payload ->> 'clinic_patient_id', '')::uuid,  -- 96/97 lịch hẹn
        CASE WHEN e.aggregate_type = 'patient'                -- 51/51 bệnh nhân
             THEN e.aggregate_id END,
        v.clinic_patient_id,                                  -- qua lượt khám
        a.clinic_patient_id                                   -- qua giữ chỗ
    )                                               AS subject_patient_id,
    p.full_name                                     AS subject_name,
    p.patient_code                                  AS subject_code,

    -- Nhóm sự kiện KHÔNG có bệnh nhân theo đúng bản chất — luật đặt lịch, cấu
    -- hình phòng khám, nhân sự. Để trống ở cột Đối tượng sẽ đọc thành "mất dữ
    -- liệu", nên nói rõ nó nói về cái gì.
    CASE e.aggregate_type
        WHEN 'booking_override' THEN 'luat_dat_lich'
        WHEN 'clinic'           THEN 'cau_hinh_phong_kham'
        WHEN 'staff'            THEN 'nhan_su'
        ELSE NULL
    END                                             AS subject_kind,
    sr.full_name                                    AS subject_ref_name

  FROM public.event_log e

  LEFT JOIN public.staff s1
         ON s1.id = nullif(e.metadata ->> 'clinic_staff_id', '')::uuid
  -- `auth_user_id` có chỉ mục duy nhất (một phần), nên nhánh này không nhân
  -- đôi dòng. Nếu chỉ mục ấy mất đi thì view sẽ nhân bản lịch sử — có bài kiểm
  -- đếm số dòng ở cuối file để bắt đúng chuyện đó.
  LEFT JOIN public.staff s2
         ON s2.auth_user_id = nullif(e.metadata ->> 'actor_auth_user_id', '')::uuid

  LEFT JOIN public.visit v
         ON v.visit_id = e.aggregate_id AND v.clinic_id = e.clinic_id
  LEFT JOIN public.slot_hold h
         ON h.id = e.aggregate_id AND h.clinic_id = e.clinic_id
  LEFT JOIN public.appointment a
         ON a.id = h.appointment_id AND a.clinic_id = e.clinic_id

  LEFT JOIN public.patient p
         ON p.clinic_id = e.clinic_id
        AND p.clinic_patient_id = coalesce(
              nullif(e.payload ->> 'clinic_patient_id', '')::uuid,
              CASE WHEN e.aggregate_type = 'patient' THEN e.aggregate_id END,
              v.clinic_patient_id,
              a.clinic_patient_id)

  -- Bác sĩ mà một LUẬT ĐẶT LỊCH nói về — để màn hình viết được "Luật của BS.
  -- Thành" thay vì một ô trống.
  LEFT JOIN public.staff sr
         ON sr.id = nullif(e.payload ->> 'doctor_id', '')::uuid;

COMMENT ON VIEW public.v_audit_log IS
    'Nhật ký thao tác đã giải tên: ai làm (từ metadata.clinic_staff_id), việc '
    'về ai (bốn đường tra ra bệnh nhân). Tên giải lúc ĐỌC — event_log chỉ ghi '
    'thêm, nên tên chép vào đó sẽ không bao giờ sửa được.';

GRANT SELECT ON public.v_audit_log TO authenticated;

DO $verify$
DECLARE
    v_goc   bigint;
    v_view  bigint;
    v_ten   bigint;
    v_bn    bigint;
BEGIN
    SELECT count(*) INTO v_goc  FROM public.event_log;
    SELECT count(*) INTO v_view FROM public.v_audit_log;

    -- MỘT DÒNG NHẬT KÝ VÀO, MỘT DÒNG RA. Bốn LEFT JOIN ở trên đều đi qua khoá
    -- duy nhất, nhưng "đều nên là duy nhất" và "đang là duy nhất" là hai điều
    -- khác nhau — và một view nhân đôi lịch sử thì đọc thành hai lần thao tác.
    IF v_view <> v_goc THEN
        RAISE EXCEPTION
            'v_audit_log nhân dòng: event_log có %, view trả % — có JOIN nào '
            'không duy nhất', v_goc, v_view;
    END IF;

    SELECT count(*) FILTER (WHERE actor_name IS NOT NULL),
           count(*) FILTER (WHERE subject_name IS NOT NULL)
      INTO v_ten, v_bn
      FROM public.v_audit_log;

    RAISE NOTICE
        'v_audit_log: %/% dòng ra được TÊN NGƯỜI, %/% dòng ra được TÊN BỆNH '
        'NHÂN (phần còn lại là sự kiện hệ thống hoặc dữ liệu chưa từng có)',
        v_ten, v_goc, v_bn, v_goc;
END
$verify$;
