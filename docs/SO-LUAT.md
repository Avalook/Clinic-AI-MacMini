# SỔ LUẬT — ClinicAI

Cập nhật: **13/08/2026**

Sổ này là **một** chỗ duy nhất ghi mọi luật của hệ thống. Đọc từ trên xuống là
hiểu cách hệ thống được xây và vì sao nó được xây như vậy.

**Ba điều về sổ này:**

1. **Mọi con số trong đây đều đo được**, không ước. Chỗ nào là ước thì ghi rõ.
2. **Mỗi luật đều có ngưỡng để lật lại.** Luật không có điều kiện lật là giáo
   điều, không phải kỹ thuật.
3. **Luật không có người canh thì không phải luật, chỉ là lời khuyên.** Nên mỗi
   luật ghi rõ *ai canh*: CI, database, GitHub, hay con người.

---

# Phần 1 — Quy mô thật

Mọi thứ trong sổ này treo vào bảng này. Đổi bảng này là phải đọc lại cả sổ.

| | |
|---|---|
| Lượt khám | ~50–80 bệnh nhân/ngày · 1 cơ sở đang mở (Kim Ngưu, 12 phòng) |
| Người dùng | 40 nhân sự · đỉnh vài chục thao tác/phút |
| Tải đo được | **~1 lượt gọi/giây** |
| Database | Postgres 17 tự dựng, **chạy cùng máy** với backend |
| Dữ liệu | 22 MB lúc rời Supabase cloud · nhật ký ~2.400 dòng/ngày (dưới 1 GB/năm) |
| Máy chủ | 1 VPS Vietnix · 4 lõi · 8 GB (đang dùng 37%) · **50 GB đĩa** (14%). Máy Mac chỉ còn nhận bản sao lưu đêm |
| Đội | 1 người + AI |

Hai con số quyết định gần hết mọi thứ: **1 lượt gọi/giây** và **1 người vận
hành**. Mỗi thứ thêm vào là một thứ phải sao lưu, canh chừng, vá lỗi, và khôi
phục lúc 7h sáng khi phòng khám mở cửa.

---

# Phần 2 — Đường đi của code, từ máy Quang tới khách

```
1. Viết code ở nhánh riêng, tên tiếng Việt nói ra việc   (bat-sentry, bang-gia-qua-api)
2. Mở PR vào main → CI chạy 5 chặng → đỏ thì không gộp được
3. Gộp vào main → CI dựng ĐÚNG MỘT ảnh Docker (amd64), đẩy lên kho ảnh,
   dán nhãn bằng mã commit
4. staging TỰ ĐỘNG chạy đúng ảnh đó → vào xem thật ở cổng :8080
5. Ưng → bấm nút "đưa lên prod" trên GitHub
   → prod TẢI ĐÚNG ẢNH staging đang chạy, KHÔNG dựng lại
6. Nút bấm được cả ngày, nhưng máy xếp hàng, chỉ chạy trong 1h–4h sáng giờ VN
7. Xong: khoẻ → đánh dấu phiên bản · không khoẻ → tự trỏ về ảnh cũ
```

**Luật 2.1 — Code chỉ sống ở `main`.** `staging` là cái nhãn trỏ vào thứ đang
chạy trên bản thử, **không bao giờ gộp ngược vào `main`**.
*Vì sao:* đã từng có nhánh `staging` dài hạn và **`main` tụt lại 63 commit** mà
không ai biết; toàn bộ nền multi-tenant chỉ sống trên `staging`.
*Ai canh:* GitHub (khoá không cho gộp ngược).

**Luật 2.2 — Dựng ảnh một lần, chạy đúng ảnh đó ở mọi nơi.**
*Vì sao:* hôm nay CI dựng ảnh để thử rồi vứt, còn máy đích **dựng lại từ đầu**
(`deploy-backend.sh` dòng 262). Thứ được kiểm và thứ chạy cho khách là hai lần
dựng khác nhau — giống nhau hầu hết thời gian, cho tới ngày ảnh nền được nhà
phát hành cập nhật giữa hai lần.
*Ai canh:* CI (chỉ đẩy đi ảnh đã qua kiểm) + deploy script (chỉ tải, không dựng).

