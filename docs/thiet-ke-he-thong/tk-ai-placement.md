---
title: "AI đúng chỗ — Interpretation/Decision, derived event có confidence/expiry, allowlist system-agent, Recommend là Decision event có người duyệt"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "graphs/lab_triage · policy.authority_level · TAM-NHIN 3 câu"
tags: [clinicai, lop5-thiet-ke]
---

# AI đúng chỗ — Interpretation/Decision, derived event có confidence/expiry, allowlist system-agent, Recommend là Decision event có người duyệt

> [!abstract] Không xây AI mới ở Phase 0–A; Phase B đóng provenance; Phase C Recommend cho redistribution — rule đã chứng minh giá trị trước.

Ba câu TAM-NHIN trước mọi thứ «thông minh»: *nó đọc bảng lv3 nào — bảng đó đáng tin chưa — người nào duyệt đầu ra?* Trước Phase B, `event_log`/`work_item`/`experience_state` chưa đáng tin → **không** thêm AI vận hành.

### Giữ nguyên

Lab triage (persist → hard_block GROUP_C → `staff_task` URGENT), static routing, Anthropic API 2-tier, D012/D013, checkpointer disposable. Khi `work_item` Protocol có: `create_review_tasks` tạo `work_item` node `DICHVU-DUYET-KETQUA` với `clinical_priority='urgent'`, `owner_type='role_queue' DOCTOR`, ack 15′, completion `required_event clinical.released|lab_result.finalized` — thay `staff_task` (0 dòng).

### Thêm ở Phase B — provenance đủ theo §20.10 và Spec §4

`ghi_su_kien('lab.triage_classified', evidence='inferred', confidence=<từ model>, policy_id=<rule/model version>)` khi classify xong → vào timeline, vẽ khác observed. `lab_result` thêm `triage_confidence numeric`, `triage_expires_at` (kết quả cũ phải phân loại lại nếu reference range đổi).

### Phase C — Recommend

`policy.authority_level = 'recommend'`: action `recommend_redistribution` (khi `room_overloaded` critical ∧ phòng cùng node `accepting` và rảnh) → ghi `policy.recommended` (Decision event, `evidence='decision'`, payload `{suggestion, evidence_event_ids, confidence}`) + `thong_bao` cho TRUONG_CA với hai nút **Áp dụng** (→ `move_visit_to_station` với `reason='theo đề xuất #id'`) / **Bỏ qua** (lý do). Cả hai ghi `policy.recommendation_resolved`. Đây là «lưu được: tín hiệu đầu vào, lý do, đề xuất, người phê duyệt, kết quả» (v1 §5.2). Chạy **shadow** 2 tuần (Tổng-Quan §9): ghi đề xuất, không hiện — đo precision bằng «Trưởng ca có tự làm đúng thế không».

LLM chỉ vào khi rule không đủ (v1 §5.1): tóm tắt evidence cho nhân viên («chị Lan chờ SA2 27′, đã được báo lúc 10:05 về máy siêu âm hỏng, chưa có cập nhật mới») — Spec §13 «tóm tắt evidence», «đề xuất cách diễn đạt». Không tự gửi (Spec §13 «AI không được tự gửi nội dung lâm sàng chưa duyệt»).

### System agent trong Work Item

`owner_type='system'` chỉ cho work type trong allowlist `policy.action.system_allowed = true` (Protocol §16 «AI/system agent chỉ nhận Work Type đã được allowlist»); ack = command accepted; completion vẫn cần outcome (§5 «với automated agent, acknowledgement có thể là command accepted; completion vẫn cần outcome riêng»).

### Kill switch

v2 §3.10: nếu Phase C không tăng precision so với rule, tắt `authority_level` về `observe` — một UPDATE, không deploy. Cost guard theo ngày (design v5 §6.3) giữ.

## Nối tới
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[ai-hien-co|AI đang có]]
- [[gap-ai|Khoảng cách 14]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[phase-c-intelligence|Phase C]]

## Được dẫn từ
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[ai-hien-co|AI đang có]]
- [[gap-ai|Khoảng cách 14]]
- [[phase-c-intelligence|Phase C]]
