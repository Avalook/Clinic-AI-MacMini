-- PHẦN BỔ SUNG của lịch sử Notion (06/10/2026): lịch sử chăm sóc khách + các ô hồ
-- sơ còn thiếu (nguồn khách, người nhà, dự kiến sinh).
--
-- Bộ nạp: src/clinicai/services/nhap_bo_sung_notion.py (MỘT giao dịch, mặc định thử
-- khô, `--that` mới ghi, chạy lại không sinh trùng). Gỡ:
-- scripts/hoan-tac-bo-sung-notion.sql. Gói phụ dựng trên máy dev (dong_goi_phu.py).
--
-- LỊCH SỬ CHĂM SÓC CHỈ ĐỌC, KHÔNG SINH VIỆC: bảng "CSKH - Action" (63.659 dòng) nằm
-- ở `lich_su_notion.cham_soc`, KHÔNG đổ vào `tuong_tac_cskh` / `nhac_tai_kham` /
-- `hen_goi_lai` hay bảng nào `v_viec_cskh` đọc — đổ vào đó là sinh hàng nghìn việc
-- CSKH ma (yêu cầu cũ "chờ xác nhận lịch hẹn" từ tháng 11/2025…).

CREATE TABLE IF NOT EXISTS lich_su_notion.cham_soc (
    notion_id         uuid PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id),
    clinic_patient_id uuid NOT NULL REFERENCES public.patient(clinic_patient_id),
    lan_nhap_id       bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    ma                text,                    -- ACT-n
    luc               timestamptz NOT NULL,    -- lúc tạo dòng (giờ thật, hiển thị giờ VN)
    -- yeu_cau = việc được giao (có hạn) · thuc_hien = một lần gọi / nhắn / trả KQ ·
    -- chuyen_tiep = chuyển bác sĩ / đổi lịch… · ghi_chu = ghi chú trên hồ sơ.
    buoc              text NOT NULL
        CHECK (buoc IN ('yeu_cau', 'thuc_hien', 'chuyen_tiep', 'ghi_chu')),
    phan_loai         text,                    -- Đặt hẹn / Trả xét nghiệm / CSKH sau khám…
    kich_ban          text,                    -- kết quả theo kịch bản CSKH
    tinh_trang        text,                    -- trạng thái cuối của một yêu cầu
    noi_dung          text,                    -- mô tả chi tiết nhân viên ghi
    doi_tuong         text,                    -- "Lịch hẹn: 21/01 13:00 Sản 1 | BS … | …"
    nguoi_lam         text,                    -- tên tài khoản người làm (chữ, không ghép staff)
    cha_id            uuid,                    -- yêu cầu cha của một thao tác
    lich_hen_id       uuid REFERENCES lich_su_notion.lich_hen(notion_id),
    luot_kham_id      uuid REFERENCES lich_su_notion.luot_kham(notion_id),
    xet_nghiem_id     uuid REFERENCES lich_su_notion.xet_nghiem(notion_id),
    notion_url        text
);
CREATE INDEX IF NOT EXISTS cham_soc_bn
    ON lich_su_notion.cham_soc (clinic_patient_id, luc DESC);

COMMENT ON TABLE lich_su_notion.cham_soc IS
'Lịch sử chăm sóc khách trước 10/2026 (bảng CSKH - Action). Chỉ đọc — KHÔNG phải '
'việc CSKH, không bảng nào của luồng việc đọc nó. 20261006120000.';

-- Nguồn khách cũ (FB / Zalo / Hotline / TikTok). Hệ thống không lưu kênh trên hồ sơ:
-- "Kênh" ở Danh sách bệnh nhân / Quản lý khách hàng là kênh của LỊCH HẸN gần nhất
-- (`danh_sach_khach_cskh.COT_KENH_DOI_HUY`). Nguồn cũ chỉ hiện khi khách CHƯA có
-- kênh nào trên hệ thống — không ghi đè.
ALTER TABLE lich_su_notion.nguoi ADD COLUMN IF NOT EXISTS kenh text;

-- Bản ghi phần bổ sung tạo ra trong bảng của hệ thống (`patient_link` người nhà,
-- `pregnancy` dự kiến sinh) — để chạy lại không trùng và gỡ đúng những dòng ấy.
CREATE TABLE IF NOT EXISTS lich_su_notion.ban_ghi_bo_sung (
    bang          text NOT NULL CHECK (bang IN ('patient_link', 'pregnancy')),
    ban_ghi_id    uuid NOT NULL,
    nguon         text NOT NULL,              -- nguoi_key / cặp nguoi_key / trang gốc
    lan_nhap_id   bigint NOT NULL REFERENCES lich_su_notion.lan_nhap(id),
    PRIMARY KEY (bang, ban_ghi_id)
);
