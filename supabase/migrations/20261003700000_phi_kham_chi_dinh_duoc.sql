-- PHÍ KHÁM CŨNG CHỈ ĐỊNH ĐƯỢC + MỞ HẾT PHÒNG (Tuyền 02/10/2026, C21).
--
-- Tuyền: "toàn bộ 93 dịch vụ từ file Excel khách gửi phải chọn được, hiện đủ ở
-- bàn khám chỗ chọn chỉ định … vào Bảng giá dịch vụ & phòng có cái không chọn
-- phòng được … tôi đã nói mở full hết tất cả các phòng … toàn bộ phải được dùng
-- hết".
--
-- Đo prod 02/10 (ade2f732): 85/93 dịch vụ Excel chỉ định được, đủ 12 phòng.
-- THIẾU ĐÚNG 8 = nhóm "Phí khám" chưa có nhóm việc (KHAM_SAN_1, KV_SP000119,
-- KV_SP000112, KV_SP000077, KHAM_NAM_KHOA, KHAM_PHU_KHOA, KHAM_HIEM_MUON,
-- KHAM_HIEM_MUON_TAI_KHAM). Ba luật chồng nhau loại chúng:
--   1. `danh_muc_dich_vu.la_phi_kham` (không nhóm việc + nhóm Phí khám / mã
--      KHAM_* / thuộc loại khám) bị dùng làm BỘ LỌC: danh mục chỉ định phiếu
--      khám, ô "Chỉ định thêm" của Bàn khám, và `can_phong = NOT la_phi_kham`
--      → Bảng giá ẩn ô nhóm việc + ô phòng ("—").
--   2. Chỉ định đòi nhóm việc (`_services` → SERVICE_NOT_MAPPED); "Làm việc
--      gì" của phòng chỉ liệt kê dịch vụ có nhóm việc.
--   3. Script "mở hết phòng" 01/10 (`mo-het-phong-0110b.sql`) ghi rõ "mọi
--      dịch vụ TRỪ phí khám".
--
-- SỬA (chỉ THÊM, không xoá gì; dịch vụ khám tick theo loại khám giữ nguyên —
-- `loai_kham_phi` / `luot_phi_kham` không đụng):
--   a. Phí khám chưa có nhóm việc → nhóm việc "Thực hiện thủ thuật (nhóm)"
--      (DICHVU-THUTHUAT) — đúng tiền lệ Tư vấn phụ khoa chuyên sâu / Vật lý trị
--      liệu (Excel xếp nhóm Phí khám, đã chỉ định được + có phòng từ 01/10).
--      Quản lý đổi nhóm việc tại chỗ ở Bảng giá.
--   b. Dịch vụ ấy làm được ở MỌI phòng đang bật (gán riêng, như 01/10).
--   c. `danh_muc_dich_vu.can_phong` không còn loại phí khám: phí khám nào sau
--      này thêm mà chưa có phòng → hiện "Chưa có phòng" + [Gán phòng], không
--      im lặng biến mất.
--   d. Đồng bộ danh mục chạy lại: nhóm hàng "Phí khám" → DICHVU-THUTHUAT khi
--      dịch vụ chưa có nhóm việc (lần sau nạp file không mở lại lỗ này).
-- Tiền khám không tính hai lần: chặn ở `phi_kham_service.chan_trung_dich_vu_kham`
-- (chỉ định lại dịch vụ đang tick ở "Dịch vụ khám", và ngược lại).

