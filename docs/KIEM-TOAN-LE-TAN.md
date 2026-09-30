# Kiểm toán vai Lễ tân — ClinicAI

Ngày: 19/08/2026 · Phạm vi: 7 mục thanh bên của vai `RECEPTION` · **9 lễ tân đang dùng thật**
(nhóm đông thứ ba, ngang bác sĩ).

Phương pháp: 5 chuyên gia đọc song song toàn bộ mã nguồn của từng màn — từ nút bấm trên
giao diện, qua tầng chuyển tiếp, tới service và bảng dữ liệu. Mọi khẳng định kèm `tệp:dòng`.
Các phát hiện nặng nhất đã được **kiểm chứng lại độc lập** trên mã nguồn và trên dữ liệu thật
của staging (ghi rõ trong từng mục).

> **Kết luận một câu:** lễ tân *vừa thiếu vừa thừa* — hai công cụ của riêng họ cộng lại chưa
> tới 1.600 dòng và phần lớn là vỏ rỗng, trong khi họ bị thả vào hai màn khổng lồ (14.000 dòng)
> xây cho vai khác, nơi có bốn nút bấm vào là bị từ chối.

## Bảng cân đối nhanh

| Màn | Dòng code | Đánh giá |
|---|---:|---|
| Hàng đợi tiếp nhận | 733 | Vỏ rỗng — ~20 điều khiển, 3 thứ chạm database |
| Check-out lượt khám | 794 | Phần đọc đầu tư kỹ hơn phần làm; 1/2 nút hành động chết |
| Danh sách bệnh nhân | 860 | Quá mỏng với lễ tân, trùng chỗ với Quản lý khách hàng |
| Tạo bệnh nhân | 1.846 | Lõi tốt; 5 cột địa chỉ ghi rồi không ai đọc |
| Trang chủ | 1.972 | Đáng giữ, cần sửa 5 điểm |
| Quản lý khách hàng *(xây cho CSKH)* | 8.342 | Giữ nhưng phải rút gọn — 4 nút hỏng |
| Công việc của tôi *(xây cho bác sĩ)* | 5.768 | Không đáng nằm trên thanh bên lễ tân |

## Ba lỗi nghiêm trọng nhất (đã kiểm chứng)

**① Lễ tân gọi khách theo thứ tự SAI.** Hệ có luật gọi số ở backend (`queue_order.py`:
ưu tiên → có hẹn đúng giờ → vãng lai theo giờ đến), có bài kiểm canh. Bảng TV dùng luật đó.
Nhưng màn hàng đợi của chính lễ tân tự xếp ở trình duyệt theo *số phút chờ lâu nhất*
(`QueueBoard.tsx:172`). Quầy gọi một đằng, bảng ngoài hiện một nẻo.

**② Đóng lượt ở quầy không đóng lịch hẹn.** `CheckoutService.close()` **không gọi**
`apply_action("complete")` — nó chỉ huỷ các việc còn mở. Đường CSKH thì có gọi
(`tuong_tac_cskh_service.py:481`). Hệ quả: khách đã về vẫn còn tên trên bảng gọi số.
*Dữ liệu thật staging:* 32/32 lượt khám kẹt ở `IN_PROGRESS`, trong đó 20 lịch hẹn đã COMPLETED.

**③ Bốn nút bày ra cho lễ tân mà backend từ chối.** Gốc: `canOperateCustomerCare`
(`roles.ts:140`) chỉ là bí danh của `canWriteIntake` nên lễ tân nhận nguyên vùng làm việc
CSKH — trong khi `MANAGE_ROLES` = {CSKH, MANAGEMENT, TRUONG_CA} **không có RECEPTION**.
Nút "Checkout", "Hẹn tái khám", "Đặt lịch mới", "Đổi/huỷ lịch" đều hỏng theo cách khác nhau.

## Đồ trang trí (hiện số nhưng không bao giờ có dữ liệu)

- **Ô "Quá SLA" + thanh tiến độ**: cột `due_at` chưa từng có dòng code nào ghi vào.
  *Dữ liệu thật staging:* 242 công việc, **0** cái có hạn. Luôn 0, luôn "—", luôn 0%.
- **Nút "Check-in — khách đã đến"** trên màn hàng đợi: không bao giờ hiện, vì việc chỉ sinh
  ra *sau khi* check-in.
- **Ô "Bảo hiểm y tế"**, **"Địa chỉ"** trong thẻ bệnh nhân: một dòng báo thiếu dữ liệu.
- **Màn `/queue`**: `roles.ts:365` khai `[]` — tạm ẩn từ 03/07, không vai nào vào được.

---

## 1. Hàng đợi tiếp nhận — /reception/queue

Phạm vi đọc: `src/dashboard/app/(dashboard)/reception/queue/page.tsx` (95 dòng),
`QueueBoard.tsx` (638 dòng), `lib/worklist.ts`, `lib/worklist-server.ts`,
`lib/work-item-status.ts`, route BFF `app/api/work-items/[id]/commands/[command]/route.ts`
và `app/api/appointments/route.ts`, backend `src/clinicai/api/v1/routers/work_items.py`,
`src/clinicai/services/work_item_service.py`, `booking_service.py`, cùng seed
`supabase/migrations/20260730000006_seed_node_catalogue.sql` và
`20260731000003_visit_workflow_instantiation.sql`.

Vai được vào: `RECEPTION`, `NURSE_ULTRASOUND`, `MANAGEMENT` — `lib/roles.ts:263-265`.
Trưởng ca KHÔNG có mục này trên thanh bên, dù backend cho `TRUONG_CA` đọc chéo
node (`work_item_service.py:472-473`). Lệch nhỏ, chưa gây hại.

---

### 1. Bên trong màn có những THÀNH PHẦN gì

| Thành phần | Làm gì | Vai nào thấy |
|---|---|---|
| `LiveBoardSync` (page.tsx:32) | Làm mới khi vào màn / khi quay lại tab | Mọi vai vào được |
| Thẻ lỗi tải hàng đợi (page.tsx:40-54) | Phân biệt "mất kết nối" với "hàng đợi trống" | Như trên |
| StatCard **Đang chờ tiếp nhận** (page.tsx:58-63) | Đếm `status === "PENDING"` | Như trên |
| StatCard **Đang xử lý** (page.tsx:65-69) | Đếm `status === "IN_PROGRESS"` | Như trên |
| StatCard **Cần xác minh** (page.tsx:70-75) | Đếm `node_code === "LUOTKHAM-02"` | Như trên |
| StatCard **Quá SLA** (page.tsx:76-81) | Đếm `isOverdue(i)` | Như trên |
| Cột trái — khối "Danh sách hàng đợi" (QueueBoard.tsx:199-307) | Khung chứa 6 điều khiển dưới | Như trên |
| Tab **Tất cả** / **Cần xác minh** (QueueBoard.tsx:206-234) | Lọc theo `node_code` | Như trên |
| Ô tìm kiếm (QueueBoard.tsx:236-246) | Lọc theo tên / mã BN / số thứ tự | Như trên |
| Select **Bộ lọc** (QueueBoard.tsx:248-262) | Đặt hẹn ↔ Đến trực tiếp | Như trên |
| Select **Sắp xếp** (QueueBoard.tsx:263-276) | Chờ lâu ↔ số thứ tự | Như trên |
| Dòng người bệnh `Row` (QueueBoard.tsx:84-142) | STT · tên · `PriorityChip` · năm sinh/giới/tuổi · `StatusChip` · kênh đến · số phút chờ | Như trên |
| Chân bảng: "Hiển thị X trong Y" + nút **Xem tất cả** (QueueBoard.tsx:301-306) | Đếm và xoá bộ lọc | Như trên |
| Cột giữa — "Thông tin người bệnh" (QueueBoard.tsx:328-420) | Khung chứa 5 khối dưới | Như trên |
| Thẻ nhân thân (QueueBoard.tsx:354-370) | Chữ cái đầu, tên, SĐT, mã BN | Như trên |
| `dl` Mã số / Ngày sinh / **Địa chỉ** (QueueBoard.tsx:371-378) | 2 trường thật + 1 dòng báo thiếu dữ liệu | Như trên |
| Ô **SLA mục tiêu** + thanh tiến độ + Thời gian chờ (QueueBoard.tsx:379-392) | Đích phút, % đã tiêu, phút đã chờ | Như trên |
| InfoCard **Lịch hẹn** (QueueBoard.tsx:396-400) | Ngày/giờ hẹn, hình thức, tên bước | Như trên |
| InfoCard **Thông tin hàng đợi** (QueueBoard.tsx:401-405) | Giờ đến, giờ vào hàng, giờ bắt đầu xử lý | Như trên |
| InfoCard **Bảo hiểm y tế** (QueueBoard.tsx:406-410) | Một dòng chữ báo chưa có dữ liệu | Như trên |
| `Stepper` **Trạng thái xử lý** (QueueBoard.tsx:413-416, 67-82) | 2 bước: Check-in → Gọi vào khám | Như trên |
| Cột phải — "Điều phối tại quầy" (QueueBoard.tsx:477-616) | Khung chứa 8 khối/nút dưới | Như trên |
| Khối **Hiện trạng quầy** (QueueBoard.tsx:484-502) | 4 ô: Sức chứa · Đang phục vụ · Đang chờ · Trống | Như trên |
| Khối **Xem trước màn hình hiển thị** (QueueBoard.tsx:504-530) | Vẽ thử thẻ "Mời <tên> · số <STT> · chờ N′" | Như trên |
| Khối **Nhật ký thao tác** (QueueBoard.tsx:532-546) | 2 dòng mốc thời gian | Như trên |
| Khối **Bước tiếp theo** (QueueBoard.tsx:548-554) | Một câu giải thích tĩnh | Như trên |
| Ô báo lỗi thao tác (QueueBoard.tsx:557) | Hiện `error` của lệnh vừa bấm | Như trên |
| Nút **Check-in — khách đã đến** / dòng "Đã check-in lúc" (QueueBoard.tsx:564-578) | `PATCH /api/appointments` action `checkin` | Như trên |
| Nút **Chưa đến — gọi người tiếp theo** (QueueBoard.tsx:590-596) | Nhảy chọn sang dòng kế tiếp | Như trên |
| Nút **Bắt đầu xử lý** (QueueBoard.tsx:597-606) | Lệnh kernel `start` | Như trên |
| Nút **Xong tiếp nhận — mời vào khám** (QueueBoard.tsx:607-615) | Lệnh kernel `complete` | Như trên |

Tổng: 4 thẻ số + 3 cột + khoảng 20 điều khiển/khối con.

---

### 2. Logic nào CHẠY THẬT

**✅ Chạy thật**

- **Tải danh sách.** `fetchWorklist("bang_dieu_phoi")` (page.tsx:28) →
  `GET {CLINIC_API_URL}/api/v1/work-items?workspace=…` (worklist-server.ts:49) →
  `require_workspace_read_access` (work_items.py:345) →
  `WorkItemService.list_worklist` (work_item_service.py:370) đọc `work_item`
  JOIN `node_definition` / `appointment` / `visit` / `patient` / `service_type`.
  Có gác đa phòng khám (`w.clinic_id = $3`) và gác vai (`m.role = ANY(n.actor_roles)`).
- **Nút "Bắt đầu xử lý"** → `POST /api/work-items/{id}/commands/start`
  (route.ts:43-47) → `WorkItemService.issue` (work_item_service.py:80) → `UPDATE
  work_item` + `INSERT work_item_event` trong một giao dịch, có kiểm vai
  (work_item_service.py:142-151), kiểm cổng phụ thuộc (:153-160) và
  `expected_version` chống ghi đè.
- **Nút "Xong tiếp nhận — mời vào khám"** → lệnh `complete`, cùng đường trên.

**⚠️ Chạy nửa vời**

- **"Xong tiếp nhận" KHÔNG dời con trỏ vị trí.** `issue()` không đụng
  `visit.current_node_code` (không có chuỗi ấy trong `work_item_service.py`);
  chỉ `move_visit_to_station` (`supabase/migrations/20260804000006_…sql:26`) dời,
  và nó do màn Trưởng ca gọi. Lễ tân bấm xong → bảng điều phối vẫn thấy người
  này đứng ở quầy tiếp nhận.
- **Nút "Chưa đến — gọi người tiếp theo"** (`QueueBoard.tsx:590-596` → `onSkip`
  tại `QueueBoard.tsx:314-321`): chỉ `setSelectedId`. Không ghi gì, không có mốc
  "đã gọi", không đánh dấu gì cho lần sau — người vừa bị bỏ qua và người chưa
  từng gọi trông giống hệt nhau.
- **"Nhật ký thao tác"** (`QueueBoard.tsx:536-545`): suy ra từ `created_at` và
  `started_at`, tối đa 2 dòng. Bảng `work_item_event` CÓ ghi thật
  (`work_item_service.py:200`) nhưng không có endpoint nào đọc nó ra — grep
  `work_item_event` trong `src/clinicai/api` không ra dòng SELECT nào.
- **Nút "Xem tất cả"** (`QueueBoard.tsx:303`): reset `tab`/`arrival`/`query`
  nhưng KHÔNG reset `sort`. Bấm xong vẫn còn một bộ lọc đang bật.
- **Nút bị `blocked` không nói vì sao.** `canAct` (`QueueBoard.tsx:473`) tắt nút
  im lặng. Route `/api/work-items/[id]/blockers` đã có và màn Bàn khám đang dùng
  (`doctor/board/DoctorBoard.tsx:477`); màn này không gọi.

**❌ Chết**

- **Nút "Check-in — khách đã đến"** (`QueueBoard.tsx:569-577`) **không bao giờ
  hiện**. Nhánh `item.checked_in_at ? … : <button>` ở `QueueBoard.tsx:564` luôn
  rơi vào vế "Đã check-in lúc", vì: work_item CHỈ được sinh trong
  `instantiate_visit_workflow` gọi từ `_open_visit` lúc check-in
  (`booking_service.py:1861-1867`), và cả ba đường tạo `visit` đều ghi
  `checked_in_at = now()` (`booking_service.py:1832-1841`,
  `clinical_record_service.py:437-446`, `ultrasound_service.py:173-181`). SQL
  của bảng lấy `v.checked_in_at` qua LEFT JOIN visit (`work_item_service.py:436,
  452-454`) nên cột này không thể null. Hàm `checkIn()` (`QueueBoard.tsx:442-456`)
  là code chết theo.
- **Bước "Check-in" của Stepper** (`QueueBoard.tsx:71-75`): luôn `done`, nhánh
  "Chưa đến" không bao giờ vẽ — cùng lý do trên.
- **StatCard "Quá SLA"** (`page.tsx:76-81`) luôn bằng 0. `work_item.due_at` được
  khai ở `supabase/migrations/20260730000005_workflow_kernel.sql:140` nhưng
  KHÔNG có một câu ghi nào trong repo (grep `due_at` trong `supabase/` chỉ ra 3
  dòng khai cột; `instantiate_visit_workflow` không liệt kê cột này ở
  `20260731000003_…sql:109-113`).
- **Ô "SLA mục tiêu" + thanh tiến độ** (`QueueBoard.tsx:331-338, 379-392`): luôn
  "—" và thanh rộng 0%.
- **Cột phải của mỗi dòng không bao giờ đổi màu/đổi chữ "quá"**
  (`QueueBoard.tsx:132-138`), và `StatusChip` không bao giờ ra nhãn "Quá SLA"
  (`work-item-status.ts:131`) — cùng lý do `due_at`.
- **Tab "Cần xác minh"** (`QueueBoard.tsx:218`) cho ra danh sách **y hệt** tab
  "Tất cả". Workspace `bang_dieu_phoi` chỉ có 2 node —
  `LUOTKHAM-01` và `LUOTKHAM-02` (seed:44-45); `LUOTKHAM-01` sinh ra đã
  `COMPLETED` (`20260731000003_…sql:57-60` đặt `spawn_on`, `:116-119` đặt trạng
  thái), còn truy vấn chỉ lấy `PENDING`/`IN_PROGRESS`
  (`work_item_service.py:474`). Nghĩa là 100% dòng trên bảng là `LUOTKHAM-02`.
- **StatCard "Cần xác minh"** (`page.tsx:70-75`) vì thế luôn bằng tổng số dòng,
  tức bằng "Đang chờ tiếp nhận" + "Đang xử lý". Một con số nói lại điều đã nói.
- **`PriorityChip`** (`QueueBoard.tsx:117`) không bao giờ hiện: `is_priority_slot`
  chỉ được ghi từ `scheduling_service.py:300,319`, mà route đặt lịch của
  dashboard không gửi trường ấy (payload `app/api/appointments/route.ts:263-282`).
  Chú thích tại `QueueBoard.tsx:209-217` tự thừa nhận điều này.
