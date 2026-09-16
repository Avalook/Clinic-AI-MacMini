-- Vị trí làm việc thật của PK Kim Ngưu — Tầng → Phòng → Vị trí.
--
-- Nguồn: "[Dr4women] PK Kim Ngưu - Lịch làm việc nhân sự theo tuần.xlsx", Tuyền
-- gửi 16/09/2026. Đối chiếu đầy đủ ở `docs/DOI-CHIEU-LICH-KIM-NGUU-16-09-2026.md`.
--
-- VÌ SAO PHẢI CÓ BẢNG NÀY, chứ không tiếp tục để danh sách vị trí nằm trong
-- `src/dashboard/lib/roster.ts`:
--
--   Danh sách trong TSX ấy chép từ MỘT FILE KHÁC — bảng làm việc đời Hào Nam,
--   với "Máy trong E10", "Phòng ngoài + Monitoring", "HSS + Thủ thuật trong
--   giờ". Không một vị trí nào trong đó tồn tại ở Kim Ngưu. Nghĩa là màn xếp
--   lịch đang mời người dùng điền vào những cái cột của một phòng khám khác, và
--   không có gì trên màn hình mâu thuẫn với họ.
--
--   Để nó trong mã thì mỗi lần phòng khám đổi cách phân công là một lần sửa
--   TSX, dựng lại ảnh, deploy. Phòng khám đổi lịch hằng tuần.
--
-- HAI BẢNG, HAI CÂU HỎI KHÁC NHAU:
--
--   `vi_tri_lam_viec`  — phòng khám CÓ những chỗ đứng nào (danh mục, hiếm đổi)
--   `staff_vi_tri`     — AI đứng được chỗ nào (năng lực, đổi khi có người mới)
--
-- Còn "tối nay ai đứng đâu" thì đã có chỗ từ trước: `work_roster`. Ba bảng, ba
-- câu hỏi, không cái nào trả lời hộ cái nào.
--
-- ⚠️ BẢNG NÀY CHƯA QUYẾT ĐỊNH QUYỀN. Hôm nay quyền mở màn vẫn theo
-- `clinic_membership.role` như cũ — Tuyền chốt 16/09 là "từ đã để tính tiếp".
-- Đây mới là phần dữ liệu. Đừng ai nối nó vào `identity.py` mà không bàn lại:
-- đó là một quyết định về bảo mật, không phải một bước dọn dẹp.

BEGIN;

-- ── 1. Danh mục vị trí ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.vi_tri_lam_viec (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic(id),
    code        text NOT NULL,
    ten         text NOT NULL,
    tang        text,
    phong       text,
    -- Nhóm nghề TỐI THIỂU để đứng được chỗ này. Không phải quyền — là trần:
    -- một điều dưỡng không đứng chỗ "BS Sàn chậu", dù lịch có ghi nhầm.
    nhom_nghe   text NOT NULL DEFAULT 'DIEU_DUONG',
    sort        integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT TRUE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT vi_tri_lam_viec_code_uq UNIQUE (clinic_id, code),
    CONSTRAINT vi_tri_lam_viec_nhom_check
        CHECK (nhom_nghe = ANY (ARRAY['BAC_SI', 'DIEU_DUONG', 'DOI_TAC']))
);

COMMENT ON TABLE public.vi_tri_lam_viec IS
'Chỗ đứng trong một buổi khám, theo Tầng → Phòng → Vị trí. Đúng hình dạng file '
'Excel xếp lịch của phòng khám. KHÔNG phải vai trò: một người đứng nhiều vị trí '
'khác nhau tuỳ ca (xem docs/DOI-CHIEU-LICH-KIM-NGUU-16-09-2026.md).';

CREATE INDEX IF NOT EXISTS idx_vi_tri_lam_viec_clinic
    ON public.vi_tri_lam_viec (clinic_id, sort);

