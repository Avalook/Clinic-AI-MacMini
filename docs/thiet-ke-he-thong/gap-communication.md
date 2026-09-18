---
title: "Khoảng cách 8 — Communication: attestation tốt, delivery kém; sent = done; không coverage window"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "bat-dang-thuc ↔ tuong_tac_cskh / relay"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 8 — Communication: attestation tốt, delivery kém; sent = done; không coverage window

> [!abstract] Với bệnh nhân: sổ chạm là bằng chứng đủ ở quy mô này; với nội bộ: Telegram gửi xong là 'xong', không ai biết ai đọc.

Hai kênh, hai tình trạng:

**Với bệnh nhân** (qua CSKH gọi/Zalo cá nhân): `tuong_tac_cskh` ghi có người, có giờ, có kết quả, có `khach_xac_nhan` — «SỔ CHĂM SÓC CHÍNH LÀ BẰNG CHỨNG, ở quy mô hiện tại» (docstring, Tuyền chốt 14/08). Đúng Protocol §8 *Structured attestation*. Thiếu: `valid_until` (coverage hết hạn khi nào), chủ đề rõ (`loai` gộp "giải thích chờ" vào KHAC), và không nối commitment (dòng TRA_KQ không đóng một work item nào — nó đóng một *nhánh view*).

**Nội bộ** (Telegram): `event_published` được đặt cả ở nhánh không-có-template (không gửi gì, `notification_relay.py:205-214`) lẫn nhánh nhà cung cấp trả ok (`:238`), và `processed` trong log cộng cả hai (`:256`) → nhẹ hơn cả §20.9 «Coi "sent" là "done"»: ở đây "chưa từng gửi" cũng đọc ra thành "đã xử lý". Không MessageDeliveryConfirmed, không ai-đã-đọc, không retry có lịch (3 lần rồi nằm lại đến vòng sau — thực ra là retry vô hạn mỗi 30s cho event hỏng vĩnh viễn, không DEAD). `thong_bao` trong app làm đúng hơn (đọc ≠ xử lý) nhưng không gửi ra ngoài.

Zalo OA (kênh cho bệnh nhân theo D010) chưa xây; `providers/zalo.py` là stub.

Người dùng gặp: Trưởng ca gọi «SA1 tắc» → điều dưỡng có thấy không? Nếu họ không mở app, không có gì báo; nếu Telegram nhóm báo, không ai biết ai nhận.

Đóng bằng: [[tk-communication-delivery|notification_delivery]] — `notification_delivery` per channel (ADR-0002), `tuong_tac_cskh` + `valid_until` + `subject`, và quy tắc: **PatientInformed chỉ từ attestation có subject**, MessageSent không bao giờ đóng việc.

## Nối tới
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[notification-relay|notification_relay]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[thong-bao|thong_bao]]
- [[tk-communication-delivery|notification_delivery]]
- [[experience-state|Experience State]]

## Được dẫn từ
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[notification-relay|notification_relay]]
- [[gap-experience-state|Khoảng cách 5]]
- [[tk-communication-delivery|notification_delivery]]