- **Nhánh lọc `tab === "priority"`** (`QueueBoard.tsx:156`): không tab nào đặt
  được giá trị đó nữa — code không ai gọi tới.
- **"Hiện trạng quầy"**: "Sức chứa" và "Trống" là chuỗi `"—"` viết cứng
  (`QueueBoard.tsx:490,494`), kèm nhãn tự thú "Chưa kết nối schema quầy"
  (`QueueBoard.tsx:487`). 2/4 ô là trang trí.
- **"Xem trước màn hình hiển thị"** (`QueueBoard.tsx:504-530`): chỉ vẽ tại chỗ,
  không có `fetch`, không đẩy gì lên TV. Màn TV thật đọc `DisplayBoardService`
  và xếp theo `queue_order.py` — hai thứ không liên quan nhau.
- **"Bước tiếp theo"** (`QueueBoard.tsx:548-554`): một câu chữ tĩnh.
- **InfoCard "Bảo hiểm y tế"** (`QueueBoard.tsx:406-410`) và dòng "Địa chỉ"
  (`QueueBoard.tsx:376`): chiếm 1/3 hàng InfoCard chỉ để nói "chưa có dữ liệu".

**Đếm: 11 khối/nút ❌ chết, 5 ⚠️ nửa vời, 3 ✅ chạy thật.**

Thêm một điểm đáng ngờ về chất lượng canh gác: bài kiểm
`src/dashboard/tests/reception-queue-ui-boundary.test.mts:36` bắt buộc có chuỗi
"Ưu tiên" trong `board` — nhưng nó khớp trên bản CÓ chú thích, và tab ấy đã bị
gỡ; bài kiểm xanh nhờ đúng câu chú thích ở `QueueBoard.tsx:215`. Một bài canh
không còn canh gì.

---

### 3. CHỒNG CHÉO với màn khác

**a) Check-in — trùng với Trang chủ, và bên kia mới là bên chạy được.**
`HomeCheckin.tsx:238` (nút Check-in), `:244` (Không đến), `:226` (Hoàn tác
check-in) gọi cùng `PATCH /api/appointments` mà `QueueBoard.tsx:445-448` gọi.
Khác nhau tinh vi: Trang chủ liệt kê **lịch hẹn hôm nay** (kể cả người CHƯA đến)
nên nút bấm được; màn này liệt kê **work_item**, chỉ tồn tại SAU khi đã check-in
— nên nút ở đây vĩnh viễn không hiện. Trang chủ còn có `no_show` và `undo_checkin`;
màn này không có cái nào. Đồng bộ về đường ghi, nhưng lệch hẳn về tập dữ liệu.

**b) Thứ tự gọi — KHÔNG đồng bộ, và đây là chỗ nguy hiểm nhất.**
`/queue` xếp theo `call_rank` do backend tính (`queue/page.tsx:34`, luật 4 làn ở
`services/queue_order.py`, có làn "ƯT" đọc từ tiền tố số vé `_ut_num`, và làn
"đến muộn"). Trang chủ xếp theo `call_order` (`HomeCheckin.tsx:80-82`). TV phòng
chờ dùng chính `explain_queue` (`display_board_service.py`, đoạn ②: "THỨ TỰ PHẢI
GIỐNG HỆT BẢNG CỦA NHÂN VIÊN"). **Còn màn này xếp theo số phút chờ**
(`page.tsx:86-88` và `QueueBoard.tsx:172-178`) — một luật thứ tư, không ai
duyệt, và nó bỏ qua cả ưu tiên lẫn giờ hẹn. Lễ tân đọc bảng này rồi gọi tên sẽ
gọi lệch với thứ tự TV đang chiếu cho phòng chờ xem.

**c) "Ai đang chờ ở đâu"** — `/truong-ca/hang-doi` (`truong-ca/hang-doi/page.tsx`)
liệt kê hàng đợi theo từng trạm, gồm cả trạm tiếp nhận. Khác nhau: bên kia là góc
nhìn toàn phòng khám và có quyền **dời** người bệnh sang trạm khác; bên này chỉ
đóng được bước của chính mình.

**d) Đóng lượt** — `/reception/checkout` (`reception/checkout/page.tsx`) lo node
`LUOTKHAM-15`. Không chồng chéo, nhưng là màn thứ hai của cùng một người ngồi
cùng một quầy.

---

### 4. NGHIỆP VỤ CÓ ĐỦ KHÔNG

Một buổi sáng ở quầy sản phụ khoa, đối chiếu từng việc:

| Tình huống | Màn này làm được? |
|---|---|
| Khách có hẹn đến, báo tên | **Không.** Người chưa check-in không xuất hiện trên bảng (mục 2). Phải sang Trang chủ. |
| Khách đến sớm | Không có gì phân biệt đến sớm; không có giờ hẹn trên dòng danh sách (chỉ có trong khối chi tiết, `QueueBoard.tsx:397`). |
| Khách đến muộn | Luật "đến muộn" nằm ở `queue_order.py` và màn này không dùng — xếp theo phút chờ nên người đến muộn vẫn có thể đứng trên. |
| Khách vãng lai không hẹn | **Không.** Không có nút tạo lượt/tạo bệnh nhân; phải sang `/appointments` hoặc `/patients/new`. |
| Bà bầu / khách ưu tiên | **Không.** `PriorityChip` không bao giờ bật; vé "ƯT" của `queue_order.py` màn này không hiểu. |
| "Còn bao lâu tới lượt tôi?" | **Không.** Không có vị trí thứ mấy, không có ước tính phút, không có SLA thật. |
| Khách bỏ về giữa chừng | **Không.** Không có `no_show`, không có huỷ, không có đánh dấu INCOMPLETE. |
| Gọi tên khách vào khám | Chỉ **xem trước** thẻ mời (`QueueBoard.tsx:504-530`). Không có nút Gọi, không có mốc "đã gọi lúc" — `work-item-status.ts:70-74` tự ghi nhận: khái niệm `called` chưa có schema. |
| In vé / phiếu | **Không.** Trang chủ có (`HomeCheckin.tsx:213,217`). |
| Hỏi BHYT, địa chỉ | **Không** — hai ô báo thiếu dữ liệu. |
| Chỉ khách sang phòng nào | **Không.** Không có dữ liệu quầy/phòng. |
| Xác minh dịch vụ hôm nay rồi mời vào khám | **Có** — đây là việc duy nhất màn này làm trọn vẹn (2 nút kernel). |

Nói gọn: tên màn là "Hàng đợi **tiếp nhận**", nhưng nó là màn **sau tiếp nhận** —
mọi việc đón khách thật đã xảy ra ở Trang chủ trước khi dòng đầu tiên hiện ra ở
đây.

---

### 5. ĐÁNH GIÁ CHUYÊN MÔN

Màn này **vừa rườm rà vừa mỏng**, và rườm rà là triệu chứng chứ không phải bệnh:
3 cột, ~20 điều khiển, mà chỉ 3 thứ chạm được database. 11 khối/nút chết chiếm
gần hết diện tích cột phải và cột giữa. Người dùng học rất nhanh rằng phần lớn
màn hình là chữ trang trí — và khi đó họ cũng bỏ qua nốt 3 thứ có thật.

Đề xuất, xếp theo ưu tiên:

1. **Sửa thứ tự sắp xếp về `call_rank` của backend** (thay `waitedMinutes` ở
   `page.tsx:86-88` và `QueueBoard.tsx:172-178`).
   *Vì sao:* đây là lỗi nghiệp vụ thật, không phải lỗi thẩm mỹ — bảng của Lễ tân
   đang nói một thứ tự khác với TV phòng chờ và khác với `/queue`. Gọi sai lượt
   là thứ khách nhìn thấy ngay.
   *Công sức: vừa* (cần thêm trường thứ tự vào `/api/v1/work-items` hoặc ghép
   với `/api/v1/queue`).

2. **Gỡ toàn bộ phần chết vì `due_at`** — StatCard "Quá SLA" (`page.tsx:76-81`),
   ô "SLA mục tiêu" + thanh tiến độ (`QueueBoard.tsx:379-392`), nhánh "quá"
   trong `Row` (`QueueBoard.tsx:132-138`) — HOẶC ghi `due_at` lúc
   `instantiate_visit_workflow` theo SLA của node.
   *Vì sao:* một thẻ đếm luôn bằng 0 và một thanh tiến độ luôn 0% dạy người dùng
   rằng chưa ai quá hạn — đúng cái kết luận sai nhất mà quầy có thể tin.
   *Công sức: nhỏ nếu gỡ · vừa nếu nối (cần cột SLA trong node_definition).*

3. **Gộp việc đón khách vào đúng màn này**: đưa danh sách lịch hẹn hôm nay CHƯA
   check-in (đường mà `HomeCheckin` đang đọc) lên bảng, giữ nguyên nút check-in
   đã viết sẵn ở `QueueBoard.tsx:569-577`, và thêm "Không đến" + "Hoàn tác".
   *Vì sao:* hiện Lễ tân phải làm việc trên hai màn cho một hàng người; và cái
   nút quan trọng nhất của màn "tiếp nhận" đang là code chết.
   *Công sức: lớn.*

4. **Bỏ tab "Cần xác minh", StatCard "Cần xác minh", `PriorityChip`, nhánh
   `tab === "priority"`, khối "Bước tiếp theo", 2 ô "—" trong Hiện trạng quầy,
   ô BHYT và dòng Địa chỉ.** Sửa luôn bài kiểm
   `reception-queue-ui-boundary.test.mts:36` đang khớp vào chú thích.
   *Vì sao:* tab thứ hai trả về đúng danh sách của tab thứ nhất là nói dối bằng
   giao diện; phần còn lại là chỗ trống có viền.
   *Công sức: nhỏ.*

5. **Hiện lý do bị chặn** khi `canAct === false` bằng
   `/api/work-items/[id]/blockers`, y như `doctor/board/DoctorBoard.tsx:477`; và
   dời con trỏ `visit.current_node_code` khi `complete` thành công.
   *Vì sao:* nút xám không giải thích là nguyên nhân số một của việc gọi điện
   hỏi kỹ thuật; còn con trỏ không dời khiến bảng điều phối tin rằng người bệnh
   vẫn đang đứng ở quầy.
   *Công sức: nhỏ (blockers) · vừa (con trỏ — cần chốt ai chịu trách nhiệm dời).*

*Chưa rõ — cần kiểm:* liệu trên prod có node nào khác được cấu hình vào
workspace `bang_dieu_phoi` ngoài 2 node trong seed hay không (kết luận về tab
"Cần xác minh" dựa trên seed, không dựa trên dữ liệu prod).


---

## 2. Check-out lượt khám & Bảng số thứ tự

# MÀN A — Check-out lượt khám (`/reception/checkout`)

### 1. Thành phần bên trong

Quyền vào màn: `RECEPTION, TRUONG_CA, MANAGEMENT` (`roles.ts:262`), khớp gác BFF
(`route.ts:12`) và `_RECEPTION_GUARD` (`dispatch.py:301,339,355,379`); Quản lý vào được
nhưng mục bị ẩn khỏi thanh bên (`roles.ts:439-446`). Không thành phần nào phân biệt vai.

| Thành phần | Làm gì | Vai nào thấy |
| --- | --- | --- |
| Tiêu đề GlobalHeader | "Check-out lượt khám" + phụ đề đặt cứng theo pathname — `GlobalHeader.tsx:223-229` | cả 3 |
| `LiveBoardSync` | `router.refresh()` khi vào màn và khi tab được nhìn lại — `page.tsx:23`, `LiveBoardSync.tsx:35-45` | cả 3 |
| Băng đỏ "Không đọc được danh sách" | Hiện khi backend im lặng (`ok=false`) — `CheckoutBoard.tsx:193-201` | cả 3 |
| Toast kết quả | Câu xác nhận sau khi đóng, tắt sau 3.5s — `CheckoutBoard.tsx:115-118,203-207` | cả 3 |
| 3 tab: Tất cả / Đủ điều kiện / Bị chặn | Lọc client trên `can_close` — `CheckoutBoard.tsx:179-189,230-244` | cả 3 |
| Ô tìm tên hoặc mã BN | Lọc client — `CheckoutBoard.tsx:246-252,162-173` | cả 3 |
| Danh sách lượt (cột trái) | Mỗi dòng là nút chọn, kèm giờ check-in + chip "Đủ điều kiện đóng"/"Còn N việc" — `CheckoutBoard.tsx:261-308` | cả 3 |
| Mục ① Dịch vụ | Từng `work_item`, ai làm, xong lúc mấy giờ — `ChiTietLuot.tsx:193-226` | cả 3 |
| Mục ② Tài chính | Từng dòng `payment`, số tiền, đã huỷ chưa — `ChiTietLuot.tsx:228-264` | cả 3 |
| Mục ③ Hồ sơ trả bệnh nhân | Chỉ một câu "chưa có" — `ChiTietLuot.tsx:266-279` | cả 3 |
| Mục ④ Theo dõi sau khám | `follow_up_case` sinh từ lượt — `ChiTietLuot.tsx:281-310` | cả 3 |
| Hộp kết luận đối soát | Xanh "đóng được" / vàng liệt kê blockers — `ChiTietLuot.tsx:312-335` | cả 3 |
| Thẻ "Thông tin lượt khám" | Tên, mã BN, giờ check-in, phòng, trạng thái lượt — `ChiTietLuot.tsx:340-356` | cả 3 |
| Thẻ "Dòng thời gian" | Mốc thật từ `work_item_event` — `ChiTietLuot.tsx:358-381` | cả 3 |
| Ô nhập lý do ngoại lệ | Textarea, CHỈ render khi `blockers.length > 0` — `CheckoutBoard.tsx:318-329` | cả 3 |
| Nút "Xác nhận đóng lượt khám" | Đường đóng chính — `CheckoutBoard.tsx:331-340` | cả 3 |
| Nút "Đóng — khách về giữa chừng" | Đóng kèm `incomplete=true` — `CheckoutBoard.tsx:341-349` | cả 3 |

### 2. Logic nào chạy thật

✅ Đọc danh sách: `page.tsx:17-19` → `dispatch.py:337-346` → `CheckoutService.pending_list`
(`checkout_service.py:131-170`) → `visit`+`work_item`+`service_log`+`lab_result`+`payment`+
`prescription` (`_READINESS_SQL`, `checkout_service.py:51-93`). Realtime nghe 3 bảng
`visit/work_item/payment` (`CheckoutBoard.tsx:94-102`), lưới an toàn 60s (`:106`).
✅ Đọc chi tiết: `ChiTietLuot.tsx:153` → `route.ts:39` → `dispatch.py:318-334` →
`CheckoutService.chi_tiet` (`checkout_service.py:172-326`), 4 truy vấn thật.
✅ Đóng lượt: `CheckoutBoard.tsx:124-133` → `route.ts:57` → `dispatch.py:376-397` →
`CheckoutService.close` (`checkout_service.py:373-587`). Một transaction: đóng work_item
LUOTKHAM-15, xoá con trỏ phòng + ghi `visit.closed_at/closed_by_staff_id`, huỷ mọi
work_item còn treo, ghi `event_log` kèm ảnh chụp blockers; nhánh `incomplete` ghi
`visit.status='INCOMPLETE'` (`:521-539`). ✅ Blockers: hàm thuần `build_blockers`
(`checkout_service.py:602-643`) — dịch vụ chưa xong, KQ chưa về, chưa thu tiền dịch vụ, có
đơn thuốc chưa thu, còn đứng ở phòng.

❌ **Nút "Đóng — khách về giữa chừng" chết với lượt sạch vướng mắc.** Nút `disabled` khi
`!reason.trim()` (`CheckoutBoard.tsx:343`), nhưng ô nhập lý do chỉ render khi
`blockers.length > 0` (`:318`) → không blocker thì không có ô để gõ, nút không bao giờ bấm
được, trong khi màn hình vẫn in dòng hướng dẫn cho đúng tình huống ấy (`:351-356`). Cùng
loại ngõ cụt mà `tuong_tac_cskh_service.py:517-521` đã ghi lại bài học một lần.

⚠️ **`reason` không reset khi đổi lượt** — state khai ở `CheckoutBoard.tsx:47`, `setDangChon`
(`:267`) không xoá; lý do gõ cho bà A còn nguyên khi chọn bà B. ⚠️ Cộng thêm: **lượt đang
chọn tự đổi người dưới tay** vì `chon = hienThi.find(dangChon) ?? hienThi[0]` (`:176-177`) —
realtime đẩy danh sách mới hoặc gõ ô tìm kiếm là `chon` lặng lẽ nhảy sang dòng đầu, nút đóng
khi ấy tác động lên bệnh nhân khác kèm lý do cũ.

