-- Migration: 20260920000005_xac_nhan_tep_ket_qua.sql
-- Result confirmation per file (Blocker 1)
-- Tách UPLOAD khỏi KET_QUA_HOP_LE.
-- Tệp đối tác upload bắt đầu ở trạng thái CHO_XAC_NHAN.
-- Chỉ tệp được xác nhận HOP_LE mới làm has_valid_result = true cho external order.
-- Internal / non-order files: xac_nhan_trang_thai = NULL (confirmation flow không áp dụng).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'tep_ket_qua') THEN
    RAISE EXCEPTION 'Table public.tep_ket_qua does not exist.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'staff') THEN
    RAISE EXCEPTION 'Table public.staff does not exist.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'staff_capability') THEN
    RAISE EXCEPTION 'Table public.staff_capability does not exist. Baseline schema required.';
  END IF;
END $$;

-- 1. Thêm các cột trạng thái xác nhận và thu hồi
-- NULL = confirmation flow không áp dụng (internal / non-order files).
-- Không dùng DEFAULT 'CHO_XAC_NHAN' — chỉ external partner files mới có state.
ALTER TABLE public.tep_ket_qua
  ADD COLUMN IF NOT EXISTS xac_nhan_trang_thai text NULL,
  ADD COLUMN IF NOT EXISTS xac_nhan_luc timestamp with time zone NULL,
  ADD COLUMN IF NOT EXISTS xac_nhan_boi_staff_id uuid NULL REFERENCES public.staff(id),
  ADD COLUMN IF NOT EXISTS xac_nhan_ly_do text NULL,
  ADD COLUMN IF NOT EXISTS thu_hoi_luc timestamp with time zone NULL,
  ADD COLUMN IF NOT EXISTS thu_hoi_boi_staff_id uuid NULL REFERENCES public.staff(id),
  ADD COLUMN IF NOT EXISTS thu_hoi_ly_do text NULL;

-- 2. Ràng buộc toàn vẹn trạng thái
-- Hỗ trợ 5 trạng thái: NULL (không áp dụng), CHO_XAC_NHAN, HOP_LE, TU_CHOI, THU_HOI.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_tep_ket_qua_xac_nhan'
  ) THEN
    ALTER TABLE public.tep_ket_qua DROP CONSTRAINT chk_tep_ket_qua_xac_nhan;
  END IF;

  ALTER TABLE public.tep_ket_qua
    ADD CONSTRAINT chk_tep_ket_qua_xac_nhan CHECK (
      -- NULL: confirmation flow không áp dụng (internal/non-order).
      -- Mọi confirmation/thu-hoi fields phải NULL.
      (xac_nhan_trang_thai IS NULL
       AND xac_nhan_luc IS NULL
       AND xac_nhan_boi_staff_id IS NULL
       AND xac_nhan_ly_do IS NULL
       AND thu_hoi_luc IS NULL
       AND thu_hoi_boi_staff_id IS NULL
       AND thu_hoi_ly_do IS NULL)
      OR
      (xac_nhan_trang_thai = 'CHO_XAC_NHAN'
       AND xac_nhan_luc IS NULL
       AND xac_nhan_boi_staff_id IS NULL
       AND thu_hoi_luc IS NULL
       AND thu_hoi_boi_staff_id IS NULL)
      OR
      (xac_nhan_trang_thai = 'HOP_LE'
       AND xac_nhan_luc IS NOT NULL
       AND xac_nhan_boi_staff_id IS NOT NULL
       AND thu_hoi_luc IS NULL
       AND thu_hoi_boi_staff_id IS NULL)
      OR
      (xac_nhan_trang_thai = 'TU_CHOI'
       AND xac_nhan_luc IS NOT NULL
       AND xac_nhan_boi_staff_id IS NOT NULL
       AND xac_nhan_ly_do IS NOT NULL AND length(trim(xac_nhan_ly_do)) > 0
       AND thu_hoi_luc IS NULL
       AND thu_hoi_boi_staff_id IS NULL)
      OR
      (xac_nhan_trang_thai = 'THU_HOI'
       AND xac_nhan_luc IS NOT NULL
       AND xac_nhan_boi_staff_id IS NOT NULL
       AND thu_hoi_luc IS NOT NULL
       AND thu_hoi_boi_staff_id IS NOT NULL
       AND thu_hoi_ly_do IS NOT NULL AND length(trim(thu_hoi_ly_do)) > 0)
    );
