# Pha 1 — Soát kho thuốc, quầy thuốc và kho vật tư

Ngày kiểm: 22/10/2026 · Nhánh: `codex/soat-kho-quay-vat-tu` từ `origin/main`.

## Kết luận cho người duyệt

Các luồng kho/quầy/vật tư đã có service tách biệt, sổ giao dịch và nhiều đường ghi nhận sự kiện; các mô phỏng nghiệp vụ hiện có chạy xanh. Tuy vậy, hợp đồng cập nhật liên màn của ba bảng lõi kho thuốc chưa đầy đủ, và service nhập lô không ghi domain event. Bộ test mới giữ hai thiếu sót này thành `xfail(strict=True)` để CI báo ngay khi trạng thái thay đổi.

Phân quyền có kiểm ở backend. Tuy nhiên, migration mở rộng lego cấp nhiều quyền cho nhân sự nội bộ theo mặc định, nên chưa đáp ứng mục tiêu vận hành “quản lý bật từng người” nếu không rà lại dữ liệu quyền theo từng nhân viên. UI staging được xem ở 375px và 1280px bằng tài khoản quản lý; không phát sinh giao dịch staging trong phiên này. Việc tắt quyền bằng tài khoản nhân viên, kiểm tra log server, hai tab cùng thao tác và luồng giao dịch UI chưa được thử.

## Phạm vi, nguồn và giới hạn

- Đọc luồng service/router/UI/migration theo `docs/BAN-DO-SUA.md` và `docs/BAN-DO-CODE.md`; đối chiếu 12 mục trong bản kiểm kê nền được giao, đã tổng hợp lại ở mục D.
- Chạy mô phỏng gọi service thật trên DB thử cô lập: 7 tệp mô phỏng, 295 passed; có chuỗi ngẫu nhiên hạt cố định 40 lượt × 10 bước. Chạy riêng test hợp đồng mới: 2 xfailed, không XPASS.
- Quan sát UI chỉ là snapshot của staging đã đăng nhập, tại hai cỡ 375×812 và 1280×900. Kho vật tư staging trống tồn/lịch sử/duyệt; không đủ dữ liệu để bấm giao dịch. Không dùng staging làm nơi diễn tập thao tác ghi.
- Số liệu staging là trạng thái tại thời điểm xem: kho thuốc hiển thị 81 lô, 107 thuốc; cấp thuốc 50 lượt đang xử lý; thu ngân 59 lượt chờ và 216 lượt đã thu xong; danh mục thu ngân hiện 108 thuốc. Dữ liệu định danh khách không được đưa vào báo cáo.
- Không đọc log API/container hoặc worker `su-kien`; không thử đổi lego, không có tài khoản nhân viên thử quyền; không thử hai tab khác vai. Vì vậy các phần đó được ghi “chưa xác minh”, không suy diễn từ browser console.

## A. Bản đồ nghiệp vụ: thao tác → service → bảng → sự kiện → màn nghe → khôi phục

