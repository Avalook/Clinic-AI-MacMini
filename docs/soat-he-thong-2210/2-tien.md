# Soát hệ thống 22/10/2026 · Khối 2 — TIỀN

> Đang viết dần. Phạm vi: thu ngân, hoá đơn (`bill_service`), tiền thừa, nợ / sổ nợ,
> hoàn tiền, huỷ / hoàn tác phiếu, giảm giá, đối tác (`billing_owner`), báo cáo cuối
> ngày / chốt ca, xuất hoá đơn công ty. KHÔNG gồm thuốc bán ở quầy thuốc / kho / lô.
> Code soát: nhánh `main` tại `00bde52`. Chỉ đọc — không sửa code.

## Nhóm A — Thu tiền, hoá đơn, hoàn tiền (người soát chính tự lần theo code)

### A1 · CAO · Phí khám mặc định đã thu, rồi tick "Dịch vụ khám" → khách trả tiền khám hai lần, phần cũ không thành tiền thừa

- **Ở đâu:** `src/clinicai/services/bill_service.py:880-926` (`hoa_don_con_no` — tìm "đã phủ" theo
  nguồn khám HIỆN TẠI), `src/clinicai/services/tien_thua_service.py:72-83` (nhánh 3 chỉ nhận
  `exam-%-selected-%`), `src/clinicai/services/phi_kham_service.py:363-364` (tick thêm không hỏi
  phí mặc định đã thu chưa).
- **Vì sao sai:** chưa tick dịch vụ khám nào thì hoá đơn tự cộng **phí mặc định** với mã nguồn
  `exam-<lượt>` (`bill_service.py:320-330`, `417-421`). Thu xong, bác sĩ/thu ngân tick một dịch vụ
  khám (vd "Khám phụ khoa" 280.000đ) → nguồn tiền khám đổi sang `exam-<lượt>-selected-<id>`. Hàm
  tìm "đã phủ" chỉ tìm nguồn mới; dòng `exam-<lượt>` đã thu chỉ được công nhận nếu **tên + tổng**
  trùng khít một dịch vụ con (`_nguon_con_duoc_legacy_phu`, dòng 523-557) — tên phí mặc định là
  "Tiền khám <loại khám>" nên gần như không bao giờ trùng. Kết quả: hoá đơn đòi thêm 280.000đ.
  Phía tiền thừa thì chỉ coi dòng `-selected-` bị bỏ tick là thừa, nên 150.000đ phí mặc định
  đã thu **không hiện ở đâu cả** (không phủ, không thừa, không hoàn được bằng nút "Hoàn tiền thừa").
- **Kịch bản:** loại khám có phí mặc định 150.000đ → khách thu 150.000đ tiền mặt → bác sĩ tick
  "Khám con" 280.000đ → quầy hiện còn nợ 280.000đ → thu tiếp. Khách trả **430.000đ** cho một buổi
  khám đáng lẽ 280.000đ; check-out không bị chặn vì tiền thừa = 0.
- **Độ chắc:** chắc chắn về code. Test có sẵn còn **khẳng định** hành vi này:
  `src/tests/services/test_thu_dich_vu_nhieu_lan_db.py:230-269`
  (`test_tick_dich_vu_kham_sau_khi_da_thu_tao_lan_thu_hai`: thu 150.000 rồi thu thêm 280.000, hoá
  đơn rỗng, không kiểm tiền thừa). Cần **Tuyền chốt nghiệp vụ**: tick dịch vụ khám thay phí mặc
  định (phí cũ thành tiền thừa / được trừ) hay cộng thêm.
- **Test đề xuất:** cùng kịch bản trên, khẳng định `tong(lần thu) − tien_thua == 280.000`
  (hoặc hoá đơn lần 2 = 130.000đ nếu Tuyền chọn "trừ phần đã thu").
- **Hướng sửa:** (a) coi dòng `exam-<lượt>` PAID là tiền thừa loại `BO_DICH_VU_KHAM` khi lượt đã
  có tick sống (sửa cả `_DONG_THUA_SQL` và `_HOAN_TIEN_THUA_SQL` — hai chỗ phải khớp); hoặc
  (b) chặn tick ở `phi_kham_service.chon` khi phí mặc định đã thu, bắt hoàn tác/hoàn trước.

