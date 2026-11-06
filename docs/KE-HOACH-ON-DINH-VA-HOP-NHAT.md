# Kế hoạch ổn định + hợp nhất hệ thống (17/10/2026) — CHỜ DUYỆT

Nguồn số liệu: log thật trên prod (Caddy + GoTrue qua journald/docker logs, chỉ đọc,
đo lúc 03:00 sáng 17/10, không ai dùng). Mỗi con số dưới đây có lệnh đo lại ở mục 7.
Khi kế hoạch được duyệt, file này **thay** `docs/DANG-LAM.md` và mọi `docs/KE-HOACH-*`
làm nơi duy nhất ghi "đang làm gì, vì sao" (xem mục 4).

## 1. Đo được gì (không suy đoán)

| | Ban ngày 16/10 (7–17h) | Tối 14/10 19–20h | Tối 16/10 19–20h |
|---|---|---|---|
| Lượt gọi / giây (trung bình giờ) | 0,5–1,2 | 18,6 | 8,4 |
| Đỉnh 1 phút | — | 34,5/s (20:06) | 16,9/s (19:57) |
| p95 / p99 | 0,2–0,6s / ≤1,2s | 1,5s / 3,1s (20h: 1,7s / 5,4s) | 1,0s / 2,4s |
| Request chậm > 3 giây | ~0 | 706 (20h: 1.285) | 176 |
| Lượt GHI (người bấm/lưu) | — | 1.665 | 1.294 |
| Lần DỰNG LẠI CẢ TRANG (RSC) | — | 16.269 | 8.802 |
| **Dựng lại trang / 1 lượt ghi** | — | **9,8** | **6,8** |
| Giây máy chủ xử lý / giờ | — | 24.082 | 7.723 |

- Mạng phòng khám = `1.52.242.171` (cao điểm mỗi tối 18–21h). `118.70.10.45` = máy Mac dev.
- Cả hệ thống chỉ ~15–26 trình duyệt. **~16 máy sinh 8–34 lượt/giây** ⇒ vấn đề là
  cách thiết kế làm mới, không phải số người.
- 16/10 nhẹ hơn 14/10 ~3 lần sau đợt sửa hiệu năng (cache tĩnh, SQL, pool) — đã đỡ
  phần ngọn, **chưa chạm gốc**.
- Prod đã chạy **HTTP/2** (log `HTTP/2.0`).
- Đăng nhập (GoTrue, 14→17/10): 113 lần đăng xuất, 96 lần `refresh_token_not_found`
  (máy bị đá ra), ~358 lần đăng nhập của người thật / 30 tài khoản (tài khoản nhiều
  nhất: 59 lần đăng nhập, 18 lần đăng xuất / 3 ngày). Thêm 1.058 lần "login" không ghi
  tên người dùng — nghi tài khoản máy/giám sát, CHƯA xác định.

## 2. Nguyên nhân gốc (đã đối chiếu code)

**G1 — Mỗi thay đổi làm MỌI màn đang mở dựng lại TOÀN TRANG.** Ghi dữ liệu → trigger
`notify_row_change` → SSE → `RealtimeRefresher` → `router.refresh()` ở mọi tab đang
hiện (41 bảng trong `LIVE_TABLES`, không trang nào truyền `tables=` hẹp). Một lượt ghi
= 7–10 lần dựng trang (mỗi lần nhiều lời gọi backend) + ~15 lời gọi API.
Tải ≈ (số người đang nhìn) × (số lượt ghi) — **cả hai cùng tăng theo số nhân viên, nên
tải tăng theo BÌNH PHƯƠNG**. 16 người → 100 người ≈ ×6 × ×6 ≈ **×36 tải** nếu giữ thiết kế này.

**G2 — Tự lưu phiếu khám bắn tin cho cả phòng khám.** `trg_notify_phieu_kham_luot`
(migration `20261010100001`) bắn ở MỌI UPDATE; phiếu tự lưu khi gõ → mỗi lần tự lưu
mọi màn nghe `phieu_kham_luot` dựng lại. (`form_instance` thì đã làm đúng: chỉ báo khi
đổi `trang_thai`/`dang_sua`.)

**G3 — Đóng/mở SSE theo tab + làm mới cả trang mỗi lần mở lại.** `lib/nhip-lam-moi.ts`
viết để né giới hạn 6 kết nối của HTTP/1.1. Prod nay là HTTP/2 ⇒ lý do ấy hết, nhưng mỗi
lần đổi tab/cửa sổ vẫn: mở lại SSE + `batKip()` dựng lại trang ngay + mọi widget tự tải lại.