**Luật 2.3 — Prod chỉ đổi trong 1h–4h sáng.** Ngoài khung đó, nút bấm được
nhưng máy xếp hàng chờ.
*Ngoại lệ:* cửa vượt cho lúc cháy nhà — bắt gõ lý do, và lý do được ghi lại.
*Bẫy phải tránh:* máy chủ chạy giờ quốc tế; "1h sáng" của nó là **8h sáng** của
mình — đúng giờ đông khách nhất. Giờ phải ghim `Asia/Ho_Chi_Minh`.
*Ai canh:* CD.

**Luật 2.4 — Lùi bản là trỏ lại ảnh cũ, không phải dựng lại code cũ.**

---

# Phần 3 — Logic nằm ở đâu

Đây là luật hay bị hiểu sai nhất. Không phải "mọi thứ ở backend".

| Loại logic | Ví dụ | Ở đâu |
|---|---|---|
| **Quyết định** | còn chỗ không · vai này được đặt lịch không · giá bao nhiêu · ai được mở bệnh án | **Backend + database. Không ngoại lệ.** Trình duyệt sửa được nên không bao giờ tin |
| **Kiểm tra lặp cho mượt tay** | ô ngày kín thì mờ nút · nhập sai định dạng báo đỏ ngay | **Cả hai nơi.** Frontend báo sớm, backend vẫn kiểm lại từ đầu |
| **Trình bày** | sắp xếp · gộp nhóm · định dạng ngày · ẩn hiện cột | **Frontend.** Đúng việc của nó |
| **Nhớ tạm dữ liệu ít đổi** | 5 dịch vụ · 39 chỉ định · danh sách bác sĩ · bảng giá | **Frontend**, tải một lần mỗi phiên |

**Luật 3.1 — Không luật nghiệp vụ nào được chỉ tồn tại ở frontend.**
Kiểm ở frontend là *đếm rồi mới quyết định*, mà giữa lúc đếm và lúc quyết định
thì người thứ hai chen vào được. Chốt chặn thật phải ở database.

**Luật 3.2 — Một file route ở frontend hoặc chỉ chuyển tiếp, hoặc biến mất.**
Không được vừa chuyển tiếp vừa tự truy vấn: lúc đó đường đi thành **hai lượt
HTTP** thay vì một, cộng ~4 ms mà không gộp được gì.
*Hiện trạng:* 63 route · 42 chạm thẳng database · **33 cái đang làm cả hai**.

---

# Phần 4 — Bốn luật giữ ranh giới

**Luật 4.1 — Đường ray một chiều.** Con số "route còn chạm thẳng database" hôm
nay là **42**. CI đếm mỗi lần: thêm cái thứ 43 → đỏ, không gộp được; gỡ được
một cái → hạ mốc, **và không bao giờ cho lên lại**.
*Vì sao thế này mà không dọn một lượt:* dọn 42 chỗ mất hàng tuần, còn hệ thống
thì vẫn phải chạy. Đây là cái chèn bánh xe khi đỗ dốc — không bắt lên đỉnh
ngay, nhưng cấm tụt.
*Ai canh:* CI.

**Luật 4.2 — Nhánh sống tối đa 2 ngày.** Đây là luật về **kích thước một lần
làm**, không phải về thời gian. *Hiện trạng:* 5 PR mở, cũ nhất 11 ngày, ba cái
trong đó cùng đụng phần đăng nhập.
*Ai canh:* một việc chạy hằng ngày, báo danh sách PR quá hạn.

**Luật 4.3 — Gộp xong xoá nhánh ngay.** *Hiện trạng:* 25 nhánh chưa gộp + 7
nhánh đã gộp còn nằm đó, nhìn không phân biệt được cái nào còn sống.
*Ai canh:* GitHub (một ô trong cài đặt).

**Luật 4.4 — Một bảng, một người ghi.** Mỗi bảng khai rõ phần code nào được ghi
vào nó; chỗ khác muốn ghi phải gọi qua đó.
*Vì sao:* bảng `appointment` hôm nay bị ghi từ nhiều nơi; đổi luật "một khung
giờ tối đa mấy người" phải nhớ đủ mọi nơi, quên một chỗ là dữ liệu lệch mà test
khó bắt.
*Cách khai:* **mỗi tính năng một trang** — màn hình nào, đường API nào, hàm xử
lý nào, chạm bảng nào, ai được ghi. Người đọc hiểu, **máy cũng đọc được**.
*Ai canh:* CI đọc trang khai báo.
*Thứ tự:* làm **sau** luật 4.1, vì 42 route frontend chính là đám ghi chéo lớn nhất.

