# Kế hoạch: Kho thuốc · Quầy thuốc · Vật tư

> 27/10/2026. Yêu cầu: `docs/DE-BAI-KHO-THUOC-QUAY-VAT-TU.md` mục 6 (đã chốt).
> Hiện trạng đọc từ `origin/main` 9dcba2ea + `origin/dot/2710` (PR #543 giao tự chọn
> lô, #546 chặn trừ sai tồn — chưa lên prod). Mức 3: migration, tiền, kho.
> **Duyệt xong mới code.** Mỗi đợt một nhánh, một PR, một dải giờ migration.

## 1. Ba quyết định mô hình

**Q-A · Nhiều quầy = thêm `drug_batch.room_id`, giữ cờ `noi_chua`.**
Kho cơ sở: `noi_chua='KHO'`, `room_id` rỗng. Quầy: `noi_chua='QUAY'`, `room_id` = phòng
quầy. Mọi bất biến hiện chạy theo từng hàng `drug_batch.id` (tồn ≥ 0, tồn = cộng dồn
sổ, `drug_batch_kha_dung`, khoá ngoại của phân lô/trả/phiếu) — giữ nguyên, không viết
lại lõi tiền–kho. Phương án bảng tồn riêng (kiểu vật tư) phải viết lại
`inventory_txn_apply` + `drug_batch_kha_dung` + ~26 chỗ `quantity_on_hand` → loại.
- Phòng là quầy: cột mới `clinic_room.la_quay_thuoc` (bật trên màn cấu trúc phòng).
- Người bán đang ở quầy nào: lịch hôm nay `work_roster → vi_tri_lam_viec.room_id`
  (cách `bac_si_phu_trach` đang làm) — quầy đi theo vị trí thu ngân thuốc. **Không
  hỏi** (Tuyền 27/10): cơ sở có một quầy thì mọi lần bán trừ quầy đó; nhiều quầy thì
  theo lịch, không có lịch thì quầy đầu tiên của cơ sở + ghi chú trong sổ.
- Tồn quầy đang có (`room_id` rỗng) → gán vào quầy duy nhất của cơ sở lúc bật. Sau
  dọn lô mẫu, prod gần như không có tồn thật nên gần như không có gì để dời.

**Q-B · "Chờ bù" dùng lại sổ `thuoc_giao_chua_gan_lo`** (đang là "giao trước, gán lô
sau"), thêm `room_id` + `ly_do`. Chuyển kho→quầy có thuốc đang chờ bù thì máy đề xuất
gán luôn; gán đủ thì cảnh báo tắt. Nhắc sau 1 giờ đi qua bộ canh gác mỗi phút có sẵn.

**Q-C · Nhiều đơn vị + giá theo đơn vị = bảng mới `thuoc_don_vi`.**
`(thuốc, đơn vị, hệ số về đơn vị gốc, giá bán, bán được, nhập được, mặc định, đang dùng)`.
Đơn vị gốc vẫn là `drug_catalog.don_vi_ban` + `unit_price` (không thêm nguồn giá thứ
ba). Hệ số **đóng băng** trên dòng đơn (`prescription.he_so_goc`) và trên ảnh hoá đơn
lúc thu (`payment_bill_line.he_so_goc`). Kho và giao luôn tính theo đơn vị gốc của lô;
tiền tính theo đơn vị bán. Dòng cũ: hệ số rỗng = 1, không đổi nghĩa. **Không khoá
chặt** (Tuyền 27/10): sửa hệ số / giá / đơn vị gốc lúc nào cũng được, chỉ áp cho dòng
mới (dòng cũ đã đóng băng nên không đổi tiền), mọi lần sửa có vết.

## 2. Đợt (thứ tự đề xuất: rủi ro thấp trước)

| Đợt | Gồm | Migration | Mức |
|---|---|---|---|
| **1 · Báo cáo chỉ đọc** | Tồn có giá trị + "nhập ngày … · N ngày" + tồn lâu > 90 ngày; XNT tách kho/quầy/lô; cận/quá hạn có giá trị; doanh số theo thuốc nhiều ngày; màn **"Kho hôm nay"** gom cảnh báo; lọc ngày (T9); Excel xlsx qua `excel_export` có sẵn | không | 2 |
| **2 · Thời gian thực** | Trigger `notify_row_change` cho `phieu_kho`, `inventory_txn` (chỉ INSERT), `thuoc_giao_chua_gan_lo`, `drug_return`, `kiem_ke_ca_dong`; màn kho/quầy nghe bằng `useNgheBang`. KHÔNG thêm vào `LIVE_TABLES` chung (đo 17/10: 1 lượt ghi dựng lại 7–10 trang) | có, nhỏ | 3 |
| **3 · Kiểm ca** | Lý do lệch theo từng thuốc (chọn sẵn + gõ tự do) và "đã xem" của quản lý — **bảng riêng**, không nới trigger bất biến của phiếu đã chốt; danh sách nhiều ngày/mọi ca; báo cáo ca thêm: nhận từ kho (tách khỏi nhập), khách trả kèm hoàn tiền mặt/CK/đổi/giữ lại + số tiền (đọc `drug_return → payment_refund`), còn trong kho; Excel | có | 3 |
| **4 · Kho→quầy nhiều quầy** | Q-A + Q-B; lego mới **"Chuyển thuốc kho→quầy"** (chỉ Quản lý cấp); chuyển một bước, FEFO đề xuất sửa được, hoàn tác = phiếu ngược (đã có); bán trừ quầy của người bán; bán tạm bắt lý do, nhắc 1 giờ, gợi ý phiếu bù, đếm theo nhân viên; kiểm ca theo từng quầy; gắn lại màn chuyển (`ChuyenKho.tsx` đang mồ côi). Diễn tập trên bản sao prod | có | 3 |
| **5 · Vật tư** | Danh mục NCC + `so_chung_tu` trên phiếu (nới CHECK hiện chỉ cho NCC ở phiếu trả); dòng nhập: hãng · tình trạng · số lô · hạn (**chỉ ghi để tra**, tồn không tách theo lô); bán vật tư **trừ kho ở chỗ thu ngân dịch vụ** (loại phiếu `BAN`, trừ lúc thêm/đổi/bỏ dòng — cả đường quầy thu lẫn đường Bio) + dòng báo cáo "khách · phòng khám · món · thu ở đâu · phòng đã giao (tuỳ chọn)"; VTYT tuỳ chọn ghi dùng cho khách (`DUNG`); VPP theo dõi ở phòng; màn tổng quan vật tư kiểu Phòng dịch vụ; báo cáo vật tư + Excel. Trường mới phải đi qua đường "nhập chờ duyệt" | có | 3 |
| **6 · Nhiều đơn vị + giá** | Q-C; kê đơn chọn đơn vị; quầy/bán lẻ; hoá đơn; giao trừ theo hệ số; trả thuốc; báo cáo; kiểm ca nhập "2 hộp + 3 viên" quy về gốc. Giả lập tiền ≥20 hạt trước khi code | có | 3 (rủi ro tiền cao nhất) |
| **7 · Hướng dẫn ảnh thật** | Sau khi 1–6 lên staging: trang web + PDF, lớp người dùng + lớp kỹ thuật | — | 1 |

**Việc dữ liệu làm ngay, không cần code:** cận hạn 3 tháng = Kho thuốc → "Cảnh báo
trước hạn (số ngày)" → nhập **90** → Lưu (mặc định đang 60).

## 3. Đã chốt (Tuyền trả lời 27/10)

| # | Câu | Chốt |
|---|---|---|
| 1 | Người bán không có lịch ở quầy | **Không hỏi.** Quầy đi theo thu ngân thuốc; cơ sở một quầy → trừ quầy đó; nhiều quầy → theo lịch xếp vào vị trí quầy |
| 2 | Nhập vật tư "thiếu" | **(a)** nhập theo số đếm được, ghi "thiếu N so với chứng từ" |
| 3 | Bán vật tư trừ kho nào | **Chưa tách phòng.** Bán thêm vật tư đang làm ở thu ngân dịch vụ → trừ ở **chỗ thu ngân dịch vụ** (chưa khai thì kho cơ sở). Báo cáo ghi rõ một dòng: *khách X · khám ở phòng Y · mua thêm đầu dò · thu ở thu ngân · [tuỳ chọn] phòng đã giao cho khách*. Bước "phòng đã giao" **không bắt buộc** nhưng ghi chú phải hiện ở báo cáo tổng quan cho quản lý. Bán tại phòng làm sau |
| 4 | Khách trả lẻ từ hộp | **(a)** hoàn theo giá đã thu: trả 3/10 viên của hộp 450.000đ → 135.000đ |
| 5 | Giá hộp vs giá viên | **Tự do**, gán giá nào bán giá đó, không cảnh báo |
| 6 | Mua "2,5 hộp" | **Không.** Mỗi đơn vị bán số nguyên; muốn lẻ thì thêm dòng chọn đơn vị viên |
| 7 | Bác sĩ kê đơn vị nào | **Tự do** trong các đơn vị bán được; quầy đổi được lúc bán |
| 8 | Đơn vị gốc của thuốc lệch | **Đơn vị bán hiện tại** làm gốc; **không khoá chặt** (sửa sau được, có vết) |

## 4. Không đổi

- Luồng THU / HOÀN tiền thuốc và vật tư (đợt 6 chỉ thêm hệ số trên dòng, công thức hoàn
  theo câu 4).
- Sổ chỉ ghi thêm; tồn thuốc không âm theo lô; vật tư tồn âm chỉ cảnh báo.
- Giao tự chọn lô FEFO (#543), chặn trừ sai tồn (#546), thuốc trả chờ kiểm, đếm mù,
  "Lấy số cuối ca trước" (đã có), báo cáo tiêu hao vật tư.
- Công tắc tách kho/quầy theo cơ sở: Hào Nam bật trước, Kim Ngưu sau.

## 5. Rủi ro và cách chặn

| Rủi ro | Chặn |
|---|---|
| Kiểm ca gộp 2 quầy, điều chỉnh sai quầy | thêm `room_id` vào 5 truy vấn kiểm ca; giả lập 2 quầy |
| Hai đường ghi `luot_vat_tu` (quầy thu, Bio) — sót một là lệch kho | gọi chung một hàm ghi sổ; test cả hai đường + hoàn tác thu |
| Phiếu `BAN` làm sai báo cáo tiêu hao | đọc lại `tinh_theo_moc` trước; test tiêu hao với phiếu bán |
| Đổi hệ số/giá khi đơn chưa thu → tiền đổi | không khoá (Tuyền chốt): hệ số đóng băng trên dòng đơn lúc kê, giá theo lúc thu (như hiện nay), mọi lần sửa có vết |
| Lỗ hổng sẵn có: hoá đơn nhân số lượng với giá đơn vị gốc dù dòng đơn ghi đơn vị khác | đo trên bản sao trước đợt 6 (SQL dưới), sửa trong đợt 6 |
| Thông báo realtime dồn dập | chỉ trigger INSERT ở sổ, chỉ màn kho nghe |

```sql
-- Đo trước đợt 6 (chỉ đọc, bản sao prod): dòng đơn có đơn vị khác đơn vị gốc
SELECT count(*) FROM prescription p JOIN drug_catalog c ON c.id = p.drug_catalog_id
 WHERE btrim(lower(p.unit)) <> btrim(lower(c.don_vi_ban));
```

## 6. Cách kiểm mỗi đợt

Test liên quan + test giả lập ≥20 hạt × 12 bước với mô hình "kệ thật" độc lập với sổ
(kho + từng quầy + chờ bù = tồn sổ sau mọi bước; tiền khi đụng giá), thử ngược (gỡ bản
sửa → đỏ); bấm thật local 375/1280 vai dược sĩ, thủ kho, điều dưỡng phòng, quản lý;
`ci-may.sh --bao-github`; migration diễn tập trên bản sao prod; lên staging theo đợt.
