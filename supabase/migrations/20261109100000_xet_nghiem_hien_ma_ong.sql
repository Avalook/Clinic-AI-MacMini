-- XÉT NGHIỆM ĐỐI TÁC — công tắc "Hiện mã ống" (Tuyền 09/11/2026).
--
-- Phòng khám chưa thống nhất với đối tác cách ghi mã lên ống ⇒ tạm ẨN mã ở màn.
-- Chỉ ẩn ở lớp đọc (services/xet_nghiem/ban.py, mau.py, qua_trinh.py); Postgres vẫn
-- cấp mã như cũ (`cap_ma_mau`, Damm) — `mau_xet_nghiem.ma_mau`, ghép Drive theo mã,
-- sự kiện `lab.sample_collected` không đổi. Bật lại = một công tắc ở Cài đặt.
-- Mặc định TẮT: phòng khám đang thấy mã sẽ thôi thấy (không có dòng cài đặt = tắt).
-- Chạy lại được.

ALTER TABLE public.xet_nghiem_cai_dat
    ADD COLUMN IF NOT EXISTS hien_ma_ong boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.xet_nghiem_cai_dat.hien_ma_ong IS
'true = màn bàn XN hiện mã ống (M + 6 số). false (mặc định) = mẫu vẫn được đánh số trong DB nhưng mọi cửa đọc trả ma_mau = null.';

NOTIFY pgrst, 'reload schema';