| Thao tác | Service / ghi dữ liệu chính | Vết / sự kiện | Màn có thể cập nhật | Hoàn tác / giới hạn |
|---|---|---|---|---|
| Nhập lô thuốc trực tiếp | `PharmacyService.nhap_lo` (`pharmacy_service.py:542`); `drug_batch`, `inventory_txn`, khóa idempotency | Ghi log ứng dụng, nhưng chưa `record_event`/`_log`/`emit_event` cho lô; test hợp đồng xfail 1 | Màn kho dùng API đọc lô; chưa có trigger `drug_batch`/`inventory_txn`, chưa có hai bảng này trong `LIVE_TABLES` | Ghi điều chỉnh ngược có lý do; chưa có nút undo nhập lô riêng |
| Nhập bằng phiếu kho thuốc | `kho_thuoc_service.tao_phieu_nhap` (`:488`); `phieu_kho`, dòng phiếu, `drug_batch`, `inventory_txn` | `ghi_nhat_ky pharmacy.phieu_nhap` (`:631–634`) | Không có trigger `trg_notify_phieu_kho`; cần nạp lại hoặc nguồn refresh khác | Phiếu đã ghi không xóa sổ; tạo phiếu/điều chỉnh đối ứng |
| Sửa mã lô / hạn dùng | `lo_thuoc_service.sua_lo` (`:72`); cập nhật `drug_batch` | `pharmacy.batch_updated` (`:116–119`) | `drug_batch` chưa nằm trong `LIVE_TABLES`; chưa có trigger bảng | Sửa lại giá trị cũ; audit vẫn giữ lịch sử |
| Hủy lô / hoàn hủy lô | `huy_lo`, `hoan_huy_lo` (`lo_thuoc_service.py:135,193`); ghi `inventory_txn` | `pharmacy.batch_discarded`, `pharmacy.batch_discard_undone` (`:178–181`, `:231–234`) | Cập nhật kho thuốc bị ảnh hưởng bởi thiếu trigger `inventory_txn` | Có luồng hoàn hủy riêng, tạo giao dịch đối ứng; có điều kiện theo tồn đã phát sinh |
| Điều chỉnh / hủy tồn | `PharmacyService.dieu_chinh`, `huy` (`pharmacy_service.py:1721,1752`); `inventory_txn` | `pharmacy.adjusted`, `pharmacy.discarded` (`:1748`, `:1771`) | Không có trigger `inventory_txn` | Tạo giao dịch ngược; không xóa giao dịch gốc |
| Kiểm kho / nhập số kiểm | `kho_thuoc_service.kiem_kho` (`:658`); phiếu và chênh lệch sổ kho | `pharmacy.kiem_kho` (`:759–762`) | Sự kiện bảng kiểm/phiếu; sổ `inventory_txn` thiếu notify chung | Kiểm lại rồi ghi điều chỉnh có căn cứ |
| Mở, lưu đếm, chốt kiểm kê ca | `kiem_ke_ca_service.mo_phieu`, `luu_dem`, `chot` (`:645,765,884`); `kiem_ke_ca`, dòng kiểm và giao dịch điều chỉnh | Nhật ký `pharmacy.kiem_ke_ca_mo`, `..._chot`; chênh lệch phát `pharmacy.stocktake_mismatch` (`:701–704`, `:982–998`) | `kiem_ke_ca` có trigger + nằm trong `LIVE_TABLES`; `inventory_txn` vẫn thiếu notify | Sửa số đếm thành phiên bản hiệu chỉnh (`:1271`); điều chỉnh có `hoan_tac_dieu_chinh` (`:1194`) nếu chưa phát sinh giao dịch làm mất điều kiện |
| Chuyển thuốc kho ↔ quầy | `kho_thuoc_service.chuyen_kho`, `hoan_tac_chuyen` (`:1023,1102`); phiếu và cặp giao dịch sổ | `pharmacy.chuyen_kho`, `pharmacy.chuyen_kho_hoan_tac` (`:1077–1080`, `:1169–1172`) | Cần refresh màn kho/quầy; bảng lõi vẫn thiếu notify | Có hoàn tác một lần nếu tồn cho phép trả lại |
| Thuốc đã thu, giao đủ/một phần | `PharmacyService.cap_phat` (`pharmacy_service.py:672`); cập nhật `prescription`, ghi `inventory_txn` khi trừ lô | `medicine.dispensed` và nhật ký `pharmacy.dispensed` (`:779`, `:929`, `:995`, `:1330`) | `prescription` nằm trong `LIVE_TABLES`; sổ tồn không có trigger riêng | Giao dịch dương/âm phải qua luồng sửa/điều chỉnh có audit; không thấy nút hoàn tác ngay trên dòng cấp thuốc |
| Gán lô sau khi giao | `PharmacyService.gan_lo_da_giao` (`:1115`); cập nhật gán và `inventory_txn` | Nhật ký `pharmacy.lot_assigned` (`:1211`) | Thiếu notify `inventory_txn` | Đổi/gỡ gán qua API có kiểm soát; chưa xác minh luồng đảo giao dịch sau khi đã gán |
| Từ chối / chốt dòng không giao thêm | `tu_choi`, `chot` (`:1686,1703`); cập nhật `prescription` | `pharmacy.refused`, `pharmacy.line_closed` (`:1700,1718`) | `prescription` có notify và nằm trong danh sách live | Không thấy API mở lại chuyên biệt; cần sửa qua luồng quản lý có audit nếu được cấp quyền |
| Khách trả thuốc / kiểm thuốc trả | `khach_tra_thuoc`, `xu_ly_thuoc_tra` (`:1875,2098`); `drug_return`, sổ tồn, có thể kèm hoàn tiền | `pharmacy.drug_returned`, `medicine.returned`, `pharmacy.drug_return_decided` (`:2007,2022,2191`) | `payment_refund*` được nghe chung; trigger riêng cho `drug_return`/`inventory_txn` chưa thấy trong danh sách đã rà | Chọn nhập bán lại hoặc hủy; quyết định một lần, không có đảo tùy tiện |
| Thu tiền thuốc / hoàn / hoàn tác phiếu thu | `PaymentService.record_payment`, `hoan_tac` (`payment_service.py:353,1625`); `payment`, `payment_cycle`, dòng bill/allocations, refund | Có domain event và bảng hoàn; payment/refund có trigger và refresh theo từng màn | `RealtimeRefresher` có `payment`, refund; `BanLeThu` nghe thêm `payment_cycle` (`BanLeThu.tsx:88`) | Hủy/hoàn tiền/hoàn tác theo kiểm quyền, trần số tiền và điều kiện trạng thái; hoàn ≤ đã thu là bất biến được mô phỏng |
| Chọn thuốc, sửa SL, bán thêm tại quầy | `QuayThuocService.chon`, `doi_so_luong`, `luu_dong_them` (`quay_thuoc_service.py:223,265,398`); `prescription` | `record_event pharmacy.counter_changed` + `emit_event medicine.counter_changed` (`:159–177`) | `prescription`/`visit` có refresh | Có thể chỉnh lại số lượng trước thu; sau thu phải dùng luồng hoàn/hủy hợp lệ |
| Lập/hoàn phiếu vật tư | `vat_tu_kho_service.tao_phieu`, `hoan_phieu` (`:308,357`); `vat_tu_phieu`, `vat_tu_txn`; trigger duy trì `vat_tu_ton` | Phiếu kho và sổ giao dịch; lô nhập cần duyệt chuyển sang `vat_tu_nhap_cho_duyet` | Ba bảng tồn/kho có trigger; `KhoVatTu.tsx:72` nghe `vat_tu_txn`; màn chờ duyệt nghe `vat_tu_nhap_cho_duyet` (`ChoDuyetVatTu.tsx:86`) | Hoàn phiếu là giao dịch ngược; yêu cầu nhập chờ duyệt có luồng duyệt/rút/từ chối |
| Vật tư gắn vào lượt khám / sửa SL / bỏ | `VatTuService.them`, `dat_so_luong`, `bo` (`vat_tu_service.py:342,488,534`); `luot_vat_tu` | `emit_event` + `record_event` (`:596–617`); trigger notify `luot_vat_tu` ở migration `20261003000000` | Có trigger bảng; chưa xác nhận toàn bộ màn tiêu thụ nào đang nghe bảng này | Bỏ là soft-delete (`bo_luc`, `bo_boi`), có dấu người thao tác |

