# Kiểm toán toàn hệ thống ClinicAI — 27/09/2026

Phạm vi: repo (main `809feb8`), stack local và VPS prod `clinic-vps-moi` (prod đang chạy `87ae7d1`).
Cách làm: 4 agent quét song song, chỉ đọc. Trên prod chỉ lấy số đếm, không đọc dữ liệu bệnh nhân. Các phát hiện quan trọng tôi kiểm lại bằng tay.

Bản gốc chi tiết của 4 agent (có dòng code cụ thể và số đo cấu hình máy chủ) không đưa vào repo; các ý chính được tóm ở dưới.

---

## 0. Tóm tắt một màn hình

| Mảng | Kết luận |
|---|---|
| Tốc độ | ✅ Tốt. Prod: p50 **66 ms**, p95 **267 ms** (log Caddy 24h); `/login` từ ngoài vào khoảng 104 ms. Sự kiện p95 khoảng 1 giây, 0 tin chết. |
| Chạy đúng nghiệp vụ | ✅ Mô phỏng 23/23. Ngày khám 603 thao tác có 10 hỏng: 1 lỗi thật (**đã sửa**), 4 do kỳ vọng cũ, 5 do DB local không reset. Tầng API: 1.287 lượt gọi, **0 lỗi 5xx**. |
| Theo dõi lỗi | ⚠️ Pha 0 đã lên prod. Nhưng **Kuma rỗng** (0 monitor) nên **không có gì báo động khi sập**, và log vẫn mất mỗi lần deploy cho tới khi chạy script sudo. |
| Máy chủ | ❌ **Ubuntu 25.04 đã hết hỗ trợ** từ 15/01/2026, 8 tháng không có bản vá bảo mật. ⚠️ Tường lửa ufw và fail2ban đang tắt; không có swap. |
| Sao lưu | ⚠️ Backup đêm vẫn chạy và được đẩy lên Viettel CFS. Nhưng **bản kéo về Mac chết từ 12/09** (script còn trỏ IP cũ), còn CFS gắn đọc-ghi ngay trên VPS và không mã hoá: ai chiếm được VPS thì xoá được cả bản gốc lẫn bản sao. |
| Realtime | ❌ Supabase Realtime `postgres_changes` **hỏng** ở cả prod lẫn local: Postgres từ chối plugin `wal2json`, sinh khoảng 8.600 dòng ERROR mỗi ngày. 4 màn (chuông thông báo, trưởng ca, lịch hẹn, checkout) **không nhận được tin tức thời**. |
| Kiến trúc | Lego **6/10** · Open **6/10** · Event-driven **7/10** · Không khoá **8/10** · Frontend mỏng **7/10**. |
| Quyền (lego) | ❌ Gõ thẳng URL vẫn vào được màn thuộc lego đang TẮT: 16 ô lệch. Ngược lại có 8 trang gác bằng vai, nên cấp lego rồi vẫn bị đá về /home. |
| File cũ | Còn khoảng 4,5 MB file thừa chắc chắn. `CLAUDE.md` / `README` / `AGENTS.md` vẫn tả hạ tầng đã chết (staging :8080, `clinic-vps` cũ, CD GitHub, `supabase db push`, "42/63"). |

---

## 1. Đã sửa ngay trong đợt này (PR #213, prod `d210882`)

| # | Lỗi | Sửa |
|---|---|---|
| L1 | Thu tiền xong rồi check-out ngay thì worker vẫn tự xếp phòng, để lại **khách ma** trong hàng chờ phòng | Dây tự xếp phòng xét thêm `visit.closed_at`. Test tái hiện: không có bản sửa thì đỏ, có thì xanh. |
| L2 | **Quản lý bị 403** khi mở hồ sơ khách: lego Bàn khám cộng thêm vai DOCTOR nên rơi vào nhánh "chỉ khách của mình" | Quản lý luôn mở được, xét trước nhánh bác sĩ. Có unit test. |
| L3 | Máy chủ bận (429 / 502 lúc deploy / DB treo) thì **đá người dùng về /login** giữa ca, dù phiên vẫn còn | Chỉ 401/403 mới đá về login. Trường hợp còn lại hiện trang lỗi có nút "Thử lại" (`app/error.tsx` mới). `proxy.ts` tra `staff` hỏng thì cho đi tiếp. |
| L4 | `GET /appointments/policy?date=abc` hoặc `doctor_id=abc` trả **500** (trái luật "ngày giờ rác trả rỗng") | Đầu vào rác thì trả luật mặc định. Có 5 test đầu vào rác. |

