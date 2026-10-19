# Kiểm toán kho thuốc và vật tư — 19/10/2026

## Phạm vi và cách kiểm tra

Đã truy vết route/API, service, UI, migration, RLS/SQL grants và test của kho
thuốc cùng kho vật tư. Audit ban đầu trên `HEAD 8a338dcb`; sau đó kiểm tra staging
đang chạy `8033e01` (có chứa các thay đổi P1 đã duyệt). Không sửa dữ liệu prod,
không đọc PHI và không khẳng định phát hiện code đã làm sai tồn thật. Metadata
prod đã truy vấn trước đó không có NaN/Infinity trong các cột tồn/giao dịch.
Trên staging tái hiện nút lưu vật tư vẫn bật với số lượng `-1`; không gửi phiếu,
và API có kiểm tra từ chối số âm nên chưa ghi thay đổi tồn.

## P1 — cần xử lý

| Phát hiện | Căn cứ và tác động | Trạng thái |
|---|---|---|
| PostgREST cho phép nhân viên cùng cơ sở đọc trực tiếp sổ kho dù thiếu quyền kho | RLS của kho vật tư và thuốc lọc theo clinic membership nhưng không kiểm capability. Dữ liệu có tồn, giao dịch, giá nhập, phiếu chờ duyệt/lý do. Chưa thấy quyền ghi cho `authenticated` hay bằng chứng đọc chéo cơ sở. Dashboard hiện lấy dữ liệu qua FastAPI; SSE chỉ gửi tên bảng + clinic. | Thu hồi SELECT trực tiếp trên 11 bảng; staging SHA `8033e01` chứa migration ACL. CI trước đó gồm SQL ACL test và RLS scope test xanh ở `62d11cab`; còn kiểm tra bằng tài khoản staging thiếu quyền. Hai script nạp bản sao staging áp lại ACL sau GRANT rộng. |
| Điều chỉnh kho thuốc nhận giá trị NaN/Infinity | `/pharmacy/adjust` nhận float; service chưa kiểm hữu hạn; CHECK hiện tại chưa chặn rõ mọi số không hữu hạn. Có thể làm sai phép cộng tồn. | Đã thêm chặn ở API/service/DB; test chặn ở unit/API/DB. Có trong staging SHA `8033e01`. Migration `20261019110000_pharmacy_inventory_p1_guards.sql`. |
| Retry điều chỉnh/huỷ lô/nhập lô nhanh có thể ghi lặp | Nếu server đã commit nhưng response mất, gửi lại thao tác không idempotent có thể thêm/xoá tồn lần hai. Luồng nhập cũ `/pharmacy/receive` vẫn được gọi bởi modal `NhapLo.tsx`, nên phải nằm trong xử lý retry. Guard chung lưu response tách khỏi giao dịch sổ không đủ để đóng khe crash. | Đã thêm biên nhận idempotency nguyên tử với ledger cho receive/adjust/discard; UI giữ key qua retry và fail-closed nếu không lưu được key. Có trong staging SHA `8033e01`; CI xanh ở `62d11cab`. |
| Cùng mã lô nhưng khác đơn vị bị cộng vào cùng lô | `nhap_vao_lo()` tìm lại theo clinic/kho/mã lô, nhưng chưa so đơn vị đã chuẩn hoá; cùng mã theo “viên” rồi “hộp” có thể bị cộng chung mà không quy đổi. | Đã chặn khác đơn vị đã chuẩn hoá trên mọi hàng KHO/QUẦY cùng mã lô; có trong staging SHA `8033e01`; regression test xanh ở `62d11cab`. |

## P2 — trạng thái sau lượt sửa hiện tại

1. **Đơn vị vật tư có thể đổi sau khi đã phát sinh giao dịch — đã sửa trên nhánh.**
   Service từ chối đổi đơn vị sau giao dịch; migration `20261019130000` chặn cả
   SQL trực tiếp. Regression test service + DB xanh; staging chưa có migration này.
2. **Báo cáo tiêu hao có thể lấy giá nhập từ phòng khác.** Truy vấn giá theo vật
   tư/thời gian, chưa khoanh cùng dòng tồn (`ton_id`); nếu giá giữa phòng khác
   nhau thì giá trị tiêu hao có thể sai. Đã khoanh giá theo `ton_id`; regression
   test hai phòng khác giá xanh. Staging chưa có thay đổi này.
3. **Phiếu vật tư ngoài loại nhập vẫn nhận giá nhập.** Giá snapshot đó có thể
   ảnh hưởng báo cáo định giá. Đã ẩn trường khỏi loại phiếu khác nhập và API từ
   chối payload có giá; regression test xanh. Staging chưa có thay đổi này.
