## Cổng bổ sung Round 44 — đơn thuốc, duyệt kết quả và recovery

1. Lưu bệnh án có draft: đổi riêng `drug_catalog_id` phải cập nhật đúng đơn; payload không đổi vẫn replay/no-op an toàn.
2. TKYK chỉ duyệt/chốt kết quả bệnh nhân thuộc assignment được phép; negative case không đổi result, task, audit hoặc release gate.
3. Tắt cơ sở rồi bật/tạo phòng con phải bị từ chối hoặc giữ rõ policy; routing/query/API cùng tôn trọng trạng thái cha.
4. Dựng recovery set trên kiến trúc Supabase self-hosted mới; diễn tập auth/credential policy, media, ACL, ledger, app version và một workflow synthetic. Bỏ điều kiện cloud PITR nếu không thuộc deployment.
5. Config mutation và audit event phải cùng transaction/outbox; test permission revoke interleaving trên DB disposable.

Các cổng này chưa được chạy; không phải kết quả production.

## Cổng bổ sung sau Round 31 — dữ liệu CSKH và phục hồi queue

- Tạo fixture >300 phản hồi trong nhóm khách đang xem, có khiếu nại cũ chưa đóng; API/UI phơi bày phân trang/truncated state và không hiển thị empty tuyệt đối. Kiểm clinic boundary và trạng thái open qua trang.
- Tạo DB scenario queue ROOM → checkout (`left`) → deactivate phòng → undo. Chốt kết quả: route sang queue cần định tuyến lại hoặc từ chối có giải thích; không để waiting gắn phòng inactive biến mất khỏi hàng làm việc. Dùng phòng active làm đối chứng.
- Product/ops chốt policy owner/SLA/escalation/ack/reopen cho khiếu nại trước acceptance. Volume production chưa đo; findings hiện là evidence tĩnh có điều kiện.

## Cổng bổ sung sau Round 30 — artifact kế toán, danh tính thuốc, audit semantics

- **Xuất hóa đơn:** kế toán nghiệm thu file XLSX độc lập trên các fixture tổng hợp: một/nhiều thuế suất, gộp/tách, giảm giá, refund gắn dòng và refund không gắn dòng. Chưa chốt contract thì export phải block có giải thích hoặc gói exception mang theo file; preview không đủ làm bằng chứng nghiệm thu.
- **Catalog thuốc:** chỉ phát hành sau khi dược sĩ/chủ catalog chốt khóa định danh và quy tắc tương đương brand/hoạt chất/hàm lượng/dạng dùng; seed/mapping test phải bắt được hai source ID bị nhập cùng nhãn ngoài chủ ý.
- **Audit events:** quy ước transition event so với command/actor event; retry cùng idempotency key phải ổn định, key mới phải tạo hành động/audit record theo policy; dashboard không dùng số event thô thay cho trạng thái nghiệp vụ.

## Cổng bổ sung sau Round 29

**Cổng dữ liệu và điều hành:** trước pilot nhiều phòng khám, kiểm synthetic clinic có hơn năm lượt và khoản nợ cũ để đối chiếu hồ sơ khách với sổ công nợ; kiểm overview trên 400 lượt để KPI không im lặng bị cắt. Thêm fault tests cho từng panel refresh và trạng thái unknown. Đây là acceptance gate được đề xuất, không phải khẳng định rằng hệ thống đã vượt giới hạn.

**Cổng tài chính liệu trình:** kiểm hoàn lẻ/nhiều lần với tiền lẻ, invariant tổng hoàn không vượt số thu, và crash sau commit trước receipt rồi retry. Không mở rộng thu/hoàn tự động cho tới khi biên nhận, đối soát và phục hồi cho mọi source type được kiểm chứng.

Ưu tiên theo rủi ro người bệnh và tiền, nhưng đi theo lát nhỏ trên kiến trúc hiện tại; không viết lại toàn bộ chỉ dựa trên audit tĩnh. Mỗi cổng cần test trên dữ liệu tổng hợp và người chịu trách nhiệm nghiệp vụ/kỹ thuật rõ ràng trước rollout.

# Lộ trình đề xuất và tiêu chí sẵn sàng bán

Đây là các đợt theo điều kiện đạt, không phải lịch hứa theo ngày. Chưa đủ dữ liệu để
ước lượng tổng công thực hiện đáng tin. Mỗi đợt tạo ticket nhỏ, ghi phạm vi, phụ thuộc,
người phụ trách, phép đo trước/sau và đường phục hồi. Đổi code là công việc sau audit.

