-- XOÁ ẢNH / TỆP KẾT QUẢ — XOÁ MỀM, HOÀN TÁC 30 NGÀY (V9, Tuyền chốt 30/09/2026).
--
-- Trước migration này KHÔNG có đường xoá nào: tải nhầm ảnh của khách khác, ảnh
-- mờ phải chụp lại, tệp trùng… đều nằm lại trong hồ sơ và hiện ra ở mọi màn.
--
-- XOÁ MỀM, KHÔNG XOÁ DÒNG. Tệp kết quả là hồ sơ y khoa: khách có thể đã cầm bản
-- in, bác sĩ có thể đã đọc. Nên "xoá" = ẩn khỏi mọi chỗ đọc (view hiệu lực bên
-- dưới) + ghi ai, lúc nào, vì sao. Khôi phục được trong 30 ngày khi tệp vật lý
-- còn trên ổ. Việc dọn ổ (job hằng ngày trong su-kien) chỉ đụng tệp đã xoá quá
-- 30 ngày VÀ chưa từng được xem / duyệt / gửi — tệp đã vào hồ sơ thì chỉ ẩn.
--
--   da_xoa_luc / da_xoa_boi_staff_id / da_xoa_ly_do / da_xoa_loai   đủ bộ hoặc rỗng hết
--   da_xoa_loai  XOA         xoá thường (chưa gửi khách, phiên đọc chưa đóng)
--                DINH_CHINH  "Đính chính – gỡ tệp": tệp đã gửi khách / phiên đọc
--                            đã đóng — cần quyền duyệt kết quả (service kiểm)
--   da_don_tep_luc  job đã xoá tệp vật lý; từ đây KHÔNG khôi phục được nữa.
--
-- BA CHỐT Ở POSTGRES (không nhờ Python nhớ):
--   1. CHECK đủ bộ (không có "đã xoá" mà thiếu người / lý do).
--   2. Không DELETE dòng (dùng lại `prevent_hard_delete` — cùng cửa thoát
--      `app.allow_hard_delete` cho job dọn có kiểm soát) và không TRUNCATE.
--   3. Không sửa đè vết xoá: đã xoá thì chỉ được (a) khôi phục — đưa cả bộ về
--      NULL, chỉ khi `da_don_tep_luc IS NULL`; hoặc (b) đánh dấu đã dọn một lần.
--
-- VIEW `v_tep_ket_qua_hieu_luc` = chưa xoá VÀ chưa thu hồi. Mọi chỗ ĐỌC tệp
-- trong code đọc view này (sửa luôn lỗi cũ: danh sách tệp của khách vẫn hiện tệp
-- đã thu hồi). Chỗ GHI vẫn ghi bảng. `security_invoker` để RLS của bảng vẫn áp
-- cho vai `authenticated`.
--
-- QUYỀN `result.file.delete` thuộc khối `ket_qua` (Kết quả cận lâm sàng) — hướng
-- "MỞ HẾT" 30/09: ai có lego kết quả thì xoá được. Cấp bù cho mọi người đang
-- giữ `result.form.fill` (cùng phạm vi, cùng hạn).
--
-- `v_viec_cskh`: tệp đã xoá không còn sinh việc "kết quả chưa gửi" — chép nguyên
-- bản 20260929950000, chỉ thêm `k.da_xoa_luc IS NULL` ở ba chỗ đọc tep_ket_qua.

-- ── 1. Cột ──────────────────────────────────────────────────────────────────
ALTER TABLE public.tep_ket_qua
    ADD COLUMN IF NOT EXISTS da_xoa_luc timestamptz,
    ADD COLUMN IF NOT EXISTS da_xoa_boi_staff_id uuid REFERENCES public.staff(id),
    ADD COLUMN IF NOT EXISTS da_xoa_ly_do text,
    ADD COLUMN IF NOT EXISTS da_xoa_loai text,
    ADD COLUMN IF NOT EXISTS da_don_tep_luc timestamptz;

COMMENT ON COLUMN public.tep_ket_qua.da_xoa_luc IS
    'Xoá mềm (V9 30/09/2026): tệp ẩn khỏi mọi chỗ đọc; khôi phục được khi da_don_tep_luc IS NULL.';
COMMENT ON COLUMN public.tep_ket_qua.da_xoa_loai IS
    'XOA = xoá thường; DINH_CHINH = đính chính – gỡ tệp đã gửi khách / phiên đọc đã đóng.';
COMMENT ON COLUMN public.tep_ket_qua.da_don_tep_luc IS
    'Job hằng ngày đã xoá tệp vật lý. Từ đây không khôi phục được.';