4. **Idempotency chung chưa gắn key với payload.** Tái dùng cùng key với body
   khác có thể trả kết quả cũ. Đã gắn key với hash body/query, thêm migration
   `20261019140000`, và kiểm thử key trùng body khác bị từ chối. Staging chưa có
   thay đổi này.
5. **Lý do huỷ/điều chỉnh vật tư chưa bắt buộc.** Actor và ledger được lưu nhưng
   thiếu nguyên nhân nghiệp vụ để truy vết.
6. **Giới hạn phân trang thuốc.** Một số danh sách chỉ trả 100 phiếu/1.000 dòng
   thẻ kho; dữ liệu không bị xoá nhưng không truy cập hết qua màn truy vấn đó.
7. **Thuốc khách trả ở trạng thái cách ly chưa có thao tác kết thúc.** Hàng được
   giữ ngoài tồn khả dụng có chủ ý; cần thống nhất nghiệp vụ nhận lại/tiêu huỷ.
8. **Chưa có chuyển kho giữa các cơ sở.** Đây là thiếu chức năng, chưa phải sai
   số tồn.
9. **Vật tư và billing đang tách sổ.** Bán qua billing không tự trừ sổ vật tư
   này; cần xác nhận có chủ đích hay cần luồng xuất kho bán hàng.
10. **Đổi đơn vị khi phiếu nhập còn chờ duyệt hoặc đang ghi đồng thời.** Trước
    sửa, yêu cầu chờ duyệt chỉ lưu số lượng, không lưu đơn vị; đơn vị có thể đổi
    trước lúc duyệt, khiến số cũ được hiểu theo đơn vị mới. Đã thêm bản chụp đơn
    vị vào phiếu, khóa dòng mặt hàng khi gửi/duyệt/ghi sổ, và chặn đổi đơn vị khi
    còn yêu cầu chờ. Test DB kiểm tra cả phiếu chờ, form cũ và tranh chấp đồng
    thời; hiện 68 test kho liên quan xanh. Chưa lên staging.

## Hàng rào đang có

- Kho vật tư kiểm tra `vat_tu.manage`/`vat_tu.approve`; ghi phiếu và ledger trong
  transaction, khóa theo clinic/location, khóa tồn `FOR UPDATE`, ledger append-only.
- Kho thuốc có kiểm tra quyền ở API, scope theo cơ sở, khóa tồn và ledger
  append-only. Nhập phiếu nhiều dòng/cấp phát có idempotency ở một số luồng.
- Tồn âm vật tư được cho phép ở một số loại phiếu theo chính sách hiện tại;
  cảnh báo và test đã xác nhận hành vi, không tự phân loại đó là lỗi.
- Tìm kiếm caller không thấy UI kho vật tư đọc bảng trực tiếp qua PostgREST;
  các màn dùng FastAPI/SSE. Vẫn còn quyền SQL `SELECT authenticated`, nên người
  dùng có token có thể gọi PostgREST trực tiếp ngoài UI.

## Quyết định và bước tiếp theo

- Tuyền đã duyệt 3 P1 kho thuốc: số không hữu hạn, retry điều chỉnh/huỷ (kèm
  luồng nhập nhanh đang hoạt động), và cùng mã lô khác đơn vị. Đã sửa API/service/
  DB/UI, test hồi quy phù hợp và full CI đã xanh trên `62d11cab` với 8 DB workers;
  còn kiểm chứng staging trước prod.
- Tuyền đã duyệt thu hồi `SELECT` của `authenticated` trên bảng sổ kho thuốc/
  vật tư, giữ quyền `service_role`, và kiểm thử quyền trước khi áp staging.
  Migration ACL cùng SQL regression test đã thêm cho 11 bảng; CI đã xanh trên
  `62d11cab`, còn kiểm chứng staging. Hai script khôi phục staging áp lại ACL
  sau GRANT rộng để quyền không bị mở lại khi nạp bản sao.
- Các mục P2 còn lại cần quyết định nghiệp vụ/ưu tiên riêng; chưa đổi cách xử lý
  thuốc trả, chuyển kho giữa cơ sở, hay liên kết bán hàng khi chưa có quy tắc rõ.
- Quy trình deploy repo: CI xanh → đưa đúng SHA lên staging → kiểm tra nghiệp vụ
  trên staging → mới đưa cùng SHA lên prod. AI chỉ chuẩn bị lệnh VPS; người vận
  hành chạy bước ghi/deploy theo `CLAUDE.md` và `docs/STAGING.md`.
