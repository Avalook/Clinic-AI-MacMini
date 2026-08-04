-- Cái net không được mắc vào lưới.
--
-- booking_service.py mở đầu bằng: "Two invariants are enforced by Postgres, not
-- here: appointment_no_doctor_overlap and the atomic slot-capacity trigger. The
-- checks in this module run *before* the write purely to produce a sentence a
-- receptionist can act on … They are best-effort and fail open, because the
-- database is the actual net."
--
-- Trên prod, ngày 2026-08-03, trigger trên bảng appointment là:
--
--     appointment_assign_queue_number
--     trg_appointment_no_delete
--     trg_appointment_no_truncate
--
-- KHÔNG có trg_enforce_slot_capacity. Hàm enforce_slot_capacity() thì có — nó
-- được CREATE OR REPLACE lại ở 20260731000002 và 20260803000002 — nhưng TRIGGER
-- gọi nó chỉ được tạo đúng một lần, ở 20260714000002, và nó không còn gắn.
--
-- Hệ quả: tầng kiểm tra trong Python cố ý "fail open" vì tin rằng database sẽ
-- chặn, còn database thì không chặn gì. Số chỗ mỗi khung suốt thời gian qua là
-- một con số để TÔ MÀU ô lịch, không phải một giới hạn.
--
-- VÌ SAO KHÔNG AI THẤY: mọi phép kiểm — kể cả script check-schema-drift.sh tôi
-- viết hôm nay — hỏi "hàm enforce_slot_capacity có tồn tại không". Có. Câu hỏi
-- đúng là "trigger có gắn không", và hai câu đó khác nhau kể từ lần đầu ai đó
-- DROP trigger mà giữ lại hàm.

-- ---------------------------------------------------------------------------
-- 1. Sửa lỗi làm hàm đổ khi lịch CHƯA PHÂN BÁC SĨ
-- ---------------------------------------------------------------------------
-- Gắn trigger vào mà không sửa chỗ này thì mọi lịch không có bác sĩ sẽ đổ ngay:
--
--     ERROR: record "v_doc" is not assigned yet
--
-- `v_doc` là một RECORD, và SELECT INTO nó nằm trong `IF p_doctor_id IS NOT
-- NULL`. Khi doctor_id NULL, nhánh đó không chạy, record không bao giờ được
-- gán, và plpgsql từ chối đọc trường của một record chưa gán — khác hẳn một
-- record đã gán mà không có dòng nào (trường hợp đó cho NULL, hoàn toàn hợp lệ).
--
-- Lịch chưa phân bác sĩ là luồng CÓ THẬT: lib/slot-capacity.ts ghi rõ "Hàng
-- 'Chưa phân bác sĩ' (doctor_id null) cũng bị giới hạn y hệt như một hàng
-- riêng". Nó chưa từng lộ ra chỉ vì trigger không chạy.
--
-- Dùng biến vô hướng thay cho record: biến vô hướng mặc định là NULL, nên không
-- có trạng thái "chưa gán" nào để vấp.

CREATE OR REPLACE FUNCTION public.resolve_effective_cap(
    p_clinic_id uuid,
    p_doctor_id uuid,
    p_slot_start timestamptz
)
RETURNS TABLE (slot_minutes integer, regular_cap integer, walkin_cap integer)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_local        timestamp;
    v_date         date;
    v_minute       integer;
    v_weekday      smallint;
    v_slot_regular integer;
    v_slot_walkin  integer;
    v_doc_minutes  integer;
    v_doc_regular  integer;
    v_doc_walkin   integer;
    v_cl_minutes   integer;
    v_cl_regular   integer;
    v_cl_walkin    integer;