| Đợt | Kết quả cần đạt | Bằng chứng để đi tiếp |
|---|---|---|
| 0 — Chốt sự thật kỹ thuật | Code, schema, config thử và bản phát hành khớp; hoàn tất audit main | Manifest/checksum, không còn ca đỏ do nhầm phiên bản; coverage ledger và findings được review |
| 1 — Giảm rủi ro lớn | Quyền đúng sau mọi vòng đời; backup/restore đủ tập; scripts thử fail-closed | Negative role tests, ACL diff trước/sau restore, login+file+ledger recovery drill |
| 2 — Tin được trạng thái | Không gắn hoàn thành giả; dữ liệu cũ/thiếu/lỗi rõ; việc tái khám không rơi | Fault injection API/worker/mạng, nhận bàn giao, đối chiếu trạng thái xuyên màn |
| 3 — Lõi ghi đáng tin | Command retry an toàn; tiền/tồn/state có invariant; consumer/timer có budget | Concurrent/replay tests, property tiền, crash-after-commit, bounded worker delay |
| 4 — Gói sản phẩm | Clinic thứ hai chạy bằng cấu hình, không fork code hay mang danh mục khách khác | Clean install, import/export, upgrade hai clinic khác nhau, tenant isolation E2E |
| 5 — Pilot có đo | Nhân viên làm trọn ca, ngoại lệ và mất kết nối có đường xử lý | Số liệu alignment, SLO đã chốt, support/runbook và chi phí trên khách |
| 6 — Mở rộng có điều kiện | Bán thêm khi pilot đạt; thêm AI ở chỗ đã đo có lợi | Không còn rủi ro HIGH chưa có xử lý được chấp nhận; năng lực trực và phục hồi đáp ứng cam kết |

## Cổng nghiệm thu trước khi nhận khách hàng độc lập

### Đúng và an toàn

- Ma trận quyền theo đối tượng và clinic được kiểm từ API, RPC, file, export, SSE và worker.
- Tài khoản quầy/điều dưỡng chỉ nhận danh bạ nhân sự tối thiểu; CCCD và hồ sơ pháp lý cần quyền đọc riêng theo clinic, được kiểm bằng API/export tests.
- Ban/unban và mọi dual-write với GoTrue có retry/reconcile và trạng thái partial rõ; fault-injection không được hiện thành công giả.
- Mọi cổng upload (CSKH, đối tác, chứng từ thu) giữ reserve ổ khi body chunked/thiếu Content-Length, khi nhiều lượt cùng chạy và khi parser nhận nhiều metadata.
- Tiền thu/hoàn, giảm giá, tồn/giao/trả và lịch giữ bất biến khi retry hoặc hai người thao tác.
- Bệnh án/kết quả có phiên bản và dấu người sửa; những xác nhận y khoa dựa đúng bằng chứng.
- Lỗi từng phần được nhìn thấy; không có đường báo thành công giả trong các luồng ưu tiên.

### Cài và nâng cấp lặp lại được

- Một người mới làm theo tài liệu có thể dựng môi trường trắng và clinic giả mà không hỏi tác giả.
- Cùng release/config có kết quả tương đương ở thử và đích; secrets được cấp riêng.
- Nâng cấp không thay danh mục/giá của khách ngoài scope; schema/ACL được đối chiếu.
- Khả năng quay lại ứng dụng cũ và giới hạn tương thích dữ liệu được diễn tập trước phát hành.

### Vận hành và hỗ trợ

- Có chủ sở hữu sự cố, kênh báo, delivery retry và người nhận; cảnh báo không phụ thuộc xem /ops thủ công.
- Mất máy chủ vẫn phục hồi được tài khoản, DB và file; RPO/RTO đo từ drill, chưa dùng số hứa tùy ý.
- Có quy trình hỗ trợ có quyền hạn, nhật ký, che dữ liệu và khả năng bàn giao cho người khác.
- Có quy trình xuất/nhập, chấm dứt sử dụng, retention/xóa và kiểm tính đầy đủ.

### Chất lượng sử dụng và hiệu quả thực tế