END $$;

-- 3. Trigger kiểm soát chuyển đổi trạng thái (State Machine) + Immutability
CREATE OR REPLACE FUNCTION public.fn_tep_ket_qua_chuyen_trang_thai()
RETURNS TRIGGER AS $$
BEGIN
  -- Bỏ qua nếu cả OLD và NEW đều NULL (internal files, không áp dụng)
  IF OLD.xac_nhan_trang_thai IS NULL AND NEW.xac_nhan_trang_thai IS NULL THEN
    RETURN NEW;
  END IF;

  -- Không cho phép chuyển từ NULL sang non-NULL hoặc ngược lại bằng UPDATE
  -- (chỉ INSERT mới quyết định state ban đầu)
  IF OLD.xac_nhan_trang_thai IS NULL AND NEW.xac_nhan_trang_thai IS NOT NULL THEN
    RAISE EXCEPTION 'Không được chuyển tệp nội bộ (NULL) sang luồng xác nhận bên ngoài';
  END IF;
  IF OLD.xac_nhan_trang_thai IS NOT NULL AND NEW.xac_nhan_trang_thai IS NULL THEN
    RAISE EXCEPTION 'Không được chuyển tệp bên ngoài sang NULL';
  END IF;

  -- Same state: chặn sửa confirmation/thu-hoi fields (immutability)
  IF OLD.xac_nhan_trang_thai IS NOT DISTINCT FROM NEW.xac_nhan_trang_thai THEN
    IF OLD.xac_nhan_luc IS DISTINCT FROM NEW.xac_nhan_luc
       OR OLD.xac_nhan_boi_staff_id IS DISTINCT FROM NEW.xac_nhan_boi_staff_id
       OR OLD.xac_nhan_ly_do IS DISTINCT FROM NEW.xac_nhan_ly_do
       OR OLD.thu_hoi_luc IS DISTINCT FROM NEW.thu_hoi_luc
       OR OLD.thu_hoi_boi_staff_id IS DISTINCT FROM NEW.thu_hoi_boi_staff_id
       OR OLD.thu_hoi_ly_do IS DISTINCT FROM NEW.thu_hoi_ly_do
    THEN
      RAISE EXCEPTION 'Không được sửa thông tin xác nhận/thu hồi khi giữ nguyên trạng thái (immutable audit fields)';
    END IF;
    RETURN NEW;
  END IF;

  -- State machine:
  -- CHO_XAC_NHAN -> HOP_LE
  -- CHO_XAC_NHAN -> TU_CHOI
  -- HOP_LE       -> THU_HOI
  IF OLD.xac_nhan_trang_thai = 'CHO_XAC_NHAN' AND NEW.xac_nhan_trang_thai IN ('HOP_LE', 'TU_CHOI') THEN
    RETURN NEW;
  ELSIF OLD.xac_nhan_trang_thai = 'HOP_LE' AND NEW.xac_nhan_trang_thai = 'THU_HOI' THEN
    -- Giữ nguyên actor và thời gian xác nhận ban đầu
    IF NEW.xac_nhan_luc IS DISTINCT FROM OLD.xac_nhan_luc
       OR NEW.xac_nhan_boi_staff_id IS DISTINCT FROM OLD.xac_nhan_boi_staff_id
    THEN
      RAISE EXCEPTION 'Không được ghi đè thông tin xác nhận ban đầu khi thu hồi tệp kết quả';
    END IF;
    -- GIỮ NGUYÊN cho_phep_gui_luc / cho_phep_gui_boi_staff_id
    -- để audit vẫn biết bác sĩ từng duyệt.
    -- Tệp THU_HOI không gửi được vì current state, không phải vì xóa lịch sử approval.
    RETURN NEW;
  ELSE
    RAISE EXCEPTION 'Chuyển trạng thái xác nhận tệp không hợp lệ từ % sang %',
      OLD.xac_nhan_trang_thai, NEW.xac_nhan_trang_thai;
  END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tep_ket_qua_chuyen_trang_thai ON public.tep_ket_qua;
