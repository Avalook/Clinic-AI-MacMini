# Soát 22/10 · Khối 4 — LEGO + QUYỀN

> Phiên soát CHỈ ĐỌC trên nhánh `main` (SHA `00bde52`). Không sửa code, test hay
> migration. Bản đồ dùng để định hướng: nhánh `claude/ban-do-hieu`; bản khai chủ
> bảng: PR #513 (nhánh `claude/goi4-ranh-gioi-lego`, chưa merge).
>
> **Đang viết dần** — các mục còn trống sẽ được bổ sung ở commit sau.

## Tóm tắt 10 dòng

_(điền khi xong cả bốn phần)_

## Bảng phát hiện

_(điền khi xong cả bốn phần)_

---

## Từ ngữ dùng trong báo cáo

- **Khối lego / module**: một vùng nghiệp vụ có ranh giới rõ (Đặt lịch, Thu tiền,
  Khám bệnh…). Khai trong `src/clinicai/modules.py`.
- **Chủ bảng**: khối DUY NHẤT được ghi một bảng. Khối khác muốn đổi dữ liệu ấy thì
  gọi lệnh của khối chủ hoặc phát sự kiện cho nó tự nghe.
- **Ghi chéo**: tệp của khối A chạy `INSERT/UPDATE/DELETE` vào bảng của khối B.
- **Capability (khối công việc)**: một quyền lệnh, vd `payment.service.collect`.
  Bật một lego trên màn Phân quyền = cấp một gói capability vào `capability_grant`.
- **Hỏi vai** vs **hỏi quyền**: hỏi vai = `if role == 'DOCTOR'`; hỏi quyền =
  `can(identity, 'clinical.record.write')`. Luật dự án: phải hỏi quyền.

---

## Phần (a) — Ranh giới khối lego

### a.1 Bản khai ở PR #513 có khớp code thật không?

Cách kiểm: chép `src/clinicai` của `main` hiện tại ra thư mục nháp, thay đúng
`modules.py` bằng bản của PR #513, rồi chạy 4 hàm kiểm của
`test_luat_cam_ghi_cheo.py` (bài quét mọi câu SQL ghi bảng trong code Python).

| Kiểm | Kết quả trên `main` 00bde52 |
|---|---|
| Mọi bảng bị ghi đều có chủ (hoặc là bảng kỹ thuật) | ĐẠT |
| Mọi tệp ghi bảng có chủ đều khai thuộc một khối | ĐẠT |
| Bản khai tệp hợp lệ (tệp còn, không khai hai nơi) | ĐẠT |
| Ghi chéo thực tế == sổ nợ `NO_GHI_CHEO` | ĐẠT — main chưa thêm chỗ ghi chéo mới kể từ lúc PR cắt nhánh |

**Sổ nợ ghi chéo: 97 chỗ** — 17 `VI_PHAM` (đã xác nhận sai), 71 `CHUA_XET` (chưa ai
đọc), 5 `XEM_LAI_KHOI`, 4 `DUNG_THIET_KE`. Tệp ghi chéo nhiều nhất:

| Tệp | Số bảng khối khác bị ghi | Ghi chú |
|---|---|---|
| `services/hoan_tac_service.py` | 10 | Hoàn tác nhiều khối trong một giao dịch — phần lớn là chủ ý |
| `services/luot_kham_service.py` | 9 | `appointment`, `queue_entry`, `service_order`, `tep_ket_qua`, `visit`… — **điểm nóng số 1** |
| `services/config_service.py` | 7 | Màn cấu hình ghi giá, thuốc, lịch trực |
| `services/booking_service.py` | 6 | Ghi `queue_entry`, `visit`, `patient`, `work_roster` |
| `services/clinical_sign_service.py` | 4 | Ký bệnh án ghi việc CSKH, hẹn gọi lại |