`event_log` được `trg_notify_event_log` đánh thức relay ở migration `20260815000003`; đây là đường relay sự kiện server, không tự thay thế trigger của bảng nghiệp vụ hay bảo đảm từng màn UI đang nghe. `RealtimeRefresher.LIVE_TABLES` ở `RealtimeRefresher.tsx:88–145` có `prescription`, `payment`, `payment_refund*`, `vat_tu_*`, `kiem_ke_ca`; hiện không có `drug_batch`, `inventory_txn`, `phieu_kho`, `payment_cycle`, `luot_vat_tu`. Một số trang có `useNgheBang` riêng nên cần kiểm theo từng consumer trước khi kết luận toàn hệ thống không refresh.

## B. Test và bất biến

| Bài kiểm | Cách làm | Kết quả |
|---|---|---|
| Mô phỏng kho/quầy/tiền/vật tư | Gọi service thật trên DB thử cô lập, qua 7 tệp `test_mo_phong_kho_thuoc_db.py`, `test_kho_quay_db.py`, `test_mo_phong_kho_day_du_db.py`, `test_kiem_ke_ca_db.py`, `test_quay_thuoc_db.py`, `test_mo_phong_dong_tien_db.py`, `test_mo_phong_vat_tu_day_du_db.py` | **295 passed**; hai bài mô phỏng có chuỗi hạt cố định 40×10 |
| Domain event khi nhập lô | Tạo lô bằng luồng service, đếm `event_log` theo `aggregate_id` | **xfail(strict=True)**: `PharmacyService.nhap_lo` chưa ghi event |
| Trigger notify ba bảng kho | Kiểm tra `trg_notify_drug_batch`, `trg_notify_inventory_txn`, `trg_notify_phieu_kho` trên DB thử | **xfail(strict=True)**: thiếu trigger tương ứng |