- Người thật hiểu đúng “đã giao”, “đã nhận”, “đang chờ”, “chưa xác minh”, “đã về”.
- Luồng chính dùng được bằng bàn phím; lỗi không làm mất nội dung; kiểm mobile/desktop.
- Pilot cho thấy giảm hỏi ngoài, giảm việc rơi, giảm unknown hoặc công tìm hiểu; không chỉ thêm chuông.
- Giá bán, hỗ trợ, trách nhiệm dữ liệu và ngân sách vận hành được người kinh doanh chốt.

## Kịch bản nghiệm thu ưu tiên

1. Hai clinic, hai tài khoản: đoán UUID/cursor/file/RPC của clinic kia đều bị chặn.
2. Lưu tiền/thêm thuốc đã commit nhưng mất response: retry không tạo thêm tác động.
3. Kết quả đối tác chưa về, bác sĩ hoàn tất phiên: không ghi đã đọc kết quả chưa tồn tại.
4. Khách về và mua thuốc ngoài: kết thúc buổi hợp lệ, không ghi giờ giao thuốc giả.
5. Đồng bộ ngày tái khám hỏng: phiếu vẫn giữ, việc pending có chủ và tự thử lại an toàn.
6. API bảng lỗi sau lần tải đầu: người dùng thấy dữ liệu cũ và thời điểm cuối, không nhầm hiện tại.
7. Hơn 300 dòng đơn/lượt: không cắt nửa đơn; tìm được khách ngoài trang đầu và biết độ đầy đủ.
8. Cảnh báo gửi lần đầu lỗi: lần sau retry; đã nhận thì dedupe; chưa nhận quá hạn thì leo thang.
9. Worker backlog không rỗng: timer/canh gác vẫn chạy trong budget; worker cũ không ghi đè claim mới.
10. Restore từ bộ backup thiếu từng phần: checker báo thiếu; bộ đủ phục hồi được đăng nhập, file và ledger.
11. Nâng cấp clinic có catalog riêng: danh mục/giá giữ nguyên nếu không có lệnh đổi được phép.
12. Đăng xuất máy quầy: draft nhạy cảm được xử lý theo chính sách; đổi người không lộ phiên/dữ liệu cũ.
13. Đổi lịch đang bay, check-in hoàn tất ở quầy khác: lịch vẫn đã đến, hoặc lệnh cũ trả conflict.
14. Bác sĩ ẩn thông báo correction v2; correction v3 phải nổi lại đúng phiên bản, giao lặp v3 không spam.
15. 201 việc vẫn quá hạn: không đóng việc thứ 201 vì bộ phát hiện chỉ lấy 200 dòng.
16. Hai người cùng viết ghi chú: bản nháp của bên nhận 409 không mất, có đường hợp nhất.
17. Hoàn chia số lượng thành nhiều phần: tổng tiền hoàn không vượt và khi hoàn hết phải bằng tiền đã thu.
18. Upload không khai Content-Length hoặc nhiều upload lớn đồng thời: dự phòng đĩa vẫn được giữ.
19. Đơn thuốc A, lô B cùng cơ sở/đơn vị: mọi cửa giao/gán lô đều từ chối, không đổi tồn/số giao; lô A hợp lệ vẫn dùng được.
20. Image phát hành mới: lockfile/runtime/SBOM khớp, advisory được vá/mitigate có chứng cứ, không chấp nhận downgrade tự động để xanh bảng scan.
21. Sổ thu có trên 3.000 lần thu/hoàn, gồm timestamp trùng và giao dịch khớp filter nằm sau trang đầu: màn hình/API báo đủ tổng + cursor, KPI khớp query chuẩn, CSV/XLSX xuất đủ hoặc nói rõ chưa đủ.
22. Báo cáo cuối ngày và xuất hoá đơn với kỳ >92 ngày: API/UI phải trả đủ requested period hoặc từ chối rõ; preview, CSV/XLSX, bản in, effective period và bộ đếm không được tạo cảm giác hoàn chỉnh khi backend đã cắt.
23. Hai clinic giả qua PostgREST: JWT clinic A không đọc được giờ/quy tắc sức chứa clinic B bằng các capacity RPC SECURITY DEFINER; role backend còn hoạt động sau fresh install/upgrade/restore.

## Trạng thái cổng bán ở lần kiểm hiện tại

Không dùng một điểm “production ready 80%”: các cổng dưới đây không bù trừ cho nhau.
Một giao diện đẹp không bù được lỗi bàn giao/kết quả, nhiều test xanh không bù được
phép thử bất biến đỏ. Chỉ tiêu chưa thử phải ghi chưa biết.

