-- ĐỐI TÁC NHẬN VIỆC BẰNG SỰ KIỆN (Tuyền 24/09/2026: "bác sĩ chỉ định sinh event
-- đối tác nhận chưa").
--
-- Bảng CỦA khối Đối tác (modules.py `doi_tac.bang`): mỗi chỉ định làm bên ngoài
-- đã sang bàn đối tác là một dòng. Ghi bởi bên nhận `doi_tac_nhan_viec` khi nghe
-- `payment.service_collected` (đối tác tự lấy mẫu, khách đã trả) hoặc
-- `service.completed` (điều dưỡng lấy mẫu xong). Bàn đối tác đọc bảng này — thay
-- cho câu truy vấn cũ hiện việc tự-lấy-mẫu ngay lúc bác sĩ chỉ định (trước khi
-- khách chọn làm và trả tiền).
--
-- BÙ DỮ LIỆU: việc đang nằm trên bàn đối tác theo luật cũ được ghi nhận luôn, để
-- đối tác không mất việc đang dở khi đổi luật.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.doi_tac_nhan_viec (
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    service_order_id uuid NOT NULL REFERENCES public.service_order(id) ON DELETE CASCADE,
    ly_do            text NOT NULL
                     CHECK (ly_do IN ('DA_THU_TIEN', 'DA_LAY_MAU', 'BU_DU_LIEU')),
    nhan_luc         timestamptz NOT NULL DEFAULT now(),
    nguon_event_id   uuid,
    PRIMARY KEY (clinic_id, service_order_id)
);

COMMENT ON TABLE public.doi_tac_nhan_viec IS
'Chỉ định làm bên ngoài đã sang bàn đối tác (khối Đối tác, nhận qua sự kiện).';

ALTER TABLE public.doi_tac_nhan_viec ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS doi_tac_nhan_viec_select_own_clinic ON public.doi_tac_nhan_viec;
CREATE POLICY doi_tac_nhan_viec_select_own_clinic ON public.doi_tac_nhan_viec
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.doi_tac_nhan_viec TO service_role;

INSERT INTO public.doi_tac_nhan_viec (clinic_id, service_order_id, ly_do, nhan_luc)
SELECT o.clinic_id, o.id, 'BU_DU_LIEU', coalesce(o.finished_at, o.created_at)
  FROM public.service_order o
  JOIN public.node_definition n
    ON n.clinic_id = o.clinic_id AND n.code = o.node_code AND n.lam_ben_ngoai
  LEFT JOIN LATERAL (
       SELECT s.doi_tac_lay_mau FROM public.service_price s
        WHERE s.clinic_id = o.clinic_id AND s.service_code = o.service_code
          AND s.active
        ORDER BY (s."group" = 'dich_vu') DESC LIMIT 1) sp ON true
 WHERE o.created_at > now() - interval '60 days'
   AND (o.exec_status = 'performed'
        OR (coalesce(sp.doi_tac_lay_mau, false)
            AND o.exec_status IN ('authorized', 'assigned', 'in_progress')))
ON CONFLICT (clinic_id, service_order_id) DO NOTHING;