Mô phỏng hiện có kiểm các phép cộng/trừ sổ kho, giới hạn giao so với số lượng đã thu, hoàn không vượt thu, đối chiếu thuần sau hoàn và điều kiện hoàn tác. Mục tiêu “mọi thao tác UI, mọi vai, hai tab, mọi API và mọi log 4xx/5xx” chưa được bao phủ trong lần này. Test mới ở `src/tests/services/test_kho_quay_event_contract_db.py`; lỗi mới đánh strict xfail để khi sửa service/migration về sau thì XPASS làm CI yêu cầu gỡ xfail.

## C. Quyền màn hình và API

| Màn / API | Lego | Chặn phía backend | Bằng chứng hiện tại |
|---|---|---|---|
| `/pharmacy`, `/pharmacy/inventory`, `/pharmacy/history`, `/pharmacy/consult` và `/api/v1/pharmacy/*` | `pharmacy.view` hoặc `pharmacy.dispense` để vào/đọc; thao tác ghi dùng `pharmacy.dispense` | Router dùng guard `_DOC`, `_GHI` trong `src/clinicai/api/v1/routers/pharmacy.py:52–53`; service kiểm quyền trong luồng ghi | Đọc mã; chưa thử tài khoản bị tắt lego |
| `/thu-ngan/thuoc`, `/thu-ngan/thuoc/lich-su`; `/api/v1/payments*`, `/api/v1/quay-thuoc*` | `payment.medicine.collect` / `payment.medicine.history` theo đường | `PaymentService._assert_kind_allowed` và `payment_access_service.authorize_payment` kiểm quyền loại thuốc (`payment_service.py:330–350`, `payment_access_service.py:20–52`) | Đọc mã; không tạo/hủy/hoàn giao dịch staging |
| `/kho-vat-tu`; `/api/v1/vat-tu-kho/*` | `vat_tu.manage`; quyền duyệt nhập là lego riêng | Router `_QL` trong `src/clinicai/api/v1/routers/vat_tu_kho.py:29` và kiểm ở service duyệt | Đọc mã; màn staging không có tồn để thao tác |
| Điều hướng frontend | `NAV_QUYEN`: các đường trên khai báo ở `src/dashboard/lib/roles.ts:644–662` | Là lớp ẩn/hiện; không thay kiểm quyền backend | Đã đọc cấu hình; chưa tắt quyền để kiểm luồng 403 |

**Rủi ro triển khai quyền:** `supabase/migrations/20260930900000_mo_full_lego.sql:1–52` cấp rộng các lego cho phần lớn tài khoản nội bộ và tắt cổng role/shift theo ghi chú migration; migration `20261014181100_lego_kho_vat_tu.sql:14–30` thêm `vat_tu.manage` cho nhân viên đang hoạt động trừ nhóm ngoại lệ. Đây là cấu hình dữ liệu mặc định, không chứng minh backend bỏ chốt. Đề nghị rà quyền từng nhân viên tại `/phan-quyen` trong một phiên có tài khoản thử chuyên biệt; không chạy migration thu hẹp hàng loạt trong Pha 1.