| Cổng | Hiện trạng có căn cứ | Đánh giá |
|---|---|---|
| Định danh bản đang chạy | Checkout sạch956ba4f2; API+worker424.py khớp;373migration IDs khớp | Đạt phần metadata; chưa checksum SQL đã áp/bundle frontend |
| Quyền hiện tại, RPC tenant và vòng đời | DB-001/002 có rủi ro restore; SEC-007 capacity RPC nhận clinic UUID caller mà không xác minh membership; SEC-008 Next buffer 10 MiB / service 12 MiB lệch hợp đồng multipart | Chưa đạt; cần PostgREST hai clinic và full restore drill |
| Giao đúng thuốc | Service và router ASGI nhận lô khác thuốc ở đường không allocation | Chưa đạt, ưu tiên đóng bất biến |
| Hồ sơ và định danh bệnh nhân | CLIN-008: PATCH CCCD không dùng chung cảnh báo trùng/lý do của CREATE | Chưa đạt; thêm test update trùng và audit reason trong cùng transaction |
| Dependency phát hành | Runtime Next/sharp thuộc phiên bản có advisory; chưa chứng minh exploit | Cần triage/vá trước mở rộng |
| Lệnh ghi, tiền, trạng thái | Retry thuốc, mất receipt, race lịch và tiền hoàn có probe đỏ | Chưa đạt |
| Sổ thu/hoàn, kỳ báo cáo và export | FIN-005: hai query LIMIT 3.000; FIN-006: invoice và báo cáo cuối ngày âm thầm co kỳ ngày; UI/API/file chưa có hợp đồng completeness chung | Chưa đạt; chưa đo ngưỡng/dữ liệu thật |
| Thấy đúng và nhận biết bản mới | Hành trình suy sai, đóng nhận định do LIMIT, correction bị ẩn, mất draft | Chưa đạt |
| Kho vật tư được giữ nguyên khi sửa | Đã đọc các chốt khóa/sổ/đơn vị/duyệt;47 test liên quan xanh | Có bằng chứng tốt trong phạm vi này; chưa toàn thuốc/kho |
| Khôi phục toàn bộ dịch vụ | Chưa thử recovery set với auth+file+quyền+ledger | Chưa chứng minh |
| Clinic độc lập thứ hai | Hàm catalog lịch sử làm đổi cả2clinic giả; chưa clean install/upgrade/export đầy đủ | Chưa đạt phần bootstrap catalog |
| Tải và hỗ trợ theo cam kết | Chưa đo tải hành trình, RPO/RTO và bàn giao cho operator khác | Chưa chứng minh |

Khuyến nghị hiện tại: giữ phục vụ và cải tiến có giám sát ở môi trường hiện hữu;
chưa dùng kết quả audit này để hứa bán rộng/khách tự vận hành. Muốn pilot khách
độc lập cần đóng các cổng về dữ liệu, quyền, retry và phục hồi với bằng chứng.

## Các gói sửa đầu tiên đề xuất, chưa phải lệnh triển khai

| Gói | Phạm vi cụ thể | Cách nghiệm thu sẵn có |
|---|---|---|
| S — Chốt giao đúng thuốc | CLIN-007; cùng thuốc ở service/DB cho legacy/no-allocation/late-assign | Hai probe service/HTTP RED xanh; thêm control lô đúng và không đổi sổ khi từ chối |
| R — Thành phần được phát hành | SEC-004; bản vá Next/native dependencies và SBOM/image provenance | Scan/triage trên image mới, không blind-force upgrade; hành trình login/file/ảnh/in vẫn đúng |
| A — Trạng thái và bản kết quả mới | CLIN-005, CLIN-006, FE-006; chặn ghi status cũ, delivery theo revision, retry mốc đã xem | Hai probe RED đổi sang xanh; thêm permutation undo/cancel và hide/read/resolve |
| B — Ghi một ý định một lần | FIN-003, INF-007; receipt chung transaction và ID dòng ổn định | Kill/error sau commit rồi retry; đối chiếu cả natural keys đang bảo vệ kho vật tư |
| C — Không rơi việc/không kết luận từ tập thiếu | CLIN-003, AI-001 | Retry không đổi ngày giả; scan201 và đối tượng chuyển trang vẫn giữ việc đúng |
| D — Không mất chữ và không giấu dữ liệu cũ | FE-005, FE-002/003/004, FIN-002 | Browser409 giữ cả local/remote; API lỗi/row cap không thành “không có” |
| E — Đường nâng cấp và phục hồi | DB-001/002, INF-001/003/006 | Restore ACL negative tests, script env production fail-closed, drill đầy đủ |
| F — Bảo toàn tiền và tài nguyên | FIN-004, SEC-003 | Partition refund properties; streaming capacity/cleanup với tải đồng thời |
| G — Bootstrap có scope | DB-004; tách data package khỏi schema, không sửa lịch sử migration đã phát hành | Hai clinic catalog riêng nâng/cài không bị thay ngoài scope; probe cũ được giữ làm đối chứng |

