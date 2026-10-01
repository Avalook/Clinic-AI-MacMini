-- DANH MỤC DỊCH VỤ CHUẨN 01/10/2026 + PHÒNG LÀM (Tuyền 01/10/2026).
--
-- Nguồn sự thật MỚI: "[Dr4women] Bảng giá dịch vụ trên Kiot 01.10.26 (Hà Nguyễn
-- gửi).xlsx" — 93 dịch vụ đang kinh doanh, cột Nhóm hàng / Tên / Thời lượng /
-- Giá bán / ĐVT. KHÔNG có cột mã → khớp theo TÊN CHUẨN HOÁ (thường, NFC, gộp
-- khoảng trắng), cộng bảng ánh xạ tay cho tên đã đổi (TPC → Tropocel SP000140,
-- RG → Regenlab SP000136). Tuyền: "đây là chuẩn; lần trước giao sai, danh sách
-- chỉ định đang thiếu rất nhiều; KHÔNG được để dịch vụ nào bị lọt; cái nào XN
-- thu hộ thì hiện đúng giá khách gửi, 0đ cũng hiện".
--
-- Đối chiếu prod trước khi viết (SELECT 01/10): 91/93 khớp tên, 2 đổi tên
-- (PRP), 14 lệch giá (12 XN thu hộ: Excel 0đ, prod TRỐNG hoặc giá cũ HPV 900k /
-- ThinPrep 650k / PCR 1,1tr; 2 phí khám 0đ). Mọi dịch vụ đang bán đã có phòng.
--
-- LÀM GÌ (hàm `dong_bo_danh_muc_dich_vu`, chạy lại được, lần 2 không đổi gì):
--   1. Bảng nguồn `danh_muc_dich_vu_nguon` giữ nguyên 93 dòng Excel (cả thời
--      lượng, ĐVT) — để đối chiếu / kiểm, không phải dữ liệu vận hành.
--   2. Dòng khớp: tên = tên Excel; NHÓM (`category`) = cột Nhóm hàng; đang bán;
--      giá = giá Excel khi > 0. Giá 0đ CHỈ nạp cho dịch vụ THU HỘ đối tác
--      (billing_owner EXTERNAL_PARTNER — khách trả thẳng đối tác, giá phòng khám
--      chỉ để tham khảo, quầy hiện "0đ"). Dịch vụ phòng khám thu mà Excel ghi 0đ
--      (Khám sau sinh BN cũ, Tư vấn KQ XN cũ) GIỮ giá đang có / trống — luật
--      20260926000001 vẫn đúng ở đây: nạp 0 cho dòng phòng khám thu là thu 0 đồng.
--   3. Nhóm "XN thu hộ": bên thu = thu hộ đối tác (trừ dòng quản lý đã chọn tay).
--   4. Thiếu dòng (DB mới dựng) → thêm, mã ổn định `DV_<md5 tên>` , nhóm việc
--      theo nhóm hàng (Siêu âm → DICHVU-SIEUAM; Thủ thuật / Dịch vụ khác →
--      DICHVU-THUTHUAT; XN thu hộ / Xét nghiệm → DICHVU-LAYMAU-MAU = Lấy mẫu).
--      Phí khám thiếu thì KHÔNG thêm — phí khám đi theo loại khám (`loai_kham_phi`).
--   5. Dịch vụ đang bán KHÔNG có trong Excel: KHÔNG xoá, KHÔNG tắt — chỉ gắn
--      nhóm cho gọn (Nam khoa XN → XN thu hộ / Xét nghiệm theo bên thu…). Tắt
--      ĐÚNG HAI dòng chắc chắn là dòng TIÊU ĐỀ của phiếu giấy cũ (đã ẩn khỏi danh
--      mục chỉ định từ 27/09, B10): "Xét nghiệm dịch âm đạo", "Laser sàn chậu".
--   6. Loại khám THỦ THUẬT chọn được mọi dịch vụ nhóm "Thủ thuật" của Excel (thêm
--      3 dòng soi buồng tử cung còn thiếu so với file 21/09).
--
-- ĐỌC: hàm `danh_muc_dich_vu(clinic)` — MỘT chỗ trả lời "dịch vụ này là phí khám
-- không, cần phòng không, phòng nào làm được, đang thiếu phòng không" (cùng luật
-- `phong_lam_duoc` với xếp phòng). Danh mục chỉ định, Bảng giá dịch vụ & phòng,
-- cảnh báo trang chủ đều đọc hàm này.

