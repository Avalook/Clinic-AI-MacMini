# ADR-0006 — Ngân sách tài nguyên Mac mini M4 Pro 48GB: Colima VM codified, mem-limit từng container, voice tách khỏi api

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-18 |
| **Deciders** | Quang |
| **Liên quan** | Design doc v5 §5.8; khảo sát 18-07 (đo thực tế) |

## Context
Hiện KHÔNG có `mem_limit`/`cpus` nào trong compose (grep = 0); Colima VM size cấu hình
tay (đo được 7.7GiB) không nằm trong git — host rebuild là mất; PhoWhisper lazy-load
1–3GB vào **chính api process** ở lần gọi /voice/transcribe đầu tiên; Next build ăn
2–4GB có thể chạy đè giờ khám; đang có stack thứ 3 `clinicai_opsacceptance` ngoài quản
lý; weekly `docker volume prune` có thể xoá kuma_data/caddy_data nếu stack down đúng
lúc chạy. Một container leak hiện có thể ăn cả VM và đè prod.

## Decision
1. **Codify Colima VM** trong `clinic-backend-boot.sh`: `colima start --cpu 8 --memory 16
   --disk 100` (M4 Pro 12 core / 48GB → VM 8 core / 16GB).
2. **`mem_limit` mọi service** trong compose: api 1G (prod) / 768M (staging), dashboard
   512M, caddy 128M, relay 256M, kuma 256M, dozzle 128M, voice 3G (profile riêng).
3. **Voice tách container riêng** (`voice`, profile `voice`) — model không load trong
   api process; api gọi qua HTTP nội bộ.
4. Ngân sách tổng (đỉnh): macOS+nền 8G · VM 16G (prod ~2.3G + staging ~2G + voice 3G +
   build headroom 6G + slack) · dự phòng ngoài VM ~24G không cam kết.
5. Dọn drift: xoá/quản lý stack `opsacceptance`; redeploy prod đúng compose; **bỏ
   `docker volume prune`** khỏi cleanup script (giữ `system prune` có filter).
6. Build CD nếu được thì lệch giờ vắng; giữ image tag `-prev` để rollback không phụ
   thuộc prune 7 ngày.

## Considered Options
| Phương án | Ưu | Nhược |
|---|---|---|
| **A (chọn) VM 16G + limit từng container** | cô lập lỗi; ngân sách rõ; host còn 24G cho tương lai | limit sai → OOMKill service (chọn số dư dả, có Kuma alert) |
| B Không limit (hiện trạng) | không bao giờ OOMKill oan | 1 leak đè cả prod+staging; không đo đếm được |
| C VM to hơn (32G) | thoải mái | chiếm RAM host vô ích; macOS cần RAM cho FS cache |

## Consequences
**Tích cực:** "một container leak không thể giết phòng khám"; cấu hình sống trong git —
host rebuild được. **Tiêu cực:** phải theo dõi OOMKill 2 tuần đầu để chỉnh số; voice
thành 1 service mới (nhưng đằng nào cũng phải tách vì 1–3GB).
