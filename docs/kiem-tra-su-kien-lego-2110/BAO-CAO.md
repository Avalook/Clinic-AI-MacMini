# Kiểm event-driven + lego — 21/10/2026

Đo trên `main` @ `bbd7327d` (đúng bản prod đang chạy) và database prod (chỉ đọc, chỉ đếm).
Không sửa code, không ghi gì lên prod.

## Kết luận

- **Dây sự kiện: tốt.** Có 97 loại sự kiện được khai, code phát đủ cả 97, không phát loại
  nào ngoài danh sách. Trên prod, 30 ngày qua có 72 loại chạy thật. 11 khối nghe đã nhận
  51.683 lần, không kẹt lần nào.
- **Nhưng khoảng 1/3 chỗ đổi dữ liệu nghiệp vụ vẫn "lặng lẽ".** Dữ liệu đã đổi mà không
  phát sự kiện, nên khối khác không biết và dòng thời gian của lượt không ghi. Gồm 78 hàm
  Python và 12 hàm SQL.
- **Lego bên trong máy chủ mới phủ được 1/4.** Bản khai chỉ nói ai giữ 51/183 bảng. Các
  bảng lõi như lượt khám, khách, hàng chờ thì chưa có chủ, nên luật "khối khác không được
  tự ghi" không áp được cho chúng. Có 29 vi phạm luật cắm thật (28 ghi chéo + 1 gọi chéo).
  Agent xếp 3 chỗ là "nặng", nhưng khi kiểm lại bằng test thì 2 chỗ là lỗi tiềm ẩn (đã
  sửa ở gói 1) và 1 chỗ đúng thiết kế (xem mục 2).
- **Lego ở giao diện gần xong.** Chỉ còn 8 chỗ chặn cửa theo vai, nằm trong 4 tệp. Con số
  "~123 chỗ" trong CLAUDE.md là số cũ từ 27/09.

## Hệ thống được thiết kế để chạy thế nào

```
người bấm ──lệnh──▶ KHỐI A ghi bảng CỦA A ──phát sự kiện──▶ KHỐI B, C nghe và tự làm việc của mình
                                                         └▶ dòng thời gian lượt ghi lại
```

Bản khai nằm ở `src/clinicai/modules.py`: 34 khối, mỗi khối khai bảng nó giữ, sự kiện nó
phát/nghe, và lệnh của khối khác mà nó được gọi thẳng.

CI hiện chỉ kiểm bản khai có tự khớp với chính nó không
(`src/tests/unit/test_o_cam_module.py`). CI **chưa** kiểm hai luật chính: "khối không ghi
bảng của khối khác" và "gọi thẳng khối khác thì phải khai ra".

## 1. Chỗ đổi dữ liệu mà không phát sự kiện

Máy tìm ra 415 hàm ghi dữ liệu. Trong đó có 334 hàm không gọi `emit_event` ngay trong
thân hàm. AI đọc từng hàm một và xếp loại:

| Loại | Số hàm | Có cần sửa? |
|---|---|---|
| Hàm gọi nó (hoặc hàm con) đã phát sự kiện | 75 | không |
| Ghi cấu hình, có nhật ký | 64 | không |
| Bảng phụ, hàng đợi kỹ thuật, script, code chết | 88 | không (dọn code chết) |
| **Việc nghiệp vụ không phát sự kiện** | **78** | **có** |
| **Sửa cấu hình mà không để vết (ai sửa, giá cũ)** | **17** | **có** |
| Chưa chắc | 12 | đọc thêm |

Những chỗ đáng lo nhất, gom theo việc ở phòng khám. Mọi chỗ dưới đây mình đã mở code ra
xác nhận; chỗ nào chỉ mới đọc mà chưa chạy thử thì có ghi rõ.

- **Giá cả không có dấu vết.**
  - Sửa giá dịch vụ: `config_service.py:1676`, `:1792`, `:1945`.
  - Sửa danh mục và giá thuốc: `pharmacy_service.py:442`.

  Ví dụ: giá khám đổi từ 300k xuống 200k thì không biết ai đổi, lúc nào, giá cũ bao
  nhiêu. Đây đúng loại câu Quang bị hỏi "số này ở đâu ra".
