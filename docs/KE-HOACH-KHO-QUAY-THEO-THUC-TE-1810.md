# Kho thuốc, quầy và vật tư theo thao tác thực tế

Trạng thái: Tuyền duyệt tiếp tục sửa và triển khai staging trong chat ngày 18/10/2026. Nguồn: phản hồi trực tiếp trong chat. Chưa coi nội dung này là hành vi đã được triển khai hoặc kiểm chứng.

## 1. Nhập hàng và xem lại

- Một phiếu nhận hàng có nhiều dòng; mỗi dòng một thuốc, quy cách, số lô nếu biết, hạn dùng, số lượng và giá nhập thực tế. Cho nhập một hộp hoặc nhiều loại trong cùng phiếu.
- Tách mã phiếu do hệ thống cấp khỏi số lô nhà sản xuất trên bao bì. Không tự bịa số lô. Chưa rõ số lô thì hiển thị “Chưa ghi số lô”; mã nội bộ vẫn giúp truy phiếu.
- Cùng thuốc và số lô nhưng khác giá nhập phải giữ được từng lần nhập và giá gốc. Quy đổi hộp/gói/viên theo cấu hình của thuốc; không cộng trực tiếp các đơn vị khác nhau.
- Sau lưu hiển thị biên nhận nhanh: số phiếu, giờ thực hiện, ngày chứng từ, người nhập, số dòng, tổng tiền và tồn trước/sau; mở chi tiết, sửa sai, hoàn tác, tải Excel.
- Phiếu nháp sửa trực tiếp. Phiếu đã ghi sổ sửa bằng chứng từ đính chính/đảo có lý do, giữ bản gốc. Nếu hàng đã bán/cấp thì xử lý phần liên quan, không xoá dấu vết hoặc đảo mù toàn phiếu.
- Danh sách mặc định nhóm theo thuốc, mở rộng thấy từng lô/lần nhập. Chi tiết có lịch sử nhập, giao, trả, huỷ, điều chỉnh và hoàn tác; lọc ngày/người/lô/phiếu, xuất Excel đúng bộ lọc.

## 2. Kho và quầy

Không suy ra chuyển kho từ số kiểm đếm. Đếm là một quan sát, chuyển là một giao dịch; nếu gộp sẽ không phân biệt bán, bổ sung và thất thoát.

Đề xuất hai cách theo dõi, cần chốt:

1. Dùng chung tồn cơ sở: phù hợp khi nhân viên chạy vào kho lấy thuốc bán trực tiếp, không muốn quản lý từng lần bổ sung quầy. Bán trừ tổng tồn một lần; kiểm ca chỉ ghi nhận phạm vi kệ quầy, không so với toàn kho để tạo chênh lệch giả. Không hứa báo cáo tồn riêng kho/quầy chính xác.
2. Theo dõi riêng: không cần một bước chuyển riêng trước mỗi lần bán. Khi chọn lấy từ kho, giao dịch bán ghi phần di chuyển và phần giao cùng một lần; kho giảm, quầy không bị trừ hai lần. Bổ sung kệ để dành vẫn cần ghi nhận số đã mang sang, có thể ghi sau với giờ thực tế và giờ nhập sổ riêng.

Giữ luồng giao trước, hoàn thiện số lô sau. Hiển thị rõ lượng đã giao chưa phân bổ để tồn khả dụng không bị báo thừa. Không tự coi bản ghi chưa gắn lô là chưa giao; khi gắn lô sau phải tiêu trừ đúng khoản chờ, không ghi thêm một lần bán. Bán hàng không có dữ liệu nhập cần cảnh báo và lưu việc cần đối soát; chính sách cho âm cần chốt, không tự mở vượt quyền.

## 3. Kiểm đầu/cuối ca

