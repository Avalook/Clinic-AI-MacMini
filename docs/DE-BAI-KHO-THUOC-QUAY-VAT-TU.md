# Đề bài: Kho thuốc · Quầy thuốc · Kho vật tư + hướng dẫn có ảnh thật

> Soạn 27/10/2026 từ yêu cầu của Tuyền, đối chiếu code thật trên `main` (9dcba2ea).
> **Cách điền:** mỗi câu hỏi có chỗ `…` để điền. Câu nào có **[Mặc định]** mà
> bạn bỏ trống thì mình làm theo mặc định đó. Điền xong gửi lại là làm được ngay.
> Ký hiệu: ✅ đã có · 🟡 có nhưng thiếu/tắt · ❌ chưa có.

---

## 0. Hiểu ý bạn trong một hình

```
NHẬP (ngày, NCC, số lô, hạn, giá)
   │
   ▼
KHO ──[phiếu chuyển: ngày, ai giao, ai nhận, số lượng từng lô]──▶ QUẦY
   ▲                                                               │
   │                                     đầu ca: đếm từng thuốc ───┤
   │                                     bán: trừ vào số ở QUẦY ───┤
   │                    quầy hết vẫn bán TẠM (ghi lý do) ──────────┤
   └──── chuyển bù sau, nối với lần bán tạm ◀──────────────────────┘
                                         cuối ca: đếm lại, lệch → ghi chú
MỌI bước: ai · lúc nào · bao nhiêu · vì sao — xem lại được, hoàn tác được.
```

Vật tư cùng khuôn đó, nhưng **KHO → PHÒNG** thay cho **KHO → QUẦY**, cộng thêm
phần hãng / nhà cung cấp và nhóm **VTYT / Văn phòng phẩm**.

---

## 1. Hiện trạng: đã có gì, thiếu gì (đọc code thật)

### Thuốc

| Khâu | Trạng thái | Ghi chú |
|---|---|---|
| Nhập thuốc vào kho (phiếu nhập, lô, hạn, NCC, giá, quy đổi hộp→viên) | ✅ | Nhập nhầm chưa hoàn tác được: phải điều chỉnh tay |
| Xem tồn theo thuốc / theo lô | ✅ | Thẻ kho chưa lọc ngày, chưa có Excel |
| Số ngày từ lúc nhập đến nay | ❌ | Có ngày nhập (`received_at`) nhưng chưa hiện "nhập 23 ngày trước" |
| Lọc theo ngày/tháng/năm | 🟡 | Xuất–nhập–tồn có lọc kỳ; tồn kho và thẻ kho chưa có |
| Tách KHO / QUẦY, phiếu chuyển kho→quầy | 🟡 | Máy chủ có đủ, nhưng **màn đã gỡ 18/10 và công tắc đang tắt** |
| Báo cáo chuyển kho→quầy theo ngày | ❌ | |
| Kiểm quầy đầu ca / cuối ca (đếm mù, chốt, lệch, ghi chú, điều chỉnh, hoàn tác) | ✅ | Mới xem từng ngày, chưa có lịch sử lệch nhiều ngày |
| Bán trừ vào số ở quầy | 🟡 | Đang trừ vào tồn chung (chưa tách quầy) |
| Quầy hết vẫn bán tạm, bù sau | ✅ | "Giao trước, gán lô sau"; **chưa bắt ghi lý do**, chưa nối với phiếu chuyển bù |
| Số tồn tự cập nhật khi người khác nhập/bán | ❌ | Bảng kho không phát tin thời gian thực |
| Chặn trừ sai tồn (kiểm kho khi còn chờ gán lô, huỷ lấn phần đã bán) | ✅ | PR #546 (đợt A), đang lên staging |

### Vật tư