- **Xoá ca bác sĩ hoặc cho nhân sự nghỉ thì lịch hẹn lặng lẽ mất bác sĩ.**
  - `config_service.py:669` `_go_lich_ngoai_ca`. Hàm này và cả ba nơi gọi nó đều không
    phát sự kiện.
  - Hậu quả: đặt lịch, CSKH và dòng thời gian đều không biết khách vừa mất bác sĩ.
- **Đính chính bệnh án hoặc đơn thuốc đã ký không phát sự kiện.**
  - `clinical_sign_service.py:230` `release`, `:372` `amend`; `dinh_chinh_don.py:413`.
  - Cả tệp `clinical_sign_service.py` không có `emit_event` nào.
  - Quầy thuốc có thể giao theo đơn cũ; CSKH không nhận chuông.
- **Hồ sơ khách: tạo và sửa đều không có sự kiện.**
  - `patient_service.py:256`, `:445`. Danh mục sự kiện chỉ có `patient.contacted`.
  - Khách đổi số điện thoại thì khối CSKH/Zalo không biết.
- **Kho đổi tồn mà không khối nào biết.**
  - Nhập, kiểm, chuyển, điều chỉnh: `kho_thuoc_service.py:488`, `:658`, `:852`;
    `kiem_ke_ca_service.py:1023`, `:1194`.
  - Huỷ lô: `lo_thuoc_service.py:135`.
  - Phiếu vật tư: `vat_tu_kho_service.py:158`, `:238`.
- **Đổi bác sĩ giữa lượt:** `doi_bac_si_service.py:101`. Bác sĩ mới không nhận chuông,
  dòng thời gian không ghi.
- **Hẹn tái khám ghi trong phiếu khám:** `hen_tai_kham_service.py:356`. Không phát
  `followup.scheduled`, trong khi đường ở bàn khám thì có phát.
- **Siêu âm tự tạo lượt khám** khi khách chưa có lượt: `ultrasound_service.py:177`. Không
  phát check-in, nên quầy thu và hành trình không thấy lượt này.
- **Khách từ chối mua thuốc:** `pharmacy_service.py:2537`. Chỉ ghi vào sổ cũ, CSKH không
  được báo để gọi lại hỏi lý do.
- **Ba chỗ xoá cứng, không để vết:** `luat_bac_si_service.py:177`,
  `permission_service.py:556`, `mau_ket_qua_service.py:273`.

### Logic nằm trong SQL (hàm trong database)

Trên prod có 165 hàm SQL. 50 hàm tự ghi bảng:
- 18 hàm canh, ghi lịch sử hoặc đồng bộ phụ: đúng luật, giữ.
- 19 hàm chạy một lần (nạp KiotViet, chuẩn hoá, dọn thử): dọn được.
- 1 hàm có thể đã chết: `order_services`.
- **12 hàm là quyết định nghiệp vụ mà không phát sự kiện:**
  - **Liệu trình.** Khi thêm/sửa chỉ định hoặc thu/hoàn tiền, trigger tự gắn buổi, gỡ
    buổi, chia lại phần trả trước, tính lại cả gói (`lieu_trinh_*`, đã đối chiếu trigger
    trên prod). Đường bấm tay có phát `lieu_trinh.session_relinked`; đường tự động thì
    không phát gì.
  - **Chuỗi việc của lượt.** Check-in tự sinh việc qua các trạm, chuyển trạm tự đóng
    việc cũ, huỷ lịch huỷ việc (`instantiate_visit_workflow`, `move_visit_to_station`,
    `cancel_visit_workflow`, `update_visit_current_node`).
  - **Nhắc tái khám.** Tự sinh việc gọi nhắc, và tự đóng việc đó khi khách đặt lịch
    (`sinh_viec_nhac_tai_kham`, `nhac_tai_kham_dong_khi_co_lich`).

## 2. Ranh giới khối (lego bên trong máy chủ)

**Bảng chưa có chủ:** 100 bảng bị code ghi mà không khối nào khai giữ.
- 50 là bảng nghiệp vụ nên có chủ. Nhiều tệp cùng ghi nhất:
  - `visit` (15 tệp);
  - `thong_bao`, `work_item` (7 tệp mỗi bảng);
  - `encounter_flow` (5 tệp);
  - `consultation`, `patient`, `ultrasound_record` (4 tệp mỗi bảng).
