# HỢP ĐỒNG AGENT — AI điều phối vận hành ClinicAI

> **BẢN NHÁP v0.1 · 07/10/2026 · chờ Quang duyệt.** Chỗ có ⚖ là quyết định
> nghiệp vụ/pháp lý, AI không tự chốt.

## Tài liệu này là gì

Agent cần ba lớp tài liệu, mỗi lớp trả lời một câu khác nhau:

| Lớp | Trả lời | Ở đâu |
|---|---|---|
| 1. Hiến pháp | Agent **nghĩ** thế nào: ưu tiên P0–P7, sự thật ≠ suy luận, đóng vòng lặp | Bản Quang viết ("Agent này là ai?" §0–§25). **Cần đưa vào repo** thành `docs/ai/HIEN-PHAP-AGENT.md` để có lịch sử sửa |
| 2. Hợp đồng vận hành | Agent **đọc gì, ghi gì, gửi ai, được làm tới đâu** | Phần A–F dưới đây |
| 3. Dữ liệu & an toàn | Dữ liệu nào được rời máy, dữ liệu nào là rác, khi agent sai thì sao | Phần G–J dưới đây |

Hiến pháp thắng khi hai lớp mâu thuẫn. Hợp đồng chỉ cụ thể hoá, không nới ra.

Thiết kế nền đã có trong vault `docs/thiet-ke-he-thong/` (`3-muc-quyen-ai`,
`tk-ai-placement`, `tk-experience-state`, `tk-work-item-protocol`). Tài liệu này
không lặp lại thiết kế ấy, chỉ chốt luật chơi cho agent.

---

## A. Agent là gì về mặt kỹ thuật

- **Không phải chatbot.** Agent là một **bên nghe sự kiện** chạy trong worker
  `su-kien` có sẵn (`src/clinicai/events/worker.py`), cộng với các loại hẹn của
  `hen_gio`. Đây là 0 hạ tầng mới (SO-LUAT Phần 7, ADR-0005).
- **Danh tính:** mọi thứ agent ghi ra đều mang
  `ai_agent(ten_agent="dieu_phoi", phien_ban=…)` (`src/clinicai/events/emit.py`),
  tức `domain_event.actor_type = 'AGENT'` và bắt buộc có `agent_version`
  (Postgres ép). Mỗi lần đổi luật/prompt/model thì tăng phiên bản.
- **Rule trước, LLM sau** (hiến pháp §20). Giai đoạn 0–1 **không gọi LLM**. LLM
  chỉ vào khi cần tóm tắt nhiều tín hiệu thành một câu cho người đọc.
- **Giữ nguyên các lằn ranh cũ:** D012 không chatbot tư vấn lâm sàng; D013 không
  chấm điểm rủi ro bằng AI; lab triage (`graphs/lab_triage`) giữ nguyên cổng chặn
  GROUP_C.

## B. Đầu vào — agent được đọc gì

Luật TAM-NHIN số 1: tính năng lv4 phải chỉ ra được nó đọc bảng lv3 nào, và bảng
đó phải đáng tin. Danh sách dưới đây là **toàn bộ** những gì agent được đọc;
muốn thêm nguồn thì sửa tài liệu này trước.

| Nguồn | Dùng cho | Độ tin hôm nay |
|---|---|---|
| `domain_event` (chỉ `is_public`) | Chuyện gì vừa xảy ra, ai làm, lúc nào | Tốt về cấu trúc (chỉ thêm, có correlation/causation). **Độ phủ chưa đo** (xem I.5) |
| `hen_gio` | Việc đang chờ tới giờ kiểm lại | Tốt; mỗi loại hẹn tự kiểm lại hiện trạng |
| `dispatch_threshold` | Ngưỡng chờ theo phòng | Là dữ liệu quản lý nhập. Thiếu dòng thì dùng mặc định |
| Hiện trạng `visit`, `service_order` | Khách đang ở bước nào | Là "sự thật bây giờ" (state-first) |
| `thong_bao` (`da_doc_luc`, `da_xu_ly_luc/boi`) | Đã báo ai chưa, người đó đã xem/xử lý chưa | Có sẵn: đây là dạng "nhận việc" sơ khai duy nhất hiện có |

**Không được đọc**, giai đoạn 0–2:

- Mọi ô chữ tự do: ghi chú, lý do, tin Zalo, nội dung phiếu khám.
- Kết quả xét nghiệm/chẩn đoán. Chỉ được đọc cờ mức độ đã có (`triage_group`)
  khi cần ưu tiên.
- `event_log`: đây là nhật ký thao tác, không phải sự thật nghiệp vụ.

