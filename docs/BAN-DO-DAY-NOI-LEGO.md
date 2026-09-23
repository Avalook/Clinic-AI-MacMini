# BẢN ĐỒ DÂY NỐI LEGO — để Tuyền duyệt TRƯỚC khi code

Bản nháp 23/09/2026. Mục đích: duyệt NGHĨA nghiệp vụ của từng dây nối trước khi
viết code (kỹ thuật *Event Storming*). Chuẩn mỗi khối: `docs/CHUAN-CAM-LEGO.md`.
Luồng chuẩn 11 bước: memory `luong-chuan-tuyen-2309.md`.

Ký hiệu hiện trạng: ✅ đã có ở sổ mới (`domain_event`) · 🟡 có nhưng chỉ ghi sổ cũ
hoặc gọi thẳng khối khác · ❌ chưa có · ◻︎ không cần event (cấu hình/CRUD có nhật ký,
đúng thesis: "cấu hình tĩnh dùng CRUD với audit log").

Cách đọc một dây: **Lệnh** (ai bấm) → khối ghi **state riêng** → phát **event** (sự
thật đã xảy ra) → **node nghe** làm việc của nó.

---

## BẢN CHỐT 24/09 — đọc phần này là đủ

Kể theo một khách thật cho dễ theo: **chị Lan**, đặt khám Nội tiết.

### Các dây của khối Hành trình (đánh số lại cho gọn)

- **H1 — Check-in khám thường → hàng tư vấn.** Chị Lan check-in, loại khám là 1 trong
  5 loại khám lõi → vào hàng chờ **bác sĩ tư vấn** (hàng chung, bác sĩ tư vấn nào rảnh
  thì nhận). Bác sĩ chính của chị thấy chị ngay nhưng ở dạng **"sắp tới — đang ở tư
  vấn"** (chỉ xem, không gọi được). Điều dưỡng thấy chị ở hàng đo sinh hiệu.
- **H2 — Check-in thủ thuật / sàn chậu → phòng.** Nếu lịch là thủ thuật hoặc sàn chậu:
  không qua tư vấn. Hệ thống tạo sẵn chỉ định theo lịch. Đã trả tiền ở lượt trước mà
  chưa làm → mang sang, vào thẳng hàng của phòng. Chưa trả → chờ lễ tân thu tiền (H4).
- **H3 — Tư vấn xong → bác sĩ chính.** Bác sĩ tư vấn bấm Xong (đã ghi vào chính bệnh án
  của lượt) → chị Lan vào **hàng chờ khám thật** của bác sĩ chính.
- **H4 — Trả tiền xong → tự xếp phòng.** Lễ tân thu tiền dịch vụ → hệ thống xếp chị vào
  phòng vắng nhất làm được dịch vụ đó (thay cho người vừa thu tiền, dùng quyền của người
  ấy). Ai có quyền điều phối đổi lại được bất cứ lúc nào, lần sau đè lần trước.
- **H5 — Phòng làm xong / có kết quả → bác sĩ chính.** Bác sĩ chính thấy "có kết quả
  mới", chị Lan vào hàng **đọc kết quả** của bác sĩ chính.
- **H6 — Khách về mà còn việc dở → CSKH theo dõi.** Chị Lan về (check-out hoặc bỏ về)
  mà còn kết quả chưa ai xem / kết quả chưa về → mở việc theo dõi cho CSKH.
- **H7 — Kết quả đối tác quá hạn → CSKH.** Quá hạn chưa về → việc CSKH gọi đối tác/khách.
- **H8 — Trả tiền xong quá 1 giờ chưa check-out → nhắc lễ tân** (chỉ nhắc, không tự đóng lượt).

**Chỉnh được trên màn (dây nghiệp vụ):** loại khám nào qua tư vấn (H1/H2) · bật/tắt tự
xếp phòng (H4) · các thời hạn (H6/H7: mấy ngày, H8: mấy giờ) · ai nhận chuông cho event
nào (vd tệp kết quả về → bác sĩ, thư ký, điều dưỡng, CSKH). **Khoá trong code (dây lõi):**
dòng thời gian, trách nhiệm tiền (không làm được mà đã thu tiền → việc đối soát).

