# ClinicAI UI Quality Contract v0.1

**Mục đích:** tài liệu bàn giao cho AI coding agent (Codex / Claude Code / agent tương đương) khi bắt đầu sửa giao diện ClinicAI sau này.

**Trạng thái:** `[CHỐT-TUYỀN]` về hướng UI/UX và nguyên tắc triển khai. Tài liệu này **không tự đồng nghĩa PM/bác sĩ đã phê duyệt nghiệp vụ**, và **không phải lệnh sửa code ngay bây giờ**.

**Ngày đóng gói:** 22/09/2026.

---

## 0. Cách dùng tài liệu này

AI coding agent phải đọc tài liệu này **trước khi sửa UI** và dùng nó như hợp đồng chất lượng. Tài liệu trả lời ba câu hỏi:

1. UI ClinicAI phải hành xử như thế nào.
2. Phần frontend hiện tại nào nên giữ, phần nào phải chuẩn hóa.
3. AI phải chứng minh thay đổi bằng browser/visual QA thế nào trước khi báo xong.

Không dùng tài liệu này để tự đổi nghiệp vụ, phân quyền, state machine, database, migration hoặc API contract.

### Trước mọi lần code

Agent phải xác minh lại:

- repo đang làm;
- branch;
- HEAD SHA;
- working tree sạch/bẩn;
- route chuẩn trong `docs/SITEMAP.md`;
- luật giao diện hiện hành trong `DESIGN.md`;
- chỉ dẫn repo trong `CLAUDE.md`, `AGENTS.md`, `docs/DANG-LAM.md` nếu còn áp dụng;
- component/primitives đang tồn tại trước khi tạo component mới.

**Không được lấy SHA audit trong tài liệu này làm bằng chứng code vẫn y nguyên.**

---

# 1. Nguồn và ranh giới

## 1.1. Nguồn bàn giao dự án

- `ClinicAI-CONTEXT-v1.0.md`: bản bàn giao để hiểu bối cảnh và nguyên tắc làm việc; không phải toàn bộ thiết kế đã được phê duyệt.
- `NGUON-PM-v1.0.0.txt`: yêu cầu/kế hoạch từ PM; nơi mâu thuẫn phải hỏi lại.
- `NGUON-ARTIFACT-QUANG.md`: nguồn định hướng về event/state/work item/role view; không phải mọi chi tiết đều là implementation đã duyệt.
- `NGUON-REVIEW-KY-THUAT.md`: snapshot review kỹ thuật lịch sử, không tự coi là hiện trạng.

## 1.2. Nguyên tắc ưu tiên

- Lời chốt rõ của Tuyền cho UI/UX > tài liệu UI cũ > thói quen code cũ.
- Code hiện tại là bằng chứng triển khai, **không phải chân lý thiết kế**.
- Không chọn nguồn thuận tiện để tự giải quyết mâu thuẫn.
- Khi UI contract xung đột với nghiệp vụ/permission thật, **không đổi nghiệp vụ để vừa UI**; đưa mâu thuẫn ra để chốt.

## 1.3. Ranh giới không được tự mở rộng

- Không thêm Flutter chỉ để làm mobile.
- Không thêm CRDT chỉ để giữ form.
- Không thêm offline-first.
- Không thêm microservices/event sourcing.
- PWA không đồng nghĩa cache hồ sơ lâm sàng để dùng offline.
- Không thay đổi database/migration khi nhiệm vụ chỉ là UI.
- Không tự đổi role/permission; menu ẩn không bao giờ được coi là lớp bảo mật.

---

# 2. Tư tưởng UI gốc

ClinicAI là **phần mềm vận hành phòng khám**, không phải landing page hoặc dashboard trang trí.

Mục tiêu ưu tiên:

1. Người dùng luôn biết **mình đang ở đâu**.
2. Luôn biết **đang xử lý ai/cái gì**.
3. Thấy được **trạng thái hiện tại** và **hành động tiếp theo**.
4. Bấm nút phải có phản hồi rõ; không để người dùng đoán thao tác đã lưu hay chưa.
5. Nội dung y tế/vận hành phải ưu tiên độ rõ, tốc độ và giảm lỗi hơn hiệu ứng thẩm mỹ.
6. Giao diện đẹp bằng **tính nhất quán, nhịp spacing, typography, hierarchy, feedback**, không bằng nhiều màu hoặc animation.
7. **Feature work must not invent a new visual language.** Tính năng mới dùng hệ component/token hiện có; thiếu primitive thì bổ sung primitive trước.
8. Không clone Apple/Vercel/Linear. Có thể học mức hoàn thiện nhưng phải giữ bản chất phần mềm vận hành y tế của ClinicAI.

