# Giám sát — cái gì đang được theo dõi, và ai biết điều đó

Thư mục này **từng rỗng hoàn toàn** trong khi Uptime Kuma vẫn chạy trong
`docker-compose.yml`. Toàn bộ danh sách monitor nằm trong volume `kuma_data`,
được bấm tay qua giao diện. Hệ quả:

- Không ai trả lời được câu "hệ thống đang giám sát những gì" mà không mở
  trình duyệt vào máy đó.
- Mất volume (dọn Docker, đổi máy, khôi phục thiếu) là **mất sạch giám sát,
  trong im lặng** — Kuma khởi động lại với 0 monitor và không cảnh báo gì, vì
  đúng nghĩa là không có gì để cảnh báo.
- "Không có cảnh báo nào" và "không có monitor nào" trông giống hệt nhau.

`monitors.json` dưới đây là bản khai báo chính thức. Nó không tự nạp vào Kuma
(Kuma 1.x không có import theo file); nó là **nguồn sự thật để dựng lại và để
đối chiếu**, và `scripts/check-monitoring.sh` so nó với thực tế.

## Nguyên tắc chọn monitor

Ba câu hỏi khác nhau, đừng trộn:

1. **Tiến trình còn sống không?** → Docker `restart:` lo. Không cần Kuma.
2. **Dịch vụ có phục vụ được không?** → `/health/db` (API) và `/health`
   (dashboard, Caddy). Đây là phần Kuma theo dõi.
3. **Nó có ĐANG chạy đúng không?** → độ trễ p95 + lỗi 5xx, xem
   `/ops/telemetry`. Kuma không trả lời được câu này.

Thêm một monitor vào Kuma mà không thêm vào đây là quay lại đúng tình trạng cũ.

## Khôi phục sau khi mất `kuma_data`

```bash
./scripts/check-monitoring.sh          # liệt kê monitor còn thiếu
```

Rồi tạo lại theo `monitors.json` (Kuma → Add New Monitor). Mười phút, và là
mười phút chỉ mất một lần — miễn là file này được cập nhật cùng lúc.

## Cảnh báo gửi đi đâu

Kênh thông báo (Telegram/email) **không** nằm trong file này vì chúng chứa
token. Cấu hình trong Kuma, và ghi tên kênh vào `notification_channels` của
`monitors.json` để biết monitor nào bắn đi đâu.
