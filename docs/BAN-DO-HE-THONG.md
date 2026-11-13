# Bản đồ hệ thống — mở cái nào khi muốn biết gì

Gom 23/10/2026 từ các đợt soát bằng cloud (#533–#538). Code soát: `main` @ `00bde524`,
đúng bản prod đang chạy. Ba trang HTML đều **tự chứa**: tải về, bấm đúp là mở, không cần mạng.

| Muốn biết | Mở | Ghi chú |
|---|---|---|
| **Sửa gì trước, theo thứ tự nào** | [`VIEC-CAN-LAM.md`](VIEC-CAN-LAM.md) | 10 việc + phân loại 56 PR + kế hoạch 4 tuần. Thước đo duy nhất cho đợt sửa tới. |
| **Bấm một nút thì đi qua đâu** — logic, bảng SQL, sự kiện, thời gian, khi 1.000 người cùng bấm | [`lego/index.html`](lego/index.html) | 74 thao tác · 23 khối · 126 bảng · 97 sự kiện · 39 đề xuất. Chấm đỏ/vàng/xanh; "đã đo" vs "ước". |
| **Hệ thống chạy ở đâu, request đi thế nào, bảo mật, số đo thật** | [`he-thong/index.html`](he-thong/index.html) | 5 tab: Môi trường & request · Lượng request (đo thật) · Bảo mật 9 lớp · Bảng điều khiển 8 trang · Có cần Redis/RabbitMQ. |
| **Học thuộc hệ thống theo nghiệp vụ** | [`so-hoc/index.html`](so-hoc/index.html) | 12 khối, 90 màn, 59 đường đi, từ điển tên code ↔ tên dễ hiểu, thẻ tự kiểm. |
| **Vì sao chậm, sửa thế nào cho đúng tiền** | [`RA-SOAT-TOC-DO.md`](RA-SOAT-TOC-DO.md) | Từng chỗ N+1 / tải lại dây chuyền, tệp:dòng, 19 PR chia 3 đợt. |
| Muốn sửa gì thì vào màn / tệp nào | [`BAN-DO-SUA.md`](BAN-DO-SUA.md), [`BAN-DO-CODE.md`](BAN-DO-CODE.md), [`SITEMAP.md`](SITEMAP.md) | Có từ trước. |
| Luật hệ thống, thứ đã cân nhắc và loại | [`SO-LUAT.md`](SO-LUAT.md) | Phần 7: hạ tầng đã loại + ngưỡng mở lại. |

Bản gộp ngoại tuyến: [**Bản đồ ClinicAI — một tệp, có minh hoạ động**](ban-do-clinicai.html) · sinh lại bằng `python3 scripts/ban-do-mot-tep.py`.

## Số đo thật mới nhất

`he-thong/so-do.json`, đo chỉ đọc từ Mac. Đo lại và nhúng vào trang bằng một lệnh:

```bash
python3 scripts/do-so-do.py --nhung
```

Script gửi `scripts/so-do/caddy.py` và `scripts/so-do/vps.sh` vào `ssh clinic-vps-moi` với ưu tiên
thấp; không ghi gì lên VPS, không in IP hay thông tin khách. Hai bẫy đã gặp khi đo (đã chặn trong script):
`journalctl` bằng user `clinicai` trả rỗng im lặng → dùng `docker logs`; Caddy prod đứng trước cả
staging và giám sát → lọc theo tên miền.

## Cập nhật các trang khi code đổi

```bash
python3 scripts/lego-data.py           # bản đồ lego; --kiem: báo tệp:dòng hỏng
python3 scripts/he-thong-data.py --so-do docs/he-thong/so-do.json
python3 scripts/so-hoc-data.py
```

Phần viết tay (lời giải thích, đề xuất, thẻ học) nằm ở `*/viet-tay.json` của từng trang — sửa ở đó
rồi chạy lại script, đừng sửa `index.html` bằng tay.