| Khâu | Trạng thái | Ghi chú |
|---|---|---|
| Danh mục, nhóm **VTYT / VPP**, đơn vị, giá nhập | ✅ | |
| Phiếu nhập · cấp phòng · trả kho · chuyển phòng · kiểm · điều chỉnh · huỷ · hoàn tác | ✅ | Sổ chỉ ghi thêm |
| Duyệt nhập hàng "cần duyệt" | ✅ | |
| Tồn theo kho cơ sở và từng phòng, mức tối thiểu, nhắc | ✅ | Tồn âm chỉ cảnh báo, không chặn (Quang chốt 17/10) |
| Báo cáo tiêu hao theo phòng × kỳ (đầu + nhận − trả − cuối) | ✅ | |
| **Hãng / nhà cung cấp** của lần nhập | ❌ | Tên NCC hiện **chỉ** ghi được ở phiếu *trả* NCC; phiếu nhập bị ràng buộc không cho ghi |
| Lô / hạn dùng của vật tư | ❌ | |
| "Tình trạng lúc nhập" (đủ / thiếu / hỏng…) | ❌ | |
| Bán vật tư cho khách thì **trừ kho** | ❌ | Đang bán ở quầy thu nhưng sổ kho không trừ |
| Trả nhà cung cấp (kèm tên NCC) | ✅ | Có từ 18/10 |

---

## 2. Câu hỏi: THUỐC

**T1. Tách kho / quầy.**
- Cách 1: một số tồn chung, chuyển kho→quầy chỉ để ghi nhận.
- Cách 2: hai số riêng (kho có X, quầy có Y), bán chỉ trừ ở quầy.

Theo lời bạn thì là **cách 2**. Chốt: **[cách 2]**
Áp cho cơ sở:  **Hào Nam trước, Kim Ngưu sau**

**T2. Mỗi cơ sở có mấy quầy thuốc?** Ví dụ: chỉ "Thu ngân thuốc tầng 5", hay thêm quầy tầng 2.
linh hoạt theo lego, 1 cũng được, 2 cũng được tuỳ cấu trúc phòng của cơ sở

**T3. Chuyển kho → quầy làm mấy bước?**
- (a) Một bước: kho bấm chuyển là quầy có hàng.
- (b) Hai bước: kho xuất, quầy đếm rồi bấm "đã nhận". Lệch thì ghi lý do. Ví dụ: kho xuất 10 hộp Femoston, quầy đếm được 9, ghi "thiếu 1 hộp, rơi vỡ".

Chọn: 1 bước thôithôiôiôiô, kiểm lại là khi kiểm đầu ca cuối ca thôi,thô vì đẫ từ kho sang quầy rồi thì nhầm gì nữa, hoạt nếu có tính sau
Ai được chuyển: tôi tính tuỳ theo quản lý cho ai được quyền chuyển thuốc từ kho ra quầy, cái này thêm nút và quyền cho quản lý

**T4. Chuyển theo lô nào?**
- (a) Máy tự lấy lô hết hạn sớm nhất (FEFO), sửa tay được.
- (b) Luôn quét / chọn lô.

Chọn: a

**T5. Kiểm quầy đầu ca và cuối ca.**
- Đếm **mù** (không thấy số máy, như hiện nay) hay **thấy** số máy: chưa hiểu
- Đếm thuốc nào: tất cả thuốc đang có ở quầy / chỉ thuốc đã bán trong ca / danh sách cố định: muốn đếm rõ ra đủ báo cáo, thuốc đã bán, chênh lệch nhập tay, thuốc còn lại trong kho, còn có cả thuốc khách trả lại mình phải trả tiền ấy, trả lại còn lại ghi rõ là trả lại bằng tienef mặt hay chuyển khoản, số là bao nhiêu ghi rõ ( trong phần thanh toán dịch vụ có logic này rồi tuỳ thết kế của ban sao cho tối uuw khi dùng laịhoajc clone)
- Các ca: **[Mặc định: theo giờ ca đang cài: sáng / chiều / tối]**
- Có được bỏ qua đầu ca không (đầu ca = cuối ca trước): có nút lấy số cuối ca truóc cho lẹ nếu userr chắc căhns khôngkhasc nhiều **[Mặc định: được, lấy số cuối ca trước làm đầu ca]**

**T6. Lệch cuối ca: khi nào cần quản lý duyệt?**
Ví dụ: cuối ca máy còn 20 viên, đếm được 18, lệch −2 viên (khoảng 30.000đ).
- Ngưỡng cần duyệt: phải báo cáo hết, cuối ca nào cũng báo cáo, thông tin đồng bộ hết về cho quản lý xem đuọc, chỗ cuối ca thì cũng phỉa có xuất exxxxcel **[Mặc định: mọi lệch đều cần ghi chú; ≥ 100.000đ cần Quản lý duyệt]**
- Lý do chọn sẵn (thêm/bớt): bán nhanh chưa kịp ghi · đếm nhầm ca trước · rơi vỡ · trả khách chưa nhập · cũng được nhưng cũng có freetext

