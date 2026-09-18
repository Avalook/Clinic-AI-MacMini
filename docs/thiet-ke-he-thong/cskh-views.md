---
title: "v_viec_cskh · v_trang_thai_cskh · luat_cskh — trạng thái là hàm của dữ liệu, luật là dữ liệu"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "20260809000005 · 20260809000007 · 20260810000004 · 20260810000009"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# v_viec_cskh · v_trang_thai_cskh · luat_cskh — trạng thái là hàm của dữ liệu, luật là dữ liệu

> [!abstract] 11 nhánh việc suy ra từ sự vắng mặt của một dòng sổ; đóng việc = ghi một dòng; đúng tinh thần projection — nhưng fold từ bảng trạng thái.

`luat_cskh (clinic_id, loai_viec) → bat, so_ngay, cua_so_ngay, nhan` — 11 dòng trên prod: CHO_XAC_NHAN 7 ngày · NHAC_HEN_MAI 1 · GOI_LAI 0 · HOI_LY_DO_HUY 1 (cửa sổ 14) · CHO_KQ_XN 2 · CHO_BAC_SI 1 · KQ_CHUA_GUI 1 · HEN_GOI_LAI 0 · MOI_TAI_KHAM 0 · NHAC_DI_KHAM 0 · **DA_CHECKIN** 0 (ưu tiên 0). «"Gọi xác nhận trước 7 ngày" là con số của Dr4Women. […] Ghim vào SQL thì mỗi lần đổi là một lần deploy.»

`v_viec_cskh` = 11 nhánh `UNION ALL` (uu_tien 0–10), mỗi nhánh một câu hỏi và đọc ngưỡng từ `luat_cskh`:

| uu_tien | loai | Suy từ |
|---|---|---|
| 0 | DA_CHECKIN | `appointment.status = 'CHECKED_IN'` («Khách có mặt tại chỗ là sự thật gấp nhất») |
| 1 | CHO_BAC_SI | `lab_result` có giá trị, `requires_doctor_review`, chưa `reviewed_at` |
| 2 | KQ_CHUA_GUI | kết quả đã duyệt mà **chưa có** dòng `TRA_KQ` sau `created_at` |
| 3 | CHO_KQ_XN | `result_value IS NULL` |
| 4 | GOI_LAI | lần chạm gần nhất trả CHUA_NGHE_MAY/KHONG_LIEN_LAC_DUOC/HEN_GOI_LAI |
| 5 | HOI_LY_DO_HUY | CANCELLED trong cửa sổ 1–14 ngày, chưa ai hỏi |
| 6 | HEN_GOI_LAI | `hen_goi_lai.dong_luc IS NULL AND ngay_goi <= hôm nay` |
| 7/9 | NHAC_DI_KHAM / MOI_TAI_KHAM | `nhac_tai_kham.trang_thai='CHO_GOI'` theo `luot_goi` |
| 8 | NHAC_HEN_MAI | lịch ngày mai chưa có `NHAC_HEN` |
| 10 | CHO_XAC_NHAN | lịch trong N ngày chưa có `XAC_NHAN_LICH` — «Suy từ sự VẮNG MẶT của một cuộc gọi, KHÔNG từ appointment.status» |

`v_trang_thai_cskh`: `DISTINCT ON (clinic, patient) ORDER BY qua_han DESC, uu_tien, han` — «QUÁ HẠN TRƯỚC, rồi mới tới ưu tiên. Đảo hai vế này là việc trễ ba ngày nằm im sau một việc chưa tới hạn»; kèm `so_viec_mo`, `co_viec_qua_han`, `da_xac_nhan`; `security_invoker = true`.

Bẫy đã trả giá và sửa: `DISTINCT ON` theo khách gộp mọi lượt → «mốc "Đã check-in" sáng chữ "đang ở đây" trên một lượt khách chưa từng đến» (ca anh Cường) → tách `v_viec_cskh` theo `appointment_id`; ba nhánh gọi điện quên loại CHECKED_IN → «vẫn giục gọi một người vừa bước vào cửa».

### Đối chiếu thesis

Đây là **projection + policy-as-data** làm đúng nhất trong repo — và là bằng chứng team đã tự đi tới Care Model §8 trước khi đọc thesis. Điểm khác: (1) fold từ **bảng trạng thái**, không từ event; (2) đánh đổi nói thẳng trong migration: «view không giữ được "ai nhận việc này"» → không ownership/ack = vi phạm Principle 3; (3) "quá hạn" là thuộc tính lúc đọc, không phải event có thời điểm phát hiện ([[gap-timer|Khoảng cách 4]]). Thiết kế giữ nguyên hai view làm *Work Queue projection*, và **thêm** lớp commitment bên trên: mỗi dòng việc CSKH đủ điều kiện được policy vật chất hoá thành `work_item` có owner/ack/SLA ([[tk-work-item-protocol|Work Item Protocol trên kernel]]) — đúng câu «Khi thật sự cần nhận việc thì thêm một bảng mỏng» của chính migration.

## Nối tới
- [[state-la-projection|State chỉ là projection]]
- [[policy-engine|Policy Engine]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[gap-timer|Khoảng cách 4]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[state-la-projection|State chỉ là projection]]
- [[policy-engine|Policy Engine]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-timer|Khoảng cách 4]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[tk-projections|Projection có kỷ luật]]