### Đã làm — nhóm 1 + nhóm 2 (code, chưa deploy)

- **H1, H3** (nhóm 1): check-in → tư vấn (đo trước) → bác sĩ chính, qua khối Hành trình.
- **H2** (nhóm 2): check-in lịch "đi thẳng phòng" (`service_type.di_thang_phong`, bật
  sẵn cho THỦ THUẬT) → chỉ định chưa làm của lượt trước đi theo khách sang lượt mới
  (sự kiện `service_order.carried_over`), khách đi thẳng dịch vụ, không vào hàng bác sĩ.
  Chỉ định ĐÃ TRẢ mà chưa làm thì mang sang ở MỌI lượt và vào thẳng hàng phòng.
- **H4** (nhóm 2): lễ tân thu tiền dịch vụ (sự kiện `payment.service_collected`) → Hành
  trình xếp phòng vắng nhất thay người vừa thu, bằng quyền của người ấy (sự kiện
  `service.routed`, `tu_dong=true`). Lễ tân/ai có quyền điều phối đổi lại được.
- Thu tiền dịch vụ không đợi "khám xong"; màn thu ngân có ô "Khách làm dịch vụ nào?".
- Phòng bấm Bắt đầu khi phiên bác sĩ còn mở → khách "đợi quay lại" ở hàng bác sĩ; phòng
  xong → khách về hàng bác sĩ; bác sĩ bấm Bắt đầu lần nữa = khám tiếp.

**Chỗ Claude tự chốt khi làm nhóm 2 (Tuyền soát, sai thì nói một câu là đổi):**
1. Người thu KHÔNG có quyền điều phối (vd tài khoản "Thu ngân" riêng) → không tự xếp,
   để người có quyền xếp tay. Lễ tân có sẵn quyền điều phối nên lễ tân thu là tự xếp.
2. Thu tiền dịch vụ được ngay khi lượt ĐÃ CÓ chỉ định. Lượt chỉ có tiền khám (chưa chỉ
   định gì) vẫn đợi khám xong — bác sĩ còn có thể chỉ định thêm.
3. Lịch đi thẳng phòng: KHÔNG tính tiền khám (khách không khám). Không có chỉ định nào
   để mang sang → về hàng bác sĩ chính (có người quyết), khi đó tính tiền khám như thường.
4. Lịch thủ thuật mang sang cả chỉ định hôm trước khách "không làm" — ngoài đời "hẹn hôm
   khác" và "không làm" là cùng một cú bỏ tick; hôm nay hỏi lại. Lượt khám thường thì
   chỉ mang cái đã trả tiền.
5. Phòng cũ bị huỷ (sự cố phòng) thì Hành trình KHÔNG tự xếp phòng khác — đã có việc
   "điều phối lại" cho người (giữ luật cũ).
6. Chỉ định cũ quá 180 ngày không mang sang.

**Nhóm 4 — kê đơn + quầy thuốc (đã làm):** thư ký y khoa ghi đơn THẲNG như bác sĩ (không
nháp, không duyệt); dòng đơn ghi người nhập (`created_by`) + bác sĩ chính (`bac_si_chinh_id`,
chụp lúc ghi). Quầy thuốc và tiền thuốc KHÔNG đợi Khám xong — lượt đã có đơn là làm/thu
được. Hai bản đơn: số bác sĩ kê ↔ số khách mua (màn quầy báo "khác số kê"); sự kiện
`payment.medicine_collected`, `medicine.dispensed` (mang số kê / mua / đã giao) lên dòng
thời gian. Đơn đổi sau khi quầy đã đụng → đường ĐÍNH CHÍNH, màn bệnh án nay có ô lý do.

**Chỗ Claude tự chốt ở nhóm 4:**
7. Nháp đơn cũ của thư ký (trước 24/09) vẫn duyệt được — OFF, không xoá; ai ghi thẳng một
   đơn mới thì nháp cũ bị thay.