**Bảng `visit` (lượt khám, chủ là Tiếp đón) bị 11 tệp của 5 khối khác (Đặt lịch, Khám bệnh, Điều phối, Khách chọn dịch vụ, Kết quả, cộng 2 tệp quầy thuốc) ghi trực
tiếp.** Đây là chỗ "lego" yếu nhất: mọi khối đều tự đổi cột trạng thái lượt, nên
không có một chỗ nào biết đầy đủ "lượt đổi trạng thái vì sao". Muốn cho phòng khám
thứ hai dùng (có luật lượt khác) thì phải sửa ở 11 nơi.

### a.2 Điểm mù của bài quét — ghi chéo nằm trong hàm SQL của database

Bài quét của PR #513 chỉ đọc chuỗi SQL trong tệp `.py`. Nó tự ghi điểm mù "hàm SQL
trong database (trigger) không quét". Đo bổ sung: lấy định nghĩa CUỐI của mỗi hàm
`CREATE OR REPLACE FUNCTION` trong `supabase/migrations/` → **222 hàm, 53 hàm có
câu ghi bảng**. Một số ghi bảng của khối khác:

| Hàm (migration định nghĩa cuối) | Ghi bảng | Khối chủ bảng |
|---|---|---|
| `move_visit_to_station` (`20260920000003_…cp6_doc_don_hien_hanh.sql`) | `visit`, `work_item`, `event_log` | Tiếp đón, Trách nhiệm |
| `update_visit_current_node` (`20260807000003_…`) | `visit` | Tiếp đón |
| `instantiate_visit_workflow`, `order_services` (`20260915000022_…`) | `work_item`, `work_item_event` | Trách nhiệm |
| `check_in_appointment` (`20260812000001_…`) | `appointment` | Đặt lịch |
| `nhac_tai_kham_dong_khi_co_lich` (`20261003720000_…`) | `nhac_tai_kham`, `hen_gio` | CSKH |
| `sdt_them_lam_tuoi_patient` (`20260815000002_…`) | `patient` | Hồ sơ khách |

(Các hàm nạp danh mục / dọn dữ liệu thử chạy một lần — bỏ qua.)

### a.3 Router chứa luật thay vì gọi service

Đếm câu SQL viết thẳng trong `src/clinicai/api/v1/routers/*.py` (57 tệp): 15 tệp có
SQL. Phần lớn là ĐỌC (danh mục, tỉnh/thành) — chấp nhận được. Chỗ có LUẬT:

