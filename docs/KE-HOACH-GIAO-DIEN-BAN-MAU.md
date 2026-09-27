# Kế hoạch: giao diện Y HỆT bản mẫu (27/09/2026)

Nguồn: bản mẫu `~/Downloads/Dr4women-giao-dien-mau/` (Tuyền duyệt ~20 vòng ở phiên
"Tab và role view options"). Tuyền 27/09: *"làm cho đến khi giống được như giao diện
mà đoạn chat kia bàn giao… xem kĩ hết mà làm"*.

**Quyết định 27/09 (Tuyền):**
- Y HỆT bản mẫu — kể cả chỗ trái `DESIGN.md`: tên khách 22px, avatar đổi màu theo
  giới, đệm 20/10. Ghi NGOẠI LỆ vào DESIGN.md (mục "Ngoại lệ theo bản mẫu").
- Hoàn tất + In phiếu khám ở **chân cột phải** (dính), Hoàn tất = nút chính brand.
- Không chép CSS/JS bản mẫu: dựng lại bằng component thật + token.

Bảng đối chiếu đầy đủ từng màn (element → bản mẫu → thật file:line → dữ liệu) do trợ
lý soát 27/09 — tóm tắt ở dưới; chi tiết nằm trong lịch sử phiên, soi lại code trước
khi tin.

## Thứ tự làm (tác động thấy được trước) — ✅ xong · ⏳ đang · ☐ chưa

1. ✅ (27/09, đợt 1) **Thẻ khách + thẻ sinh hiệu dùng chung, bỏ lặp** (M). Bàn tư vấn chưa dùng (mục 8). `TheKhach`: avatar 56 tròn
   (nữ brand-50/brand-700, nam xanh), tên 22px/600 HOA + chip loại khám, "Nữ • 42 tuổi
   (1984)", 3 viên (Mã khách · SĐT · Khám dd/mm/yyyy), ô Cơ sở phải, 4 ô icon (Địa chỉ ·
   Bác sĩ · Kênh đặt · Người giới thiệu). `TheSinhHieu`: lưới ô surface-muted, nhãn đầy
   đủ + ĐƠN VỊ, đầu thẻ "Đo lúc HH:MM · người đo · chỉ xem (sửa ở Đo sinh hiệu)". Dùng
   ở phiếu khám + bàn tư vấn; bỏ đầu thẻ / dải sinh hiệu trùng ở Bàn khám.
   Máy chủ `doc_dau_phieu`: bác sĩ, kênh đặt, cơ sở của LƯỢT, người đo, nhãn + đơn vị.
2. ✅ (27/09, đợt 1) **Dòng kết quả khối 2** (L). Chữ "Lần n" thay "Lượt n" (lượt = lượt khám). Mỗi chỉ định một thẻ: tên 600 + mã SP; "Trên phiếu
   giấy: …"; chip một trục (Chờ thu · Đã thu — chờ làm · Đang làm · Có KQ) + chip mẫu
   (mẫu PDF / tự do / đối tác); giá; nút "Mở phiếu kết quả". **Tóm tắt LUÔN hiện** khi
   có KQ (2 cột, bỏ ô rỗng, ≤14 dòng), **hộp KẾT LUẬN** brand-50, ⤢ ở góc, khối "ẢNH ·
   VIDEO" có đếm, chồng giấy xoay. Gom theo lần (mới trên), đặt TRÊN danh mục, lọc bỏ
   thủ thuật. Máy chủ `ket_qua_chi_dinh`: ma_kiotviet, gia, da_thu, da_xem_luc.
3. ✅ (27/09, đợt 1) **Tiêu đề khối có số + thẻ con + cột phải** (M). Thêm: Bàn khám gập cột hàng chờ khi mở phiếu (<1536px) — nút "☰ Hàng chờ". Ô số 32 vuông bo 8 brand-600 +
   h2 22px + câu gợi ý; mỗi mục một thẻ trắng; cột phải có khung, ô số vuông, chip "N
   mới", In + Hoàn tất ở chân; màn hẹp: thanh nút dính trên.
4. ☐ **Danh mục tick kiểu phiếu giấy** (M). Luôn mở, lưới 3/2/1 cột; dòng 20px|1fr|auto;
   giá + chip mẫu; đã chỉ định lần trước tô brand đậm; nhóm "(danh mục phòng khám)" gom
   vào một `<details>` "Dịch vụ khác trong bảng giá".
5. ☐ **Ô số `components/ui/OSo`** (S) — text + inputMode decimal, lăn chuột chỉ khi
   focus (hiện `type=number` chặn "12 x 8", bước 1 làm "36.6" sai).
6. ☐ Ô nhập khối 1: chip tick / chip radio, ô ghi kèm cột phải, lưới 3 cột, ô số 96 +
   đơn vị (cần `don_vi` trong khung).
7. ☐ Bản in: phiếu khám đầu trang 2 bên + khối bệnh nhân riêng + in tóm tắt kết quả +
   tên bác sĩ ký; phiếu kết quả ẩn ô trống, ảnh trước, chia bên, giờ/chẩn đoán/mã.
8. ☐ Bàn tư vấn: TheKhach, "✎ Bác sĩ tư vấn · tự lưu", chip "N ô đã điền" + "đồng bộ
   bác sĩ chính", thanh dính đáy "Xong tư vấn — chuyển bác sĩ chính".
9. ☐ Đơn thuốc: cột Đơn giá, ĐVT chữ, dòng gõ tự do, chip hẹn 1 tuần/2 tuần/1 tháng/3 tháng.
10. ☐ Timeline: tông bản mẫu, nhãn viên, lăn/kéo/mờ mép/tự cuộn, bảng "Từng dịch vụ".
11. ☐ Phòng dịch vụ: thang chữ DESIGN, đầu dịch vụ (mã · giá · phút), form 2 cột.
12. ☐ Bác sĩ chính sửa ô tư vấn (quyền ở máy chủ).
13. ☐ Chip xem lại lần chỉ định cũ (chỉ xem).
14. ☐ Lightbox thành hộp giữa màn bo 16.

Mỗi mục: tra SITEMAP, sửa đủ lối (`/ban-kham`, `/tu-van`, `/print/phieu-kham`, `/phong`,
`/print/ket-qua`), bấm thật 375/768/1280, đối chiếu cạnh bản mẫu (mở `python3 -m
http.server 8791` trong thư mục bản mẫu).
