# ADR-0016 — Nhịp làm mới và dòng sự kiện (`src/dashboard/lib/nhip-lam-moi.ts`)

Trạng thái: đang dùng. Chuyển từ đầu tệp code sang đây ngày 20/11/2026 (tệp vượt
trần 400 dòng). Code giữ tóm tắt + đường dẫn tới đây.

## 21/08/2026 — Tab ẩn không giữ kết nối

Người dùng báo "đơ 5–10 phút, bấm nút không ăn, bấm năm lần mới ghi nhận", và
đơ CẢ KHI DÙNG 4G. Giả thuyết ban đầu là bão render: 91 lời gọi
`router.refresh()` nhân với số tab đang mở, dồn lên một tiến trình Node.
Đo xong thì nguyên nhân chính nằm hẳn trong TRÌNH DUYỆT.

EventSource là một kết nối HTTP không bao giờ đóng. Trên HTTP/1.1 trình duyệt
chỉ cho 6 kết nối tới một origin. Mỗi tab mở một EventSource, nên mỗi tab NUỐT
VĨNH VIỄN một trong sáu chỗ ấy:

    số tab mở   1    2    4    5    6
    còn lại     5    4    2    1    0

Đo bằng cách bắn 6 request /home cùng lúc rồi đếm số chạy song song — ra đúng
dãy trên. Tới tab thứ SÁU thì tab mới không tải nổi trang (treo 300 giây), fetch
từ tab cũ cũng treo — trong lúc CPU máy chủ: dashboard 0.03%, api 0.25%, db
0.39%, load 0.43. Phòng khám mở khoảng mười tab: hệ thống không "chậm", nó ĐỨNG
HẲN, và mọi phép đo phía máy chủ đều báo khoẻ.

**Cách chữa: tab nào không ai nhìn thì không giữ gì cả.** Đóng dòng lúc ẩn, mở
lại lúc hiện, rồi làm mới một lượt để bắt kịp. Mười tab mở mà một tab đang nhìn
thì hệ thống dùng MỘT kết nối.

**Đã cân nhắc và bỏ:** bầu một "tab chủ" giữ dòng chung rồi phát lại qua
BroadcastChannel. Cách bầu đáng tin duy nhất là `navigator.locks`, mà Web Locks
chỉ có trong secure context — kiểm trên staging 21/08: `isSecureContext` false,
`navigator.locks` undefined (prod cũng vậy, HTTP thường trên IP). Bản bầu-tab-chủ
sẽ âm thầm rơi về cách cũ đúng ở hai chỗ cần nó nhất, test vẫn xanh vì có Web
Locks giả. Tự bầu bằng nhịp tim BroadcastChannel thì vướng trình duyệt bóp hẹn
giờ tab nền xuống một lần mỗi phút.

**Không thay cho HTTP/2.** HTTP/2 xoá hẳn giới hạn 6 kết nối; kể cả khi có thì
"tab ẩn không dựng lại trang" vẫn đáng giữ. Dựng /home tốn ~163ms CPU (60 lượt =
9.76s CPU container dashboard) trên MỘT tiến trình Node, mà broker phát theo
clinic_id tới MỌI tab đang nghe (`change_broker.py`).

## 20/11/2026 — Tin dồn: khoảng tối thiểu giữa hai lượt làm mới

**Sự cố.** 11:20 chạy xoá lô giả + bù trừ kho trên prod (~1.000 dòng ghi trong
vài chục giây). 11:21–11:27: nhân viên CSKH và màn Kho thấy "Máy chủ đang bận —
bấm Thử lại" (digest 652691283, cùng mã lặp từ 16/11). Log API: cảnh báo
`request_rate_unusually_high` 200–374 lượt/phút/tài khoản, 75 lần 429 ở
11:26–11:27.

**Cơ chế.** Mỗi dòng ghi → `pg_notify` → SSE → `RealtimeRefresher` /
`useNgheBang`. Nhịp cũ gộp 250ms với trần `choToiDa` 600ms → khi tin chảy liên
tục, mỗi tab dựng lại trang ~1 lần/giây; mỗi lượt kéo 6–7 API (`/me`,
`/phan-quyen/toi`, `/appointments/policy`…) → một tài khoản 400+ lượt/phút →
`runaway_guard` (trần 400/phút/tài khoản) trả 429 → `app/(dashboard)/layout.tsx`
thấy `/me` lỗi không phải 401/403 → ném "Máy chủ đang bận".

**Tái hiện.** Staging, code cũ: 600 tín hiệu `prescription` giả trong 60 giây
(`pg_notify('clinicai_changes', …)`, mỗi tín hiệu một giao dịch) → màn lỗi, 10
lần 429.

**Sửa.** `taoNhipLamMoi` thêm `khoangToiThieu` (3 giây trong `NHIP_NGHE_TIN`):
tin LẺ sau lúc yên vẫn làm mới ~1 giây như cũ; tin dồn thì hai lượt cách ≥ 3
giây, và luôn có một lượt SAU tin cuối. Bão DÀY (≥ `TIN_DAY` = 10 tin trong một
lần chờ — script ghi hàng loạt, không phải người bấm) thì khoảng gấp đôi (6
giây), yên 12 giây thì về 3. Kẹp chờ ≤ một khoảng (đồng hồ chỉnh lùi). `batKip`
(quay lại tab) không bị chặn. Ước lượng trong bão: ~10 lượt/phút × 7 API × 3 cửa
sổ cùng tài khoản ≈ 210 < 400. `ClinicalRecordForm` bỏ nhịp 250ms tự chế, dùng
nhịp chung.

**Chưa làm (ghi để mở lại nếu cần):** bỏ `/me` khỏi mỗi lượt `router.refresh()`
(cache theo phiên); `dung-giu-cho.ts` (màn Đặt lịch) vẫn hỏi lại mỗi tin
`slot_hold` không gộp — endpoint nhẹ, không gặp trong sự cố này.