| Router | Chỗ | Luật nằm ở router |
|---|---|---|
| `config.py:784-835` | `PATCH /display-settings` | Đọc–trộn–ghi `clinic.settings.display` (không khoá dòng, hai người lưu cùng lúc thì người sau đè) |
| `config.py:~930-1030` | lưu giờ ca + giờ mở cửa | Kiểm giờ mở/đóng, gộp lỗi, khoá `FOR UPDATE`, ghi `clinic.settings` — đúng ra là `clinic_settings_service` (PR #513 đã tự ghi "trái luật router mỏng, để dời sau") |
| `booking.py:660-700` | lưới nhận lịch | Đọc giờ mở cửa + ca rồi cắt khung — gọi hàm thuần `khung_theo_thu`, chấp nhận được nhưng SQL nên về service |
| `booking.py:395-430` | CSKH báo cần xếp bác sĩ | Luật "lịch đã có bác sĩ thì không báo" ở router |
| `queue.py:104` | hàng chờ | lấy `date.today()` — **đã biết** (phat-hien.json, sửa ở PR #522) |

Đáng chú ý: comment ở `booking.py:337` ghi rõ **"backend chạy quyền chủ nên RLS
không áp"** — nghĩa là cách ly phòng khám A/B ở FastAPI hoàn toàn dựa vào việc MỖI
câu SQL tự nhớ `WHERE clinic_id = …`. Không có lưới an toàn thứ hai ở database.
Với mục tiêu "nhiều phòng khám dùng", đây là rủi ro cấu trúc (xem phát hiện A3).

### Phát hiện phần (a)

**A1 · vừa · `visit` bị 11 tệp của khối khác ghi thẳng** —
`services/luot_kham_service.py`, `booking_service.py`, `clinical_record_service.py`,
`clinical_sign_service.py`, `hoan_tac_service.py`, `hang_cho.py`,
`ultrasound_service.py`, `lam_truoc_thu_sau.py`, `ban_le_service.py`,
`ban_theo_don_service.py`, `doi_bac_si_service.py` (đều trong sổ nợ, nhãn `CHUA_XET`).
- Vì sao sai: lượt khám là trục của cả hệ thống; khi nhiều khối tự đổi trạng thái,
  bất biến kiểu "lượt đã đóng thì đứng yên" phải được ép lại ở từng chỗ (hiện ép bằng
  trigger `update_visit_current_node`). Thêm một khối mới là thêm một chỗ có thể quên.
- Kịch bản: chưa có kịch bản sai cụ thể đã tái hiện — đây là rủi ro bảo trì.
- Độ chắc: chắc chắn về cấu trúc (bài quét chạy được); về lỗi cụ thể: chưa.
- Test đề xuất: đã có bánh cóc `test_luat_cam_ghi_cheo` (PR #513) — **merge PR #513**
  là bước đầu; sau đó gỡ dần nhãn `CHUA_XET` của `visit` thành lệnh của Tiếp đón.
- Hướng sửa: khối Tiếp đón mở vài lệnh `dong_luot`, `mo_lai_luot`, `doi_buoc_luot`;
  các khối khác gọi lệnh đó thay vì `UPDATE visit`.

**A2 · thấp · Bài quét ghi chéo không thấy hàm SQL** — 53 hàm SQL ghi bảng (bảng
a.2). Độ chắc: chắc (đã đo). Test đề xuất: mở rộng bài quét đọc định nghĩa cuối
của hàm trong migration (cách đo ở a.2) và đưa vào sổ nợ riêng. Hướng sửa: ghi vào
sổ nợ trước, không cần đổi hàm ngay.

**A3 · vừa · Cách ly phòng khám ở FastAPI chỉ dựa vào `WHERE clinic_id` thủ công** —
`api/v1/routers/booking.py:337` (comment tự xác nhận), toàn bộ service dùng pool chủ.
- Vì sao sai: một câu SQL mới quên `clinic_id` = phòng khám B thấy dữ liệu phòng
  khám A. Hôm nay chỉ có MỘT phòng khám thật (Dr4Women, cơ sở Hào Nam) nên chưa có
  hại; với mục tiêu nhiều phòng khám thì đây là lỗ lớn nhất.
- Kịch bản (tương lai): phòng khám thứ hai lên; một endpoint đọc theo `id` lấy từ
  URL mà quên lọc `clinic_id` → nhân viên phòng khám B mở được lượt của A bằng cách
  đổi id trên URL.
- Độ chắc: chắc về cơ chế; chưa liệt kê đủ từng câu thiếu lọc (ngoài phạm vi).
- Test đề xuất: test "hai phòng khám" — dựng clinic A, B trong DB tạm, gọi mọi GET
  `/{id}` bằng danh tính B với id của A, mong 404.
- Hướng sửa: (dài hạn) đặt `SET LOCAL app.clinic_id` mỗi giao dịch và bật RLS theo
  biến đó cho bảng có `clinic_id`; (ngắn hạn) test hai phòng khám ở trên.

**A4 · thấp · `PATCH /display-settings` đọc–trộn–ghi không khoá** —
`api/v1/routers/config.py:800-833`. Hai người lưu cùng lúc (một bật khu A, một tắt
khu B) → người lưu sau đè mất thay đổi của người trước. Hàm giờ ca ngay dưới đã khoá
`FOR UPDATE`, hàm này thì không. Độ chắc: chắc (đọc code). Hậu quả nhỏ (công tắc
bảng gọi số). Hướng sửa: dời vào `clinic_settings_service`, dùng `jsonb_set` theo
từng khu hoặc `SELECT … FOR UPDATE`.
