-- MẪU "PHIẾU SOI ÂM HỘ": ĐẶT TÊN CHO MỤC ĐẦU (27/09/2026 — đợt 3, B6b).
--
-- PDF gốc không có tiêu đề mục, bản giao diện mẫu ghi chỗ giữ "(không có tiêu
-- đề mục)" và v3 (20260926000004) chép nguyên văn → phiếu kết quả, màn xem kết
-- quả và bản in hiện đúng chữ ấy. Xuất bản phiên bản mới đổi TÊN mục "o" thành
-- "Kết quả soi". GIỮ NGUYÊN mọi `ma` (mục "o", bốn ô, mục "Đề nghị") — phiếu đã
-- điền đọc sang bản mới không mất ô nào; phiếu ghim bản cũ vẫn đọc đúng bản cũ.
--
-- Khuôn như 20260926000004: chỉ thay bản do HỆ THỐNG xuất bản
-- (xuat_ban_boi IS NULL) — phòng khám đã tự sửa mẫu ở Cài đặt → Mẫu kết quả
-- thì không đè. Bản cũ → RETIRED. Chạy lại được (khung đã đúng thì bỏ qua).
-- Cùng dữ liệu: src/clinicai/phieu_kham/mau_ket_qua_v3.json (SOI_AM_HO).

WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = 'KQ_SOI_AM_HO' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung$[{"ma": "o", "ten": "Kết quả soi", "block": [{"ma": "quy_dau_am_vat", "ten": "Quy đầu âm vật", "kieu": "text"}, {"ma": "tien_dinh_am_ho", "ten": "Tiền đình âm hộ", "kieu": "text"}, {"ma": "test_ran", "ten": "Test rặn", "kieu": "text"}, {"ma": "co_luc_am_dao_theo_oxford_cai_tien", "ten": "Cơ lực âm đạo theo Oxford cải tiến", "kieu": "text", "goi_y": "Độ"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = 'KQ_SOI_AM_HO'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, 'KQ_SOI_AM_HO',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = 'KQ_SOI_AM_HO'),
       'Phiếu soi âm hộ', cu.nhom, $khung$[{"ma": "o", "ten": "Kết quả soi", "block": [{"ma": "quy_dau_am_vat", "ten": "Quy đầu âm vật", "kieu": "text"}, {"ma": "tien_dinh_am_ho", "ten": "Tiền đình âm hộ", "kieu": "text"}, {"ma": "test_ran", "ten": "Test rặn", "kieu": "text"}, {"ma": "co_luc_am_dao_theo_oxford_cai_tien", "ten": "Cơ lực âm đạo theo Oxford cải tiến", "kieu": "text", "goi_y": "Độ"}]}, {"ma": "de_nghi", "ten": "Đề nghị", "block": [{"ma": "de_nghi", "ten": "Đề nghị / lời dặn", "kieu": "doan_van"}]}]$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;