❌ **Mục ③ là vỏ rỗng.** Backend trả `muc: []` cứng (`checkout_service.py:300-305`),
frontend in câu giải thích (`ChiTietLuot.tsx:276-278`), đầu mục hiện "0/0 hoàn tất" — trung
thực, nhưng vẫn chiếm 1/4 cột giữa.

❌ **`stale_list` là mã mồ côi**, và ⚠️ nhánh `readiness` một lượt cũng vậy.
`checkout_service.py:328-371` + endpoint `/reception/checkout/ton-dong`
(`dispatch.py:299-315`) không có người gọi nào trong `src/dashboard` (grep "ton-dong" = 0),
dù docstring `:329-334` nói 18 lượt tồn "không có chỗ nào để xuất hiện". Còn `route.ts:36-40`
dựng `/reception/checkout/{visit_id}` (`dispatch.py:352-363`) mà mọi lời gọi frontend đều
kèm `chi_tiet=1` (`ChiTietLuot.tsx:153`).

⚠️ **Nhãn "Nghĩa vụ" ở mục Tài chính gây hiểu nhầm.** `ChiTietLuot.tsx:248` in "Nghĩa vụ:"
cho từng dòng `payment`, mà bảng đó chỉ có dòng khi ĐÃ thu; lượt chưa thanh toán hiện "0/0"
+ "Chưa có phiếu thu nào" (`:236-238`) — Tài chính trông sạch trong khi blocker "Chưa thu
tiền dịch vụ khám" đang bật ngay dưới.

### 3. Chồng chéo với màn khác — CÂU QUAN TRỌNG NHẤT

Có hai nút "Checkout". Chúng ghi CÙNG bảng `visit`, nhưng LỆCH ở bảng `appointment`.

**Đường 1 — Lễ tân:** `CheckoutBoard.tsx:124` → `route.ts:57` → `dispatch.py:376` →
`CheckoutService.close`. Ghi `work_item`, `visit` (`closed_at`, `closed_by_staff_id`,
`current_room_id=NULL`), `event_log`. **KHÔNG đụng `appointment.status`** — không UPDATE nào
trong `checkout_service.py`, và không trigger DB nào làm hộ (grep `supabase/migrations`).

**Đường 2 — màn Quản lý khách hàng:** `VungLamViecKhach.tsx:933` `ghiCheckout()` →
`POST /api/cskh/tuong-tac` `loai=CHECK_OUT` → `tuong_tac_cskh_service.py:188-189` →
`_doi_trang_thai_lich` (`:422-425`) → `_checkout_atomically` (`:451-486`): một transaction
gọi **chính `CheckoutService.close`** (`:573-577` qua `_dong_luot_kham` `:488-577`) rồi
`BookingService.apply_action("complete")` (`:481-485`).

Kết luận:

1. **Phần `visit` đã hợp nhất.** Đường CSKH gọi lại đúng service của quầy (lý do chép ở
   `tuong_tac_cskh_service.py:510-513`); trước đó đo được 12/15 lượt lệch (`:504-507`).
2. **Vẫn lệch một chiều, và chiều lệch là chiều của Lễ tân.** Đường CSKH đặt
   `appointment.status='COMPLETED'`, đường Lễ tân thì không. Hậu quả ở hai bảng khác:
   - `/api/v1/queue` lọc `a.status='CHECKED_IN'` và loại visit thuộc `VISIT_DA_RA_VE =
     {INCOMPLETE, FINALIZED, AMENDED}` (`queue.py:63,70`, `queue_order.py:66`). Đóng lượt
     bình thường ở quầy không đặt cả hai → bệnh nhân đã về vẫn nằm trong bảng gọi số.
   - Bảng TV tính `waiting` bằng `status != 'COMPLETED'` AND visit ∉ `VISIT_DA_RA_VE`
     (`display_board_service.py:311-315`) — cùng lỗ hổng: tên người đã về treo trên màn
     phòng chờ cho tới khi bác sĩ ký FINALIZED.
   - `VungLamViecKhach.tsx:1136` `xongTheoLich("DA_CHECKIN")` trả `status === "COMPLETED"`,
     kèm bình luận `:1132-1134` "lễ tân có thể đóng lượt khám từ màn khác, và node ở đây
     phải nói đúng chuyện đó" — với đường Lễ tân thì node không tích.
3. **Lệch ở chốt nghiệp vụ.** Lễ tân còn vướng thì buộc gõ lý do
   (`checkout_service.py:433-438`); đường CSKH luôn qua được vì backend tự dựng
   `ly_do_tu_dong` (`tuong_tac_cskh_service.py:576`) — đường ít thông tin hơn lại ít ma sát hơn.
4. **`incomplete=True` chỉ có ở đường Lễ tân** (`dispatch.py:369-370`); `_dong_luot_kham`
   không truyền tham số đó, nên CSKH không ghi được "khách về giữa chừng".
5. **Bình luận đã cũ và sai:** `VungLamViecKhach.tsx:930-932` khẳng định "ĐIỀU NÀY KHÔNG
   ĐÓNG DÒNG `visit`" — sai kể từ khi `_dong_luot_kham` ra đời.

Chồng chéo khác: `/reception/queue` chạy trên `work_item`, mà đóng lượt huỷ hết work_item
treo (`checkout_service.py:509-520`) nên bảng đó tự sạch — chỉ `/queue` và `/display` không.

### 4. Nghiệp vụ có đủ không — góc quầy

| Tình huống thật | Đáp ứng |
| --- | --- |
| Đóng lượt cho khách khám xong | ✅ đối soát 4 mục rồi bấm một nút |
| Khám xong chưa thanh toán | ⚠️ thấy blocker, đóng được kèm lý do; không thu tiền ở đây (cố ý — `CheckoutBoard.tsx:10-11`), cũng không có nút chuyển sang Thu ngân |
| Khách bỏ về giữa chừng | ❌ backend đủ, nút chết khi lượt sạch vướng mắc (`CheckoutBoard.tsx:318` vs `:343`) — mà "về khi chỉ còn ngồi chờ đọc KQ" là ca hay gặp |
| Hẹn tái khám ngay tại quầy | ❌ không nút, không link. Đối chiếu `ketThucRoiDatLich` (`VungLamViecKhach.tsx:1113-1119`) làm đúng việc "đóng lượt rồi mở form đặt lịch" |
| Lượt tồn từ hôm trước | ❌ `pending_list` chỉ lấy từ nửa đêm hôm nay (`checkout_service.py:144,150`); `stale_list` không nối vào UI |
| In hồ sơ trả khách | ❌ chưa có (mục ③) |

### 5. Đánh giá chuyên môn

Không rườm rà — ngược lại, phần ĐỌC được đầu tư kỹ hơn phần LÀM: cột giữa có 4 mục + dòng
thời gian + hộp kết luận, còn hành động chỉ có 2 nút và 1 trong 2 đang chết. Backend cũng đi
trước UI (`stale_list`, `readiness` viết xong rồi để đó).

1. **Sửa nút "khách về giữa chừng"** — luôn render ô lý do, hoặc mở hộp xin lý do khi bấm.
   Vì sao: tính năng đã viết đủ ở DB + service + router mà người dùng không chạm tới được ở
   đúng ca hay gặp nhất. Công sức: **nhỏ** (`CheckoutBoard.tsx:318-349`).
2. **Xoá `reason` khi đổi lượt và khoá `chon` khi danh sách đổi** — lượt đang chọn rời danh
   sách thì báo "vừa được đóng" thay vì nhảy sang `hienThi[0]`. Vì sao: hai lỗi cộng lại có
   thể ghi lý do của người này vào hồ sơ người kia. Công sức: **nhỏ**
   (`CheckoutBoard.tsx:47,176-177,267`).
3. **Thống nhất hai đường checkout ở `appointment`** — hoặc đường Lễ tân cũng gọi
   `apply_action("complete")`, hoặc `/queue` + `/display` lọc theo `visit.closed_at`. Vì
   sao: đây là nguồn của "người đã về vẫn còn tên trên bảng gọi số", đúng lớp lỗi mà
   `display_board_service.py:306-310` đã dính một lần. Công sức: **vừa**.
4. **Nối `stale_list` vào màn** — thêm tab thứ tư "Tồn từ hôm trước (N)". Vì sao: code đã
   xong, chỉ thiếu 1 tab; mỗi dòng tồn là một bệnh nhân thật không ai chịu trách nhiệm.
   Công sức: **nhỏ**.
5. **Thêm "Đóng lượt & hẹn tái khám"** dùng lại luồng `ketThucRoiDatLich`. Vì sao: khách
   đang đứng ở quầy là lúc đặt lịch dễ nhất. Công sức: **vừa**.

# MÀN B — Số thứ tự gọi khám (`/queue`)

### 1. Thành phần bên trong

Cột "Vai nào thấy" chỉ có một giá trị — xem mục 2. Màn chỉ đọc, không nút nào.

| Thành phần | Làm gì | Vai nào thấy |
| --- | --- | --- |
| Header "Nội bộ / Hàng đợi khám" | Nhãn tĩnh, nhắc đây là bảng có PII — `QueueBoard.tsx:82-95` | không vai nào |
| 3 thẻ số: Đang chờ / Đang khám / Chờ đọc KQ | Đếm client từ `rows` — `QueueBoard.tsx:72-78,97-101` | không vai nào |
| Băng lỗi tải | Hiện khi fetch hỏng — `QueueBoard.tsx:103-107` | không vai nào |
| Cột theo bác sĩ | Gom theo `doctor.full_name`, sort theo tên — `QueueBoard.tsx:64-71,115-140` | không vai nào |
| Làn "Chờ đọc kết quả" (B3) | Tách riêng, nền vàng — `QueueBoard.tsx:142-153` | không vai nào |
| Làn "Đang khám" | `visit_status === IN_PROGRESS` — `QueueBoard.tsx:155-166` | không vai nào |
| Danh sách chờ đánh số 1..n | Số là chỉ số trong cột, KHÔNG phải số vé — `QueueBoard.tsx:168-177,230-234` | không vai nào |
| Dòng bệnh nhân | Tên đầy đủ, "Vé X", giờ hẹn, dịch vụ, chip Có hẹn/Vãng lai/Chờ đọc — `QueueBoard.tsx:216-262` | không vai nào |
| Tự refresh 30s | `setInterval(router.refresh, 30_000)` — `QueueBoard.tsx:58-61` | không vai nào |

### 2. Logic nào chạy thật

❌ **CẢ MÀN KHÔNG AI VÀO ĐƯỢC.** `roles.ts:365` khai `"/queue": []`; `canSeeNav`
(`roles.ts:462-466`) trả `rule.includes(role)` trên mảng rỗng → false cho MỌI vai, kể cả
MANAGEMENT. `page.tsx:15` gọi `requireNavAccess("/queue")` → `clinic-session.ts:26-28`
`redirect("/home")`. Bình luận `roles.ts:362-364` xác nhận tạm ẩn từ 2026-07-03; mục vẫn
còn ở `nav-items.ts:129-135` nhưng bị `hienTrenThanhBen` lọc. Vậy 309 dòng TSX
(`page.tsx` 46 + `QueueBoard.tsx` 263) là mã chết tính đến hôm nay.

Bỏ qua cổng đóng thì bên trong ✅ chạy thật: `page.tsx:32-40` gọi `GET /api/v1/queue?date=`
bằng token của chính người dùng → `queue.py:81-146` → `entry_from_row` (`queue_rows.py:26`)
+ `explain_queue` (`queue_order.py:204-234`), lọc người đã ra về ở SQL (`queue.py:70`), tính
B3 từ `lab_result` (`:99-100`). Xếp hạng ở backend, frontend chỉ gom nhóm (`QueueBoard.tsx:116-118`).

⚠️ **Backend tính lý do, frontend vứt đi.** `queue.py:138-142` trả `call_order`,
`call_tier`, `call_reason`, `promoted`, `promoted_over`; interface `QueueRow`
(`QueueBoard.tsx:13-25`) không khai trường nào và không render chỗ nào — đúng thứ
`queue_order.py:49-50` nói là để "màn hình NÓI ĐƯỢC, không chỉ xếp được"; chỉ bảng TV dùng.
⚠️ **Tự refresh 30s bằng `router.refresh()`** trong khi màn check-out cạnh đó đã chuyển
sang realtime và ghi hẳn lý do vì sao poll là sai (`CheckoutBoard.tsx:66-83`).

⚠️ **Bài kiểm e2e là bài kiểm rỗng:** `e2e/intake-day-simulation.mjs:218-224` chỉ khẳng
định "status < 500 và không redirect /login" — redirect `/home` vẫn PASS, nên nó xanh suốt
thời gian màn bị khoá. Tương tự `feature-mode-client.ts:18`: luật ẩn cho mục đã ẩn với tất cả.

### 3. Chồng chéo với màn khác

| Bảng | Nguồn | Còn sống? |
| --- | --- | --- |
| `/queue` | `/api/v1/queue` → `explain_queue` | ❌ khoá bằng `roles.ts:365` |
| `/display` (TV phòng chờ) | `display.py:67` → `display_board_service.py`, cùng `explain_queue` | ✅ vai `DISPLAY` riêng, `layout.tsx:33` đẩy thẳng vào |
| `/reception/queue` | workflow kernel / `work_item` | ✅ `roles.ts:263-265` |
| `/doctor/board`, `/tasks` | `doctor_board_service.py` (cũng dùng `QueueDecision`) | ✅ |

Nặng nhất là `/queue` với `/display`: cùng luật xếp, cùng dữ liệu, khác ở chỗ `/display`
che tên và không gửi PII khác (`display_board_service.py:5-17`) — tức `/queue` = `/display`
cộng tên đầy đủ, mã vé, tên bác sĩ. `/api/v1/queue` hiện chỉ còn đúng một người gọi là màn
đã khoá, nên cả endpoint lẫn màn đều đang chờ một quyết định.

### 4. Nghiệp vụ có đủ không — nó phục vụ ai?

Nội dung tự trả lời: hiển thị tên đầy đủ, mã vé, tên bác sĩ, tên dịch vụ, và tự nhận "chỉ
dành cho nhân sự đã được cấp quyền" (`QueueBoard.tsx:90-92`). **Đây là bảng NỘI BỘ, không
phải TV phòng chờ** — treo lên tường là công khai tên + dịch vụ ở một phòng khám phụ khoa/
hiếm muộn, đúng thứ `display_board_service.py:8-17` dựng `hien_ten`/`che_ten` để tránh.

Lễ tân có cần nó trên thanh bên không: **không, ở dạng hiện tại.** Thứ tự gọi đã có ở
`/reception/queue` và `/display`; màn này không có nút nào ("gọi", "gọi lại", "vắng mặt")
nên nhìn xong vẫn phải làm ở màn khác; và nó gom cột theo bác sĩ — cách nhìn của điều phối,
không phải của quầy. Nếu mở lại thì thiếu: nút "Gọi" ghi mốc, đồng hồ đếm thời gian chờ, và
`call_reason` để trả lời được "sao chị kia đến sau mà vào trước".

### 5. Đánh giá chuyên môn

Quá mỏng, và ở trạng thái tệ nhất: mã còn nguyên, endpoint còn chạy, e2e còn xanh — nhưng không ai chạm tới được.

1. **Quyết dứt điểm: xoá hoặc mở lại.** Xoá thì gỡ `page.tsx`, `QueueBoard.tsx`,
   `nav-items.ts:129-135`, `roles.ts:361-365`, `feature-mode-client.ts:18`, bước e2e
   `:218-224`, và cân nhắc cả `queue.py` vì hết người gọi. Vì sao: một màn khoá nhiều tuần
   mà mọi thứ xung quanh vẫn giả vờ nó tồn tại là bẫy. Công sức: **nhỏ** (xoá) / **vừa** (mở).
2. **Nếu mở lại: render `call_reason` + `promoted`** — backend đã trả sẵn
   (`queue.py:138-142`), chỉ thiếu 5 trường trong interface. Vì sao: đó là lý do duy nhất
   khiến bảng nội bộ hơn được bảng TV. Công sức: **nhỏ**.
3. **Sửa e2e để phân biệt "tải được" với "bị đá về /home"**
   (`intake-day-simulation.mjs:220`). Vì sao: bài kiểm xanh trên màn không vào được làm
   hỏng niềm tin vào cả bộ. Công sức: **nhỏ**.
4. **Nếu mở lại: đổi 30s-poll sang realtime** như `CheckoutBoard.tsx:84-113`. Vì sao: cùng
   người dùng, cùng quầy, không nên hai luật làm mới. Công sức: **nhỏ**.