### A2 · CAO (cần chốt) · Hoàn tiền được trên phiếu ĐÃ HUỶ → tiền ra khỏi két hai lần

- **Ở đâu:** `src/clinicai/services/hoan_tien_service.py:323-338` (`_tao_trong` chỉ kiểm
  `paid_at IS NOT NULL`, không kiểm `status = 'PAID'`); trigger `payment_refund_guard`
  (`supabase/migrations/20260919000004_tien_thuoc_cp5_hoan_tra.sql`, chỉ kiểm `paid_at`);
  `src/clinicai/services/cashier_board_service.py:532-537` cố ý trả dòng hoàn được "kể cả đã huỷ
  phiếu"; nút ở `src/dashboard/app/(dashboard)/thu-ngan/GiaoDich.tsx:242-250` hiện cho mọi phiếu.
- **Vì sao sai:** "Huỷ phiếu / Hoàn tác lần thu" nghĩa là *thu nhầm, trả lại ngay — lượt về chưa
  thu* (docstring `payment_service.py:1633-1645`). Phiếu huỷ vẫn giữ `paid_at` (huỷ chỉ đặt
  `status='VOIDED'`, `payment_service.py:1499-1509`). Chiều ngược lại đã được chặn cho tiền dịch vụ
  ("đã có khoản hoàn thì không huỷ được — huỷ nữa là trả khách hai lần", dòng 1429-1443), nhưng
  **huỷ trước rồi hoàn sau** thì không ai chặn.
- **Kịch bản:** thu siêu âm 500.000đ tiền mặt → bấm Hoàn tác (két trả khách 500.000đ, phiếu
  VOIDED) → ở tab Giao dịch, phiếu ấy vẫn có khung "Hoàn tiền" với dòng còn hoàn 1 → bấm hoàn
  1 × 500.000đ → khoản hoàn COMPLETED, phát `payment.refunded`. Sổ ghi két đã chi ra **1.000.000đ**
  cho một lần thu 500.000đ.
- **Độ chắc:** chắc chắn về code. Với tiền THUỐC đây là luật cố ý của CP5
  (`src/tests/services/test_tien_thuoc_cp5_db.py:266-272`, `test_r6_hoan_duoc_lan_thu_da_huy_phieu…`);
  với tiền DỊCH VỤ không có test nào nói cho phép, và nó trái chính lý do chặn ở dòng 1429.
  Cần Tuyền chốt: "huỷ phiếu" có trả tiền mặt cho khách không?
- **Test đề xuất:** thu DV 500.000 → `hoan_tac` → `HoanTienService.tao(...)` phải `ConflictError`;
  bất biến chung: với mỗi lần thu, `(VOIDED ? amount : 0) + Σ hoàn COMPLETED/PENDING ≤ amount`.
- **Hướng sửa:** trong `payment_refund_guard` (Postgres — để hai người bấm cùng lúc cũng bị
  chặn) thêm `lan.status = 'PAID'` cho `kind='dich_vu'` (hoặc cả hai loại nếu Tuyền chốt), và
  `hoan_cua_cac_lan_thu` không trả `dong_hoan_duoc` cho phiếu VOIDED.

### A3 · VỪA · Lần thu CHIA "tiền mặt + chuyển khoản": phần tiền mặt đã cầm ở quầy nhưng sổ không biết tới cho tới lúc xác minh CK — và mất hẳn nếu huỷ lần chờ

- **Ở đâu:** `src/clinicai/services/payment_service.py:413-415` + `phan_thu.py:144-146`
  (`hinh_thuc_chinh`: có phần CK là CẢ lần thu thành chuyển khoản → `PENDING_VERIFICATION`);
  `payment_service.py:1220-1225` (`paid_at = now()` lúc **xác minh**); `payment_service.py:1343-1354`
  (`huy_cho_xac_minh` huỷ cả lần, không tách phần TM); báo cáo chỉ đọc `PAID/VOIDED` theo
  `paid_at`: `src/clinicai/services/bao_cao_cuoi_ngay_service.py:916-947`.
- **Vì sao sai:** tiền mặt là tiền thật đã vào két ngay lúc bấm thu, nhưng nó bị buộc chung số
  phận với phần chuyển khoản chưa về.