-- ── d. Nhóm hàng → nhóm việc: thêm Phí khám ────────────────────────────────
CREATE OR REPLACE FUNCTION public.nhom_viec_theo_nhom_hang(p_nhom text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT CASE
        WHEN p_nhom LIKE 'Siêu âm%' THEN 'DICHVU-SIEUAM'
        -- Phí khám (02/10/2026): chỉ định được như dịch vụ ở phòng.
        WHEN p_nhom IN ('Thủ thuật', 'Dịch vụ khác', 'Phí khám') THEN 'DICHVU-THUTHUAT'
        -- XN thu hộ: phòng = nơi LẤY MẪU (gợi ý — quản lý chỉnh được).
        WHEN p_nhom IN ('XN thu hộ', 'Xét nghiệm') THEN 'DICHVU-LAYMAU-MAU'
        ELSE NULL
    END
$fn$;

-- ── c. Một chỗ đọc danh mục: cần phòng không còn trừ phí khám ───────────────
CREATE OR REPLACE FUNCTION public.danh_muc_dich_vu(p_clinic_id uuid)
RETURNS TABLE (
    id uuid, service_code text, name text, nhom text, unit_price numeric,
    active boolean, billing_owner text, billing_owner_chon_tay boolean,
    node_code text, ten_nhom_viec text, ma_kiotviet text, gia_tam boolean,
    la_phi_kham boolean, can_phong boolean, gan_rieng boolean, phong jsonb,
    chua_co_phong boolean)
LANGUAGE sql
STABLE
AS $fn$
    SELECT sp.id, sp.service_code, sp.name, sp.category, sp.unit_price,
           sp.active, sp.billing_owner, sp.billing_owner_chon_tay,
           sp.node_code, n.name, sp.ma_kiotviet, sp.gia_tam,
           pk.la, cp.can,
           EXISTS (SELECT 1 FROM public.clinic_room_service s
                    WHERE s.clinic_id = sp.clinic_id
                      AND s.service_code = sp.service_code),
           coalesce((
               SELECT jsonb_agg(jsonb_build_object(
                          'id', r.id, 'ten', coalesce(r.name, r.code),
                          'doi_tac', r.la_doi_tac) ORDER BY r.sort, r.code)
                 FROM public.clinic_room r
                WHERE r.clinic_id = sp.clinic_id AND r.is_active
                  AND public.phong_lam_duoc(r.clinic_id, r.id, sp.node_code,
                                            sp.service_code)), '[]'::jsonb),
           sp.active AND cp.can AND NOT EXISTS (
               SELECT 1 FROM public.clinic_room r
                WHERE r.clinic_id = sp.clinic_id AND r.is_active
                  AND NOT r.la_doi_tac
                  AND public.phong_lam_duoc(r.clinic_id, r.id, sp.node_code,
                                            sp.service_code))
      FROM public.service_price sp
      LEFT JOIN public.node_definition n
        ON n.clinic_id = sp.clinic_id AND n.code = sp.node_code
     CROSS JOIN LATERAL (
         SELECT sp.node_code IS NULL AND (
                    coalesce(sp.category, '') LIKE 'Phí khám%'
                    OR coalesce(sp.category, '') LIKE 'Tiền khám%'
                    OR sp.service_code LIKE 'KHAM\_%'
                    OR EXISTS (SELECT 1 FROM public.loai_kham_phi l
                                WHERE l.service_price_id = sp.id)) AS la) pk
     CROSS JOIN LATERAL (
         SELECT NOT (sp.doi_tac_lay_mau OR coalesce(n.lam_ben_ngoai, false))
                AS can) cp
     WHERE sp.clinic_id = p_clinic_id AND sp."group" = 'dich_vu'
$fn$;

COMMENT ON FUNCTION public.danh_muc_dich_vu(uuid) IS
'Danh mục dịch vụ + phòng làm được (01/10/2026; 02/10: phí khám cũng cần phòng, chỉ định được): la_phi_kham chỉ là NHÃN (phí khám chưa nhóm việc), không lọc. MỘT chỗ cho danh mục chỉ định, Bảng giá dịch vụ & phòng, cảnh báo trang chủ.';

-- ── a + b. Phí khám chưa nhóm việc → nhóm việc + mọi phòng đang bật ─────────
DO $$
DECLARE
    n_nhom integer;
    n_phong integer;
BEGIN
    CREATE TEMP TABLE _phi_kham_mo ON COMMIT DROP AS
    SELECT d.id, c.id AS clinic_id, d.service_code
      FROM public.clinic c
     CROSS JOIN LATERAL public.danh_muc_dich_vu(c.id) d
     WHERE d.active AND d.la_phi_kham
       AND EXISTS (SELECT 1 FROM public.node_definition n
                    WHERE n.clinic_id = c.id AND n.is_active
                      AND n.code = 'DICHVU-THUTHUAT');

    UPDATE public.service_price sp
       SET node_code = 'DICHVU-THUTHUAT', updated_at = now()
      FROM _phi_kham_mo m
     WHERE sp.id = m.id AND sp.node_code IS NULL;
    GET DIAGNOSTICS n_nhom = ROW_COUNT;

    INSERT INTO public.clinic_room_service (clinic_id, room_id, service_code)
    SELECT m.clinic_id, r.id, m.service_code
      FROM _phi_kham_mo m
      JOIN public.clinic_room r ON r.clinic_id = m.clinic_id AND r.is_active
    ON CONFLICT (room_id, service_code) DO NOTHING;
    GET DIAGNOSTICS n_phong = ROW_COUNT;

    RAISE NOTICE 'Phí khám mở chỉ định: % dịch vụ gắn nhóm việc · % cặp phòng',
        n_nhom, n_phong;
END
$$;