-- ── 2. CHECK đủ bộ ──────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.tep_ket_qua'::regclass
                      AND conname = 'tep_ket_qua_xoa_du_bo') THEN
        ALTER TABLE public.tep_ket_qua
            ADD CONSTRAINT tep_ket_qua_xoa_du_bo CHECK (
                (da_xoa_luc IS NULL
                 AND da_xoa_boi_staff_id IS NULL
                 AND da_xoa_ly_do IS NULL
                 AND da_xoa_loai IS NULL
                 AND da_don_tep_luc IS NULL)
                OR
                (da_xoa_luc IS NOT NULL
                 AND da_xoa_boi_staff_id IS NOT NULL
                 AND da_xoa_ly_do IS NOT NULL
                 AND length(btrim(da_xoa_ly_do)) > 0
                 AND da_xoa_loai IN ('XOA', 'DINH_CHINH')
                 AND (da_don_tep_luc IS NULL OR da_don_tep_luc >= da_xoa_luc))
            );
    END IF;
END $$;

-- ── 3. Không xoá dòng, không TRUNCATE ───────────────────────────────────────
DROP TRIGGER IF EXISTS trg_tep_ket_qua_no_delete ON public.tep_ket_qua;
CREATE TRIGGER trg_tep_ket_qua_no_delete
    BEFORE DELETE ON public.tep_ket_qua
    FOR EACH ROW EXECUTE FUNCTION public.prevent_hard_delete();

DROP TRIGGER IF EXISTS trg_tep_ket_qua_no_truncate ON public.tep_ket_qua;
CREATE TRIGGER trg_tep_ket_qua_no_truncate
    BEFORE TRUNCATE ON public.tep_ket_qua
    FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_hard_delete();

-- ── 4. Không sửa đè vết xoá ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.tep_ket_qua_khoa_vet_xoa()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
BEGIN
    -- Đã dọn tệp vật lý: bộ cột xoá đóng băng hoàn toàn.
    IF OLD.da_don_tep_luc IS NOT NULL THEN
        IF NEW.da_xoa_luc IS DISTINCT FROM OLD.da_xoa_luc
           OR NEW.da_xoa_boi_staff_id IS DISTINCT FROM OLD.da_xoa_boi_staff_id
           OR NEW.da_xoa_ly_do IS DISTINCT FROM OLD.da_xoa_ly_do
           OR NEW.da_xoa_loai IS DISTINCT FROM OLD.da_xoa_loai
           OR NEW.da_don_tep_luc IS DISTINCT FROM OLD.da_don_tep_luc THEN
            RAISE EXCEPTION 'Tệp kết quả đã dọn khỏi ổ — không khôi phục hay sửa vết xoá được'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.da_xoa_luc IS NULL THEN
        -- Chưa xoá → xoá (đặt cả bộ; CHECK ép đủ). Không đánh dấu dọn cùng lúc.
        IF NEW.da_don_tep_luc IS NOT NULL THEN
            RAISE EXCEPTION 'Chỉ dọn tệp vật lý của tệp đã xoá từ trước'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- Đã xoá, chưa dọn.
    IF NEW.da_xoa_luc IS NULL THEN
        -- Khôi phục: cả bộ về NULL (CHECK ép), không kèm mốc dọn.
        RETURN NEW;
    END IF;

    -- Vẫn ở trạng thái đã xoá: vết xoá không được sửa; chỉ được đánh dấu đã dọn.
    IF NEW.da_xoa_luc IS DISTINCT FROM OLD.da_xoa_luc
       OR NEW.da_xoa_boi_staff_id IS DISTINCT FROM OLD.da_xoa_boi_staff_id
       OR NEW.da_xoa_ly_do IS DISTINCT FROM OLD.da_xoa_ly_do
       OR NEW.da_xoa_loai IS DISTINCT FROM OLD.da_xoa_loai THEN
        RAISE EXCEPTION 'Không sửa đè vết xoá tệp kết quả (ai, lúc nào, vì sao)'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_tep_ket_qua_khoa_vet_xoa ON public.tep_ket_qua;
CREATE TRIGGER trg_tep_ket_qua_khoa_vet_xoa
    BEFORE UPDATE OF da_xoa_luc, da_xoa_boi_staff_id, da_xoa_ly_do, da_xoa_loai,
                     da_don_tep_luc
    ON public.tep_ket_qua
    FOR EACH ROW EXECUTE FUNCTION public.tep_ket_qua_khoa_vet_xoa();