---

# Phần 5 — Tốc độ: cái gì đắt

Đo trên staging 13/08/2026, 60 lượt, từ container giao diện sang container backend:

| | p50 | p95 |
|---|---|---|
| Một lượt gọi backend, **không** chạm database | **4,13 ms** | 6,81 ms |
| Một lượt gọi backend, **có** chạm database | **4,94 ms** | 7,64 ms |

**Một truy vấn database tốn ~0,8 ms. Một lượt đi hỏi tốn ~4 ms.** Đi hỏi đắt
gấp năm lần việc trả lời.

**Luật 5.1 — Một màn hình, một lượt gọi.** Backend viết riêng cho từng màn, gộp
mọi thứ màn đó cần vào **một** câu SQL.
*Bằng chứng đã có:* `reports_service` gộp 8 lượt PostgREST thành 1 `GROUP BY`.
Trang chủ hiện vẫn **11 truy vấn mỗi lần dựng lại** — đó là phần lớn cảm giác chậm.

**Luật 5.2 — Thứ tự tối ưu, đúng theo mức đắt:**
1. Bớt số lượt gọi (4 ms/lượt)
2. Bớt số truy vấn trong một lượt (vòng lặp gọi database 50 lần = 40 ms bốc hơi)
3. Index đúng
4. Cách viết từng dòng code — **cuối bảng**, ở 1 lượt/giây gần như không đo được

**Luật 5.3 — Đo trước khi tối ưu.** Không sửa cho nhanh khi chưa có số nói chỗ nào chậm.

---

# Phần 6 — Hai người cùng thao tác một chỗ

Ba lớp chồng lên nhau. **Phải đủ cả ba**; thiếu lớp 2 thì vẫn đặt trùng được,
chỉ là hiếm nên lâu mới lộ.

| Lớp | Làm gì | Trong hệ thống |
|---|---|---|
| **1. Giữ chỗ mềm** | CSKH đang chọn khung giờ thì người thứ hai thấy "đang có người giữ" | `slot_hold_service` — 10 phút |
| **2. Chốt cứng ở database** | hai lượt ghi đồng thời phải xếp hàng | trigger `enforce_slot_capacity` + khoá theo (bác sĩ, khung 15 phút) |
| **3. Bấm hai lần không tạo hai bản ghi** | mã lần gửi | bảng `idempotency_key` |

**Luật 6.1 — Giữ chỗ là tư vấn, không phải khoá.** Một dòng giữ chỗ bị rò (đóng
trình duyệt giữa chừng) chỉ làm phiền người khác tối đa 10 phút, và **không bao
giờ được làm một lịch hẹn hợp lệ bị từ chối**.

**Luật 6.2 — Mọi bất biến có kẽ hở tranh chấp phải ép ở Postgres**, theo bậc
thang: ràng buộc UNIQUE/CHECK → `UPDATE … WHERE status IN (…)` một câu → trigger
+ khoá tư vấn → hàm RPC khi cần nhiều câu lệnh nguyên khối. **Không tự cài khoá
trong Python.**

**Luật 6.3 — Việc người này ảnh hưởng người kia thì đẩy tin, không bắt hỏi
lại.** Database bắn tin lúc ghi xong (`LISTEN/NOTIFY`) → backend đẩy về màn hình
(SSE) → màn hình **chỉ làm mới đúng phần bị ảnh hưởng**.
*Hiện trạng:* nửa đầu đã xong; nửa sau chưa — mỗi tin về là dựng lại **cả trang**.

**Luật 6.4 — Độ trễ mà người dùng cảm nhận là NHỊP HỎI, không phải máy chủ.**
Đo thật trên staging 14/08/2026 (`scripts/tests/do-giu-cho.py`, ba tài khoản
CSKH thật):