**G4 — Một máy 4 nhân / 7,8 GB / không swap chạy cả prod + staging + build;** API 1
tiến trình uvicorn, dashboard 1 tiến trình Node. Chưa có số đo riêng ảnh hưởng của staging.

**G5 — Một tài khoản không dùng được nhiều máy:** `logout()` và 3 nhánh lỗi ở
`src/dashboard/app/(auth)/login/actions.ts` gọi `supabase.auth.signOut()`; thư viện
`@supabase/auth-js` 2.106 mặc định `scope: 'global'` (đã đọc trong `GoTrueClient.js`)
⇒ một người bấm Đăng xuất là **mọi máy khác dùng cùng tài khoản bị thu hồi phiên**
(tới lần làm mới token kế tiếp, ≤ 1 giờ vì `GOTRUE_JWT_EXP=3600`). Khớp với 96 lần
`refresh_token_not_found` trong log dashboard/GoTrue.

## 3. Việc sửa — theo thứ tự lợi/rủi ro

| # | Việc | Gốc | Mức | Ước | Ai |
|---|---|---|---|---|---|
| S1 | `signOut({ scope: "local" })` ở 4 chỗ `login/actions.ts` (+ soát `ResetPasswordForm`) | G5 | 2 | 30′ | Claude/Codex |
| S2 | Trigger `phieu_kham_luot` chỉ báo khi đổi trạng thái (như `form_instance`), tự lưu không báo | G2 | 3 | 1–2h | Codex, Claude duyệt |
| S3 | Mỗi trang khai `tables=` đúng bảng nó vẽ; mặc định HẸP thay vì 41 bảng | G1 | 2 | 0,5 ngày | Codex |
| S4 | Giữ SSE khi tab ẩn (HTTP/2) + `Last-Event-ID`: mở lại chỉ làm mới khi THẬT SỰ lỡ tin | G3 | 2 | 0,5 ngày | Claude |
| S5 | Staging: giới hạn CPU/RAM (`cpus`, `mem_limit`), cấm build trong giờ khám | G4 | 3 | 1h | Tuyền chạy |
| S6 | Tin SSE mang phạm vi (bảng + id lượt/phòng); màn chỉ tải lại khối bị ảnh hưởng, bỏ `router.refresh()` toàn trang ở màn nóng (Bàn khám, Tiếp đón, Thu ngân, Phòng) | G1 | 3 | 1–2 tuần | Claude thiết kế, Codex làm theo lát |
| S7 | Bài đo tải: phát lại hỗn hợp request THẬT (từ log) ×5/×10 trên staging; chốt SLO p95 < 500ms giờ cao điểm, 0 request > 3s | đo | 2 | 1 ngày | Antigravity viết, Claude duyệt |
| S8 | 2–4 tiến trình uvicorn + chỉnh pool; cảnh báo p95 > 1s, ổ > 85%, staging-nap lỗi, đăng nhập dồn dập | G4 | 3 | 0,5 ngày | Claude soạn, Tuyền chạy |

S1–S5 làm trước (tuần này), mỗi việc một PR nhỏ, lên staging cùng một đợt, deploy ngoài
ca. S6 là thay đổi kiến trúc thật — chỉ làm sau khi S7 có số đo nền để so.

### 3b. Kết quả thực thi 17/10 (đo lại trước khi làm — số đo SỬA kế hoạch)

| # | Kết quả | PR |
|---|---|---|
| S1 | **Xong.** 4 `signOut()` → `{ scope: "local" }` + bài canh. Giữ nguyên `ResetPasswordForm` (đặt lại mật khẩu → đá tất cả, cố ý) và `DoiMatKhauModal` (`others`) | #490 |
| S2 | **Xong, mức 3, chưa áp prod.** Migration `20261017100000`: INSERT/DELETE vẫn báo; UPDATE chỉ báo khi ô `*_follow_date` đổi. Hàm điều kiện không bao giờ ném. 27/27 test DB. **Lợi ích đã hạ:** `/api/phieu-kham` chỉ ~9–15% lượt ghi buổi tối ⇒ giảm ~10–15% lần dựng lại, không phải phần lớn | #492 |
| S3a | **Xong.** `/patients/new` vào `MAN_TU_TAI` (4.346 lần dựng lại/3 giờ cao điểm cho một form không có dữ liệu sống ở server) | #491 |
| S3b | **Chỉ ánh xạ, chưa code — xem dưới.** | — |
| S4 | **BỎ.** Đo log prod 14 và 16/10 (19–20h): chỉ **3–5%** lần dựng lại trang đi ngay sau khi SSE mở lại (= hiện tab); **99,99%** request đã là HTTP/2 (2/29.596 là HTTP/1.1). ~95% lần dựng lại đến từ tin thật, nên thuộc S3/S6 | — |
| S5 | **ĐÃ CÓ từ 14/10, không cần làm.** `cpu_shares: 256`, `oom_score_adj`, `mem_limit`, builder buildx riêng, và `deploy-staging.sh` TỪ CHỐI chạy 7h–21h (`scripts/lib/staging-chung.sh:146-177`, ghi đè bằng `CHO_PHEP_GIO_KHAM=1`). Kế hoạch ban đầu ghi "chưa có giới hạn CPU" là SAI — đã không đọc `docs/STAGING.md` trước | — |