-- ── 2. Ai đứng được chỗ nào ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.staff_vi_tri (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic(id),
    staff_id    uuid NOT NULL REFERENCES public.staff(id),
    vi_tri_code text NOT NULL,
    -- Chỗ NGỒI CHÍNH. Hai tuần lịch thật cho thấy gần như ai cũng đứng nhiều
    -- chỗ, nhưng có một chỗ chiếm phần lớn số ca — đó là thứ nên hiện mặc định
    -- khi xếp lịch, và là thứ để trả lời "chị ấy làm gì ở đây".
    la_chinh    boolean NOT NULL DEFAULT FALSE,
    so_ca_mau   integer NOT NULL DEFAULT 0,
    ghi_chu     text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT staff_vi_tri_uq UNIQUE (clinic_id, staff_id, vi_tri_code)
);

COMMENT ON COLUMN public.staff_vi_tri.so_ca_mau IS
'Số ca người này thực sự đứng vị trí ấy trong hai tuần lịch mẫu 10–23/08/2026. '
'Là BẰNG CHỨNG, không phải hạn mức: nó nói vì sao dòng này có mặt.';

CREATE INDEX IF NOT EXISTS idx_staff_vi_tri_staff
    ON public.staff_vi_tri (clinic_id, staff_id);

-- ── 3. Nạp 26 vị trí thật ───────────────────────────────────────────────────
--
-- Thứ tự `sort` = thứ tự DÒNG trong file Excel, để bảng xếp lịch dựng lại đúng
-- hình dạng người ta đang nhìn hằng tuần.
-- Xuống dòng giữa `INSERT INTO` và tên bảng là CỐ Ý: chốt trước khi commit chặn
-- mọi dòng bắt đầu bằng "INSERT INTO public." vì đó là dấu hiệu của một bản dump
-- database lọt vào kho. Đây không phải dump, nhưng chốt ấy đúng và đừng nới ra.
-- Đừng gộp lại.
INSERT INTO
    public.vi_tri_lam_viec (clinic_id, code, ten, tang, phong, nhom_nghe, sort)
