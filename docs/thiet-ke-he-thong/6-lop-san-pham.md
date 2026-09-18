---
title: "Product map 6 lớp — Sensing · State · Coordination · Intelligence · Interfaces · Governance"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §8"
tags: [clinicai, lop1-hien-phap]
---

# Product map 6 lớp — Sensing · State · Coordination · Intelligence · Interfaces · Governance

> [!abstract] Bản đồ sản phẩm chính thức; mọi module chỉ được thêm khi phục vụ một lớp — và code hiện dồn vào lớp nào.

> «Các module appointment, CRM, EHR-lite, follow-up hay inventory chỉ nên được đưa vào khi chúng phục vụ một hoặc nhiều lớp nói trên. Product map không được quay lại logic "có feature nào thì thêm feature đó".» — *Thesis v1 §8*

Sáu lớp nguyên văn, và code đang ở đâu:

| Lớp | Năng lực (thesis) | Sản phẩm biểu hiện (thesis) | Code hôm nay |
|---|---|---|---|
| 1. Sensing | Thu event từ hệ thống và thế giới thật | Check-in, integration, nhập nhanh, thiết bị, event API | Check-in RPC, mốc quầy `tuong_tac_cskh` (CHECK_IN/OUT/THANH_TOAN/MUA_THUOC), `move_visit_to_station`. Không integration, không thiết bị. |
| 2. Operational State | Dựng trạng thái hiện tại | Encounter timeline, node, resource state, experience state | `visit.current_*`, `_STATIONS_SQL` (tải phòng), `v_viec_cskh`. Không experience state. |
| 3. Coordination | Tạo và phân phối công việc | Work Item, queue, ownership, SLA, escalation, handoff | `work_item` + gate SQL; `thong_bao` (gọi bộ phận). Không SLA/escalation/handoff-ack. |
| 4. Intelligence | Hiểu, dự báo, đề xuất | Risk detection, ETA, prioritization, recommendation | Lab triage (LLM + rule) là thứ duy nhất. |
| 5. Human Interfaces | Biến state thành nhận thức và hành động | Air Traffic Control, role views, patient status, daily brief | 55 màn theo 13 vai; `/truong-ca/*` 5 màn; `/display` TV; `pre_visit_brief` graph. |
| 6. Learning & Governance | Đo, truy nguyên và cải tiến | Analytics, audit, simulation, policy, AI governance | `v_audit_log` + `/audit-log`; `reports_service`; RLS tenant/role; **policy có nhưng không version**. |

Đọc bảng thấy hình dạng thật của sản phẩm: **nặng ở lớp 5 (giao diện) và lớp 1 (nhập tay), rỗng ở lớp 3–4**. 326 file TS/TSX so với 212 file Python là một chỉ dấu; `booking_service.py` 2.037 dòng là module dày nhất — tức là tiền và công đang đổ vào *appointment*, thứ thesis liệt vào «không phải appointment software» (*v1 §3.2*).

Thiết kế đích ([[tk-modular-monolith|Thi hành ADR-0001]]) xếp lại thư mục backend theo đúng 6 lớp này để ranh giới nằm trong code, đúng ADR-0001 chưa thi hành.

## Nối tới
- [[north-star|North Star]]
- [[wedge|Wedge]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[workflow-kernel|Workflow kernel]]
- [[ai-hien-co|AI đang có]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[gap-wedge-mismatch|Khoảng cách 15]]

## Được dẫn từ
- [[wedge|Wedge]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