**Đo thứ tự trang tốn nhất (RSC, 16/10 18–21h, 27.349 lần):** `/display` 5.135 (59ms) ·
`/reception/queue` 4.675 (338ms, 1.582s) · `/patients/new` 4.346 (S3a) · `/customers` 2.998
(569ms, **1.705s**) · `/home` 2.737 (505ms, 1.382s) · `/phong/{id}` 2.034 · `/patient-list` 1.778.

**S3b — vì sao KHÔNG chỉ thu hẹp `tables=`** (agent ánh xạ chỉ đọc, 17/10): các bảng nóng nhất
(`appointment`, `visit`, `queue_entry`, `consultation`, `service_order`) nằm trong tập bảng thật
sự đọc của CẢ ba trang. Thu hẹp chỉ cắt phần nhiễu (vật tư, `payment_refund*`, `staff_task`,
`work_item_event`, `kiem_ke_ca`… — /home thừa 24 bảng, /reception/queue 25, /customers 21),
không cắt phần lớn lần dựng lại. Phần lớn chỉ giảm khi **tách ô đếm + danh sách sang client tự
tải** (`useNgheBang`/`docBang`) — chính là S6. Thêm hai phát hiện cần xử lý khi làm:
- `payment_cycle`, `so_no`, `cong_no` CÓ trigger nhưng KHÔNG nằm `LIVE_TABLES` ⇒ chip "Thu
  tiền" và ô "Khách còn nợ" hiện chỉ tươi nhờ nhịp 60s.
- `/customers` mỗi lần dựng trang còn **GHI** `nhac_tai_kham` (`recall_job_service.sinh_viec_nhac_tai_kham`)
  — ghi trong lúc render, nên tăng tải theo số lần dựng lại. Nên tách thành một lời gọi riêng, chạy một lần khi vào màn.

**Đề xuất S6 theo lát (mức 3, chờ duyệt):** (1) `/customers`: tách `recall-jobs` ra khỏi lúc dựng
trang + chuyển khối `danh-sach-khach` sang client tự tải; (2) `/home`: ba ô số + cột tổng quan →
client tự tải; (3) `/reception/queue`: `QueueBoard` sang `docBang`. Mỗi lát một PR, đo trước/sau
bằng `scripts/do-tai` (cùng cách đo ở mục 7), và chỉ lên prod khi số lần dựng lại của trang đó
giảm thật trên staging.

## 4. Một nơi trí nhớ cho MỌI AI

Hiện trạng: trạng thái nằm 3 nơi (`docs/DANG-LAM.md` 2.764 dòng; memory Claude ~200 tệp
trong `~/.claude` mà Codex/Antigravity KHÔNG thấy; ~20 tệp `viec-cho-*` ngoài repo) ⇒
mỗi AI hiểu một kiểu, mâu thuẫn nhau, phình mãi.

Cấu trúc đích (tất cả trong repo, mọi AI đọc qua `AGENTS.md`/`CLAUDE.md`):

```
docs/
  HIEN-TRANG.md        ≤150 dòng: đang chạy bản nào, đang dở gì, chờ ai quyết gì. Chỉ hiện tại.
  CHUAN-CODE.md        MỘT cách làm cho mỗi tầng (router, service, SQL, quyền, màn, gọi API)
  he-thong/<mien>.md   ~20 "thẻ miền", mỗi thẻ ≤150 dòng, cùng một khuôn (dưới)
  quyet-dinh/<ngay>-<ten>.md   mỗi quyết định nghiệp vụ một tệp: ai chốt, ngày, vì sao
  legacy/              lịch sử — không ai phải đọc
```