5. **Đừng bày `/queue` cho lễ tân trước khi có nút hành động.** Vì sao: thêm một mục
   chỉ-để-nhìn vào thanh bên vốn đã dài làm loãng những màn họ phải bấm. Công sức: **nhỏ**.

*Chưa rõ — cần kiểm:* (a) có nơi nào treo TV chạy `/queue` bằng tài khoản MANAGEMENT từ
trước 2026-07-03 không; (b) tỉ lệ hai đường checkout trên prod — đếm `event_log` theo `source`.


---

## 3. Danh sách bệnh nhân & Tạo bệnh nhân

> Gốc mã nguồn đọc kiểm: `/private/tmp/claude-501/-Users-quangdang-Projects-Dr4Women-MacMini--claude-worktrees-learning-knowledge-synthesis-0fdca7/491e9f6d-49ba-4a7c-bbc1-fff67ca56b22/scratchpad/fix-gach-ngang`
> Mọi `tệp:dòng` bên dưới tính từ gốc đó. Chỉ đọc, không sửa gì.

---

# A. Màn "Danh sách bệnh nhân" — `/patient-list`

## 1. Thành phần bên trong

| Thành phần | Làm gì | Vai nào thấy |
|---|---|---|
| 5 thẻ số tổng quan: Tổng hồ sơ / Có lượt đang mở / Khám lần đầu / Tái khám / Chưa khám lần nào | Đếm trên chính mảng `rows` đã dựng ở server (`patient-list/page.tsx:211-228`) | Mọi vai vào được màn |
| Ô tìm "Tìm tên, mã BN hoặc SĐT" | Lọc **tại máy khách**, bỏ dấu bằng `unaccentVi` (`PatientListView.tsx:200-213`) | Mọi vai |
| 4 nút lọc: Tất cả / Khám lần đầu / Tái khám / Chưa khám (kèm số đếm) | Lọc cục bộ theo `phan_loai` (`PatientListView.tsx:230-235`) | Mọi vai |
| Nhãn "Lọc cục bộ" | Chữ tĩnh, không bấm được (`PatientListView.tsx:284-286`) | Mọi vai |
| Cột trái — mỗi dòng BN: chữ cái tắt, Họ tên, chip phân loại, mã BN, SĐT chính, "N lượt · ngày gần nhất" | Chọn hồ sơ để đổ sang hai cột phải (`PatientListView.tsx:296-335`) | Mọi vai |
| Chân cột trái "Hiển thị X trên Y hồ sơ" | Đếm sau lọc (`PatientListView.tsx:337-339`) | Mọi vai |
| Cột giữa — đầu phiếu: tên, mã BN, chip phân loại, ngày sinh, giới tính, số lượt | (`PatientListView.tsx:350-368`) | Mọi vai |
| Cột giữa — khối "Hành chính": Ngày sinh, Giới tính, Dân tộc, Quốc tịch, Nghề nghiệp, Đối tượng, Người giám hộ | Chỉ đọc; thiếu thì in "Chưa có" (`PatientListView.tsx:378-391`) | Mọi vai |
| Cột giữa — khối "Liên hệ & địa chỉ": Điện thoại, Điện thoại (thêm), Điện thoại phụ, Người nhà (thêm), Địa chỉ, dòng "Lần gần nhất" | Số thêm lấy từ `patient_sdt_them` (`PatientListView.tsx:392-417`) | Mọi vai |
| Cột giữa — khối "Lượt khám gần nhất": Thời gian, Dịch vụ, Số thứ tự, Kênh, chip trạng thái | Chưa khám thì thay bằng một câu nhắc (`PatientListView.tsx:419-439`) | Mọi vai |
| Nút "Mở phiếu khám" | Mở `ClinicalRecordForm` chế độ chỉ-đọc trong khung chia đôi | **CHỈ vai lâm sàng** (`canReadClinical` = BS/ĐD/TKYK) — `page.tsx:58,451` |
| Cột phải "Thông tin lượt khám": Thời gian hẹn, Dịch vụ, Loại hồ sơ, Trạng thái lịch | Lặp lại dữ liệu cột giữa (`PatientListView.tsx:504-513`) | Mọi vai |
| Nút "Các lượt khám (N)" | Bung danh sách từng lượt: Lần k, trạng thái, ngày, dịch vụ (`PatientListView.tsx:486-539`) | Mọi vai |
| Thanh kéo chia đôi khung (SplitPane) | Chỉ tồn tại khi đã mở phiếu khám (`PatientListView.tsx:547-573`) | Vai lâm sàng |

Vai vào được màn: RECEPTION, MANAGEMENT, CSKH, CASHIER×3, TKYK, NURSE_ULTRASOUND, DOCTOR, ULTRASOUND_DOCTOR (`lib/roles.ts:332`).
⚠️ **TRUONG_CA không có trong danh sách** (`lib/roles.ts:332`) → gõ URL bị `requireNavAccess` đá về `/home` (`lib/clinic-session.ts:26-29`), dù ghi chú ngay trên dòng ấy nói màn này dành cho "CSKH/Lễ tân/QL + BÁC SĨ".

## 2. Logic nào chạy thật

- ✅ Nguồn danh sách: `patient` (5000 dòng) + `appointment` (2000 dòng) đọc thẳng Supabase bằng phiên người dùng, ghép ở server (`page.tsx:74-97`). Hồ sơ chưa khám vẫn hiện với 0 lượt.
- ✅ Phân loại Chưa khám / Khám lần đầu / Tái khám tính từ `visit_count` (`page.tsx:190-201`).
- ✅ Danh sách "Các lượt khám" là dữ liệu thật, dựng từ từng dòng `appointment` (`page.tsx:152-157`).
- ✅ Số điện thoại thêm (`patient_sdt_them`) hiện đúng theo loại CHINH / NGUOI_NHA (`PatientListView.tsx:398-408`).
- ✅ Nút "Mở phiếu khám" → `ClinicalRecordForm` chỉ-đọc; route `/api/clinical-record` chặn độc lập (ghi chú `page.tsx:10-12`).
- ⚠️ **Ô tìm không tìm được số điện thoại thêm.** Màn tải `patient_sdt_them` về và **hiện** nó, nhưng phép lọc chỉ so `full_name`, `patient_code`, `phone_primary` (`PatientListView.tsx:208-211`). Khách cũ đọc số thứ hai — đúng số vừa được gắn ở màn tạo BN — tra ở đây ra rỗng.
- ⚠️ **Không tìm được bằng CCCD.** Không màn nào của lễ tân đọc `national_id_number`; `patients/[id]/page.tsx:4` nói rõ là cố ý loại bỏ.
- ⚠️ **Ngày sinh in thô dạng ISO.** `page.tsx:364` ghép thẳng `Ngày sinh ${selected.date_of_birth}` và `PatientListView.tsx:383` cũng vậy → hiện "1990-01-01". Truy vấn không lấy `birth_year` (`page.tsx:77-81`) nên khách "chỉ nhớ năm" hiện thành một ngày sinh cụ thể trông như thật. Màn `/customers` cùng dữ liệu thì in "1990 (chỉ năm)" (`customers/CustomersView.tsx:2182`).
- ⚠️ **Trần cứng, cắt im lặng.** `.limit(5000)` hồ sơ và `.limit(2000)` lượt khám (`page.tsx:83,92`) — vượt thì mất dòng mà không có cảnh báo nào trên màn.
- ⚠️ **Lọc + tìm chạy hết ở máy khách** trên toàn bộ 5000 dòng đã tải về — không phân trang, không tìm phía máy chủ (`PatientListView.tsx:200-213`).
- ⚠️ `visit_count` chỉ đếm lượt `COMPLETED` + lượt `CHECKED_IN/IN_PROGRESS` **của hôm nay** (`page.tsx:88-90`). Lượt bỏ dở của hôm qua biến mất khỏi số đếm, khách hiện lại thành "Chưa khám".
- ❌ **Ba props chết với vai vận hành**: `showRebook`, `showPreVisitBrief`, `enableVisitPager` chỉ có tác dụng bên trong phiếu khám, mà phiếu khám chỉ mở được khi `enablePopup` = true. Với Lễ tân `enablePopup` = false (`page.tsx:58,61,243-246`) → nút "Tái khám" và hàm `datLichLai` (`PatientListView.tsx:195-198`) **không bao giờ chạy được** cho lễ tân.
- ❌ **Không có đường tạo bệnh nhân từ màn này.** `PatientListView.tsx` không nhập `Link`; không nút "Thêm hồ sơ" nào. Trớ trêu là màn tạo BN lại lấy `/patient-list` làm nút "Huỷ" (`patients/new/NewPatientForm.tsx:1712`) và làm nơi hạ cánh sau khi tạo xong (`NewPatientForm.tsx:802-805`) — một chiều đi, không có chiều về.
- ❌ Không có làm tươi thời gian thực: màn `force-dynamic` nhưng không gắn `RealtimeRefresher`. Khách do máy khác vừa tạo chỉ hiện sau khi F5.

## 3. Chồng chéo với `/customers`

Cả hai đều là master–detail trên **cùng bảng `patient`**, và có bốn thứ trùng nhau gần như từng chữ:

| | `/patient-list` | `/customers` |
|---|---|---|
| Nguồn | `patient` + `appointment`, `.limit(5000)` (`page.tsx:74-92`) | `patient` `.limit(300)` (`customers/page.tsx:186`) |
| Tìm | tại máy khách: tên / mã / SĐT chính (`PatientListView.tsx:208`) | tại máy chủ: tên, tên-không-dấu, mã, **`sdt_tim_kiem`** = gộp mọi số (`customers/page.tsx:198-206`) |
| Cột danh sách | Tên · mã · SĐT · N lượt · ngày | Khách hàng · Trạng thái · Mới/cũ · Tương tác gần nhất · Bước tiếp theo · Hạn xử lý · Người xử lý (`CustomersView.tsx:607-619`) |
| Khối hành chính | **chỉ đọc** (`PatientListView.tsx:378-417`) | **sửa được** qua `PatientAdminEditor` (`PatientAdminEditor.tsx:331-365`) |
| Lịch hẹn | chỉ xem lượt gần nhất | xem + **đổi/huỷ** lịch (`canManageAppt`) |
| Nút tạo BN | không có | có — "Thêm khách hàng mới" (`CustomersView.tsx:1368-1378`) |
| Việc CSKH (chuỗi bước, tương tác, phản hồi, tệp kết quả, nhắc tái khám) | không có | có |
| Bộ lọc kỳ | không có | Hôm nay / Tuần / Tháng / Tất cả × theo ngày tạo hoặc ngày hẹn (`customers/page.tsx:137-142`) |

**Cái nào làm được nhiều hơn:** `/customers` — nó bao trùm toàn bộ chức năng của `/patient-list` **trừ ba thứ**: (a) danh sách "Các lượt khám" của một BN, (b) bộ đếm lần đầu/tái khám, (c) nút "Mở phiếu khám" (vốn không dành cho lễ tân). Đổi lại, `/customers` chỉ tải 300 hồ sơ nên **không dùng được như một danh bạ toàn phòng khám**, còn `/patient-list` tải 5000.

**Lễ tân có cần cả hai không:** không, ở dạng hiện tại. Với lễ tân, `/patient-list` là bản `/customers` bị gỡ mất mọi nút bấm: không sửa được hồ sơ, không đặt lại lịch, không tạo BN, không mở phiếu khám. Thứ duy nhất nó hơn là **tra cứu rộng** (5000 vs 300) và **lịch sử lượt khám**. Hai điều ấy có thể đưa vào `/customers` mà không cần một màn thứ hai.

**Đường tạo bệnh nhân KHÁC ngoài `/patients/new`:** có đúng một — `BookingHub` ở màn Đặt lịch nhúng chính `NewPatientForm` khi `mode === "new_patient"` (`appointments/BookingHub.tsx:1744-1753`). Nhưng lối ấy **không dành cho lễ tân**: `/appointments` chỉ mở cho CSKH + MANAGEMENT (`lib/roles.ts:303`). Ngoài ra không có "tạo nhanh" ở màn check-in / hàng đợi nào: chỉ có hai chỗ POST `/api/patients` để TẠO (`NewPatientForm.tsx:947`, và `BookingHub` dùng lại chính nó); `tasks/ConfirmBoard.tsx:249` và `PatientAdminEditor.tsx:149` là PATCH — sửa, không tạo.

## 4. Nghiệp vụ có đủ không — góc quầy lễ tân

| Tình huống ở quầy | Màn này đáp ứng | Thiếu |
|---|---|---|
| Khách mới chưa từng khám | ✅ hiện ngay sau khi tạo, nhóm "Chưa khám" (`page.tsx:99-124`) | ❌ không có nút tạo tại chỗ — phải sang mục khác ở thanh bên |
| Khách cũ quên mã | ✅ gõ tên không dấu hoặc SĐT chính là ra | ⚠️ hai người trùng tên chỉ phân biệt được bằng ngày sinh in thô ISO và SĐT |
| Khách đưa CCCD | ❌ không tra được bằng CCCD, cũng không hiện CCCD để đối chiếu | Cần ít nhất một chỗ đối chiếu 4 số cuối |
| Trẻ em / người nhà đứng tên | ⚠️ có dòng "Người giám hộ" và "Người nhà (thêm)" để ĐỌC (`PatientListView.tsx:389,404-408`) | ❌ không nhập/sửa được từ đây; và `guardian_name` **không có ô nào ở màn tạo BN** (xem B§2) |
| Khách không nhớ số điện thoại | ⚠️ tra bằng tên được, nhưng nếu khách khai một số khác đã gắn thêm thì tìm không ra (`PatientListView.tsx:208-211`) | Ô tìm phải soi cả `patient_sdt_them` như `/customers` đã làm |
| Khách hỏi "lần trước tôi khám ngày nào" | ✅ nút "Các lượt khám (N)" trả lời đúng (`PatientListView.tsx:519-539`) | — |
| Khách muốn đặt lại lịch ngay | ❌ với lễ tân không có nút nào — hàm `datLichLai` nằm sau cửa phiếu khám mà lễ tân không mở được | — |

## 5. Đánh giá chuyên môn

Màn này **quá mỏng cho lễ tân và trùng chỗ với `/customers`**: ba cột, mười mấy khối chữ, nhưng với vai lễ tân chỉ có đúng hai thao tác thật (gõ tìm, bấm chọn). Cột phải là bản lặp lại của cột giữa (Thời gian hẹn / Dịch vụ / Trạng thái đã in ở khối "Lượt khám gần nhất" ngay trên). Ngược lại, nó là màn duy nhất tra được toàn bộ 5000 hồ sơ.

1. **Cho ô tìm soi cả `patient_sdt_them` (và cho tìm theo 4 số cuối CCCD nếu chấp nhận).** Vì sao: cả một đường "thêm số cho khách này" đã dựng xong ở màn tạo BN, mà màn tra cứu lại không thấy số ấy — nửa tính năng. Công sức: **nhỏ** (một biểu thức lọc, dữ liệu đã có trong `rows`).
2. **In ngày sinh qua `fmtDate` và lấy thêm `birth_year`.** Vì sao: "1990-01-01" trông như một ngày sinh có thật; lễ tân đối chiếu với CCCD của khách sẽ kết luận sai người. Công sức: **nhỏ** (thêm 1 cột vào `SELECT` ở `page.tsx:77-81` + đổi 2 chỗ in).
3. **Gộp cột phải vào cột giữa và thêm nút "Tạo hồ sơ mới" ở đầu danh sách.** Vì sao: bỏ một cột lặp, và trả lại chiều về cho đúng màn mà `NewPatientForm` đang lấy làm nơi hạ cánh. Công sức: **nhỏ–vừa**.
4. **Quyết một trong hai: hoặc đưa 5000-hồ-sơ + lịch sử lượt khám vào `/customers` rồi bỏ `/patient-list` khỏi thanh bên lễ tân, hoặc cho `/patient-list` quyền sửa hồ sơ + đặt lại lịch.** Vì sao: hiện lễ tân phải nhớ "tra thì vào màn này, làm thì vào màn kia" — và ranh giới ấy không viết ở đâu trên giao diện. Công sức: **lớn**.
5. **Thêm TRUONG_CA vào `/patient-list` hoặc sửa lại ghi chú.** Vì sao: `lib/roles.ts:332` và chính ghi chú ngay trên nó đang nói hai điều khác nhau; trưởng ca làm thay lễ tân lúc cao điểm thì bị đá về `/home` không lời giải thích. Công sức: **nhỏ**.

---

# B. Màn "Tạo bệnh nhân" — `/patients/new`

