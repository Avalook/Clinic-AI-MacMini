---
title: "55 màn theo 13 vai — NAV_ROLES, 5 màn Trưởng ca, /home gói một vòng, /display"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "src/dashboard/app · lib/roles.ts · services/man_trang_chu_service.py"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# 55 màn theo 13 vai — NAV_ROLES, 5 màn Trưởng ca, /home gói một vòng, /display

> [!abstract] Lớp Human Interfaces dày nhất sản phẩm; đọc roles.ts chứ đừng đọc bảng trong tài liệu.

Vai (`api/identity.py ClinicRole`, 13): DOCTOR · ULTRASOUND_DOCTOR · NURSE_ULTRASOUND · RECEPTION · CSKH · MANAGEMENT · CASHIER · CASHIER_THUOC · CASHIER_DV · TKYK · TRUONG_CA · PHARMACIST · DISPLAY («Không phải người — cái TV treo tường; backend từ chối vai này ở mọi endpoint trừ bảng gọi số»).

Ranh giới nghiệp vụ (`roles.ts`, mirror ở `identity.py`): `canWriteClinical` = BS + ĐD + TKYK · chỉ bác sĩ **ký** · CSKH không tự phát hành kết quả · `canWriteIntake` = CSKH/Lễ tân/QL/Trưởng ca · `canCheckin` = Lễ tân/QL/CSKH («sản phẩm MVP này là cskh thao tác được hết mà»).

Màn hình theo nhóm (55 route):
- **CSKH** `/customers` (1.184 dòng server component, Lát 2 gói 10 vòng thành `GET /cskh/man-khach-hang`), `/cskh-tasks`, `/nhac-tai-kham`, `/lich-do-ve`
- **Lễ tân** `/home` (Lát 3: `GET /home/bang-dieu-khien` — «khối theo vai do backend quyết từ identity»), `/patients/new`, `/reception/queue`, `/reception/checkout`
- **Trưởng ca** `/truong-ca` · `/hang-doi` · `/canh-bao` · `/lich-su` · `/tv` — «bị siết từ 28/36 mục xuống còn 5 màn điều phối (Quang, 04/08)»
- **Bác sĩ** `/tasks`, `/doctor/board`, `/doctor/orders/[visitId]`, `/result-review`, `/sieu-am`, `/sono`
- **Điều dưỡng** `/lab-queue`, `/service-queue`
- **Thu ngân / Dược** `/cashier/*`, `/pharmacy/*`
- **Quản lý** `/settings/*` (booking-policy, clinic-config, tai-khoan), `/ops`, `/reports`, `/audit-log`, `/nhan-su`, `/work-sessions`
- **TV** `/display`; in `/print/*`

Nợ đo được: SO-LUAT Luật 4.1 «route còn chạm thẳng database hôm nay là 42» (ratchet CI, chỉ được giảm); ADR-0012 nói cutover đã xong 30/07 và allowlist service-role còn 2 — hai con số nói hai chuyện, GIAI-THICH-CODE ghi «Chưa rõ con số hiện tại — cần kiểm».

### Đối chiếu thesis

Thesis §19 đòi ATC/My Work/Team Queue/Patient panel/Timeline với các trường cụ thể ([[product-surface|Product surface sinh ra từ event model]]). Các màn trên **có khung đúng** (Trưởng ca = ATC, `/tasks` = My Work, `/display` = Patient panel, `/audit-log` = Timeline) — [[tk-atc-ui|Giao diện]] chỉ thêm trường, không thêm màn.

## Nối tới
- [[product-surface|Product surface sinh ra từ event model]]
- [[tk-atc-ui|Giao diện]]
- [[6-lop-san-pham|Product map 6 lớp]]
- [[dispatch|Điều phối Trưởng ca]]
- [[gap-atc|Khoảng cách 12]]

## Được dẫn từ
- [[6-lop-san-pham|Product map 6 lớp]]
- [[product-surface|Product surface sinh ra từ event model]]
- [[gap-atc|Khoảng cách 12]]
- [[tk-atc-ui|Giao diện]]