**T7. Quầy hết mà vẫn bán tạm.**
- Bắt ghi lý do lúc bán: **[Mặc định: có, không cần chọn nhanh: "lấy tạm từ kho" / "hộp chưa nhập máy" / "khác…", cuối ca có báo cáo tưng thuốc đã bán mà không có ở quầy vì hết, cho nhập bổ sung, cũng lấy từ kho luôn, khi nhập từ kho sang quầy tự fill vào đủ thì hết cảnh báo, số cảnh báo này nhắc nhở nhân viên đó]**
- Sau đó bù bằng phiếu chuyển kho→quầy. Máy tự gợi ý phiếu bù gồm đúng các thuốc đã bán tạm:  **[Mặc định: có]**
- Bán tạm quá bao lâu chưa bù thì nhắc: nhắc 1 giờ **[Mặc định: cuối ca]**

**T8. "Số ngày đã nhập".** Tính từ ngày nhập lô đến hôm nay, ví dụ "Lô A123 · nhập 05/10 · 22 ngày".
- Nhắc "tồn lâu / chậm bán" khi quá ngày **[Mặc định: 90 ngày]**
- Nhắc cận hạn trước 3 ngày **[Mặc định: đang có cài đặt, giữ nguyên]**

**T9. Lọc ngày / tháng / năm ở các màn nào?** đánh x:
- [x] Tồn kho theo lô (lọc theo **ngày nhập**)
- [x] Thẻ kho từng thuốc (lọc theo **ngày phát sinh**)
- [x] Báo cáo chuyển kho→quầy
- [x] Kiểm ca (nhiều ngày)
- [x] Khác: `…`

**T10. Đơn vị trong báo cáo:** đơn vị bán (viên/gói) · hộp · cả hai: cả đi, cho sửa được luôn, sửa được giá theo loại đơn vị luôn, 1 thuốc có thể có nhiều loại đơn vị luôn, người dùng có thể nhập và thiết lập thêm **[Mặc định: đơn vị bán, kèm quy ra hộp nếu đã khai]**

**T11. Xuất Excel** cho báo cáo nào:  **[Mặc định: mọi báo cáo kho]**

---

## 3. Câu hỏi: VẬT TƯ

**V1. Nhập vật tư cần ghi gì?** Tick x, không điền hết cũng không sao:
- [x] Hãng sản xuất (ví dụ: B. Braun)
- [x] Nhà cung cấp (ví dụ: Công ty TBYT Minh Anh)
- [x] Số hoá đơn / chứng từ
- [x] Số lô + hạn dùng (chỉ VTYT? cả VPP?): 
- [x] Tình trạng lúc nhập: đủ · thiếu · hỏng · đổi trả ·
- [x] Khác: `…`

Hãng và NCC gõ tự do hay chọn trong danh sách có sẵn (thêm mới được):  **[Mặc định: chọn trong danh sách, thêm mới được]**

**V2. Bán vật tư cho khách** (đầu dò Bio, vòng…) **trừ kho nào?**
- (a) Kho của phòng làm dịch vụ
- (b) Kho cơ sở
- (c) Không trừ (như hiện nay)

Chọn:  **[Mặc định: (a); phòng chưa có thì trừ kho cơ sở và ghi chú, xử lý như ở kho thuốc ấy]**

làm thêm cái giao diện tổng quan như giao diện phòng dịch vụ đang có, khác là hiển thị luôn số vật tư đang có ở từng phòng

**V3. Dùng vật tư ở phòng ghi thế nào?**
- (a) Chỉ đếm cuối ngày/kỳ, máy tính tiêu hao (như hiện nay).
- (b) Ghi từng lần dùng cho khách nào.

Chọn:  **[Mặc định: (a) cho VPP; VTYT thì bạn thấy thêm được gì càng tốt, càng kĩ càng tốt, nưhgn không bất buộc điền]**