## C. Đầu ra — agent ghi gì, hiện ở đâu

Mỗi kết luận của agent là **một nhận định**, mang đủ 10 mục của hiến pháp §13.
Cần một bảng mới (⚙ migration, Mức 3, kế hoạch riêng). Tạm gọi là `agent_nhan_dinh`:

| Cột | Hiến pháp §13 |
|---|---|
| `loai` (vd `khach_cho_qua_nguong`), `correlation_id` (lượt) | 1. Tình huống |
| `bang_chung_event_ids uuid[]` | 2. Bằng chứng |
| `muc_bang_chung` ∈ `quan_sat`/`suy_ra`/`du_bao` + `do_chac` (0–1) | 9. Độ tin cậy, và §3.3 |
| `rui_ro`, `de_xuat`, `phuong_an_khac` | 3, 4, 10 |
| `vai_nhan` / `nguoi_nhan`, `han` | 5. Người chịu trách nhiệm, 6. Thời điểm |
| `su_kien_xac_nhan` (loại sự kiện chứng minh đã xong) | 7, 8. Kết quả mong đợi, cách xác nhận |
| `che_do` ∈ `shadow`/`hien`, `trang_thai`, `ket_qua`, `nguoi_quyet`, `ly_do` | Đóng vòng lặp |
| `agent_version` | Truy được bản nào nói gì |

Kèm ba sự kiện:

- `agent.flagged`: mở nhận định.
- `agent.recommendation_resolved`: người bấm Áp dụng hoặc Bỏ qua, có lý do.
- `agent.closed`: sự kiện xác nhận đã tới, hoặc hiện trạng đã đổi nên hết cần.

**Hiện ở đâu:** qua chuông `thong_bao`, người nhận lấy theo `day_nhan_thong_bao`
(quản lý chỉnh trên màn, không viết cứng trong code). Telegram **không** dùng cho
agent ở giai đoạn đầu.

## D. Quyền — đi theo giai đoạn, không nhảy cấp

| Giai đoạn | Agent làm | Điều kiện để lên giai đoạn sau |
|---|---|---|
| **0. Shadow** | Ghi nhận định `che_do='shadow'`, **không hiện cho ai** | ≥ 2 tuần dữ liệu thật; độ đúng ≥ ⚖ (đề xuất 80%) khi so với việc trưởng ca thực sự đã làm |
| **1. Observe** | Hiện chuông cho đúng vai | Tỉ lệ bị bỏ qua < 30%; không ai phàn nàn bị réo |
| **2. Recommend** | Chuông có 2 nút **Áp dụng** / **Bỏ qua (lý do)**. Bấm Áp dụng thì vẫn gọi đúng lệnh thường của người, ghi `reason='theo đề xuất #id'` | Mỗi loại đề xuất tự đủ điều kiện riêng |
| **3. Act** | **Danh sách cho phép đang RỖNG.** Mỗi mục thêm vào cần PR riêng, Quang duyệt, và thoả đủ 6 điều của hiến pháp §14 | — |

Mỗi **loại** nhận định có giai đoạn riêng. Loại A có thể đã ở mức 2 trong khi
loại B mới ở mức shadow.

**Cấm vĩnh viễn**, kể cả khi ở giai đoạn 3:

- chẩn đoán, chọn hoặc đổi chỉ định chuyên môn;
- thu tiền, hoàn tiền, sửa giá, ghi công nợ;
- sửa hay xoá dữ liệu nghiệp vụ, phát sự kiện bù thay người;
- gửi bất kỳ tin nào cho khách;
- đổi quyền, lịch trực, dây nối, ngưỡng, luật;
- khoá hay chặn thao tác của nhân viên (CLAUDE.md #7: mọi thao tác hoàn tác được).

## E. Ngân sách chú ý

Thực thi hiến pháp §3.8 và §12 bằng con số (⚖ số đề xuất, chờ chốt):

- Tối đa **3 chuông agent / người / giờ**. Vượt mức thì gom thành một chuông tóm tắt.
- Cùng một chuyện (cùng `loai` + `correlation_id`) chỉ báo lại khi **nặng hơn**,
  hoặc sau 30 phút chưa ai xử lý.
- **Trước khi bắn phải kiểm lại hiện trạng**, theo luật 2 của `hen_gio`: báo sai
  là cách nhanh nhất dạy người ta bỏ qua mọi lời báo.
- Sự kiện phát lại (`replay_id` có giá trị) thì **im lặng**.
- Một loại nhận định có > 50% bị Bỏ qua trong 1 tuần thì tự lùi về shadow, và báo
  quản lý một lần.

## F. Nhân viên — không thành công cụ giám sát

Hiến pháp §9 và §22 kéo nhau ngược chiều. Luật tách như sau:

- Màn chung chỉ hiện số **theo phòng / vai / ca**, không xếp hạng cá nhân.
- Số theo từng người (vd "quá tải kéo dài") chỉ hiện cho **chính người đó** và cho
  ⚖ (quản lý? Quang?), và luôn đi kèm nguyên nhân hệ thống (hiến pháp §3.9).
- Agent không dùng `actor_staff_id` để kết luận về năng lực ai.

---

## G. Dữ liệu khách — NĐ 13/2023 ⚖

Dữ liệu sức khoẻ là **dữ liệu cá nhân nhạy cảm**. Dr4Women lại là phụ khoa/nam
khoa, nên đến cả *tên dịch vụ* cũng có thể nhạy cảm.

- **Giai đoạn 0–1 rule-only: không dữ liệu nào rời VPS.**
- Khi bật LLM, chỉ được gửi: mã lượt **giả danh** (đổi theo từng lần gọi),
  khoảng thời gian, mã phòng, **nhóm** dịch vụ (không gửi tên), và loại sự kiện.
  **Không bao giờ gửi:** tên, SĐT, ngày sinh, địa chỉ, mã khách, nội dung khám,
  kết quả, ảnh, chữ tự do.
- Không ghi prompt/phản hồi có dữ liệu khách vào log thường.
- ⚖ **Chờ Quang chốt / hỏi người hiểu luật:**
  1. Có được gửi nhóm dịch vụ ra nước ngoài không?
  2. Đã có thoả thuận xử lý dữ liệu với Anthropic chưa?
  3. Có cần hồ sơ đánh giá tác động khi chuyển dữ liệu ra nước ngoài không?
     Cần đối chiếu cả NĐ 13/2023 và Luật Bảo vệ dữ liệu cá nhân 2025; AI không
     tự kết luận phần này.

## H. Chữ trong dữ liệu là dữ liệu, không phải lệnh

- Giai đoạn 0–2 không đọc chữ tự do (mục B), nên phần lớn đường tiêm lệnh đã bị chặn.
- Khi LLM được đọc chữ: bọc chữ trong khối đánh dấu là dữ liệu, và đầu ra **chỉ**
  là JSON theo schema cố định. LLM **không có tool ghi nào**: mọi hành động đi
  qua code, theo danh sách cho phép ở mục D.
- ⚙ Đề xuất: agent dùng một **vai Postgres riêng**, chỉ có quyền ghi
  `agent_nhan_dinh`, `thong_bao` và phát `agent.*`. Khi đó Postgres ép quyền,
  không dựa vào việc prompt nói "không được".

## I. Dữ liệu đã biết là xấu — agent phải loại ra

1. **Lượt hồ sơ cũ từ Notion** (`lich_su_notion.luot_that`): chỉ có ngày (giờ
   00:00 là giả), cố ý không có dòng thu. Loại khỏi mọi phân tích thời gian và tiền.
2. **Trước 23/09/2026 chưa có `domain_event`**, chỉ có `event_log` (nhật ký thao
   tác). Lịch sử trước mốc này không dùng để "học".
3. **Bấm Bắt đầu/Hoàn tất là mốc thời gian, không phải bằng chứng** (luật "open":
   không khoá, sửa được). Ghi là `quan_sat` cho việc bấm, nhưng chỉ là `suy_ra`
   cho việc làm thật (hiến pháp §3.3).
4. **Khách `DEMO-*`, tài khoản `@dr4women.local`** chỉ có ở local; staging đã che
   tên. Số đo ở hai nơi này không phải số thật, không được dùng để chốt ngưỡng.
5. **Độ phủ sự kiện chưa đo.** Trước khi một luật dựa vào "sự kiện X không xuất
   hiện", phải chứng minh X **luôn** được phát: có test, hoặc đếm đối chiếu với bảng
   hiện trạng. Từng có ca vãng lai tự check-in mà không phát `visit.checked_in`.
   Thiếu phủ thì agent sẽ báo "khách bị quên" cho khách đang được phục vụ bình thường.

## J. Khi agent sai hoặc sập

- **Công tắc tắt** (⚙ chưa có, phải có trước giai đoạn 0): mỗi `loai` có một dòng
  cấu hình `tat`/`shadow`/`hien`/`de_xuat`. Đổi bằng màn quản lý hoặc một lệnh
  UPDATE, **không cần deploy**.
- **LLM sập:** quay về rule/template (ADR-0005). Không im lặng như thể mọi thứ bình
  thường: ghi rõ "chưa phân tích được" (hiến pháp §3.2).
- **Trần chi phí theo ngày:** ADR-0005 có ghi nhưng **code chưa có**
  (`src/clinicai/llm/anthropic_client.py` mới có `max_tokens`). Phải làm trước khi
  bật LLM. Model đang ghim trong `llm/models.py` (Sonnet 4.6 / Haiku 4.5), chọn lại
  lúc bật và ghi vào `agent_version`.
- **Lỗi của agent** đổ vào `loi_nhom` / `canh_bao` như mọi lỗi khác. Agent hỏng thì
  không được làm hỏng đường phục vụ khách: bên nghe lỗi chỉ làm lời nhắc chậm lại,
  không chặn lệnh của người.

## K. Đo — nhận định cũng cần "test" như code

- Mỗi `loai` có: **độ đúng** (tỉ lệ người Áp dụng, hoặc ở shadow là trưởng ca tự
  làm đúng như thế), **tỉ lệ bỏ qua**, **thời gian từ lúc phát hiện tới khi có
  người xử lý** (`thong_bao.da_xu_ly_luc − agent.flagged`), và **chỉ số đối trọng**
  (hiến pháp §21). Ví dụ: "chờ ngắn lại" phải đi kèm "giờ check-in có bị nhập trễ
  không".
- **Bộ ca vàng:** dựng từ mô phỏng `scripts/mo-phong/` (ngày khám giả lập). Mỗi
  luật có ca phải báo, ca không được báo, và ca dữ liệu rác (luật repo: đầu vào
  ngày giờ rác thì trả rỗng, không ném lỗi).
- Mỗi bước lên giai đoạn (mục D) dựa trên số, không dựa trên cảm giác.

## L. Học — agent đề xuất, người duyệt

Agent **không bao giờ tự sửa luật, ngưỡng hay policy** (TAM-NHIN điểm 5). Muốn đổi
thì agent lập một **bản đề xuất kèm bằng chứng**, vd "ngưỡng chờ SA2 20′ → 30′,
vì 14/20 lần báo bị Bỏ qua kèm lý do 'đang làm bình thường'". Người duyệt rồi đổi
trên màn cấu hình hoặc qua PR, giống hệt vòng PR-review đang chạy.

---

## Lộ trình trước khi bật (mỗi bước một PR)

| # | Việc | Mức |
|---|---|---|
| 1 | Đưa hiến pháp vào repo `docs/ai/HIEN-PHAP-AGENT.md`; Quang duyệt bản hợp đồng này | 1 |
| 2 | Đo độ phủ cho các sự kiện mà use case đầu dùng (`visit.checked_in`, `service.routed`, `service.started`, `service.completed`, `visit.checked_out`, `visit.left_early`, `patient.contacted`) | 1–2 |
| 3 | Migration: `agent_nhan_dinh` + cấu hình bật/tắt theo loại + vai Postgres riêng + 3 sự kiện `agent.*` vào catalogue | **3**: kế hoạch duyệt trước |
| 4 | Use case 1, rule-only, **shadow**: *khách đang ở phòng khám, chờ quá `dispatch_threshold`, và chưa có `patient.contacted` sau khi bắt đầu chờ* (dạng thô của UnexplainedWaitRisk) | 2 |
| 5 | Sau ≥ 2 tuần shadow: đọc số, quyết định lên giai đoạn 1 | — |
| 6 | Thêm `muc_bang_chung` + `do_chac` cho sự kiện suy ra (nối tiếp `tk-ai-placement` Phase B) | 3 |
| 7 | Trần chi phí theo ngày + giả danh dữ liệu, rồi mới bật LLM (chỉ để tóm tắt) | 2 |

Use case 1 có một chỗ hở cần ghi rõ: `patient.contacted` là CSKH liên hệ khách,
**chưa** phải "đã giải thích lý do chờ tại chỗ". Muốn đo đúng thì cần ghi nhận
giải thích (communication coverage, `tk-experience-state`). Shadow sẽ cho biết
chỗ hở này lớn tới đâu.

## Chờ Quang chốt ⚖

1. Ngưỡng độ đúng để rời shadow (đề xuất 80%) và ngân sách chuông (3/người/giờ).
2. Ai được xem số theo từng nhân viên (mục F).
3. Ba câu về dữ liệu ra nước ngoài (mục G).
4. Use case đầu tiên: "chờ quá ngưỡng chưa ai báo" (đề xuất), hay "khách có nguy
   cơ bị quên", hay việc khác Quang thấy đau hơn.
5. Agent nói với **vai** nào trước: trưởng ca, CSKH, hay cả hai.