---

## 2. Máy chủ prod (audit C)

| Mục | Số đo | Đánh giá |
|---|---|---|
| Tài nguyên | 4 vCPU, load 0.1–0.3; RAM dùng 2.4/7.8 GB; đĩa 39%; 12 container, 0 lần restart | ✅ |
| Swap | 0 | ⚠️ Nếu hết RAM thì tiến trình bị giết thẳng |
| Cổng mở ra ngoài | 22, 80, 443; Kuma, Dozzle, Postgres chỉ nghe trong máy | ✅ |
| ufw / fail2ban | tắt / tắt | ⚠️ SSH 22 mở ra internet mà không chặn dò mật khẩu |
| sshd | file chính ghi `PermitRootLogin yes` + `PasswordAuthentication yes`; drop-in có vẻ ghi đè thành `no` | ⚠️ Cần `sudo sshd -T` để xác nhận |
| TLS | Let's Encrypt, hết hạn 15/12/2026, Caddy tự gia hạn | ✅ |
| Header bảo mật | HSTS, X-Frame, nosniff có; **thiếu CSP**; lộ `x-powered-by` | ⚠️ |
| OS | Ubuntu 25.04, EOL 15/01/2026; kernel mới chờ reboot từ 16/09 | ❌ |
| Event | 457 DONE / 0 DEAD, p95 khoảng 1.07 s; `/health/su-kien` báo ok | ✅ |
| 5xx 24h | 59 lỗi, đều là 502 và trùng giờ deploy (18:47 có 34 cái) | ⚠️ Deploy ban ngày làm người dùng thấy lỗi |
| Dữ liệu trôi | 17 lượt IN_PROGRESS quá 24h; 4 hàng chờ `serving` trên lượt đã FINALIZED; 3 tài khoản `.local` | ⚠️ |
| Rác | Build cache 11.75 GB; 22 volume mồ côi 1.66 GB | ⚠️ Dọn được khoảng 13.4 GB |
| Kuma | 0 monitor, 0 tài khoản, 0 kênh báo | ❌ |
| Log | json-file, mất khi dựng lại container; journald chưa lưu bền | ❌ Đã có script, chờ chạy sudo |

## 3. Kiến trúc so với "lego · open · event-driven · không khoá" (audit B)

- **Lego 6/10:**
  - Được: danh mục 21 lego khớp 100% với thanh bên.
  - Hở: 8 trang và 14 proxy Next gác bằng **vai**. Thanh bên ngày có ca dựng theo vị trí, bỏ qua lego. 3 lego không được backend kiểm (`worklist.handle`, `roster.view`, `partner.work`). Đọc hồ sơ khách và bảng điều phối chỉ cần đăng nhập. Công tắc `MO_QUYEN_TAM_THOI` mặc định "1", tức hỏng thì mở.
- **Event-driven 7/10:**
  - Được: 8/8 thay đổi chính phát sự kiện trong cùng giao dịch.
  - Hở: 6 màn chính vẫn poll mỗi 15–20 giây. Đường `authorize-orders` cũ tự xếp phòng song song với H4. Có hai sổ sự kiện (`event_log` và `domain_event`). `thong_bao` và `phieu_kham_luot` chưa có NOTIFY.
- **Frontend mỏng 7/10:**
  - Route chạm DB trực tiếp giảm từ 42 xuống **2** (`admin/users` và `check-phone`, route sau đã tắt).
  - Còn 123 chỗ `if` theo vai trong TSX.
- **Không khoá 8/10:** phiếu mở, có lịch sử sửa, bất biến ép ở Postgres rất đầy đủ.
- **Open 6/10:** còn GoTrue admin + service-role key ở Next; `supabase-py`, RabbitMQ, `sentry-sdk` là phụ thuộc chết; mã cơ sở Kim Ngưu viết cứng ở 4 file.
- **Chất lượng:**
  - 11 migration bị sửa sau khi đã vào main, và không có bài kiểm nào chặn việc này.
  - 9 module không có test, trong đó có `phan_lo_service`.

## 4. File thừa / cũ dễ hiểu lầm (audit A)

**Xoá được ngay, không rủi ro:**
- `System design/` (3,9 MB, không chỗ nào dẫn tới);
- `src/truong-ca-prototype/`;
- `quan-ly-nhan-su.html` và `logo.png` ở gốc (trùng byte với bản khác);
- `render.yaml`, `vercel.json`;
- `.claude-linear-design.md` (một thông báo lỗi bị commit nhầm) và 2 file 0 byte;
- SQL "dán vào Supabase SQL Editor";
- `_classify_stub_backup.py`.