**V4. Văn phòng phẩm** có theo dõi tồn ở phòng không, hay xuất kho là coi như dùng hết: theo dõi hết đừng để lạc mất đồ nào 

**V5. Trả lại.** Tick x:
- [x] Phòng trả kho (đang có), bắt lý do không bắt buộc
- [x] Trả nhà cung cấp (đã có): giữ như cũ hay bắt thêm số chứng từ: không thêm số chứng từ cũng được 

**V6. Chênh lệch vật tư** cần quản lý duyệt khi ≥ `…` đơn vị / ≥ `…` đồng **[Mặc định: ghi chú bắt buộc, không cần duyệt]**

---

## 4. Báo cáo cần xem (tick cái cần, thêm cột nếu thiếu)

- [x] **Tồn hiện tại**: thuốc × kho/quầy × lô × hạn × ngày nhập × số ngày đã nhập × giá trị
- [x] **Xuất–nhập–tồn** theo kỳ, tách kho / quầy, tách lô
- [x] **Chuyển kho→quầy theo ngày**: từng phiếu, từng thuốc, ai giao, ai nhận, lệch
- [x] **Quầy theo ca**: đầu ca · nhận thêm · bán · cuối ca · lệch · ghi chú · người đếm
- [x] **Bán tạm khi quầy hết**: thuốc · số · lý do · đã bù chưa · bù bằng phiếu nào
- [x] **Doanh số theo thuốc** nhiều ngày (bán chạy / chậm bán)
- [x] **Cận hạn / quá hạn** kèm giá trị
- [x] **Vật tư**: nhập theo hãng / NCC · cấp phòng · còn lại theo phòng · đã dùng · đã bán · trả · lệch có lý do · tách VTYT / VPP
- [x] **Màn tổng quan "Kho hôm nay"** gom cảnh báo về một chỗ: sắp hết · cận hạn · chờ gán lô · trả chờ kiểm · lệch ca · bán tạm chưa bù
- [x] Khác: `…`

---

## 5. Hướng dẫn có ảnh thật

- Cho ai đọc: dược sĩ / thu ngân thuốc · thủ kho · điều dưỡng phòng · quản lý: cho cả team làm ra hệ thóng đọc nữa
- Dạng: trang web xem trên điện thoại · PDF in ra · cả hai: `…` **[Mặc định: trang web + PDF]**
- Chụp ở đâu: **staging**, dữ liệu khách `DEMO-*`, cỡ 1280 và điện thoại 375.
- Mỗi việc một mục: *mở màn nào → bấm gì → thấy gì* (ảnh có khoanh chỗ bấm), cuối mục ghi "nếu sai thì hoàn tác thế nào".
- Danh sách mục **[Mặc định]**:
  1. Nhập thuốc (phiếu nhập, quy đổi hộp→viên, in tem lô)
  2. Xem tồn theo thuốc / lô, lọc ngày, số ngày đã nhập
  3. Chuyển kho → quầy (giao, nhận, lệch)
  4. Kiểm đầu ca / cuối ca, ghi chú lệch
  5. Bán / giao thuốc, bán tạm khi quầy hết, bù sau
  6. Khách trả thuốc, huỷ thuốc hỏng / hết hạn
  7. Báo cáo kho thuốc (từng báo cáo một)
  8. Nhập vật tư (hãng, NCC, tình trạng)
  9. Cấp vật tư cho phòng, phòng trả kho, đếm cuối kỳ
  10. Báo cáo vật tư
  11. Thêm mục: `…`
- Chụp **sau khi** làm xong các đợt dưới đây (chụp màn cũ rồi lại phải chụp lại là phí).

---

## 6. Chốt từ câu trả lời (27/10, Tuyền điền)

**Còn 2 chỗ cần Tuyền xác nhận một chữ** (chưa xác nhận thì AI làm theo chữ in đậm):
- T8 nhắc cận hạn "trước 3 ngày": **3 THÁNG** (3 ngày quá sát với thuốc). Đúng 3 ngày thì sửa ở đây: `…`
- T6 lệch cuối ca: mọi lệch bắt ghi chú, báo đủ về quản lý. **Không có ngưỡng chặn chờ duyệt**; quản lý xem và đánh dấu "đã xem". Muốn có ngưỡng duyệt thì ghi: `…`

**Đã chốt:**