**Lưu ý quyết định luồng:** với vai RECEPTION, `forcedWalkin = true` (`patients/new/NewPatientForm.tsx:307-311` và `patients/new/page.tsx:37-39`) → lễ tân **luôn** ở luồng **walk-in**; toàn bộ khối "Lịch hẹn khám" (Kênh đặt, sơ đồ khung giờ ngày khác, ngày khám) **không hiện** cho lễ tân (`NewPatientForm.tsx:1494`).

## 1. Thành phần bên trong

| Thành phần | Làm gì | Vai nào thấy |
|---|---|---|
| Hai nút chuyển luồng "Nhập thông tin khách hàng mới" / "Tạo bệnh nhân mới" | Đổi `?mode=walkin` | **CHỈ** TRUONG_CA + MANAGEMENT (`page.tsx:36,79`) |
| Thanh 3 bước (Thông tin hồ sơ → Lịch hẹn → Xác nhận) | Trang trí, không bấm được | Ẩn ở `/patients/new` vì `nhung` = true (`page.tsx:118`); chỉ hiện khi form đứng độc lập |
| Băng "Có bản nhập dở … Khôi phục / Bỏ nháp" | Đổ lại 17 trường hành chính từ localStorage (`NewPatientForm.tsx:1027-1047,762-784`) | Mọi vai vào được, **nếu** có `staffId` |
| Họ tên * | Tự viết hoa đầu từ khi rời ô (`:1060-1066`) | Mọi vai |
| Ngày sinh * + tick "Chỉ biết năm" → ô Năm sinh | (`:1068-1118`) | Mọi vai |
| SĐT chính * + hai ô cảnh báo trùng (vàng = trùng mạnh, xám = trùng tên) + nút "＋ Thêm số điện thoại cho khách này" + ô nhập số + hai nút "Số của khách"/"Số người nhà" + nút "Lưu số"/"Thôi" | (`:1119-1208`, `:112-222`) | Mọi vai |
| SĐT người nhà | (`:1209-1222`) | Mọi vai |
| CCCD | (`:1223-1236`) | Mọi vai |
| Cơ sở đăng ký khám * | (`:1237-1252`) | Mọi vai |
| Giới tính * (Nữ/Nam/Khác) | (`:1253-1267`) | Mọi vai |
| Dân tộc (mặc định "Kinh") | (`:1268-1275`) | Mọi vai |
| Quốc tịch (mặc định "Việt Nam") | (`:1276-1283`) | Mọi vai |
| Nghề nghiệp | (`:1284-1291`) | Mọi vai |
| Đối tượng | (`:1292-1300`) | Mọi vai |
| Tỉnh/Thành phố * | Combobox 34 tỉnh (`:1301-1312`) | Mọi vai |
| Phường/Xã * | Nạp runtime theo tỉnh qua `/api/wards` (`:1313-1331`) | Mọi vai |
| Địa chỉ chi tiết | (`:1332-1340`) | Mọi vai |
| Vấn đề khiến bệnh nhân đi khám | (`:1342-1350`) | Mọi vai |
| Dịch vụ khám (5 lĩnh vực PK/SK/NT/HMVS/NK) | (`:1355-1374` walk-in, `:1502-1523` full) | Mọi vai |
| Bác sĩ (ô gõ tìm) | Chỉ mời bác sĩ **có trực ngày đó** (`:471-485`) | **Chỉ luồng walk-in** |
| "Có siêu âm" (checkbox) | (`:1431-1448` / `:1591-1608`) | Mọi vai |
| Sơ đồ chỗ "Xếp chỗ vãng lai (ô xanh)" | `CinemaSlotPicker mode="walkin"` (`:1453-1488`) | **Chỉ walk-in** |
| Ngày khám * / Sơ đồ "Bác sĩ & khung giờ" / Giờ * / Kênh đặt * | (`:1533-1636`) | **Chỉ luồng full** — lễ tân không thấy |
| Hộp trùng SĐT sau khi bấm Lưu + nút "Dùng bệnh nhân này" + "Vẫn tạo bệnh nhân mới" | (`:1642-1683`) | Mọi vai |
| Nút Lưu (nhãn đổi theo vai/luồng) + "Huỷ" → `/patient-list` | (`:1691-1716`) | Mọi vai |

Vai vào được: page tự gác bằng `canWriteIntake` = CSKH/RECEPTION/MANAGEMENT/TRUONG_CA (`page.tsx:30-31`). ⚠️ `NAV_ROLES["/patients/new"]` chỉ liệt RECEPTION + MANAGEMENT (`lib/roles.ts:337`) → CSKH và TRUONG_CA vào được bằng URL nhưng **không thấy mục trên thanh bên**; hàm đổi nhãn nav riêng cho CSKH (`nav-items.ts:292-294`) vì thế không bao giờ chạy — mã chết.

## 2. Logic nào chạy thật

**Số trường:** luồng **full** = **21 ô nhập** (15 hành chính + 6 lịch hẹn); luồng **walk-in (lễ tân)** = **19 ô** (15 hành chính + Dịch vụ + Bác sĩ + Có siêu âm + sơ đồ chỗ). Ghi xuống database là **22 cột** (`patient_service.py:44-67`).

**Bắt buộc (lễ tân, walk-in):** Họ tên, Ngày sinh **hoặc** Năm sinh, SĐT chính, Giới tính, Cơ sở, Tỉnh/TP, Phường/Xã — 7 mục (`NewPatientForm.tsx:846-894`). Luồng full bắt thêm Dịch vụ + Ngày + Giờ + Kênh đặt (`:897-923`). **Bác sĩ KHÔNG bắt buộc** ở cả hai luồng (`:902-910`) dù nhãn có in dấu `*` (`:1546`) — nhãn nói dối, nhẹ.

- ✅ Lưu hồ sơ: nút → `POST /api/patients` (`:947`) → BFF kiểm định dạng tiếng Việt rồi **chuyển tiếp bắt buộc** xuống FastAPI, thiếu `CLINIC_API_URL` thì 503 chứ không tự ghi (`api/patients/route.ts:122-127`) → `PatientService.create_patient` (`patient_service.py:99-223`): kiểm cơ sở còn hoạt động → chặn cứng CCCD trùng (409, `force` không phá được) → chặn mềm SĐT trùng → INSERT + ghi `event_log` **trong cùng một giao dịch**.
- ✅ Dò trùng lúc gõ: `GET /api/patients/check-duplicate` (`:644`) → BFF (`check-duplicate/route.ts:41-44`) → FastAPI gọi **đúng hàm mà đường lưu gọi** `MPIService.find_candidates` (`api/v1/patients.py:143`), cộng nhánh "trùng tên đơn thuần" riêng (`api/v1/patients.py:158-186`). Ba nhánh khớp: SĐT (kể cả số thêm), CCCD, họ-tên + năm sinh (`mpi_service.py:98-149`).
- ✅ Nút "＋ Thêm số điện thoại cho khách này": `POST /api/patients/sdt-them` (`:133`) → `patient_service.them_so_dien_thoai` (`patient_service.py:511-600`) — chuẩn hoá số, chặn trùng trong chính hồ sơ, ghi `event_log` chỉ 4 số cuối.
- ✅ Sơ đồ chỗ đọc ca trực thật: `/api/roster?date=` (`:445`) + `/api/appointments?date=` (`:501,526`) + luật sức chứa `useBookingPolicy` (`:429-431`, `:549-575`).
- ✅ Walk-in vào thẳng trạng thái đã check-in: quyết ở backend `booking_service.py:462` (`auto_checkin = kênh WALK_IN và là hôm nay`), không phải ở giao diện.
- ✅ Bản nhập dở: ghi localStorage sau mỗi 1 giây ngừng gõ, khoá theo `staffId`, hạn 24 giờ (`:736-760`, `lib/luu-nhap.ts:38-45`).
- ⚠️ **Nháp không chạy khi form nhúng ở màn Đặt lịch**: `BookingHub` không truyền `staffId` (`appointments/BookingHub.tsx:1744-1753`) → `khoaNhap` trả `null` (`lib/luu-nhap.ts:43`) → im lặng không lưu gì. Cùng một biểu mẫu, hai hành vi.
- ⚠️ **`BookingHub` đóng cứng `role="CSKH"`** (`BookingHub.tsx:1745`) → quản lý dùng lối ấy sẽ bị đưa về `/customers` sau khi lưu chứ không phải nơi vai họ đáng tới (`NewPatientForm.tsx:802-814`).
- ⚠️ **Luồng walk-in bỏ qua `?date` hoàn toàn**: giờ bắt đầu luôn tính trên `TODAY` (`:699-703`), dù state `apptDate` đã nhận ngày từ URL (`:415`). Hiện an toàn chỉ vì bên gọi tự chặn — ô xanh chỉ tạo link khi là hôm nay (`home/WeeklyAppointmentsTable.tsx:229-236`). Một bên gọi khác quên luật ấy là đặt nhầm ngày mà không có gì báo.
- ⚠️ **`/api/patients/check-phone` là route chết**: không nơi nào trong `src/dashboard` gọi nó nữa (đã grep) — 72 dòng + một bản sao luật dò trùng vẫn nằm đó chờ ai đó dùng nhầm.
- ⚠️ Cảnh báo trùng im lặng khi backend không với tới: `fetchFromBackend` trả `null` → BFF trả `{exists:false}` (`check-duplicate/route.ts:41-44`, `lib/backend-proxy.ts:210-216`). Guard lúc lưu vẫn chạy nên không lọt hồ sơ, nhưng người trực đọc được câu "không trùng" mà thật ra là "chưa kiểm được".
- ❌ **`gheTrucTiep` là hằng `false`** (`:427`) — mọi nhánh `walkin || gheTrucTiep` và `!gheTrucTiep && <Req/>` (`:560,717,919,1622`) chỉ còn một vế sống.
- ❌ **`patientKind` khai bằng `useState` không có setter** (`:490`) — luôn `"NEW"`.
- ❌ **Số khám ở luồng full luôn bị xoá** bởi một effect (`:580-584`) → `queue_number` gửi đi luôn rỗng ở luồng ấy.
- ❌ **Nhánh điều dưỡng là mã chết**: `isNurseRole` được tính ở `page.tsx:32` sau khi `canWriteIntake` đã loại NURSE_ULTRASOUND ở dòng 31 (`lib/roles.ts:125-132`) → `nurse` luôn `false`; ghi chú "Điều dưỡng walk-in giữ TUỲ CHỌN [địa chỉ]" (`NewPatientForm.tsx:306`) mô tả một trường hợp không tồn tại.
- ❌ **Không có ô "Người giám hộ"** trên biểu mẫu, dù cột `guardian_name` tồn tại, được API nhận (`api/patients/route.ts:50`) và được **hiển thị** ở `/patient-list` (`PatientListView.tsx:389`) và phiếu in (`print/[appointmentId]/page.tsx:244`). Chỉ nhập được **sau** khi tạo, qua `PatientAdminEditor.tsx:364`.

**Trường ghi xuống database rồi không màn nào đọc lại** (đã grep toàn repo, loại `node_modules`/`.next`):

| Cột | Ghi ở | Ai đọc |
|---|---|---|
| `province_code` | `NewPatientForm.tsx:964` → `patient_service.py:60` | **không màn nào** (chỉ có `ward.province_code` ở `/api/wards`) |
| `province_name` | `:965` → `patient_service.py:61` | **không màn nào** |
| `ward_code` | `:966` → `patient_service.py:62` | **không màn nào** |
| `ward_name` | `:967` → `patient_service.py:63` | **không màn nào** |
| `address_detail` | `:968` → `patient_service.py:64` | **không màn nào** |
| `national_id_number` (CCCD) | `:956` | **không màn nào cho người đọc** — `patients/[id]/page.tsx:4` cố ý loại; chỉ máy dùng để chặn 409 |

Năm cột địa chỉ có cấu trúc bị "ghi rồi bỏ" vì giao diện chỉ đọc lại chuỗi `address` đã ghép sẵn (`:944-946`). Các cột còn lại đều có nơi đọc: `van_de_di_kham`/`linh_vuc` (`PatientAdminEditor.tsx:248-252`), `ethnicity`/`nationality`/`occupation`/`patient_objection`/`guardian_name` (`PatientAdminEditor.tsx:199-246`, `print/[appointmentId]/page.tsx:239-244`), `birth_year` (`customers/page.tsx:107`, `patients/[id]/PatientDetail.tsx:70`).

## 3. Chồng chéo

- **Cùng một biểu mẫu, ba lối vào:** `/patients/new` (lễ tân, walk-in), `/patients/new?mode=walkin` (trưởng ca/quản lý), và `/appointments` → BookingHub `mode="new_patient"` (CSKH/quản lý, `BookingHub.tsx:1744`). Với **lễ tân** thì chỉ có lối thứ nhất, vì `/appointments` không mở cho vai này (`lib/roles.ts:303`).
- **Nút "Thêm khách hàng mới"** ở `/customers` (`CustomersView.tsx:1368-1378`) không phải lối thứ tư — nó trỏ về đúng `/patients/new` (không kèm `?date`), có gác `canEdit` = `canWriteIntake` nên khớp cửa trang.
- **Không có "tạo nhanh" ở màn check-in / hàng đợi.** Khách lạ đến quầy phải đi trọn 19 ô của biểu mẫu này rồi mới có lượt khám.
- **`/patients/new` và `/customers` cùng ghi một tập trường hành chính** — một bên qua `POST /api/patients`, một bên qua `PATCH /api/patients` → `PatientAdminEditor`. Danh sách trường lệch nhau: `PatientAdminEditor` có "Người giám hộ", biểu mẫu tạo mới thì không; biểu mẫu tạo mới có Tỉnh/Phường/Địa chỉ chi tiết, `PatientAdminEditor` chỉ có một ô "Địa chỉ" tự do (`PatientAdminEditor.tsx:31-68`).

## 4. Nghiệp vụ có đủ không — góc quầy lễ tân

| Tình huống ở quầy | Đáp ứng | Thiếu |
|---|---|---|
| Khách mới chưa từng khám | ✅ 7 mục bắt buộc, xong là có lượt khám hôm nay nếu chọn dịch vụ (`:668-670`, `booking_service.py:462`) | ⚠️ Tỉnh + Phường bắt buộc với lễ tân (`:307-311`) — khách không nhớ phường thì **không lưu được hồ sơ** |
| Khách cũ quên mã | ✅ gõ tên ≥ 3 ký tự là hiện ngay hồ sơ trùng tên, kèm mã BN + năm sinh (`:619-624`, `api/v1/patients.py:158-186`) | — |
| Khách đưa CCCD | ⚠️ nhập được, và trùng thì chặn cứng có tên hồ sơ cũ (`patient_service.py:143-156`) | ❌ **không tra ngược được**: không có ô "tìm theo CCCD" ở bất kỳ màn nào; và CCCD đã nhập rồi thì không màn nào cho xem lại để đối chiếu |
| Trẻ em / người nhà đứng tên | ⚠️ có "SĐT người nhà", có nút gắn số loại "NGUOI_NHA" | ❌ **không có ô "Người giám hộ"** ở màn tạo (chỉ nhập được sau, ở màn khác); không có quan hệ mẹ–con giữa hai hồ sơ; Giới tính bắt buộc nhưng không có ô tuổi/nhóm trẻ em |
| Khách không nhớ số điện thoại | ❌ **SĐT chính là bắt buộc** (`:850-853`) và phải đủ 10 số đúng đầu số (`lib/validation.ts` `PHONE_RE`, `api/patients/route.ts:103-108`) — không có lối "chưa có số" | Cần cho phép để trống, hoặc một ô ghi chú "khách không cung cấp" |
| Khách cũ gọi từ số mới | ✅ đúng ca này đã có lối đi thứ ba: cảnh báo → "＋ Thêm số điện thoại cho khách này" → gắn vào hồ sơ cũ (`:112-222`, `patient_service.py:511-600`) | ⚠️ nhưng số vừa gắn lại **không tra được ở `/patient-list`** (xem A§2) |
| Khách chỉ hỏi, chưa chốt ngày | ✅ bỏ trống dịch vụ → chỉ tạo hồ sơ, không tạo lượt (`:668-670`) | — |
| Hai khách trùng cả tên lẫn năm sinh | ✅ cảnh báo mạnh (ô vàng) và nói đúng thứ đã khớp (`:1145-1154`) | — |
| Mất mạng / lỡ F5 giữa chừng | ✅ có bản nhập dở 24 giờ (`:1027-1047`) | ⚠️ chỉ phần hành chính; dịch vụ/bác sĩ/khung giờ phải chọn lại (có chủ ý, ghi rõ ở `:353-359`) |