BEGIN
    v_local   := p_slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh';
    v_date    := v_local::date;
    v_minute  := EXTRACT(HOUR FROM v_local)::int * 60
               + EXTRACT(MINUTE FROM v_local)::int;
    v_weekday := EXTRACT(DOW FROM v_local)::smallint;

    -- Tầng 3 — ngoại lệ theo khung (mịn tới phút, 20260803000009).
    SELECT s.regular_cap, s.walkin_cap
      INTO v_slot_regular, v_slot_walkin
      FROM public.slot_booking_override s
     WHERE s.clinic_id = p_clinic_id
       AND (s.doctor_id = p_doctor_id OR s.doctor_id IS NULL)
       AND v_date BETWEEN s.date_start AND s.date_end
       AND v_minute >= s.minute_start AND v_minute < s.minute_end
     ORDER BY s.doctor_id IS NULL   -- luật riêng thắng luật chung
     LIMIT 1;

    -- Tầng 2 — mặc định của bác sĩ. Bỏ qua khi chưa phân bác sĩ; các biến ở
    -- đây vẫn là NULL và coalesce bên dưới xử lý đúng.
    IF p_doctor_id IS NOT NULL THEN
        SELECT d.slot_minutes, d.regular_cap, d.walkin_cap
          INTO v_doc_minutes, v_doc_regular, v_doc_walkin
          FROM public.doctor_booking_override d
         WHERE d.clinic_id = p_clinic_id
           AND d.doctor_id = p_doctor_id
           AND d.effective_from <= v_date
           AND (d.effective_to IS NULL OR d.effective_to >= v_date)
           AND (d.weekday IS NULL OR d.weekday = v_weekday)
         ORDER BY d.weekday IS NULL,
                  d.effective_from DESC
         LIMIT 1;
    END IF;

    -- Tầng 1 — luật phòng khám.
    SELECT p.slot_minutes, p.regular_cap, p.walkin_cap
      INTO v_cl_minutes, v_cl_regular, v_cl_walkin
      FROM public.clinic_booking_policy(p_clinic_id) p;

    RETURN QUERY SELECT
        coalesce(v_doc_minutes, v_cl_minutes),
        coalesce(v_slot_regular, v_doc_regular, v_cl_regular),
        coalesce(v_slot_walkin,  v_doc_walkin,  v_cl_walkin);
END;
$function$;

COMMENT ON FUNCTION public.resolve_effective_cap(uuid, uuid, timestamptz) IS
  'C.4: sức chứa hiệu lực, 3 tầng — slot_override (mịn tới phút) -> '
  'doctor_override -> clinic_booking_policy. Dùng biến vô hướng thay record để '
  'lịch CHƯA PHÂN BÁC SĨ không làm hàm đổ (xem 20260803000010).';

-- ---------------------------------------------------------------------------
-- 2. Mắc net vào lưới
-- ---------------------------------------------------------------------------
-- DROP trước: 20260714000002 chỉ có CREATE TRIGGER trần, nên nó không chạy lại
-- được và đó là lý do migration ấy bị loại khỏi đợt repair hôm nay. Ở đây thì
-- chạy lại được bao nhiêu lần cũng như một.
--
-- BEFORE INSERT OR UPDATE OF (slot_start, doctor_id, booking_channel, status):
-- đúng bốn cột đổi chỗ ngồi của một lịch hẹn trong lưới sức chứa. Đổi tên bệnh
-- nhân thì không cần đếm lại.

DROP TRIGGER IF EXISTS trg_enforce_slot_capacity ON public.appointment;
CREATE TRIGGER trg_enforce_slot_capacity
    BEFORE INSERT OR UPDATE OF slot_start, doctor_id, booking_channel, status
    ON public.appointment
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_slot_capacity();

COMMENT ON TRIGGER trg_enforce_slot_capacity ON public.appointment IS
  'CAP-01: giới hạn số chỗ mỗi (phòng khám, bác sĩ, khung, đặt-trước/vãng-lai). '
  'Đây là chỗ luật được THI HÀNH; pre-check trong booking_service.py chỉ để tạo '
  'một câu tiếng Việt và cố ý fail open.';

-- ---------------------------------------------------------------------------
-- 3. Kiểm ngay tại đây, không để lần sau phát hiện lại
-- ---------------------------------------------------------------------------
-- Migration tự chứng minh việc nó vừa làm. Nếu trigger vẫn không gắn được thì
-- dừng ở đây còn hơn báo thành công.

DO $verify$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
         WHERE tgrelid = 'public.appointment'::regclass
           AND NOT tgisinternal
           AND tgname = 'trg_enforce_slot_capacity'
    ) THEN
        RAISE EXCEPTION 'trg_enforce_slot_capacity vẫn chưa gắn — dừng lại.';
    END IF;

    -- Và hàm phải chạy được với doctor_id NULL, vì đó chính là lỗi vừa sửa.
    PERFORM public.resolve_effective_cap(
        (SELECT id FROM public.clinic LIMIT 1), NULL, now());

    RAISE NOTICE 'CAP-01: trigger đã gắn, resolver chạy được với lịch chưa phân bác sĩ';
END
$verify$;
