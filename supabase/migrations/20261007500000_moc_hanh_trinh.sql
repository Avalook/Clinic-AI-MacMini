-- NHẬN KHÁCH TẠI PHÒNG + MỐC HÀNH TRÌNH (Tuyền chốt 07/10/2026 —
-- docs/KE-HOACH-NHAN-TAI-PHONG.md).
--
-- 1. `service_order.routing_nguon` nhận thêm 'tai_phong': phòng tự bấm Nhận
--    (dây `nhan_tai_phong`). Không đổi dữ liệu cũ.
-- 2. View `v_moc_hanh_trinh`: MỖI MỐC MỘT DÒNG (lượt, chỉ định / phiên khám,
--    phòng, loại mốc, giờ, người, mốc ấy đã bị hoàn tác chưa, lý do nhả, hướng
--    dẫn ↔ thực tế) — đọc thẳng từ `domain_event` (chỉ thêm, không sửa), cho AI
--    phân tích thời gian chờ (Nhận→Bắt đầu), làm (Bắt đầu→Xong), đi lại (Nhả →
--    Nhận phòng sau). Cột giờ trên các bảng là giá trị HIỆN TẠI; lịch sử đủ ở đây.
--
-- "Bị hoàn tác" = có sự kiện nghịch đảo của cùng đối tượng SAU mốc ấy và TRƯỚC
-- lần lặp lại kế tiếp của chính loại mốc ấy (bấm Xong → hoàn tác → Xong lần hai:
-- chỉ lần một bị hoàn tác).
--
-- Không thêm index: `ix_domain_event_aggregate` (clinic, loại, đối tượng, giờ)
-- và `ix_domain_event_correlation` (clinic, lượt) đã phủ hai đường đọc của view.
--
-- Chạy lại được.

-- ── 1. Nguồn xếp phòng 'tai_phong' ──────────────────────────────────────────
ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_routing_nguon;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_routing_nguon CHECK (
        routing_nguon IS NULL
        OR routing_nguon IN ('quay_thu', 'truong_ca', 'tu_dong', 'khac', 'tai_phong'));

COMMENT ON COLUMN public.service_order.routing_nguon IS
'Nguồn của lần xếp phòng hiệu lực: quay_thu · truong_ca · tu_dong · khac · tai_phong (phòng tự bấm Nhận, 07/10/2026).';

-- ── 2. View mốc hành trình ──────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_moc_hanh_trinh
    WITH (security_invoker = true) AS
