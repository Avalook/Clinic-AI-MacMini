-- Mua / không mua / mua một phần (migration 20260807000004).
--
-- Kiểm HÀNH VI của lược đồ, không kiểm hình dạng SQL: trạng thái cấp phát có
-- tự đúng với số liệu không, có cấp quá số kê được không, có cấp mà không để
-- lại dấu vết được không, và sổ kho có khớp tồn không.
--
-- Mọi thứ rollback.

BEGIN;

DO $$
DECLARE
    v_clinic uuid := (SELECT id FROM public.clinic ORDER BY id LIMIT 1);
    v_loc    uuid := (SELECT id FROM public.clinic_location ORDER BY id LIMIT 1);
    -- `staff` KHÔNG có cột clinic_id (nhân sự nối vào phòng khám qua
    -- clinic_membership) — lấy bừa một người, bài kiểm này không xét vai.
    v_staff  uuid := (SELECT id FROM public.staff ORDER BY id LIMIT 1);
    v_bn     uuid;
    v_thuoc  uuid;
    v_lo     uuid;
    v_don    uuid;
    v_tt     text;
    v_ton    numeric;
BEGIN
    IF v_clinic IS NULL OR v_loc IS NULL THEN
        RAISE EXCEPTION 'Không dựng được dữ liệu kiểm (clinic=% loc=%)',
            v_clinic, v_loc;
    END IF;
    IF v_staff IS NULL THEN
        -- `inventory_txn_manual_needs_actor` đòi người thực hiện với dòng
        -- 'manual'. Không có nhân sự nào thì bài kiểm không dựng được — nói
        -- thẳng, đừng tự bỏ qua.
        INSERT INTO public.staff (full_name, short_name, primary_department,
                                  employment_type, is_active)
        VALUES ('Dược sĩ kiểm thử', 'DSKT', 'PHARMACIST', 'FULL_TIME', TRUE)
        RETURNING id INTO v_staff;
    END IF;

    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    VALUES ('BN-KIEMTHU-THUOC', 'Kiểm thử cấp thuốc', v_loc, v_clinic)
    RETURNING clinic_patient_id INTO v_bn;

    INSERT INTO public.drug_catalog (name_base, name_raw, clinic_id)
    VALUES ('Kiểm thử', 'Thuốc kiểm thử 500mg', v_clinic)
    RETURNING id INTO v_thuoc;

    INSERT INTO public.drug_batch
        (clinic_id, drug_catalog_id, batch_code, expiry_date,
         quantity_on_hand, unit, received_at)
    VALUES (v_clinic, v_thuoc, 'LO-KIEMTHU-001',
            current_date + 365, 0, 'viên', now())
    RETURNING id INTO v_lo;

    -- ── ① NHẬP KHO: tồn phải do TRIGGER cộng, không ai ghi tay ─────────────
    INSERT INTO public.inventory_txn
        (clinic_id, drug_batch_id, txn_type, quantity, ref_type,
         performed_by_staff_id, performed_at)
    VALUES (v_clinic, v_lo, 'RECEIVE', 100, 'manual', v_staff, now());

    SELECT quantity_on_hand INTO v_ton FROM public.drug_batch WHERE id = v_lo;
    IF v_ton <> 100 THEN
        RAISE EXCEPTION 'Nhập 100 mà tồn là % — trigger cộng dồn không chạy', v_ton;
    END IF;

    -- ── ② ĐƠN THUỐC: số lượng đọc được từ câu bác sĩ gõ ───────────────────
    INSERT INTO public.prescription
        (source_ref, clinic_patient_id, drug_name_raw, quantity, quantity_num,
         unit, clinic_id)
    VALUES ('kiemthu-1', v_bn, 'Thuốc kiểm thử 500mg', '10 viên',
            public.so_luong_tu_van_ban('10 viên'),
            public.don_vi_tu_van_ban('10 viên'), v_clinic)
    RETURNING id INTO v_don;

    SELECT quantity_num INTO v_ton FROM public.prescription WHERE id = v_don;
    IF v_ton <> 10 THEN
        RAISE EXCEPTION 'Đọc "10 viên" ra % thay vì 10', v_ton;
    END IF;

    SELECT dispense_status INTO v_tt FROM public.prescription WHERE id = v_don;
    IF v_tt <> 'CHUA_CAP' THEN
        RAISE EXCEPTION 'Đơn mới kê phải là CHUA_CAP, đang là %', v_tt;
    END IF;

    -- ── ③ CẤP MỘT PHẦN: 4 trên 10 ─────────────────────────────────────────
    INSERT INTO public.inventory_txn
        (clinic_id, drug_batch_id, txn_type, quantity, ref_type, ref_id,
         performed_by_staff_id, performed_at)
    VALUES (v_clinic, v_lo, 'DISPENSE', -4, 'prescription', v_don, v_staff, now());

    UPDATE public.prescription
       SET dispensed_qty = dispensed_qty + 4,
           dispensed_at = now(), dispensed_by_staff_id = v_staff
     WHERE id = v_don;

    SELECT dispense_status INTO v_tt FROM public.prescription WHERE id = v_don;
    IF v_tt <> 'CAP_MOT_PHAN' THEN
        RAISE EXCEPTION 'Cấp 4/10 phải là CAP_MOT_PHAN, đang là %', v_tt;
    END IF;

    SELECT quantity_on_hand INTO v_ton FROM public.drug_batch WHERE id = v_lo;
    IF v_ton <> 96 THEN
        RAISE EXCEPTION 'Cấp 4 mà tồn là % thay vì 96', v_ton;
    END IF;

    -- ── ④ CẤP NỐT: 6 nữa là đủ 10 ─────────────────────────────────────────
    UPDATE public.prescription SET dispensed_qty = dispensed_qty + 6
     WHERE id = v_don;

    SELECT dispense_status INTO v_tt FROM public.prescription WHERE id = v_don;
    IF v_tt <> 'CAP_DU' THEN
        RAISE EXCEPTION 'Cấp đủ 10/10 phải là CAP_DU, đang là %', v_tt;
    END IF;

    -- ── ⑤ KHÔNG CẤP QUÁ SỐ KÊ ─────────────────────────────────────────────
    BEGIN
        UPDATE public.prescription SET dispensed_qty = dispensed_qty + 1
         WHERE id = v_don;
        RAISE EXCEPTION 'Cấp 11/10 KHÔNG bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;   -- đúng
    END;

    -- ── ⑥ CẤP MÀ KHÔNG ĐỂ LẠI DẤU VẾT: phải bị chặn ───────────────────────
    -- Ràng buộc hai chiều: đã cấp ⇔ biết ai cấp và lúc nào.
    BEGIN
        UPDATE public.prescription
           SET dispensed_by_staff_id = NULL WHERE id = v_don;
        RAISE EXCEPTION 'Xoá người cấp KHÔNG bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;   -- đúng
    END;

    -- ── ⑦ KHÔNG MUA: từ chối, có lý do ────────────────────────────────────
    INSERT INTO public.prescription
        (source_ref, clinic_patient_id, drug_name_raw, quantity, quantity_num,
         clinic_id, refusal_reason, closed_at)
    VALUES ('kiemthu-2', v_bn, 'Thuốc kiểm thử khác', '5 viên', 5, v_clinic,
            'Khách nói đã có thuốc ở nhà', now())
    RETURNING id INTO v_don;

    SELECT dispense_status INTO v_tt FROM public.prescription WHERE id = v_don;
    IF v_tt <> 'TU_CHOI' THEN
        RAISE EXCEPTION 'Khách không mua phải là TU_CHOI, đang là %', v_tt;
    END IF;

    -- ── ⑧ TỒN KHÔNG XUỐNG ÂM ──────────────────────────────────────────────
    BEGIN
        INSERT INTO public.inventory_txn
            (clinic_id, drug_batch_id, txn_type, quantity, ref_type,
             performed_by_staff_id, performed_at)
        VALUES (v_clinic, v_lo, 'DISPENSE', -1000, 'manual', v_staff, now());
        RAISE EXCEPTION 'Cấp quá tồn KHÔNG bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;   -- đúng
    END;

    -- ── ⑨ SỔ KHO KHÔNG SỬA ĐƯỢC ───────────────────────────────────────────
    BEGIN
        UPDATE public.inventory_txn SET quantity = 1
         WHERE drug_batch_id = v_lo;
        RAISE EXCEPTION 'Sửa được sổ kho — lẽ ra phải chỉ-thêm';
    EXCEPTION WHEN insufficient_privilege THEN NULL;   -- đúng
    END;

    -- ── ⑩ SỔ KHỚP TỒN ─────────────────────────────────────────────────────
    -- Số dư là thứ dẫn xuất; nếu nó không bằng tổng sổ thì có ai đó ghi tay.
    SELECT quantity_on_hand INTO v_ton FROM public.drug_batch WHERE id = v_lo;
    IF v_ton <> (SELECT sum(quantity) FROM public.inventory_txn
                  WHERE drug_batch_id = v_lo) THEN
        RAISE EXCEPTION 'Tồn (%) không bằng tổng sổ (%)',
            v_ton, (SELECT sum(quantity) FROM public.inventory_txn
                     WHERE drug_batch_id = v_lo);
    END IF;

    RAISE NOTICE 'cap_phat_thuoc_mot_phan: tất cả khẳng định đều đạt';
END $$;

ROLLBACK;