## D. Giao diện staging, đối chiếu 12 điểm nền

**Quan sát mới:** ở 375px, bảng tồn kho thuốc rộng hơn viewport; cột bên phải và thao tác chỉ thấy sau cuộn ngang, không có gợi ý cuộn rõ. Ở màn cấp thuốc, danh sách và chi tiết xếp nối dọc; phải cuộn qua danh sách dài mới tới phần chi tiết, các nhãn lý do bị bó hẹp. Ở 1280px, bảng và bố cục danh sách/chi tiết dễ đọc hơn. Trên một dòng đã giao đủ vẫn hiện trường lý do và nút “Chốt — không giao thêm”.

| # nền | Kết quả đối chiếu 22/10 | Mức / phân loại / độ chắc |
|---|---|---|
| 1. Thuốc đang bán thiếu lô / lô demo gắn tên khác | Mốc kiểm kê nền được giao ghi 55/107 thiếu lô; lần này kho có 107 thuốc, 81 lô. Chưa chạy truy vấn đối chiếu lại từng mã | Cao, dữ liệu; cần đối soát danh mục và lô trước khi nạp tồn thật |
| 2. Lô phù hợp không được gán cho dòng đã giao | Baseline có ví dụ thiếu lô do tên/đơn vị khác; lần này chưa ghi một giao dịch thử để xác nhận phép gán | Cao, dữ liệu/đơn vị; chưa tái lập trong phiên |
| 3. Đơn đã thu còn treo giao, thiếu tuổi đơn | Có 50 lượt đang xử lý; chưa rà đủ ngày tạo của mỗi lượt | Cao, luồng vận hành/UI; cần tuổi đơn và lọc quá hạn |
| 4. Thu ngân nhận đơn thiếu SL dẫn đến 0đ | Có 59 lượt chờ; chi tiết được chọn có 5 dòng thiếu lượng bác sĩ nhập và tổng 0đ, nút tạo bill tắt | Vừa, tái hiện trực tiếp; không chỉnh/lưu số lượng |
| 5. Hàng chờ gồm lượt cũ/không mua, thiếu đóng “không lấy” | Snapshot có 59 chờ; chưa phân loại toàn bộ ngày/nhánh đóng | Vừa, cần lọc theo ngày và kiểm luồng bỏ qua có undo |
| 6. Dòng “Đã giao đủ” vẫn hiện lý do và nút chốt | Tái hiện trực tiếp ở dòng đã giao đủ | Thấp, UI; ẩn trường/nút khi trạng thái đã kết thúc |
| 7. Không có hoàn tác ngay sau giao | Nút xem lịch sử mở hồ sơ lượt khám chỉ xem; không thấy hành động hoàn tác tại dòng thuốc | Vừa, UI/luồng; cần chỉ rõ đường xử lý an toàn hoặc thêm hoàn tác có kiểm soát |
| 8. Ở khoảng 800px không thấy chi tiết | Chưa đo lại đúng 800px; tại 375px chi tiết nằm dưới danh sách dài | Vừa, responsive; một phần được tái hiện ở màn hẹp |
| 9. Hướng dẫn “Tồn theo lô” lệch tên tab | Dòng chờ gán lô nói vào “Tồn theo lô”; tab thực tế ghi “Thuốc trong kho” | Thấp, chữ; tái hiện trực tiếp |
| 10. Danh mục 108 ở quầy vs 107 ở kho | Màn thu ngân hiển thị 108, kho hiển thị 107 | Thấp, dữ liệu/lọc; cần xác định khác nhau do trạng thái/điều kiện lọc nào |
| 11. “THUỐC ĐÃ KÊ” lặp nội dung danh sách phía trên | Có hai khối trong màn thu ngân với cùng danh sách kê | Thấp, UI; tái hiện trên snapshot |
| 12. Kiểm đầu ca phải đếm mọi mặt hàng, có cả hàng không hoạt động | Baseline ghi 81 dòng; lần này chưa đối chiếu cờ hoạt động từng dòng, nên chưa kết luận có bao gồm hàng ngừng bán | Thấp, UI/danh mục; cần lọc theo tồn hoặc hoạt động |

