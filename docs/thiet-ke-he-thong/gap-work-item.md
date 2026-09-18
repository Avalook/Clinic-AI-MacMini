---
title: "Khoảng cách 3 — Work Item: 5 trạng thái, không owner bắt buộc, không ack, không SLA, không escalation"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "work-item-commitment ↔ workflow-kernel"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 3 — Work Item: 5 trạng thái, không owner bắt buộc, không ack, không SLA, không escalation

> [!abstract] Kernel có transition + gate + version; thiếu toàn bộ nửa 'commitment' của Protocol; lúc đo trên prod chưa có lệnh start nào.

Đối chiếu 10 bất biến Protocol §2 với `work_item`:

| Bất biến | Cột/lệnh hiện có | Kết luận |
|---|---|---|
| Purpose | `node_definition.name` | ✅ qua node |
| Reason (event/policy) | `work_item_event.metadata.spawn_on` | 🟡 không trỏ event |
| Subject | `clinic_patient_id/visit_id/appointment_id/care_episode_id` | ✅ |
| Owner (người/role/queue) | `assigned_to` nullable, `assigned_role` nullable | ❌ 1/7 có `assigned_to`; không «queue» |
| Priority tách clinical/operational | `priority P0/P1/P2` một trục | ❌ |
| Deadline/SLA | `due_at` nullable, không ai đặt | ❌ |
| Completion criteria | — | ❌ (complete = bấm nút) |
| Expected outcome event | — | ❌ |
| Escalation policy | — | ❌ |
| Authority | `actor_roles` theo node ✅ | ✅ |

Vòng đời: Protocol 8 trạng thái (Open/Assigned/Acknowledged/Active/Blocked/Escalated/Completed/Cancelled) vs kernel 5. Thiếu lệnh: **assign · claim · acknowledge · block · resume · reassign (có trong CHECK của `work_item_event` nhưng không có API) · escalate · reject_completion**.

Timer 4 mốc (claim_by/acknowledge_by/start_by/complete_by): không có mốc nào, không có timer.

Idempotency §13 «cùng origin_event + policy_version + work_type + subject chỉ tạo một»: có `uq_work_item_visit_node_live` (theo visit+node) — tốt cho spine, không phủ work item do policy sinh (chưa có).

`follow_up_case` (parent–child §9: «Parent work chỉ Completed khi các child work bắt buộc đã completed»): 0 dòng, không writer.

Hai thứ kernel làm **tốt hơn** Protocol: gate trong SQL để «no caller can route around it», và luật SKIPPED/CANCELLED. Giữ.

Hệ quả người dùng: Trưởng ca nhìn bảng thấy «SA1: 4 người chờ» nhưng không thể hỏi «ai đang phụ trách đưa người thứ nhất vào, đã biết chưa, còn mấy phút». Đó chính là Coordination Debt (v1 §9.2) — không đo được vì không có dữ liệu.

Đóng bằng: [[tk-work-item-protocol|Work Item Protocol trên kernel]].

## Nối tới
- [[work-item-commitment|Work Item là commitment]]
- [[workflow-kernel|Workflow kernel]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[thong-bao|thong_bao]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[metrics-thesis|Bốn nhóm chỉ số]]

## Được dẫn từ
- [[north-star|North Star]]
- [[ontology-9|Ontology]]
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[work-item-commitment|Work Item là commitment]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]
- [[workflow-kernel|Workflow kernel]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
