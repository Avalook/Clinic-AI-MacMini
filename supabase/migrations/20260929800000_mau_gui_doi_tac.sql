-- MẪU GỬI ĐỐI TÁC + CHỐT THU HỘ 10 DỊCH VỤ NGOÀI KIOTVIET (Tuyền 29/09/2026).
--
-- 1. LÝ DO NHẬN VIỆC MỚI `MAU_GUI_DOI_TAC`. Dịch vụ THU HỘ đối tác
--    (`service_price.billing_owner = 'EXTERNAL_PARTNER'`) mà phòng làm là phòng
--    CỦA PHÒNG KHÁM (node KHÔNG `lam_ben_ngoai` — vd Giải phẫu bệnh SP000092,
--    Sinh thiết CTC/âm hộ/âm đạo + GPB SP000075 làm ở DICHVU-THUTHUAT): phòng
--    bấm Xong → mẫu đã có, gửi sang đối tác → bên nhận `doi_tac_nhan_viec` ghi
--    một dòng lý do này. Trước đây việc ấy không bao giờ lên /doi-tac (bàn chỉ
--    nhận node `lam_ben_ngoai`), nên không có chỗ tích "Đã thu hộ cho đối tác"
--    và không có chỗ tải kết quả đối tác gửi về. Tổng quát theo (bên thu, phòng
--    làm) — KHÔNG viết cứng mã dịch vụ.
--
-- 2. BÙ DỮ LIỆU: việc như trên đã làm xong trong 60 ngày mà CHƯA có kết quả →
--    ghi nhận luôn (`BU_DU_LIEU`, như migration 20260925000009) để bàn đối tác
--    thấy mẫu đang chờ trả kết quả.
--
-- 3. CHỐT THU HỘ 10 dịch vụ KHÔNG có trong KiotViet (Tuyền xác nhận 29/09/2026
--    là ĐÚNG thu hộ): billing_owner = EXTERNAL_PARTNER + billing_owner_chon_tay
--    = true theo service_code, để việc suy-từ-phòng-làm về sau (Bảng giá đổi
--    phòng làm) không lật lại được. Mọi mã khác GIỮ NGUYÊN.
--
-- Chạy lại được: CHECK dựng lại cùng nội dung, bù dữ liệu ON CONFLICT DO NOTHING,
-- hàm chỉ chạm dòng còn lệch. DB DỰNG MỚI nạp danh mục (seed) SAU migration nên
-- `scripts/dev-up.sh` chạy lại file này sau seed (như 20260929000020).

-- 1 ------------------------------------------------------------------------
ALTER TABLE public.doi_tac_nhan_viec
    DROP CONSTRAINT IF EXISTS doi_tac_nhan_viec_ly_do_check;
ALTER TABLE public.doi_tac_nhan_viec
    ADD CONSTRAINT doi_tac_nhan_viec_ly_do_check
    CHECK (ly_do IN ('DA_THU_TIEN', 'KHACH_DA_CHON', 'DA_LAY_MAU',
                     'MAU_GUI_DOI_TAC', 'BU_DU_LIEU'));

COMMENT ON TABLE public.doi_tac_nhan_viec IS
'Việc đã sang bàn đối tác (khối Đối tác, nhận qua sự kiện): chỉ định làm bên '
'ngoài (node lam_ben_ngoai), hoặc dịch vụ thu hộ đối tác làm ở phòng của phòng '
'khám đã xong — mẫu gửi đối tác (ly_do MAU_GUI_DOI_TAC, 29/09/2026). Một chỉ '
'định tối đa một dòng (khoá chính) — nhận lại là không làm gì.';

-- 2 ------------------------------------------------------------------------
INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do, nhan_luc)
SELECT o.clinic_id, o.id, 'BU_DU_LIEU', coalesce(o.finished_at, o.created_at)
  FROM public.service_order o
  LEFT JOIN public.node_definition n
    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
  JOIN LATERAL (
       SELECT s.billing_owner FROM public.service_price s
        WHERE s.clinic_id = o.clinic_id AND s.service_code = o.service_code
          AND s.active
        ORDER BY (s."group" = 'dich_vu') DESC LIMIT 1) sp ON true
 WHERE o.created_at > now() - interval '60 days'
   AND o.exec_status = 'performed'
   AND o.ket_qua_luc IS NULL
   AND coalesce(o.selection_status, 'SELECTED') = 'SELECTED'
   AND NOT coalesce(n.lam_ben_ngoai, false)
   AND sp.billing_owner = 'EXTERNAL_PARTNER'