-- Job dọn tìm theo mốc xoá.
CREATE INDEX IF NOT EXISTS idx_tep_ket_qua_cho_don
    ON public.tep_ket_qua (da_xoa_luc)
    WHERE da_xoa_luc IS NOT NULL AND da_don_tep_luc IS NULL;

-- ── 5. View hiệu lực ────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_tep_ket_qua_hieu_luc
    WITH (security_invoker = true) AS
SELECT t.*
  FROM public.tep_ket_qua t
 WHERE t.da_xoa_luc IS NULL
   AND t.thu_hoi_luc IS NULL;

COMMENT ON VIEW public.v_tep_ket_qua_hieu_luc IS
    'Tệp kết quả còn hiệu lực: chưa xoá mềm, chưa thu hồi. Mọi chỗ ĐỌC tệp đọc view này (V9 30/09/2026).';

GRANT SELECT ON public.v_tep_ket_qua_hieu_luc TO authenticated;
GRANT SELECT ON public.v_tep_ket_qua_hieu_luc TO service_role;

-- ── 6. Quyền result.file.delete (khối ket_qua) ──────────────────────────────
INSERT INTO capability (ma, ten, work_pack, module, rui_ro)
VALUES ('result.file.delete',
        'Xoá / khôi phục tệp kết quả (xoá mềm, hoàn tác 30 ngày)',
        'ket_qua', 'result', 'clinical')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO capability_grant
    (clinic_id, staff_id, capability, scope_type, scope_id, valid_from,
     valid_until, tu_khoi, tu_preset, ly_do)
SELECT g.clinic_id, g.staff_id, 'result.file.delete', g.scope_type, g.scope_id,
       g.valid_from, g.valid_until, coalesce(g.tu_khoi, 'ket_qua'), g.tu_preset,
       'Quyền mới của khối Kết quả (V9 30/09/2026) — cấp bù cho người đang có result.form.fill'
  FROM public.capability_grant g
 WHERE g.capability = 'result.form.fill'
   AND g.revoked_at IS NULL
   AND (g.valid_until IS NULL OR g.valid_until > now())
ON CONFLICT DO NOTHING;

