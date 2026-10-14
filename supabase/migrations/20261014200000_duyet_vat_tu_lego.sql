-- G8b — NGƯỜI DUYỆT vật tư cần duyệt = LEGO "Duyệt vật tư" (Tuyền chốt 14/10/2026,
-- Q11: "Trưởng ca + Quản lý duyệt, cờ từng mặt hàng") + NGUYÊN NHÂN bán thêm.
--
-- Trước: trigger `luot_vat_tu_gac` ép "người duyệt là vai MANAGEMENT" (viết cứng
-- theo VAI, trái nguyên tắc `permissions/can.py`: không có "quản lý thì được tất").
-- Nay người duyệt là người CÓ quyền `vat_tu.approve` (khối `duyet_vat_tu`):
--   * mặc định chỉ Quản lý (khối nằm trong KHOI_CHI_QUAN_LY — không "mở full",
--     vì mở cho mọi người thì "duyệt" mất nghĩa);
--   * tài khoản Trưởng ca ĐANG có được cấp sẵn ở dưới (Quản lý thu / cấp thêm
--     cho ai tuỳ ý ở màn Phân quyền — tài khoản Trưởng ca MỚI sau này do Quản lý cấp);
--   * không đổi luật nào khác của trigger (giá, hàng đang bán, khoá khi đã thu).
--
-- Chạy lại được (IF NOT EXISTS / ON CONFLICT / CREATE OR REPLACE), không BEGIN/COMMIT.

-- ── 1. Khối + quyền (khớp permissions/catalogue.py — test_danh_muc_quyen_db) ───
INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('duyet_vat_tu', 'Duyệt vật tư', 'supplies',
     'Duyệt bán thêm / nhập vật tư thuộc loại cần duyệt — mặc định Quản lý, Quản lý cấp thêm cho Trưởng ca')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('vat_tu.approve', 'Duyệt bán thêm / nhập vật tư thuộc loại cần duyệt',
     'duyet_vat_tu', 'supplies', 'financial', false)
ON CONFLICT (ma) DO NOTHING;

-- ── 2. Nhóm mẫu: chỉ Quản lý có khối mặc định ────────────────────────────────
UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || ARRAY['duyet_vat_tu']) AS k)
 WHERE p.he_thong
   AND p.ma = 'MANAGEMENT'
   AND NOT (p.khoi @> ARRAY['duyet_vat_tu']);

-- ── 3. Cấp bù cho người đang giữ vai Quản lý + Trưởng ca ─────────────────────
-- Quản lý: giữ đúng quyền họ đang có (trước đây vai MANAGEMENT duyệt được).
-- Trưởng ca: Q11 "Trưởng ca được duyệt". Cùng cách `roster.manage` (20261001260000).
INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, tu_khoi, tu_preset, ly_do)
SELECT DISTINCT m.clinic_id, m.staff_id, 'vat_tu.approve', 'CLINIC', NULL::uuid,
       'duyet_vat_tu', m.role, 'Lego Duyệt vật tư (Tuyền 14/10/2026) — Quản lý + Trưởng ca'
  FROM public.clinic_membership m
  JOIN public.staff s ON s.id = m.staff_id AND s.is_active
 WHERE m.is_active AND m.role IN ('MANAGEMENT', 'TRUONG_CA')
ON CONFLICT DO NOTHING;

-- ── 4. Nguyên nhân bán thêm ──────────────────────────────────────────────────
ALTER TABLE public.luot_vat_tu ADD COLUMN IF NOT EXISTS ly_do_ban text;
ALTER TABLE public.luot_vat_tu DROP CONSTRAINT IF EXISTS luot_vat_tu_ly_do_ban_hop_le;
ALTER TABLE public.luot_vat_tu ADD CONSTRAINT luot_vat_tu_ly_do_ban_hop_le
    CHECK (ly_do_ban IS NULL OR char_length(btrim(ly_do_ban)) BETWEEN 5 AND 500);
COMMENT ON COLUMN public.luot_vat_tu.ly_do_ban IS
'Nguyên nhân bán thêm vật tư ở quầy thu (khách yêu cầu thêm, dịch vụ cần thêm, thay vật tư hỏng…). Luôn ghi khi có gửi; bắt buộc khi dây vat_tu_bat_ly_do_ban BẬT. G8b, 14/10/2026.';

-- ── 5. Trigger: người duyệt phải CÓ lego (thay vì vai MANAGEMENT) ───────────
-- Chép nguyên hàm của 20261003000000; CHỈ đổi điều kiện người duyệt.
CREATE OR REPLACE FUNCTION public.luot_vat_tu_gac()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    sp record;
    trung uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT s."group", s.active, s.unit_price, s.can_ql_duyet, s.clinic_id
          INTO sp FROM public.service_price s WHERE s.id = NEW.service_price_id;
        IF NOT FOUND OR sp."group" <> 'vat_tu' OR sp.clinic_id <> NEW.clinic_id THEN
            RAISE EXCEPTION 'luot_vat_tu: không phải vật tư của phòng khám này'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT sp.active OR coalesce(sp.unit_price, 0) <= 0 THEN
            RAISE EXCEPTION 'luot_vat_tu: vật tư chưa có giá hoặc đã ngưng bán — không bán được'
                USING ERRCODE = 'check_violation';
        END IF;
        IF sp.can_ql_duyet AND NOT EXISTS (
               SELECT 1
                 FROM public.v_quyen_thuc_te q
                 JOIN public.clinic_membership m
                   ON m.clinic_id = q.clinic_id AND m.staff_id = q.staff_id
                  AND m.is_active
                 JOIN public.staff s2 ON s2.id = q.staff_id AND s2.is_active
                WHERE q.clinic_id = NEW.clinic_id AND q.staff_id = NEW.duyet_boi
                  AND q.capability = 'vat_tu.approve'
                  AND q.scope_type = 'CLINIC') THEN
            RAISE EXCEPTION 'luot_vat_tu: hàng này cần người có quyền Duyệt vật tư duyệt bán (kèm lý do)'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    -- UPDATE: đổi số lượng / giá / bỏ khi đã nằm trong lần thu.
    IF NEW.so_luong IS DISTINCT FROM OLD.so_luong
       OR NEW.don_gia IS DISTINCT FROM OLD.don_gia
       OR (NEW.bo_luc IS NOT NULL AND OLD.bo_luc IS NULL) THEN
        SELECT bl.payment_cycle_id INTO trung
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = OLD.clinic_id
           AND bl.source_type = 'vat_tu' AND bl.source_id = OLD.id::text
           AND bl.billing_owner = 'CLINIC'
           AND c.status IN ('PENDING_VERIFICATION', 'PAID')
         LIMIT 1;
        IF trung IS NOT NULL THEN
            RAISE EXCEPTION
                'luot_vat_tu: dòng đã nằm trong lần thu % — hoàn tác lần thu trước khi đổi', trung
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
