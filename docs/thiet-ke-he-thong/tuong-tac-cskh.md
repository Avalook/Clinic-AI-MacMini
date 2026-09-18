---
title: "tuong_tac_cskh — sổ chỉ-thêm của mọi lần chạm khách, hoàn tác không xoá vết"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "20260809000003 · 20260809000007 · 20260810000009 · services/tuong_tac_cskh_service.py (883 dòng)"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# tuong_tac_cskh — sổ chỉ-thêm của mọi lần chạm khách, hoàn tác không xoá vết

> [!abstract] Communication stream đã có thật: loai/kenh/ket_qua với CHECK chéo, mốc quầy, huy_luc; gần PatientInformed nhất trong code.

> «Nút "📞 Gọi nhắc hẹn" trên màn Quản lý khách hàng là một thẻ `<a href="tel:…">`: nó quay số rồi thôi. Gọi xong không ai biết đã gọi, gọi lần hai không ai biết là lần hai […]. Sổ này CHỈ THÊM. Không có hàm sửa, không có hàm xoá: một cuộc gọi đã xảy ra thì đã xảy ra, và bản ghi sai được sửa bằng cách ghi thêm một dòng nói rõ, không phải bằng cách viết lại quá khứ.» — *docstring*

Cột: `clinic_patient_id · appointment_id (SET NULL) · loai · kenh · ket_qua · khach_xac_nhan · noi_dung · nhan_vien_staff_id · xay_ra_luc · trang_thai_ma · huy_luc · huy_boi_staff_id`.

| Trường | Giá trị |
|---|---|
| `loai` | XAC_NHAN_LICH · NHAC_HEN · CHECK_XN · TRA_KQ · HOI_LY_DO_HUY · HOI_THAM · KHAC + mốc quầy **CHECK_IN · CHECK_OUT · THANH_TOAN · MUA_THUOC** |
| `kenh` | GOI · ZALO · SMS · TRUC_TIEP · KHONG_LIEN_HE |
| `ket_qua` | DA_LIEN_HE · CHUA_NGHE_MAY · KHONG_LIEN_LAC_DUOC · HEN_GOI_LAI · CAN_BAC_SI · TU_CHOI · BO_QUA · **GHI_NHAN** (chỉ mốc quầy) |

CHECK chéo ép ở DB và giải nghĩa ở Python: `(ket_qua='BO_QUA') = (kenh='KHONG_LIEN_HE')` («hai nửa của một việc»); mốc quầy ⇔ GHI_NHAN ⇔ TRUC_TIEP («Cho mốc mượn DA_LIEN_HE là bịa ra một cuộc gọi chưa từng có»); XAC_NHAN_LICH/NHAC_HEN/HOI_LY_DO_HUY/CHECK_IN/CHECK_OUT **bắt buộc `appointment_id`**; `TRA_KQ` chỉ với `DA_LIEN_HE`.

`nhan_vien_staff_id` **từ phiên đăng nhập, không nhận từ client**; bảng chỉ `GRANT SELECT` cho trình duyệt. CHECK_IN/CHECK_OUT «không chỉ là dòng sổ» — chạy `BookingService.apply_action` trước, ghi sổ sau («hành động lịch thất bại […] thì KHÔNG được để lại dòng sổ nói việc đã xảy ra»).

Hoàn tác (`20260810000009`): `huy_luc` + `huy_boi_staff_id` với CHECK cặp — «Dòng ở lại, chỉ thôi được tính». Vì sao không bút toán đảo: «mọi câu NOT EXISTS phải đếm cặp ghi/huỷ — mười nhánh, mỗi nhánh một câu con, chỉ cần một nhánh quên là một trạng thái sai âm thầm.» `huy_luc IS NULL` phải có ở 5 chỗ trong view.

Bài học `trang_thai_ma`: «`loai` không phải trạng thái — đó là bài học phải sửa bằng một cột mới» (bấm "Đã hỏi bác sĩ" thì mốc "Đã trả kết quả" cũng tích).

Ghi event: `cskh.tuong_tac` payload `{loai, kenh, ket_qua, by_staff_id}` — actor ở payload, không ở metadata (lệch với đa số).

### Đối chiếu thesis

Đây là **Communication Stream** (§6.5) và **structured attestation** (Work Item §8) tốt nhất repo. `TRA_KQ + DA_LIEN_HE` ≈ ResultCommunicated/PatientInformed; `XAC_NHAN_LICH + khach_xac_nhan` ≈ PatientAcknowledged; `CHUA_NGHE_MAY` ≈ CommunicationFailed; `HEN_GOI_LAI` ≈ CommunicationRetryScheduled. Thiếu cho coverage (Spec §8): `valid_until`, chủ đề rõ hơn `loai` (đang gộp "giải thích chờ" vào KHAC/HOI_THAM), và kết nối tới một *commitment*. [[tk-communication-delivery|notification_delivery]] giữ nguyên bảng, thêm hai cột.

## Nối tới
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[reliability|Reliability semantics]]
- [[tk-communication-delivery|notification_delivery]]
- [[experience-state|Experience State]]
- [[5-loai-event|Năm loại event]]

## Được dẫn từ
- [[event-vs-record|Event khác record]]
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[experience-state|Experience State]]
- [[reliability|Reliability semantics]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[gap-experience-state|Khoảng cách 5]]
- [[gap-communication|Khoảng cách 8]]
- [[tk-experience-state|experience_state]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-sensing|Sensing]]
