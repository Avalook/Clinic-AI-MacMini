---
title: "Khoảng cách 5 — Experience State: không có; gần nhất là ngưỡng chờ theo phòng"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "experience-state ↔ dispatch_threshold"
trang_thai: Chưa có
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 5 — Experience State: không có; gần nhất là ngưỡng chờ theo phòng

> [!abstract] Hệ thống biết 'chờ bao lâu' nhưng không biết 'đã được giải thích chưa' — nên không phân biệt được chờ có thông tin và chờ vô định.

Có mảnh: `dispatch_threshold` (ngưỡng theo phòng ✓ = Spec §12 «waiting threshold theo node»), `wait_too_long` alert (≈ WaitingThresholdExceeded nhưng không phải event), `tuong_tac_cskh` (≈ communication record), `lab_result.triage_group` (clinical severity riêng trục ✓).

Không có: bảng `experience_state`; khái niệm **communication coverage** (Spec §8: subject · category · communicated_at · **valid_until** · actor · channel); lifecycle Detected→Intervening→Resolved/Expired; intervention contract; confidence/evidence_event_ids; owner_queue; review_at/expires_at.

Ba rule mẫu của Spec §7 đối chiếu:

| Rule | Cần | Có |
|---|---|---|
| 7.1 UnexplainedWaitRisk | active + onsite + waiting + vượt threshold node + **không coverage** + không suppression | vượt threshold ✓; onsite ✓ (`visit.status IN OPEN/IN_PROGRESS`); coverage ❌; suppression ❌ |
| 7.2 HandoffUncertaintyRisk | WorkAssigned + hết ack window + chưa Acknowledged/Reassigned/Cancelled | không có assign/ack |
| 7.3 ContinuityRisk | PatientLeftFacility + open commitment + chưa post-visit owner | `dispatch.checkout` ✓; open commitment tính được từ `work_item PENDING` + `lab_result` chưa review ✓; owner ❌ |

Hệ quả người dùng: CSKH không được nhắc «chị Lan chờ SA2 25 phút chưa ai nói gì với chị» — họ chỉ thấy nếu đang mở màn Trưởng ca, mà CSKH không có màn đó.

Điểm cần nói thẳng (Spec §2.5): «State chỉ nên tồn tại khi có intervention khả thi.» Dr4Women hôm nay có 10 CSKH và Zalo cá nhân — intervention «giải thích lý do + ETA» khả thi ngay. Nên state đầu tiên nên là UnexplainedWaitRisk, không phải cái gì cần AI. [[tk-experience-state|experience_state]].

## Nối tới
- [[experience-state|Experience State]]
- [[tk-experience-state|experience_state]]
- [[dispatch|Điều phối Trưởng ca]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[gap-timer|Khoảng cách 4]]
- [[gap-communication|Khoảng cách 8]]

## Được dẫn từ
- [[north-star|North Star]]
- [[ontology-9|Ontology]]
- [[experience-state|Experience State]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]
- [[tk-experience-state|experience_state]]