- Màn hình chọn ca, phạm vi đếm và danh sách thuốc; cho đếm từng phần, ô bỏ trống khác số 0. “Dùng số ca trước” chỉ điền tham khảo, không xác nhận đã đếm.
- Lưu nháp, xác nhận số đếm, sửa bằng phiên bản có người/lúc/lý do. Không khoá cứng khiến không thể sửa sai.
- Kiểm đếm không cộng/trừ kho. Hiện tồn dự kiến, số đếm, lệch, các giao dịch chưa hoàn thiện; điều chỉnh là quyết định riêng có lý do và hoàn tác.
- Nếu cơ sở theo dõi riêng: tồn đầu + bổ sung - giao + trả đủ điều kiện - chuyển ra/huỷ + điều chỉnh = tồn cuối dự kiến. Giao dịch ghi muộn phải thể hiện tác động đối soát, không âm thầm viết lại số đã chốt.
- Báo cáo ca có chi tiết thuốc/lô, người đếm, giờ đếm/chốt, lịch sử sửa, lệch và xử lý; tải Excel.

## 4. Khách trả thuốc và hoàn tiền

- Một hồ sơ liên kết đơn bán, lượng nhận lại, kết quả kiểm tra hàng, nơi nhận, yêu cầu hoàn tiền và phiếu chi thực tế.
- Nhận lại vào khu chờ kiểm: tăng lượng hàng đang giữ nhưng chưa tăng tồn bán được. Sau xác nhận phù hợp mới nhập lại quầy/kho; huỷ thì không tăng tồn bán được. Không cộng cả kho lẫn quầy cho cùng một lượng.
- Hoàn tiền độc lập với việc hàng có bán lại được không. Hàng nhận lại không đồng nghĩa đã chi tiền; hàng không nhận lại vẫn có thể phát sinh hoàn tiền theo quyền/quy định.
- Hoàn một phần/nhiều lần phải cộng dồn và không vượt khoản có thể hoàn sau giảm giá/hoàn trước. Có phương thức chi, người thực hiện, thời gian, lý do và hoàn tác có đối ứng.
- Báo cáo phân biệt tiền thu, tiền đã hoàn, doanh thu thuần và yêu cầu chưa chi; đối chiếu báo cáo thuốc, thu ngân và tổng hệ thống cùng nguồn dữ liệu.

## 5. Vật tư

- Dùng chung cách trình bày phiếu nhập/lịch sử/đếm/hoàn tác, giữ quy tắc vật tư riêng.
- Nhìn theo kho và từng phòng: tồn, đơn vị, người bàn giao/nhận, thời gian, tiêu hao, hàng chờ kiểm/hỏng. Vật tư tiêu hao đếm theo lượng; dụng cụ theo dõi riêng chỉ thêm khi đã xác nhận yêu cầu.
- Cấp kho sang phòng: kho giảm, phòng tăng cùng giao dịch; trả dư chưa dùng: phòng giảm, kho tăng đúng lượng đủ điều kiện. Hàng hỏng/chờ kiểm không cộng vào tồn sử dụng được.
- Kiểm đếm phòng không tự trở thành tiêu hao hay trả kho. Không tự trừ thêm lần hai khi khoản bán/tiêu hao đã có giao dịch liên kết.

## 6. Giao diện và thứ tự làm

Kho thuốc: **Tồn thuốc | Nhập hàng | Lịch sử & sửa sai | Báo cáo**. Quầy: **Bán & giao | Kiểm ca | Khách trả**. Kho vật tư: **Tồn theo nơi | Nhập/cấp/trả | Kiểm đếm | Lịch sử & báo cáo**. Các thao tác phụ nằm trong chi tiết, dùng tên hành động rõ ràng thay tên kỹ thuật.

1. Chốt phạm vi tồn chung/riêng và cách xử lý bán thiếu dữ liệu.
2. Cải tổ nhập hàng, xem theo thuốc/lô, báo cáo nhanh, đính chính/hoàn tác và Excel.
3. Hoàn thiện bán trước/ghi sau, kiểm ca, chênh lệch và lịch sử sửa.
4. Kiểm chứng xuyên suốt khách trả → tồn → hoàn tiền → báo cáo.
5. Vật tư: nhập → cấp phòng → dùng/trả dư → kiểm → hoàn tác.

