---
title: "Patient Journey — 4 chặng, 3 lớp, 7 nhánh phát sinh"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Patient Journey v1"
tags: [clinicai, lop1-hien-phap]
---

# Patient Journey — 4 chặng, 3 lớp, 7 nhánh phát sinh

> [!abstract] Bản dành cho đối tác: hành trình là trải nghiệm liên tục, không phải sơ đồ phòng; 3 lớp expected/actual/next.

> «Bệnh nhân không phân biệt đâu là việc của lễ tân, điều dưỡng, bác sĩ, kỹ thuật viên, thu ngân hay CSKH. Họ chỉ cảm nhận: phòng khám có biết tôi là ai và tôi đến để làm gì không? tôi đang phải đi đâu? tại sao tôi phải chờ? ai đang chịu trách nhiệm cho bước tiếp theo? …» — *Journey §1*

Ba điều một journey tốt tạo ra (*§1*): **Liên tục · Có người chịu trách nhiệm · Có thông tin**. «Một hành trình tốt không nhất thiết không có chờ đợi. Nhưng nó không để bệnh nhân chờ trong vô định và không để công việc tồn tại mà không có người sở hữu.»

Ba lớp (*§2*):

| Lớp | Ý nghĩa | Trong code |
|---|---|---|
| Hành trình dự kiến | Con đường thông thường cho loại dịch vụ đã đặt | `node_dependency` + `route_template` (3 tuyến) |
| Hành trình thực tế | Những gì đang thật sự xảy ra | `work_item` + `visit.current_*` + `event_log dispatch.*` |
| Việc cần xảy ra tiếp theo | Hành động phù hợp với tình huống hiện tại | `dispatch_service.next_step_of()` — chỉ khi có `visit_route` (0 dòng) |

Bốn chặng (*§3*): Trước khi đến · Đến và được tiếp nhận · Khám, chờ và dùng dịch vụ · Kết thúc và sau khám. Mỗi chặng có "bệnh nhân cần / phòng khám cần biết / ClinicAI hỗ trợ / kết quả mong muốn". Chặng 4: «Patient Journey không kết thúc khi bệnh nhân thanh toán hoặc bước ra khỏi cửa.» → «Không có bệnh nhân "rơi khỏi hệ thống" chỉ vì họ đã rời cơ sở.»

Bảy nhánh phát sinh (*§5*) mà thiết kế phải xử lý: đến muộn · chờ lâu · node quá tải · phát sinh chỉ định · **rời cơ sở trước khi hoàn tất** · kết quả bất thường · **hệ thống nguồn mất kết nối** («Không được khiến người dùng hiểu nhầm rằng "không có kết quả" khi thực tế là hệ thống không nhận được dữ liệu» — §5.7).

Bảy nguyên tắc (*§10*), câu 10.3 đáng in ra dán tường: «Mười lăm phút không biết chuyện gì có thể tệ hơn ba mươi phút được giải thích rõ.»

### Cách làm discovery với đối tác (*§11*)

Năm nhóm câu hỏi cho từng loại dịch vụ: hành trình dự kiến · tín hiệu quan sát («Tín hiệu đang ở HIS, LIS, một phần mềm khác hay chỉ trong đầu người?») · trách nhiệm · trải nghiệm · kết quả. Đây là **format workshop** để lấp `visit_gate_rule` (0 dòng) và sửa `route_template` («Không có tuyến nào cho người chỉ khám rồi về» — `docs/kien-truc-nhieu-phong-kham.md` §2c).

## Nối tới
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[dispatch|Điều phối Trưởng ca]]
- [[gap-process-manager|Khoảng cách 7]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[experience-state|Experience State]]

## Được dẫn từ
- [[pilot-scope|Partner Pilot Proposal]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[gap-process-manager|Khoảng cách 7]]