-- ── 0. Tên chuẩn hoá ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.khoa_ten_dich_vu(p text)
RETURNS text
LANGUAGE sql
STABLE
AS $fn$
    SELECT lower(regexp_replace(btrim(normalize(coalesce(p, ''), NFC)),
                                '\s+', ' ', 'g'))
$fn$;

-- ── 1. Bảng nguồn (Excel 01/10) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.danh_muc_dich_vu_nguon (
    nguon        text    NOT NULL,
    thu_tu       integer NOT NULL,
    nhom         text    NOT NULL,
    ten          text    NOT NULL,
    gia          numeric(12, 0) NOT NULL CHECK (gia >= 0),
    thoi_luong   integer,
    don_vi       text,
    -- Ánh xạ tay khi tên trên hệ thống khác tên Excel (mã SP KiotViet).
    ma_kiotviet  text,
    PRIMARY KEY (nguon, thu_tu)
);
COMMENT ON TABLE public.danh_muc_dich_vu_nguon IS
'Danh mục dịch vụ chuẩn nguyên văn từ file phòng khám gửi (nguon = tên đợt). Chỉ để đồng bộ/đối chiếu — vận hành đọc service_price (01/10/2026).';
ALTER TABLE public.danh_muc_dich_vu_nguon ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.danh_muc_dich_vu_nguon FROM anon, authenticated;

INSERT INTO public.danh_muc_dich_vu_nguon
    (nguon, thu_tu, nhom, ten, gia, thoi_luong, don_vi, ma_kiotviet)