Mỗi đợt có test giao dịch, gửi lại/tranh chấp, hoàn tác sau giao dịch xen giữa; bấm local 375/1280. Kịch bản chấp nhận gồm Canxi + Androgel nhiều dòng, cùng lô khác giá, quy đổi hộp/gói, giao trước gắn lô sau, sửa phiếu đã dùng một phần, kiểm một phần/ghi muộn, trả một phần và hoàn nhiều lần, cấp/trả vật tư. CI một lần cuối đợt, staging trước prod. Không triển khai thay đổi mức 3 trước khi Tuyền duyệt kế hoạch.


## Quyết định bổ sung đã chốt trong chat

- Bỏ nút chuyển kho ra quầy; không bắt chọn nguồn lấy lúc bán.
- Giao trước, đối chiếu nguồn/lô sau. Tồn khả dụng phải trừ nghĩa vụ đã giao chưa phân bổ; khi gắn lô chuyển nghĩa vụ sang sổ xuất, không trừ hai lần.
- Tuyền cho phép lên staging trong giờ khám nếu kiểm tra tài nguyên và ảnh hưởng prod đạt. Không triển khai prod trong đợt này.
- Sửa phiếu kiểm kê sau chốt bằng phiên bản có lý do và lịch sử; không xoá snapshot cũ. Điều chỉnh còn hiệu lực phải hoàn tác trước.

## Kết quả ban đầu 18/10

- Local: số đếm Androgel 14, tồn sổ 15 → lệch -1; lưu nháp/tải lại, chốt, điều chỉnh rồi hoàn tác đạt, tồn trở lại 15. Phiếu thử còn trong lịch sử local.
- Test kiểm ca ban đầu: 70 passed. Test giao diện báo cáo/kiểm ca: 10 passed. Không thay thế kết quả sau thay đổi mới.
- VPS 11:38 giờ VN: RAM khả dụng 4262 MiB, đĩa / còn 8.5 GiB; load 0.77, prod/staging API và dashboard healthy. /login prod 200 trong 0.184s; staging 200 trong 0.129s. Đây là một mẫu, phải đo lại trước deploy.
- Staging trước đợt: 17e5dbbe; prod: 25140241. Staging đã đăng nhập do người dùng thao tác.

## Ma trận nghiệm thu đợt này

| Nhóm | Ca phải kiểm | Bằng chứng / trạng thái |
|---|---|---|
| Nhập | Một dòng; nhiều dòng; hộp→gói; sai hệ số; số âm/rác; gửi lại | Chờ kiểm đợt cuối |
| Giao | Có lô; chưa lô; lấy từ KHO khi tách; quầy hết; gắn sau; gửi trùng | Chờ kiểm đợt cuối |
| Tồn | Ledger trước/sau; khả dụng trừ pending; cách ly khách trả; không cộng lẫn đơn vị | Chờ kiểm đợt cuối |
| Kiểm | Trống khác 0; một phần; lưu/tải lại; đầu↔cuối; đổi ngày/ca | Local ban đầu đạt một phần; chờ kiểm lại |
| Đính chính | Giữ snapshot cũ; lý do; undo điều chỉnh trước sửa; báo cáo dùng phiên bản đúng | Chờ triển khai |
| Tranh chấp | Giao trong lúc đếm; gắn trước/sau chốt; điều chỉnh và hoàn tác xen giao dịch | Chờ kiểm đợt cuối |
| Trả/tiền | Một phần; chờ kiểm; nhập bán lại/hủy; hoàn một/nhiều lần; báo cáo | Chờ kiểm đợt cuối |
| Vật tư | Nhập; cấp phòng; trả dư; kiểm; hoàn tác; tồn theo nơi | Chờ kiểm đợt cuối |
| UI | 375/768/1280; báo cáo ngày tùy chọn; tải Excel; chỉ xem không ghi | Đợt báo cáo đã bấm; chờ hồi quy |
| Staging | SHA/migration đúng; banner; health; prod trước/trong/sau; log | Chưa triển khai đợt mới |


## Kết quả phần đính chính kiểm ca — 18/10/2026