---

# 3. App Shell Contract

## 3.1. Kiến trúc shell

Dùng **Responsive Hybrid Shell**.

### Desktop / màn rộng

```text
┌──────── Sidebar ────────┬──────────────────────────────┐
│ ClinicAI                │ Global App Bar               │
│ Các khu vực chính       ├──────────────────────────────┤
│ theo vai/quyền          │ Page Header                  │
│                         ├──────────────────────────────┤
│                         │ PAGE CONTENT                 │
└─────────────────────────┴──────────────────────────────┘
```

### Mobile / PWA

```text
┌──────────────────────────┐
│ ←  Page title        ⋯   │
├──────────────────────────┤
│ PAGE CONTENT             │
│                          │
├──────────────────────────┤
│ frequent destinations    │
└──────────────────────────┘
```

**Không thu nhỏ desktop sidebar thành một sidebar bé trên điện thoại.**

## 3.2. Sidebar

Sidebar desktop chỉ phục vụ:

- điều hướng khu vực chính;
- báo vị trí hiện tại;
- các mục tài khoản/hệ thống phù hợp.

Không nhét patient detail, trạng thái phòng hoặc dữ liệu nghiệp vụ chỉ vì còn chỗ.

Menu có thể lọc theo role/permission/vị trí làm việc, nhưng:

> **backend vẫn là authority; menu không phải security boundary.**

## 3.3. Global App Bar và Page Header phải là hai khái niệm khác nhau

**Global App Bar**: context toàn ứng dụng như account, clinic/location, thông báo, global status.

**Page Header**: màn hiện tại, context hiện tại, Back và action của chính màn.

Không lặp title nhiều lớp gây tốn chiều cao.

## 3.4. App-level Back

Các deep screen phải có Back thuộc ứng dụng.

Không triển khai chỉ bằng `history.back()`.

Thuật toán mục tiêu:

1. Nếu có prior ClinicAI route hợp lệ trong cùng flow → quay về route đó và khôi phục context phù hợp.
2. Nếu mở deep-link trực tiếp / PWA cold start → quay về **canonical parent** của màn.
3. Không đưa người dùng ra website ngoài, trang trắng hoặc route vô nghĩa.
4. Browser Back vẫn phải hoạt động; app Back và browser history không được đánh nhau.

Ví dụ:

```text
Danh sách → BN A → Hồ sơ
Back Hồ sơ → BN A / danh sách với context phù hợp
```

Deep-link thẳng vào Hồ sơ:

```text
Back → màn cha hợp lý trong ClinicAI
```

## 3.5. Cảnh báo an toàn về state khi làm Back

Code audit cho thấy shell hiện dùng `key={pathname}` để remount page khi đổi route nhằm tránh state form của bệnh nhân trước bị tái sử dụng cho bệnh nhân sau.

**Không được xoá cơ chế này chỉ để giữ filter/scroll.**

Thiết kế Back phải giữ đồng thời hai điều:

```text
Không mang draft/form BN A sang BN B
+
Back vẫn phục hồi được context danh sách cần thiết
```

Filter/search/tab/scroll nên có storage/navigation strategy riêng (ví dụ URL hoặc navigation state phù hợp), không giữ clinical form sống qua route chỉ vì tiện.

## 3.6. Content width

Không dùng một `max-width` toàn hệ thống.

Mỗi screen chọn một preset đã đặt tên:

- `standard`: hồ sơ/form/màn thông thường;
- `wide`: bảng/lịch nhiều cột;
- `full`: điều phối, floor/ops board, màn cần toàn chiều ngang.

Page không tự invent width riêng nếu chưa có lý do và primitive tương ứng.

## 3.7. Persistent shell

Khi đổi route:

- sidebar/header không flash hoặc dựng lại vô ích;
- loading chủ yếu nằm ở vùng content;
- shell phải tạo cảm giác ứng dụng ổn định, không phải mỗi màn là một website khác.

---

# 4. Navigation và Page Header Contract

