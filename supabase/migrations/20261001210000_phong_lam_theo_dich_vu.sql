-- PHÒNG LÀM THEO DỊCH VỤ (Tuyền chốt 30/09/2026).
--
-- Định tuyến chỉ định → phòng đi theo NODE: `service_price.node_code` → phòng
-- có node ấy (`clinic_room_node`). Node thô: DICHVU-THUTHUAT gom ~45 dịch vụ,
-- nên Ghế điện từ trường / Tập máy Bio xếp được vào 4 phòng (Thủ thuật 1, 2,
-- Sàn chậu, Sản - Biofeedback) trong khi máy chỉ đặt ở Phòng Sàn chậu.
--
-- KHÔNG đổi node_code của dịch vụ (node còn dùng cho mẫu kết quả, theo dõi thủ
-- thuật, quyền…). Thêm một lớp THU HẸP theo dịch vụ:
--
--   * dịch vụ CÓ dòng trong `clinic_room_service` → CHỈ các phòng được gắn làm
--     được (vẫn phải cùng cơ sở, đang mở, nhận khách — người gọi lọc tiếp);
--   * dịch vụ KHÔNG có dòng nào → như cũ, theo node.
--
-- Luật nằm ở MỘT hàm `phong_lam_duoc(clinic, room, node, service)`: mọi chỗ
-- tính "phòng làm được chỉ định này" (gợi ý phòng, dây H4 tự xếp, lệnh xếp tay,
-- hàng "chờ nhận" của phòng, trưởng ca, cảnh báo cấu hình) gọi hàm này thay vì
-- tự JOIN clinic_room_node — sửa luật một chỗ là đủ.
--
-- Kèm (bổ sung 01/10, danh sách 93 dịch vụ đang bán của Tuyền — đối chiếu
-- ma_kiotviet thiếu đúng 2 mã):
--   * SP000083 "Vật lý trị liệu" 500.000đ — KiotViet xếp nhóm "Phí khám" nhưng
--     là việc làm ở phòng → DỊCH VỤ node DICHVU-THUTHUAT, chỉ Phòng Sàn chậu.
--   * SP000077 "Tư vấn KQ XN cũ" — phí khám, theo khuôn 20260928000100
--     (service_price nhóm dịch vụ không node + `loai_kham_phi`), chọn được ở MỌI
--     loại khám đang bật. KiotViet ghi 0đ → giá để TRỐNG ("chưa có giá", quầy
--     chặn, quản lý điền ở Bảng giá) như SP000112 — luật 20260926000001: không
--     bao giờ nạp 0đ, nạp 0 là thu 0 đồng. Miễn phí thật thì quản lý đặt 0đ.
--
-- Chạy lại được. Tra phòng theo `code` (KN-SANCHAU), dịch vụ theo mã — không
-- theo tên (tên phòng đang được đổi ở nhánh khác).

-- ── 1. Bảng phòng ↔ dịch vụ ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.clinic_room_service (
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    room_id      uuid NOT NULL REFERENCES public.clinic_room(id) ON DELETE CASCADE,
    service_code text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    created_by   uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    PRIMARY KEY (room_id, service_code)
);
-- KHÔNG khoá ngoại tới service_price: bảng giá chỉ có chỉ mục duy nhất
-- (clinic_id, "group", service_code), và migration 20260730000003 xoá / dựng lại
-- chỉ mục ấy — khoá ngoại bám vào nó làm migration cũ hết chạy lại được. Kiểm
-- mã dịch vụ bằng trigger bên dưới (bảng giá tắt chứ không xoá dòng).

COMMENT ON TABLE public.clinic_room_service IS
'Phòng làm dịch vụ nào — lớp THU HẸP trên clinic_room_node (30/09/2026). Dịch vụ có dòng ở đây thì CHỈ các phòng được gắn làm được; không có dòng nào thì theo node như cũ. Luật ở hàm phong_lam_duoc().';

CREATE INDEX IF NOT EXISTS idx_clinic_room_service_dich_vu
    ON public.clinic_room_service (clinic_id, service_code);

-- Phòng và dịch vụ phải cùng phòng khám; mã phải là DỊCH VỤ trong bảng giá.
CREATE OR REPLACE FUNCTION public.clinic_room_service_cung_phong_kham()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.clinic_room r
                    WHERE r.id = NEW.room_id AND r.clinic_id = NEW.clinic_id) THEN
        RAISE EXCEPTION 'Phòng % không thuộc phòng khám này', NEW.room_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.service_price sp
                    WHERE sp.clinic_id = NEW.clinic_id AND sp."group" = 'dich_vu'
                      AND sp.service_code = NEW.service_code) THEN
        RAISE EXCEPTION 'Không có dịch vụ % trong bảng giá', NEW.service_code
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_clinic_room_service_cung_phong_kham
    ON public.clinic_room_service;
CREATE TRIGGER trg_clinic_room_service_cung_phong_kham
    BEFORE INSERT OR UPDATE ON public.clinic_room_service
    FOR EACH ROW EXECUTE FUNCTION public.clinic_room_service_cung_phong_kham();

-- RLS theo mẫu clinic_room_node: đọc trong phòng khám của mình, KHÔNG ghi từ
-- trình duyệt (20260804000016) — ghi chỉ qua API cấu hình.
ALTER TABLE public.clinic_room_service ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS clinic_room_service_select ON public.clinic_room_service;
CREATE POLICY clinic_room_service_select ON public.clinic_room_service
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));
GRANT SELECT ON public.clinic_room_service TO authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.clinic_room_service FROM authenticated;