- Khối `payment` quên khai chính bảng `payment`.
- Còn lại: 28 bảng cấu hình, 15 bảng kỹ thuật, 6 bảng có thể bỏ.

**Ghi chéo:** máy đánh dấu 62 chỗ một khối ghi vào bảng của khối khác. AI đọc rồi xếp:
- 19 chỗ đúng thiết kế hoặc máy đoán sai khối;
- **28 vi phạm thật.** Cộng 1 vi phạm ở phần gọi chéo bên dưới thành 29: 3 nặng, 11 vừa,
  15 nhẹ. Phần nhẹ chủ yếu là cột của khối này nằm nhờ trong bảng của khối kia, tức bản
  khai lệch chứ code không sai.
- Riêng **bảng hàng chờ `queue_entry` có ít nhất 7 khối cùng ghi**, trong khi bản khai
  nói chỉ một khối giữ.

**Ba chỗ agent xếp "nặng". Kết quả sau khi kiểm lại bằng test (gói 1, 21/10):**
1. **Chuyển phòng giữa chừng** (`service_routing_service.py:2008`): **lỗi thật, tiềm ẩn,
   đã sửa.**
   - Lệnh đóng lần làm nhưng chỉ phát `service.room_transferred`, nên chuông nhận chéo
     của lần làm ấy treo mãi. Test đỏ đã chứng minh.
   - Trên prod chưa có chuông nào treo: 18 chuông nhận chéo, 0 treo; 30 ngày qua không
     lần nào dùng lệnh này.
   - Sửa: chuông nghe thêm sự kiện ấy.
   - Giả thuyết thứ hai của mình ("B bấm Bắt đầu cũng làm chuông treo") bị test bác bỏ.
2. **Bắt đầu tại bàn khám** (`service_execution_service.py:1216`): **đúng thiết kế,
   không sửa.**
   - Tự xếp vào phòng bàn khám là cố ý (09/10): đó đúng là nơi làm thật.
   - Các bước kiểm của lệnh xếp phòng thường không áp được cho bàn khám.
   - Chỉ bản khai chưa ghi ngoại lệ này, nên chuyển sang gói 4.
3. **Đối tác "Nhận mẫu" khi phòng chưa Bắt đầu** (`doi_tac_service.py:999`, được gọi từ
   nút Nhận mẫu): **lỗi thật, tiềm ẩn, đã sửa.**
   - Lỗi thật chỉ có một: **sổ nợ không được báo** để tính lại số dư của lượt.
   - Hai nghi ngờ khác của agent không đúng: cột trạng thái mới đã đúng là COMPLETED;
     và nhánh nhận chéo không áp cho việc đối tác.
   - Trên prod chưa từng có lần nào đi đường này.
   - Sửa: sổ nợ nghe thêm `partner.sample_collected`.

Bài học: mức "nặng" của agent dựa trên đọc code. Phải chạy test và đếm trên prod thì mới
biết mức độ thật.

**Gọi chéo:** 51 cạnh. 46 cạnh là gọi đúng hàm của khối chủ, nhưng **chỉ 1 cạnh được khai**
trong `goi_dong_bo`. Bản khai đang thiếu, nên đọc nó không thấy hết đường dây.

## 3. Lego ở giao diện

Tổng 150 chỗ đã đọc:
- 38 chỗ đã theo lego;
- 37 chỗ lai (có quyền thì xét quyền, chưa biết thì xét vai);
- 48 chỗ chỉ đổi chữ hoặc bố cục theo vai, giữ được;
- 19 chỗ là code chết;
- **8 chỗ chặn cửa theo vai**, nằm trong 4 tệp: `layout.tsx`, `home/page.tsx`,
  `patients/new/page.tsx`, `lib/roles.ts`.

Ví dụ hậu quả của kiểu chặn cửa theo vai:
- **Khung "bác sĩ từ chối lịch"** (`layout.tsx:105`) xét vai. Thu ngân được bật lego Quản
  lý lịch hẹn vẫn không thấy khung.
- **Cột "Điền sinh hiệu"** trên trang chủ vào ngày không có ca (`home/page.tsx:176`) chỉ
  hiện cho điều dưỡng. Lễ tân được bật lego Đo sinh hiệu vẫn không thấy.