- **Kịch bản 1 (két lệch ca):** phiếu 500.000đ = 200.000đ TM + 300.000đ CK, thu lúc 11:00 ca sáng.
  CK về, thu ngân ca chiều xác minh lúc 14:00 → `paid_at` = 14:00 → cả 500.000đ (gồm 200.000đ TM)
  tính vào **ca chiều**. Ca sáng đếm két thừa 200.000đ so với báo cáo, ca chiều thiếu 200.000đ.
- **Kịch bản 2 (mất dấu tiền mặt):** khách không chuyển 300.000đ → thu ngân "Huỷ lần chờ" → cả lần
  thu CANCELLED, khách nợ lại 500.000đ. 200.000đ tiền mặt đang nằm trong két **không có dòng sổ nào**
  (không phải thu, không phải hoàn). Thu lại 500.000đ thì khách trả 700.000đ nếu không ai nhớ.
- **Độ chắc:** chắc chắn về code; chưa đo tần suất chia TM+CK ở prod.
- **Test đề xuất:** thu `phan=[TM 200.000, CK 300.000]` → `huy_cho_xac_minh` → khẳng định có
  ghi nhận 200.000đ tiền mặt (PAID riêng hoặc khoản phải trả khách); và báo cáo ca chứa 200.000đ TM
  theo giờ thu, không theo giờ xác minh.
- **Hướng sửa:** tách phần TM thành lần thu PAID riêng ngay lúc thu (phần CK là lần chờ riêng),
  hoặc khi huỷ lần chờ có phần TM thì bắt chọn "trả lại TM cho khách" / "giữ làm thu một phần".

## Bất biến (luật luôn phải đúng) — đã canh / còn thiếu

**Đã canh** trong `src/tests/services/test_mo_phong_dong_tien_db.py` (`_lech`, dòng 209-238), chỉ
cho lượt ĐÃ VỀ, một chỉ định siêu âm 300.000đ:

| Mã | Luật | Ghi chú |
|---|---|---|
| B1 | Khách nợ thật (`no_khi_ve` + CK chờ) = số "việc tồn" (GHI_NO + CK_CHUA_VE) | |
| B2 | Phòng khám nợ khách (tiền thừa + đã thu chưa làm) = việc tồn (CHUA_TRA_LAI…) | |
| B3 | Không hoàn TIỀN MẶT cho tiền khách trả CK | |
| — | Bài bấm lộn xộn 80 lượt × 10 bước: thu TM/CK, xác minh, huỷ chờ, huỷ phiếu, làm xong, bỏ chỉ định, ghi nợ, hoàn tiền thừa, giữ lại, về | |

**Còn thiếu** (đề xuất thêm vào `VIEC` / `_lech`):

| # | Bất biến còn thiếu | Bắt được phát hiện |
|---|---|---|
| T1 | Với mỗi lần thu: `(VOIDED ? amount : 0) + Σ hoàn (PENDING+COMPLETED) ≤ amount` — tiền ra không vượt tiền vào | A2 |
| T2 | Khách trả ròng (Σ PAID − Σ hoàn xong) ≤ tổng giá dịch vụ thật đã làm + phí khám đúng một lần | A1 |
| T3 | Σ tiền mặt trong báo cáo ca = Σ phần TM của các lần thu **có tiền mặt đã cầm** trong ca (kể cả lần chia đang chờ CK) − hoàn TM | A3 |
| T4 | Báo cáo cuối ngày = Σ bản chụp `chot_so_ca` các ca trong ngày + điều chỉnh sau chốt (huỷ/đổi hình thức) | xem nhóm C |
| T5 | Lượt CÒN MỞ cũng phải đúng B1/B2 (hiện `_lech` trả `[]` ngay nếu chưa về, dòng 214-220) | |
| T6 | Bài lộn xộn chưa có: hoàn tiền theo dòng (`HoanTienService.tao`), hoàn tác/`hoan_tac`, đổi hình thức, giảm giá, tick/bỏ tick dịch vụ khám, thu chia TM+CK, hai người bấm cùng lúc | A1, A2, A3 |

## Nhóm B — Nợ khi về, ghi nợ, sổ nợ hai chiều