| chặng | thời gian |
|---|---|
| chờ trước khi gửi lệnh giữ chỗ | 400ms |
| máy chủ ghi xong → máy bên kia **đọc được** | **27–40ms** |
| nhịp màn hình bên kia hỏi lại | 0–5s |
| **người bên cạnh thực sự thấy** | ~2,5s trung bình, ~5,4s chậm nhất |

Máy chủ chiếm **dưới 1%** con số ấy. Nhịp từng là 15s (trung bình 8 giây) và
được hạ xuống 5s ngày 14/08 sau khi đo giá: một nhịp tốn **4,8ms** cả chuỗi
(GoTrue xác minh token 2,1ms + FastAPI đọc bảng 2,7ms — `do-nhip-hoi.py`), bốn
CSKH cùng mở màn ở nhịp 5s là **0,4% một lõi**. *Ngưỡng xem lại:* khoảng 30
người cùng mở màn đặt lịch, hoặc khi Luật 6.3 xong nửa sau thì bỏ hỏi lại hẳn.

**Luật 6.5 — Sức chứa là ghế CỦA MỘT BÁC SĨ, và được kiểm lúc XẾP bác sĩ.**
Trigger nói thẳng: *lịch chưa phân bác sĩ thì chưa chiếm ghế của ai*. Nên một
lịch để trống bác sĩ **luôn được nhận**, kể cả khi mọi bác sĩ đã kín — nó vào
hàng chờ xếp, và chỗ vỡ ra (nếu có) là ở bước xếp. Đây là hành vi đúng, nhưng
nó khiến hai phép đo ngây thơ cho kết quả sai: đặt lịch không chọn bác sĩ rồi
kết luận "vượt sức chứa", và đọc `/quote` không kèm `doctor_id` rồi tưởng con
số ấy là trần của cả phòng khám.

---

# Phần 7 — Đừng thêm hạ tầng (và ngưỡng để lật lại)

| Lời khuyên phổ biến | Vì sao không áp ở đây | Lật lại khi |
|---|---|---|
| **Cài Redis** làm cache/session/hàng chờ | Database đứng cùng máy, một truy vấn nóng dưới 1 ms. Cache chỉ mua thêm dữ liệu cũ và một dịch vụ phải sống 24/7 | p95 một màn > 800 ms **và** đã chứng minh nguyên nhân là số vòng, không phải thiếu index |
| **Đẩy nhật ký truy vết qua hàng chờ** | Sai với y tế. Ghi vết đi **cùng transaction** với dữ liệu nó mô tả: hoặc cả hai cùng vào, hoặc không cái nào. Qua hàng chờ thì worker chết = mất vết đúng lúc ghi hỏng nửa chừng | không bao giờ, cho *ghi vết*. Việc đáng đẩy async là *gửi thông báo* |
| **Elasticsearch / ClickHouse cho log** | Dưới 1 GB/năm; Postgres + 5 index nuốt gọn 10 năm | nhật ký vượt ~50 triệu dòng |
| **Xoá log cũ hơn 60 ngày** | **Không xoá được, và đó là chủ ý** — bảng nhật ký có chốt chặn cả xoá lẫn làm rỗng | khi cần: **chia bảng theo tháng rồi tách ra kho lạnh**, không bao giờ xoá |
| **Chạy 3–4 bản sao ứng dụng** | Lời khuyên viết cho Node một luồng. FastAPI async nuốt hàng trăm lượt/giây bằng **một** tiến trình. Và **chưa chạy được 2 tiến trình**: bộ đếm giới hạn truy cập nằm trong RAM một tiến trình | CPU backend > 70% kéo dài; **điều kiện tiên quyết:** chuyển bộ đếm sang Postgres trước |
| **Đẩy file lên AWS S3 / Cloudflare R2** | Đúng hướng "đừng để trên ổ hệ điều hành", sai đích: dữ liệu y tế + hạ tầng trong nước | có kho đối tượng **trong nước** hoặc ổ dữ liệu riêng |
| **Canary 1% → 5% → 100%** | Cần nhiều bản sao và bộ chia traffic. Với một máy, thứ tương đương đã có: kiểm tra sức khoẻ + tự lùi bản | khi có từ 2 máy phục vụ thật |
| **Nginx** | Caddy làm đúng việc đó và tự xin/gia hạn chứng chỉ | — |