Mỗi màn nghiệp vụ phải trả lời được ngay:

- Tôi đang ở màn nào?
- Tôi đang xử lý ai/ca nào nếu có?
- Trạng thái chính là gì?
- Tôi có thể làm gì tiếp?
- Tôi quay lại đâu?

Page Header chuẩn gồm tối đa:

```text
Back | title/context | primary/secondary actions
sub-context nếu thực sự cần
```

Mobile phải **condense**, không được mất title/context quan trọng.

Không dùng Global Header để nhồi tất cả date/clock/profile/notification nếu điều đó làm mất page identity trên mobile.

Canonical parent map phải được khai tập trung; không để mỗi page tự nghĩ một Back khác nhau.

---

# 5. Button và Control Contract

## 5.1. Một hệ Button duy nhất

Các variant chuẩn:

- `primary`
- `secondary`
- `ghost`
- `danger`

Không tự tạo kiểu nút thứ năm tại màn hình bằng chuỗi class dài nếu ý nghĩa đã thuộc một variant có sẵn.

## 5.2. Ngữ nghĩa HTML đúng

- Hành động → `<button>`.
- Điều hướng → `<Link>`/anchor phù hợp.
- Nút trong form mặc định phải tránh submit ngoài ý muốn (`type="button"` khi không submit).

## 5.3. Touch target

Các thao tác chính trên mobile/PWA cần target gần **44px trở lên** theo contract mới.

Nếu design system hiện dùng cỡ nhỏ hơn, điều chỉnh ở primitive sau khi kiểm tác động, không vá từng màn.

## 5.4. Text và overflow

Nút không được:

- tràn chữ khỏi khung;
- cắt chữ quan trọng thành câu không hiểu được;
- co chiều ngang làm label đọc sai nghĩa.

Dùng `min-width: 0`, wrapping, truncate hoặc responsive action layout theo ngữ cảnh; không dùng một quy tắc duy nhất cho mọi nút.

## 5.5. Trạng thái bắt buộc

Action async phải có đủ trạng thái thích hợp:

```text
idle → pending → success/error
```

Trong khi pending:

- chống bấm lặp khi cần;
- label phản ánh đang xử lý;
- không báo thành công trước response hợp lệ.

---

# 6. Form & Input Contract

## 6.1. Field primitive

Mục tiêu là gom presentation field về một hệ chung có thể biểu diễn:

- label;
- required;
- unit;
- hint;
- error;
- read-only/disabled;
- pending/saving nếu cần.

Không bắt mọi form dùng cùng layout; nhưng typography, state và interaction phải cùng ngôn ngữ.

## 6.2. Mobile

- Không ép label cạnh input nếu làm input quá hẹp.
- Input text trên iOS phải tránh kích hoạt auto-zoom không chủ ý.
- Target tương tác đủ lớn.
- Khi chọn item ở danh sách dài rồi form nằm phía dưới, UI phải đưa người dùng tới vùng làm việc hợp lý.

## 6.3. Read-only phải nhìn ra read-only

Ô không sửa được không được trông giống ô có thể nhập.

## 6.4. Validation

- Lỗi gần field khi có thể.
- Nội dung lỗi nói người dùng phải làm gì.
- Frontend validation chỉ giúp thao tác; backend vẫn quyết định tính hợp lệ nghiệp vụ.

## 6.5. Draft / concurrency

UI không được che giấu xung đột phiên bản.

Nếu backend trả stale/revision conflict:

- không tự overwrite;
- nói rõ có bản mới;
- cung cấp đường xử lý an toàn.

---

# 7. Data Display Contract

## 7.1. Một renderer cho một khái niệm

Cùng một status/domain status không được mỗi màn tự map màu/label khác nhau nếu có thể dùng shared renderer.

Mục tiêu:

- `StatusChip` cho trạng thái;
- `Chip` cho nhãn/metadata không phải trạng thái;
- shared `StatCard` cho KPI/filter;
- table/card primitive cho danh sách.

## 7.2. Status không chỉ bằng màu

Luôn có text/icon/hình dạng đủ để hiểu khi không phân biệt được màu.

## 7.3. Table responsive

Hai chiến lược:

**Danh sách thông thường:** dưới tablet có thể chuyển row → card.

**Bảng vận hành rộng/lưới:** giữ bảng và cuộn ngang **bên trong container**, không để toàn body cuộn ngang.

