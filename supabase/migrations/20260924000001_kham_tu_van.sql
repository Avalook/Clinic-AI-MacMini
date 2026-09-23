-- KHÁM TƯ VẤN + đường đi sau check-in do khối HÀNH TRÌNH quyết (nhóm 1, Tuyền
-- chốt 24/09/2026 — docs/BAN-DO-DAY-NOI-LEGO.md "Bản chốt 24/09", dây H1/H3).
--
--   H1  check-in loại khám "qua tư vấn" → hàng BÁC SĨ TƯ VẤN (hàng chung, ai rảnh
--       nhận); đo sinh hiệu trước — khách hiện "chờ đo sinh hiệu" (blocked) tới
--       khi có sinh hiệu thì mở (waiting). Không khoá: tư vấn vẫn nhận được sớm.
--   H3  tư vấn bấm Xong → hàng chờ khám thật của BÁC SĨ CHÍNH.
--
-- Chạy lại được (IF NOT EXISTS / DROP CONSTRAINT IF EXISTS).

-- 1. Loại dịch vụ nào đi qua tư vấn — DÂY NGHIỆP VỤ, quản lý chỉnh được.
ALTER TABLE public.service_type
    ADD COLUMN IF NOT EXISTS qua_tu_van boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.service_type.qua_tu_van IS
'Check-in loại khám này thì khách qua bác sĩ tư vấn trước bác sĩ chính (dây H1). Quản lý chỉnh được.';

-- 5 loại khám lõi (Tuyền 24/09: "trừ thủ thuật và sàn chậu còn 5 cái kia đều
-- đi qua"). Sản 1/2/3 là sản khoa theo tầng — cùng một loại khám.
UPDATE public.service_type
   SET qua_tu_van = true
 WHERE code IN ('PHU_KHOA', 'NOI_TIET_TINH_DUC', 'NAM_KHOA', 'HIEM_MUON',
                'SAN_1', 'SAN_2', 'SAN_3')
   AND NOT qua_tu_van;

-- 2. Phiên TƯ VẤN: vòng số 0, kết thúc bằng "đã chuyển bác sĩ chính".
ALTER TABLE public.consultation DROP CONSTRAINT IF EXISTS consultation_round_positive;
ALTER TABLE public.consultation ADD CONSTRAINT consultation_round_positive
    CHECK (round_no >= 0);
ALTER TABLE public.consultation DROP CONSTRAINT IF EXISTS consultation_kind;
ALTER TABLE public.consultation ADD CONSTRAINT consultation_kind
    CHECK (kind IN ('TU_VAN', 'PRIMARY', 'REVIEW'));
ALTER TABLE public.consultation DROP CONSTRAINT IF EXISTS consultation_kind_round;
ALTER TABLE public.consultation ADD CONSTRAINT consultation_kind_round
    CHECK ((kind = 'PRIMARY') = (round_no = 1) AND (kind = 'TU_VAN') = (round_no = 0));
ALTER TABLE public.consultation DROP CONSTRAINT IF EXISTS consultation_outcome;
ALTER TABLE public.consultation ADD CONSTRAINT consultation_outcome
    CHECK (outcome IS NULL OR outcome IN
           ('NO_SERVICES', 'SERVICES', 'DONE', 'MORE_SERVICES', 'HANDED_OVER'));
ALTER TABLE public.consultation DROP CONSTRAINT IF EXISTS consultation_outcome_kind;
ALTER TABLE public.consultation ADD CONSTRAINT consultation_outcome_kind
    CHECK (outcome IS NULL
           OR (kind = 'PRIMARY' AND outcome IN ('NO_SERVICES', 'SERVICES'))
           OR (kind = 'REVIEW' AND outcome IN ('DONE', 'MORE_SERVICES'))
           OR (kind = 'TU_VAN' AND outcome = 'HANDED_OVER'));

-- 3. Hàng chờ TƯ VẤN: làn riêng, không gắn bác sĩ, không gắn phòng.
ALTER TABLE public.queue_entry DROP CONSTRAINT IF EXISTS queue_entry_lane;
ALTER TABLE public.queue_entry ADD CONSTRAINT queue_entry_lane
    CHECK (lane IN ('TU_VAN', 'DOCTOR', 'ROOM'));
ALTER TABLE public.queue_entry DROP CONSTRAINT IF EXISTS queue_entry_reason;
ALTER TABLE public.queue_entry ADD CONSTRAINT queue_entry_reason
    CHECK (reason IN ('TU_VAN', 'PRIMARY', 'SERVICE', 'REVIEW'));
ALTER TABLE public.queue_entry DROP CONSTRAINT IF EXISTS queue_entry_lane_reason;
ALTER TABLE public.queue_entry ADD CONSTRAINT queue_entry_lane_reason
    CHECK ((lane = 'DOCTOR') = (reason IN ('PRIMARY', 'REVIEW'))
           AND (lane = 'TU_VAN') = (reason = 'TU_VAN'));

-- 4. Đường đi của lượt: thêm "qua tư vấn".
ALTER TABLE public.encounter_flow DROP CONSTRAINT IF EXISTS encounter_flow_route;
ALTER TABLE public.encounter_flow ADD CONSTRAINT encounter_flow_route
    CHECK (route_decision IS NULL OR route_decision IN ('TU_VAN', 'PRIMARY', 'SERVICES'));

-- 5. Quyền "Khám tư vấn" — khối riêng, mặc định cho bác sĩ (bảng màn Tuyền chốt
-- 23/09: "Bàn khám tư vấn — mặc định ở bác sĩ tư vấn"); quản lý cấp thêm được.
INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('tu_van', 'Khám tư vấn', 'consultation',
     'Nhận khách ở hàng tư vấn, hỏi bệnh ban đầu, chuyển bác sĩ chính')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang)
VALUES ('clinical.intake.perform', 'Khám tư vấn — nhận khách, chuyển bác sĩ chính',
        'tu_van', 'consultation', 'clinical', false)
ON CONFLICT (ma) DO NOTHING;

UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k) FROM unnest(p.khoi || ARRAY['tu_van']) AS k)
 WHERE p.ma = 'DOCTOR' AND p.he_thong
   AND NOT ('tu_van' = ANY(p.khoi));

SELECT public.cap_quyen_cho_moi_thanh_vien();
