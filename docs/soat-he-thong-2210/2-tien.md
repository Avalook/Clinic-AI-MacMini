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
