-- Danh mục vị trí trực đọc từ DATABASE, không từ TSX (CORE-C4, 23/09/2026).
--
-- Bảng lịch làm việc (trang chủ, lịch chính thức, bảng xếp ca) và màn phạm vi
-- vị trí trước nay đọc 34 vị trí viết cứng trong `src/dashboard/lib/roster.ts`,
-- trong khi database đã có `vi_tri_lam_viec` từ 16/09. Hai nguồn cho một danh
-- mục: quản lý thêm/đổi một vị trí thì bảng lịch không biết.
--
-- Thứ duy nhất TSX có mà database chưa có là NHÃN HÀNG — chữ in ở đầu mỗi hàng
-- bảng lịch, đúng như file Excel (dưới "Phòng thủ thuật" chỉ ghi "BS", không
-- ghi lại "BS thủ thuật"). Thêm cột `ten_ngan`, chép đúng nhãn đang hiện, để
-- bảng lịch không đổi mặt sau khi chuyển nguồn. Trống = dùng `ten`.

ALTER TABLE public.vi_tri_lam_viec
    ADD COLUMN IF NOT EXISTS ten_ngan text;

COMMENT ON COLUMN public.vi_tri_lam_viec.ten_ngan IS
'Nhãn in ở đầu hàng bảng lịch làm việc (theo file Excel xếp lịch). Trống = dùng ten.';

UPDATE public.vi_tri_lam_viec v
   SET ten_ngan = n.ten_ngan
  FROM (VALUES
    ('T1_DOCHISO', 'Đo chỉ số sức khoẻ (HA, MĐX, test nước tiểu), dịch cơ thể'),
    ('T1_TT_BS', 'BS'),
    ('T1_TT_DD', 'Điều dưỡng'),
    ('T1_TT_TK', 'Thư ký'),
    ('T1_SA_BS', 'BS'),
    ('T1_SA_DD', 'Điều dưỡng'),
    ('T1_SA_TK', 'Thư ký'),
    ('T1_TTNG_BS', 'BS'),
    ('T1_TTNG_DD1', 'Điều dưỡng 1'),
    ('T1_TTNG_DD2', 'Điều dưỡng 2'),
    ('T1_TTNG_TK', 'Thư ký'),
    ('T4_SANCHAU_TK', 'Thư ký'),
    ('T4_SANCHAU_BSTT', 'BS Thủ thuật (soi âm hộ/âm vật/CTC, nong/tách bao quy đầu âm vật)'),
    ('T4_SANCHAU_TKTT', 'Thư ký'),
    ('T4_SANCHAU_DD', 'Điều dưỡng Sàn chậu (Phụ khám Sàn chậu, Ghế Starformer, Thủ thuật)'),
    ('T4_SAN_TK', 'Thư ký'),
    ('T4_SA_BS1', 'BS 1'),
    ('T4_SA_DD1', 'Điều dưỡng 1'),
    ('T4_SA_TK1', 'Thư ký'),
    ('T4_SA_BS2', 'BS 2'),
    ('T4_SA_DD2', 'Điều dưỡng 2'),
    ('T4_SA_TK2', 'Thư ký'),
    ('DIEU_PHOI', 'Trưởng ca')
       ) AS n(code, ten_ngan)
 WHERE v.code = n.code AND v.ten_ngan IS NULL;
