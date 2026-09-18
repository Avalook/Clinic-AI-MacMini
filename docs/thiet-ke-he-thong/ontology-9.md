---
title: "Ontology — 9 thực thể lõi và bảng nào trong code đang gánh chúng"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §4.1"
tags: [clinicai, lop1-hien-phap]
---

# Ontology — 9 thực thể lõi và bảng nào trong code đang gánh chúng

> [!abstract] Patient · Encounter · Node · Event · State · Work Item · Actor/Resource · Policy/SLA · Experience State — ánh xạ từng cái sang bảng thật.

> «Ontology là bộ khái niệm gốc mà từ đó dữ liệu, tính năng và quyết định được xây dựng. Nếu ontology sai, sản phẩm sẽ dần trở thành một tập hợp tính năng rời rạc.» — *Thesis v1 §4*

Bảng gốc (*v1 §4.1*) và ánh xạ sang lược đồ prod (79 bảng, đo 05/09/2026):

| Thực thể | Câu hỏi nó trả lời | Trong code hôm nay | Nhận xét |
|---|---|---|---|
| **Patient** | Ai đang được chăm sóc? | `patient` (+`patient_sdt_them`, `patient_medical_profile`, `pregnancy`, `patient_link`) | ✅ Đủ. Đa SĐT, MPI dò trùng có. |
| **Encounter** | Một lần chăm sóc đang diễn ra trong bối cảnh nào? | `visit` (lượt khám) — *không phải* `appointment` | ✅ Tách đúng: «`appointment` là lời hứa, `visit` là sự việc» (*GIAI-THICH-CODE §0.4*). `care_episode` = nhiều encounter. |
| **Node** | Encounter đang ở đâu trong hệ thống dịch vụ? | `node_definition` (41 node) + `clinic_room` (12 phòng) + `visit.current_node_code` | ✅ Có, và **là dữ liệu** (ADR-0011). Thesis không tách "node" khỏi "phòng"; code đã tách ([[dispatch|Điều phối Trưởng ca]]). |
| **Event** | Điều gì vừa thực sự xảy ra? | `event_log` (449 dòng, 17 loại) | 🟡 Có bảng, thiếu envelope, thiếu độ phủ ([[gap-envelope|Khoảng cách 1]]). |
| **State** | Reality hiện tại của đối tượng là gì? | `appointment.status`, `visit.status`, `work_item.status`, `v_trang_thai_cskh` | 🟡 Là **cột được ghi**, không phải projection từ event — trừ view CSKH ([[gap-projection-rebuild|Khoảng cách 6]]). |
| **Work Item** | Điều gì cần được làm? | `work_item` (5 trạng thái) + `nhac_tai_kham` + `thong_bao` + `hen_goi_lai` + `follow_up_case` | 🟡 Kernel có nhưng thiếu ownership/ack/SLA ([[gap-work-item|Khoảng cách 3]]); việc CSKH sống ở view chứ không ở bảng. |
| **Actor / Resource** | Ai hoặc nguồn lực nào có thể thực hiện? | `staff` + `clinic_membership` (13 vai) · `clinic_room` · `work_roster` (ca trực) | ✅ Người và phòng có; **thiết bị** chưa là thực thể. |
| **Policy / SLA** | Khi nào trạng thái trở thành bất thường? | `luat_cskh` (11) · `dispatch_threshold` · `visit_gate_rule` · `luat_bac_si_bat_buoc` · `*_booking_override` · `clinic.settings` | ✅ Luật là dữ liệu — mạnh nhất trong 9 thực thể ([[policy-as-data-hien-co|Luật là dữ liệu]]). Nhưng SLA cho *work item* thì chưa có. |
| **Experience State** | Bệnh nhân đang có nguy cơ trải nghiệm điều gì? | — | ❌ Không có gì ([[gap-experience-state|Khoảng cách 5]]). |

Kết luận đọc được từ bảng: **8/9 thực thể đã có chỗ đứng trong lược đồ**, thực thể thiếu hẳn là Experience State. Nhưng ba thực thể giữa (Event · State · Work Item) mới có *hình dạng* chứ chưa có *nghĩa* theo thesis — đó chính là toàn bộ [[gap-crud-roi-log|Khoảng cách 2]] và [[gap-work-item|Khoảng cách 3]].

Thesis cũng dặn về FHIR: «có thể ánh xạ với chuẩn FHIR phù hợp — Encounter, Task, HealthcareService, Location — nhưng ClinicAI cần giữ một operational model đủ linh hoạt» (*v1 §4.1*); Care Model §27 nói rõ hơn ở [[fhir-mapping|Quan hệ với chuẩn y tế]].

## Nối tới
- [[event-vs-record|Event khác record]]
- [[workflow-kernel|Workflow kernel]]
- [[dispatch|Điều phối Trưởng ca]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[gap-envelope|Khoảng cách 1]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-experience-state|Khoảng cách 5]]
- [[fhir-mapping|Quan hệ với chuẩn y tế]]
- [[gap-crud-roi-log|Khoảng cách 2]]

## Được dẫn từ
- [[north-star|North Star]]
- [[event-vs-record|Event khác record]]
- [[fhir-mapping|Quan hệ với chuẩn y tế]]
- [[workflow-kernel|Workflow kernel]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