| # | Chốt |
|---|---|
| T1 | Cách 2: hai số riêng KHO / QUẦY, bán trừ ở quầy. Hào Nam trước, Kim Ngưu sau (công tắc theo cơ sở) |
| T2 | Số quầy **linh hoạt**: mỗi quầy là một phòng loại "quầy thuốc" trong cấu trúc phòng của cơ sở (1 hay 2 đều được). Nơi chứa thuốc = kho cơ sở + các phòng quầy |
| T3 | Chuyển **một bước**: kho bấm chuyển thì quầy có hàng ngay. Kiểm lại ở đếm đầu/cuối ca. Quyền chuyển là **lego mới** (ví dụ "Chuyển thuốc kho→quầy"), Quản lý cấp cho ai thì người đó được bấm |
| T4 | Máy tự chọn lô hết hạn sớm nhất (FEFO), sửa tay được |
| T5 | Đếm mù như hiện nay. Báo cáo ca gồm từng thuốc: đầu ca · nhận từ kho · đã bán · khách trả (kèm **hoàn tiền mặt / chuyển khoản / đổi / giữ lại, số tiền**, đọc từ sổ trả thuốc có sẵn) · cuối ca đếm · lệch · ghi chú, kèm số còn trong kho. Nút **"Lấy số cuối ca trước"** điền nhanh đầu ca |
| T6 | Mọi ca đều có báo cáo, đồng bộ cho quản lý xem, **xuất Excel**. Lý do lệch: chọn sẵn (bán nhanh chưa kịp ghi · đếm nhầm ca trước · rơi vỡ · trả khách chưa nhập) **+ ô gõ tự do** |
| T7 | Quầy hết vẫn bán tạm, **bắt ghi lý do** (gõ tự do được). Sau **1 giờ** chưa bù thì nhắc. Cuối ca có báo cáo "đã bán mà quầy không có". Máy gợi ý phiếu chuyển bù đúng các thuốc ấy; chuyển đủ thì cảnh báo tự tắt. Đếm số lần bán tạm chưa bù **theo nhân viên** để nhắc |
| T8 | Hiện "nhập ngày … · N ngày". Nhắc tồn lâu sau **90 ngày**. Cận hạn: xem dòng xác nhận ở trên |
| T9 | Lọc ngày/tháng/năm ở: tồn theo lô (ngày nhập), thẻ kho (ngày phát sinh), chuyển kho→quầy, kiểm ca nhiều ngày |
| T10 | **Một thuốc nhiều đơn vị** (viên / vỉ / hộp…): người dùng tự thêm, mỗi đơn vị có hệ số quy đổi + **giá bán riêng**, sửa được. Báo cáo hiện cả đơn vị bán và quy đổi |
| T11 | Mọi báo cáo kho đều xuất Excel |
| V1 | Nhập vật tư ghi: hãng · NCC (chọn trong danh sách, thêm mới được) · số chứng từ · lô + hạn (**không bắt buộc**; mặc định hiện cho VTYT, ẩn với VPP) · tình trạng lúc nhập (đủ / thiếu / hỏng / đổi trả) |
| V2 | Bán vật tư trừ kho **phòng làm dịch vụ**; phòng không có thì trừ kho cơ sở và ghi chú (cùng kiểu "bán tạm" bên thuốc) |
| V2+ | **Màn tổng quan vật tư** giống màn Phòng dịch vụ: mỗi phòng một ô, hiện số vật tư đang có ở phòng |
| V3 | VPP: đếm cuối kỳ (như hiện nay). VTYT: thêm tuỳ chọn ghi từng lần dùng cho khách nào, **không bắt buộc** |
| V4 | Theo dõi tồn VPP ở từng phòng luôn, không coi "xuất là hết" |
| V5 | Phòng trả kho: lý do **không bắt buộc**. Trả NCC giữ như cũ |
| V6 | Chênh lệch vật tư: ghi chú bắt buộc, không cần duyệt |
| Báo cáo | Làm hết mục 4 |
| Hướng dẫn | Cho nhân viên **và** đội làm hệ thống. Hai lớp: (1) cách dùng có ảnh thật; (2) phần kỹ thuật: luồng dữ liệu, bảng, luật, test. Trang web + PDF |

---