## 5. Đánh giá chuyên môn

**Rườm rà.** 19 ô cho một lần tiếp nhận tại quầy, trong đó có ba ô gần như không ai đổi (Dân tộc "Kinh", Quốc tịch "Việt Nam", Đối tượng) và **năm cột địa chỉ ghi xuống rồi không màn nào đọc lại**. Cùng lúc đó thì **thiếu đúng ba thứ lễ tân cần**: ô Người giám hộ, lối tra/đối chiếu CCCD, và một đường thoát khi khách không có số điện thoại. Phần lõi — dò trùng, chống tách đôi bệnh án, ghi sổ trong cùng giao dịch — thì làm đúng và làm kỹ.

1. **Bỏ bắt buộc Tỉnh + Phường cho vai RECEPTION** (`NewPatientForm.tsx:307-311`), hoặc cho một lối "chưa rõ". Vì sao: đây là ràng buộc **chặn lưu** duy nhất không đến từ y tế hay định danh; khách đứng ở quầy không nhớ phường là hồ sơ không tạo được, và người trực sẽ học cách chọn bừa một phường. Công sức: **nhỏ**.
2. **Thêm ô "Người giám hộ" vào biểu mẫu.** Vì sao: cột đã có, API đã nhận (`api/patients/route.ts:50`), hai màn đã hiển thị nó — chỉ thiếu đúng ô nhập; hiện phải tạo xong rồi sang màn khác sửa, và không ai nhớ làm bước hai. Công sức: **nhỏ**.
3. **Quyết dứt điểm về địa chỉ có cấu trúc: hoặc đọc lại 5 cột ấy ở màn hồ sơ, hoặc bỏ hẳn hai combobox và giữ một ô địa chỉ tự do.** Vì sao: hiện đang trả giá cả hai đầu — lễ tân gõ hai combobox (một cái phải chờ nạp runtime), còn dữ liệu thu được thì không màn nào dùng. Công sức: **vừa**.
4. **Dọn mã chết cùng lượt: `gheTrucTiep` (`:427`), `patientKind` (`:490`), nhánh `nurse` (`page.tsx:32-38`), route `/api/patients/check-phone`, nhãn nav CSKH (`nav-items.ts:292-294`), dấu `*` sai ở nhãn "Bác sĩ & khung giờ" (`:1546`).** Vì sao: mỗi thứ đều làm người đọc sau tin rằng còn có một nhánh nữa để kiểm; `check-phone` còn là bản sao **thứ hai** của luật dò trùng — đúng thứ mà `check-duplicate` sinh ra để xoá bỏ. Công sức: **nhỏ**.
5. **Nói ra khi cảnh báo trùng "chưa kiểm được".** Vì sao: hiện backend im lặng và màn hình trông y hệt lúc thật sự không trùng (`check-duplicate/route.ts:39-44`); người trực đọc sự im lặng ấy thành một lời bảo đảm. Công sức: **nhỏ** (một cờ trong đáp trả + một dòng chữ xám).
6. **Cho phép SĐT chính để trống, kèm một lý do chọn được.** Vì sao: đây là tình huống có thật ở quầy và hiện không có đường đi; hệ quả xấu nhất bây giờ là người trực gõ một số bịa, làm hỏng chính cột mà toàn bộ máy dò trùng dựa vào. Công sức: **vừa** (đụng cả `PHONE_RE` phía BFF `api/patients/route.ts:103-108` và luật dò trùng).


---

## 4. Trang chủ & Công việc của tôi (góc nhìn Lễ tân)

Cửa quyền áp cho vai `RECEPTION` (đọc từ code, không suy đoán):

| Cửa | Giá trị cho Lễ tân | Nguồn |
|---|---|---|
| `canSeeNav("/home")` | ✅ `"all"` | `src/dashboard/lib/roles.ts:280` |
| `canSeeNav("/tasks")` | ✅ có `RECEPTION` trong mảng | `src/dashboard/lib/roles.ts:343` |
| `canCheckin` | ✅ (RECEPTION + MANAGEMENT) | `src/dashboard/lib/roles.ts:161-163` |
| `canWriteIntake` | ✅ | `src/dashboard/lib/roles.ts:125-132` |
| `canWriteClinical` / `canReadClinical` | ❌ | `src/dashboard/lib/roles.ts:112-119` |
| `canManageAppt` (huỷ / phân lại BS) | ❌ | `src/dashboard/lib/roles.ts:167-169` |
| `isTasksReadOnly` | ✅ → `/tasks` chỉ-đọc | `src/dashboard/lib/roles.ts:196-200` |

Thanh bên của Lễ tân chỉ còn 8 mục (mọi href khác trong `NAV` đều rớt `canSeeNav`):
Trang chủ · Hàng đợi tiếp nhận · Check-out lượt khám · Quản lý khách hàng · Danh sách
bệnh nhân · Tạo bệnh nhân · **Công việc của tôi** · Lịch làm việc
(`src/dashboard/app/(dashboard)/nav-items.ts:59-216`, đối chiếu `roles.ts:253-421`).

---

## A. Trang chủ (`/home`)

### A1. Thành phần bên trong

| Thành phần | Làm gì | Lễ tân có thấy không |
|---|---|---|
| Lời chào / tiêu đề | Lễ tân được thay bằng "Tổng quan tiếp nhận" thay vì "Xin chào…" (`home/page.tsx:378-381`) | ✅ thấy (bản riêng) |
| 3 ô số `StatCard` | Việc đang chờ làm · BN mới đăng ký hôm nay · Lịch chờ xác nhận (`home/page.tsx:317-321`) | ✅ thấy, **không bấm được** (`StatCard.tsx:3-18` không có `Link`) |
| `HomeCheckin` (ô check-in riêng, có STT + thứ tự gọi) | Danh sách BN hôm nay, xếp theo `call_order`, chip `queue_number` (`HomeCheckin.tsx:81,164-166`) | ❌ **ẩn** — `showCheckin = canCheckin(role) && role !== "RECEPTION"` (`home/page.tsx:101`) |
| `VisitStatusBoard` + `VisitStatusRealtime` | Bảng trạng thái buổi khám hôm nay, thanh 4 mốc + đồng hồ chờ | ✅ **CHỈ Lễ tân** (`home/page.tsx:104,424-434`) |
| `WeeklyAppointmentsTable` | Lưới lịch hẹn cả tuần theo khung giờ / bác sĩ | ✅ thấy, kèm cột "Thao tác Check-in" (`WeeklyAppointmentsTable.tsx:275-279`) |
| — nút Check-in / Không đến / Hoàn tác check-in | PATCH `/api/appointments` | ✅ **dùng được** (`WeeklyAppointmentsTable.tsx:505-537`; backend cho phép: `app/api/appointments/route.ts:383-395`) |
| — bấm TÊN bệnh nhân mở hồ sơ hành chính + sinh hiệu | popup `ClinicalRecordForm` | ❌ chỉ khi `canWriteClinical` (`WeeklyAppointmentsTable.tsx:428-449, 581`) → Lễ tân chỉ thấy chữ thường |
| — ô xanh "＋ Đặt lịch vào đây" | link `/patients/new?date&time&doctor` | ✅ dùng được (`WeeklyAppointmentsTable.tsx:228-238`; `/patients/new` mở cho RECEPTION, `roles.ts:337`) |
| — nút In phiếu (lịch `COMPLETED`) | `/print/{id}` | ✅ thấy (`WeeklyAppointmentsTable.tsx:498-504`) |
| `WorkRosterTable` ("Lịch làm việc") | Bảng ca trực cả tuần, read-only | ✅ thấy (`home/page.tsx:459-470`) |
| Khối "Lối tắt" | các nút nav dạng lớn | ❌ đã comment chết (`home/page.tsx:472-486`) |

### A2. Logic nào chạy thật

- ✅ Check-in / Không đến / Hoàn tác check-in: gọi thật, có gate backend đúng vai
  (`WeeklyAppointmentsTable.tsx:281-299` → `app/api/appointments/route.ts:383-395`).
- ✅ Bảng trạng thái buổi khám: đọc `visit` hôm nay + lọc bỏ lịch `CANCELLED/NO_SHOW`
  (`home/page.tsx:199-207, 288-291`), có đường lùi khi select chính lỗi (`:248-282`).
- ✅ Bảng lịch trực: dữ liệu thật `work_roster` đã duyệt, tên đồng bộ từ `staff`
  (`home/page.tsx:164-170, 329-332`).
- ⚠️ **Ô số "Việc đang chờ làm" đếm cả phòng khám, mọi thời điểm**: `work_item` với
  `status in (PENDING, IN_PROGRESS)`, không lọc ngày, không lọc người, không lọc
  workspace — `home/page.tsx:144-147`. Nó KHÔNG phải "việc của tôi" và không khớp con
  số nào trên `/reception/queue` (màn kia lọc theo workspace `bang_dieu_phoi`,
  `reception/queue/page.tsx:32`).
- ⚠️ **Thanh tiến trình phụ thuộc tuần đang xem của bảng lịch hẹn**: cờ `paid`,
  `exam_started_at`, `paid_at` lấy từ `/api/v1/visits/progress?from=apptDates[0]&to=…`
  (`home/page.tsx:217-219`), mà backend lọc theo `appointment.slot_start` trong khoảng đó
  (`src/clinicai/services/visit_progress_service.py:123-125`). Lễ tân bấm mũi tên tuần của
  bảng "Lịch hẹn khám" (`home/page.tsx:442-447`) là các mốc "Đang khám / Đã thanh toán"
  của **hôm nay** biến mất, bảng tụt về "Chờ khám" — sai im lặng, không báo lỗi.
- ⚠️ **Chip "khám N phút" lệch với tooltip của chính nó**: `examMinutes` =
  `finalized_at − checked_in_at`, gồm cả thời gian ngồi chờ (`VisitStatusBoard.tsx:86-94`),
  trong khi title ghi "khám xong − bắt đầu khám" (`VisitStatusBoard.tsx:157`).
- ⚠️ **Ghi chú lý do ẩn `HomeCheckin` mô tả sai giao diện**: `home/page.tsx:97-100` viết "bấm
  tên BN mở popup check-in", nhưng nút tên chỉ mở popup khi `canWriteClinical`
  (`WeeklyAppointmentsTable.tsx:428`) — Lễ tân không có. Kết luận "trùng nên ẩn" chỉ đúng
  một nửa: thứ **mất hẳn** là cột STT + xếp theo `call_order` của `HomeCheckin`.
- ❌ Chết hẳn trên đường Lễ tân: chỉ khối "Lối tắt" đã comment (`home/page.tsx:472-486`).

### A3. Chồng chéo

- "Lịch làm việc" ở cuối `/home` (`home/page.tsx:459-470`) **trùng nguyên bảng** với mục
  thanh bên `/schedule` mà Lễ tân vẫn thấy (`roles.ts:389` cho mọi vai trừ CSKH). Chính
  ghi chú tại `roles.ts:382-384` nói đã gỡ `/schedule` khỏi CSKH vì lý do "đường thứ hai
  tới cùng một bảng" — lý do ấy đúng y hệt với Lễ tân nhưng chưa áp.
- Ba ô số không dẫn đi đâu (`StatCard.tsx`): "Lịch chờ xác nhận" đếm lịch `SCHEDULED` hôm nay
  (`home/page.tsx:154-158`) nhưng Lễ tân không có màn nào để xác nhận (xem B).
- "Việc đang chờ làm" và `/reception/queue` cùng đọc `work_item` nhưng khác phạm vi → hai
  con số khác nhau cho cùng một khái niệm.
- Lưới "Lịch hẹn khám" (`/home`) và board `/tasks` cùng liệt kê lịch hẹn hôm nay, khác
  cách trình bày; xem mục B3.

### A4. Nghiệp vụ có đủ không

Đầu ca sáng, Lễ tân cần theo thứ tự: (1) hôm nay có bao nhiêu lịch, ai đến giờ nào, bác sĩ
nào trực; (2) ai đã đến / chưa đến để check-in; (3) ai đang chờ quá lâu; (4) khách vãng lai
đặt vào chỗ nào còn trống.

- (1) ✅ có: lưới tuần theo khung giờ + nhóm bác sĩ, kèm cảnh báo "bác sĩ đã nghỉ — gọi
  khách đổi lịch" ngay tại dòng (`WeeklyAppointmentsTable.tsx:410-427`).
- (2) ✅ có: cột Thao tác Check-in.
- (3) ✅ có: `WaitClock` đổi màu theo ngưỡng 10/20 phút (`VisitProgress.tsx:14-16, 177-225`).
- (4) ✅ có: ô xanh "đặt vào đây" chỉ mở cho ngày hôm nay (`WeeklyAppointmentsTable.tsx:228-238`).
- ❌ **Thiếu**: mặc định trang mở ra là **cả tuần**, không phải hôm nay — Lễ tân phải cuộn
  qua các ngày khác để tới ngày đang làm (`home/page.tsx:365-376` dựng đủ 7 ngày).
- ❌ **Thiếu**: số thứ tự gọi. `HomeCheckin` (nơi có `queue_number` + `call_order`) bị ẩn cho
  chính Lễ tân (`home/page.tsx:101`), còn màn `/queue` đã tắt cho mọi vai (`roles.ts:365`).
- ❌ **Thiếu**: không có ô "hôm nay còn ai chưa check-in mà đã quá giờ hẹn" — dữ liệu có
  (`status` + `slot_start`) nhưng không khối nào tổng hợp.

### A5. Đánh giá chuyên môn

Đáng nằm trên thanh bên: **có** — với Lễ tân đây là màn duy nhất gộp lịch hẹn + trạng thái
buổi khám + ca trực, và là nơi họ bấm check-in. Nhưng nó đang gánh ba thứ cho ba loại người
(ô số kiểu quản lý, lịch trực kiểu nhân sự, lưới tuần kiểu điều phối).

1. **Sửa nguồn dữ liệu thanh tiến trình, tách khỏi tuần đang xem** — vì sai im lặng đúng
   thứ Lễ tân dùng để trả lời "chị đợi thêm mấy phút". Gọi `visits/progress` theo NGÀY hôm
   nay cho bảng trạng thái, tách khỏi `apptDates`. Công sức: **nhỏ**.
2. **Đổi 3 ô số thành số dùng được cho quầy + bấm được** (chưa check-in quá giờ · đang chờ
   > 20 phút · chờ thu) — vì "Việc đang chờ làm" đang là con số toàn phòng khám không ai
   hành động được (`home/page.tsx:144-147`). Công sức: **vừa**.
3. **Mặc định lưới lịch hẹn mở ở HÔM NAY, tuần là tuỳ chọn** — vì màn đầu ca phải trả lời
   "hôm nay" trước. Công sức: **nhỏ**.
4. **Trả lại STT / thứ tự gọi cho Lễ tân**: hoặc thêm cột `queue_number` vào lưới, hoặc bỏ
   điều kiện `role !== "RECEPTION"` và gộp `HomeCheckin` vào một khối duy nhất. Công sức:
   **vừa**.
5. **Bỏ mục `/schedule` khỏi thanh bên Lễ tân** (giữ bảng ở cuối `/home`) — cùng lập luận đã
   áp cho CSKH tại `roles.ts:382-384`. Công sức: **nhỏ**.

---

## B. Công việc của tôi (`/tasks`)

`/tasks` là **năm màn khác nhau dùng chung một URL**, phân nhánh theo vai ở
`app/(dashboard)/tasks/page.tsx:207-231`: Thu ngân → `CashierTasks`; TKYK → board bác sĩ
ghi được; Bác sĩ → board bác sĩ; Điều dưỡng → board bác sĩ; **Lễ tân/Thu ngân → board bác
sĩ CHỈ-ĐỌC**; còn lại (CSKH/Quản lý) → `ConfirmBoard` + nhật ký CSKH.

Lễ tân rơi vào nhánh `isTasksReadOnly` (`tasks/page.tsx:228-231`) → `DoctorTasks(readOnly=true,
showPreVisitBrief=false, allDoctors=false, showSono=false, vitalsOnly=true)`.
Vì `readOnly=true` nên bỏ lọc `doctor_id` → Lễ tân thấy lịch của **mọi bác sĩ**
(`tasks/page.tsx:136-142`), cửa sổ từ đầu tuần/đầu tháng đến +31 ngày (`:111-122`).

### B1. Thành phần bên trong