SELECT 'kiot_0110', v.thu_tu, v.nhom, v.ten, v.gia, v.thoi_luong, v.don_vi,
       v.ma_kiotviet
  FROM (VALUES
    (1, 'Dịch vụ khác', 'Ghế điện từ trường', 3000000, 30, 'buổi', NULL),
    (2, 'Dịch vụ khác', 'Tập máy Bio điều trị (chưa bao gồm đầu dò)', 900000, 45, 'lần', NULL),
    (3, 'Dịch vụ khác', 'Bơm PRP niêm mạc tử cung (Tropocel)', 8000000, 10, NULL, 'SP000140'),
    (4, 'Dịch vụ khác', 'Bơm PRP niêm mạc tử cung (Regenlab)', 8000000, 30, NULL, 'SP000136'),
    (5, 'Dịch vụ khác', 'Massage vú', 200000, 10, NULL, NULL),
    (6, 'Dịch vụ khác', 'Đo trương lực cơ sàn chậu máy Bio (ko bao gồm đầu dò)', 300000, 15, 'lần', NULL),
    (7, 'Dịch vụ khác', 'Soi âm hộ', 250000, 10, 'lần', NULL),
    (8, 'Phí khám', 'Khám quản lý thai (TS)', 250000, 15, NULL, NULL),
    (9, 'Phí khám', 'Khám sau sinh BN cũ', 0, 5, NULL, NULL),
    (10, 'Phí khám', 'Vật lý trị liệu', 500000, 1, NULL, NULL),
    (11, 'Phí khám', 'Khám quản lý thai', 200000, 1, NULL, NULL),
    (12, 'Phí khám', 'Tư vấn KQ XN cũ', 0, 1, NULL, NULL),
    (13, 'Phí khám', 'Khám nam khoa', 300000, 1, NULL, NULL),
    (14, 'Phí khám', 'Tư vấn phụ khoa chuyên sâu (TMK, TD, sàn chậu…)', 300000, 1, NULL, NULL),
    (15, 'Phí khám', 'Khám tư vấn viêm nhiễm phụ khoa', 300000, 1, NULL, NULL),
    (16, 'Phí khám', 'Tái khám mong con', 150000, 1, NULL, NULL),
    (17, 'Phí khám', 'Khám mong con lần đầu', 400000, 1, NULL, NULL),
    (18, 'Siêu âm', 'Siêu âm 4D sàn chậu (20 phút)', 500000, 15, 'lần', NULL),
    (19, 'Siêu âm', 'Siêu âm 3D song thai thai nhỏ', 300000, 20, NULL, NULL),
    (20, 'Siêu âm', 'Siêu âm tuyến tiền liệt', 250000, 10, NULL, NULL),
    (21, 'Siêu âm', 'Siêu âm âm vật', 150000, 5, NULL, NULL),
    (22, 'Siêu âm', 'Siêu âm khớp 1 bên (gối, vai, háng…)', 150000, 1, 'lần', NULL),
    (23, 'Siêu âm', 'SA bơm nước buồng tử cung', 800000, 1, NULL, NULL),
    (24, 'Siêu âm', 'Siêu âm COMBO PHỤ KHOA BỤNG VÚ GIÁP MẠCH CẢNH', 900000, 1, NULL, NULL),
    (25, 'Siêu âm', 'Siêu âm 4D tử cung buồng trứng', 350000, 1, NULL, NULL),
    (26, 'Siêu âm', 'Siêu âm 2D tử cung buồng trứng', 250000, 1, NULL, NULL),
    (27, 'Siêu âm', 'Siêu âm tuyến giáp', 200000, 1, NULL, NULL),
    (28, 'Siêu âm', 'Siêu âm ổ bụng', 250000, 1, NULL, NULL),
    (29, 'Siêu âm', 'Siêu âm tuyến vú hai bên', 200000, 1, NULL, NULL),
    (30, 'Siêu âm', 'Siêu âm dương vật', 250000, 10, 'lần', NULL),
    (31, 'Siêu âm>>Siêu âm Doppler', 'Siêu âm Doppler dương vật', 300000, 15, NULL, NULL),
    (32, 'Siêu âm>>Siêu âm Doppler', 'Siêu âm Doppler động tĩnh mạch chi dưới hai bên', 400000, 1, NULL, NULL),
    (33, 'Siêu âm>>Siêu âm Doppler', 'Siêu âm Doppler động mạch thận hai bên', 400000, 1, NULL, NULL),
    (34, 'Siêu âm>>Siêu âm Doppler', 'Siêu âm Doppler tinh hoàn hai bên', 350000, 1, NULL, NULL),
    (35, 'Siêu âm>>Siêu âm Doppler', 'Siêu âm Doppler hệ động mạch cảnh và sống nền hai bên', 400000, 1, NULL, NULL),
    (36, 'Siêu âm>>Siêu âm thai', 'Siêu âm 6D thai 12 tuần', 400000, 1, NULL, NULL),
    (37, 'Siêu âm>>Siêu âm thai', 'Siêu âm 6D song thai', 700000, 1, NULL, NULL),
    (38, 'Siêu âm>>Siêu âm thai', 'Siêu âm 3D thai > 12 tuần (Song thai)', 400000, 1, NULL, NULL),
    (39, 'Siêu âm>>Siêu âm thai', 'Siêu âm 3D thai > 12 tuần', 300000, 1, NULL, NULL),
    (40, 'Siêu âm>>Siêu âm thai', 'Siêu âm đầu dò độ dài CTC', 50000, 1, NULL, NULL),
    (41, 'Siêu âm>>Siêu âm thai', 'Siêu âm Doppler thai nhi', 300000, 1, NULL, NULL),
    (42, 'Siêu âm>>Siêu âm thai', 'Siêu âm 6D sàng lọc hình thái', 400000, 1, NULL, NULL),
    (43, 'Siêu âm>>Siêu âm thai', 'Siêu âm 2D thai >12 tuần', 300000, 1, NULL, NULL),
    (44, 'Siêu âm>>Siêu âm thai', 'Siêu âm 2D thai <12 tuần', 250000, 1, NULL, NULL),
    (45, 'Thủ thuật', 'Soi buồng tử cung cắt dính từ lần thứ 6', 7000000, 5, NULL, NULL),
    (46, 'Thủ thuật', 'Soi buồng tử cung cắt dính', 11000000, 5, NULL, NULL),
    (47, 'Thủ thuật', 'Soi buồng tử cung chẩn đoán', 6000000, 5, NULL, NULL),
    (48, 'Thủ thuật', 'Laser trẻ hoá tiền đình và âm đạo', 7000000, 20, 'lần', NULL),
    (49, 'Thủ thuật', 'Đặt bóng chống dính buồng tử cung', 800000, 15, 'lần', NULL),
    (50, 'Thủ thuật', 'Laser điều trị bệnh lý (SSD, són tiểu…) 2 thành', 15000000, 45, 'lần', NULL),
    (51, 'Thủ thuật', 'Laser điều trị bệnh lý (SSD, són tiểu..) (1 thành)', 10000000, 30, 'lần', NULL),
    (52, 'Thủ thuật', 'Laser trẻ hoá tiền đình', 4500000, 10, 'lần', NULL),
    (53, 'Thủ thuật', 'Nong tách dính âm hộ, âm vật', 1700000, 15, 'lần', NULL),
    (54, 'Thủ thuật', 'Cắt/ tách bao quy đầu âm vật', 7000000, 45, 'lần', NULL),
    (55, 'Thủ thuật', 'Tiêm HA Gspot', 15000000, 20, 'lần', NULL),
    (56, 'Thủ thuật', 'Sinh thiết vú, hạch dưới siêu âm (đã bao gồm giải phẫu bệnh)', 4500000, 15, NULL, NULL),
    (57, 'Thủ thuật', 'Cắt đốt u sinh dục', 3500000, 20, NULL, NULL),
    (58, 'Thủ thuật', 'Nạo ống cổ tử cung và làm giải phẫu bệnh', 1000000, 15, NULL, NULL),
    (59, 'Thủ thuật', 'Cắt đốt sùi mào gà', 5000000, 20, 'lần', NULL),
    (60, 'Thủ thuật', 'Khoét chóp CTC', 5000000, 30, NULL, NULL),
    (61, 'Thủ thuật', 'Bơm IUI', 4000000, 30, NULL, NULL),
    (62, 'Thủ thuật', 'Nong bao quy đầu dương vật', 1000000, 15, NULL, NULL),
    (63, 'Thủ thuật', 'Đặt vòng nâng cổ tử cung Pessary', 4500000, 5, NULL, NULL),
    (64, 'Thủ thuật', 'Siêu âm bơm nước', 800000, 1, NULL, NULL),
    (65, 'Thủ thuật', 'Đặt vòng nội tiết Mirena', 5000000, 1, NULL, NULL),
    (66, 'Thủ thuật', 'Cắt LEEP cổ tử cung', 5000000, 1, NULL, NULL),
    (67, 'Thủ thuật', 'Hút BTC', 2000000, 1, NULL, NULL),
    (68, 'Thủ thuật', 'Soi cổ tử cung', 400000, 1, NULL, NULL),
    (69, 'Thủ thuật', 'Xoắn lấy polyp CTC AH, ÂĐ < 1cm', 1500000, 1, NULL, NULL),
    (70, 'Thủ thuật', 'Tháo que thánh thai', 700000, 1, NULL, NULL),
    (71, 'Thủ thuật', 'Cấy que tránh thai', 2600000, 1, NULL, NULL),
    (72, 'Thủ thuật', 'Đốt điện cổ tử cung lộ tuyến', 4500000, 1, NULL, NULL),
    (73, 'Thủ thuật', 'Đặt vòng tránh thai', 500000, 1, NULL, NULL),
    (74, 'Thủ thuật', 'Tháo vòng tránh thai', 350000, 1, NULL, NULL),
    (75, 'Xét nghiệm', 'Đo mật độ xương', 200000, 2, NULL, NULL),
    (76, 'Xét nghiệm', 'Monitor Sản khoa song thai - đa thai', 300000, 5, NULL, NULL),
    (77, 'Xét nghiệm', 'Monitor sản khoa đơn thai', 200000, 5, NULL, NULL),
    (78, 'Xét nghiệm', 'Tổng phân tích nước tiểu', 50000, 5, NULL, NULL),
    (79, 'XN thu hộ', 'NIPT basic', 0, 10, NULL, NULL),
    (80, 'XN thu hộ', 'Liên cầu B', 0, 5, NULL, NULL),
    (81, 'XN thu hộ', '13 bệnh lây STD', 0, 5, NULL, NULL),
    (82, 'XN thu hộ', 'Combo HPV 40 + thinprep', 0, 5, NULL, NULL),
    (83, 'XN thu hộ', 'HPV định type PCR 16 type', 0, 5, NULL, NULL),
    (84, 'XN thu hộ', 'NIPT Basic plus', 0, 15, NULL, NULL),
    (85, 'XN thu hộ', 'NIPT Trisure Procare / Geneva plus', 0, 15, NULL, NULL),
    (86, 'XN thu hộ', 'Giải phẫu bệnh', 600000, 5, NULL, NULL),
    (87, 'XN thu hộ', 'Gentis 9 bệnh gen lặn', 0, 5, NULL, NULL),
    (88, 'XN thu hộ', 'XN gen BrCa', 2500000, 5, NULL, NULL),
    (89, 'XN thu hộ', 'NIPT trisure / Geneva', 0, 5, NULL, NULL),
    (90, 'XN thu hộ', 'NIPT Geneva 7', 0, 5, NULL, NULL),
    (91, 'XN thu hộ', 'Sinh thiết CTC, âm hộ, âm đạo (bấm ST + làm giải phẫu bệnh) (5 ngày)', 1000000, 1, NULL, NULL),
    (92, 'XN thu hộ', 'HPV định type PCR (40 type)', 0, 5, NULL, NULL),
    (93, 'XN thu hộ', 'Thinprep sàng lọc tế bào ung thử cổ tử cung', 0, 5, NULL, NULL)
  ) AS v(thu_tu, nhom, ten, gia, thoi_luong, don_vi, ma_kiotviet)