ON CONFLICT (clinic_id, service_order_id) DO NOTHING;

-- 3 ------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.chot_thu_ho_dich_vu_ngoai_kiotviet()
RETURNS integer
LANGUAGE sql
AS $$
    WITH doi AS (
        UPDATE public.service_price s
           SET billing_owner = 'EXTERNAL_PARTNER',
               billing_owner_chon_tay = true,
               updated_at = now()
         WHERE s."group" = 'dich_vu'
           AND s.service_code IN (
               'CLS_XET_NGHIEM_MAU',          -- Xét nghiệm máu
               'CLS_XN_NOI_TIET_NAM',         -- XN nội tiết nam
               'CLS_CFTR',                    -- CFTR
               'CLS_Y_MICRODELETION',         -- Mất đoạn nhỏ NST Y
               'CLS_KARYOTYPE',               -- Nhiễm sắc thể đồ
               'CLS_XET_NGHIEM_DICH_AM_DAO',  -- Xét nghiệm dịch âm đạo
               'CLS_NUOC_TIEU_SAU_XUAT_TINH', -- Nước tiểu sau xuất tinh
               'CLS_CHUP_VU_EP',              -- Chụp vú ép
               'CLS_CHUP_MRI_VU',             -- Chụp MRI vú
               'CLS_CHUP_TU_CUNG_VOI_TRUNG'   -- Chụp tử cung – vòi trứng
           )
           AND (s.billing_owner IS DISTINCT FROM 'EXTERNAL_PARTNER'
                OR NOT s.billing_owner_chon_tay)
        RETURNING 1)
    SELECT count(*)::integer FROM doi;
$$;

COMMENT ON FUNCTION public.chot_thu_ho_dich_vu_ngoai_kiotviet() IS
    'Tuyền 29/09/2026: 10 dịch vụ không có trong KiotViet (CLS_XET_NGHIEM_MAU, '
    'CLS_XN_NOI_TIET_NAM, CLS_CFTR, CLS_Y_MICRODELETION, CLS_KARYOTYPE, '
    'CLS_XET_NGHIEM_DICH_AM_DAO, CLS_NUOC_TIEU_SAU_XUAT_TINH, CLS_CHUP_VU_EP, '
    'CLS_CHUP_MRI_VU, CLS_CHUP_TU_CUNG_VOI_TRUNG) là THU HỘ đối tác — chốt '
    'EXTERNAL_PARTNER + chọn tay để suy-từ-phòng-làm không đổi được. Chỉ chạm '
    '10 mã ấy (mọi phòng khám), chạy lại được. Trả số dòng đã đổi.';

-- Hàm ghi dữ liệu: không mở cho PostgREST (/rest/v1/rpc) — chỉ migration/seed.
REVOKE ALL ON FUNCTION public.chot_thu_ho_dich_vu_ngoai_kiotviet() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION public.chot_thu_ho_dich_vu_ngoai_kiotviet()
            FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION public.chot_thu_ho_dich_vu_ngoai_kiotviet()
            FROM authenticated;
    END IF;
END $$;

SELECT public.chot_thu_ho_dich_vu_ngoai_kiotviet();

COMMENT ON COLUMN public.service_price.billing_owner IS
    'CLINIC = phòng khám thu; EXTERNAL_PARTNER = thu hộ đối tác (không cộng vào '
    'hoá đơn phòng khám). Thuộc TỪNG DỊCH VỤ — 29/09/2026: SP000092, SP000075 '
    'thu hộ đối tác; SP000025, SP000076 phòng khám thu (file KiotViet, nhóm '
    '"XN thu hộ"); 10 mã CLS_* ngoài KiotViet thu hộ đối tác (xem hàm '
    'chot_thu_ho_dich_vu_ngoai_kiotviet). Dịch vụ thu hộ làm ở phòng CỦA phòng '
    'khám: xong thì lên bàn đối tác (mẫu gửi đối tác).';