| Thành phần | Làm gì | Lễ tân có thấy không |
|---|---|---|
| Tiêu đề "Danh sách khám bệnh" + dòng "Vai trò hiện tại không mở hồ sơ lâm sàng" | nhãn màn | ✅ (`tasks/page.tsx:150-158`) |
| 4 ô số workspace (Lịch trong kỳ · Chờ lễ tân/bác sĩ · Đã check-in · Chờ đọc kết quả) | đếm theo bộ lọc kỳ | ✅ (`DoctorWorkBoard.tsx:354-381`) |
| Cột trái "Hàng đợi hôm nay" — tìm kiếm + lọc kỳ, có STT, xếp theo `call_order` | đọc | ✅ (`DoctorWorkBoard.tsx:385-437`, sắp xếp `:296-304`) |
| Cột giữa: tóm tắt BN + bảng lịch (Ngày/Giờ/BN/Phân loại/Trạng thái) | đọc | ✅ (`DoctorWorkBoard.tsx:439-513`) |
| Cột phải "Việc còn thiếu & điều phối": STT, giờ check-in, cờ KQ CLS | đọc | ✅ (`DoctorWorkBoard.tsx:520-529`) |
| Nút "Mở hồ sơ lâm sàng" | mở `ClinicalRecordForm` | ❌ thay bằng câu "Vai trò hiện tại chỉ được xem lịch" (`DoctorWorkBoard.tsx:532-544`) |
| `ClinicalRecordForm` (1490 dòng) | bệnh án | ❌ không bao giờ mount: `open = readOnly ? null : …` (`DoctorWorkBoard.tsx:258`) |
| Nút "In phiếu khám" (lịch `COMPLETED`) | `/print/{id}` | ✅ **thấy và bấm được** (`DoctorWorkBoard.tsx:545-549`) |
| `ConfirmBoard` (kanban xác nhận lịch) + chú giải trạng thái | quản lý lịch CSKH | ❌ Lễ tân không tới nhánh này (`tasks/page.tsx:228-231` chặn trước) |
| `CskhActionBoard` (Nhật ký CSKH, gắn nhãn "🚧 Đang xây dựng") | ghi việc CSKH | ❌ như trên (`tasks/page.tsx:344-372`) |
| `CashierWorkBoard`, `SonoBiometry`, `AndrologyReview`, `ClinicalSignPanel`, `ServiceFormEngine` | thu ngân / siêu âm / lâm sàng | ❌ ngoài nhánh Lễ tân |

### B2. Logic nào chạy thật

- ✅ Hàng đợi + bộ lọc kỳ/trạng thái/tìm kiếm: chạy thật trên dữ liệu backend
  (`tasks/page.tsx:136-146`, `DoctorWorkBoard.tsx:277-305`).
- ✅ Chặn ghi: `readOnly` cắt cả `openId` cũ còn sót trong state (`DoctorWorkBoard.tsx:256-258`).
- ⚠️ **`vitalsOnly=true` truyền cho Lễ tân là tham số chết**: `tasks/page.tsx:230` bật nó,
  nhưng nó chỉ được dùng khi form mở (`DoctorWorkBoard.tsx:338`), mà form không bao giờ mở
  với `readOnly=true`. Đọc code sẽ tưởng Lễ tân điền được sinh hiệu.
- ⚠️ **Ba cái tên cho một màn**: thanh bên ghi "Công việc của tôi" (`nav-items.ts:126`),
  thanh trên cùng ghi "Công việc chăm sóc — ghi nhận kết quả chăm sóc khách hàng"
  (`GlobalHeader.tsx:214-215`, câu của CSKH), thân trang ghi "Danh sách khám bệnh"
  (`tasks/page.tsx:151-153`). Lễ tân mở màn thấy ba nhãn không liên quan nhau.
- ⚠️ Ô "Chờ lễ tân / bác sĩ" đếm gộp `SCHEDULED + CSKH_CONFIRMED + CONFIRMED`
  (`DoctorWorkBoard.tsx:308-310`) — trộn việc của CSKH (chưa gọi xác nhận) với việc của Lễ
  tân (đã xác nhận, chờ khách đến), nên con số không chỉ ra việc phải làm của ai.
- ❌ **`TasksRealtime.tsx` (194 dòng) là code chết**: chỉ còn được nhắc trong một comment
  (`tasks/page.tsx:3`) và một test đọc nội dung tệp
  (`src/dashboard/tests/clinical-ultrasound-ui-boundary.test.mts:21`); không tệp nguồn nào
  import.
- ❌ Ghi chú lược đồ nói "`/tasks` sẽ đọc `work_item`"
  (`supabase/migrations/20260730000005_workflow_kernel.sql:23-25`) — thực tế `/tasks` không
  chạm `work_item` ở bất kỳ nhánh nào; màn đọc kernel là `/reception/queue`.

### B3. Chồng chéo

- **`/tasks` (Lễ tân) vs `/reception/queue`**: cùng trả lời "hôm nay phải làm gì" nhưng hai
  nguồn khác nhau — `/tasks` đọc `appointment` qua `doctor-board` (`tasks/page.tsx:136-142`),
  `/reception/queue` đọc `work_item` của workspace `bang_dieu_phoi`
  (`reception/queue/page.tsx:32`). `/reception/queue` mới là màn có SLA, "cần xác minh", "quá
  hạn" (`reception/queue/page.tsx:57-81`); `/tasks` không có khái niệm quá hạn.
- **`/tasks` vs `/home`**: cùng liệt kê lịch hẹn. Khác biệt thật của `/tasks` với Lễ tân chỉ
  còn: có ô tìm kiếm theo tên/mã, có bộ lọc kỳ tới 31 ngày, và **hiển thị `queue_number` +
  xếp theo `call_order`** — thứ mà `/home` đã ẩn khỏi Lễ tân. Ngược lại `/tasks` **không**
  cho check-in, nên không thay được `/home`.
- Hệ quả: Lễ tân có **ba** danh sách bệnh nhân hôm nay (`/home` lưới tuần, `/home` bảng
  trạng thái buổi khám, `/tasks` board bác sĩ) cộng **một** hàng đợi kernel
  (`/reception/queue`), không màn nào là nguồn duy nhất.

### B4. Nghiệp vụ có đủ không

Với đúng vai Lễ tân, `/tasks` không mang lại hành động nào (trừ In phiếu). Nó là bản sao
giao diện bàn khám của bác sĩ kèm câu báo không dùng được (`DoctorWorkBoard.tsx:532-535`).
Đầu ca sáng nó không trả lời thêm câu nào ở mục A4 ngoài STT gọi khám — mà đó là hệ quả
`/home` ẩn nhầm, không phải giá trị riêng của màn này.

### B5. Đánh giá chuyên môn

Đáng nằm trên thanh bên Lễ tân: **không**, ở dạng hiện tại. Nhãn "Công việc của tôi" hứa một
danh sách việc; thứ mở ra là bàn khám của người khác ở chế độ chỉ nhìn. Đây là nhiễu, và còn
là nhiễu tốn tiền: mỗi lần mở là một truy vấn board 31 ngày cho toàn bộ bác sĩ.

1. **Gỡ `/tasks` khỏi thanh bên Lễ tân** (giữ route + quyền, như đã làm với Quản lý ở
   `roles.ts:439-449` — chỉ thêm `RECEPTION: ["/tasks"]` vào `AN_KHOI_THANH_BEN`) — vì Lễ
   tân đã có `/reception/queue` là màn "việc phải làm" thật. Công sức: **nhỏ**.
2. **Trước khi gỡ, chuyển hai thứ Lễ tân thật sự dùng sang `/home`**: cột STT
   (`queue_number`) và ô tìm theo tên/mã. Nếu không sẽ mất chức năng chứ không phải dọn
   nhiễu. Công sức: **vừa**.
3. **Thống nhất tên màn** ở ba nơi (`nav-items.ts:126`, `GlobalHeader.tsx:214-215`,
   `tasks/page.tsx:151`) — vì hiện tại thanh trên cùng đọc cho Lễ tân một câu viết cho CSKH.
   Công sức: **nhỏ**.
4. **Bỏ `vitalsOnly` khỏi lời gọi cho Lễ tân** (`tasks/page.tsx:230`) và xoá
   `TasksRealtime.tsx` cùng dòng test đọc nó — hai mẩu code chết đang mô tả sai quyền hạn.
   Công sức: **nhỏ**.
5. **Nếu muốn giữ `/tasks` cho Lễ tân**, phải đổi mục tiêu màn: lọc mặc định "hôm nay",
   chỉ trạng thái `CONFIRMED/CHECKED_IN`, thêm nút check-in — tức là biến nó thành màn quầy
   thật. Công sức: **lớn**, và trùng đích với `/reception/queue`, nên chỉ nên chọn một
   trong hai.

> Chưa rõ — cần kiểm: lượt khám **không gắn `appointment_id`** (nếu có luồng tạo visit vãng
> lai không qua lịch hẹn) sẽ không có dòng nào trong `/api/v1/visits/progress` (khoá theo
> `appointment.id`, `visit_progress_service.py:123-125`) → thanh tiến trình của những dòng ấy
> đứng mãi ở "Đang khám". Cần dựng thử một ca vãng lai trên staging để xác nhận.


---

## 5. Quản lý khách hàng (góc nhìn Lễ tân)

**Ba cờ quyết định mọi thứ trên màn này**, tính ở `customers/page.tsx:131-134`
rồi truyền xuống `CustomersView` (`page.tsx:1175-1177`). Với vai `RECEPTION`:
`canEdit` = `canWriteIntake` → **true** (`lib/roles.ts:125-132`);
`canOperateCskh` = `canOperateCustomerCare` → **true** (`lib/roles.ts:140-142`,
đang là alias gọi thẳng `canWriteIntake`); `canManage` = `canManageAppt` →
**false** (`lib/roles.ts:167-169`, chỉ CSKH/MANAGEMENT/TRUONG_CA).

Lễ tân vào được màn vì `/customers` liệt kê 7 vai trong đó có `RECEPTION`
(`lib/roles.ts:306-314`), và **không** bị ẩn khỏi thanh bên vì
`AN_KHOI_THANH_BEN` mới chỉ khai cho `MANAGEMENT` (`lib/roles.ts:439-449`).

---

### 1. Thành phần bên trong

| Thành phần | Làm gì | Lễ tân có thấy / dùng được không |
|---|---|---|
| Ô tìm kiếm + bộ lọc kỳ/chiều | Tra tên, SĐT, mã khách; lọc theo ngày tạo / ngày hẹn | **Thấy, dùng được.** Không gác vai — `CustomersView.tsx:1332-1350`. Truy vấn chạy qua RLS (`page.tsx:181-211`) |
| Nút "Thêm khách hàng mới" | Link `/patients/new` | **Thấy, dùng được.** Gác `canEdit` (`CustomersView.tsx:1368-1377`); `/patients/new` mở cho `RECEPTION` (`lib/roles.ts:337`) |
| Danh sách khách (cột trái) | Tên, chip trạng thái CSKH, "+N việc", tương tác gần nhất, hạn, người chạm cuối | **Thấy toàn bộ.** Không gác vai — `CustomersView.tsx:1419-1594` |
| Chip "N lịch trùng" | Cảnh báo trùng lịch | **Thấy nhưng KHÔNG bấm được** — `canManage ? <button> : <span>` (`CustomersView.tsx:1476-1497`). Trung thực, không lừa |
| `VungLamViecKhach` (cột giữa) — sơ đồ trạng thái CSKH, nút "Làm bước này" | Sổ chăm sóc: gọi xác nhận, nhắc hẹn, hỏi XN, trả kết quả, hỏi thăm sau sinh/thủ thuật | **Thấy đủ, ghi được thật.** Gác `canOperateCskh` (`CustomersView.tsx:1607`). Backend `_INTAKE_GUARD` có `RECEPTION` (`clinicai/api/v1/routers/cskh.py:42`, `services/cskh_service.py:41-48`) |
| Khối "Kết thúc lượt khám": Checkout / Tái khám / Đặt lịch khám mới | Đóng lượt + đặt lịch nối chuỗi | **Thấy. Checkout hỏng (403), hai nút kia hỏng theo khi khách đang CHECKED_IN.** `VungLamViecKhach.tsx:1574-1647` — chi tiết ở mục 2 |
| Khối "Nhắc tái khám" (mốc gọi trước 7 ngày / 1 ngày) | Ghi kết quả cuộc gọi nhắc | **Không thấy** — `recallPromise` trả null vì `_RECALL_GUARD` không có `RECEPTION` (`page.tsx:362-365`, `cskh.py:43-47`), nên `taiKham` rỗng và khối tự ẩn (`VungLamViecKhach.tsx:1466`) |
| Khối "Đã hẹn gọi lại" | Xem + đóng lời hẹn gọi lại | **Thấy, dùng được** — `PATCH /api/cskh/hen-goi-lai/{id}` gác `_INTAKE_GUARD` (`cskh.py:433-436`) |
| "Lịch sử thao tác" (details) + "Lịch sử các lần khám" | Sổ đọc, chọn lượt để làm việc | **Thấy, dùng được** — `VungLamViecKhach.tsx:1675-1707`, `CustomersView.tsx:1643-1647` |
| `PhanHoiKhach` (phản hồi/khiếu nại) | Ghi + đổi trạng thái phản hồi | **Thấy, ghi được** — `CustomersView.tsx:1648-1652`; backend `_INTAKE_GUARD` (`cskh.py:457-478`) |
| `TepKetQua` (tải ảnh SA / phiếu XN lên, đánh dấu đã gửi) | Gửi kết quả cho khách | **Thấy, ghi được** — dựng trong `HanhDongTrangThai.tsx:710`; backend `_INTAKE_GUARD` (`cskh.py:499-608`) |
| Ô "Lịch hẹn sắp tới" (cột phải) | Bấm để đổi/huỷ | **Thấy ở dạng CHỈ ĐỌC** — nhánh `canManage && apptSuaDuoc` không chạy, rơi xuống `<div>` tĩnh (`CustomersView.tsx:1730` vs `1797-1839`) |
| Khối brand "CSKH / Lễ tân" + `HanhDongTrangThai` | Số điện thoại khách, bộ nút theo trạng thái, "Hẹn ngày tái khám…", "Hẹn gọi lại ngày…" | **Thấy** (`CustomersView.tsx:1876`, nhãn ở `1894-1896`). "Hẹn ngày tái khám" **403** — mục 2 |
| Nút "Đổi / huỷ lịch hẹn (ghi lý do)" | Mở `AppointmentEditModal` | **Thấy nhưng LUÔN mờ** — `disabled={!canManage \|\| !apptSuaDuoc}` (`CustomersView.tsx:1952`) |
| Nút "Đặt lịch mới" | `router.push("/appointments?bn=…")` | **Thấy, bấm vào bị đá về `/home`** — `CustomersView.tsx:1968-1991`; `/appointments` chỉ mở cho CSKH+MANAGEMENT (`lib/roles.ts:303`) |
| `PatientAdminEditor` (sửa hồ sơ hành chính) | Sửa tên, SĐT, địa chỉ, nghề nghiệp… | **Thấy, sửa được** — gác `canEdit` (`CustomersView.tsx:1993-2015`) |
| Link "Hồ sơ và lịch sử khám" | `/patients/[id]` | **Thấy, vào được** — `CustomersView.tsx:2055-2063`; trang đích cho Lễ tân `canEdit`+`canBook` (`patients/[id]/page.tsx:54-57`) |
| `AppointmentEditModal`, `LichTrungCuaKhach`, `BaoXepBacSi` | Đổi/huỷ lịch, dọn lịch trùng, báo quản lý xếp bác sĩ | **Không bao giờ dựng** — cả ba phụ thuộc `canManage` hoặc `apptSuaDuoc` (`CustomersView.tsx:2081`, `2096`; `VungLamViecKhach`… `CustomersView.tsx:1947-1949`) |
| `DatLichModal` (form đặt lịch trong màn) | Đặt tái khám / khám mới ngay tại chỗ | **Thấy khi mở được**, và ghi được thật — gác `canEdit` (`CustomersView.tsx:2109`); backend `_BOOKING_GUARD = INTAKE_ROLES` có `RECEPTION` (`routers/booking.py:44`, `services/booking_service.py:160-167`) |

---

### 2. Logic nào chạy thật với vai Lễ tân

**✅ Chạy thật**

- Tra cứu, lọc, mở hồ sơ, đọc lịch sử khám và sổ chăm sóc.
- Sửa hồ sơ hành chính (`PatientAdminEditor`).
- Ghi mọi bước sổ chăm sóc một-chạm (`mot-cham.ts:27-105`) và mọi bộ nút của
  `HanhDongTrangThai` — trừ "Hẹn ngày tái khám".
- **Check-in** qua node "Đã check-in": `loai = "CHECK_IN"` →
  `tuong_tac_cskh_service:437-446` → `apply_action("checkin")` →
  `CHECKIN_ROLES` gồm `RECEPTION` (`booking_service.py:149-158`).