- **Điều dưỡng luôn bị ép dùng biểu mẫu vãng lai cũ**, kể cả khi đã có lego Tiếp đón
  (`patients/new/page.tsx:37`).

## 4. Code chết dọn được

- **Python, khoảng 20 đường không màn nào gọi:**
  - nháp chỉ định của `service_order_service`;
  - 3 công cụ lịch của `scheduling_service`. Nếu ai nối lại thì sẽ đặt lịch mà bỏ qua
    `booking_service`.
  - các đường start/complete/goi/notes cũ của `luot_kham_service`.
- **Giao diện:** 19 chỗ, nằm ở 5 route đã tắt (`lib/route-da-tat.ts`).
- **Database:**
  - 6 bảng có thể bỏ: `service_log`, `service_order_draft`, `mpi_merge_queue` (chỉ ghi
    vào, không ai đọc ra), `work_session`, `work_session_staff`, `staff_task`;
  - 19 hàm chạy một lần; hàm `order_services`.
  - Xoá bảng/hàm trên database là Mức 3.

## 5. Đề xuất thứ tự sửa

Mỗi gói một PR, viết test đỏ trước rồi mới sửa.

1. ~~Ba vi phạm nặng~~ — **xong ở gói 1** (nhánh `claude/goi1-vi-pham-nang`, commit
   `6911bddd`): đã sửa 2 việc; việc bàn khám chuyển sang gói 4.
2. **Dấu vết khi sửa giá dịch vụ/thuốc** và 3 chỗ xoá cứng. Mức 2. Cho câu "số này ở đâu ra".
3. **Sự kiện cho các việc lặng lẽ ở mục 1:** hồ sơ khách, đính chính đã ký, kho, đổi/gỡ
   bác sĩ, hẹn tái khám, siêu âm tự tạo lượt. Mức 2, chia nhiều PR nhỏ.
4. **Khai chủ cho 50 bảng lõi** trong `modules.py`, khai đủ `goi_dong_bo` (kể cả ngoại lệ
   "bắt đầu tại bàn khám tự xếp phòng" từ gói 1), và thêm bài CI
   "khối không ghi bảng khối khác". Lúc đầu chỉ báo, chưa làm CI đỏ. Mức 1. Đây là nền cho
   bản đồ code thống nhất và cho việc tách tệp to.
5. **Lego giao diện:** 8 chỗ, 4 tệp. Mức 2.
6. **Logic SQL không phát sự kiện** (liệu trình, chuỗi việc, nhắc tái khám). Mức 3, cần
   kế hoạch riêng.
7. **Dọn code chết.** Python và giao diện là Mức 1–2; bảng và hàm database là Mức 3.

## Cách đo và giới hạn

- **Lớp 1, máy đếm.** `quet_backend.py` trong thư mục này đọc code theo cú pháp, không đọc
  bằng mắt. Nó tìm mọi câu SQL ghi bảng, mọi `emit_event`, mọi import giữa các tệp service.
  Máy quét phía giao diện bằng regex nằm ở `du-lieu/giao-dien.tsv`. Chạy lại máy quét
  backend:
  ```bash
  python3 -I docs/kiem-tra-su-kien-lego-2110/quet_backend.py . /tmp/kq-quet
  ```
- **Lớp 2, prod chỉ đọc.** Lấy hàm SQL, trigger và sự kiện 30 ngày với người nghe
  (`du-lieu/su-kien-prod-30-ngay.tsv`).
- **Lớp 3, AI đọc.** 6 agent đọc từng chỗ máy đánh dấu (`du-lieu/ra-*.json`, mỗi dòng có
  tệp:dòng và lý do). Mình kiểm tay 11 kết luận nặng nhất: 11/11 đúng. Riêng kết luận
  "không ai gọi `get_pending_queue`" là đúng vì cả 4 chỗ có tên này đều chỉ là test.
- **Điểm mù:**
  - Câu SQL dựng tên bảng lúc chạy thì máy không thấy.
  - Kết luận "không màn nào gọi" dựa trên tìm chữ, có thể sót khi màn ghép đường dẫn lúc chạy.
  - Mục "chuông kêu mãi" mới đọc code, chưa bấm thử.
  - Có 12 hàm Python xếp "chưa chắc".
