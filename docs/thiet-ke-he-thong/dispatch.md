---
title: "Điều phối Trưởng ca — phòng, tuyến, move_visit_to_station, ngưỡng, 4 loại cảnh báo"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "20260804000001–003 · services/dispatch_service.py (633 dòng) · route_derivation.py"
trang_thai: Một phần
tags: [clinicai, lop3-code]
---

# Điều phối Trưởng ca — phòng, tuyến, move_visit_to_station, ngưỡng, 4 loại cảnh báo

> [!abstract] Bảng ATC sơ khai đã có, đọc từ một nguồn (visit.current_*); nhưng visit_route 0 dòng và cảnh báo chỉ tồn tại lúc đọc.

### Ba bảng cấu hình

- `clinic_room` (12 phòng Dr4Women: TIEPNHAN, SINHHIEU, KB01–04, SA1–3, XETNGHIEM, NHATHUOC, THUNGAN; `capacity` = «Số người phục vụ ĐỒNG THỜI, không phải sức chứa hàng chờ»; `floor`; `show_on_tv`) + `clinic_room_node` (một phòng phục vụ nhiều bước — vá cho «KB01–04 đều gắn cứng vào KHAM-PHUKHOA»).
- `route_template` (3 tuyến A/B/C = hoán vị siêu âm/lấy máu/đọc KQ + thuốc + thanh toán) và `visit_route` (append-only, «Đổi tuyến giữa chừng thì PHẢI có lý do» — CHECK `visit_route_exception_needs_reason`; unique một tuyến hiệu lực/lượt).
- `dispatch_threshold` (theo phòng hoặc mặc định phòng khám: `wait_minutes` 20, `max_waiting` 8).

### Đường ghi duy nhất — `move_visit_to_station()` SQL

> «TÌNH TRẠNG TRƯỚC MIGRATION NÀY (đo trên prod 04/08): `work_item` có 0 dòng, và `visit.current_node_code` NULL ở cả 24 lượt khám. […] Nghĩa là hôm nay hệ thống không biết bệnh nhân đang đứng ở đâu.» — *20260804000003*

Bốn việc trong một giao dịch, khoá dòng `visit FOR UPDATE`: (1) đóng **mọi** bước đang mở (`COMPLETED`) · (2) mở bước mới gắn phòng · (3) cập nhật con trỏ `visit.current_node_code/current_room_id/current_node_since` · (4) INSERT `event_log 'dispatch.moved'` payload `{from_node, to_node, from_room, to_room, reason, work_item_id}`. `v_dispatch_history` đọc lại từ `event_log` («Không tạo bảng log thứ hai»). Trước khi move, `gate_rule_service.enforce()` chạy **trong cùng transaction** ([[gate-rule|visit_gate_rule]]).

### Đọc — ba truy vấn, một nguồn

`_OVERVIEW_SQL`: mỗi lượt khám sống một dòng — node/phòng/tầng hiện tại, `wait_minutes` (tại bước) ≠ `total_minutes` (trong phòng khám) («Trộn chúng làm một sẽ khiến người vừa được chuyển phòng trông như vừa mới đến»), `done_steps` từ timeline, `route_steps`, `next_step_of()`. `_STATIONS_SQL`: tải mỗi phòng — `serving` (IN_PROGRESS) ≠ `waiting` (PENDING), max/avg wait, ngưỡng, `state` ok/warning/critical («Vượt CẢ HAI ngưỡng mới là critical»). `build_alerts()` hàm thuần: `room_overloaded` · `wait_too_long` (critical khi > 2× ngưỡng) · `missing_next_step` · `no_route`.

`route_derivation.derive_route()`: suy tuyến từ chỉ định còn mở + đuôi chung của mọi tuyến mẫu — vì «trên prod hôm nay 0/25 lượt khám có tuyến».

### Đối chiếu thesis

Đây là *Encounter Board* + *Resource Load* projection (Care Model §8.1) và một nửa ATC (§19.1). Đúng ở: một nguồn sự thật, con trỏ do trigger/hàm nuôi, cảnh báo tính lúc đọc thay vì bảng cảnh báo («nó sẽ cũ đúng vào lúc Trưởng ca cần tin nó nhất»). Thiếu: cảnh báo không phải event (không owner/ack/thời điểm phát hiện), không commitment/SLA trên card, không freshness. Đo: `visit_route` **0**, `visit_gate_rule` **0**, `dispatch_threshold` 1 (mặc định). Xem [[gap-atc|Khoảng cách 12]], [[tk-atc-ui|Giao diện]].

## Nối tới
- [[gate-rule|visit_gate_rule]]
- [[workflow-kernel|Workflow kernel]]
- [[product-surface|Product surface sinh ra từ event model]]
- [[gap-atc|Khoảng cách 12]]
- [[tk-atc-ui|Giao diện]]
- [[state-la-projection|State chỉ là projection]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[gap-timer|Khoảng cách 4]]

## Được dẫn từ
- [[north-star|North Star]]
- [[ontology-9|Ontology]]
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[wedge|Wedge]]
- [[humane-ops|Design for Humane Operations]]
- [[patient-journey-4-chang|Patient Journey]]
- [[state-la-projection|State chỉ là projection]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[experience-state|Experience State]]
- [[product-surface|Product surface sinh ra từ event model]]
- [[workflow-kernel|Workflow kernel]]
- [[gate-rule|visit_gate_rule]]
- [[thong-bao|thong_bao]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[gap-timer|Khoảng cách 4]]
- [[gap-experience-state|Khoảng cách 5]]
- [[gap-process-manager|Khoảng cách 7]]
- [[gap-atc|Khoảng cách 12]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-projections|Projection có kỷ luật]]
- [[tk-atc-ui|Giao diện]]