- Ghi/đóng phản hồi khách; tải và đánh dấu đã gửi tệp kết quả.
- Hẹn gọi lại + đóng lời hẹn.
- Đặt lịch qua `DatLichModal` (khi mở được — xem ❌ bên dưới).

**⚠️ Nửa vời**

- **Nút "Đổi / huỷ lịch hẹn (ghi lý do)" mờ vĩnh viễn, và tooltip nói dối.**
  `CustomersView.tsx:1950-1962`: `disabled={!canManage || !apptSuaDuoc}`, nhưng
  `title` chỉ có hai câu — "Đổi giờ hoặc huỷ lượt đang xem" hoặc *"Lượt đang xem
  đã đóng hoặc đã huỷ — không đổi được nữa"*. Với Lễ tân `apptSuaDuoc` luôn
  `undefined` (`CustomersView.tsx:999-1002`, vì `appt` chỉ dựng khi `canManage` —
  `page.tsx:598-614`), nên họ luôn đọc câu thứ hai: màn đổ lỗi cho **lịch hẹn**
  trong khi thủ phạm là **quyền của họ**. Backend đồng ý là họ không được huỷ
  (`cancel`/`reschedule` = `MANAGE_ROLES`, `booking_service.py:292`, `320-322`,
  `142-144`) — nên đây là lỗi câu chữ, không phải lỗi quyền.
- **Chip "N lịch trùng" chỉ là chữ.** `CustomersView.tsx:1490-1497`. Lễ tân thấy
  cảnh báo nhưng không có đường xử lý ở màn này.
- **Khối "Nhắc tái khám" luôn rỗng nhưng SÁU chỗ trên màn vẫn bảo đi tìm nó.**
  `HanhDongTrangThai.tsx:111`, `118`, `135`, `142`, `144`, `812` đều viết "bấm
  Hẹn ngày tái khám…" / "hiện ở khối Nhắc tái khám cột giữa". Với Lễ tân khối ấy
  không bao giờ hiện (`page.tsx:362-365`).

**❌ Chết hoặc bị chặn**

1. **"Hẹn ngày tái khám…" — nút hiện cho mọi vai, Lễ tân bấm là 403.**
   Nút render vô điều kiện (`HanhDongTrangThai.tsx:1005-1013`), gọi
   `POST /api/cskh/nhac-tai-kham` (`HanhDongTrangThai.tsx:387`) → BFF proxy
   nguyên si (`app/api/cskh/nhac-tai-kham/route.ts:24`) → backend
   `_RECALL_GUARD = {CSKH, MANAGEMENT, TRUONG_CA}` (`cskh.py:43-47`, `220-223`).
   `RECEPTION` không có trong đó. Đây là ca kinh điển mà `lib/roles.ts:53-66`
   viết ra để cảnh báo: *"The server was right; the screen was lying."*

2. **"Checkout" — nút hiện, backend từ chối, và đúng vai LỄ TÂN là vai bị từ chối.**
   `VungLamViecKhach.tsx:1574-1591` → `ghiCheckout()` (`:933-981`) POST
   `loai: "CHECK_OUT"` → `_INTAKE_GUARD` cho qua (RECEPTION có) →
   `tuong_tac_cskh_service:421-423` → `_checkout_atomically` (`:449-486`) →
   `apply_action("complete")` với `allowed_roles = DOCTOR_ROLES | MANAGE_ROLES`
   (`booking_service.py:253-266`) → `SafetyGateError` (`booking_service.py:675-678`).
   Nghịch lý nằm ngay trong chú thích ở `VungLamViecKhach.tsx:918-928`: đường
   `dispatch/checkout` bị bỏ **vì** nó chỉ mở cho Lễ tân/Trưởng ca/Quản lý
   (`routers/dispatch.py:36-38`) và CSKH không gọi được — đường thay thế chọn
   cho CSKH lại loại đúng Lễ tân ra.

3. **"Tái khám" và "Đặt lịch khám mới" hỏng theo, đúng lúc cần nhất.**
   `ketThucRoiDatLich()` (`VungLamViecKhach.tsx:1113-1119`): nếu lượt đang
   `CHECKED_IN` thì gọi `ghiCheckout()` trước, `if (!xong) return;`. Với Lễ tân
   `ghiCheckout()` luôn thất bại (mục 2) ⇒ **modal đặt lịch không bao giờ mở cho
   khách đang ngồi trong phòng khám** — tình huống "khám xong, đặt tái khám tại
   quầy" chính là việc của Lễ tân. Khách chưa check-in thì hai nút này chạy bình
   thường.

4. **"Đặt lịch mới" (cột phải) dẫn tới một trang Lễ tân bị chặn ở cửa.**
   `CustomersView.tsx:1981-1985` push sang `/appointments`;
   `appointments/page.tsx:16` gọi `requireNavAccess("/appointments")` và
   `NAV_ROLES["/appointments"] = ["CSKH","MANAGEMENT"]` (`lib/roles.ts:303`) →
   `redirect("/home")` (`lib/clinic-session.ts:26-29`). Không thông báo, không
   giải thích. Đúng cái bẫy mà chú thích ngay trên nút "Thêm khách hàng mới"
   (`CustomersView.tsx:1359-1367`) đã dặn tránh — nhưng nút ở dưới thì mắc.

5. **`BaoXepBacSi` chết lặng.** `CustomersView.tsx:1947-1949` gác bằng
   `apptSuaDuoc` (⊂ `canManage`). Backend lại cho phép: `POST
   /appointments/{id}/bao-xep-bac-si` gác `_BOOKING_GUARD = INTAKE_ROLES` có
   `RECEPTION` (`routers/booking.py:209-213`). Quyền có, đường đi không có.

---

### 3. Chồng chéo với `/reception/queue` và `/patient-list`

| Việc | `/customers` | `/reception/queue` | `/patient-list` | Có ghi cùng dữ liệu không |
|---|---|---|---|---|
| Check-in | node "Đã check-in" → `POST /api/cskh/tuong-tac` `loai=CHECK_IN` (`mot-cham.ts:52-56`) | nút "Check-in — khách đã đến" → `PATCH /api/appointments {action:"checkin"}` (`QueueBoard.tsx:442-456`) | không có | **Gần như.** Cả hai cuối cùng gọi `apply_action("checkin")` → `_check_in` + `_open_visit` (`booking_service.py:781`, `829`), nên `appointment` + `visit` + hàng đợi giống hệt. **Khác một chỗ:** đường `/customers` ghi thêm một dòng `tuong_tac_cskh`; đường hàng đợi thì không. Cùng một sự kiện, sổ chăm sóc dày mỏng khác nhau tuỳ người trực bấm ở màn nào |
| Check-out / đóng lượt | nút "Checkout" — **403 cho Lễ tân** | không | không | `/reception/checkout` mới là đường của Lễ tân (`routers/dispatch.py:36-38`, nav `lib/roles.ts:262`). Hai đường ghi khác nhau: `dispatch` đóng `visit.closed_at`; đường CSKH chỉ đặt `appointment=COMPLETED` (nói rõ ở `VungLamViecKhach.tsx:930-932`) |
| Tra cứu khách + xem lịch sử khám | có, kèm sổ chăm sóc | không (chỉ hàng đợi hôm nay) | có (`patient-list/page.tsx:54`) | Cùng nguồn `patient`/`appointment`, chỉ đọc |
| Sửa hồ sơ hành chính | `PatientAdminEditor` tại chỗ (`CustomersView.tsx:1995`) | không | phải mở `/patients/[id]` (popup lâm sàng bị chặn: `enablePopup = canReadClinical(role)` = false cho Lễ tân, `patient-list/page.tsx:58`) | **Cùng một `PATCH /api/patients`** — `PatientAdminEditor` dùng chung ở cả hai (`app/(dashboard)/PatientAdminEditor.tsx`) |
| Đặt lịch | `DatLichModal` (chạy được) + nút "Đặt lịch mới" (đá về /home) | không | nút "Tái khám" **không có cho Lễ tân** (`showRebook = enablePopup && canWriteIntake` → false, `patient-list/page.tsx:61`) | `DatLichModal` → `AppointmentBooking` → `POST /appointments/bookings`, cùng đường với màn `/appointments` |

Kết luận mục này: **check-in là chỗ trùng thật** (hai nút, hai màn, một hành
động, hậu quả phụ khác nhau). Tra cứu hồ sơ trùng với `/patient-list`. Còn
check-out thì **ngược lại**: đường của Lễ tân nằm ở màn khác, và cái nút mang
tên "Checkout" ở đây lại là cái duy nhất họ không bấm được.

---

### 4. Nghiệp vụ — Lễ tân thật sự cần gì

**Cần (và màn này làm được):**

- Tra nhanh người đang đứng trước mặt: gõ tên/SĐT/mã, thấy ngay lịch hẹn, lượt
  gần nhất, số điện thoại phụ (`CustomersView.tsx:1704-1714`). Đây là thứ
  `/reception/queue` không có (hàng đợi chỉ có người đã đến trong ngày).
- Sửa hồ sơ hành chính tại quầy khi khách báo đổi số/địa chỉ.
- Tạo khách mới cho người gọi hỏi (`/patients/new`).
- Đặt lịch tái khám tại quầy ngay sau khi khám xong — **đúng việc màn đang chặn**
  (mục 2, ❌ số 3).
- Đọc lý do huỷ đã ghi và cảnh báo "bác sĩ đã đổi lịch làm việc"
  (`CustomersView.tsx:1817-1837`) để trả lời khách tại quầy.

**Nhiễu với Lễ tân (là việc CSKH):**

- Sơ đồ 8 bước chăm sóc "trước khám / sau khám" với các node "Chờ kết quả xét
  nghiệm", "Nhắc bác sĩ duyệt", "Sau sinh 1 tháng", "Sau thủ thuật 1 ngày"
  (`VungLamViecKhach.tsx:530-600`). Lễ tân không gọi điện theo dõi sau khám.
- Khối "Đã hẹn gọi lại" và nút "Hẹn gọi lại ngày…"
  (`HanhDongTrangThai.tsx:1016-1084`) — việc người trực điện thoại tự đặt cho ca sau.
- "Hẹn ngày tái khám…" — vừa là việc CSKH, vừa 403 (mục 2, ❌ số 1).
- Cột "Hạn xử lý", "Tương tác gần nhất", "+N việc" trong danh sách: đó là hàng
  đợi công việc của CSKH, không phải thông tin quầy.
- Tải/gửi tệp kết quả cho khách (`TepKetQua`) — Lễ tân **có quyền** backend
  nhưng đây là quy trình trả kết quả của CSKH, không phải việc quầy.

Nói gọn: khoảng **70% chiều cao cột giữa và cột phải** là sổ chăm sóc; phần Lễ
tân thật sự cần nằm ở ô tìm kiếm, cột hồ sơ bên phải, và hai nút đặt lịch.

---

### 5. Đánh giá chuyên môn

**Kết luận: GIỮ nhưng RÚT GỌN.** Không bỏ khỏi thanh bên của Lễ tân — đây là
màn tra cứu khách duy nhất có cả hồ sơ hành chính lẫn lịch hẹn tương lai, và
`/patient-list` không thay được (nó xoay quanh **bệnh nhân đã khám**, còn màn
này xoay quanh **khách và lịch hẹn**, kể cả người chưa khám lần nào). Nhưng
không được giữ nguyên: hiện màn đang bày cho Lễ tân bốn thứ bấm vào là hỏng
(mục 2), trong đó hai thứ hỏng **ngay tại tình huống nghiệp vụ của chính họ**.

Cơ chế rút gọn đã có sẵn và không cần phát minh gì: `AN_KHOI_THANH_BEN`
(`lib/roles.ts:439-449`) cho việc ẩn **mục thanh bên**, và tiền lệ ẩn **khối
trùng theo vai** đã có ở `home/page.tsx:101`
(`showCheckin = canCheckin(role) && role !== "RECEPTION"`).

**Đề xuất, xếp theo ưu tiên:**

1. **Tách `canOperateCustomerCare` ra khỏi `canWriteIntake`, bỏ `RECEPTION` khỏi
   nó.** — *Vì sao:* đây là gốc của cả bốn lỗi. `lib/roles.ts:140-142` đang là
   một alias (`return canWriteIntake(role)`) trong khi chính chú thích ngay trên
   nó nói mục đích là *"tách tên capability ở UI"*. Bỏ `RECEPTION` ⇒ cột giữa
   (sổ chăm sóc) và khối brand "CSKH / Lễ tân" không mount, Lễ tân rơi xuống
   nhánh chỉ-đọc đã có sẵn (`CustomersView.tsx:1660-1685`: lịch sử khám + phản
   hồi + tệp kết quả, `readOnly`), và ba nút hỏng biến mất cùng lúc. **Công sức:
   nhỏ** (một hàm + kiểm lại nhãn ở `CustomersView.tsx:1894-1896`). *Cảnh báo:*
   check-in ở màn này biến mất theo — chấp nhận được vì `/reception/queue` và
   Trang chủ đều còn, và như mục 3 đã đo, hai đường ghi cùng dữ liệu.

2. **Chữa nút "Đặt lịch mới" — đừng đẩy Lễ tân sang `/appointments`.**
   — *Vì sao:* `CustomersView.tsx:1981-1985` đá họ về `/home` không một lời.
   `DatLichModal` đã chạy được cho `canEdit` và ngay trong file đó
   (`DatLichModal.tsx:14-17`) đã lập luận vì sao mở hộp thoại tốt hơn chuyển
   trang. Đổi `router.push` thành `setDatLich("kham-moi")`, hoặc tối thiểu chỉ
   hiện nút khi `canSeeNav(role, "/appointments")`. **Công sức: nhỏ.**

3. **Mở `complete` cho `RECEPTION`, hoặc bỏ nút "Checkout" khỏi màn của Lễ tân.**
   — *Vì sao:* hiện Lễ tân bấm Checkout là lỗi đỏ, và kéo chết luôn "Tái khám"
   qua `ketThucRoiDatLich` (`VungLamViecKhach.tsx:1113-1118`). Hai hướng: (a)
   thêm `ClinicRole.RECEPTION` vào `allowed_roles` của `complete`
   (`booking_service.py:265`) — hợp lý vì Lễ tân **đã** được đóng lượt qua
   `/reception/checkout`; hoặc (b) nếu chọn đề xuất 1 thì nút tự biến mất. Dù
   chọn gì, `ketThucRoiDatLich` phải **không** chặn mở form đặt lịch khi bước
   đóng lượt thất bại vì quyền. **Công sức: vừa** (đụng máy trạng thái + test).

4. **Sửa `title` của nút "Đổi / huỷ lịch hẹn" để phân biệt "hết đổi được" với
   "bạn không có quyền".** — *Vì sao:* `CustomersView.tsx:1953-1957` đang đổ lỗi
   cho lịch hẹn trong khi lý do là vai. Người trực đọc xong sẽ đi hỏi khách thay
   vì đi hỏi trưởng ca. Thêm nhánh `!canManage` → "Chỉ CSKH / Trưởng ca / Quản lý
   đổi hoặc huỷ được lịch". **Công sức: nhỏ.**

5. **Dọn sáu câu "gõ ngày ở khối Nhắc tái khám".** — *Vì sao:* với Lễ tân khối
   ấy không bao giờ hiện (`page.tsx:362-365`), nên sáu chỗ ở
   `HanhDongTrangThai.tsx:111,118,135,142,144,812` đang chỉ người dùng đi tìm
   một khối không tồn tại — đúng lỗi commit `4442e7b` vừa vá cho một vai khác.
   Nếu làm đề xuất 1 thì phần lớn tự hết; phần còn lại nên gác theo cờ. **Công
   sức: nhỏ.**

**Không đề xuất:** bỏ `/customers` khỏi thanh bên Lễ tân. Nút "Thêm khách hàng
mới" và ô tra cứu ở đây là đường ngắn nhất cho việc quầy, và
`AN_KHOI_THANH_BEN` chỉ ẩn khỏi tầm mắt chứ không chặn — nhưng ẩn ở đây sẽ để
lại một màn mà Lễ tân vẫn cần mà không có đường đi tới.

**Chưa rõ — cần kiểm:** RLS trên `tuong_tac_cskh`, `hen_goi_lai`, `phan_hoi_khach`,
`tep_ket_qua` có chặn `RECEPTION` ở tầng đọc không. Ở đây tôi chỉ đọc được các
truy vấn Supabase phía server (`page.tsx:372-455`) và các guard FastAPI; các
policy SQL trong `supabase/migrations/` chưa soi.


---