Khuôn thẻ miền (đặt lịch, tiếp đón, lượt khám, bàn khám, phiếu, chỉ định, phòng dịch vụ,
thu ngân, hoàn tiền, kho thuốc, quầy thuốc, vật tư, liệu trình, CSKH, đối tác, hoá đơn/kế
toán, báo cáo, quyền/lego, lịch trực, sự kiện/realtime, đăng nhập, hạ tầng):
1. Làm gì cho ai (3 dòng) · 2. Màn (route) · 3. API · 4. Service + hàm chính · 5. Bảng +
trigger/sự kiện · 6. Luật bất biến (và ép ở đâu: SQL hay Python) · 7. Lỗi/nợ đang biết ·
8. Test bao quanh · 9. Quyết định liên quan (link `quyet-dinh/`).
Mục 2–5 sinh tự động từ code (mở rộng `scripts/ban-do-code.py`); CI `--kiem` bắt thẻ
trỏ tới file/hàm không còn tồn tại ⇒ tài liệu không thể mục.

Memory của Claude chỉ còn: luật hành vi (cách làm việc với Tuyền) + con trỏ vào repo.

Cách dựng (≈1 tuần, chạy song song):
- **Antigravity** (nhiều tài khoản, ngữ cảnh lớn): mỗi tài khoản đọc 3–4 miền, CHỈ ĐỌC,
  viết thẻ theo khuôn; mọi khẳng định kèm `file:dòng`.
- **Codex**: soát chéo thẻ với code (khẳng định sai → sửa), chạy công cụ tất định
  (vulture, knip, jscpd, radon, import-linter) ra danh sách mã chết/trùng/phức tạp.
- **Claude** (hạn mức ít): duyệt thẻ miền rủi ro (tiền, kho, quyền, đăng nhập), gỡ mâu
  thuẫn, viết `CHUAN-CODE.md` + bài canh kiến trúc.
- **Tuyền/Quang**: chỉ trả lời danh sách "chờ quyết" mà các thẻ gom lại.

Luật chống phình: ai viết ≠ ai duyệt; `HIEN-TRANG.md` > 150 dòng thì CI đỏ; mỗi PR
đổi hành vi phải sửa thẻ miền tương ứng trong cùng PR.

## 5. Đến 100 người dùng

| Ngưỡng | Cần có | Vì sao |
|---|---|---|
| Ngay (16 máy) | S1–S5 | cắt phần nhân bình phương dễ nhất, sửa đăng nhập |
| ~40 máy | S6 + S7 + S8 | bỏ "dựng lại toàn trang"; có số đo năng lực thật |
| ~100 máy / nhiều cơ sở | Tách staging sang máy riêng; prod 8 nhân/16 GB hoặc DB máy riêng; chỉ khi S7 đo thấy cần | đo trước, mua sau (`docs/SO-LUAT.md` Phần 7) |

Không cần Redis / message broker / microservice ở quy mô này: gốc là số lần làm mới
thừa, không phải thiếu hạ tầng.

## 6. Cách quản lý (đề xuất)

- **Đóng băng tính năng 2 tuần** cho S1–S5 + dựng thẻ miền. Yêu cầu mới vẫn nhận, ghi
  vào một hàng chờ, chưa code.
- **Một hàng chờ duy nhất**, mỗi yêu cầu qua "phiếu làm rõ" trước khi code: ai dùng, màn
  nào, trường hợp biên, cách nghiệm thu ⇒ bớt làm sai yêu cầu (hiện fix 255 ≈ feat 253).
- **Giới hạn đang dở**: ≤ 5 PR mở, đợt ≤ 60 commit, deploy chỉ ngoài ca.
- **Chỉ số tuần** (không cảm giác): p95 giờ cao điểm, request > 3s, dựng lại/lượt ghi,
  số lần bị đá đăng nhập, tỉ lệ fix/feat, PR mở, CI đỏ trên `main`.
- **Phân vai**: Quang = thứ tự ưu tiên; Tuyền = duyệt kỹ thuật + nghiệm thu; AI = làm
  theo làn (mục 4); phòng khám = bấm kịch bản trên staging.

## 7. Đo lại (chỉ đọc, chạy ngoài giờ khám)

Script tổng hợp chạy trên VPS bằng `nice -n 19 ionice -c3`, đọc
`journalctl CONTAINER_NAME=clinicai_prod-caddy-1` (container prod log qua journald —
**đừng `journalctl --vacuum` khi chưa trích số liệu**) và `docker logs clinicai_auth`.
Bản script dùng 17/10: đưa vào `scripts/do-tai/` khi kế hoạch được duyệt.