## 7.4. Dense nhưng không ngộp

ClinicAI có dữ liệu dày, nhưng hierarchy phải rõ:

- tên/đối tượng chính nổi bật;
- metadata thấp hơn;
- trạng thái/action dễ quét;
- không kẻ grid dày như spreadsheet nếu whitespace/hairline đã đủ.

---

# 8. Feedback, Loading, Error và Realtime Contract

## 8.1. Không im lặng

Mọi thao tác quan trọng phải có phản hồi.

## 8.2. Không khẳng định quá bằng chứng

Sau lỗi network/render, nếu hệ thống không biết chắc transaction đã commit hay chưa, UI không được nói chắc "thất bại".

Nên hướng người dùng kiểm tra lại state trước khi bấm lần nữa.

## 8.3. Loading

- Shell giữ nguyên.
- Content có skeleton/loading phù hợp.
- Không làm toàn app nhấp nháy khi chỉ data vùng nhỏ đang tải lại.

## 8.4. Empty

Empty state phải phân biệt khi phù hợp:

- thật sự chưa có dữ liệu;
- bộ lọc không có kết quả;
- không có quyền;
- kết nối lỗi;
- đang tải.

## 8.5. Realtime freshness

Nếu ứng dụng dùng SSE/realtime/poll fallback, UI cần có vocabulary cho các trạng thái khi đáng kể:

```text
Online
Reconnecting
Offline / mất kết nối
Data may be stale
Session expired
```

Không cần biến mọi reconnect ngắn thành banner lớn; nhưng người dùng phải được biết khi độ mới dữ liệu không còn đáng tin.

---

# 9. Responsive / Mobile / PWA Contract

## 9.1. Same capability, adapted interaction

Mobile giữ **cùng capability nghiệp vụ**, nhưng interaction được sắp lại theo touch và không gian nhỏ.

Không bê nguyên desktop layout rồi scale xuống.

## 9.2. Bottom navigation

Bottom nav chỉ chứa một số ít destination thường dùng theo vai/vị trí + `More/Menu`.

Không nhét toàn bộ sidebar xuống bottom nav.

## 9.3. Safe areas và keyboard

PWA/mobile shell phải xử lý:

- notch;
- home indicator;
- keyboard;
- viewport resize;
- sticky/fixed controls không che content.

## 9.4. PWA scope

Một PWA baseline có thể gồm:

- manifest;
- icon/app metadata;
- installable shell nếu phù hợp;
- offline shell rất hạn chế nếu có lý do.

**Không cache indiscriminately patient/clinical data.**

PWA **không đồng nghĩa offline-first**.

---

# 10. Visual Foundation Contract

Giữ tư tưởng hiện có trong `DESIGN.md` và token system, trừ khi Tuyền chốt thay đổi visual direction sau này.

## 10.1. Không invent màu/kích thước/bo góc

Agent ưu tiên token/design scale hiện có.

Nếu thật sự cần giá trị mới:

1. chứng minh scale hiện tại không biểu diễn được;
2. thay đổi design system có chủ đích;
3. không chèn `[..px]`/hex lẻ ở một page rồi bỏ mặc.

## 10.2. Reskin tương lai

Business/domain behavior phải tách khỏi visual primitives để sau này có thể đổi:

- màu;
- type;
- radius;
- shadow;
- component skin;

mà không viết lại workflow.

Do đó feature mới **không được hardcode visual language riêng**.

---

# 11. Accessibility Contract

Tối thiểu phải bảo đảm:

1. Root language đúng ngôn ngữ UI.
2. Keyboard dùng được cho navigation/control quan trọng.
3. Focus-visible rõ.
4. Modal/drawer có focus management.
5. Escape/close semantics hợp lý.
6. Icon-only action có accessible name.
7. Status/priority không chỉ dựa màu.
8. Contrast đạt mức đọc được theo token system.
9. Touch target đủ lớn trên mobile.
10. Reduced-motion được tôn trọng.
11. Form label/error liên kết có nghĩa cho assistive tech.
12. Heading/landmark không dùng chỉ để trang trí.
13. Disabled/read-only state không gây hiểu nhầm.
14. Thay đổi UI quan trọng phải được kiểm bằng browser, không chỉ lint/build.

---

# 12. Performance Contract

UI nhanh theo cảm nhận trước hết bằng:

- shell ổn định;
- giảm round-trip không cần thiết;
- parallelize request độc lập;
- tránh re-render toàn page khi chỉ một vùng thay đổi nếu có thể;
- không prefetch hàng loạt force-dynamic screen;
- loading phản hồi tức thì;
- chỉ tối ưu sau khi đo.

Không thêm hạ tầng chỉ để chữa UI chậm nếu chưa chứng minh bottleneck.

---

# 13. QA Contract — AI không được chỉ “code rồi build xanh”

Một thay đổi UI không được báo hoàn tất chỉ vì:

```text
TypeScript pass
ESLint pass
Next build pass
```

AI phải theo vòng:

```text
design intent
→ code
→ render browser
→ interact
→ resize
→ screenshot
→ kiểm lỗi
→ sửa
→ regression check
```

## 13.1. Viewport tối thiểu

Nghiệm thu ít nhất:

- **375px** — phone;
- **768px** — tablet/narrow desktop boundary;
- **1280px** — desktop.

Nếu screen đặc thù rộng, bổ sung viewport phù hợp nhưng không bỏ ba baseline trên.

## 13.2. Browser checks tối thiểu

- không body horizontal overflow;
- không button/text overflow;
- Back đúng route;
- tab/filter/selected state đúng;
- loading/error/empty hợp lý;
- keyboard navigation cơ bản;
- modal/drawer close/focus;
- touch layout không bị fixed element che;
- screen critical không carry state patient trước;
- screenshot đủ để reviewer nhìn được trước/sau.

## 13.3. Visual regression

Mục tiêu bổ sung Playwright screenshot regression cho:

- App Shell desktop/mobile;
- PageHeader/Back;
- Button/Field primitives;
- table/card representative screens;
- một số screen critical theo vai.

Không cần snapshot mọi pixel của mọi màn ngay lần đầu; bắt đầu từ primitives + representative screens rồi mở rộng dần.

---

# 14. Baseline audit code — 22/09/2026

## 14.1. Repo đã xác minh

Audit read-only đã xác định:

```text
repo   : Avalook/Clinic-AI-MacMini
branch : main
SHA    : 99c3e0ec9c88e9153866fcd2908ceb02ea72c1f7
```

SHA trên là remote `main` tại thời điểm audit.

**Local/VPS working tree: CHƯA XÁC MINH.**

Trước khi coding, phải xác minh lại target thực tế.

## 14.2. Bảng đối chiếu hiện trạng

| Hạng mục | Kết luận | Bằng chứng/ý nghĩa |
|---|---|---|
| App Shell | `GIỮ` | `Shell.tsx` đã có desktop sidebar, mobile drawer, BottomNav, focus trap, safe area |
| Sidebar/Nav role logic | `GIỮ` | desktop/mobile dùng chung logic lọc; backend vẫn phải là authority |
| Page Header + Back | `REFACTOR` | có `GlobalHeader` và title logic nhưng chưa có PageHeader/Back/canonical parent system |
| Button | `GOM COMPONENT` | shared `components/ui/Button.tsx` tốt nhưng raw button và `BTN/BTN_GHOST` vẫn tồn tại |
| Responsive | `GIỮ + SỬA NHẸ` | có breakpoint, container query, mobile shell; vẫn còn ad-hoc sizing cần giảm dần |
| Form | `GOM COMPONENT` | có `INPUT/LABEL`, form logic tốt nhưng chưa có Field primitive thống nhất |
| Status/Chip | `GOM COMPONENT` | có shared `StatusChip/Chip`; vẫn còn renderer riêng như `StatusBadge` |
| StatCard | `GOM COMPONENT` | tồn tại shared bản mới và một bản dashboard cũ riêng |
| Loading/Error | `GIỮ + SỬA NHẸ` | có skeleton/error boundary tốt; cần feedback về freshness/network state |
| Visual tokens | `GIỮ` | `DESIGN.md`, `globals.css`, living `/design-system`, boundary tests đã có nền tốt |
| Accessibility | `SỬA NHẸ + QA` | nhiều aria/focus/reduced-motion đã có; root `lang="en"` không khớp UI tiếng Việt |
| Touch size | `SỬA NHẸ` | shared Button `lg` hiện 40px, contract mới muốn gần 44px+ trên mobile |
| PWA installability | `CHƯA CÓ` | audit không thấy manifest/service worker/install flow; hiện mới là responsive/mobile web |
| Visual regression | `CHƯA CÓ` | Playwright dependency có nhưng chưa thấy screenshot regression/axe/lighthouse gate |
| Working tree thật | `CHƯA XÁC MINH` | GitHub remote không chứng minh VPS/local sạch |

