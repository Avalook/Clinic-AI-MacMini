> LỖI THỜI (chuyển legacy 01/10/2026): phép đo 16/09, đúng tại thời điểm, không còn ai trỏ tới — đừng làm theo.

# Cập nhật tính năng mà không làm phiền khách · và mất mạng thì sao

> Hai câu Tuyền hỏi 16/09/2026. Trả lời bằng số đo trên chính máy chủ thật,
> không bằng lý thuyết.

## 1. Deploy hiện tại làm gián đoạn bao lâu — **13 giây**

Đo thật: gõ trang `https://dr4women.io.vn/login` mỗi giây trong lúc chạy
`docker compose up -d --force-recreate api dashboard`.

```
13:21:08–13:21:12   200   (4 giây bình thường)
13:21:13–13:21:25   502   ← 13 GIÂY TRANG CHẾT
13:21:26–…          200
```

13 giây ấy, người đang bấm nhận **502**. Bản nháp trong máy họ không mất (xem
§3), nhưng thao tác đang gửi thì hỏng và phải bấm lại.

### Vì sao 13 giây
`--force-recreate` **dừng container cũ trước rồi mới dựng container mới**. Giữa
hai việc đó Caddy không có ai để chuyển tiếp → 502. Dashboard Next.js mất ~10s
để sẵn sàng, API ~3s.

### Ba mức xử lý, theo thứ tự rẻ-tiền-trước

**Mức 1 — CHỌN GIỜ (làm được ngay, tốn 0 đồng).**
Phòng khám nhận lịch 08:00–21:30. `CLAUDE.md` đã có luật: deploy prod chỉ trong
khung **1h–4h sáng**. 13 giây lúc 2 giờ sáng là 13 giây không ai thấy. **Đây là
câu trả lời đúng cho quy mô hiện tại** — mọi thứ dưới đây chỉ cần khi phòng khám
chạy 24/7 hoặc khi một lần deploy không thể đợi tới đêm.

**Mức 2 — LUẬT VIẾT MIGRATION (bắt buộc, kể cả khi deploy ban đêm).**
Lược đồ đi trước code, và **một bản phát hành phải chạy được với CẢ code cũ lẫn
code mới**:

| Được | Không được trong cùng một lần phát hành |
|---|---|
| thêm cột cho phép NULL | đổi tên cột |
| thêm bảng, thêm index | xoá cột đang có code đọc |
| thêm giá trị vào CHECK | siết CHECK chặt hơn |
| thêm hàm mới | đổi chữ ký hàm đang được gọi |

Muốn xoá/đổi tên thì làm **hai lần phát hành**: lần một thêm cái mới và ghi cả
hai; lần hai, sau khi code cũ đã chết hẳn, mới xoá cái cũ. 25 migration đưa lên
hôm nay đều là loại "thêm" nên deploy theo thứ tự lược đồ-trước-code là an toàn.

Cách hôm nay đã làm, giữ nguyên: **sao lưu → migration → `NOTIFY pgrst` → dựng
lại code → quét màn**.

**Mức 3 — HAI BẢN API CHẠY SONG SONG (khi thật sự cần 0 giây).**
Caddy chuyển tiếp tới hai container api; dựng bản mới, đợi nó `healthy`, rồi mới
tắt bản cũ. Giá phải trả: gấp đôi RAM cho lớp api (máy có 7,8 GB, đủ) và **mọi
migration bắt buộc phải tương thích ngược** — vì trong vài giây chuyển giao, hai
phiên bản code cùng đọc một database. Chưa đáng làm bây giờ; ghi ra đây để lần
sau không phải nghĩ lại từ đầu.

### Quay lui khi bản mới hỏng
`deploy-backend.sh` giữ ảnh cũ và bản `.env` đã đóng băng theo từng lần phát
hành, nên quay lui là đổi thẻ ảnh chứ không phải dựng lại từ mã nguồn. **Thứ
KHÔNG quay lui được là migration** — đó chính là lý do luật ở Mức 2 tồn tại.

---

## 2. Đang làm mà mất mạng thì sao

Phân biệt ba chỗ đứt, vì cách chữa khác hẳn nhau.

### ① Mất mạng ở phòng khám (máy trạm ↔ VPS)
Trang không tải được, thao tác đang gửi hỏng.

**Cái đã có:**
- Bản gõ dở nằm trong `localStorage` máy trạm, hạn 24 giờ
  (`lib/luu-nhap.ts`) — bệnh án, phiếu khám, form khách mới. Mất điện giữa
  chừng, bật lại vẫn còn. Khoá theo người đăng nhập và theo lượt khám, và từ
  16/09 khoá theo cả TAB (`lib/ma-tab.ts`) nên hai tab không đè nhau.
- Màn nói rõ **"Mất kết nối tới máy chủ — chưa lưu"**, không giả vờ đã lưu.
- Mọi cửa ghi quan trọng nhận `Idempotency-Key`, nên **bấm lại sau khi mạng về
  không tạo bản ghi thứ hai** (đặt lịch, sinh hiệu, chỉ định, thanh toán).

**Cái chưa có:** hàng đợi tự gửi lại khi mạng về. Hiện người dùng phải tự bấm
lại. Với một phòng khám có mạng ổn định thì chấp nhận được; nếu mạng hay chập
thì đây là việc đáng làm tiếp.

**Việc KHÔNG nên làm:** cho phép làm việc offline rồi đồng bộ sau. Hai người
cùng check-in một bệnh nhân khi offline thì lúc nối lại không có cách nào đúng
để hoà giải — và đây là hồ sơ bệnh án, không phải ghi chú cá nhân.

### ② Mất mạng giữa VPS và database
Không xảy ra: database chạy **trên chính VPS ấy** (xem `DANG-LAM` mục −0002).
Đây là lý do không được tách database sang nhà cung cấp khác.

### ③ VPS chết hẳn
Đã diễn tập: sao lưu đêm 02:15 lên Viettel Storage (SMB3 mã hoá), và
`restore-drill.sh` đã nạp thử thành công — **16/16 mục trên bản dump thật**.
`/ops` hiện mốc diễn tập và kêu khi nó quá 30 ngày.

Thứ vẫn mất nếu VPS chết giữa ngày: **mọi thứ nhập từ 02:15 tới lúc chết**. Muốn
nhỏ hơn thì phải sao lưu dày hơn (mỗi giờ) hoặc bật WAL archiving. Chưa làm.

---

## 3. Bảng tra nhanh khi có sự cố

| Triệu chứng | Nhìn vào đâu | Thường là gì |
|---|---|---|
| Trang 502 vài giây | vừa deploy? | bình thường, 13 giây |
| Trang 502 kéo dài | `docker compose ps` | container không lên — xem `docker logs` |
| Đăng nhập được, một màn đỏ "Could not find a relationship" | PostgREST | quên `NOTIFY pgrst, 'reload schema'` sau migration |
| Cả API chết sau khi đổi `.env` | log api | thiếu biến môi trường bắt buộc |
| Một vai làm gì cũng 403 | `staff.auth_user_id` | tài khoản chưa gắn hồ sơ nhân sự |
| Màn chậm bất thường | `/ops/telemetry` | xem p95 theo route, rồi `pg_stat_statements` |