> Do agent con soát; người soát chính đã mở lại code các mục B1, B2 và câu hỏi "huỷ lần chờ sau
> khi về". **Sổ nợ `so_no` không sai số dư lâu dài** ở mục nào — nó luôn tính lại từ trạng thái
> hiện tại. Các lỗi nằm ở bảng `cong_no` (khoản ghi nợ lễ tân ký), số hiển thị và vòng đối chiếu.
> *Thuật ngữ:* **ghi nợ** = lễ tân bấm "Ghi nợ" kèm lý do để khách về khi chưa trả; **sổ nợ** =
> bảng `so_no` máy tự ghi (khách nợ phòng khám / phòng khám nợ khách); **bên nghe** = đoạn code
> trong worker `su-kien` chạy khi có một sự kiện.

### B1 · VỪA · Khoản ghi nợ treo "CHƯA THU" mãi khi nợ hết mà không qua lần thu nào

- **Ở đâu:** `src/clinicai/events/consumers/cong_no.py:28-66` (bên nghe duy nhất đặt `DA_THU`,
  chỉ chạy khi có `payment.service_collected` / `payment.medicine_collected` — `catalogue.py:2119, 2176`);
  `src/clinicai/services/cong_no_service.py:161-171` (`chan` = còn dòng nợ mà chưa phủ — nợ rỗng thì
  cho về); `cong_no_service.py:525-536` (đã về thì không huỷ được ghi nợ).
- **Kịch bản:** siêu âm 500.000đ đã làm → Ghi nợ 500.000đ → KTV hoàn tác "đã làm xong" hoặc bác sĩ
  huỷ chỉ định → nợ thật về 0, check-out cho qua → dòng `cong_no` vẫn `CHUA_THU 500.000đ`. Không
  thu được (hoá đơn 0đ: "Lượt này không có khoản nào để thu", `payment_service.py:557-560`), không
  huỷ được (đã về). Lượt hiện ở quầy thu **mọi ngày** với nhãn "đang ghi nợ 500.000đ". Nếu sau đó
  khách mua thuốc, lần thu thuốc sẽ đóng khoản nợ dịch vụ với "đã thu" = tiền thuốc.
- **Độ chắc:** chắc chắn (đã lần theo code: ngoài bên nghe, không chỗ nào đặt `DA_THU`).
- **Test đề xuất:** làm xong → ghi nợ → hoàn tác xong → check-out → không còn `cong_no` CHUA_THU.
- **Hướng sửa:** check-out tự đóng khoản ghi nợ khi `no.dong` rỗng (lý do "hết nợ không qua thu"),
  hoặc cho bên nghe `cong_no` nghe thêm sự kiện huỷ chỉ định / hoàn tác / đổi vật tư.

### B2 · THẤP–VỪA · "Phủ đủ" so theo MÃ dòng, không so SỐ TIỀN (bản đồ đã ghi, `phat-hien.json` chưa có)

- **Ở đâu:** `cong_no_service.py:161-166` (`phu_boi_ghi_no`).
- **Kịch bản:** vật tư 2 × 100.000đ → Ghi nợ 200.000đ → sửa thành 5 cái (cùng mã dòng) → check-out
  qua. Lý do lễ tân ký chỉ cho 200.000đ, nợ thật 500.000đ; hộp check-out và quầy hiện "đang ghi nợ
  200.000đ". Sổ nợ vẫn đúng 500.000đ.
- **Độ chắc:** chắc chắn. **Test:** ghi nợ → đổi số lượng vật tư → check-out phải bị chặn.
- **Hướng sửa:** so thêm số tiền từng `source_id`.

### B3 · THẤP (nghi) · Huỷ lần CK chờ SAU khi khách về: không sinh khoản ghi nợ

- **Ở đâu:** `payment_service.py:1306-1386` (`huy_cho_xac_minh` không gọi `_tu_ghi_no_sau_ve`,
  trong khi `void_payment` gọi ở dòng 1598-1607).
- **Kịch bản:** khách về với CK 500.000đ đang chờ → hôm sau huỷ lần chờ (khách không chuyển). Sổ nợ
  và màn "Khách còn nợ" vẫn đúng 500.000đ (test `test_r11_…` canh). Nhưng quầy thu chỉ kéo lượt cũ
  về khi có `cong_no` CHUA_THU / CK chờ / phòng khám nợ khách / chỉ định–đơn thuốc chưa thu trong
  30 ngày (`cashier_board_service.py:111-134`) — nếu 500.000đ là **phí khám đã tick hoặc vật tư**
  thì có thể không vế nào khớp: báo cáo nói khách nợ, quầy không có chỗ thu.
