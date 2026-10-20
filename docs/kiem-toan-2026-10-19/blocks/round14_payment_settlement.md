# Round 14 — Thu tiền, phiếu, idempotency và hoàn tiền

**Nguồn kiểm:** snapshot `/tmp/clinicai-audit-main-956ba4f2`, SHA được giao `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Bản export không có `.git`; SHA là pin theo nhiệm vụ, không tự xác minh bằng Git. Đây là kiểm tra tĩnh có chọn lát; không chạy test, app, DB, VPS hay CI.

**Kết quả:** một candidate LOW về ranh giới idempotency của thu dịch vụ và lựa chọn xuất hoá đơn công ty. Không ghi nhận lỗi mới về số tiền thu, phân bổ giảm giá/hoàn tiền, hoặc trạng thái hoàn trong lát đã đọc. Các mục hiện hữu được đối chiếu và loại trừ bên dưới.

## Candidate mới

### CAND-R14-PAY-IDEM-001 — Receipt thu dịch vụ không fingerprint lựa chọn công ty nhưng replay vẫn áp lựa chọn mới

- **Mức / bằng chứng:** LOW; mismatch payload được xác nhận tĩnh, tác động hoá đơn suy ra từ đường ghi và xuất snapshot. Chưa tái hiện HTTP request.
- **Kích hoạt chính xác:** gửi `POST /api/v1/payments` cho `kind=dich_vu`, `Idempotency-Key: K`, cùng các trường tiền như thường nhưng không có `cong_ty_id` (hoặc có company khác). Sau khi lần thu commit, gửi lại cùng K với mọi trường được fingerprint không đổi nhưng đổi `cong_ty_id` sang công ty hợp lệ của đúng khách. Tác động chỉ có nếu payment cycle chưa có snapshot `hoa_don_cong_ty`.
- **Chuỗi code:** `PaymentService._thu_dich_vu` dựng payload receipt gồm visit/kind/patient/revision/method/amount và có điều kiện thêm split/discount/selection; không gồm `cong_ty_id` (`payment_service.py:740-757`). `bien_nhan_doc` so hash của payload và trả kết quả cũ khi hash khớp (`lenh_kham_core.py:180-201`). Router nhận kết quả/replay rồi vẫn gọi `_gan_cong_ty` bằng body hiện tại (`payment.py:130-156, 193-213`). Nếu cycle chưa có snapshot, `gan_khi_thu` ghi company đang có trong request (`hoa_don_cong_ty_service.py:581-630`). Cùng key vì thế không tạo lần thu thứ hai, nhưng field bị bỏ khỏi hash có thể đổi đơn vị mua của snapshot hoá đơn.
- **Tác động:** payload khác qua cùng key không bị từ chối bằng `IDEMPOTENCY_KEY_REUSED`; snapshot hoá đơn có thể được gắn company theo request replay. Bộ xuất chỉ đọc snapshot còn hiệu lực (`hoa_don_cong_ty_service.py:731-748`; `xuat_hoa_don_service.py:246-279`). Đây là sai đích/metadata hoá đơn kế toán, không phải thu tiền hai lần.
- **Giới hạn:** UI hiện tại đưa company ID vào định danh thao tác ở quầy thường và quầy một hoá đơn (`QuayThuNgan.tsx:446-455`, `HoaDonMot.tsx:261-275`), nên đổi lựa chọn trong UI sẽ tạo key khác. Candidate đòi caller tái dùng key với body mới; chưa có bằng chứng việc này từng xảy ra. Không ảnh hưởng tiền thu. Nếu cycle đã có snapshot, kể cả đã bỏ chọn, service không ghi đè (`hoa_don_cong_ty_service.py:581-588`).
- **Test liên quan:** `test_thu_dich_vu_nhieu_lan_db.py:477-500` bao phủ replay cùng body và từ chối cùng key khi đổi phương thức, nhưng không đổi `cong_ty_id`. `test_tick_cong_ty_khi_thu_db.py:173-182` kiểm tra replay không hồi sinh snapshot đã bỏ chọn; `:192-213` kiểm tra helper router ở nhánh thành công/lỗi, không kiểm tra cùng key đổi company. Dashboard boundary tests kiểm tra UI gắn company vào key và BFF chuyển trường, không kiểm tra backend fingerprint.
- **Hướng chấp nhận:** giữ nguyên tắc cùng key + payload khác bị từ chối xuyên suốt lệnh thu: fingerprint `cong_ty_id` trong receipt hoặc tách gắn snapshot thành command riêng có idempotency riêng. Test route/service: cùng key/company replay không thêm snapshot; cùng key nhưng thêm/bỏ/đổi company bị từ chối; key mới mới được phép thực hiện thao tác theo chính sách. Không hồi sinh snapshot đã bỏ chọn.

## Phạm vi đã lần theo

- **Thu dịch vụ:** route/BFF → `record_payment` / `_thu_dich_vu` → receipt trong transaction, bill snapshot, event, cycle; selection/revision, nhiều đợt thu, chia TM/CK, void và refund.
- **Thu thuốc:** nhánh `IdempotencyGuard` và `record_payment`; trạng thái pending/xác minh/đã thu, lệnh nhắm đúng cycle; đối chiếu function inventory của CP2 tests.
- **Hoàn tiền:** route tạo/xác nhận/đóng, quyền, số tiền server tính từ bill line, khoá visit/cycle, reservation pending/completed, CASH và TRANSFER, void và invoice export sau hoàn.
- **Phiếu/hoá đơn:** cashier receipt service/route, BFF và bản in; lịch sử thu; export MISA theo cycle, refund status và snapshot công ty.
- **UI/direct tests:** request thu/hoàn, key và xử lý response, in phiếu; các direct test/service và boundary test liên quan được đọc có chọn lọc, không chạy.

## Đối chiếu candidate hiện hữu

- **INF-007:** không lặp đường `IdempotencyGuard` save receipt sau commit / lease 5 phút có thể chạy lại nghiệp vụ (đã có path refund). Candidate mới dùng receipt transactional để ngăn thu lại, nhưng `cong_ty_id` vắng khỏi payload hash và side effect gắn company vẫn chạy theo body replay.
- **FIN-001:** pinned code dùng phân bổ phần dư lớn nhất và bảo toàn tổng giảm, không vượt giá dòng (`bill_service.py:1254-1276`); không ghi lại lỗi cũ.
- **FIN-004:** làm tròn từng lần refund không giảm giá có thể vượt tiền dòng qua nhiều partial refunds; đã có, không lặp.
- **FIN-005..008:** cap danh sách/sổ/report và kỳ ngày đã có, không đưa vào candidate mới.
- **FIN-009/010/011/012:** giữ ngoài lát này (tiền thừa sau checkout, lý do void đối tác, cutoff chốt ca, phép kiểm đối soát đồng nhất).
- **DB-006/007, PHAR-001/002, POS/outbox findings from round12 (empty), INF-011/017/018:** migration/FK, trả thuốc/tồn kho, POS outbox và event worker; khác failure mode hoặc ngoài phạm vi.

`findings.json` chỉ chứa candidate mới nói trên. `coverage.json` phân biệt code/test đọc có chọn lọc với test chỉ rà tên. Không có test nào được chạy; kết quả không xác nhận lỗi production hoặc tần suất xảy ra.