**Luật 7.1 — Postgres là hạ tầng có trạng thái duy nhất phía ứng dụng.**
Idempotency, hàng chờ gửi tin, giữ chỗ, giới hạn truy cập, "cache" = index +
view. Ngoại lệ duy nhất đã duyệt: nhận dạng giọng nói chạy tại chỗ (dữ liệu âm
thanh không được rời phòng khám).

**Luật 7.2 — Trước khi đề xuất bất kỳ hạ tầng nào: đưa ra phép đo chứng minh
thứ đang có không đủ.**

---

# Phần 8 — Ghi vết, và tìm lỗi

**Luật 8.1 — Ghi vết đi cùng transaction với việc nó mô tả.** Một vết có thể
thiếu đúng lúc ghi nửa chừng còn tệ hơn không có vết, vì nó đọc như "việc này
không xảy ra".

**Luật 8.2 — Trong vết chỉ có mã số, không có nội dung.** Mã hồ sơ, không phải
nội dung khám. Tên trường đã đổi, không phải giá trị. Màn nhật ký mở cho các vai
vận hành — những người không được mở bệnh án.

**Luật 8.3 — Tìm lỗi bằng mã đi theo request, không bằng chú thích trong code.**
Mỗi lượt bấm nút có một mã; mã đó có mặt trong **mọi dòng log** của lượt đó và
trong báo cáo lỗi. Từ một lỗi → lấy mã → kéo ra toàn bộ hành trình, không cần
tái hiện lỗi trên máy mình.
*Hiện trạng:* `request_id` đã có trong log. **Chưa gắn được vào báo cáo lỗi vì
`sentry-sdk` chưa được cài** — nên hiện tại lỗi của người dùng thật không báo về đâu cả.

---

# Phần 9 — Những quyết định đã chốt trước đây

Dịch sang tiếng Việt, kèm **trạng thái thi hành đo trên code 13/08/2026** —
khác với "đã quyết" là hai chuyện.

| Quyết định | Nội dung | Đã làm chưa |
|---|---|---|
| **Một khối, chia phần rõ** | Một backend duy nhất, chia theo nghiệp vụ; mỗi phần khai bảng nó sở hữu; CI chặn ghi chéo | ❌ **Chưa** — không có trang khai báo nào, CI không kiểm |
| **Gửi tin bằng sổ, không bằng bưu tá riêng** | Bỏ RabbitMQ; dùng bảng nhật ký làm hàng chờ, một tiến trình quét mỗi 30 giây | ❌ **Chưa** — RabbitMQ vẫn khởi động cùng stack, hàm gửi vẫn ném lỗi "chưa làm" |
| **Tranh chấp ép ở database** | Bậc thang ràng buộc → khoá → RPC (Phần 6) | ✅ Đang chạy cho 2+1 và số thứ tự |
| **Cửa vào hai lớp, khoá là mặc định** | Khoá dịch vụ giữa frontend và backend + danh tính từng người trên **100%** đường nghiệp vụ; thiếu khoá thì **không cho khởi động** | ✅ Đang chạy |
| **Không thêm máy móc mới** | Postgres làm mọi việc có trạng thái; trí tuệ nhân tạo gọi qua API ngoài | ✅ Đang giữ đúng |
| **Ngân sách tài nguyên** | Giới hạn RAM từng container; nhận dạng giọng nói tách riêng | ⚠️ Phần giới hạn RAM đã làm; phần Mac mini **đã lỗi thời** — hệ thống chạy trên VPS từ 07/08 |
| **Bộ nhớ hội thoại để riêng** | Trạng thái hội thoại của trợ lý nằm trong lược đồ riêng, mất cũng không mất nghiệp vụ | ✅ |
| **Đính chính bệnh án có đường riêng** | Hồ sơ đã chốt không sửa thẳng; chỉ qua một hàm ghi lý do + vết trước/sau trong một transaction | ✅ |
| **Nhiều phòng khám ngay từ đầu** | 27 bảng mang mã phòng khám; danh mục hành chính quốc gia thì không; một bác sĩ làm nhiều nơi qua bảng thành viên | ✅ |
| **Cổng tích hợp bán hàng để mở** | ClinicAI là nguồn sự thật; hệ thống bán hàng ngoài chỉ được đồng bộ tới, không ghi ngược | ✅ (đang dùng bộ nối rỗng) |
| **Luồng khám là dữ liệu, không phải code** | 37 chặng nằm trong bảng; đổi luồng = sửa dữ liệu; chỉ một đường ghi trạng thái | ✅ |
| **Hợp đồng frontend–backend thay được** | OpenAPI có phiên bản là mặt tiếp xúc duy nhất; frontend chỉ dùng Supabase cho đăng nhập và tin thời gian thực; khoá quyền cao **không** nằm ở frontend | ⚠️ Một phần — 42 route vẫn chạm thẳng database |
| **Chạy được ở đâu cũng được** | Không đường dẫn cứng theo máy, không trạng thái trong container, ảnh dựng cho cả hai kiến trúc, CI kiểm bằng máy Linux | ✅ Đã lên VPS thật |