ON CONFLICT (nguon, thu_tu) DO UPDATE
   SET nhom = EXCLUDED.nhom, ten = EXCLUDED.ten, gia = EXCLUDED.gia,
       thoi_luong = EXCLUDED.thoi_luong, don_vi = EXCLUDED.don_vi,
       ma_kiotviet = EXCLUDED.ma_kiotviet;

-- ── 2. Nhóm hàng → nhóm việc mặc định (chỉ dùng khi dịch vụ chưa có) ────────
CREATE OR REPLACE FUNCTION public.nhom_viec_theo_nhom_hang(p_nhom text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT CASE
        WHEN p_nhom LIKE 'Siêu âm%' THEN 'DICHVU-SIEUAM'
        WHEN p_nhom IN ('Thủ thuật', 'Dịch vụ khác') THEN 'DICHVU-THUTHUAT'
        -- XN thu hộ: phòng = nơi LẤY MẪU (gợi ý — quản lý chỉnh được).
        WHEN p_nhom IN ('XN thu hộ', 'Xét nghiệm') THEN 'DICHVU-LAYMAU-MAU'
        ELSE NULL
    END
$fn$;

-- ── 3. Ghép dòng nguồn ↔ dòng bảng giá ──────────────────────────────────────
CREATE OR REPLACE FUNCTION public.ghep_danh_muc_dich_vu(p_nguon text)
RETURNS TABLE (clinic_id uuid, thu_tu integer, service_price_id uuid)
LANGUAGE sql
STABLE
AS $fn$
    SELECT DISTINCT ON (sp.clinic_id, x.thu_tu)
           sp.clinic_id, x.thu_tu, sp.id
      FROM public.danh_muc_dich_vu_nguon x
      JOIN public.service_price sp
        ON sp."group" = 'dich_vu'
       AND ((x.ma_kiotviet IS NOT NULL AND sp.ma_kiotviet = x.ma_kiotviet)
            OR public.khoa_ten_dich_vu(sp.name) = public.khoa_ten_dich_vu(x.ten))
     WHERE x.nguon = p_nguon
     ORDER BY sp.clinic_id, x.thu_tu,
              (x.ma_kiotviet IS NOT NULL AND sp.ma_kiotviet = x.ma_kiotviet) DESC,
              sp.active DESC, (sp.ma_kiotviet IS NOT NULL) DESC, sp.service_code
$fn$;

-- ── 4. Đồng bộ ───────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.dong_bo_danh_muc_dich_vu(
    p_nguon text DEFAULT 'kiot_0110')
RETURNS TABLE (sua integer, them integer, tat integer, gan_thu_thuat integer)
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
    n_sua integer := 0;
    n_them integer := 0;
    n_tat integer := 0;
    n_tt integer := 0;
    n integer := 0;
BEGIN
    -- 4a. Dòng đã có: tên, nhóm, đang bán, bên thu, giá, nhóm việc còn trống.
    WITH g AS (SELECT * FROM public.ghep_danh_muc_dich_vu(p_nguon)),
    moi AS (
        SELECT sp.id, x.ten, x.nhom, x.gia,
               CASE WHEN x.nhom = 'XN thu hộ' AND NOT sp.billing_owner_chon_tay
                    THEN 'EXTERNAL_PARTNER' ELSE sp.billing_owner END AS ben,
               (x.nhom = 'XN thu hộ' AND NOT sp.billing_owner_chon_tay)
                   OR sp.billing_owner_chon_tay AS chon_tay,
               coalesce(sp.node_code,
                        (SELECT n.code FROM public.node_definition n
                          WHERE n.clinic_id = sp.clinic_id AND n.is_active
                            AND n.code = public.nhom_viec_theo_nhom_hang(x.nhom)))
                   AS node
          FROM g
          JOIN public.danh_muc_dich_vu_nguon x
            ON x.nguon = p_nguon AND x.thu_tu = g.thu_tu
          JOIN public.service_price sp ON sp.id = g.service_price_id
    ),
    dich AS (
        SELECT m.*,
               CASE WHEN m.gia > 0 THEN m.gia
                    WHEN m.ben = 'EXTERNAL_PARTNER' THEN m.gia
                    ELSE NULL END AS gia_nap
          FROM moi m
    ),
    sua AS (
        UPDATE public.service_price sp
           SET name = d.ten,
               category = d.nhom,
               active = true,
               billing_owner = d.ben,
               billing_owner_chon_tay = d.chon_tay,
               unit_price = coalesce(d.gia_nap, sp.unit_price),
               gia_tam = CASE WHEN d.gia_nap IS NOT NULL THEN false
                              ELSE sp.gia_tam END,
               node_code = d.node,
               updated_at = now()
          FROM dich d
         WHERE sp.id = d.id
           AND (sp.name, sp.category, sp.active, sp.billing_owner,
                sp.billing_owner_chon_tay, sp.unit_price, sp.gia_tam,
                sp.node_code)
               IS DISTINCT FROM
               (d.ten, d.nhom, true, d.ben, d.chon_tay,
                coalesce(d.gia_nap, sp.unit_price),
                CASE WHEN d.gia_nap IS NOT NULL THEN false ELSE sp.gia_tam END,
                d.node)
        RETURNING 1
    )
    SELECT count(*) INTO n_sua FROM sua;

    -- 4b. Thiếu dòng (trừ Phí khám) → thêm. Chỉ phòng khám đã có bảng giá dịch vụ.
    WITH thieu AS (
        SELECT c.id AS clinic_id, x.*
          FROM public.clinic c
         CROSS JOIN public.danh_muc_dich_vu_nguon x
         WHERE x.nguon = p_nguon AND x.nhom <> 'Phí khám'
           AND EXISTS (SELECT 1 FROM public.service_price p
                        WHERE p.clinic_id = c.id AND p."group" = 'dich_vu')
           AND NOT EXISTS (SELECT 1 FROM public.ghep_danh_muc_dich_vu(p_nguon) g
                            WHERE g.clinic_id = c.id AND g.thu_tu = x.thu_tu)
    ),
    them AS (
        INSERT INTO public.service_price
            (clinic_id, service_code, name, "group", unit_price, active,
             category, node_code, billing_owner, billing_owner_chon_tay)
        SELECT t.clinic_id,
               'DV_' || upper(substr(md5(public.khoa_ten_dich_vu(t.ten)), 1, 10)),
               t.ten, 'dich_vu',
               CASE WHEN t.gia > 0 OR t.nhom = 'XN thu hộ' THEN t.gia END,
               true, t.nhom, n.code,
               CASE WHEN t.nhom = 'XN thu hộ' OR coalesce(n.lam_ben_ngoai, false)
                    THEN 'EXTERNAL_PARTNER' ELSE 'CLINIC' END,
               t.nhom = 'XN thu hộ'
          FROM thieu t
          LEFT JOIN public.node_definition n
            ON n.clinic_id = t.clinic_id AND n.is_active
           AND n.code = public.nhom_viec_theo_nhom_hang(t.nhom)
        ON CONFLICT (clinic_id, "group", service_code) DO NOTHING
        RETURNING 1
    )
    SELECT count(*) INTO n_them FROM them;

    -- 4c. Dịch vụ đang bán ngoài Excel: chỉ gắn NHÓM cho gọn (không đổi giá /
    -- bên thu / phòng). Xét nghiệm nam khoa theo bên thu đang có.
    UPDATE public.service_price sp
       SET category = coalesce(v.nhom, CASE WHEN sp.billing_owner = 'EXTERNAL_PARTNER'
                                            THEN 'XN thu hộ' ELSE 'Xét nghiệm' END),
           updated_at = now()
      FROM (VALUES
            ('CLS_SIEU_AM_3D_SAN_CHAU', 'Siêu âm'),
            ('CLS_GHE_DTT_DAU_CO', 'Dịch vụ khác'),
            ('CLS_GHE_DTT_YEU_CO', 'Dịch vụ khác'),
            ('CLS_BIOFEEDBACK_CO_BAN', 'Dịch vụ khác'),
            ('CLS_BIOFEEDBACK_NANG_CAO', 'Dịch vụ khác'),
            ('CLS_DFI', 'Xét nghiệm'),
            ('CLS_TINH_DICH_DO', 'Xét nghiệm'),
            ('CLS_XET_NGHIEM_MAU', NULL),
            ('CLS_CFTR', NULL),
            ('CLS_Y_MICRODELETION', NULL),
            ('CLS_KARYOTYPE', NULL),
            ('CLS_NUOC_TIEU_SAU_XUAT_TINH', NULL),
            ('CLS_XN_NOI_TIET_NAM', NULL),
            ('CLS_CHUP_MRI_VU', 'Chụp phim ngoài'),
            ('CLS_CHUP_VU_EP', 'Chụp phim ngoài'),
            ('CLS_CHUP_TU_CUNG_VOI_TRUNG', 'Chụp phim ngoài')
           ) AS v(ma, nhom)
     WHERE sp."group" = 'dich_vu' AND sp.service_code = v.ma
       AND sp.category IS DISTINCT FROM coalesce(v.nhom,
               CASE WHEN sp.billing_owner = 'EXTERNAL_PARTNER'
                    THEN 'XN thu hộ' ELSE 'Xét nghiệm' END)
       AND NOT EXISTS (SELECT 1 FROM public.ghep_danh_muc_dich_vu(p_nguon) g
                        WHERE g.service_price_id = sp.id);
    GET DIAGNOSTICS n = ROW_COUNT;
    n_sua := n_sua + n;

    -- 4d. Hai dòng TIÊU ĐỀ phiếu giấy cũ (không có trong Excel, đã ẩn khỏi danh
    -- mục chỉ định từ 27/09): tắt — không xoá; quản lý bật lại được ở Bảng giá.
    UPDATE public.service_price sp
       SET active = false, updated_at = now()
     WHERE sp."group" = 'dich_vu' AND sp.active
       AND sp.service_code IN ('CLS_XET_NGHIEM_DICH_AM_DAO', 'CLS_LASER')
       AND NOT EXISTS (SELECT 1 FROM public.ghep_danh_muc_dich_vu(p_nguon) g
                        WHERE g.service_price_id = sp.id);
    GET DIAGNOSTICS n_tat = ROW_COUNT;

    -- 4e. Loại khám Thủ thuật chọn được mọi dịch vụ nhóm "Thủ thuật".
    INSERT INTO public.loai_kham_phi
        (clinic_id, service_type_id, service_price_id, thu_tu)
    SELECT st.clinic_id, st.id, g.service_price_id,
           100 + x.thu_tu
      FROM public.ghep_danh_muc_dich_vu(p_nguon) g
      JOIN public.danh_muc_dich_vu_nguon x
        ON x.nguon = p_nguon AND x.thu_tu = g.thu_tu AND x.nhom = 'Thủ thuật'
      JOIN public.service_type st
        ON st.clinic_id = g.clinic_id AND st.code = 'THU_THUAT'
     WHERE NOT EXISTS (SELECT 1 FROM public.loai_kham_phi l
                        WHERE l.clinic_id = st.clinic_id
                          AND l.service_type_id = st.id
                          AND l.service_price_id = g.service_price_id)
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n_tt = ROW_COUNT;

    RETURN QUERY SELECT n_sua, n_them, n_tat, n_tt;
END
$fn$;

-- ── 5. MỘT chỗ đọc danh mục dịch vụ + phòng ─────────────────────────────────
-- Phí khám = không nhóm việc VÀ (nhóm Phí khám / tiền khám, mã KHAM_*, hoặc là
-- dịch vụ con của một loại khám). Dịch vụ có nhóm việc (Vật lý trị liệu, Tư vấn
-- phụ khoa chuyên sâu — Excel xếp nhóm Phí khám) vẫn là dịch vụ làm ở phòng.
-- Cần phòng = không phải phí khám, không phải việc đối tác làm trọn.
-- Chưa có phòng = đang bán + cần phòng + không phòng NỘI BỘ đang bật nào làm
-- được (cùng `phong_lam_duoc` với xếp phòng).
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
         SELECT NOT pk.la
                AND NOT (sp.doi_tac_lay_mau OR coalesce(n.lam_ben_ngoai, false))
                AS can) cp
     WHERE sp.clinic_id = p_clinic_id AND sp."group" = 'dich_vu'
$fn$;

COMMENT ON FUNCTION public.danh_muc_dich_vu(uuid) IS
'Danh mục dịch vụ + phòng làm được (01/10/2026): phí khám? cần phòng? phòng nào (phong_lam_duoc)? chưa có phòng? — MỘT chỗ cho danh mục chỉ định, Bảng giá dịch vụ & phòng, cảnh báo trang chủ.';

-- ── 6. Chạy (DB mới dựng: seed.sql gọi lại sau khi nạp dữ liệu) ─────────────
DO $$
DECLARE
    r record;
BEGIN
    SELECT * INTO r FROM public.dong_bo_danh_muc_dich_vu('kiot_0110');
    RAISE NOTICE 'Danh mục 01/10: sửa % · thêm % · tắt % · gắn loại khám Thủ thuật %',
        r.sua, r.them, r.tat, r.gan_thu_thuat;
END
$$;