**Đề nghị UX:** trên điện thoại chuyển bảng lô thành thẻ hoặc thêm thanh cuộn ngang ghim/nhãn cột; trên cấp thuốc ghim danh sách và chi tiết theo tab hoặc drawer; ẩn điều khiển sau trạng thái đã giao đủ; dùng cùng tên tab trong hướng dẫn; thêm ngày kê và tuổi đơn; hiển thị rõ “thiếu lô/khác đơn vị” và cách xử lý; bỏ khối “THUỐC ĐÃ KÊ” lặp; cho phép lọc danh sách kiểm đầu ca theo hoạt động/tồn. Không gộp hoàn tiền với hoàn giao thuốc vì hai sổ khác nhau.

## E. Thống nhất với hệ thống sự kiện và quy tắc chung

- Frontend vẫn là UI; thao tác nghiệp vụ nằm trong service Python. Thu tiền và vật tư dùng các service quyền/audit/event chung; service nhận thuốc trực tiếp là chỗ lệch rõ nhất vì chỉ có `logger.info` mà chưa ghi event nghiệp vụ.
- Có hai hợp đồng khác nhau cần cùng tồn tại: domain event/`event_log` cho audit và consumer server; trigger `notify_row_change` + bảng được listener theo dõi để màn đang mở tự tải lại. Một loại không tự bù cho loại còn thiếu.
- `event_log` có notify riêng cho relay (insert-only); không nên thêm nó vào listener làm mới toàn trang một cách máy móc. `LIVE_TABLES` cũng loại trừ có chủ ý `thong_bao` và `slot_hold`; sửa danh sách phải dựa trên consumer thực tế.
- Kho vật tư đã có sổ giao dịch + bảng tồn dẫn xuất + hoàn phiếu ngược; kho thuốc có nhiều đường audit nhưng các bảng lõi chưa đồng bộ notify. Ca kiểm kê thuốc đã có event và trigger riêng, nhưng notify của giao dịch điều chỉnh vẫn thiếu.
- Không có dấu hiệu Pha 1 cần gộp với thay đổi đơn vị hộp/gói `#499`. Cần Tuyền quyết phương án dữ liệu mã thuốc/lô và quy đổi đơn vị trước khi làm sạch tồn thật.

## SO-LUAT 12.4 — Bàn giao theo bốn mục

### 1. Đã đổi gì

Pha 1 bổ sung hai test hợp đồng strict xfail cho domain event nhập lô và notify của ba bảng kho thuốc. Báo cáo này ghi luồng nghiệp vụ, quyền, sự kiện, quan sát UI và kế hoạch sửa để Tuyền duyệt. Không có sửa code sản phẩm.

### 2. Kịch bản bấm thử

1. Đăng nhập một tài khoản thử có quyền dược sĩ và mở `/pharmacy/inventory`; xem danh sách lô ở 375px và 1280px, cuộn tới cột cuối.
2. Trên DB thử cô lập, nhận một lô demo rồi kiểm `drug_batch`, `inventory_txn`, `event_log`; xác nhận các màn kho mở ở tab khác nhận refresh khi có trigger.
3. Với đơn thử đã thu, giao một phần rồi xem sổ kho, dòng đơn và lịch sử; thử đường hoàn tác có kiểm soát, không dùng khách thật.
4. Trên tài khoản nhân viên dùng để thử quyền, tắt một lego ở `/phan-quyen`; xác nhận menu biến mất và API tương ứng trả 403; sau đó bật lại quyền.
5. Trên DB thử cô lập, lập một phiếu vật tư và hoàn phiếu; so sổ `vat_tu_txn` với `vat_tu_ton`.

Đây là kịch bản đề nghị cho Pha 2; các bước ghi giao dịch và tắt quyền chưa chạy trong lượt Pha 1.

### 3. Những gì không đổi

