# Kế hoạch: Kho thuốc · Quầy thuốc · Vật tư (chờ Tuyền duyệt)

> 27/10/2026. Yêu cầu: `docs/DE-BAI-KHO-THUOC-QUAY-VAT-TU.md` mục 6 (đã chốt).
> Hiện trạng đọc từ `origin/main` 9dcba2ea + `origin/dot/2710` (PR #543 giao tự chọn
> lô, #546 chặn trừ sai tồn — chưa lên prod). Mức 3: migration, tiền, kho.
> **Duyệt xong mới code.** Mỗi đợt một nhánh, một PR, một dải giờ migration.

## 1. Ba quyết định mô hình (đề xuất)

**Q-A · Nhiều quầy = thêm `drug_batch.room_id`, giữ cờ `noi_chua`.**
Kho cơ sở: `noi_chua='KHO'`, `room_id` rỗng. Quầy: `noi_chua='QUAY'`, `room_id` = phòng
quầy. Mọi bất biến hiện chạy theo từng hàng `drug_batch.id` (tồn ≥ 0, tồn = cộng dồn
sổ, `drug_batch_kha_dung`, khoá ngoại của phân lô/trả/phiếu) — giữ nguyên, không viết
lại lõi tiền–kho. Phương án bảng tồn riêng (kiểu vật tư) phải viết lại
`inventory_txn_apply` + `drug_batch_kha_dung` + ~26 chỗ `quantity_on_hand` → loại.
- Phòng là quầy: cột mới `clinic_room.la_quay_thuoc` (bật trên màn cấu trúc phòng).
- Người bán đang ở quầy nào: lịch hôm nay `work_roster → vi_tri_lam_viec.room_id`
  (cách `bac_si_phu_trach` đang làm). Không có lịch / đứng 2 quầy → màn hỏi một lần,
  nhớ cho phiên. Cơ sở chỉ có 1 quầy → tự là quầy đó.
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
tiền tính theo đơn vị bán. Dòng cũ: hệ số rỗng = 1, không đổi nghĩa. Đổi hệ số khi đã có
đơn dùng → bị chặn (ngừng đơn vị cũ, tạo đơn vị mới); đổi giá có vết.

## 2. Đợt (thứ tự đề xuất: rủi ro thấp trước)

| Đợt | Gồm | Migration | Mức |
|---|---|---|---|
| **1 · Báo cáo chỉ đọc** | Tồn có giá trị + "nhập ngày … · N ngày" + tồn lâu > 90 ngày; XNT tách kho/quầy/lô; cận/quá hạn có giá trị; doanh số theo thuốc nhiều ngày; màn **"Kho hôm nay"** gom cảnh báo; lọc ngày (T9); Excel xlsx qua `excel_export` có sẵn | không | 2 |
| **2 · Thời gian thực** | Trigger `notify_row_change` cho `phieu_kho`, `inventory_txn` (chỉ INSERT), `thuoc_giao_chua_gan_lo`, `drug_return`, `kiem_ke_ca_dong`; màn kho/quầy nghe bằng `useNgheBang`. KHÔNG thêm vào `LIVE_TABLES` chung (đo 17/10: 1 lượt ghi dựng lại 7–10 trang) | có, nhỏ | 3 |
| **3 · Kiểm ca** | Lý do lệch theo từng thuốc (chọn sẵn + gõ tự do) và "đã xem" của quản lý — **bảng riêng**, không nới trigger bất biến của phiếu đã chốt; danh sách nhiều ngày/mọi ca; báo cáo ca thêm: nhận từ kho (tách khỏi nhập), khách trả kèm hoàn tiền mặt/CK/đổi/giữ lại + số tiền (đọc `drug_return → payment_refund`), còn trong kho; Excel | có | 3 |
| **4 · Kho→quầy nhiều quầy** | Q-A + Q-B; lego mới **"Chuyển thuốc kho→quầy"** (chỉ Quản lý cấp); chuyển một bước, FEFO đề xuất sửa được, hoàn tác = phiếu ngược (đã có); bán trừ quầy của người bán; bán tạm bắt lý do, nhắc 1 giờ, gợi ý phiếu bù, đếm theo nhân viên; kiểm ca theo từng quầy; gắn lại màn chuyển (`ChuyenKho.tsx` đang mồ côi). Diễn tập trên bản sao prod | có | 3 |
| **5 · Vật tư** | Danh mục NCC + `so_chung_tu` trên phiếu (nới CHECK hiện chỉ cho NCC ở phiếu trả); dòng nhập: hãng · tình trạng · số lô · hạn (**chỉ ghi để tra**, tồn không tách theo lô); bán vật tư **trừ kho** (loại phiếu `BAN`, `luot_vat_tu.room_id`, trừ lúc thêm/đổi/bỏ dòng — cả đường quầy thu lẫn đường Bio); VTYT tuỳ chọn ghi dùng cho khách (`DUNG`); VPP theo dõi ở phòng; màn tổng quan vật tư kiểu Phòng dịch vụ; báo cáo vật tư + Excel. Trường mới phải đi qua đường "nhập chờ duyệt" | có | 3 |
| **6 · Nhiều đơn vị + giá** | Q-C; kê đơn chọn đơn vị; quầy/bán lẻ; hoá đơn; giao trừ theo hệ số; trả thuốc; báo cáo; kiểm ca nhập "2 hộp + 3 viên" quy về gốc. Giả lập tiền ≥20 hạt trước khi code | có | 3 (rủi ro tiền cao nhất) |
| **7 · Hướng dẫn ảnh thật** | Sau khi 1–6 lên staging: trang web + PDF, lớp người dùng + lớp kỹ thuật | — | 1 |

**Việc dữ liệu làm ngay, không cần code:** cận hạn 3 tháng = Kho thuốc → "Cảnh báo
trước hạn (số ngày)" → nhập **90** → Lưu (mặc định đang 60).

## 3. Cần Tuyền chốt trước đợt tương ứng (kèm ví dụ số)

**Đợt 4**
1. Người bán không có lịch ở quầy nào hôm nay (vd quản lý đứng bán hộ) → **đề xuất:** màn hỏi "bán từ quầy nào", nhớ cho phiên. `…`

**Đợt 5**
2. "Thiếu" ở tình trạng nhập nghĩa là gì? Vd phiếu ghi 100 cái, đếm được 95: (a) nhập 95 + ghi "thiếu 5 so với chứng từ"; (b) nhập 100 rồi điều chỉnh −5. **Đề xuất (a).** `…`
3. Bán vật tư theo lượt (không gắn chỉ định) mà lượt có 2 phòng làm dịch vụ → trừ phòng nào? **Đề xuất:** quầy thu chọn phòng (mặc định phòng có chỉ định gần nhất); không chọn → kho cơ sở + ghi chú. `…`

**Đợt 6** (ví dụ: 1 hộp = 10 viên; hộp 450.000đ; viên 50.000đ)
4. Bán 1 hộp, khách trả 3 viên → hoàn: (a) 3/10 × 450.000 = **135.000**; (b) 3 × 50.000 = 150.000; (c) không cho trả lẻ khỏi hộp. **Đề xuất (a)** (hoàn theo giá đã thu). `…`
5. Giá hộp có phải = 10 × giá viên? **Đề xuất:** khai tự do, màn cảnh báo khi giá lẻ rẻ hơn giá hộp quy ra. `…`
6. Khách mua "2,5 hộp"? **Đề xuất:** đơn vị lớn chỉ số nguyên; lẻ thì đổi sang viên. `…`
7. Bác sĩ kê đơn vị nào? **Đề xuất:** chọn trong các đơn vị "bán được", mặc định đơn vị mặc định; quầy đổi được lúc bán. `…`
8. Thuốc có lô lệch đơn vị (kho tính gói, nhập theo hộp): lấy `don_vi_ban` hiện tại làm gốc? **Đề xuất: có.** `…`

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
| Đổi hệ số/giá khi đơn chưa thu → tiền đổi | trigger chặn đổi hệ số đã dùng; giá theo lúc thu (như hiện nay) + vết |
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