CREATE TRIGGER trg_tep_ket_qua_chuyen_trang_thai
  BEFORE UPDATE OF xac_nhan_trang_thai ON public.tep_ket_qua
  FOR EACH ROW
  EXECUTE FUNCTION public.fn_tep_ket_qua_chuyen_trang_thai();

-- 4. Trigger kiểm soát duyệt gửi khách
-- Chỉ chặn hành động MỚI SET approval (NULL -> non-NULL)
-- nếu external confirmation state chưa HOP_LE.
-- Không chặn UPDATE khác trên row chỉ vì row từng có cho_phep_gui_luc.
-- Đặc biệt: HOP_LE + đã doctor approve -> THU_HOI phải thành công (giữ approval history).
-- Internal/non-order files (xac_nhan_trang_thai IS NULL): KHÔNG bị chặn.
CREATE OR REPLACE FUNCTION public.fn_tep_ket_qua_kiem_tra_cho_phep_gui()
RETURNS TRIGGER AS $$
BEGIN
  -- Chỉ quan tâm khi đang SET approval mới (NULL -> non-NULL)
  IF OLD.cho_phep_gui_luc IS NULL AND NEW.cho_phep_gui_luc IS NOT NULL THEN
    -- External files: phải ở HOP_LE mới được approve-send
    IF NEW.xac_nhan_trang_thai IS NOT NULL AND NEW.xac_nhan_trang_thai <> 'HOP_LE' THEN
      RAISE EXCEPTION 'Chỉ tệp kết quả ở trạng thái HOP_LE mới được phép duyệt gửi cho khách (hiện tại: %)',
        NEW.xac_nhan_trang_thai;
    END IF;
    -- Internal files (xac_nhan_trang_thai IS NULL): cho qua, không yêu cầu confirmation
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tep_ket_qua_kiem_tra_cho_phep_gui ON public.tep_ket_qua;
CREATE TRIGGER trg_tep_ket_qua_kiem_tra_cho_phep_gui
  BEFORE INSERT OR UPDATE OF cho_phep_gui_luc, xac_nhan_trang_thai ON public.tep_ket_qua
  FOR EACH ROW
  EXECUTE FUNCTION public.fn_tep_ket_qua_kiem_tra_cho_phep_gui();

COMMENT ON COLUMN public.tep_ket_qua.xac_nhan_trang_thai IS 'Trạng thái xác nhận: NULL (không áp dụng / internal), CHO_XAC_NHAN, HOP_LE, TU_CHOI, THU_HOI';
COMMENT ON COLUMN public.tep_ket_qua.xac_nhan_luc IS 'Thời điểm xác nhận';
COMMENT ON COLUMN public.tep_ket_qua.xac_nhan_boi_staff_id IS 'Nhân sự có capability ket_qua.xac_nhan thực hiện xác nhận';
COMMENT ON COLUMN public.tep_ket_qua.xac_nhan_ly_do IS 'Lý do từ chối (bắt buộc khi xac_nhan_trang_thai = TU_CHOI)';
COMMENT ON COLUMN public.tep_ket_qua.thu_hoi_luc IS 'Thời điểm thu hồi tệp đã từng HOP_LE';
COMMENT ON COLUMN public.tep_ket_qua.thu_hoi_boi_staff_id IS 'Nhân sự thực hiện thu hồi';
COMMENT ON COLUMN public.tep_ket_qua.thu_hoi_ly_do IS 'Lý do thu hồi (bắt buộc khi xac_nhan_trang_thai = THU_HOI)';

