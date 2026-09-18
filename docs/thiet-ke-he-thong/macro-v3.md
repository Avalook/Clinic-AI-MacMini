---
title: "Thesis v3 — care capacity, 5 tài sản founder đầu tư, đội hiện tại"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v3 §2"
tags: [clinicai, lop1-hien-phap]
---

# Thesis v3 — care capacity, 5 tài sản founder đầu tư, đội hiện tại

> [!abstract] Bức tranh vĩ mô và câu tự nhận về team — quyết định 'productize gì, custom gì'.

> «Hệ thống biết điều gì nên làm, nhưng không thể làm điều đó đúng lúc, đúng người, nhất quán và ở quy mô đủ lớn.» — *v3 §2.1, healthcare delivery gap*

> «Nguồn lực khan hiếm thật sự: coordinated human attention. […] ClinicAI không chỉ là labor-saving software. Nó có thể trở thành attention allocation system for care delivery.» — *v3 §2.2*

Năm tài sản founder đang đầu tư (*§2.10*): (1) Ontology · (2) Operational data (event history) · (3) Workflow intelligence · (4) Trust · (5) Distribution. «Nếu chỉ tạo màn hình và feature theo yêu cầu từng phòng khám, phần lớn công sức không tích lũy thành tài sản.» → «Đây là tiêu chuẩn để quyết định một việc "nên build custom" hay "nên productize".»

Pilot phải tạo tài sản đi lên được (*§2.6*): canonical event model · reusable state machine · specialty configuration · integration adapters · deployment playbook · operational benchmark · trust/governance/audit layer.

Team (*§2.12*): «Cấu hình hiện tại gồm founder, người điều phối và một dev còn là sinh viên» — đủ để khám phá reality, xây ontology, prototype, pilot, chứng minh product loop; «chưa phải cấu hình để xây một healthcare infrastructure company».

Con đường (*§2.9*): 1 journey → 2 cơ sở → 1 khách ngoài pilot → 1 chuỗi khác → 1 chuyên khoa khác → 1 thị trường tương tự → partner ecosystem. «Đơn vị mở rộng phải là: thêm encounter được điều phối trên cùng một operational model với chi phí cận biên giảm dần.»

### Nghĩa cho thiết kế này

Ba thứ trong 5 tài sản mà code đã chạm: **ontology** (kernel + luật là dữ liệu — ADR-0011, `docs/kien-truc-nhieu-phong-kham.md` 4 tầng cấu hình), **operational data** (`event_log` — nhưng đang nhiễu), **trust** (RLS tenant, audit append-only, ký bệnh án). Thiết kế đích không thêm tài sản mới; nó **làm hai tài sản đầu có giá** bằng cách cho event_log nghĩa và cho work item vòng đời. Với đội 1 dev + AI, mỗi phase trong [[lo-trinh-tong|Lộ trình]] cố ý nhỏ hơn 2 tuần và không đòi hạ tầng mới (Luật 7.1).

## Nối tới
- [[lo-trinh-tong|Lộ trình]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]

## Được dẫn từ
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[phase-c-intelligence|Phase C]]