-- ── 7. v_viec_cskh: tệp đã xoá không sinh việc CSKH ─────────────────────────
CREATE OR REPLACE VIEW public.v_viec_cskh
    WITH (security_invoker = true) AS
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
         SELECT o.clinic_id,
            vi.clinic_patient_id,
            'CHO_BAC_SI'::text AS loai,
            1 AS uu_tien,
            (o.ket_qua_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay AS han,
            vi.appointment_id
           FROM service_order o
             JOIN visit vi ON vi.visit_id = o.visit_id AND vi.clinic_id = o.clinic_id
             JOIN node_definition nd ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
             JOIN luat_cskh l_1 ON l_1.clinic_id = o.clinic_id AND l_1.loai_viec = 'CHO_BAC_SI'::text AND l_1.bat
          WHERE (nd.lam_ben_ngoai OR nd.flow_group = 'ket_qua'::text) AND (o.exec_status <> ALL (ARRAY['draft'::text, 'cancelled'::text])) AND o.ket_qua_luc IS NOT NULL AND o.duyet_luc IS NULL AND NOT (EXISTS ( SELECT 1
                   FROM tep_ket_qua k
                  WHERE k.clinic_id = o.clinic_id AND k.service_order_id = o.id AND k.da_xoa_luc IS NULL))
        UNION ALL
         SELECT o.clinic_id,
            vi.clinic_patient_id,
            'CHO_KQ_XN'::text AS text,
            3,
            COALESCE((f.due_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date, (COALESCE(o.finished_at, o.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay) AS "coalesce",
            vi.appointment_id
           FROM service_order o
             JOIN visit vi ON vi.visit_id = o.visit_id AND vi.clinic_id = o.clinic_id
             JOIN node_definition nd ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
             JOIN luat_cskh l_1 ON l_1.clinic_id = o.clinic_id AND l_1.loai_viec = 'CHO_KQ_XN'::text AND l_1.bat
             LEFT JOIN follow_up_case f ON f.clinic_id = o.clinic_id AND f.service_order_id = o.id AND f.status = 'OPEN'::text
          WHERE (nd.lam_ben_ngoai OR nd.flow_group = 'ket_qua'::text) AND o.exec_status = 'performed'::text AND o.ket_qua_luc IS NULL AND o.created_at > (now() - '60 days'::interval)
        UNION ALL
         SELECT r.clinic_id,
            r.clinic_patient_id,
            'CHO_BAC_SI'::text AS loai,
            1 AS uu_tien,
            (r.result_received_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay AS han,
            NULL::uuid AS appointment_id
           FROM lab_result r
             JOIN luat_cskh l_1 ON l_1.clinic_id = r.clinic_id AND l_1.loai_viec = 'CHO_BAC_SI'::text AND l_1.bat
          WHERE r.result_value IS NOT NULL AND NOT r.is_finalized
        UNION ALL
         SELECT r.clinic_id,
            r.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (COALESCE(r.reviewed_at, r.result_received_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay,
            NULL::uuid AS uuid
           FROM lab_result r
             JOIN luat_cskh l_1 ON l_1.clinic_id = r.clinic_id AND l_1.loai_viec = 'KQ_CHUA_GUI'::text AND l_1.bat
          WHERE r.result_value IS NOT NULL AND r.is_finalized AND NOT (EXISTS ( SELECT 1
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
          WHERE n.trang_thai = 'CHO_GOI'::text
            -- 29/09/2026: việc từ phiếu khám chỉ hiện TỪ hạn gọi (T−7).
            AND (n.nguon <> 'PHIEU_KHAM'::text
                 OR n.han_goi <= (now() AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date)
            AND (n.appointment_id IS NULL OR (EXISTS ( SELECT 1
                   FROM appointment a
                  WHERE a.id = n.appointment_id AND (a.status <> ALL (ARRAY['CHECKED_IN'::text, 'COMPLETED'::text, 'NO_SHOW'::text, 'CANCELLED'::text, 'DOCTOR_DECLINED'::text])))))
        UNION ALL
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'NHAC_HEN_MAI'::text AS text,
            8,
            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date - l_1.so_ngay,
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'NHAC_HEN_MAI'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date >= h_1.d AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date <= (h_1.d + l_1.so_ngay) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'NHAC_HEN'::text AND t.huy_luc IS NULL))
        UNION ALL
         SELECT a.clinic_id,
            a.clinic_patient_id,
            'CHO_XAC_NHAN'::text AS text,
            10,
            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date - l_1.so_ngay,
            a.id
           FROM appointment a
             JOIN luat_cskh l_1 ON l_1.clinic_id = a.clinic_id AND l_1.loai_viec = 'CHO_XAC_NHAN'::text AND l_1.bat
             CROSS JOIN hom_nay h_1
          WHERE (a.status <> ALL (ARRAY['CANCELLED'::text, 'NO_SHOW'::text, 'DOCTOR_DECLINED'::text, 'COMPLETED'::text, 'CHECKED_IN'::text])) AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date >= h_1.d AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date <= (h_1.d + l_1.so_ngay) AND (a.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date < ((a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date - l_1.so_ngay) AND NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH'::text AND t.huy_luc IS NULL))
        UNION ALL
         SELECT k.clinic_id,
            k.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_kq.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_kq ON l_kq.clinic_id = k.clinic_id AND l_kq.loai_viec = 'KQ_CHUA_GUI'::text AND l_kq.bat
          WHERE k.xac_nhan_trang_thai = 'HOP_LE'::text AND k.gui_luc IS NULL AND k.da_xoa_luc IS NULL
        UNION ALL
         SELECT k.clinic_id,
            k.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_kq.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_kq ON l_kq.clinic_id = k.clinic_id AND l_kq.loai_viec = 'KQ_CHUA_GUI'::text AND l_kq.bat
          WHERE k.xac_nhan_trang_thai IS NULL AND k.gui_luc IS NULL AND k.da_xoa_luc IS NULL
        UNION ALL
         SELECT o.clinic_id,
            o.clinic_patient_id,
            'VUOT_SUC_CHUA'::text AS text,
            0,
            h_1.d,
            o.appointment_id
           FROM lich_vuot_suc_chua() o(clinic_id, appointment_id, clinic_patient_id, doctor_id, slot_start, tran, thu_tu, cong_bo_luc)
             JOIN luat_cskh l_vt ON l_vt.clinic_id = o.clinic_id AND l_vt.loai_viec = 'VUOT_SUC_CHUA'::text AND l_vt.bat
             CROSS JOIN hom_nay h_1
          WHERE NOT (EXISTS ( SELECT 1
                   FROM tuong_tac_cskh t
                  WHERE t.appointment_id = o.appointment_id AND t.trang_thai_ma = 'VUOT_SUC_CHUA'::text AND t.xay_ra_luc >= o.cong_bo_luc AND t.huy_luc IS NULL))
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