- **Độ chắc:** nghi (chưa chạy). **Test:** về → huỷ lần chờ → lượt phải có trong `CashierBoardService.board`.
- **Hướng sửa:** gọi `_tu_ghi_no_sau_ve` trong `huy_cho_xac_minh` như `void_payment`.

### B4 · VỪA (nghi) · Vòng đối chiếu sổ nợ có thể "đói" lượt mới

- **Ở đâu:** `so_no_service.py:528-543` — chọn lượt bằng `UNION … LIMIT 300` **không ORDER BY**.
- **Vì sao:** sau khi ghi số dư đầu kỳ có thể có hàng nghìn lượt cũ còn số dư; mỗi vòng 10 phút có
  thể lấy đúng 300 lượt cũ ấy, lượt vừa về không bao giờ được xét → thay đổi không qua sự kiện
  (vd hoàn CK xác nhận xong) không vào sổ.
- **Test:** 301 lượt còn số dư + 1 lượt mới đổi trạng thái không phát sự kiện → `doi_chieu_mot_vong`
  phải ghi dòng `DOI_CHIEU` cho lượt mới. **Sửa:** giới hạn riêng từng vế, vế "vừa về" sắp `closed_at DESC`.

### B5 · THẤP · Các lệch nhỏ khác (đều chắc chắn trừ mục có ghi "nghi")

| Ở đâu | Lỗi | Ví dụ |
|---|---|---|
| `events/consumers/cong_no.py:51-60` | "Đã thu" của khoản nợ cộng mọi lần thu của lượt sau giờ ghi nợ, không lọc loại tiền | nợ DV 300.000đ, khách trả 300.000đ + mua thuốc 200.000đ → dòng thời gian ghi "đã thu 500.000đ" |
| `cong_no_service.py:442-458, 477-480` (nghi) | Ghi nợ trúng lúc bên nghe vừa đóng nợ → `UPDATE` không còn dòng → `cong_no_id=None` → `emit_event` vỡ NOT NULL → 500; qua đường huỷ phiếu thì cuộn cả lệnh huỷ | bấm lại thì qua, không mất tiền |
| `so_no_service.py:479-482` | Việc tồn lấy lý do của dòng `cong_no` mới nhất **không lọc trạng thái** | ghi nợ "quên ví" → huỷ → CK chờ, về → huỷ chờ: việc tồn 500.000đ hiện lý do "quên ví" của dòng đã HUỶ |
| `events/consumers/so_no.py:99-110` (nghi) | Sự kiện thu tới SAU sự kiện check-out (thử lại) → sổ ghi THU −500.000đ rồi đối chiếu +500.000đ | số cuối đúng, báo cáo kỳ thổi phồng "thu nợ" và "phát sinh" mỗi bên 500.000đ |

### B6 · CẦN TUYỀN CHỐT · Sổ nợ coi CẢ lần CK chờ là "khách nợ", kể cả phần trả trước dịch vụ chưa làm

- **Ở đâu:** `so_no_service.py:113-118, 234-243`.
- **Ví dụ:** phí khám 300.000đ + siêu âm 500.000đ **chưa làm**, CK 800.000đ đang chờ, khách về →
  sổ ghi "khách nợ 800.000đ" (nếu CK hỏng, nợ thật chỉ 300.000đ). Khi xác minh, báo cáo ghi "thu
  nợ 800.000đ" đồng thời "phòng khám nợ khách +500.000đ". Có giảm giá thì số gốc (trước giảm) còn lớn
  hơn số khách phải chuyển. Bài giả lập không bắt được vì `_so_that` chép đúng công thức của sổ.

**Báo oan đã loại (nhóm B):** ghi nợ thiếu khoá (có `FOR UPDATE` lượt + chỉ mục duy nhất một dòng
CHUA_THU/lượt); CK chờ đóng nợ sớm (lần chờ không phát `service_collected`, có test); khoá tư vấn
sổ lệch trigger (cùng chuỗi `so_no:<clinic>:<visit>`); việc tồn đếm CK chờ hai lần
(`danh_sach_hoa_don_service.py:404` đã trừ). Khối này không có hàm nào nhận ngày/giờ từ người dùng.

## Nhóm C — Báo cáo cuối ngày, chốt ca, danh sách hoá đơn, MISA, đối tác

> Do agent con soát; người soát chính đã mở lại code C1, C3, C5.