SELECT e.event_id,
       e.seq,
       e.clinic_id,
       coalesce(nullif(e.payload->>'visit_id', '')::uuid, e.correlation_id)
           AS visit_id,
       CASE WHEN e.aggregate_type = 'service_order' THEN e.aggregate_id END
           AS service_order_id,
       CASE WHEN e.aggregate_type = 'consultation' THEN e.aggregate_id END
           AS consultation_id,
       coalesce(nullif(e.payload->>'room_id', '')::uuid, a.room_id_snapshot)
           AS room_id,
       CASE e.event_type
           WHEN 'service.routed' THEN
               CASE WHEN e.payload->>'nguon' = 'tai_phong' THEN 'NHAN'
                    ELSE 'XEP_PHONG' END
           WHEN 'service.room_released' THEN 'NHA'
           WHEN 'service.room_receive_undone' THEN 'HOAN_TAC_NHAN'
           WHEN 'service.room_release_undone' THEN 'HOAN_TAC_NHA'
           WHEN 'service.room_guided' THEN 'HUONG_DAN'
           WHEN 'service.routing_invalidated' THEN 'HUY_XEP_PHONG'
           WHEN 'service.room_transferred' THEN 'CHUYEN_PHONG'
           WHEN 'service.started' THEN 'BAT_DAU'
           WHEN 'service.start_cancelled' THEN 'HUY_BAT_DAU'
           WHEN 'service.completed' THEN 'XONG'
           WHEN 'service.completion_undone' THEN 'HOAN_TAC_XONG'
           WHEN 'service.interrupted' THEN 'GIAN_DOAN'
           WHEN 'service.not_performed' THEN 'KHONG_LAM'
           WHEN 'service.patient_moved' THEN 'CHUYEN_KHACH'
           WHEN 'consultation.started' THEN 'KHAM_BAT_DAU'
           WHEN 'consultation.resumed' THEN 'KHAM_LAI'
           WHEN 'consultation.completed' THEN 'KHAM_XONG'
           WHEN 'consultation.reopened' THEN 'HOAN_TAC_KHAM_XONG'
       END AS loai_moc,
       e.occurred_at AS luc,
       e.actor_staff_id AS nguoi_id,
       s.full_name AS nguoi,
       e.actor_role AS vai,
       e.on_behalf_of AS lam_thay_cho,
       ht.event_id IS NOT NULL AS bi_hoan_tac,
       ht.occurred_at AS hoan_tac_luc,
       -- Xong là tự nhả (không có cú bấm Nhả riêng).
       CASE e.event_type
           WHEN 'service.room_released' THEN e.payload->>'ly_do'
           WHEN 'service.completed' THEN 'XONG'
       END AS ly_do_nha,
       e.payload->>'trang_thai_truoc' AS trang_thai_truoc,
       coalesce(e.payload->>'from_room_id', e.payload->>'nhan_cheo_tu_room_id',
                e.payload->>'tu_room_id')::uuid AS tu_phong_id,
       coalesce(e.payload->>'sang_room_id', e.payload->>'to_room_id')::uuid
           AS sang_phong_id,
       CASE WHEN e.event_type = 'service.room_guided'
            THEN nullif(e.payload->>'room_id', '')
            ELSE e.payload->>'huong_dan_room_id' END::uuid AS huong_dan_phong_id,
       (e.payload->>'dung_huong_dan')::boolean AS dung_huong_dan,
       (e.payload->>'thu_tu_huong_dan')::int AS thu_tu_huong_dan,
       (e.payload->>'thu_tu_thuc_te')::int AS thu_tu_thuc_te,
       coalesce(e.payload->>'lan', e.payload->>'attempt_no')::int AS lan,
       e.payload->>'nguon' AS nguon,
       e.event_type,
       e.payload
  FROM public.domain_event e
  LEFT JOIN public.service_execution_attempt a
    ON a.clinic_id = e.clinic_id
   AND a.id = nullif(e.payload->>'attempt_id', '')::uuid
  LEFT JOIN public.staff s ON s.id = e.actor_staff_id
  LEFT JOIN LATERAL (
      SELECT u.event_id, u.occurred_at
        FROM public.domain_event u
       WHERE u.clinic_id = e.clinic_id
         AND u.aggregate_type = e.aggregate_type
         AND u.aggregate_id = e.aggregate_id
         AND u.seq > e.seq
         AND u.event_type = CASE e.event_type
                 WHEN 'service.routed' THEN
                     CASE WHEN e.payload->>'nguon' = 'tai_phong'
                          THEN 'service.room_receive_undone'
                          ELSE 'service.routing_invalidated' END
                 WHEN 'service.room_released' THEN 'service.room_release_undone'
                 WHEN 'service.started' THEN 'service.start_cancelled'
                 WHEN 'service.completed' THEN 'service.completion_undone'
                 WHEN 'consultation.completed' THEN 'consultation.reopened'
             END
         AND NOT EXISTS (
             SELECT 1 FROM public.domain_event e2
              WHERE e2.clinic_id = e.clinic_id
                AND e2.aggregate_type = e.aggregate_type
                AND e2.aggregate_id = e.aggregate_id
                AND e2.event_type = e.event_type
                AND e2.seq > e.seq AND e2.seq < u.seq)
       ORDER BY u.seq
       LIMIT 1
  ) ht ON true
 WHERE e.event_type IN (
       'service.routed', 'service.room_released', 'service.room_receive_undone',
       'service.room_release_undone', 'service.room_guided',
       'service.routing_invalidated', 'service.room_transferred',
       'service.started', 'service.start_cancelled', 'service.completed',
       'service.completion_undone', 'service.interrupted', 'service.not_performed',
       'service.patient_moved', 'consultation.started', 'consultation.resumed',
       'consultation.completed', 'consultation.reopened');

COMMENT ON VIEW public.v_moc_hanh_trinh IS
'Mỗi mốc hành trình một dòng (Nhận · Bắt đầu · Xong · Nhả · hướng dẫn · khám lại · các hoàn tác), đọc từ domain_event. bi_hoan_tac = mốc đã bị rút lại. 07/10/2026.';

-- Chỉ backend / phân tích đọc (sổ sự kiện không mở cho trình duyệt).
REVOKE ALL ON public.v_moc_hanh_trinh FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.v_moc_hanh_trinh FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.v_moc_hanh_trinh FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT ON public.v_moc_hanh_trinh TO service_role;
    END IF;
END;
$$;