## 7. PROMPT GIAO VIỆC (chép nguyên, dán cho AI)

```text
Đọc CLAUDE.md, docs/SO-LUAT.md, docs/BAN-DO-SUA.md (mục Kho thuốc, Tách KHO/QUẦY,
Kiểm kê ca, Vật tư, Lego/quyền) và docs/DE-BAI-KHO-THUOC-QUAY-VAT-TU.md — mục 6
"Chốt từ câu trả lời" là YÊU CẦU; mục 1 là hiện trạng đã đối chiếu code 27/10.

VIỆC: hoàn thiện vòng đời thuốc (nhập → kho → chuyển quầy → kiểm ca → bán → báo
cáo) và vật tư (nhập → kho → cấp phòng → dùng/bán/trả → báo cáo) đúng mục 6, rồi
viết hướng dẫn có ảnh thật (mục 5, hai lớp: người dùng + đội hệ thống).

TRƯỚC KHI CODE (mức 3 — Tuyền duyệt kế hoạch trước):
  1. Đọc code thật: pharmacy_service, kho_thuoc_service (chuyen_kho, hoan_tac_chuyen,
     dat_tach_kho_quay, kiem_kho), kiem_ke_ca_service, ban_thuoc_service,
     thuoc_giao_chua_gan_lo, drug_catalog (don_vi_ban, quy đổi), vat_tu_* (6 service),
     migration 20261014160000 (KHO/QUẦY), 20261014180000 + 20261018140000 (vật tư).
  2. Viết docs/KE-HOACH-KHO-QUAY-VAT-TU.md (≤2 trang): mô hình dữ liệu mới (đặc
     biệt T2 nhiều quầy = phòng — hiện `drug_batch.noi_chua` chỉ KHO/QUAY, mỗi lô tối
     đa 2 hàng; T10 nhiều đơn vị + giá theo đơn vị), migration nào, dữ liệu prod đang
     có đi đâu (tồn hiện tại thành tồn KHO hay QUẦY? diễn tập trên bản sao prod),
     thứ tự đợt, cái gì KHÔNG đổi. Dừng chờ Tuyền duyệt.

LÀM THEO ĐỢT — mỗi đợt một nhánh từ origin/main, một PR nháp, CI xanh, bấm thật
375/1280, kịch bản bấm thử cho người thật:
  B. Thời gian thực màn kho/quầy/vật tư: notify_row_change cho drug_batch,
     inventory_txn, phieu_kho, thuoc_giao_chua_gan_lo, drug_return, kiem_ke_ca*; CHỈ
     các màn kho nghe bằng useNgheBang (KHÔNG gắn RealtimeRefresher chung — đo
     17/10: 1 lượt ghi dựng lại 7–10 trang, gây lag prod).
  C. KHO/QUẦY (T1–T4, T7): quầy = phòng loại quầy thuốc (nhiều quầy); lego mới
     "Chuyển thuốc kho→quầy" (khai capability + preset Quản lý); phiếu chuyển một
     bước, FEFO sửa được, hoàn tác bằng phiếu đảo; bán trừ quầy; quầy hết → bán tạm
     bắt lý do → "chờ bù" (nối với thuoc_giao_chua_gan_lo), nhắc sau 1 giờ, gợi ý
     phiếu bù, đủ thì tự tắt; đếm bán-tạm-chưa-bù theo nhân viên. Gắn lại màn
     chuyển (ChuyenKho.tsx đang mồ côi) — tra SITEMAP, sửa đủ mọi lối.
  D. Kiểm ca (T5–T6): giữ đếm mù; báo cáo ca từng thuốc (đầu · nhận · bán · khách
     trả kèm HOAN/DOI/GIU_LAI + hinh_thuc + số tiền, ĐỌC từ sổ trả thuốc có sẵn ·
     cuối · lệch · ghi chú · còn trong kho); nút "Lấy số cuối ca trước"; lý do chọn
     sẵn + gõ tự do; quản lý xem mọi ca, đánh dấu đã xem; Excel; lịch sử nhiều ngày.
  E. Đơn vị (T10): nhiều đơn vị / thuốc, hệ số quy đổi, giá bán theo đơn vị, người
     dùng tự thêm/sửa (có vết: ai sửa, giá cũ → mới). Đơn thuốc/quầy bán đúng đơn vị;
     sổ kho vẫn một đơn vị gốc mỗi lô. Mức 3 — đụng giá: test giả lập tiền.
  F. Báo cáo + tổng quan (mục 4, T8, T9, T11): tồn hiện tại (kho/quầy × lô × hạn ×
     ngày nhập × số ngày × giá trị), XNT tách kho/quầy/lô, chuyển kho→quầy theo ngày,
     quầy theo ca, bán tạm, doanh số theo thuốc nhiều ngày (chạy/chậm), cận/quá hạn
     có giá trị, màn "Kho hôm nay" gom cảnh báo; nhắc tồn lâu 90 ngày; cận hạn theo
     mục 6; lọc ngày đúng T9; MỌI báo cáo xuất Excel; mỗi số bấm vào ra dòng sổ.
  G. Vật tư (V1–V6): hãng · NCC (danh mục, thêm mới được) · chứng từ · lô/hạn tuỳ
     chọn · tình trạng lúc nhập (migration; NCC ghi được ở phiếu NHẬP — hiện ràng buộc
     vat_tu_phieu chỉ cho ở TRA_NCC); bán vật tư (luot_vat_tu) TRỪ kho phòng làm dịch
     vụ, không có thì kho cơ sở + ghi chú; VPP theo dõi tồn ở phòng; VTYT tuỳ chọn ghi
     từng lần dùng cho khách; màn tổng quan vật tư kiểu màn Phòng dịch vụ (mỗi phòng
     một ô, số đang có); báo cáo vật tư mục 4 tách VTYT/VPP; lệch bắt ghi chú.
  H. Hướng dẫn (mục 5) SAU khi B–G lên staging: chụp staging, khách DEMO-*, 1280 +
     375, khoanh chỗ bấm; mỗi mục: mở màn nào → bấm gì → thấy gì → sai thì hoàn tác
     sao; lớp kỹ thuật: sơ đồ luồng, bảng, luật, test. Xuất trang web + PDF.

LUẬT PHẢI GIỮ:
  - Sổ kho/vật tư CHỈ GHI THÊM; hoàn tác bằng phiếu đảo; ghi ai · lúc · lý do.
  - Không khoá cứng: quầy hết vẫn bán tạm; vật tư tồn âm chỉ cảnh báo. Thuốc vẫn
    không âm theo lô (bán tạm đi qua "chờ bù/gán lô").
  - Đã có sẵn, đừng phá: chặn kiểm kho khi còn chờ gán lô & chặn huỷ lấn phần đã
    bán (PR #546); giao tự chọn lô FEFO (PR #543); thuốc trả chờ kiểm.
  - Luồng THU/HOÀN tiền thuốc KHÔNG đổi — báo cáo chỉ đọc.
  - Luật nghiệp vụ ở FastAPI/SQL, không trong TSX; bất biến tranh chấp ép ở Postgres.
  - Hàm nhận ngày trả rỗng thay vì ném + test đầu vào rác.
  - Thử ở Hào Nam trước (chỉ Hào Nam đang dùng).

CÁCH KIỂM mỗi đợt:
  - scripts/test-nhanh.sh: test liên quan + test giả lập ≥20 hạt × 12 bước với mô
    hình "kệ thật" độc lập với sổ (kho + mọi quầy + chờ bù = tồn sổ sau MỌI bước;
    tiền khi đụng giá), thử ngược (gỡ bản sửa → đỏ).
  - Worktree mới: `test -x .venv/bin/pytest && test -d src/dashboard/node_modules`
    trước ci-may (lỗi lặp 6 lần).
  - Bấm thật stack local 375/1280, vai dược sĩ, thủ kho, điều dưỡng phòng, quản lý.
  - ./scripts/ci-may.sh --bao-github (08:00–23:00).

KHÔNG ĐỤNG: dữ liệu prod, deploy, nạp/làm mới dữ liệu khi khách đang dùng; lệnh ghi
  VPS chỉ SOẠN cho Tuyền chạy.

ĐẦU RA mỗi đợt: PR nháp · đã đổi gì · kịch bản bấm thử · cái KHÔNG đổi · rủi ro còn
  lại · bảng "nút/link đã đụng" (màn → nút → API → vai thấy).
```