### C1 · VỪA · Hai màn báo cáo dùng HAI mốc ngày khác nhau cho phiếu huỷ và khoản hoàn → cùng ngày, hai số

- **Ở đâu:** báo cáo cuối ngày lọc phiếu (kể cả VOIDED) theo **ngày thu** `paid_at`
  (`bao_cao_cuoi_ngay_service.py:943-947`) và khoản hoàn theo **ngày lập** `created_at` (`:1003-1006`);
  danh sách hoá đơn tính huỷ theo **ngày huỷ** `closed_at` (`danh_sach_hoa_don_service.py:63`) và
  hoàn xong theo **ngày hoàn xong** `completed_at` (`:83-96`). Comment `hoa_don_projection.py:199-202`
  nói hai màn "cùng định nghĩa" — không đúng.
- **Kịch bản 1:** ca chưa chốt; 20/10 thu 900.000đ TM, 21/10 huỷ phiếu. Báo cáo cuối ngày: 20/10 thực
  thu 0, 21/10 là 0. Danh sách hoá đơn: 20/10 **+900.000đ**, 21/10 **−900.000đ**.
- **Kịch bản 2:** 20/10 21:00 lập hoàn CK 500.000đ (chờ), 21/10 09:00 xác nhận. Báo cáo cuối ngày
  ghi hoàn ở 20/10, danh sách hoá đơn ghi ở 21/10; nếu ca tối 20/10 đã chốt thì bản chụp ghi "chờ",
  không ca nào của 21/10 có 500.000đ, trong khi sao kê ngân hàng ra tiền ngày 21/10.
- **Độ chắc:** chắc chắn. Test hiện có (`test_doi_chieu_hoa_don_db::test_t1`) chỉ chạy trong một ngày.
- **Test đề xuất:** thu ngày N, huỷ / xác nhận hoàn ngày N+1 → so tổng hai màn cho cả N và N+1.
- **Hướng sửa:** một định nghĩa mốc ngày dùng chung (đề xuất: ngày tiền thật ra — `completed_at`
  cho hoàn, ngày huỷ cho phiếu huỷ, trừ ca đã chốt theo luật G4c). **Cần Tuyền chốt.**

### C2 · VỪA · Đổi hình thức thu (TM ↔ CK) sau khi ca đã chốt: báo cáo ngày lệch bản chụp ca, không ai báo

- **Ở đâu:** `doi_hinh_thuc_service.py:298-307` (không xét `chot_so_ca`); báo cáo luôn đọc hình
  thức mới nhất (`bao_cao_cuoi_ngay_service.py:922-924`); `chot_so_ca_service.py:103-111`
  (`chenh_sau_chot` chỉ so 4 tổng thu/huỷ/hoàn/thực thu — đổi hình thức không đổi tổng nào).
- **Kịch bản:** ca sáng 20/10 chốt TM 10.000.000đ; 21/10 đổi một phiếu 800.000đ của ca ấy sang CK.
  Xem ca sáng 20/10 của một cơ sở: vẫn TM 10.000.000đ, không cờ "phát sinh sau chốt". Xem cả ngày
  20/10: TM **9.200.000đ**. Két ca sáng đã nộp 10 triệu tiền mặt — hai màn cùng ngày lệch 800.000đ.
- **Độ chắc:** chắc chắn. **Test:** chốt ca → đổi hình thức → báo cáo ngày phải khớp bản chụp hoặc có
  dòng điều chỉnh ở ca đang làm.
- **Hướng sửa (Tuyền chọn):** chặn đổi hình thức phiếu thuộc ca đã chốt (Quản lý mở khoá trước),
  hoặc áp luật như huỷ sau chốt (ca cũ giữ, ca đang làm ghi điều chỉnh TM −800.000 / CK +800.000);
  tối thiểu `chenh_sau_chot` so theo từng hình thức.

### C3 · (liên quan A2) · Báo cáo trừ hai lần khi phiếu vừa bị huỷ vừa có khoản hoàn

