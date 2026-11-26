-- Tuyền 26/11/2026: tách đơn vị cũ ghi kèm số ("hộp 60 viên", "hộp 25 que") thành
-- đơn vị tính MẸ "hộp" + khối đơn vị con ("1 hộp = 60 viên"). Chạy lại được (chỉ
-- đụng thuốc còn tên đơn vị có số).
--
-- Hai loại:
-- * Kho đếm HỘP thật (Kofio, Fluconazole, Que thử, Tadal extra): chỉ đổi chữ —
--   đơn vị tính + chữ trên lô thành "hộp", điền đơn vị con / số con. Số tồn giữ nguyên.
-- * Bảng quy đổi có "hộp = N" (Ecanix 60, Aktiv 30): lần NHẬP đã quy ra viên
--   ("Quy đổi 305 hộp × 60 = 18300") nhưng bán / chuyển quầy sau đó trừ theo HỘP
--   ("1 hộp 60 viên" trừ 1). Sổ đọc ra 18.227 "hộp" là vô lý. Sửa: trên từng lô, phần
--   số theo viên (dòng nhập "Quy đổi … × N" và dòng "Chuyển tồn đầu kỳ" chuyển nó)
--   chia N; phần còn lại giữ. Ghi bằng một dòng ADJUST trong sổ kho (sổ chỉ thêm,
--   không sửa lịch sử) → Ecanix kho 18.227 → 232 hộp, Aktiv kho 1.399 → 36 hộp; lô
--   quầy (3, 11) vốn đã là hộp, không đổi. Xoá dòng quy đổi "hộp" (hộp nay là đơn vị
--   tính). Giá bán 550.000đ / 410.000đ vốn là giá hộp, giữ.
-- Thuốc loại hai còn dòng chờ gán lô (số chờ tính theo đơn vị cũ) thì bỏ qua, báo
-- NOTICE — làm tay sau.

DO $$
DECLARE
    r record;
    lo record;
    v numeric;
    lech numeric;
BEGIN
    FOR r IN
        SELECT d.id, d.clinic_id, d.don_vi_ban AS cu, m[1] AS me, m[2]::int AS n,
               m[3] AS con
          FROM public.drug_catalog d,
               regexp_match(btrim(d.don_vi_ban), '^(\S+)\s+(\d+)\s+(\S+(?:\s+\S+)?)$') m
         WHERE m IS NOT NULL AND m[2]::int > 0
         ORDER BY d.id
           FOR UPDATE OF d
    LOOP
        IF EXISTS (
            SELECT 1 FROM public.thuoc_quy_doi q
             WHERE q.clinic_id = r.clinic_id AND q.drug_catalog_id = r.id
               AND public.chuan_don_vi(q.don_vi) = public.chuan_don_vi(r.me)
               AND q.he_so = r.n
        ) THEN
            IF EXISTS (
                SELECT 1 FROM public.thuoc_giao_chua_gan_lo g
                 WHERE g.clinic_id = r.clinic_id AND g.drug_catalog_id = r.id
                   AND g.drug_batch_id IS NULL AND g.huy_luc IS NULL
            ) THEN
                RAISE NOTICE 'Bỏ qua % (%): còn dòng chờ gán lô', r.id, r.cu;
                CONTINUE;
            END IF;
            FOR lo IN
                SELECT b.id, b.quantity_on_hand FROM public.drug_batch b
                 WHERE b.clinic_id = r.clinic_id AND b.drug_catalog_id = r.id
                 ORDER BY b.id FOR UPDATE
            LOOP
                SELECT coalesce(sum(t.quantity), 0) INTO v FROM public.inventory_txn t
                 WHERE t.clinic_id = r.clinic_id AND t.drug_batch_id = lo.id
                   AND ((t.txn_type = 'RECEIVE'
                         AND t.reason ~ ('Quy đổi .* × ' || r.n || ' ='))
                        OR t.reason LIKE 'Chuyển tồn đầu kỳ%');
                lech := round(v / r.n, 3) - v;
                IF lech <> 0 THEN
                    INSERT INTO public.inventory_txn
                        (clinic_id, drug_batch_id, txn_type, quantity, reason,
                         ref_type, ref_id, performed_at)
                    VALUES (r.clinic_id, lo.id, 'ADJUST', lech,
                            format('Đổi đơn vị tính “%s” → “%s”: phần nhập theo %s '
                                   '(%s) quy về %s %s', r.cu, r.me, r.con,
                                   trim_scale(v), trim_scale(round(v / r.n, 3)), r.me),
                            'doi_don_vi_tinh', r.id, now());
                END IF;
            END LOOP;
            DELETE FROM public.thuoc_quy_doi q
             WHERE q.clinic_id = r.clinic_id AND q.drug_catalog_id = r.id
               AND public.chuan_don_vi(q.don_vi) = public.chuan_don_vi(r.me);
        END IF;
        UPDATE public.drug_batch SET unit = r.me, updated_at = now()
         WHERE clinic_id = r.clinic_id AND drug_catalog_id = r.id
           AND public.chuan_don_vi(unit) = public.chuan_don_vi(r.cu);
        UPDATE public.drug_catalog
           SET don_vi_ban = r.me,
               don_vi_con = coalesce(don_vi_con, r.con),
               so_lieu_moi_don_vi_goc = coalesce(so_lieu_moi_don_vi_goc, r.n)
         WHERE id = r.id;
    END LOOP;
END
$$;
