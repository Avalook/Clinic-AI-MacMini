---
title: "Sáu bất đẳng thức — NotificationSent ≠ PersonInformed"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §4 · Catalog §2.4 · Work Item §8"
tags: [clinicai, lop2-kien-truc]
---

# Sáu bất đẳng thức — NotificationSent ≠ PersonInformed

> [!abstract] Các khái niệm không được đồng nhất; 'sent = done' là lỗi nguy hiểm nhất của workflow software.

Bảng khái niệm (*Care Model §4*):

| Khái niệm | Câu hỏi | Ví dụ |
|---|---|---|
| Event | Điều gì đã xảy ra? | LabResultReady |
| Command | Ta muốn ai/hệ thống làm gì? | RequestDoctorReview |
| State | Ta đang tin điều gì là đúng ở thời điểm này? | Encounter.awaiting_review |
| Work Item | Công việc có ownership nào phải được hoàn tất? | "BS Lan review kết quả trước 11:10" |
| Notification | Tín hiệu nào được gửi tới một người? | Push notification đã gửi |
| Outcome | Reality có thực sự thay đổi không? | Bác sĩ đã review; bệnh nhân đã được giải thích |

> «Các bất đẳng thức bắt buộc: NotificationSent ≠ PersonInformed · WorkAssigned ≠ WorkAcknowledged · WorkAcknowledged ≠ WorkCompleted · CommandAccepted ≠ ActionCompleted · MessageDelivered ≠ MessageUnderstood · ProjectedState ≠ SourceEvent. ClinicAI không được "đóng vòng" chỉ vì đã gửi thông báo hoặc ghi một status.» — *§4*

Work Item Protocol §8 thêm: «MessageSent ≠ PatientInformed · ResultOpened ≠ ResultReviewed · WorkStarted ≠ WorkCompleted · **CheckboxTicked ≠ OutcomeObserved**.»

### Nơi code đang vi phạm — chỉ đích danh

1. **`event_published = TRUE` sau khi Telegram nhận** (`notification_relay.py`, `_mark_published`). Cờ này vừa là "đã lên hàng chờ" (`event_service.py` §Outbox pattern bước 4) vừa là "đã gửi" — ADR-0002 đã gọi tên «hai nghĩa». Không có chỗ nào cho *đã đọc*, càng không cho *đã hiểu*.
2. **Template thiếu → đánh dấu đã xử lý**: `if message is None: await _mark_published(...)` — sự kiện không có mẫu tin bị coi là xong. Thesis §15.6: «event lỗi schema được quarantine, không âm thầm bỏ».
3. **`thong_bao.da_doc_luc` ≠ `da_xu_ly_luc`** — code làm **đúng** bất đẳng thức này, có docstring giải thích: «ĐỌC ≠ ĐÃ XỬ LÝ, và đó là cả lý do có hai cột.» Đây là mẫu tốt để nhân rộng.
4. **`work_item_event` chỉ có `create`** trên prod; và Command API không có `acknowledge` — nên WorkAssigned ≠ WorkAcknowledged **không thể** vi phạm vì chưa tồn tại cả hai.
5. **`TRA_KQ` là attestation** — `tuong_tac_cskh_service.ghi()` bắt `ket_qua == 'DA_LIEN_HE'` mới cho ghi loại này: «Một cuộc gọi hụt vẫn không được mang nhãn đã trả kết quả». Đây là *structured attestation* đúng nghĩa Work Item §8 — giữ nguyên trong [[tk-communication-delivery|notification_delivery]].

## Nối tới
- [[notification-relay|notification_relay]]
- [[thong-bao|thong_bao]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[gap-communication|Khoảng cách 8]]
- [[tk-communication-delivery|notification_delivery]]
- [[work-item-commitment|Work Item là commitment]]

## Được dẫn từ
- [[work-item-commitment|Work Item là commitment]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[thong-bao|thong_bao]]
- [[notification-relay|notification_relay]]
- [[gap-communication|Khoảng cách 8]]
- [[tk-communication-delivery|notification_delivery]]
