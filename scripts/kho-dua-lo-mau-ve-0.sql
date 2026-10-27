-- ĐƯA LÔ MẪU DEMO1709-* VỀ 0 bằng ĐIỀU CHỈNH (ADJUST) — KHÔNG xoá lô, KHÔNG xoá sổ.
--
-- Vì sao: prod chỉ có lô mẫu (không phải tồn thật). Từ khi giao thuốc tự chọn lô
-- (PR "giao thuốc tự chọn lô hết hạn sớm nhất"), máy sẽ trừ vào lô mẫu nếu còn.
-- Dọn về 0 TRƯỚC khi nạp tồn thật; nạp tồn thật bằng "Nhập thuốc" theo đúng đơn vị bán.
--
--   thử khô (không ghi gì):  ... psql -v ON_ERROR_STOP=1 -v ket_thuc=ROLLBACK -U postgres -d postgres < scripts/kho-dua-lo-mau-ve-0.sql
--   chạy thật:               ... psql -v ON_ERROR_STOP=1 -v ket_thuc=COMMIT   -U postgres -d postgres < scripts/kho-dua-lo-mau-ve-0.sql
--
-- Không truyền ket_thuc thì psql báo lỗi cú pháp ở dòng cuối và KHÔNG ghi gì.
-- Chạy lại lần hai: không còn lô nào > 0 nên không ghi thêm dòng nào.
-- Lùi: scripts/kho-hoan-tac-lo-mau-ve-0.sql (cộng lại đúng số đã bớt, cũng bằng ADJUST).
--
-- DỪNG (không ghi gì) nếu có lô mẫu đang bị GIỮ cho một đơn (phân lô chưa thả) hoặc
-- đang có thuốc khách trả chờ kiểm — đó là việc thật, xử lý tay trước.
BEGIN;

-- Khoá các lô mẫu theo id tăng dần: không ai giao/điều chỉnh chen giữa chừng.
DO $$
BEGIN
    PERFORM 1 FROM public.drug_batch
     WHERE batch_code LIKE 'DEMO1709-%'
     ORDER BY id FOR UPDATE;
END $$;

-- Người ghi sổ: một Quản lý đang hoạt động của phòng khám (ràng buộc
-- inventory_txn_manual_needs_actor đòi dòng điều chỉnh tay phải có người làm).
-- Ưu tiên tài khoản 'Quản lý hệ thống' (việc do script làm, không đứng tên một người
-- thật chưa bấm gì); không có thì lấy theo tên. Tên hiện ở bảng tóm tắt cuối.
CREATE TEMP TABLE _nguoi ON COMMIT DROP AS
SELECT DISTINCT ON (m.clinic_id) m.clinic_id, m.staff_id, s.full_name
  FROM public.clinic_membership m
  JOIN public.staff s ON s.id = m.staff_id
 WHERE m.role = 'MANAGEMENT' AND m.is_active
 ORDER BY m.clinic_id, (s.full_name = 'Quản lý hệ thống') DESC, s.full_name, m.staff_id;

CREATE TEMP TABLE _lo ON COMMIT DROP AS
SELECT b.id, b.clinic_id, b.location_id, b.batch_code, b.unit,
       b.quantity_on_hand AS ton_truoc
  FROM public.drug_batch b
 WHERE b.batch_code LIKE 'DEMO1709-%' AND b.quantity_on_hand > 0;

-- Tồn các lô KHÔNG phải lô mẫu: phải y nguyên sau khi chạy.
CREATE TEMP TABLE _khac ON COMMIT DROP AS
SELECT coalesce(sum(quantity_on_hand), 0) AS tong, count(*) AS so_lo
  FROM public.drug_batch WHERE batch_code NOT LIKE 'DEMO1709-%';

DO $$
DECLARE n_giu bigint; n_tra bigint; n_khong_nguoi bigint;
BEGIN
    SELECT count(*) INTO n_khong_nguoi
      FROM _lo l LEFT JOIN _nguoi g ON g.clinic_id = l.clinic_id
     WHERE g.staff_id IS NULL;
    IF n_khong_nguoi > 0 THEN
        RAISE EXCEPTION 'Phòng khám chưa có Quản lý đang hoạt động để đứng tên điều chỉnh (% lô).', n_khong_nguoi;
    END IF;

    SELECT count(*) INTO n_giu
      FROM public.prescription_allocation a JOIN _lo l ON l.id = a.drug_batch_id
     WHERE a.released_at IS NULL;
    IF n_giu > 0 THEN
        RAISE EXCEPTION '% phân lô đang giữ lô mẫu cho một đơn — xử lý tay trước.', n_giu;
    END IF;

    SELECT count(*) INTO n_tra
      FROM public.drug_return r JOIN _lo l ON l.id = r.drug_batch_id
     WHERE r.disposition IS NULL;
    IF n_tra > 0 THEN
        RAISE EXCEPTION '% lần khách trả thuốc vào lô mẫu còn chờ kiểm — xử lý tay trước.', n_tra;
    END IF;