-- 5. Cập nhật v_viec_cskh: Chỉ tệp HOP_LE mới sinh việc CSKH (CHO_BAC_SI / KQ_CHUA_GUI)
-- Internal files (xac_nhan_trang_thai IS NULL) VẪN đi qua nhánh CHO_BAC_SI cũ từ service_order.
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
          WHERE (nd.lam_ben_ngoai OR nd.flow_group = 'ket_qua'::text)
            AND o.exec_status <> ALL (ARRAY['draft'::text, 'cancelled'::text])
            AND o.ket_qua_luc IS NOT NULL AND o.duyet_luc IS NULL
            AND NOT (EXISTS ( SELECT 1
                   FROM tep_ket_qua k
                  WHERE k.clinic_id = o.clinic_id AND k.service_order_id = o.id))
        UNION ALL
         SELECT o.clinic_id,
            vi.clinic_patient_id,
            'CHO_KQ_XN'::text AS text,
            3,
            COALESCE((f.due_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date,
                     (COALESCE(o.finished_at, o.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_1.so_ngay),
            vi.appointment_id
           FROM service_order o
             JOIN visit vi ON vi.visit_id = o.visit_id AND vi.clinic_id = o.clinic_id
             JOIN node_definition nd ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
             JOIN luat_cskh l_1 ON l_1.clinic_id = o.clinic_id AND l_1.loai_viec = 'CHO_KQ_XN'::text AND l_1.bat
             LEFT JOIN follow_up_case f ON f.clinic_id = o.clinic_id AND f.service_order_id = o.id AND f.status = 'OPEN'::text
          WHERE (nd.lam_ben_ngoai OR nd.flow_group = 'ket_qua'::text)
            AND o.exec_status = 'performed'::text
            AND o.ket_qua_luc IS NULL
            AND o.created_at > (now() - '60 days'::interval)
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
          WHERE n.trang_thai = 'CHO_GOI'::text AND (n.appointment_id IS NULL OR (EXISTS ( SELECT 1
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
        -- TỆP KẾT QUẢ ĐÃ ĐƯỢC BÁC SĨ CHO PHÉP GỬI (chỉ tệp HOP_LE external)
        SELECT k.clinic_id,
            k.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_kq.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_kq ON l_kq.clinic_id = k.clinic_id AND l_kq.loai_viec = 'KQ_CHUA_GUI'::text AND l_kq.bat
          WHERE k.xac_nhan_trang_thai = 'HOP_LE' AND k.gui_luc IS NULL AND k.cho_phep_gui_luc IS NOT NULL
        UNION ALL
        -- TỆP KẾT QUẢ ĐÃ XÁC NHẬN HỢP LỆ, CHỜ BÁC SĨ CHO PHÉP GỬI (external)
         SELECT k.clinic_id,
            k.clinic_patient_id,
            'CHO_BAC_SI'::text AS text,
            1,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_bs.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_bs ON l_bs.clinic_id = k.clinic_id AND l_bs.loai_viec = 'CHO_BAC_SI'::text AND l_bs.bat
          WHERE k.xac_nhan_trang_thai = 'HOP_LE' AND k.gui_luc IS NULL AND k.cho_phep_gui_luc IS NULL
        UNION ALL
        -- TỆP NỘI BỘ (xac_nhan_trang_thai IS NULL) CHỜ BÁC SĨ CHO PHÉP GỬI
         SELECT k.clinic_id,
            k.clinic_patient_id,
            'CHO_BAC_SI'::text AS text,
            1,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_bs.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_bs ON l_bs.clinic_id = k.clinic_id AND l_bs.loai_viec = 'CHO_BAC_SI'::text AND l_bs.bat
          WHERE k.xac_nhan_trang_thai IS NULL AND k.gui_luc IS NULL AND k.cho_phep_gui_luc IS NULL
        UNION ALL
        -- TỆP NỘI BỘ (xac_nhan_trang_thai IS NULL) ĐÃ BÁC SĨ CHO PHÉP, CHƯA GỬI
         SELECT k.clinic_id,
            k.clinic_patient_id,
            'KQ_CHUA_GUI'::text AS text,
            2,
            (k.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh'::text)::date + l_kq.so_ngay,
            k.appointment_id
           FROM tep_ket_qua k
             JOIN luat_cskh l_kq ON l_kq.clinic_id = k.clinic_id AND l_kq.loai_viec = 'KQ_CHUA_GUI'::text AND l_kq.bat
          WHERE k.xac_nhan_trang_thai IS NULL AND k.gui_luc IS NULL AND k.cho_phep_gui_luc IS NOT NULL
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