Ánh xạ sang tên cũ, để đọc được chú thích trong code: một-khối = ADR-0001 ·
gửi-tin = 0002 · tranh-chấp = 0003 · cửa-vào = 0004 · không-máy-mới = 0005 ·
ngân-sách = 0006 · bộ-nhớ-hội-thoại = 0007 · đính-chính = 0008 · nhiều-phòng-khám
= 0009 · cổng-bán-hàng = 0010 · luồng-là-dữ-liệu = 0011 · hợp-đồng = 0012 ·
chạy-đâu-cũng-được = 0013.

---

# Phần 11 — Hình dạng hệ thống sau khi dọn (13/08/2026)

Ghi lại vì trước hôm này nó không có hình dạng nào cả: hai nhánh dài song song,
prod và staging chung một thư mục, và 79 commit của prod chỉ nằm trên một ổ đĩa.

| | |
|---|---|
| Nhánh dài hạn | **`main`** — và chỉ `main` |
| prod | `/home/clinicai/clinicai` trên VPS, đứng ở `main`, cổng 80 |
| staging | `/home/clinicai/staging` trên VPS, đứng ở tag `staging-*`, cổng 8080 |
| Hai thư mục | dùng chung một kho `.git` (worktree) — tách nguồn, không nhân đôi đĩa |
| Lên staging | tự động sau khi CI xanh |
| Lên prod | người bấm, **chỉ 1h–4h sáng**, cửa vượt phải ghi lý do |
| CD chạy ở | runner của **VPS**, không còn dính máy Mac |
| Máy Mac | chỉ còn nhận **bản sao lưu hằng đêm** — chủ ý, vì bản sao phải ở máy khác |

**Luật 11.1 — Một nhánh dài hạn.** Đã hỏng hai lần vì luật này bị bỏ qua: `main`
tụt 63 commit sau `staging`; rồi một nhánh `codex/…` sống 11 ngày, đi trước 204
commit và đi sau 122.

**Luật 11.2 — Code đang chạy phải có bản sao ngoài máy chạy nó.** Ngày 13/08
phát hiện 79 commit của prod chưa từng lên GitHub, vì máy chủ không có quyền
push. Ổ đĩa hỏng là không dựng lại được thứ đang phục vụ bệnh nhân.

**Luật 11.3 — Mỗi môi trường một thư mục.** Chung thư mục thì một lần `git
checkout` đổi luôn nguồn của môi trường kia, và không ai thấy cho tới lần deploy
sau.

---

# Phần 10 — Điều gì làm sổ này phải viết lại

Bốn thay đổi lật được kết luận ở trên, theo thứ tự sức nặng:

1. **Vượt ~500 bệnh nhân/ngày**, hoặc mở thêm cơ sở phục vụ thật → tính lại
   toàn bộ Phần 7, kể cả Redis và nhiều bản sao.
2. **Database tách khỏi máy chạy backend** → truy vấn không còn dưới 1 ms, lập
   luận "không cần cache" mất chân đế.
3. **Có người vận hành thứ hai** → chi phí "một thứ nữa phải nuôi" giảm hẳn.
4. **Ràng buộc pháp lý mới** về lưu trữ hoặc truy vết → xem lại Phần 8 trước tiên.