END $$;

INSERT INTO public.inventory_txn
    (clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type, ref_id,
     performed_by_staff_id, performed_at)
SELECT l.clinic_id, l.id, 'ADJUST', -l.ton_truoc,
       'Đưa lô mẫu DEMO1709 về 0 để nạp tồn thật (27/10/2026)',
       'manual', NULL, g.staff_id, now()
  FROM _lo l JOIN _nguoi g ON g.clinic_id = l.clinic_id;

-- Cùng nhật ký như điều chỉnh làm ở màn Kho (pharmacy.adjusted).
INSERT INTO public.event_log
    (clinic_id, event_type, aggregate_type, aggregate_id, payload, metadata,
     source, event_published)
SELECT l.clinic_id, 'pharmacy.adjusted', 'drug_batch', l.id,
       jsonb_build_object('quantity', (-l.ton_truoc)::text,
                          'reason', 'Đưa lô mẫu DEMO1709 về 0 để nạp tồn thật (27/10/2026)',
                          'quantity_on_hand', '0'),
       jsonb_build_object('clinic_staff_id', g.staff_id::text,
                          'nguon', 'scripts/kho-dua-lo-mau-ve-0.sql'),
       'script:kho-dua-lo-mau-ve-0', FALSE
  FROM _lo l JOIN _nguoi g ON g.clinic_id = l.clinic_id;

-- Kiểm trước khi chốt: lô mẫu hết sạch, lô khác không suy suyển, không tồn âm.
DO $$
DECLARE con_ton bigint; lech_khac bigint; am bigint;
BEGIN
    SELECT count(*) INTO con_ton FROM public.drug_batch
     WHERE batch_code LIKE 'DEMO1709-%' AND quantity_on_hand <> 0;
    IF con_ton > 0 THEN
        RAISE EXCEPTION 'Còn % lô mẫu chưa về 0 — huỷ.', con_ton;
    END IF;
    SELECT count(*) INTO lech_khac FROM _khac k
     WHERE k.tong <> (SELECT coalesce(sum(quantity_on_hand), 0) FROM public.drug_batch
                       WHERE batch_code NOT LIKE 'DEMO1709-%')
        OR k.so_lo <> (SELECT count(*) FROM public.drug_batch
                        WHERE batch_code NOT LIKE 'DEMO1709-%');
    IF lech_khac > 0 THEN
        RAISE EXCEPTION 'Tồn các lô KHÔNG phải lô mẫu bị đổi — huỷ.';
    END IF;
    SELECT count(*) INTO am FROM public.drug_batch WHERE quantity_on_hand < 0;
    IF am > 0 THEN
        RAISE EXCEPTION 'Có % lô tồn âm — huỷ.', am;
    END IF;
END $$;

-- Tóm tắt để người chạy đối chiếu bằng mắt.
SELECT coalesce(c.name, l.location_id::text) AS co_so,
       count(*) AS so_lo_ve_0, sum(l.ton_truoc) AS tong_da_bot,
       min(g.full_name) AS nguoi_ghi_so
  FROM _lo l
  JOIN _nguoi g ON g.clinic_id = l.clinic_id
  LEFT JOIN public.clinic_location c ON c.id = l.location_id
 GROUP BY 1 ORDER BY 1;

SELECT (SELECT count(*) FROM public.drug_batch WHERE batch_code LIKE 'DEMO1709-%') AS tong_lo_mau,
       (SELECT count(*) FROM public.drug_batch
         WHERE batch_code LIKE 'DEMO1709-%' AND quantity_on_hand = 0) AS lo_mau_da_ve_0,
       (SELECT so_lo FROM _khac) AS lo_khac_giu_nguyen,
       (SELECT tong FROM _khac) AS ton_lo_khac;

:ket_thuc;
