-- NGÀY CẮT NOTION: chuyển lịch hẹn TƯƠNG LAI của sổ hẹn cũ thành lịch thật (06/10/2026).
--
-- Bộ chuyển: src/clinicai/services/chuyen_lich_hen.py (một giao dịch, mặc định
-- thử khô, chạy MỘT lần vào ngày cắt). Migration này chỉ tạo SỔ GHÉP (lịch hẹn cũ
-- → lịch hẹn / việc gọi thật) để chạy lại không sinh trùng và gỡ được
-- (scripts/hoan-tac-lich-hen-that.sql). Không đổi bảng nào của public.
--
-- Không khoá ngoại tới lich_su_notion.lich_hen: gỡ lịch sử Notion
-- (hoan-tac-lich-su-notion.sql) TRUNCATE bảng ấy, khoá ngoại sẽ chặn nó.

CREATE TABLE IF NOT EXISTS lich_su_notion.lan_chuyen_lich (
    id            bigserial PRIMARY KEY,
    clinic_id     uuid NOT NULL REFERENCES public.clinic(id),
    bat_dau       timestamptz NOT NULL DEFAULT now(),
    che_do        jsonb,            -- khong_gio (tay|viec-goi), vuot_tran (ghi|bao), tu_ngay
    so_lieu       jsonb,
    hoan_tac_luc  timestamptz
);

-- Một dòng cho MỖI lịch hẹn cũ đã chuyển. Lịch vào danh sách tay KHÔNG có dòng
-- ở đây → lần chạy sau thử lại nó (vd. sau khi quản lý mở thêm chỗ).
-- trang_thai_luc_chuyen / slot_start / doctor_id: ảnh chụp lúc chuyển, để bộ gỡ
-- biết lịch đã bị nhân viên đổi chưa (đổi rồi thì không gỡ tự động).
CREATE TABLE IF NOT EXISTS lich_su_notion.lich_hen_that (
    notion_id              uuid PRIMARY KEY,
    clinic_id              uuid NOT NULL REFERENCES public.clinic(id),
    lan_chuyen_lich_id     bigint NOT NULL REFERENCES lich_su_notion.lan_chuyen_lich(id),
    thanh                  text NOT NULL CHECK (thanh IN ('lich_hen', 'viec_goi')),
    appointment_id         uuid,
    nhac_tai_kham_id       uuid,
    trang_thai_luc_chuyen  text,
    slot_start             timestamptz,
    doctor_id              uuid,
    CONSTRAINT lich_hen_that_dung_loai CHECK (
        (thanh = 'lich_hen') = (appointment_id IS NOT NULL)
        AND (thanh = 'viec_goi') = (nhac_tai_kham_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS lich_hen_that_appt_idx
    ON lich_su_notion.lich_hen_that (appointment_id) WHERE appointment_id IS NOT NULL;

COMMENT ON TABLE lich_su_notion.lich_hen_that IS
'Sổ ghép lịch hẹn tương lai của sổ cũ → appointment / nhac_tai_kham (chuyen_lich_hen.py, ngày cắt Notion).';
