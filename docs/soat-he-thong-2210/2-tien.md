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
