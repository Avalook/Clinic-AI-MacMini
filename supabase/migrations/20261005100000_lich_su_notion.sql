-- LỊCH SỬ KHÁM CŨ TỪ NOTION (Tuyền 05/10/2026).
--
-- Phòng khám dùng Notion từ 04/2025 → 10/2026 (14.334 lượt khám, 30.751 dịch vụ,
-- 23.113 tờ kết quả, 10.684 xét nghiệm, 35.063 dòng thuốc, 19.111 lịch hẹn) và bỏ
-- Notion khi hệ thống mới nhận đủ lịch sử. Bản này chỉ tạo CHỖ CHỨA; dữ liệu do
-- `scripts/nhap-lich-su-notion.sh` nạp (gói dựng trên máy dev từ ảnh chụp Notion).
--
-- VÌ SAO SCHEMA RIÊNG, KHÔNG ĐỔ VÀO visit / appointment / prescription:
--   * các bảng ấy là LUỒNG VIỆC đang chạy — trigger báo realtime, cấp số thứ tự,
--     kiểm sức chứa, quầy thuốc lọc đơn "chưa phát", và đều khoá xoá cứng. 14
--     nghìn lượt cũ đổ vào sẽ thành việc ma và không gỡ ra được (luật "mọi thao
--     tác hoàn tác được", CLAUDE.md mục 7);
--   * sao lưu 15 phút chỉ lấy schema `public` (`backup-db.sh`): để lịch sử (tĩnh,
--     ~50 MB nén) ngoài `public` thì bản 15 phút không phình; bản đêm lấy thêm nó.
-- Không view / hàm nào trong `public` ĐỌC schema này lúc dump được nạp lại, trừ
-- `la_khach_moi_cua_dich_vu` (hàm SQL — pg_dump tắt check_function_bodies).
--
-- MỐC THỜI GIAN — chỉ NGÀY, không đoán giờ (Tuyền 05/10): Notion không có
-- check-in/check-out; giờ tạo phiếu không phải giờ khách vào. Lượt nhập hàng loạt
-- vào Notion 14/11/2025 ("Notion 1") lấy ngày ghi ở dòng đầu ô Khám – Tư vấn.
-- "Lần thứ N" chỉ đánh khi chắc; cùng ngày nhiều lượt → `thu_tu_khong_chac`.

CREATE SCHEMA IF NOT EXISTS lich_su_notion;

COMMENT ON SCHEMA lich_su_notion IS
'Lịch sử khám cũ nhập từ Notion (05/10/2026). Chỉ đọc, gỡ được theo lan_nhap. '
'Lần thứ N tính trên dữ liệu có từ 04/2025 — trước đó không có dữ liệu.';

-- Đánh dấu hồ sơ khách TẠO ra từ Notion (khách đã có sẵn trên hệ thống thì không
-- đánh dấu — chỉ gắn lịch sử vào). Hoàn tác = ẩn đúng các hồ sơ này.
ALTER TABLE public.patient ADD COLUMN IF NOT EXISTS nguon_nhap text;
ALTER TABLE public.patient DROP CONSTRAINT IF EXISTS patient_nguon_nhap_check;
ALTER TABLE public.patient ADD CONSTRAINT patient_nguon_nhap_check
    CHECK (nguon_nhap IS NULL OR nguon_nhap = 'notion');
COMMENT ON COLUMN public.patient.nguon_nhap IS
'notion = hồ sơ tạo khi nhập lịch sử Notion (05/10/2026). NULL = tạo trên hệ thống.';

CREATE TABLE IF NOT EXISTS lich_su_notion.lan_nhap (
    id          bigserial PRIMARY KEY,
    clinic_id   uuid NOT NULL REFERENCES public.clinic(id),
    goi         text NOT NULL,                 -- tên gói nhập (ngày ảnh chụp Notion)
    bat_dau     timestamptz NOT NULL DEFAULT now(),
    xong_luc    timestamptz,
    nguoi_chay  text,
    so_lieu     jsonb,
    hoan_tac_luc timestamptz
);

-- Một NGƯỜI = hồ sơ hành chính + hồ sơ lâm sàng Notion của họ (đã gộp trùng).
CREATE TABLE IF NOT EXISTS lich_su_notion.nguoi (
    nguoi_key         text PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    clinic_patient_id uuid NOT NULL REFERENCES public.patient(clinic_patient_id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    cach_ghep         text NOT NULL CHECK (cach_ghep IN ('tao_moi', 'ghep_sdt_ten')),
    ten               text,
    sdt               text,
    ho_so_notion      text[],                  -- KHACH-n, LAMSANG-n đã gộp
    nguon_ten         text,                    -- tên lấy từ đâu
    ghi_chu_lan_dau   text,                    -- "không rõ ngày khám"…
    link_drive        text,                    -- thư mục ảnh/video của khách
    notion_url        text
);
CREATE INDEX IF NOT EXISTS nguoi_bn ON lich_su_notion.nguoi (clinic_patient_id);

CREATE TABLE IF NOT EXISTS lich_su_notion.luot_kham (
    notion_id         uuid PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    clinic_patient_id uuid NOT NULL REFERENCES public.patient(clinic_patient_id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    ma                text,
    ngay_kham         date NOT NULL,
    nguon_ngay        text NOT NULL,
    lan_thu           integer,
    thu_tu_khong_chac boolean NOT NULL DEFAULT false,
    loai_kham_goc     text,
    service_type_id   uuid REFERENCES public.service_type(id),
    bac_si_goc        text,
    staff_id          uuid REFERENCES public.staff(id),
    co_so_goc         text,
    kham_tu_van       text,
    chan_doan         text,
    ghi_chu_vinh_vien text,
    tinh_trang_goc    text,
    notion_url        text
);
CREATE INDEX IF NOT EXISTS luot_bn ON lich_su_notion.luot_kham (clinic_patient_id, ngay_kham);
CREATE INDEX IF NOT EXISTS luot_loai ON lich_su_notion.luot_kham (clinic_patient_id, service_type_id);

CREATE TABLE IF NOT EXISTS lich_su_notion.dich_vu (
    notion_id         uuid PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    clinic_patient_id uuid NOT NULL REFERENCES public.patient(clinic_patient_id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    luot_kham_id      uuid REFERENCES lich_su_notion.luot_kham(notion_id),
    ma                text,
    ten_goc           text[],
    service_code      text,                    -- NULL = chưa ghép bảng giá
    nguoi_lam         text[],
    ngay              date,
    tinh_trang_goc    text,
    notion_url        text
);
CREATE INDEX IF NOT EXISTS dv_luot ON lich_su_notion.dich_vu (luot_kham_id);

CREATE TABLE IF NOT EXISTS lich_su_notion.ket_qua (
    notion_id         uuid PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    clinic_patient_id uuid NOT NULL REFERENCES public.patient(clinic_patient_id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    dich_vu_id        uuid REFERENCES lich_su_notion.dich_vu(notion_id),
    luot_kham_id      uuid REFERENCES lich_su_notion.luot_kham(notion_id),
    ma                text,
    tieu_de           text,
    mo_ta             text,
    ket_luan          text,
    bac_si_ky         text[],
    ghi_chu           text,
    ghi_de_chan_doan  text,
    da_co_noi_dung    boolean NOT NULL DEFAULT false,
    link_drive_cu     text,
    notion_url        text
);
CREATE INDEX IF NOT EXISTS kq_dv ON lich_su_notion.ket_qua (dich_vu_id);
CREATE INDEX IF NOT EXISTS kq_luot ON lich_su_notion.ket_qua (luot_kham_id);

CREATE TABLE IF NOT EXISTS lich_su_notion.xet_nghiem (
    notion_id         uuid PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    clinic_patient_id uuid NOT NULL REFERENCES public.patient(clinic_patient_id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    luot_kham_id      uuid REFERENCES lich_su_notion.luot_kham(notion_id),
    ma                text,
    noi_lam           text[],                  -- GreenLab, TrueMed… (Notion gọi là "tên XN")
    phan_loai         text,
    ket_qua           text,
    ket_qua_ai        text,
    tro_ly_ghi_chu    text,
    ghi_chu_vinh_vien text,
    tep               jsonb,                   -- [{ten, khoa}] — khoa = đường dẫn trong kho tệp
    tinh_trang_goc    text,
    ngay              date,
    notion_url        text
);
CREATE INDEX IF NOT EXISTS xn_luot ON lich_su_notion.xet_nghiem (luot_kham_id);
CREATE INDEX IF NOT EXISTS xn_bn ON lich_su_notion.xet_nghiem (clinic_patient_id);

CREATE TABLE IF NOT EXISTS lich_su_notion.ke_thuoc (
    notion_id         uuid PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    clinic_patient_id uuid NOT NULL REFERENCES public.patient(clinic_patient_id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    luot_kham_id      uuid REFERENCES lich_su_notion.luot_kham(notion_id),
    ma                text,
    ten_thuoc         text[],
    huong_dan         text,
    so_luong          text,
    ghi_chu_so_luong  text,
    luu_y             text,
    notion_url        text
);
CREATE INDEX IF NOT EXISTS thuoc_luot ON lich_su_notion.ke_thuoc (luot_kham_id);

CREATE TABLE IF NOT EXISTS lich_su_notion.lich_hen (
    notion_id         uuid PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    clinic_patient_id uuid NOT NULL REFERENCES public.patient(clinic_patient_id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    ma                text,
    ngay_hen          date,
    gio_hen           time,                    -- chỉ khi Notion ghi giờ hẹn
    loai_kham_goc     text,
    bac_si_goc        text,
    tinh_trang_den    text,
    tinh_trang_cskh   text,
    trang_thai        text,                    -- quy về trạng thái lịch hẹn của hệ thống
    luot_kham_ids     uuid[],
    notion_url        text
);
CREATE INDEX IF NOT EXISTS hen_bn ON lich_su_notion.lich_hen (clinic_patient_id, ngay_hen);

-- Sổ bất thường: mỗi dòng trỏ về người / lượt chuẩn + trang Notion gốc.
CREATE TABLE IF NOT EXISTS lich_su_notion.bat_thuong (
    id                bigserial PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    loai              text NOT NULL,
    muc               text NOT NULL,
    bang              text,
    notion_id         text,
    clinic_patient_id uuid REFERENCES public.patient(clinic_patient_id),
    luot_kham_id      uuid,
    chi_tiet          text,
    notion_url        text,
    trang_thai        text NOT NULL DEFAULT 'chờ xem'
);
CREATE INDEX IF NOT EXISTS bt_bn ON lich_su_notion.bat_thuong (clinic_patient_id);

-- KHÁCH MỚI HAY KHÁCH CŨ: đếm cả lượt Notion. Không có dòng này, khách đã khám 5
-- lần trên Notion vẫn bị luật "khách mới phải khám bác sĩ X" bắt như lần đầu.
-- (Hiện prod 0 luật bật — sửa trước cho đúng.)
CREATE OR REPLACE FUNCTION public.la_khach_moi_cua_dich_vu(
    p_clinic_id  uuid,
    p_patient_id uuid,
    p_service_id uuid,
    p_cach_tinh  text,
    p_so_thang   integer DEFAULT NULL
)
RETURNS boolean
LANGUAGE sql
STABLE
AS $function$
    SELECT CASE p_cach_tinh
        WHEN 'CHUA_TUNG' THEN NOT EXISTS (
            SELECT 1 FROM public.appointment a
             WHERE a.clinic_id = p_clinic_id
               AND a.clinic_patient_id = p_patient_id
               AND a.service_type_id = p_service_id
               AND a.status = 'COMPLETED'
        ) AND NOT EXISTS (
            SELECT 1 FROM lich_su_notion.luot_kham l
             WHERE l.clinic_id = p_clinic_id
               AND l.clinic_patient_id = p_patient_id
               AND l.service_type_id = p_service_id
        )
        WHEN 'DOT_MOI' THEN NOT EXISTS (
            SELECT 1 FROM public.care_episode e
             WHERE e.clinic_id = p_clinic_id
               AND e.clinic_patient_id = p_patient_id
               AND e.service_type_id = p_service_id
               AND e.status <> 'CLOSED'
        )
        WHEN 'QUA_N_THANG' THEN NOT EXISTS (
            SELECT 1 FROM public.appointment a
             WHERE a.clinic_id = p_clinic_id
               AND a.clinic_patient_id = p_patient_id
               AND a.service_type_id = p_service_id
               AND a.status = 'COMPLETED'
               AND a.slot_start >= now() - make_interval(months => p_so_thang)
        ) AND NOT EXISTS (
            SELECT 1 FROM lich_su_notion.luot_kham l
             WHERE l.clinic_id = p_clinic_id
               AND l.clinic_patient_id = p_patient_id
               AND l.service_type_id = p_service_id
               AND l.ngay_kham >= (now() - make_interval(months => p_so_thang))::date
        )
        ELSE false
    END
$function$;

COMMENT ON FUNCTION public.la_khach_moi_cua_dich_vu IS
    'Khách mới của một dịch vụ, theo cách tính do phòng khám chọn. '
    'Suy từ LỊCH SỬ (cả lượt Notion — 05/10/2026), không đọc ô appointment.patient_kind.';