Mỗi gói có thể tách PR nhỏ theo bất biến và module. Không gộp tất cả thành một lần
viết lại kiến trúc; các phép thử đỏ là đặc tả lỗi cần giữ trong lần sửa sau audit.

## Thứ tự tiếp quản nếu phiên hiện tại dừng

1. Ghim và khôi phục snapshot main `956ba4f2` từ Git; kiểm ref mới nếu cần nhưng không âm thầm đổi baseline.
2. Đọc PROD-CHECK.json và blocks/root-main-round2.md: DB-002 full-main actual-role đã tái hiện, live ACL đang deny. Không làm lại placeholder probe.
3. CLIN-003/FIN-003 và bảy probe mới đã có bằng chứng local; tiếp tục full application/browser fault injection hoặc phần còn thiếu, không lặp cùng test để tăng số.
4. Đọc sâu các đường chưa trace trong728 đường dẫn khác nhánh ban đầu, ưu tiên pharmacy/kho/tiền và các migration mới; kho vật tư đã có47controls xanh trong phạm vi nêu.
5. Đi hết các vùng mới `inventoried/scanned`; cập nhật ledger từng cụm, không nâng mức bằng phỏng đoán.
6. Review độc lập findings, hoàn tất probe/kiểm UI, cập nhật thiết kế và HTML. Chỉ gắn bản cuối khi đạt tiêu chí bàn giao.


## Bổ sung cổng từ findings v0.17

Trước pilot nhiều clinic, cần đóng và kiểm lại các điều kiện sau:

- **Riêng tư lâm sàng:** role không có capability y khoa không đọc được form qua shared-form dù tự đặt patient IDs; consent không thay thế quyền nhân viên.
- **Báo cáo đầy đủ:** synthetic vượt từng ngưỡng 300/200/100/1.000/5.000; hoặc lấy đủ trang, hoặc UI/JSON/CSV/XLSX đều báo incomplete và cấm hiểu là đã đối soát.
- **MPI:** candidate PENDING có reviewer path, SLA/ownership, quyết định auditable và merge có thể phục hồi.
- **Cài đặt tenant:** clinic thứ hai được provision từ template versioned, không chạy script `LIMIT 1`, workflow và ACL smoke test qua.
- **Khôi phục:** restore DB/auth/files theo tập dependency được ghi rõ; ledger/schema/ACL khớp và migration nâng cấp kế tiếp chạy được trên DB phục hồi.
- **Retry bootstrap:** fault-injection sau từng migration local cho kết quả resume an toàn hoặc báo reset có hướng dẫn, không để schema dở dang bị nhận thành DB trắng.


## Cổng bổ sung từ findings v0.18

- **Phạm vi bệnh nhân:** TKYK cùng clinic không đọc được lịch sử/form/in bệnh án ngoài bệnh nhân được phân; kiểm ID mismatch giữa patient, visit, appointment ở API, proxy và export. SEC-011 hiện static, ưu tiên trước pilot.
- **Ngữ cảnh bệnh nhân:** đổi A→B khi fetch pending/502 không được giữ dữ liệu A; lỗi phải hiển thị, mở lại visit phải khóa đúng patient. FE-007 cần browser fault test.
- **Worklist bác sĩ:** cho-quyet lỗi không được biến thành empty/ẩn panel; stale list có mốc tải và retry. FE-008 cần fault-injection 503/network.
- **Đổi dịch vụ:** reschedule CHECKED_IN phải cập nhật hoặc từ chối toàn bộ thay đổi appointment/visit; test phiếu mở theo service đã duyệt. CLIN-010 cần DB test.
- **Lịch sử nghiệp vụ:** delta service/channel/referrer cần giữ trước/sau, actor và reason. CLIN-011 cần schema/event contract test.
- **Timer tái khám:** đổi ngày sau claim DANG_LAM phải giữ một timer mới đúng hạn, dù handler cũ kết thúc muộn. INF-009 cần interleaving DB test và metric missing-timer.