-- ── 2. MỘT luật: phòng này làm được chỉ định (node, dịch vụ) này không ──────
-- Chỉ trả lời "phòng có được GẮN việc này không". Đang mở / nhận khách / cùng
-- cơ sở / phòng đối tác: người gọi tự lọc (mỗi chỗ một ngữ cảnh).
-- LANGUAGE sql không SET search_path để Postgres nhúng thẳng vào truy vấn gọi.
CREATE OR REPLACE FUNCTION public.phong_lam_duoc(
    p_clinic_id uuid, p_room_id uuid, p_node_code text, p_service_code text)
RETURNS boolean
LANGUAGE sql
STABLE
AS $fn$
    SELECT CASE
        WHEN p_service_code IS NOT NULL AND EXISTS (
                SELECT 1 FROM public.clinic_room_service s
                 WHERE s.clinic_id = p_clinic_id
                   AND s.service_code = p_service_code)
        THEN EXISTS (
                SELECT 1 FROM public.clinic_room_service s
                 WHERE s.clinic_id = p_clinic_id AND s.room_id = p_room_id
                   AND s.service_code = p_service_code)
        ELSE EXISTS (
                SELECT 1 FROM public.clinic_room_node rn
                 WHERE rn.clinic_id = p_clinic_id AND rn.room_id = p_room_id
                   AND rn.node_code = p_node_code)
    END
$fn$;

COMMENT ON FUNCTION public.phong_lam_duoc(uuid, uuid, text, text) IS
'Phòng làm được chỉ định (node, dịch vụ)? Dịch vụ có dòng clinic_room_service → chỉ phòng được gắn; không → theo clinic_room_node. MỘT luật cho mọi chỗ xếp phòng (30/09/2026).';

-- ── 3. Nạp: Sàn chậu + hai mã KiotViet còn thiếu ────────────────────────────
CREATE OR REPLACE FUNCTION public.nap_phong_lam_theo_dich_vu()
RETURNS TABLE (dich_vu_moi integer, loai_kham_gan integer, phong_gan integer)
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
    n_dv integer := 0;
    n_lk integer := 0;
    n_ph integer := 0;
BEGIN
    -- SP000083 Vật lý trị liệu (dịch vụ ở phòng) · SP000077 Tư vấn KQ XN cũ
    -- (phí khám). Chỉ phòng khám đang dùng mã KiotViet; đã có mã thì thôi.
    INSERT INTO public.service_price
        (clinic_id, service_code, name, "group", unit_price, active, category,
         node_code, ma_kiotviet, billing_owner)
    SELECT c.id, v.ma_noi_bo, v.ten, 'dich_vu', v.gia, true, v.nhom, v.node,
           v.ma_kv, 'CLINIC'
      FROM public.clinic c
     CROSS JOIN (VALUES
           ('KV_SP000083', 'Vật lý trị liệu', 500000::numeric,
            'KiotViet 21/09/2026', 'DICHVU-THUTHUAT', 'SP000083'),
           ('KV_SP000077', 'Tư vấn KQ XN cũ', NULL::numeric,
            'Phí khám · KiotViet · CHƯA CÓ GIÁ — quản lý điền ở Bảng giá',
            NULL::text, 'SP000077')
         ) AS v(ma_noi_bo, ten, gia, nhom, node, ma_kv)
     WHERE EXISTS (SELECT 1 FROM public.service_price p
                    WHERE p.clinic_id = c.id AND p.ma_kiotviet IS NOT NULL)
       AND NOT EXISTS (SELECT 1 FROM public.service_price q
                        WHERE q.clinic_id = c.id AND q.ma_kiotviet = v.ma_kv)
    ON CONFLICT (clinic_id, "group", service_code) DO NOTHING;
    GET DIAGNOSTICS n_dv = ROW_COUNT;

    -- Tư vấn KQ XN cũ chọn được ở mọi loại khám đang bật (cuối danh sách).
    INSERT INTO public.loai_kham_phi
        (clinic_id, service_type_id, service_price_id, thu_tu)
    SELECT st.clinic_id, st.id, sp.id, 99
      FROM public.service_type st
      JOIN public.service_price sp
        ON sp.clinic_id = st.clinic_id AND sp.ma_kiotviet = 'SP000077'
       AND sp.active
     WHERE st.is_active
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n_lk = ROW_COUNT;

    -- Ghế điện từ trường, Tập máy Bio (+ đo trương lực cơ bằng máy Bio), Vật lý
    -- trị liệu: CHỈ Phòng Sàn chậu (mã phòng KN-SANCHAU, chỉ khi tồn tại).
    INSERT INTO public.clinic_room_service (clinic_id, room_id, service_code)
    SELECT r.clinic_id, r.id, sp.service_code
      FROM public.clinic_room r
      JOIN public.service_price sp
        ON sp.clinic_id = r.clinic_id AND sp."group" = 'dich_vu'
       AND (sp.service_code IN ('CLS_GHE_DTT', 'CLS_GHE_DTT_DAU_CO',
                                'CLS_GHE_DTT_YEU_CO', 'CLS_BIOFEEDBACK',
                                'CLS_BIOFEEDBACK_CO_BAN',
                                'CLS_BIOFEEDBACK_NANG_CAO',
                                'CLS_DO_CO_LUC_AM_DAO')
            OR sp.ma_kiotviet = 'SP000083')
     WHERE r.code = 'KN-SANCHAU'
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n_ph = ROW_COUNT;

    RETURN QUERY SELECT n_dv, n_lk, n_ph;
END
$fn$;

DO $$
BEGIN
    PERFORM public.nap_phong_lam_theo_dich_vu();
END
$$;