Không sửa nghiệp vụ sản phẩm, không sửa migration, không đổi quyền, không ghi phiếu/thu tiền/giao thuốc ở staging, không nạp/ghép dữ liệu thuốc, không merge, không deploy. `#499` vẫn để riêng chờ Tuyền quyết.

### 4. Rủi ro còn lại

Chưa xác minh quyền từng nhân viên và 403 thực tế; chưa xem log API/worker; chưa kiểm hai tab; staging vật tư trống; dữ liệu tên/đơn vị thuốc có thể làm giao hàng mà không trừ kho; thiếu notify có thể khiến màn khác chưa tự cập nhật; mô phỏng DB không thay thế nghiệm thu UI đầy đủ.

## Bảng “nút/link đã đụng” trong lần Pha 1

| Trang / nút | Hành động | Kết quả / có ghi dữ liệu? |
|---|---|---|
| `/thu-ngan/thuoc` | Mở trang; xem tab chờ thu và chi tiết một lượt | Chỉ đọc; không tạo bill, không lưu SL đã thử trong phiên trước |
| `/pharmacy` | Mở trang; chọn một đơn đã thu | Chỉ đọc; không bấm “Giao thuốc”, “Chốt” hoặc “Từ chối” |
| “Xem chi tiết lượt & lịch sử cấp” | Mở rồi đóng cửa sổ lịch sử | Chỉ xem; cửa sổ ghi rõ không sửa được |
| `/pharmacy/inventory` | Xem tồn kho và các tab ở 375px/1280px | Chỉ đọc; không nhập/sửa/hủy/điều chỉnh lô |
| `/kho-vat-tu` → “+ Thêm vật tư” | Mở form nháp rồi đóng | Không lưu phiếu; bảng tồn, lịch sử, duyệt đang trống |
| Tab/vùng khác | Không mở hoặc không thao tác trong phiên này | Chờ kịch bản thử local/DB thử ở bước sau |

## Kế hoạch Pha 2 để Tuyền duyệt

| PR đề xuất (mỗi PR ≤400 dòng) | Nội dung | Migration | Rủi ro và hoàn tác |
|---|---|---|---|
| 1. Event nhập lô | Ghi domain event/audit cùng transaction với lô; bổ sung test chống ghi event lệch/ghi lặp | Không bắt buộc | Event trùng hoặc thiếu actor; rollback bằng revert service, dữ liệu event đã ghi vẫn giữ audit |
| 2. Realtime kho thuốc | Trigger notify cho `drug_batch`, `inventory_txn`, `phieu_kho`; thêm đúng consumer/listener cho màn đang mở; test hợp đồng theo bảng và consumer | Migration mới riêng, soát dải số trước khi tạo | Tăng tần suất refresh; rollback migration bằng `DROP TRIGGER` tương ứng và revert listener |
| 3. Dễ dùng trên màn hẹp | Sửa riêng bảng tồn lô và detail cấp thuốc; xử lý dòng đã hoàn tất, tên tab và nội dung lặp | Không | Thay đổi bố cục; revert UI PR |
| 4. Xác minh quyền theo nhân viên | Tạo user thử staging/local; kiểm menu + 403 cho mỗi lego, rà roster thực tế cùng quản lý | Không tự thu hẹp quyền bằng migration; nếu cần chỉnh dữ liệu, làm phiên riêng có duyệt | Khóa nhầm nhân viên khỏi màn; bật lại lego cũ theo danh sách chụp trước thay đổi |
| 5. Làm sạch dữ liệu thuốc | Đối soát SKU/trùng tên/đơn vị/lô; đề xuất ghép và nhập tồn từ nguồn kiểm kê đã duyệt | Không trộn với PR code; data plan riêng | Có thể làm sai tồn hoặc lịch sử; chụp snapshot và diễn tập trên bản sao trước khi ghi |

**Điều kiện vào Pha 2:** Tuyền chốt chủ sở hữu thao tác “Giao thuốc”, cách giải quyết lô khác đơn vị, nguồn dữ liệu tồn thật và người dùng thử quyền. Không gộp với `#499` trước khi có quyết định quy đổi.