- `gom_bao_cao` cộng toàn bộ tiền phiếu vào "huỷ" (`bao_cao_cuoi_ngay_service.py:209, 215`) **và**
  cộng khoản hoàn (`:271-272`). Thuốc: phiếu 1.000.000đ, hoàn 400.000đ TM rồi huỷ phiếu (luật CP5 R7
  cho phép, `test_tien_thuoc_cp5_db.py:285`) → thực thu **−400.000đ**. Dịch vụ: theo A2 → thực thu
  −900.000đ cho phiếu 900.000đ. Hai màn khớp nhau nhưng cùng sai — hoặc khách đã được trả 1,4 triệu.
  Cần Tuyền chốt: huỷ phiếu sau khi đã hoàn thì trả khách đủ tiền phiếu hay tiền phiếu trừ phần đã hoàn.

### C4 · VỪA · "Đánh dấu đã xuất MISA" dựng lại danh sách lúc bấm, không theo file đã tải

- **Ở đâu:** `hoa_don_misa_service.py:79-117` (`danh_dau` gọi lại `doc_goc` mỗi lần bấm).
- **Kịch bản:** 10:00 tải file ngày 22/10 (30 hoá đơn, 45.000.000đ) → 10:02 quầy thu thêm phiếu
  900.000đ → 10:05 bấm đánh dấu → **31** hoá đơn ghi "đã xuất"; phiếu 900.000đ không có trong MISA
  nhưng không bao giờ hiện "có thay đổi" → **sót hoá đơn GTGT**. Hoàn tiền xen giữa cũng làm dấu vân
  tay lấy số mới.
- **Độ chắc:** chắc chắn. **Test:** tải → thu thêm → đánh dấu → phiếu mới không được "đã xuất".
- **Hướng sửa:** file tải kèm danh sách mã phiếu + dấu vân tay; đánh dấu chỉ ghi phiếu còn khớp.
- Phụ: khoảng ngày > 92 ngày bị cắt im lặng (`cashier_board_service.py:1073-1074`) nhưng bản ghi lưu
  khoảng gốc.

### C5 · THẤP · Ngày cực trị gây lỗi 500 (trái luật "ngày rác trả rỗng")

- `?den=9999-12-31` ở `/reports/cuoi-ngay`, `/hoa-don`, `/hoa-don/xuat`, `POST /hoa-don/misa-xuat`,
  `POST /reports/chot-ca` → `b + timedelta(days=1)` tràn `OverflowError`
  (`danh_sach_hoa_don_service.py:271`, `bao_cao_cuoi_ngay_service.py:1274, 1299`, `khung_ca`).
  Chắc chắn. **Sửa:** năm ngoài 2000–2100 coi như rác → hôm nay; thêm test đầu vào rác.

### C6 · THẤP · Các điểm nhỏ khác

| Ở đâu | Lỗi |
|---|---|
| `xuat_hoa_don_service.py:166-171` + `hoa_don_misa_service.py:277-283` | Hoá đơn đã xuất MISA rồi bị huỷ / hoàn hết thì biến khỏi màn xuất, không đếm vào "có thay đổi sau xuất" (vd 900.000đ xuất 20/10, huỷ 21/10 → `so_co_thay_doi_sau_xuat = 0`) |
| `doi_tac_service.py:84-89` | `doc_so_tien` bỏ hết dấu chấm/phẩy: "900,000.00" → **90.000.000đ** (dưới trần 100 triệu nên lọt); "²" qua `isdigit()` rồi `int()` ném → 500 |
| `chot_so_ca_service.py:179-208` | Chốt được khi ca chưa hết giờ; chụp báo cáo trước INSERT nhưng giờ chốt lấy lúc INSERT — phiếu xen giữa hiện ngay ở "sau chốt" (không mất tiền) |
| `thue_suat_service.py:131-139, 164-172` | Sự kiện đặt thuế suất không ghi giá trị cũ |

**Báo oan đã loại (nhóm C):** chốt ca hai lần cùng lúc (chỉ mục duy nhất `uq_chot_so_ca_con_hieu_luc`,
có test); gắn công ty hai người cùng lúc (`FOR UPDATE OF pc` + `uq_hoa_don_cong_ty_cycle`); tiền đối
tác tự thu vào két (báo cáo chỉ lấy `billing_owner='CLINIC'`, có test); múi giờ (mọi câu SQL dùng
`AT TIME ZONE 'Asia/Ho_Chi_Minh'`); CK chờ vào số thu (không — `paid_at` chỉ đặt lúc xác minh); mở
khoá ca / bỏ đánh dấu MISA / bỏ công ty / huỷ ghi nhận đối tác đều hoàn tác được và có vết.