---

# 15. Các phát hiện code cần xử lý khi bắt đầu implementation

## 15.1. GlobalHeader parse identity có nguy cơ sai tên người

Audit thấy layout tạo identity dạng:

```text
role · staff name · clinic/location
```

nhưng `GlobalHeader.tsx` lấy phần tử cuối bằng `.at(-1)` làm `staffName`.

Nếu clinic/location tồn tại, phần cuối không còn là tên nhân viên.

**Hướng sửa:** truyền identity có cấu trúc (staff name / role / place) thay vì nối string rồi parse ngược.

Trạng thái: `BÁO CÁO CODE — cần kiểm lại ở target SHA trước sửa`.

## 15.2. Root language

`app/layout.tsx` tại baseline dùng:

```html
<html lang="en">
```

trong khi UI là tiếng Việt.

Hướng dự kiến: `lang="vi"` nếu target app vẫn chỉ tiếng Việt; kiểm trước khi sửa.

## 15.3. Duplicate primitives

Đang có dấu hiệu hai thế hệ UI cùng sống:

- shared `components/ui/StatCard.tsx` và dashboard `StatCard.tsx`;
- shared `StatusChip` và `StatusBadge` riêng;
- shared `Button` và raw button / `form-ui` BTN strings.

**Không xoá hàng loạt.** Migrate theo screen group, có browser QA.

## 15.4. Realtime freshness chưa được biểu diễn đầy đủ

Hệ thống đã có SSE + fallback refresh, nhưng người dùng chưa có một contract UI rõ khi reconnect/offline/stale.

Không tự suy rằng dữ liệu đang realtime chỉ vì EventSource tồn tại.

---

# 16. Những thứ hiện tại nên giữ

- `DESIGN.md` như nền visual hiện hành, sau khi reconcile với contract này.
- token trong `globals.css`.
- shared `Button`, `Chip`, `StatusChip`, `StatCard`, `Stepper` làm điểm xuất phát.
- living `/design-system`.
- mobile drawer/focus handling trong `Shell`.
- BottomNav role-aware và safe-area logic.
- container queries trong workspace khi phù hợp.
- boundary tests chống drift.
- px-ratchet: số ad-hoc px chỉ được giảm.
- error message kiểu “có thể đã lưu, hãy kiểm tra” thay vì khẳng định sai.
- cơ chế remount route để không carry patient form state qua bệnh nhân khác, cho tới khi có phương án an toàn hơn được chứng minh.

---

# 17. Những thứ không được làm trong đợt UI refactor

- Không rewrite toàn frontend.
- Không đổi business workflow để tiện layout.
- Không gộp nhiều route vì thấy UI giống nhau nếu SITEMAP/nghiệp vụ chưa cho phép.
- Không xoá safety remount mà chưa có test patient-state isolation.
- Không thêm design library/component framework mới chỉ vì agent quen dùng.
- Không tự đổi màu/status semantics.
- Không dùng hidden menu làm permission gate.
- Không cache clinical data offline chỉ để đạt nhãn PWA.
- Không báo “xong” nếu chưa bấm/nhìn trên browser ở viewport yêu cầu.

---

# 18. Trình tự implementation đề xuất

Đây là **đề xuất thứ tự**, không phải lệnh code tự động.

### Phase 0 — Verify target

Xác minh repo/branch/SHA/working tree, đọc SITEMAP + DESIGN + contract này.

### Phase 1 — Reconcile contract với design system hiện hữu

Mục tiêu: không để `DESIGN.md` và tài liệu này trở thành hai hiến pháp mâu thuẫn.

Đặc biệt chốt rõ:

- typography authority (tài liệu cũ nói system stack trong khi code baseline dùng Inter);
- touch target 40 vs 44px+;
- breakpoint nomenclature;
- PageHeader/Back chưa có trong DESIGN hiện tại.

### Phase 2 — PageHeader + Back foundation

Thêm primitive/navigation contract tập trung và pilot trên vài route đại diện.

Nghiệm thu ít nhất ba tình huống:

1. danh sách → hồ sơ → Back;
2. QR/deep-link → record → canonical parent;
3. PWA/direct open → business screen → Back an toàn.

### Phase 3 — Consolidate primitives

Migrate dần:

- Button;
- Field/Input;
- Status/Chip;
- StatCard;
- table/list helpers.

Không migration toàn repo trong một PR.

### Phase 4 — Visual QA harness

Thiết lập browser screenshot checks cho shell/primitives/representative screens ở 375/768/1280.

Sau đó mới dùng “build xanh + visual xanh” làm định nghĩa chất lượng UI.

### Phase 5 — Mobile/PWA baseline

Thêm manifest/installability và connection-state UX nếu scope được chốt.

Không offline-first.

### Phase 6 — Migrate theo nhóm màn

Ưu tiên screen đang dùng thật theo `docs/SITEMAP.md`; không sửa route đã redirect/gộp.

### Phase 7 — Visual direction/reskin nếu cần

Chỉ sau khi structure/QA ổn định mới đổi “áo” toàn hệ thống bằng tokens/primitives.

---

# 19. Definition of Done cho một PR UI

Một PR UI chỉ được coi là hoàn tất khi phù hợp với phạm vi của nó và có bằng chứng:

```text
[ ] Đúng route chuẩn trong SITEMAP
[ ] Không đổi nghiệp vụ ngoài scope
[ ] Reuse primitive/token hiện có hoặc bổ sung primitive có lý do
[ ] TypeScript/lint/build xanh
[ ] Relevant boundary/unit tests xanh
[ ] Browser test thực tế
[ ] 375 / 768 / 1280 không vỡ
[ ] Không body horizontal overflow
[ ] Keyboard/focus cơ bản ổn
[ ] Loading/error/empty/pending được kiểm
[ ] Back/navigation được kiểm nếu có đụng
[ ] Screenshot trước/sau hoặc regression evidence
[ ] Ghi rõ màn → nút/link → route/API → vai thấy
[ ] Không báo “xong” cho phần chưa bấm thật
```

---

# 20. Prompt mở đầu gợi ý cho AI coding agent

Có thể đưa nguyên tài liệu này cho AI rồi dùng prompt ngắn sau:

> Đọc `ClinicAI-UI-QUALITY-CONTRACT-v0.1.md`, `DESIGN.md`, `CLAUDE.md`, `docs/SITEMAP.md` và `docs/DANG-LAM.md` trước khi sửa. Chỉ làm đúng work item tôi giao. Trước khi code, báo repo/branch/SHA/working tree và các file sẽ đụng. Không đổi business logic, permission, DB hoặc migration nếu chưa được yêu cầu. Reuse component/token hiện có; feature không được invent visual language. Sau code phải tự kiểm browser ở 375/768/1280, interaction/loading/error/focus/overflow và đưa bằng chứng screenshot/test. Nếu source hoặc contract mâu thuẫn, dừng ở điểm mâu thuẫn và nêu hai cách hiểu; không tự chọn nguồn thuận tiện.

---

# 21. Phiếu đóng tài liệu

**Đã chốt:** UI Quality Contract v0.1 đủ để làm nền hướng dẫn AI coding và audit UI sau này.

**Đã xác minh:** baseline GitHub remote `Avalook/Clinic-AI-MacMini/main@99c3e0ec9c88e9153866fcd2908ceb02ea72c1f7`; App Shell/tokens/primitives hiện có nhiều phần đáng giữ.

**Chưa xác minh:** local/VPS working tree, runtime deployment SHA hiện tại, browser visual state toàn bộ màn.

**Nguồn:** ClinicAI CONTEXT v1.0, PM source, Quang artifacts, technical review snapshot, GitHub read-only audit 22/09/2026, cùng các quyết định UI đã chốt trong phiên thiết kế.

**Ảnh hưởng:** frontend shell/navigation/components/responsive/PWA/accessibility/performance/QA; không tự thay đổi nghiệp vụ hoặc database.

**Tài liệu repo cần cập nhật khi bắt đầu code:** reconcile với `DESIGN.md`; nếu thêm/đổi route thì cập nhật `docs/SITEMAP.md` theo luật repo.

**Bước tiếp khi Tuyền yêu cầu code:** Phase 0 verify target → PageHeader/Back pilot → primitive consolidation → visual QA harness.