Các kết quả này chưa làm trạng thái sẵn sàng bán chuyển sang đạt. Lúc chốt v0.18 HTML/ZIP còn chờ; checkpoint v0.19 phía dưới đã rebuild và QA lại.


## Cổng bổ sung từ v0.19

- **Command receipt:** fault-inject sau commit cho cả tương tác CSKH và hoàn tiền partial; cùng key retry sau lease không tạo tác động thứ hai (INF-007).
- **Thu hồi quyền:** lỗi giữa mỗi lego revoke rồi retry phải hội tụ desired permissions; không giữ capability sót và không thu grant đến từ nguồn khác (SEC-012).
- **Trả thuốc sau void:** HOAN/DOI/GIU_LAI phải ghi rõ trạng thái hàng và tiền, đối soát đúng receipt gốc, không rollback âm thầm làm nhân viên phải chuyển kênh hỏi nhau (PHAR-001).
- **Kết quả mẫu đối tác:** clinic chốt có SLA hay không; nếu có, test timer + owner + retry + hủy/đổi hạn cho `mau_gui_doi_tac` (CLIN-012).


## Cổng bổ sung v0.20 trước khi đóng gói thương mại

1. **Dữ liệu nhạy cảm:** loại bỏ CCCD/SĐT khỏi payload audit mới; phân quyền, che trường và chốt thời hạn lưu/xử lý dữ liệu lịch sử.
2. **Quyền roster:** thêm trạng thái “chưa khai / đã khai”; tắt hết phải fail-closed; ghi audit actor, lý do, diff.
3. **Cấu hình ↔ điều phối:** chọn protocol khóa/version; test hai thứ tự concurrency và chứng minh không có assignment commit trái version.
4. **Command receipts cho thao tác clinical:** `attempt_id` + revision, idempotency và conflict với lệnh cũ; kiểm assertion provenance revision của attempt/event/order.
5. **Hợp đồng PATCH:** phân biệt omitted/null/value, kiểm tra privacy flags không tự đổi; đồng bộ validation active location và số phụ giữa create/update/lookup.

Các cổng này là đề xuất backlog, chưa phải thay đổi code. Chỉ triển khai sau khi audit đủ rộng và nhóm nghiệp vụ chốt hành vi mong muốn.


## Cổng bổ sung v0.21

1. **Kết quả đối tác:** thu hồi tệp cuối phải tạo lại việc theo dõi hoặc handoff có owner; kiểm timer, undo và tình huống còn result khác (CLIN-019).
2. **FINALIZED / amendment:** chốt contract thống nhất cho phiếu v5 và clinical shell; kiểm quyền, revision, reason/approval và hồ sơ in (CLIN-020).
3. **Release kết quả:** không để bản sửa chưa duyệt xuất hiện như bản chính thức; xác định đường in/gửi có cấu trúc và quyền phát hành (CLIN-021).
4. **Worklist đầy đủ:** pagination/has_more cho worklist CSKH và mọi cap tương tự; fixture >200 chứng minh không mất người cần chăm sóc (CLIN-022).
5. **Multi-clinic:** nếu thị trường mục tiêu gồm nhóm clinic, thêm tenant selector riêng location; kiểm cùng tài khoản nhiều membership và negative authorization khi forge clinic (FE-009).
6. **POS operability:** trước khi bật/bán POS, có DLQ view theo clinic, owner, alert, retry/reconcile idempotent và end-to-end adapter test (INF-011).
7. **Worker fencing:** chạy slow-handler/two-worker test cho event và timer; worker mất lease không được commit side effect hay ghi đè trạng thái worker mới (INF-005).

Các cổng trên chưa làm app thay đổi; policy-dependent gaps cần được chủ nghiệp vụ chốt trước khi biến thành acceptance trong backlog sửa.


## Cổng bổ sung v0.27 — AI có ngân sách và trạng thái vận hành nhìn thấy được

- Mọi client LLM của app đi qua meter dùng chung; startup test kiểm tra wiring thay vì chỉ tạo client riêng trong test.
- Reservation ngân sách ngày là nguyên tử dưới tải đồng thời; retry dùng provider request ID/idempotency, không tính receipt hai lần.
- Timeout, lỗi provider và lỗi finalize đều để lại trạng thái có thể truy vết; Ops hiển thị dữ liệu `as_of`, chi phí đã xác nhận và khoản chưa đối soát.
- Meter outage chặn lời gọi trả phí hoặc bật fallback rule-based có thông báo; không bỏ qua ngân sách một cách im lặng.
- Acceptance chạy bằng provider giả và DB tổng hợp riêng; đối chiếu trần, ledger, UI Ops và cảnh báo mà không dùng hóa đơn hoặc payload bệnh nhân thật.