**Sửa vì nói sai** (agent nào cũng đọc các file này đầu tiên):
- `CLAUDE.md`: staging, `clinic-vps`, CD GitHub, `supabase db push`, "42/63", spec thời Mac mini;
- `README`, `AGENTS.md`;
- SITEMAP ghi MO_QUYEN "đang BẬT";
- `.env.prod.example` trỏ Supabase cloud;
- DANG-LAM §1 còn IP chết;
- `docs/TAI-KHOAN-FINAL-CLOUD.md` ghi mật khẩu chung: nên gỡ khỏi git.

**Theo luật "cũ thì OFF, không xoá", chờ Tuyền duyệt:**
- 17 route đã trả 410;
- khoảng 14 file TSX không ai import;
- `golden_record/`, `event_bus/adapters`;
- router `/orchestrator`, `/tools`, `/voice`;
- nhánh RabbitMQ / Cloudflare / Tailscale;
- tuỳ chọn đẩy backup lên R2 (SO-LUAT đã loại, dữ liệu y tế phải ở trong nước);
- hạ tầng launchd của Mac.

## 5. Chức năng + tốc độ local (audit D)

- Quét 76 route × 11 tài khoản ở tầng web (HTTP có cookie) và 1.287 lượt gọi API: 0 lỗi 5xx.
- API p50 phần lớn dưới 110 ms. Chậm nhất: `/xem-luot` 350 ms, `/dispatch/overview` 314 ms.
- Trang web p50 20–210 ms; riêng `/home` nặng 0,8–1 MB HTML.
- Mỗi lần dựng một trang gọi API 7–13 lần, nên mở khoảng 40 trang/phút là chạm trần 400 lượt/phút của bộ chặn dồn dập. Tôi đã gặp đúng trường hợp này khi bấm thử.
- Màn `/audit-log` báo "lỗi kết nối" trong khi thật ra là thiếu quyền.

---

## 6. Quyết định cần Tuyền chốt (xếp theo mức gấp)

1. **OS hết hỗ trợ:** nâng lên 25.10, hay dựng lại VPS trên **24.04 LTS** rồi chuyển dữ liệu? Tôi khuyên 24.04 LTS, làm trong khung đêm có người xem.
2. **Dựng lại Kuma + kênh Telegram ops**, và chạy `sudo ./scripts/may-chu/bat-theo-doi-may-chu.sh`. Đây là việc của Tuyền vì cần tài khoản và sudo.
3. **Realtime hỏng:** chuyển 4 màn sang SSE `/api/events/stream` (đã có sẵn, là chuẩn mở) rồi tắt Supabase Realtime, hay đổi image Postgres? Tôi khuyên chuyển sang SSE: khớp "open", và bỏ được một container.
4. **Cửa quyền:** trang và proxy chỉ hỏi QUYỀN (lego), bỏ hẳn cửa VAI? Quản lý có ngoại lệ "luôn vào được" không? Thanh bên ngày có ca lọc theo lego? Công tắc `MO_QUYEN` đổi mặc định sang TẮT?
5. **In phiếu ở quầy thu / lễ tân / nhà thuốc:** hiện nút In chỉ hiện với người có quyền đọc hồ sơ khám. Muốn "in ở mọi khâu" thì cấp khối đọc hồ sơ cho các vai này, hay tạo lego riêng "In phiếu cho khách"?
6. **Sao lưu ngoài máy:** sửa `keo-ve.sh` trên Mac (đổi `clinic-vps` → `clinic-vps-moi`), và thêm một nơi lưu **chỉ ghi, không xoá được** từ VPS, có mã hoá.
7. **Deploy ban ngày gây 502:** giữ khung 1–4h, hay cho deploy ngày nhưng thêm trang "đang cập nhật"? (L3 đã bớt phần đá về /login.)
8. **Dọn file thừa và gỡ Sentry / RabbitMQ / Cloudflare / Tailscale:** cho xoá theo danh sách mục 4 không? Sửa `CLAUDE.md` / `README` / `AGENTS.md` ngay?
9. **Dữ liệu trôi trên prod:** 17 lượt treo quá 24h, 4 hàng chờ `serving` trên lượt FINALIZED, 3 tài khoản `.local`. Có chạy script đóng/huỷ theo luật không (không xoá cứng)?
10. **Luật migration:** thêm kiểm checksum vào `ci-may.sh` để chặn việc sửa migration đã đẩy?
