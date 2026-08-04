-- GIỮ CHỖ 10 PHÚT — và nó giữ lúc ĐANG CHỌN, không phải sau khi đã đặt.
--
-- Quyết định của Quang (2026-08-04): *"cái đếm 10' chỉ sinh event khi mà CSKH
-- đang chọn khung giờ khám để CSKH khác được hiện là khung này đang được giữ để
-- đặt để tránh đặt trùng, chứ không phải đã ấn đặt lịch rồi lại còn giữ 10'
-- làm gì"*.
--
-- CÁI SAI ĐANG CHẠY. Màn đặt lịch hiện nhãn "Đang giữ" cho ô nào có lịch hẹn ở
-- trạng thái WAITING/CSKH_CONFIRMED — tức là nó gọi một LỊCH ĐÃ ĐẶT XONG là
-- "đang giữ". Hai thứ đó khác nhau: một cái là ghế đã bán, một cái là ghế đang
-- có người đứng cạnh. Gộp lại thì CSKH thứ hai không phân biệt được khung nào
-- thật sự còn chỗ.
--
-- GIỮ CHỖ LÀ TƯ VẤN, KHÔNG PHẢI KHOÁ. Chốt chặn thật vẫn là trigger sức chứa
-- lúc INSERT lịch hẹn — nó chạy trong cùng transaction và không ai lách được.
-- Bảng này chỉ để CSKH kia NHÌN THẤY có người đang thao tác, nên một dòng giữ
-- chỗ bị rò (trình duyệt đóng đột ngột) làm phiền chứ không chặn ai: nó tự hết
-- hạn sau 10 phút, và không dòng nào ở đây làm một lịch hẹn hợp lệ bị từ chối.

CREATE TABLE IF NOT EXISTS public.slot_hold (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    -- NULL = đang chọn ở chế độ "tất cả bác sĩ", chưa chốt bác sĩ nào.
    doctor_id      uuid REFERENCES public.staff(id),
    slot_start     timestamptz NOT NULL,
    slot_end       timestamptz NOT NULL,
    held_by        uuid NOT NULL REFERENCES public.staff(id),
    held_at        timestamptz NOT NULL DEFAULT now(),
    expires_at     timestamptz NOT NULL,
    released_at    timestamptz,
    -- Vì sao thả: 'booked' (đã đặt xong), 'cancelled' (bỏ chọn), 'expired'.
    release_reason text,
    -- Lịch hẹn mà chỗ giữ này biến thành, nếu có. Để đọc ngược được từ một
    -- lịch hẹn ra ai đã ngồi giữ chỗ trước đó và giữ bao lâu.
    appointment_id uuid,
    CONSTRAINT slot_hold_window CHECK (slot_end > slot_start),
    CONSTRAINT slot_hold_release_needs_reason
        CHECK (released_at IS NULL
               OR nullif(btrim(coalesce(release_reason, '')), '') IS NOT NULL)
);

COMMENT ON TABLE public.slot_hold IS
    'CSKH đang chọn khung giờ này — để CSKH khác thấy mà tránh đặt trùng. Tư '
    'vấn, không phải khoá: chốt chặn sức chứa thật vẫn là trigger lúc đặt lịch.';

-- MỘT NGƯỜI GIỮ MỘT CHỖ TRONG MỘT KHUNG. Không chặn hai CSKH cùng giữ một
-- khung — khung có 3 ghế thì hai người giữ hai ghế là đúng, và chặn lại sẽ
-- biến bảng tư vấn này thành cái khoá mà nó cố tình không phải.
CREATE UNIQUE INDEX IF NOT EXISTS uq_slot_hold_active
    ON public.slot_hold (clinic_id, held_by, slot_start,
                         coalesce(doctor_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE released_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_slot_hold_live
    ON public.slot_hold (clinic_id, slot_start)
    WHERE released_at IS NULL;

-- ---------------------------------------------------------------------------
-- Chỗ đang được giữ, đọc bằng một truy vấn
-- ---------------------------------------------------------------------------
-- HẾT HẠN LÀ THỤ ĐỘNG. `expires_at < now()` là hết giữ — không cần cron, không
-- cần ai dọn. Một hàng đợi dọn rác chạy trễ nghĩa là chỗ vẫn hiện "đang giữ"
-- sau khi đã hết hạn, và đó đúng là thứ bảng này sinh ra để tránh.

CREATE OR REPLACE VIEW public.v_slot_hold_active
WITH (security_invoker = true) AS
SELECT h.id,
       h.clinic_id,
       h.doctor_id,
       h.slot_start,
       h.slot_end,
       h.held_by,
       s.full_name AS held_by_name,
       h.held_at,
       h.expires_at
  FROM public.slot_hold h
  LEFT JOIN public.staff s ON s.id = h.held_by
 WHERE h.released_at IS NULL
   AND h.expires_at > now();

COMMENT ON VIEW public.v_slot_hold_active IS
    'Chỗ đang thực sự được giữ. Hết hạn là thụ động (expires_at < now()) nên '
    'không cần cron dọn — dọn trễ đồng nghĩa hiện sai.';

GRANT SELECT ON public.v_slot_hold_active TO authenticated;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE public.slot_hold ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS slot_hold_select ON public.slot_hold;
CREATE POLICY slot_hold_select ON public.slot_hold
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- Ai đặt lịch được thì giữ chỗ được. Giữ chỗ là bước đầu của việc đặt lịch,
-- nên hai quyền này không thể lệch nhau — đây đúng là INTAKE_ROLES bên
-- booking_service.py, chép sang chứ không nghĩ lại một danh sách thứ hai.
DROP POLICY IF EXISTS slot_hold_write ON public.slot_hold;
CREATE POLICY slot_hold_write ON public.slot_hold
    FOR ALL TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['CSKH', 'RECEPTION', 'MANAGEMENT', 'TRUONG_CA'])))
    WITH CHECK (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['CSKH', 'RECEPTION', 'MANAGEMENT', 'TRUONG_CA'])));

GRANT SELECT, INSERT, UPDATE ON public.slot_hold TO authenticated;

DO $verify$
BEGIN
    PERFORM 1 FROM public.v_slot_hold_active LIMIT 1;
    RAISE NOTICE 'giữ chỗ: schema sẵn sàng';
END
$verify$;