8. Thư ký đính chính được đơn — nhưng chỉ đơn của bác sĩ mình theo (giữ luật "không đính
   chính chéo bác sĩ").
9. Thu tiền thuốc cần lượt đã có ít nhất một dòng đơn (chưa kê gì thì chưa có gì để thu).

**Nhóm 3 — kết quả, chuông, hành trình (đã làm):** tệp kết quả phát `result_file.uploaded`
(chuông KHÔNG còn gọi thẳng — khối **Chuông** nghe, người nhận là dữ liệu
`day_nhan_thong_bao`: mặc định CSKH + thư ký + điều dưỡng + bác sĩ chính đích danh);
`result_file.confirmed` / `.viewed` / `.sent_to_patient`; bác sĩ/thư ký/BS siêu âm MỞ tệp là
tự ghi "đã xem" (`tep_ket_qua.da_xem_luc`); duyệt (không bắt buộc) = `result.reviewed` + coi
như đã xem. Phiếu kết quả hoàn tất ở phòng (`result.ready`) cũng réo chuông bác sĩ chính +
thư ký. **7 sự kiện mới** Tuyền chốt: `appointment.no_show` · `appointment.confirmed_by_call`
· `visit.left_early` · `payment.refunded` · `followup.scheduled` · `partner.sample_collected`
· `patient.contacted`; kèm `appointment.booked/rescheduled/cancelled`, `visit.checked_out`.
Đổi lịch lưu lịch sử (`appointment_doi_lich`). **Bảng hành trình chung** `/hanh-trinh` + mục
"Hành trình (sự kiện)" trong Xem lượt.

**Chỗ Claude tự chốt ở nhóm 3:**
10. "Đã xem" chỉ tính khi BÁC SĨ / THƯ KÝ Y KHOA / BÁC SĨ SIÊU ÂM mở tệp (CSKH mở để gửi,
    lễ tân mở không tính). Kết quả dạng PHIẾU (điền ở phòng) chưa có "đã xem" riêng —
    bác sĩ thấy nó ngay trên Bàn khám; ghi NỢ nếu cần.
11. Kết quả xét nghiệm NHẬP TAY (`lab_order_service`) vẫn gọi chuông thẳng như cũ — NỢ,
    chuyển sang sự kiện khi làm lại màn nhập xét nghiệm.
12. Hẹn tái khám chỉ phát sự kiện lúc bấm Khám xong (bệnh án lưu liên tục không phát).
13. Bảng hành trình mở cho MỌI vai nội bộ (kể cả CSKH), không có nội dung lâm sàng.

**Nhóm 5 — khối chỉnh dây (đã làm):** màn **Cài đặt → Dây nối nghiệp vụ**
(`/settings/day-noi`, quyền `config.wiring.manage`): loại khám qua tư vấn / đi thẳng
phòng; bật/tắt H4 (tự xếp phòng) và H6 (báo CSKH khi khách về còn việc); H7 số ngày kết
quả đối tác quá hạn; H8 số phút nhắc check-out; ai nhận chuông; vị trí trực (thêm, đổi
tên, gắn phòng, tắt). H6/H7/H8 chạy bằng hẹn giờ (`hen_gio`) trong khối Hành trình, tới
giờ KIỂM LẠI rồi mới réo. **Tự nhắc tôi** (ở màn Xem lượt): hẹn nhắc chính mình về một
khách, tới giờ chuông réo đúng người.

**Chỗ Claude tự chốt ở nhóm 5:**
14. H8 mặc định 60 phút (0 = tắt), đặt cả khi thu tiền thuốc; CHỈ nhắc lễ tân, không tự
    đóng lượt.
15. H6 báo CSKH khi khách về mà còn: kết quả đối tác chưa về / tệp chưa bác sĩ xem /
    dịch vụ đã chọn chưa làm. Khách BỎ VỀ giữa chừng thì luôn báo.
16. H7 mặc định 3 ngày, tính từ lúc dịch vụ đối tác làm xong / đối tác lấy mẫu.
17. Vị trí trực không xoá — chỉ tắt (lịch trực cũ còn trỏ tới); mã nội bộ tự sinh.

**Chỗ Claude tự chốt ở phần nợ sau nhóm 6:**
18. Bác sĩ MỞ phiếu kết quả = đã xem (giống tệp). Không có nút "đánh dấu đã xem" riêng.
19. Xét nghiệm: chỉ LẦN ĐẦU có kết quả mới réo; sửa chính tả sau đó không réo lại.
20. Danh sách "màn theo vai" mặc định nằm trong code (`permissions/catalogue.py` `MAN_THEO_VAI`);
    quản lý bật/tắt màn cho NHÓM (vai); 5 màn còn đi theo vai (Thu tiền thuốc, Đặt lịch, Danh
    sách bệnh nhân, Đối tác, Hành trình) chưa chỉnh ở đó được. Sửa nhóm không đổi quyền người đã cấp.

**Chỗ Claude tự chốt ở phiếu khám v5 (23/09 tối):**
21. Chỗ lưu phiếu khám là bảng RIÊNG `phieu_kham_luot` (một lượt một phiếu mỗi loại),
    không nới `form_instance` (bảng ấy gắn chuỗi kết quả của chỉ định).
22. Lượt có loại khám gắn phiếu (form_code) → mở thẳng phiếu ấy; không có → bác sĩ chọn
    1 trong 7. Đã ghi phiếu nào thì mở lại đúng phiếu đó.
23. Giá: dịch vụ đã có giá KHÔNG đổi; chỉ điền giá cho dòng trống + dịch vụ mới theo
    chi-dinh.html. "SÂ 4D sàn chậu", "Biofeedback" (một giá) tạo MÃ MỚI, không gộp vào
    "3D sàn chậu" / "Biofeedback cơ bản-nâng cao" có sẵn — phòng khám gộp nếu đúng là một.
24. Thuốc: chỉ gắn mã kho khi tên kho khớp chắc chắn (60/73); còn lại đi tên thô, quầy
    thuốc xác định như cũ. Đường dùng + cách dùng ghép vào một cột ("Uống — …"), số lượng
    + đơn vị ghép "2 hộp" (bảng `prescription` không có cột riêng).
25. Mẫu kết quả khi bác sĩ tự điền: mẫu đã gắn cho dịch vụ → mẫu gợi ý của phiếu v5 → 18
    mẫu dự phòng. Migration KHÔNG tự gắn mẫu cho dịch vụ (luật cũ có test canh).
26. Quản lý mở phiếu khám được (đọc) nhưng chỉ ghi khi có `clinical.record.write`.

**Chỗ Claude tự chốt ở ruột mẫu kết quả + in (23/09 khuya):**
27. PDF mẫu thật của phòng khám là CHUẨN cho 16 mẫu siêu âm/soi; chi-dinh.html chỉ lấy ô
    chọn (BI-RADS, TIRADS, loại song thai, Oxford) + 3 mẫu xét nghiệm.
28. SỐ ĐO (PSV, kích thước, CRL…) và KẾT QUẢ XÉT NGHIỆM (HPV âm/dương) KHÔNG điền sẵn — chỉ
    gợi ý đơn vị. Câu của riêng một bệnh nhân trong PDF ("dính 50%", "01 nang thứ cấp",
    "mảng xơ vữa 5.7x2.0 mm") không thành câu mẫu.
29. In được cả bản nháp nhưng ghi "BẢN NHÁP"; CSKH in được (gửi kết quả cho khách); in
    không tính là "bác sĩ đã xem".
30. Kết luận soi âm hộ / HPV / PCR để trống (câu kết luận trong nguồn là của một ca cụ thể).

**Chỗ Claude tự chốt ở phòng điền kết quả (23/09 khuya):**
31. Dịch vụ chưa gắn mẫu: phòng mở mẫu gợi ý của phiếu v5 (chọn sẵn) + 18 mẫu dự phòng;
    KHÔNG tự gắn chính thức — gắn vẫn là việc của quản lý.
32. Phiếu kết quả đã Hoàn tất = có kết quả (result.ready, báo bác sĩ chính) khi dịch vụ
    chưa cấu hình `result_mode`; chỉ im lặng khi quản lý cấu hình rõ NONE / LATER.

**Chỗ Claude tự chốt ở thủ thuật + đối tác (24/09 rạng sáng):**
33. Bỏ xác nhận = tệp đối tác TỰ HỢP LỆ lúc tải lên (ghi rõ lý do tự động), không phải
    bỏ trạng thái — giữ nguyên mọi logic "kết quả hợp lệ", bật lại được bằng cờ.
34. Phòng lấy mẫu không bao giờ có phiếu kết quả (kết quả do đối tác gửi tệp); thủ thuật
    không có mẫu gợi ý thì phiếu là tuỳ chọn.
35. Thủ thuật đã làm mà không có phiếu hiện "Đã làm" ở mục C (không treo "Chưa có kết quả").
36. **Hai cột trạng thái chỉ định khớp ở Postgres** (trigger `service_order_dong_bo_trang_thai`,
    migration 20260924000011): `execution_status` là nguồn thật, `exec_status` là bản
    chiếu cho màn cũ. Lối cũ ghi cột cũ (đối tác tự lấy mẫu, `/start`, `/complete`) thì
    cột mới đi theo — CHỈ với chỉ định đời mới (`selection_status` có giá trị); đời cũ
    giữ NULL. [Không làm được] trước khi có phòng nay đóng được cả cột cũ (nới ràng buộc
    phòng cho `not_performed`). Giờ bắt đầu/xong ghi vào `service_order` ở cùng chỗ.
37. **Khối VÒNG ĐỌC** (`events/consumers/vong_doc.py`, module `vong_doc`): nghe
    service.completed / service.not_performed / partner.sample_collected / result.ready /
    result_file.uploaded|confirmed|revoked → chạy lại vòng đọc + khép lượt. Sửa lỗi thật:
    đường làm mới không mở "có kết quả cần đọc" cho bác sĩ chính, và lượt không tự khép
    khi dịch vụ cuối xong sau lúc bác sĩ Hoàn tất. Tải/xác nhận/thu hồi tệp KHÔNG còn gọi
    thẳng khối Khám. Chậm vài giây (worker) — chấp nhận, vì mọi lối giờ đi chung một cửa.
38. Sự kiện mới **`visit.exam_completed`** (phát đúng một lần, lúc lượt khép hẳn) và
    **`result_file.revoked`**. Quầy/nhà thuốc/nhắc check-out về sau cắm vào mốc này.
39. **Bàn khám tư vấn ghi vào CHÍNH phiếu khám v5 của lượt** (cùng `phieu_kham_luot`);
    người chỉ có khối Tư vấn (`clinical.intake.perform`) cũng ghi được phiếu.
    [Xong tư vấn] đợi phiếu lưu xong như [Hoàn tất].
40. [Hoàn tất] hỏi lại bằng dải xác nhận tại chỗ (`components/ui/XacNhanTaiCho.tsx`),
    không còn `window.confirm`; câu hỏi nói rõ "phiếu vẫn sửa được sau".
41. **Giá trống điền theo chi-dinh.html, chỉ chỗ đang trống** (hàm
    `dien_gia_trong_theo_phieu_v5()`, migration 20260924000012 + seed.sql): dịch vụ như
    migration 09 (lỗ: DB dựng mới chạy migration trước seed nên giá không vào) + **58
    thuốc** của phiếu v5 (`drug_catalog.unit_price`, giá một đơn vị bán như bảng giá ghi).
    Giá đã đặt không bị đè. Còn trống: dịch vụ không có trong bảng giá (khám phụ khoa,
    SA 3D sàn chậu, biofeedback cơ bản/nâng cao, 7 dịch vụ nam khoa) + 22 thuốc ngoài
    phiếu — quản lý nhập giá.

**Nhóm 6 — rà quyền + trách nhiệm không rơi (đã làm):**
- Đối chiếu bảng "màn mặc định theo vai" với quyền thật: lệch duy nhất là **Dược sĩ**
  không vào được quầy thu tiền thuốc và không thu được tiền thuốc → đã mở (chỉ tiền thuốc).
- Một bước tự động hỏng hẳn (DEAD) → chuông KHẨN cho trưởng ca + quản lý (với khối Hành
  trình, DEAD = một khách đang kẹt). `/ops` vẫn giữ số đo cho kỹ thuật.
- Bảng hành trình tách "ĐÃ TRẢ TIỀN — chờ xếp phòng" (trách nhiệm đang rơi: người thu
  không có quyền điều phối, hoặc dây tự xếp tắt) khỏi "Chờ trả tiền".
- NỢ: hẹn giờ hỏng hẳn (`hen_gio` CHET) chưa réo người trực; khối trách nhiệm cũ
  (tiền đã thu mà không làm, dừng giữa chừng, phòng hỏng) giữ nguyên, đã có việc + hẹn kiểm lại.

### Các chốt khác (24/09)

- **Bệnh án:** lưu liên tục vào database (máy khác, người khác thấy ngay bản mới nhất),
  nhưng KHÔNG phát event mỗi lần lưu. Event phát khi bấm **Hoàn tất / Khám xong** (một
  nút). Quên bấm cũng được — bản lưu vẫn là bản mới nhất.
- **Kê đơn:** thư ký = bác sĩ, không nháp, không duyệt (phòng khám cho phép). Đơn ghi
  đúng người nhập, kèm bác sĩ chính của lượt.
- **Duyệt kết quả:** không bắt buộc. Bác sĩ mở kết quả thì hệ thống TỰ ghi "đã xem lúc…"
  (không phải bấm gì) — để H6 biết kết quả nào chưa ai xem.
- **Bảng hành trình chung:** một bảng cho mọi người biết mỗi khách hôm nay **đang ở đâu,
  đã xong gì, còn chờ gì** — dựng từ event, mở được từ mọi màn (nút Xem lượt) và bảng
  tổng ở màn Trưởng ca.
- **Đổi lịch:** lưu từng lần đổi (từ giờ nào → giờ nào, ai đổi, lý do).
- **Thêm 7 event:** khách không đến · CSKH gọi xác nhận lịch · khách bỏ về giữa chừng ·
  hoàn tiền · bác sĩ hẹn tái khám · đối tác đã lấy mẫu · CSKH đã liên hệ khách.
- **Chỉ định cũ đã trả tiền mà chưa làm** → mang sang lượt mới, không thu lại.
- **Tiền thuốc:** không cần bác sĩ bấm Khám xong.

---

## PHỤ LỤC — bảng chi tiết (bản nháp 23/09, số H cũ)

## A. Các khối và event mỗi khối phát

| # | Khối (module) | Lệnh — ai bấm | State riêng | Event phát ra | Hiện trạng |
|---|---|---|---|---|---|
| 1 | **Đặt lịch** | Đặt / Đổi / Huỷ lịch — CSKH, lễ tân | `appointment` (+ số booking) | `appointment.booked` · `appointment.rescheduled` · `appointment.cancelled` | 🟡 sổ cũ |
| 2 | **Lịch làm việc** | Xếp ca, Công bố tuần — quản lý | `work_roster`, `roster_week` | `roster.week_published` | 🟡 sổ cũ |
| 3 | **Tiếp đón** | Check-in / Hoàn tác — lễ tân | `visit` (mở lượt, số quầy) | `visit.checked_in` · `visit.check_in_undone` | ✅ / ❌ |
| 4 | **Sinh hiệu** | Bắt đầu đo / Lưu — điều dưỡng | `vital_measurement`, `encounter_flow.vitals_*` | `vitals.started` · `vitals.recorded` | ✅ |
| 5 | **Khám tư vấn** | Bắt đầu / Xong tư vấn — bác sĩ tư vấn | `consultation` (loại TU_VAN) | `consultation.started` · `consultation.handed_over` (xong tư vấn, chuyển bác sĩ chính) | ❌ chưa có khối |
| 6 | **Khám chính** | Bắt đầu khám / Khám xong — bác sĩ chính, thư ký | `consultation` (PRIMARY/REVIEW) | `consultation.started` · `consultation.completed` | 🟡 sổ cũ |
| 7 | **Bệnh án** | Lưu / Hoàn tất — bác sĩ, thư ký (sửa lúc nào cũng được) | `clinical_record` (có phiên bản) | `clinical_record.completed` (chỉ khi bấm Hoàn tất, không phải mỗi lần lưu — DE-03) | ❌ |
| 8 | **Chỉ định** | Xác nhận chỉ định — bác sĩ, thư ký, điều dưỡng | `service_order` | `service_order.placed` | ✅ |
| 9 | **Chọn dịch vụ** | Chốt dịch vụ khách thật làm — lễ tân | `service_selection_state` | `service_selection.confirmed` | 🟡 sổ cũ |
| 10 | **Thu tiền dịch vụ** | Thu / Xác minh chuyển khoản / Huỷ phiếu — lễ tân | `payment_cycle`, `payment_bill_line` | `payment.service_collected` · `payment.voided` | ❌ |
| 11 | **Điều phối phòng** | Xếp / Đổi phòng — ai có quyền điều phối | `service_order.room_id`, `queue_entry` | `service.routed` · `service.routing_invalidated` | ❌ / ✅ |
| 12 | **Thực hiện dịch vụ** | Bắt đầu / Xong / Không làm / Dừng / Làm lại — phòng | `service_execution_attempt` | `service.started` · `service.completed` · `service.not_performed` · `service.interrupted` · `service.retry_prepared` | ✅ |
| 13 | **Phiếu kết quả** | Điền / Hoàn tất / Sửa lại — phòng | `form_instance` | `result_form.completed` · `result.ready` · `result.corrected` | ✅ |
| 14 | **Tệp kết quả + đối tác** | Tải tệp / Xác nhận đúng người — điều dưỡng, đối tác | `tep_ket_qua` | `result_file.uploaded` · `result_file.confirmed` | ❌ |
| 15 | **Duyệt kết quả** | Bác sĩ xem/duyệt | `service_order.duyet_*` | `result.reviewed` | 🟡 sổ cũ |
| 16 | **Kê đơn** | Kê thuốc — bác sĩ (thư ký nháp) | `prescription` | `prescription.written` | ❌ |
| 17 | **Quầy thuốc** | Phát thuốc theo khách chọn (ít/thêm) + thu tiền thuốc — dược sĩ | `prescription` (số phát), `payment_cycle` | `medicine.dispensed` (kèm chênh lệch kê ↔ mua) · `payment.medicine_collected` | 🟡 |
| 18 | **Gửi khách (CSKH)** | Đánh dấu đã gửi kết quả — CSKH | `tep_ket_qua.gui_*`, `tuong_tac_cskh` | `result.sent_to_patient` | 🟡 |
| 19 | **Rời phòng khám** | Check-out — lễ tân | `visit.closed_*` | `visit.checked_out` | 🟡 sổ cũ |
| 20 | **Quyền** | Cấp / Thu khối quyền — quản lý | `capability_grant` | `capability.granted` · `capability.revoked` | ✅ |
| 21 | **Phòng, vị trí, dịch vụ** | Thêm/đổi tên/tắt — quản lý | `clinic_room`, `vi_tri_lam_viec`, `service_price` | — | ◻︎ CRUD + nhật ký |

## B. Các node nghe — dây nối

### B1. Khối HÀNH TRÌNH (Journey Process Manager) — giữ luật THỨ TỰ, chỉ gửi LỆNH

| Dây | Nghe | Điều kiện | Gửi lệnh (của khối khác) | Hiện trạng |
|---|---|---|---|---|
| H1 | `visit.checked_in` | dịch vụ khám có bước tư vấn | Xếp khách vào hàng **bác sĩ tư vấn** | ❌ |
| H2 | `visit.checked_in` | không có bước tư vấn | Xếp khách vào hàng **bác sĩ chính** | 🟡 gọi thẳng (F2) |
| H3 | `consultation.handed_over` | — | Xếp khách vào hàng bác sĩ chính | ❌ |
| H4 | `visit.checked_in` | lịch hẹn là THỦ THUẬT/dịch vụ (đặt từ lượt trước) | Tạo sẵn chỉ định theo lịch → chờ thu tiền | ❌ |
| H5 | `payment.service_collected` | chỉ định đã chọn, chưa có phòng | **Xếp phòng** (gợi ý vắng nhất, thay cho người vừa thu tiền) | ❌ ← mối thử đầu tiên |
| H6 | `service.completed` / `result.ready` | bác sĩ chính còn chờ đọc | Đưa khách vào hàng **đọc kết quả** của bác sĩ chính | 🟡 |
| H7 | `visit.checked_out` | còn kết quả chưa đọc / việc mở | Mở **theo dõi sau khám** (CSKH) | ❌ (thesis ContinuityRisk) |
| H8 | hẹn giờ: kết quả đối tác quá hạn chưa về | — | Mở việc CSKH gọi đối tác/khách | ❌ |

### B2. Các node khác

| Node | Nghe | Làm gì | Hiện trạng |
|---|---|---|---|
| **Dòng thời gian** (projection) | mọi event của một lượt | Ghi một dòng lên màn hành trình; dựng lại được bằng phát lại | ✅ (thiếu các event ❌ ở bảng A) |
| **Trách nhiệm không rơi** | `service.not_performed` (đã thu tiền) · `service.interrupted` · `service.routing_invalidated` | Mở việc đối soát tiền / quyết làm lại, có hạn | ✅ |
| **Thông báo (chuông)** | `result_file.uploaded` · `result.ready` · `appointment.booked` | Báo CSKH + bác sĩ của khách | 🟡 gọi thẳng |
| **Việc CSKH** | `result_file.confirmed` · `result.ready` · `appointment.cancelled` · `roster.week_published` | Sinh việc: gửi KQ, hỏi lý do huỷ, lịch vượt sức chứa | 🟡 đang là VIEW đọc bảng (`v_viec_cskh`) — giữ view được |
| **Nhắc tái khám** | `consultation.completed` có hẹn tái khám | Tạo lời nhắc | 🟡 |
| **Quầy thuốc** (projection) | `prescription.written` | Hiện đơn cần phát ở quầy | 🟡 đọc bảng |
| **Sức chứa** | `appointment.booked/rescheduled/cancelled` · `roster.week_published` | Đánh dấu khung vượt sức chứa | 🟡 trigger DB + view |

## C. Luật vẫn ĐỒNG BỘ (không qua event — luật an toàn trong cùng giao dịch)

Quyền (`doi_quyen`) · cổng tiền trước khi bắt đầu dịch vụ (FinanceGate) · chặn sức
chứa khi ĐÃ công bố lịch · số booking/số quầy (trigger DB) · khoá phiên bản chống ghi
đè (revision). Mỗi cái là luật của CHÍNH khối đó, không phải dây nối giữa khối.

## D. Cần Tuyền xác minh

1. **Bảng A:** tên + ý nghĩa từng event có đúng "sự thật đã xảy ra" không? Có sự thật
   nào phòng khám cần mà thiếu không?
2. **H1/H3 (bác sĩ tư vấn):** dịch vụ khám nào đi qua tư vấn? Hay mọi khách mặc định
   qua tư vấn trừ khi lễ tân/bác sĩ chính nhận thẳng?
3. **H4:** khách đặt lịch thủ thuật từ lượt trước — check-in xong có cần thu tiền trước
   khi vào phòng như chỉ định thường không?
4. **H5:** khối Hành trình xếp phòng **thay cho người vừa thu tiền** (dùng quyền của
   người ấy, không tự nâng quyền) — đúng ý không?
5. **Quầy thuốc:** thu tiền thuốc có cần bác sĩ bấm Khám xong trước không?
6. **Bệnh án:** event chỉ phát khi bấm Hoàn tất (không phát mỗi lần lưu) — đồng ý?

Duyệt xong bản đồ này thì code theo từng nhóm dây, mỗi nhóm nghiệm thu bằng khách giả.