- Phiếu đã chốt giữ nguyên snapshot; nút **Sửa số đếm** yêu cầu lý do và tạo
  phiên bản mới, liên kết `phieu_truoc_id`, `phien_ban`, nhật ký người sửa.
- Bản sửa chỉ sửa số của thuốc/đơn vị đã đếm; không thêm/xoá dòng, không sao chép
  số của ca khác. Muốn đếm thêm thuốc ở thời điểm hiện tại: lập phiếu kiểm mới.
- Nếu từng điều chỉnh tồn, phải hoàn tác trước khi sửa. Phiếu cũ đã có bản sửa
  không được điều chỉnh tiếp; gọi mở bản sửa đồng thời trả cùng một phiếu.
- Chốt bản sửa giữ `moc_ton_luc` và tồn máy từ lần chốt gốc; `chot_luc` ghi giờ
  chốt phiên bản mới. Nhập/xuất sau lần kiểm không bị tính nhầm vào nền đính chính.
- Báo cáo giữ số đếm cũ khi bản sửa còn nháp, chỉ thay bằng phiên bản mới sau
  chốt. Dùng số cuối ca trước lấy phiên bản đã chốt mới nhất.
- Guard chặn điều chỉnh khi có giao chưa gắn lô ở snapshot **hoặc hiện tại**,
  kể cả đã gắn lô sau khi chốt, để không trừ hai lần.

### Kiểm đã thực hiện

| Lớp kiểm | Kết quả |
|---|---|
| `scripts/test-nhanh.sh src/tests/services/test_kiem_ke_ca_db.py` | **77 passed**, 12,94 giây phần pytest; DB tạm dùng migration nhánh |
| Regression migration `20261018120000` chạy lại khi đã có phiếu và bản sửa | Qua; giữ nguyên phiên bản và số đếm |
| Regression bản sửa/điều chỉnh/hoàn tác, report nháp/chốt, đồng thời, khác cơ sở | Qua |
| Pending mới sau chốt / snapshot pending sau gắn lô | Qua; không trừ lại tồn |
| Ruff service + router + test + audit label | Qua |
| Mypy `kiem_ke_ca_service.py` | Qua |
| `npx tsc --noEmit` | Qua |
| `npx tsx --test tests/kiem-ke-ca-boundary.test.mts` | **6 passed** |
| Trình duyệt local/staging 375/1280 | Chờ nghiệm thu chung của lượt triển khai; các test trên chưa thay cho bấm thật |

### Nút/link đã đụng

| Màn | Nút | Lệnh / nơi đến | Ai thấy |
|---|---|---|---|
| Kiểm đầu/cuối ca, kể cả lối mở từ báo cáo | Sửa số đếm | `POST /api/pharmacy/kiem-ke-ca/{id}/sua-so-dem` | Người có quyền ghi kho, khi chưa/đã hoàn tác điều chỉnh |
| Phiếu cũ có bản sửa | Xem bản sửa tiếp theo | Đọc bản sửa liên kết | Người được xem phiếu |
| Phiếu đang sửa | Chốt kiểm kê | Chốt phiên bản, giữ nền tồn của lần chốt gốc | Người có quyền ghi kho |

### Kịch bản người thật

1. Đếm 9 khi tồn 10, chốt: lệch −1 và tồn vẫn 10.
2. Ghi lý do, bấm **Sửa số đếm**: số 9 được điền sẵn, lịch sử còn phiếu gốc.
3. Sửa 8, lưu và tải lại: giữ 8. Trước chốt, báo cáo vẫn dùng bản gốc 9.
4. Chốt bản sửa: lệch −2, báo cáo dùng 8, tồn vẫn 10; phiếu gốc vẫn 9.
5. Điều chỉnh: tồn 8. Muốn sửa tiếp phải hoàn tác: tồn về 10, rồi mới mở bản sửa.
6. Mở phiếu gốc: thấy liên kết sang bản sửa, không có nút điều chỉnh bản cũ.
7. Có giao chờ gắn lô: điều chỉnh báo rõ chưa an toàn; gắn lô sau chốt cũng
   không cho dùng snapshot cũ để điều chỉnh lại. Cần kiểm hiện tại bằng phiếu mới.