AI-004 là static trace, nên cổng này cần test app/concurrency trước khi coi kiểm soát chi phí đã được nghiệm thu hoặc mở AI rộng cho khách hàng.


## Cổng bổ sung v0.38 — nhật ký quyền, mutation nguyên tử và lỗi đọc rõ ràng

1. Chiếu capability grant/revoke vào audit API/UI có role + clinic isolation; giữ payload tối thiểu và test hai clinic, actor, target, capability, scope, timestamp.
2. Fault-inject event insert sau mỗi lệnh floor create/rename/activate/reorder; hiện trạng và audit phải cùng commit/rollback, kết quả API phải khớp trạng thái.
3. Status BFF giữ HTTP error hoặc envelope có discriminant; UI phải render lỗi/retry khi server lỗi hoặc payload sai shape, không làm hỏng dashboard route.

Các cổng này mới là tiêu chí đề xuất. Round17 chưa chạy application test hoặc production validation; audit toàn source còn tiếp tục.

## Cổng bổ sung v0.39 — đính chính kết quả, recovery theo dòng và tender gốc

1. Tạo test cho tệp HOP_LE → staff-recorded send → revoke. Hệ thống phải chặn revoke thường hoặc tạo corrective work item có role/owner, SLA, trạng thái liên hệ và bản thay thế; clinic chốt rõ chính sách trước khi chọn nhánh.
2. Tạo event DEAD và timer CHET trên DB dùng một lần; kiểm tra Ops hiển thị từng bản ghi, owner, lỗi, tuổi và tác động bị chặn; retry có quyền, fencing, idempotency và audit. Kiểm tra riêng event do hệ thống không có actor và timer không có `nguoi_goi`.
3. Thu 100.000 CASH + 50.000 TRANSFER, làm phát sinh 150.000 tiền thừa rồi hoàn mặc định. API, phiếu hoàn và báo cáo phải giữ 100.000 CASH + 50.000 TRANSFER; override một tender cần xác nhận và audit.

Round18 chỉ xác nhận đường code tĩnh; các cổng này chưa được chạy và không đại diện cho kết quả production.



## Cổng bổ sung v0.40 — quyền bệnh nhân, release biểu mẫu và trạng thái vận hành

1. Dùng fixture hai clinic và các role giả lập để kiểm `/patients/{id}`, tìm theo phone, assignment của TKYK note, RLS bảng số phụ; kiểm cả allow/deny trên API và PostgREST. Xác nhận field projection cùng clinic và role theo policy. Không dùng PHI hoặc production.
2. Tạo visit draft, autosave, finalize/release, rồi in. Kiểm print contract báo đúng revision/status; người không có quyền không thể sửa; biểu mẫu sai service mapping bị chặn ở backend.
3. Hai client sửa cùng một field từ cùng revision: một lần lưu thành công, lần còn lại nhận conflict và giữ draft để hợp nhất; không mất update âm thầm.
4. Mock notifications: GET lỗi phải hiện lỗi/retry; trên 50 item phải báo trang tiếp; Telegram fanout có một recipient lỗi không gửi trùng cho recipient đã nhận; nội dung có ký tự HTML được escape; Zalo timeout lưu trạng thái UNKNOWN và reconcile trước retry.
5. Với roster PENDING/APPROVED/REJECTED, xác nhận chỉ APPROVED có authority/capacity; stale approve/reject bị từ chối; reject/remove đã duyệt reconciliation lịch hẹn. Stress test pool với nhiều remove đồng thời và pool nhỏ để phát hiện nested-acquire starvation.

Các cổng này chưa chạy ở vòng 19. Chỉ chạy trên DB/test provider dùng một lần, dữ liệu hoàn toàn tổng hợp. HTML browser QA chỉ xác minh artifact audit, không thay thế các cổng ứng dụng trên.

## Cổng bổ sung v0.41 — tính toàn vẹn lần ghi và khả năng thấy phần còn lại

