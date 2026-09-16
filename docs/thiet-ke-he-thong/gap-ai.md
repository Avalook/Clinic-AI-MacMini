---
title: "Khoảng cách 14 — AI: đúng chỗ, có provenance, nhưng chỉ một nhánh và không Recommend nào"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "3-muc-quyen-ai ↔ ai-hien-co"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 14 — AI: đúng chỗ, có provenance, nhưng chỉ một nhánh và không Recommend nào

> [!abstract] Lab triage là mẫu đúng; thiếu confidence/expiry; Operations Copilot chưa thể có vì chưa có projection đáng tin.

Đúng: AI ở Interpretation (phân loại lab), hard-block GROUP_C, persist trước khi trả lời, provenance model/reason/time, fallback an toàn khi không LLM, static routing, không local LLM (ADR-0005), D012/D013.

Thiếu theo thesis:
- `confidence` số + `expires_at` cho suy luận (§20.10, Spec §4).
- Derived event có `evidence_level='inferred'` — hôm nay kết quả triage là **cột** trên `lab_result`, không phải event, nên không vào timeline.
- Recommend: không có đề xuất nào được lưu «tín hiệu đầu vào, lý do, đề xuất, người phê duyệt, kết quả» (v1 §5.2). `route_derivation` gần nhất nhưng không ghi.
- Tổng-Quan §9 Copilot shadow mode: chưa — và đúng là chưa nên: TAM-NHIN «Tính năng lv4 phải chỉ được tên bảng lv3 nó đọc, và bảng đó phải đã đáng tin.» Bảng lv3 cho copilot là `event_log` + `work_item` + `experience_state` — chưa đáng tin.

`lab_result` prod 0 dòng → nhánh AI duy nhất chưa có dữ liệu thật. `scheduling` graph: «confirm không tạo lịch!» (design v5) → gate debug-only.

Đóng bằng: [[tk-ai-placement|AI đúng chỗ]] — không xây AI mới ở phase 0–A; Phase B thêm `evidence_level/confidence` cho derived; Phase C mới có Recommend (redistribution) dưới dạng Decision event có approver.

## Nối tới
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[ai-hien-co|AI đang có]]
- [[tk-ai-placement|AI đúng chỗ]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[phase-c-intelligence|Phase C]]

## Được dẫn từ
- [[ai-hien-co|AI đang có]]
- [[tk-ai-placement|AI đúng chỗ]]