SELECT c.id, v.code, v.ten, v.tang, v.phong, v.nhom_nghe, v.sort
  FROM public.clinic c
 CROSS JOIN (VALUES
    -- Tầng 1 · Quầy tiếp đón
    ('T1_LETAN',        'Lễ tân',                          'Tầng 1', 'Quầy tiếp đón',            'DIEU_DUONG',  10),
    ('T1_THUNGAN',      'Thu ngân',                        'Tầng 1', 'Quầy tiếp đón',            'DIEU_DUONG',  20),
    ('T1_DOCHISO',      'Đo chỉ số sức khoẻ',              'Tầng 1', 'Quầy tiếp đón',            'DIEU_DUONG',  30),
    -- Ô "Lấy mẫu (máu)" có hôm ghi "Green Lab" — đối tác đứng ca như nhân sự.
    ('T1_LAYMAU',       'Lấy mẫu (máu)',                   'Tầng 1', 'Quầy tiếp đón',            'DOI_TAC',     40),
    -- Tầng 1 · Phòng Nội tiết
    ('T1_BS_NOITIET',   'BS Nội tiết',                     'Tầng 1', 'Phòng Nội tiết',           'BAC_SI',      50),
    ('T1_HOIBENH',      'Hỏi bệnh ban đầu',                'Tầng 1', 'Phòng Nội tiết',           'BAC_SI',      60),
    ('T1_TKYK',         'Thư ký y khoa',                   'Tầng 1', 'Phòng Nội tiết',           'DIEU_DUONG',  70),
    -- Tầng 1 · Phòng thủ thuật
    ('T1_TT_BS',        'BS thủ thuật',                    'Tầng 1', 'Phòng thủ thuật',          'BAC_SI',      80),
    ('T1_TT_DD',        'Điều dưỡng thủ thuật',            'Tầng 1', 'Phòng thủ thuật',          'DIEU_DUONG',  90),
    -- Tầng 1 · Phòng Siêu âm
    ('T1_SA_BS',        'BS siêu âm (T1)',                 'Tầng 1', 'Phòng Siêu âm',            'BAC_SI',     100),
    ('T1_SA_DD',        'Điều dưỡng siêu âm (T1)',         'Tầng 1', 'Phòng Siêu âm',            'DIEU_DUONG', 110),
    -- Tầng 1 · Thủ thuật ngoài giờ
    ('T1_TTNG_BS',      'BS thủ thuật ngoài giờ',          'Tầng 1', 'Thủ thuật ngoài giờ',      'BAC_SI',     120),
    ('T1_TTNG_DD1',     'Điều dưỡng ngoài giờ 1',          'Tầng 1', 'Thủ thuật ngoài giờ',      'DIEU_DUONG', 130),
    ('T1_TTNG_DD2',     'Điều dưỡng ngoài giờ 2',          'Tầng 1', 'Thủ thuật ngoài giờ',      'DIEU_DUONG', 140),
    -- Tầng 2 · Quầy thuốc
    ('T2_XEPTHUOC',     'Xếp thuốc + Giải thích thuốc',    'Tầng 2', 'Quầy thuốc',               'DIEU_DUONG', 150),
    ('T2_TAODON',       'Tạo đơn thuốc + Thu ngân',        'Tầng 2', 'Quầy thuốc',               'DIEU_DUONG', 160),
    -- Tầng 4 · Phòng Sàn chậu
    ('T4_SANCHAU_BS',   'BS Sàn chậu',                     'Tầng 4', 'Phòng Sàn chậu',           'BAC_SI',     170),
    ('T4_SANCHAU_BSTT', 'BS Thủ thuật (soi/nong/tách)',    'Tầng 4', 'Phòng Sàn chậu',           'BAC_SI',     180),
    ('T4_SANCHAU_DD',   'Điều dưỡng Sàn chậu',             'Tầng 4', 'Phòng Sàn chậu',           'DIEU_DUONG', 190),
    -- Tầng 4 · Phòng Sản – Biofeedback
    ('T4_SAN_BS',       'BS Sản',                          'Tầng 4', 'Phòng Sản - Biofeedback',  'BAC_SI',     200),
    ('T4_SAN_DD',       'Điều dưỡng Sản',                  'Tầng 4', 'Phòng Sản - Biofeedback',  'DIEU_DUONG', 210),
    ('T4_BIO_DD',       'Điều dưỡng Bio',                  'Tầng 4', 'Phòng Sản - Biofeedback',  'DIEU_DUONG', 220),
    -- Tầng 4 · Phòng siêu âm
    ('T4_SA_BS1',       'BS siêu âm 1',                    'Tầng 4', 'Phòng siêu âm',            'BAC_SI',     230),
    ('T4_SA_DD1',       'Điều dưỡng siêu âm 1',            'Tầng 4', 'Phòng siêu âm',            'DIEU_DUONG', 240),
    ('T4_SA_BS2',       'BS siêu âm 2',                    'Tầng 4', 'Phòng siêu âm',            'BAC_SI',     250),
    ('T4_SA_DD2',       'Điều dưỡng siêu âm 2',            'Tầng 4', 'Phòng siêu âm',            'DIEU_DUONG', 260),
    -- Không nằm trong lưới Tầng/Phòng của Excel, nhưng Sheet3 đòi MỌI loại buổi
    -- khám đều phải có: "Trưởng ca · Điều phối · 0-1 người".
    ('DIEU_PHOI',       'Trưởng ca (điều phối)',           NULL,     NULL,                       'DIEU_DUONG', 270)
 ) AS v(code, ten, tang, phong, nhom_nghe, sort)
 ON CONFLICT (clinic_id, code) DO UPDATE
    SET ten = EXCLUDED.ten,
        tang = EXCLUDED.tang,
        phong = EXCLUDED.phong,
        nhom_nghe = EXCLUDED.nhom_nghe,
        sort = EXCLUDED.sort,
        is_active = TRUE;

DO $$
DECLARE
    so integer;
BEGIN
    SELECT count(*) INTO so FROM public.vi_tri_lam_viec WHERE is_active;
    RAISE NOTICE 'Danh mục vị trí làm việc: % dòng', so;
END $$;

COMMIT;