1. **Siêu âm/clinical revision:** tạo interleaving test trên DB dùng một lần cho hai request sửa hai field cùng aggregate. Test trạng thái work item đã nhận/chưa nhận/không tồn tại; không chấp nhận lost update hoặc success cho base revision stale (CLIN-040).
2. **Recall state machine:** barrier giữa ghi outcome và trigger tạo lịch. Mọi kết quả phải hoặc được ghi cùng `cskh_log`, hoặc báo stale/superseded có tên; replay idempotent không giả là log đã có (OPS-005).
3. **List completeness:** fixture 101+ personal reminder và 51+ inbox/200+ các worklist; API/UI phải trả trang tiếp hoặc chỉ rõ còn dữ liệu. Xác minh timer không bị thay đổi chỉ vì list view có giới hạn (FE-022, FE-020, CLIN-022).
4. **Roster state consistency:** PENDING không quyết định quyền thay, phòng/node hoặc capacity; APPROVED đúng location/shift mới được dùng. Chạy permission và queue projection cùng synthetic roster rows (SEC-028).
5. **Release contract trước mở feature:** nối `SonoBiometry` qua cùng API model và xác định full-wipe script cũ còn dùng không; nếu đã retire, gắn cảnh báo/runbook, không để trạng thái vận hành mơ hồ.

Vòng 20 chỉ đọc static source. Các cổng chưa chạy; không nâng mức readiness thương mại từ kết quả này.


## Cổng bổ sung v0.42 — quyền dữ liệu patient ở mọi đường đọc

1. **Trước bán cho clinic mới:** dựng Supabase mới chỉ từ migrations ghim, đăng nhập fixture từng vai và kiểm FastAPI lẫn `/rest/v1`. Vai thiếu `patient.list.view` phải không thể đọc hàng loạt patient qua bảng gốc; xác nhận reception chỉ nhận đúng trường cần cho intake. Kiểm national ID, phone, address, cross-location và cross-clinic; lưu allow/deny matrix làm release evidence.
2. **Realtime:** xác nhận client chỉ nhận projection tối thiểu; không dựa vào chuyện UI hiện không gọi PostgREST để coi grant an toàn. Rà grants sau fresh restore/migration và kiểm không có default privilege ngoài ý muốn.
3. **Dashboard freshness:** fault test tải thành công rồi làm request refresh của hành trình và phản hồi thuốc thất bại. Dữ liệu cũ phải còn dùng được nhưng có nhãn stale và retry; 200 empty khác với lỗi.
4. **Chọn lượt phản hồi thuốc:** fixture 21+ lượt có đơn; UI/API cho tới lượt cũ hoặc báo rõ giới hạn.
5. **Đối soát hoàn chuyển khoản:** chủ sản phẩm/kế toán chốt request date vs completion date vs pending/completed split; sau đó kiểm ngày tạo yêu cầu N và chuyển tiền N+1 trên báo cáo, lịch sử, sổ nợ và chốt ca.

Round 21 chỉ trace static. Các cổng trên chưa chạy và không xác nhận bất kỳ sự kiện production nào.


## Cổng bổ sung v0.51 — retry, nhiều người sửa và kết quả không rõ

1. **CLIN-044:** fault-inject response loss sau khi hẹn gọi lại đã commit; gửi lại cùng `operation_id` chỉ có một row/notification và trả cùng resource ID. Cùng key khác body phải conflict.
2. **PHAR-003:** hai client tải cùng revision của phiếu kiểm kê; lần lưu sau phải conflict, giữ local draft và không làm đổi snapshot; test chốt chỉ dùng revision đã xác nhận.
3. **PHAR-004:** mất response sau commit CHOT phải tự đọc lại phiếu và hiện thành công đã đối soát; trước commit thì giữ nháp, đánh dấu kết quả chưa rõ và cho retry cùng command ID. Kiểm không tạo ADJUST trùng.
4. **FE-002:** với hàng chờ đo sinh hiệu, làm GET/SSE/poll fail sau lần tải thành công; dữ liệu cũ phải gắn stale và có thời điểm tải cuối/nút retry kể cả khi chưa chọn bệnh nhân.
5. **CSKH-ROSTER-CAP-001:** đo volume bằng metric tổng hợp không chứa PHI và chốt hợp đồng completeness. Chỉ kiểm boundary >5000 trên fixture tổng hợp nếu trần còn hợp lệ với quy mô mục tiêu.

Các test trên chưa chạy trong Round 28; audit source vẫn đang tiếp tục trước khi mở các cổng ứng dụng.
