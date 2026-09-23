# ĐANG LÀM — đọc file này trước khi bắt tay

Cập nhật: **23/09/2026 tối**, sau batch CORE A+B+C (mục đầu tiên dưới đây là mới nhất; các mục dưới là nền, đọc kèm).

File này giữ trạng thái đang dở của dự án. Nó tồn tại vì một phiên dài đọc lại
ngữ cảnh tốn nhiều hơn cả việc làm; cách chữa đã chốt với Quang là **chia thành
nhiều phiên ngắn, mỗi phiên một chủ đề**, và dùng file này thay cho việc cõng
lịch sử hội thoại.

> Bản trước của file này **chưa từng được commit** nên đã mất theo phiên. Từ giờ
> nó nằm trong git. Cuối mỗi phiên: cập nhật lại, nhất là mục "chờ Quang quyết"
> và "cạm bẫy".

---

## 23/09/2026 tối — CORE A+B+C (nhánh `claude/clinicai-lifecycle-v1-8b92b8`, ĐÃ PUSH, CHƯA deploy)

ChatGPT chốt "CORE A+B+C APPROVED — IMPLEMENT, KHÔNG AUDIT THÊM". Thứ tự:
A Clinical shell → B Quyền → C Phòng/vị trí → **D V5-A** (đang đỗ ở nhánh
local `v5a-wip` 26dd065a, migration phải đánh số lại SAU 000019) → **E bấm
xuyên nguyên lượt thật**.

| Mục | Commit | Cốt lõi |
|---|---|---|
| B1 | d8ae650e | Ai vào hệ thống cũng có quyền theo nhóm mẫu của vai (SQL `cap_quyen_theo_preset`); **Postgres ép luôn còn ≥1 người `permission.manage`/phòng khám** (constraint trigger hoãn, khoá dòng clinic) |
| B2 | 310f8732 | Chỉ còn MỘT hệ quyền: xác nhận tệp kết quả vào `capability_grant`; 4 endpoint quyền cũ → 410 |
| B3 | ecafb9e7 | Đường khám chính hỏi QUYỀN: check-in · sinh hiệu · khám · ghi bệnh án · duyệt KQ · thu tiền DV. Migration 000018 |
| A | 996cfc95 | Bỏ "Ký bệnh án" (`/sign` → 410). Trên chỉ [Bắt đầu khám]; **[Hoàn tất] ở cuối = khám xong, KHÔNG khoá** |
| C1 | b3839fb2 | Phòng là tài nguyên: thêm/đổi tên/bật-tắt theo `room_id`; bước chưa có phòng (DXA, tinh dịch đồ) báo `CONFIG_MISSING` |
| C2/C3 | a28bc843 | Thanh bên + cửa trang theo `room_id`; bỏ 9 mục `/phong/KN-*`; `/phong` = danh sách phòng từ DB |
| C4 | 625a0d96 | Danh mục vị trí trực đọc từ DB (`danh_muc` trong `/me/vi-tri-hom-nay`), bỏ 34 vị trí viết cứng; migration 000019 `ten_ngan` |
| Vá | a19ca3b7 | Trọn bộ test bắt 24 bài đỏ: module chưa khai quyền, release/amend hỏi quyền sau khi tìm lượt, mock cần cửa quyền theo nhóm mẫu |

**Tuyền ĐÈ đề xuất ChatGPT (phải báo lại ChatGPT):** ChatGPT muốn "Hoàn tất =
khoá, sửa phải đính chính". Tuyền chốt 23/09: **không khoá, sửa thoải mái**.
Lượt mới không bao giờ thành FINALIZED; [Đính chính] chỉ còn cho lượt cũ đã ký.

**Đã kiểm (cuối batch, một lần):** backend 2861 passed / 0 failed, cover 86% ·
lược đồ áp 2 lần + 33 bài lược đồ · ruff/format/mypy 546 file · tsc · eslint
0 cảnh báo · 452 bài frontend · `next build`. **CHƯA bấm trình duyệt 375/1280.**

**NỢ (ngoài phạm vi CORE, KHÔNG làm lén):**
- Single write path cho sinh hiệu (xem mục dưới).
- Thu tiền THUỐC vẫn hỏi vai; các cửa vai còn lại ở proxy booking; `cho-quyet`
  đọc theo vai; ~70 chỗ hỏi vai ngoài đường chính.
- Phạm vi quyền ROOM/SHIFT có cột nhưng chưa dùng; RECORD_LOCK 48h.
- **Câu hỏi mở:** hệ mới cho người có `permission.manage` tự cấp quyền cho mình
  (hệ cũ cấm) — chưa chốt.
- Ký kết quả SIÊU ÂM (của BS siêu âm) vẫn giữ — chỉ bỏ ký BỆNH ÁN.
- `MO_QUYEN_TAM_THOI` không còn nới check-in/sinh hiệu (đã sang quyền).
- Nhóm mẫu: Lễ tân & Bác sĩ KHÔNG còn quyền sinh hiệu mặc định; Trưởng ca có
  check-in. Cần người dùng xác nhận khi UAT.
- Luật `/phong` gộp: BS và BS siêu âm nay VÀO được mọi phòng dịch vụ (trước
  mỗi vai vài phòng). Chỉ là vào xem — lệnh vẫn hỏi quyền ở máy chủ.
- Vị trí mới quản lý thêm trong DB: bảng lịch hiện ngay, nhưng THANH BÊN chưa
  biết mở màn nào (`MAN_THEO_VI_TRI`/`NHOM_THEO_VI_TRI` vẫn trong code). Bài
  `test_vi_tri_tu_database_db.py` chỉ canh danh mục gốc trong DB thử, không
  canh vị trí quản lý thêm trên máy thật.

**Kịch bản E (Tuyền tả 23/09 — kiểm, KHÔNG code trước):** khách đến → bác sĩ
[Bắt đầu khám] → điền, sang màn khác vẫn giữ → xác nhận chỉ định → sự kiện về
lễ tân đối chiếu lựa chọn thật của khách → khách trả tiền dịch vụ thật chọn →
LÚC ĐÓ phòng được chỉ định mới nhận khách vào hàng chờ; phiên bác sĩ chính vẫn
"đang khám" → phòng [Bắt đầu] → hồ sơ bác sĩ chính hiện "đang làm" → kết quả
SA/thủ thuật hiện về hồ sơ bệnh nhân cho bác sĩ xem bất cứ lúc nào.

## 23/09/2026 — NỀN EVENT-DRIVEN, bước 1–3 (nhánh `claude/clinicai-lifecycle-v1-8b92b8`, CHƯA commit/deploy)

**Bối cảnh:** Tuyền dừng Slice 4.5/5 ngày 22/09 để chốt thiết kế trước
(`memory/dung-slice-chot-thiet-ke-truoc.md`). Đã tra nguồn thật hai vòng; kết quả
và danh sách lỗ ở `memory/thiet-ke-lego/`.

**Đã làm**

| Thứ | File |
|---|---|
| Sổ sự kiện `domain_event` (chỉ thêm, trigger chặn sửa/xoá) + `event_delivery` (mỗi sự kiện × bên nhận một dòng) + view `v_event_delivery_suc_khoe` | `supabase/migrations/20260923000001_domain_event.sql` |
| Projection dòng thời gian lượt khám | `supabase/migrations/20260923000002_projection_dong_thoi_gian.sql` |
| Danh mục sự kiện + một đường phát duy nhất | `src/clinicai/events/catalogue.py`, `emit.py` |
| Người đưa tin: thuê có hạn, đúng thứ tự trong cùng đối tượng, chờ tăng dần, hộp chết | `src/clinicai/events/worker.py` |
| Bên nhận đầu tiên (vô hại) | `src/clinicai/events/consumers/dong_thoi_gian.py` |
| Chế độ chạy `python -m clinicai.worker --su-kien` | `src/clinicai/worker.py` |
| Lát CD-01: lệnh `PlaceServiceOrders` | `src/clinicai/services/chi_dinh_service.py` + endpoint trong `api/v1/routers/luot_kham.py` |
| Màn bàn khám bấm lệnh mới | `src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx`, `app/api/luot-kham/route.ts` |
| Đặc tả lát (khuôn 8 mục) | `docs/slices/CD-01-bac-si-chi-dinh-dich-vu.md` |

**Đã kiểm:** ruff · mypy · eslint · tsc · 28 test mới trên Postgres thật (DB dùng
một lần, cổng 55471) · toàn bộ `src/tests`.
**CHƯA kiểm:** chưa bấm thật trên trình duyệt ở 375 và 1280. Chưa deploy.

**Sửa kèm:** `src/tests/integration/conftest.py` — fixture `location_id` lấy
`LIMIT 1` không lọc `is_active` nên có lúc bốc trúng cơ sở đã ngừng hoạt động
("Hào Nam") và test đỏ tuỳ thứ tự dòng.

**Bổ sung cùng ngày — MÔ HÌNH QUYỀN (lát PQ-01)**

Tài khoản là người; vai chỉ là preset; quyền thật là capability gom theo **khối
công việc**; quản lý có `permission.manage` chỉnh được cao nhất, kể cả ngoài
preset. Xem `docs/slices/PQ-01-quan-ly-phan-quyen.md`.

| Thứ | File |
|---|---|
| Danh mục khối/quyền/preset | `src/clinicai/permissions/catalogue.py` |
| `can` / `doi_quyen` / `quyen_hieu_luc` | `src/clinicai/permissions/can.py` |
| Lệnh cấp/thu/thêm preset | `src/clinicai/services/permission_service.py` |
| Endpoint | `src/clinicai/api/v1/routers/phan_quyen.py` |
| Bảng + view + chép quyền cho người đang làm | `supabase/migrations/20260923000003_capability.sql` |

Lệnh CD-01 đã bỏ cửa theo vai, chuyển sang `clinical.order.place`. Các cửa khác
chuyển dần theo từng lát.

**Màn phân quyền đã dựng** (`/phan-quyen`, chỉ Quản lý thấy trong thanh bên):
chọn người → bật/tắt từng **khối công việc**, `[+ Thêm preset <vai>]` cấp nhanh
theo vai, `▾ Chi tiết` bung quyền con kèm mức rủi ro. Màn nói rõ "Vai chỉ là gợi
ý, không phải giới hạn". Vào được màn ≠ cấp được quyền: backend vẫn đòi
`permission.manage` ở từng lệnh — **ẩn nút không phải bảo mật**.
`app/(dashboard)/phan-quyen/` + `app/api/phan-quyen/route.ts`.

**Bổ sung cùng ngày — BIỂU MẪU (lát KQ-01 + BM-01)**

Nguồn: phiếu chỉ định giấy Dr4Women 17/08/2026 (`chi-dinh.html`) — 18 mẫu kết quả
và 28 chỗ "📄 Xem mẫu".

| Thứ | File |
|---|---|
| 18 mẫu + bảng gắn mẫu cho dịch vụ | `supabase/migrations/20260923000004_mau_ket_qua.sql` |
| Lệnh gắn/gỡ + đề xuất theo tên (KHÔNG tự gắn) | `services/mau_ket_qua_service.py`, `routers/mau_ket_qua.py` |
| Form Template Engine (1 engine, mẫu là dữ liệu) | `services/form_engine_service.py`, `routers/phieu.py`, migration `…000005_form_engine.sql` |
| Lát | `docs/slices/KQ-01-…md`, `docs/slices/BM-01-…md` |

**18 khung đang RỖNG** (chỉ 3 mục chung: Mô tả · Kết luận · Đề nghị). Phòng khám
đưa ruột sau → sửa DỮ LIỆU qua lệnh xuất bản, không sửa code.

**Bổ sung cùng ngày — THỰC HIỆN DỊCH VỤ (lát TH-01, Lifecycle Slice 5)**

5 lệnh theo contract EXECUTION v1: Bắt đầu · Xong · Không làm được · Gián đoạn ·
Chuẩn bị làm lại. Một chỉ định có NHIỀU lần làm; `attempt_id` bắt buộc khi Xong
và Gián đoạn để lệnh cũ không đóng lần làm mới. "Chờ làm" là trạng thái TÍNH RA,
không lưu. Xem `docs/slices/TH-01-thuc-hien-dich-vu.md`.

| Thứ | File |
|---|---|
| 5 lệnh | `src/clinicai/services/service_execution_service.py` |
| Endpoint + proxy | `routers/luot_kham.py` · `src/dashboard/app/api/luot-kham/route.ts` |
| Quyền (khối "Thực hiện dịch vụ") | `supabase/migrations/20260923000006_quyen_thuc_hien.sql` |
| Test (15) | `src/tests/services/test_service_execution_db.py` |
| Câu đọc cho màn (`?xem=thuc-hien`) | `ServiceExecutionService.xem` + `GET /luot-kham/orders/{id}/execution` |
| **Màn phòng đã chuyển sang 5 lệnh** | `app/(dashboard)/phong/[ma]/PhongDichVu.tsx` |

Màn phòng đọc trạng thái trước khi vẽ nút, vì mỗi lệnh phải kèm đúng
`execution_revision` (và `routing_revision` cho Bắt đầu) nó đang thấy. `attempt_id`
lấy từ chính câu đọc, không suy từ số thứ tự. Lịch sử các lần làm hiện thành danh
sách khi có từ 2 lần — máy hỏng 10:05 rồi làm lại 10:18 phải đọc được.

**Màn điền phiếu kết quả** (`_lam-viec/PhieuKetQua.tsx` + proxy `app/api/phieu/`):
MỘT màn cho mọi biểu mẫu, vẽ theo `khung` máy chủ trả về. Tự lưu sau 1,5 giây im
("Đã lưu 10:32 · nháp, chưa phải kết quả"); bấm Hoàn tất thì **lưu lần cuối trước
khi chốt**; hoàn tất lúc dịch vụ còn dở thì in ra dịch vụ đã đóng hay chưa.

**Bổ sung cùng ngày (chiều) — MỘT NÚT, VÀ SỬA LẠI ĐƯỢC**

Đọc lại nguyên văn chat với ChatGPT (`memory/chatgpt-clinic6/`) thì thấy màn
phòng đang bày **hai** nút kết thúc cạnh nhau — `[Xong]` cho dịch vụ và
`[Hoàn tất phiếu]` cho kết quả. Đó đúng là thứ ChatGPT tin 156 và Tuyền tin 157
đã gạt: *"chỉ cần 1 nút bắt đầu … xử lý thông minh phía sau, nút chỉ 1"*.

| Sửa | File |
|---|---|
| Gộp còn `[Bắt đầu]` → `[Hoàn tất]`; ba ngoại lệ xuống hàng phụ | `phong/[ma]/PhongDichVu.tsx` |
| `[Hoàn tất]` phát thêm `result.ready` theo `result_mode` | `services/form_engine_service.py` |
| Sửa lại sau khi hoàn tất → `result.corrected` | `mo_sua()` + cờ `dang_sua` |
| Hai sự kiện mới | `events/catalogue.py`, consumer `dong_thoi_gian` |
| Lược đồ | `…000010_ket_qua_san_sang.sql` |
| Test (7 mới) | `src/tests/services/test_form_engine_db.py` |

`service.completed` ≠ `result.ready`: lấy mẫu gửi ra ngoài thì dịch vụ xong hôm
nay, kết quả hai ngày sau mới về. `result_mode` trên `dich_vu_mau_ket_qua` quyết
(INLINE · LATER · NONE); chưa cấu hình thì coi như NONE — im lặng nghĩa là
"không có kết quả", không phải "cứ báo có cho chắc".

**NHÓM QUYỀN MẪU — quản lý tự thêm, sửa, xoá**

Preset rời khỏi hằng số Python, vào bảng `quyen_preset`. Tab "Nhóm quyền mẫu"
trong `/phan-quyen`. Ba lằn ranh có bài kiểm giữ: nhóm không phải quyền · sửa
nhóm không đổi quyền người đã cấp · nhóm dựng sẵn tắt chứ không xoá mất dấu.

| Thứ | File |
|---|---|
| Bảng + chép 10 nhóm dựng sẵn | `…000011_nhom_quyen_mau.sql` |
| Lệnh | `permission_service.py::luu_nhom/xoa_nhom/danh_sach_nhom` |
| Màn | `phan-quyen/NhomQuyenMau.tsx` + proxy |
| Test (7 mới) | `src/tests/services/test_permission_db.py` |

**RÀ HẾT `LIMIT` CẮT IM LẶNG**

Mười câu còn lại đã rà: nhà thuốc · nhắc tái khám · ba bảng tệp kết quả · hai
bảng siêu âm · hai câu lịch chờ xếp bác sĩ · kết quả xét nghiệm chờ duyệt. Danh
sách ngoại lệ trong `test_tran_khong_cat_im_lang.py` rút **15 → 9**, chốt bánh
cóc siết xuống 9.

Dùng `canh_bao_neu_day` chứ không `dem_va_bi_cat`: hàm đếm cần lặp lại y hệt bộ
lọc của câu chính, mà các bộ lọc này dài và tinh vi ("đơn thuốc còn nợ tiền",
"lịch *vừa mất* bác sĩ chứ không phải *chưa từng* xếp"). Chép lại một bộ lọc như
thế là đổi một lỗi im lặng lấy một lỗi khác. Chỗ nào trả về dict thì kèm
`bi_cat` + `tran` để màn nói được "đã đạt trần N".

**SỬA KẾT QUẢ GIỮ BẢN CŨ — ĐÓNG KỸ THUẬT 23/09, CHƯA CHỨNG NHẬN PRODUCTION**

`22d8fccb` + `105b1aa7`, CI 5/5 xanh, ChatGPT audit diff thật hai vòng.

    form_instance → result_correction (link mỏng) → visit_amendment (ảnh chụp)

Ảnh chụp là CẢ PHIÊN BẢN `{du_lieu, nhap_boi, thuc_hien_boi, hoan_tat_boi,
hoan_tat_luc}`, không chỉ phần chữ — chụp mỗi `du_lieu` thì v1→v2 nhìn đẹp và
chỉ vỡ ở v3. `ban_thu` là phiên bản CHUYÊN MÔN, không bao giờ là `revision`.

Nháp tách hẳn bản chính thức: `du_lieu_dang_sua` + `nhap_boi_dang_sua` +
`thuc_hien_boi_dang_sua`. Tự lưu không chạm gì thuộc bản đang phát hành.

`form_result_release`: quyền phát hành THEO TỪNG BẢN. **Hiện là NỀN và nguồn sự
thật, CHƯA phải hàng rào đang chặn ai** — không đường gửi/in nào đọc
`form_instance`. Chưa có thu hồi. Đừng viết tài liệu nói nó đã chặn.

⚠️ **TRƯỚC KHI ÁP MIGRATION LÊN PRODUCTION** (`…000014`): FK mới
`form_instance → service_order` xanh trên database dựng mới **không chứng minh**
dữ liệu production cũ sạch. Phải soi dòng mồ côi và dòng lệch `clinic_id` trên
dữ liệu thật trước, nếu không migration sẽ hỏng giữa chừng lúc deploy:

```sql
SELECT f.id, f.clinic_id, f.service_order_id
  FROM form_instance f
  LEFT JOIN service_order o
    ON o.clinic_id = f.clinic_id AND o.id = f.service_order_id
 WHERE o.id IS NULL;
```

Đây là **việc trước deploy**, không phải lỗi của batch.

**StartVitals — ĐÓNG (23/09): `a4792ca9` + `4814dba1`, CI xanh, BẤM THẬT XANH.**
`Chờ đo → [Bắt đầu] → Đang đo → [Lưu sinh hiệu] → Đã đo`.
- `vitals_status` thêm `in_progress`; `vitals_started_at/by` ghi ai bấm, lúc
  nào. Postgres chặn "đang đo mà không có người".
- Bấm hai lần cùng người → `already=true`, không phát sự kiện lần hai. Người
  khác bấm → `VITALS_STARTED_BY_OTHER` kèm tên và giờ.
- **Lần lưu đầu PHẢI sau [Bắt đầu]** (ChatGPT rà `a4792ca9`, chốt cùng ngày):
  còn `pending` thì `record_vitals` từ chối `VITALS_NOT_STARTED`, không ghi gì.
  KHÔNG tự bắt đầu thay (giờ bắt đầu sẽ thành giờ lưu, sai nghĩa). Màn khoá
  nút Lưu + ghi "Bấm [Bắt đầu] trước khi lưu"; ô nhập vẫn gõ được.
  A bắt đầu, B lưu → được (bàn giao), mốc bắt đầu vẫn của A. Dòng cũ đã
  `recorded` từ trước (không có người bắt đầu) vẫn lưu thêm được.
  Lưu thêm = THÊM dòng `vital_measurement`, không có `vitals.corrected`.
- ⚠️ **NỢ — batch riêng "Single write path for vitals"** (ChatGPT định hướng
  23/09, CHƯA code): bác sĩ/thư ký lưu **bệnh án đầy đủ** có kèm sinh hiệu
  (`clinical_record_service` → `dong_bo_sinh_hieu_tu_ho_so`) vẫn ghi
  `vital_measurement` và đưa `pending → recorded` KHÔNG qua [Bắt đầu] — trong
  khi chính file đó ghi "Sinh hiệu chỉ đo ở màn Đo sinh hiệu". Hướng: bệnh án
  vẫn lưu bình thường, nhưng KHÔNG được tạo/hoàn tất bước sinh hiệu; muốn đổi
  số thì đi qua contract sinh hiệu chuyên dụng. **Audit UI bệnh án trước**
  (nó gửi ô sinh hiệu thế nào) — chặn backend mù có thể làm bác sĩ không lưu
  được hồ sơ. Không trộn vào V5.
- `goi_do_luc/boi` giữ cột + dữ liệu cũ, không chép sang, không màn nào đọc
  làm trạng thái nữa. Đường `/goi-do` còn mở ở máy chủ, giao diện thôi gọi —
  gỡ hẳn là việc riêng.
- Soi rồi: `goi_do_sinh_hieu` **không** gọi `_cap_nhat_vi_tri` (khác
  `goi_khach` ở `d4d94a41`), nên bỏ nút cũ không rơi việc gì.
- Quyền: `VITALS_ROLES` (ĐD + Lễ tân + BS) là **HIỆN TRẠNG CODE, chưa phải
  chốt** — nguồn nghiệp vụ gắn ghi sinh hiệu với Điều dưỡng. Để audit quyền
  riêng, không sửa trong StartVitals.

**Bấm thật 23/09 (stack local `dev-up.sh`, dd.sa):** 8/8 ca xanh — chờ đo có
nút Bắt đầu + Lưu khoá + lời nhắc · số gõ trước giữ nguyên · bấm đúp = 1 sự
kiện · tải lại vẫn "Đang đo" · người khác bắt đầu: bảng tự hiện tên, bấm màn cũ
ra "Da nang local đã bắt đầu đo … lúc 14:28." · lưu → Đã đo · mất mạng →
"Mất kết nối — CHƯA bắt đầu đo.", DB không ghi gì · 375 và 1280 không tràn ngang.
Kiểm ở lớp: test + API + DB + bấm trình duyệt.

Bẫy môi trường gặp lúc bấm: `supabase_analytics_dr4women-clinic` (stack khác)
chết vì hết bộ nhớ mỗi giây → đường Mac→Docker chậm 0,4–27 giây, GoTrue quá
giờ, bị đá ra trang đăng nhập. Dừng nó → 0,001 giây. `dev-up.sh` đổ nếu DB thử
có lược đồ dở mà không có sổ migration → dùng `--reset` (chỉ xoá volume thử).

**Bổ sung cùng ngày — LEGO có chuẩn, trách nhiệm có chủ, cache có luật**

| Lát | Nội dung | File |
|---|---|---|
| OC-01 | Bản khai module + 5 bài kiểm CI (ổ cắm) | `src/clinicai/modules.py`, `src/tests/unit/test_o_cam_module.py` |
| TN-01 | Khách đã trả tiền mà không được làm → mở việc có chủ | `events/consumers/trach_nhiem.py`, migration `…000007` |
| — | Nhớ tạm quyền: quên NGAY khi thu/cấp, hết hạn 5 giây cho thay đổi từ nơi khác | `permissions/cache.py` |

Hai module **chỉ nghe** (`journey`, `trach_nhiem`) là bằng chứng ổ cắm chạy thật:
thêm cả hai mà không sửa một dòng nào của module phát sự kiện.

**Bổ sung cùng ngày — HÀNH TRÌNH ĐỦ MỘT LƯỢT**

Hai đường ghi cũ (check-in, sinh hiệu) nay phát thêm sự kiện nghiệp vụ trong
CÙNG giao dịch: `visit.checked_in`, `vitals.recorded`. Không đổi hành vi, chỉ
thêm một dòng vào sổ — đúng bước "Event Interception" của đường chuyển đổi.

Nhờ đó màn hành trình hiện đủ: check-in → sinh hiệu → chỉ định → bắt đầu → xong
→ phiếu kết quả. Có test dựng lại projection từ sổ sự kiện (xoá màn, chạy lại,
ra đúng như cũ).

Payload CỐ Ý không mang chỉ số sinh hiệu hay chữ lâm sàng: sổ sự kiện không xoá
được, nên nó chỉ giữ mã và số.

**Bổ sung cùng ngày — MÀN "VIỆC CẦN XỬ LÝ" (`/viec-can-xu-ly`)**

Mở việc mà không màn nào hiện thì vẫn là rơi. Màn mới đọc bảng việc khu vận hành
(`GET /api/work-items?workspace=khu_van_hanh`) và đóng việc bằng lệnh `complete`
của kernel — không luật riêng, không đường thứ hai.

| Thứ | File |
|---|---|
| Trang + bảng | `app/(dashboard)/viec-can-xu-ly/page.tsx`, `BangViecCanXuLy.tsx` |
| Proxy đọc | `app/api/work-items/route.ts` |
| Thanh bên + quyền xem | `nav-items.ts`, `lib/roles.ts` |
| SITEMAP | đã thêm hàng `/viec-can-xu-ly` |

⚠️ Bẫy đã cắn: bài kiểm ranh giới giao diện coi `#149` trong **chú thích** là mã
màu hex. Viết "tin số 149", đừng viết "#149" trong `src/dashboard`.

**Bổ sung cùng ngày — HẸN GIỜ (viên gạch cho mọi luật "quá … phút")**

Bảng `hen_gio` + vòng chạy trong `python -m clinicai.worker --su-kien`. Hai luật
đã code: (1) hẹn ghi CÙNG giao dịch với việc sinh ra nó; (2) tới giờ phải KIỂM
LẠI hiện trạng — "hết cần" là kết thúc bình thường, không phải lỗi.

Dùng ngay: việc đối soát tiền có hạn 4 giờ, việc quyết làm lại 8 giờ; tới hạn mà
việc còn mở thì tự nâng lên ưu tiên cao nhất (P0) để nổi đầu bảng.

| Thứ | File |
|---|---|
| Bảng | `supabase/migrations/20260923000008_hen_gio.sql` |
| Hạ tầng | `src/clinicai/events/hen_gio.py` |
| Dùng đầu tiên | `events/consumers/trach_nhiem.py` |
| Test (7) | `src/tests/services/test_hen_gio_db.py` |

**Lỗi thật bắt được nhờ test đỏ (23/09)**

`chi_dinh_hom_nay` (bảng trưởng ca) có `LIMIT 500` **im lặng**: quá 500 chỉ định
trong ngày là bảng thiếu người mà không ai biết — trưởng ca tưởng đã hết. Đã sửa:
trả thêm `tong` + `bi_cat`, và màn `truong-ca/ChiDinhHomNay.tsx` hiện dòng
"Bảng đang hiện N/M chỉ định". Có test.

**Bổ sung cùng ngày — LIMIT không được cắt im lặng + nối phiếu → đóng dịch vụ**

1. `src/clinicai/core/tran.py`: `canh_bao_neu_day` (log có tên bảng) và
   `dem_va_bi_cat` (trả `tong`/`bi_cat` cho màn). Đã gắn vào 5 bảng nguy hiểm
   nhất: chỉ định hôm nay · điều phối tổng quan · hàng đợi nhà thuốc · chờ đóng
   lượt · chờ bác sĩ quyết. Bài kiểm `test_tran_khong_cat_im_lang.py` là bánh
   cóc: file nào có `LIMIT` mà cắt im lặng thì đỏ, danh sách ngoại lệ chỉ được
   ngắn đi (còn 15 chỗ **chưa rà**, ghi rõ trong bài kiểm).
2. Hoàn tất phiếu kết quả → đóng dịch vụ, bằng **lệnh** của module Thực hiện.
   Không đủ quyền thì phiếu vẫn xong và kết quả nói rõ `dich_vu.vi_sao`.

**Hai lỗi thiết kế bắt được nhờ Postgres và nhờ test:**
- `result_form.completed` từng dùng `aggregate_type = service_order`, đụng số
  phiên bản với `service.*` → **chỉ mục duy nhất chặn**. Phiếu là ĐỐI TƯỢNG
  RIÊNG (`form_instance`); chỉ định nằm trong payload.
- Sự kiện ghi cùng một giao dịch có `occurred_at` BẰNG NHAU (`now()` là giờ mở
  giao dịch) → dòng thời gian xếp sai thứ tự. Thêm cột `thu_tu` = `domain_event.seq`.

**Đã áp quyết định còn nợ: SINH HIỆU KHÔNG CHẶN XẾP PHÒNG (Tuyền chốt 23/09)**

`luot_kham_rules.vitals_routing_block` trước đây trả `VITALS_REQUIRED` khi chưa
đo — giữ hành vi cũ vì chờ quyết định. Nay trả `None`: chưa đo sinh hiệu vẫn đưa
khách vào phòng dịch vụ được. Hàm GIỮ NGUYÊN (không xoá) vì nó là chỗ duy nhất
trả lời câu hỏi ấy — ngày nào muốn chặn lại thì sửa đúng một chỗ. Mã
`VITALS_REQUIRED` giữ trong bảng thông điệp để đọc được nhật ký cũ.

**Chuyển Chọn dịch vụ + Điều phối sang quyền capability (23/09)**

`can_confirm_service_selection` và ba hàm `can_route_*` trước đây là "seam" tạm
mượn ánh xạ vai; nay hỏi `can(...)` thật, **trong chính giao dịch của lệnh** (thu
quyền ở lệnh trước thì lệnh sau thấy ngay). Cửa router bỏ danh sách vai — hai bản
luật thì có ngày nói ngược nhau.

Kéo theo: fixture của các test cũ phải **cấp preset cho nhân sự vừa dựng**, đúng
như `staff_service` làm ngoài đời (người mới vào làm có quyền theo vai ngay).
Hai file test quyền CỐ Ý không cấp — đó là điều chúng kiểm.

Ba bài kiểm sửa lại cho đúng câu hỏi chúng muốn hỏi:
- hai bài "phòng khám khác": lời từ chối nay đến sớm hơn một bước (quyền cấp
  theo từng phòng khám) — nới câu chữ, KHÔNG nới ranh giới;
- `test_quyen_goi_y_va_xep`: trước dựa vào "bác sĩ không thuộc vai điều phối",
  nay hỏi đúng câu: **thu khối Điều phối thì bác sĩ không xếp phòng được nữa**.

**Màn PHÂN QUYỀN của quản lý (`/phan-quyen`) — 23/09**

Chọn người → bật/tắt **khối công việc** → xong. `[+ Thêm preset <vai>]` cấp nhanh
theo vai; "▾ Chi tiết" bung quyền con kèm mức rủi ro. Từ nay quản lý tự đổi
"ai làm được gì" mà không cần ai sửa code — đúng mô hình đã chốt trong chat.

| Thứ | File |
|---|---|
| Trang + bảng | `app/(dashboard)/phan-quyen/page.tsx`, `BangPhanQuyen.tsx` |
| Proxy | `app/api/phan-quyen/route.ts` |
| Thanh bên + quyền vào màn | `nav-items.ts`, `lib/roles.ts` (chỉ QL thấy màn; cấp được hay không do capability `permission.manage`) |

⚠️ Bẫy giao diện đã cắn: `grid-cols-[minmax(220px,300px)]` làm vượt **trần px tự
chế** (bài kiểm ratchet, trần 61). Dùng `rem` theo thang như các màn khác.

**Bước tiếp theo (đúng thứ tự)**

1. Bấm thật CD-01 trên trình duyệt: bác sĩ và thư ký y khoa, 375 + 1280.
2. Chạy worker `--su-kien` trên máy chạy thật, xem dòng thời gian có lên không.
3. Lát kế: thu tiền → xếp phòng → thực hiện (Slice 5 cũ), viết lát trước khi code.
4. Ba chỗ chưa chốt của CD-01 nằm ở mục Hotspot trong file lát.

---

## 15/09 — Bổ sung khi tiếp quản worktree Claude (chưa commit/deploy)

- Giữ giao diện Dr4Women hiện có. Phiếu bệnh án bác sĩ và thư ký cập nhật qua
  một SSE dùng chung; khi người đang gõ thì giữ nội dung và báo xung đột, tải
  lại có chủ ý. Lưu bệnh án cần đúng `revision` hiện hành.
- Thư ký nhập đơn thuốc thành bản chờ duyệt, không đổi dòng thuốc sống. Nếu
  chỉ sửa bệnh án mà đơn đang hiện y hệt đơn bác sĩ đã duyệt, không mở thêm
  bản chờ duyệt. Bác sĩ chỉ duyệt đúng bản nháp đang xem, với quyền và phiên
  bản phù hợp. Lưu bệnh án không tự đóng lượt; bác sĩ có nút kết thúc khám
  riêng sau khi đã lưu chẩn đoán, lời dặn và duyệt đơn còn chờ. Endpoint cũ
  vẫn chỉ chặn theo vai, bác sĩ sở hữu và trạng thái đã check-in; kiểm đủ mọi
  dịch vụ chỉ định ở backend còn cần nối vào workflow thống nhất.
- Cột đơn thuốc chờ duyệt bị chặn với truy vấn trực tiếp của `authenticated`;
  chỉ vai bác sĩ/thư ký đúng phòng khám đọc qua RPC. Nút chỉ định XN ở phiếu cũ
  chỉ hiện cho bác sĩ vì endpoint cũng chặn thư ký.
- Kiểm trong DB tách biệt `clinicai_privacy_qa`: toàn bộ migration áp được;
  27 ca unit + DB bệnh án/đơn thuốc vừa xanh. Browser headless hai vai kiểm đồng bộ,
  xung đột, duyệt và điều hướng lịch sử đã xanh; frontend lint/type xanh.
- **Chưa nối hai hệ lượt khám:** `/luot-kham` dùng bảng workflow lát 1 riêng;
  màn cũ dùng appointment/visit cũ. Chưa gọi đây là journey end-to-end trên
  dữ liệu thật, và chưa đưa worktree này lên VPS hay màn demo quản lý.

---

## -0023. Batch hoàn thiện pilot (18/09/2026) — nhánh `claude/pilot-batch`, CHƯA deploy

Bốn checkpoint: CP1 phiếu chuyên khoa (khoá sau ký, sinh hiệu chỉ xem, MHT tách
nghĩa, thai kỳ chỉ bác sĩ, HMVS hết lách) · CP2 xem lại lượt theo vai
(`/xem-luot/{visit}`, máy chủ cắt nội dung) · CP3 dịch vụ/thủ thuật trên rail
mới · CP4 bấm thật trên trình duyệt, đủ vai, và sửa lỗi bắt được.

Tài khoản thử mới (chỉ local, `supabase/fixtures/`):
- `doitac@` (PARTNER) — dùng để nghiệm thu đối tác, KHÔNG dùng Quản lý thay.
- `danang@` (NURSE_ULTRASOUND) + lịch trực hôm nay T1_LETAN, T1_THUNGAN,
  T1_DOCHISO (`tai_khoan_da_vai_hom_nay.sql`) — một người, ba nhóm việc.
- `gan_phong_dich_vu_thieu_local.sql`: DXA → KN-DOCHISO, Tinh dịch đồ / DFI →
  KN-LAYMAU. **Chỉ local** — phòng thật do Dr4Women chọn.
- `gia_thu_local.sql`: mọi dịch vụ 100.000đ + 5 dòng giá khám. **Không phải
  giá thật**; local trước đó 0/39 dòng có giá nên không thu được tiền.

Sửa trong CP4 (bắt được khi bấm thật):
- Audit đa vai: `dung_vai()` + mọi event ghi thêm `vai_tai_khoan` → check-in
  / thu tiền của `danang` ghi RECEPTION kèm tài khoản NURSE_ULTRASOUND.
- Tệp mới gửi SAU khi bác sĩ đã duyệt: trước đây không bao giờ quay lại hàng
  "Duyệt kết quả" (lọc `duyet_luc IS NULL`) → kẹt im lặng. Nay quay lại, có
  dải báo "bản mới", duyệt lại chỉ mở tệp mới.
- Check-out hiện dịch vụ KHÔNG làm được là "✓ Xong" → nay "Không làm".
- Khung Ký đứng yên sau khi phiếu tự lưu: chuông `lib/su-kien-benh-an.ts` +
  hỏi lại thưa 15 giây (bản đầu hỏi 4 giây, tốn request — đã bỏ).
- Hướng xử trí NT (MHT / điều trị hỗ trợ) được tính là "kế hoạch" khi ký.
- Lịch tiếp theo trong viewer không tính lịch đã check-in / đã xong.
- Tải nhiều tệp: một tệp hỏng không chặn các tệp sau.
- Màn hẹp: chọn khách ở Đo sinh hiệu / phòng dịch vụ tự cuộn tới khung làm.

Chạy local có video: `KET_QUA_VIDEO_UPLOAD_ENABLED=true ./scripts/dev-up.sh`
(mặc định tắt). Tự động hoá trình duyệt: `window.confirm` trả false trong khung
tự động — phải ghi đè trước khi bấm "khám xong".

Câu hỏi mở cho Dr4Women: xem báo cáo cuối batch (thu tiền trước hay sau khi
bác sĩ đọc kết quả; CSKH có được XEM tệp chưa duyệt; BS siêu âm tự cho phép
gửi tệp của mình; …).

## -0022. CI-01 + Slice 1 (18/09/2026) — rail mới là nguồn duy nhất cho kết quả / đọc lại / theo dõi / đóng lượt

Nhánh `claude/ci-01-slice-1-handoff-339fee`, một PR. **Chưa deploy.** Hai
migration mới (`20260918000001`, `20260918000002`) — áp bằng `supabase db push`
TRƯỚC khi deploy code, bước riêng có người xem.

- **CI-01:** test `-m db` chạy trong CI trên Postgres dùng một lần
  (`scripts/tests/dung-db-kiem.sh`, cổng 55433). Độ phủ đo cả bộ: 84%.
  11 test stale đã sửa. **CI-DEBT-1:** `src/tests/integration/` (REST đời cũ,
  fixture `clean_db` xoá TOÀN BẢNG staff/patient/appointment; 13 test
  scheduling 401 vì không có danh tính) bị loại khỏi CI — Đợt D viết lại
  hoặc xoá cùng endpoint work-sessions.
- **Bốn contract:** PERFORMED (làm xong là đạt) · VALID_RESULT (performed +
  `service_order.ket_qua_luc`; tệp gắn chỉ định chạy lại vòng đọc) · FOLLOW_UP
  (không thành yêu cầu vòng đọc; `follow_up_case` có owner/hạn/visit/chỉ định;
  duyệt kết quả thì DONE) · NOT_PERFORMED (không tự đạt; vòng vẫn sẵn sàng để
  khách về bác sĩ, không đóng được khi chưa quyết).
- **Bác sĩ quyết:** `POST /luot-kham/yeu-cau/{id}/quyet` (WAIVE | FOLLOW_UP, lý
  do bắt buộc, chỉ bác sĩ phụ trách). Khung "Chờ bác sĩ quyết" ở Bàn khám.
  "Đổi kế hoạch" = miễn + chỉ định thêm trong phiên đọc kết quả.
- **Khép lượt một chỗ:** `_ket_thuc_neu_xong` (hết kẹt khi DONE còn chỉ định dở,
  hoặc chỉ còn theo dõi).
- **Checkout** đọc `service_order`/`review_round`/`round_requirement`; **CSKH**
  `v_viec_cskh` thêm CHO_KQ_XN/CHO_BAC_SI trên `service_order`. Ba nhánh
  `lab_result` GIỮ song song cho dữ liệu cũ còn dở — xoá ở Đợt D sau khi đếm
  prod.
- **Theo dõi không mồ côi:** chỉ chuyển theo dõi khi đang chờ kết quả (dịch vụ
  không làm được → miễn + hẹn tái khám); chỉ định không làm được thì việc theo
  dõi của nó CANCELLED; yêu cầu đã đạt không quyết lại.
- **Rail cũ đã nghỉ (410 + log người gọi):** 13 lối ghi `service_log`,
  `lab_result` (tạo/nhập), `service_order_draft`, `order_services`. Ô "Chỉ định
  CLS" trong bệnh án đã gỡ. Chuyển cả lượt (`move_visit_to_station`) từ chối
  lượt luồng mới; đặt vào trạm lúc check-in GIỮ (cùng giao dịch đã có
  `appointment.checked_in` ghi đủ vai).
- **SEC-01 (có từ trước, cần làm sớm):** `v_viec_cskh` mất
  `security_invoker = true` từ một lần CREATE OR REPLACE trước Slice 1, trong
  khi dashboard đọc thẳng view (GRANT authenticated) → RLS bảng nền bị bỏ qua.
  Một phòng khám thì chưa lộ chéo; phải xử lý trước phòng khám thứ hai. Không
  lật trong Slice 1 vì đổi những gì màn CSKH thấy.
- **Còn nợ (không chặn Slice 2):** `hold_until_round` chưa ai ghi; khi làm
  tính năng giữ chỉ định phải chặn trường hợp vòng sau không được tạo (kế
  hoạch toàn FOLLOW_UP). Kết quả dạng ghi chú đã duyệt chưa sinh việc CSKH
  "gửi kết quả" (chỉ tệp mới sinh) — cần Tuyền chốt có cần không. TV/hàng chờ lễ tân tính "kết quả đã về" từ
  `lab_result` (`display_board_service`, `routers/queue.py`) — với luồng mới
  luôn "chưa về" → Đợt C (queue). `booking_service` còn tạo work_item
  DICHVU-SIEUAM lúc check-in lịch bác sĩ siêu âm → Đợt C (thống nhất SA). Mục
  VI "Cận lâm sàng" của bệnh án và lịch sử bệnh nhân vẫn đọc `lab_result` (chỉ
  hiển thị) → Đợt D. Code service rail cũ (service_log/lab_order/
  service_order_draft) còn nằm đó sau 410 → Đợt D xoá. Chưa bấm thật giao diện
  mới (cần người đăng nhập): khung Chờ bác sĩ quyết, ô CLS đã gỡ, khối chuyển
  phòng ẩn.

## -0021. Bản đồ màn hình + gộp màn cũ (18/09/2026)

- **Luật mới:** sửa giao diện phải tra `docs/SITEMAP.md` trước (quy trình 6 bước
  trong `CLAUDE.md`).
- **Tuyền chốt "1 ok, 2 bỏ ở home, 3 chỉ xem, 4 gộp hết":**
  - `/tasks` chuyển theo vai. Đã gỡ 5 component cũ và `HomeCheckin`.
  - Check-in **chỉ ở** `/reception/queue` (bảng "Lịch hẹn hôm nay").
  - Bệnh án mở từ Trang chủ và Danh sách bệnh nhân chỉ xem.
  - `/queue`, `/cashier/board`, `/cskh-tasks`, `/episodes`, `/work-sessions`
    chuyển hướng.
  - `/portal` và `/ops/telemetry` thành tab của `/ops`.
  - Backend gỡ khối `checkin` của trang chủ. Thông báo kết quả trỏ
    `/duyet-ket-qua`.
- **Lỗi có sẵn, bắt được khi kiểm thật trên prod:**
  - Trang `/` và 14 trang chỉ-chuyển-hướng bị `next build` dựng tĩnh lúc không
    có phiên.
  - Hậu quả: `/` luôn về `/home`, và mọi đường cũ (kể cả của 16/09) đều về
    `/login`.
  - Sửa bằng `force-dynamic` ở `app/page.tsx` và ở `(dashboard)/layout.tsx`.
  - **Check-in → hoàn tác → check-in lại** để lượt khám nằm im INCOMPLETE:
    khách có trong hàng đợi lễ tân nhưng không bao giờ tới bác sĩ. Sửa ở
    `_open_visit` (mở lại lượt INCOMPLETE). Test DB mới
    `test_check_in_lai_sau_hoan_tac_db.py` đã thử: gỡ bản sửa thì test đỏ.
- **Canh bằng test:** `tests/man-da-gop-boundary.test.mts`. Ratchet px 85 → 64.
- **Chưa làm:** 20 route `/api/*` không màn nào gọi (danh sách lấy bằng grep —
  phải kiểm tay trước khi xoá). Đo lại số `<button>`. Làm lại thanh bên theo
  việc.

## -0020. Khách kẹt sau đo sinh hiệu (17/09 09:53) — BỎ đường đón-khám cũ

- Nguyên nhân: ĐD Huế lưu sinh hiệu qua biểu mẫu bệnh án cũ (bấm tên khách ở Trang chủ, `ClinicalRecordForm vitalsOnly`) → có `vital_measurement` nhưng `encounter_flow` không "đã đo", không quyết tuyến → không vào hàng chờ bác sĩ/thư ký. Sáng 06:56 chỉ đổi nút "Điền sinh hiệu", sót lối bấm tên.
- Chốt (Tuyền: "cái nào cũ thì bỏ"): sinh hiệu CHỈ đo ở /do-sinh-hieu. Biểu mẫu vitalsOnly chỉ xem + nút "Đo sinh hiệu"; `ClinicalRecordService.save(vitals_only=True)` trả 422. Bác sĩ/thư ký sửa sinh hiệu trong bệnh án đầy đủ vẫn được và gọi `LuotKhamService.dong_bo_sinh_hieu_tu_ho_so` (đẩy vào luồng).
- Kiểm trên final cloud: đường cũ 422, không thêm dòng đo; trọn luồng 84/84; khách "Khám Hôm Na" đã được gỡ và Tuyền chạy tiếp tới thu tiền.

## -0019. Thao tác thật trên trình duyệt 17/09 (07:30) — luồng khách Mai Anh chạy trọn

Đã sửa + lên final cloud trong lúc thao tác: số tiếp đón chung của quầy (`appointment.so_tiep_don`, số riêng bác sĩ giữ); Trang chủ ẩn bác sĩ không có lịch; Trang chủ lễ tân không còn báo "Đang khám" ngay sau check-in; Trang chủ điều dưỡng đọc cờ đã đo từ Đo sinh hiệu + nút dẫn sang màn đo; thư ký đã phân không còn báo "chưa được phân" khi công tắc mở quyền bật; check-in mang loại khám sang lượt (hết "Chưa gán dịch vụ"); phiếu khám lưu theo ô (hai người gõ hai ô cùng lúc không đè nhau).

**ĐÃ SỬA 07:30–08:00 (kiểm lại 83/83 trên final cloud):** ký bệnh án tính phiếu chuyên khoa + sinh hiệu + ô lý do khám; việc đối tác hiện trạng thái đối tác (Bàn khám, trưởng ca); điều phối: "Tầng Tầng", số tiếp đón chung, bước kế theo chỉ định, bỏ cảnh báo tuyến; CSKH: chip "Đang ở: <phòng>" / "chờ đo sinh hiệu", ô kết quả XN chỉ tính tệp XN/đối tác, ô thủ thuật đọc service_order; đối tác bỏ "Lịch làm việc"; check-out đọc bước luồng mới; dòng thuốc gõ dở không mất; BMI tự tính (backend); thông báo đo sinh hiệu nằm dưới ô nhập.
visit.status vẫn IN_PROGRESS sau đóng lượt là CHỦ Ý (mốc đóng = closed_at; FINALIZED dành cho ký bệnh án).

Thêm 08:00–08:20: CSKH ô "Có kết quả xét nghiệm" tin tệp của lượt (cờ la_ket_qua_xet_nghiem chuyển xuống màn); lưu bệnh án không ghi thêm lần đo sinh hiệu trùng (INSERT … WHERE NOT EXISTS, ô không gửi không tính là đổi). CSKH xem trước + tạo PDF (application/pdf ~330KB) đã bấm thật trên trình duyệt. Bài kiểm trọn luồng API: 84/84.

**CÒN:** ghi chú thủ thuật (Biofeedback) của Mai Anh lưu rỗng khi bấm trên trình duyệt — API lưu đúng, chưa tái hiện; 8 khách TEST- do bài kiểm tạo còn trên prod (chờ Tuyền cho xoá).

## -0018. Luồng demo đủ vai 17/09 (06:15) — 72/72 trên final cloud

- Mới: ĐD **Gọi vào đo** (`encounter_flow.goi_do_luc/boi`); trưởng ca **chuyển phòng từng chỉ định** trong panel "Bác sĩ chỉ định gì" (số chờ + ngưỡng đầy, chặn khi phòng cũ đã gọi); tải phòng ở bảng điều phối đếm theo `queue_entry` (bản cũ đếm work_item → luồng mới luôn 0); đối tác thêm bước **Nhận mẫu · chờ tài liệu** (`service_order.doi_tac_cho_tai_lieu_luc`), việc đã gửi ở lại mục "Đã gửi hôm nay"; CSKH thấy trạng thái đối tác ở ô "Có kết quả xét nghiệm"; màn đối tác dùng khung Shell chung; thu ngân (CashierWorkBoard) bỏ QR demo → một nút "Đã thanh toán".
- Migration 000007 (cột mới), 000008 (chụp chiếu ngoài `doi_tac_lay_mau = true` — trước đó không bao giờ lên bàn đối tác). Ngưỡng đầy 4 khách cho 3 phòng siêu âm (dispatch_threshold, đặt qua API).
- 06:33 đã dọn sạch khách/lịch/lượt (TRUNCATE một giao dịch, sao lưu `~/truoc-don-khach-17-09.dump` trên VPS) và sinh 20 lịch ca Tối (14 online qua API CSKH + 6 WALK_IN chưa check-in; BS Thành 8, Hằng 5, Hùng 4, Dũng 3). Lễ tân check-in ở Trang chủ (nút "Đã đến") — "Tiếp đón khách" chỉ hiện khách ĐÃ check-in.

## -0017. Thư ký riêng từng bác sĩ — lịch 17/09 (05:30)

- 9 tài khoản mới `tk-<mã bác sĩ>@dr4women.vn` (TKYK, mật khẩu thử như các tài khoản .vn), nối `thu_ky_bac_si`: bs-thanh, bs-thiep, bs-quyet, bs-sa-hoang, bs-sa-giap, bs-sa-dat, bs-hang, bs-dung, bs-hung.
- Lịch 17/09 ca Tối: mỗi thư ký ở vị trí `*_TK` của phòng bác sĩ mình; ĐD Huế chỉ `T1_DOCHISO`; Thanh Phương rút khỏi `T1_TKYK` (10 dòng REJECTED, backup `.cach-ly-20260916/lich-hom-nay-2026-09-17-truoc-tach-thu-ky.json`).
- Tự test trên final cloud 50/52: 2 FAIL không phải lỗi (ngưỡng test cũ ≥10 bác sĩ, thực tế 9 — BS Dương hỏi bệnh không phải ca đặt lịch; Thanh Phương không ca vẫn thấy menu mặc định của vai TKYK).

## -0016. Sửa cho demo 17/09 6h — kịch bản trọn vòng 48/48 trên final cloud (04:18)

- Bàn khám gắn form bệnh án cũ (chẩn đoán, lời dặn, ĐƠN THUỐC thư ký nhập → bác sĩ duyệt), tự tải lại realtime; nút bác sĩ "Xác nhận & ký · khám xong". Đồng hồ "tổng từ check-in" + nhãn "Quay lại đọc KQ" (hang_cho trả `checkin_luc`, `vong`).
- Phòng dịch vụ: ĐD/thư ký đi kèm (`HO_TRO_PHONG`) gọi, Bắt đầu, Xong; bác sĩ bấm Xong được ghi performed_by. `_require` so tập vai bằng `is` (PERFORMER_ROLES trùng khít CLINICAL_READ_ROLES đã làm công tắc mở quyền nới nhầm quyền đọc bệnh án).
- `_cap_nhat_vi_tri`: luồng mới dời `visit.current_node_code/current_room_id` (trưởng ca, TV, đóng lượt đọc) — trước đó mọi lượt kẹt ở "Đo chỉ số".
- Bác sĩ ký khám xong hẳn (NO_SERVICES/DONE, không còn chỉ định dở) → appointment COMPLETED + exam_completed_at → quầy thu tiền được.
- Script: scratchpad `kich-ban-demo.py` (tạo "Khách Demo HHMM", chạy lễ tân→đo→thư ký/BS→thủ thuật→SA→quay lại BS→thu tiền→check-out→CSKH). 5 lượt demo đã đóng (đổi trạng thái, lý do "Dữ liệu chạy thử kịch bản demo 17/09").
- Sau đó (04:5x): thanh bên hiểu MÃ LỊCH ĐỜI CŨ (`MA_VI_TRI_CU` nav-items ↔ `VAI_THEO_VI_TRI` identity: LE_TAN, LAY_MAU, TLYK, PHU_BS_SA, MAY_*); hai vai → Lễ tân trên, Điều dưỡng dưới (`THU_TU_VAI_VAN_HANH`, trang chủ chọn Lễ tân); phòng/vị trí siêu âm bỏ chữ tầng → "Phòng siêu âm 1/2/3" (migration 20260917000003). Giá: 80/80 thuốc + 38 dịch vụ + 13 loại khám có giá (46 thuốc tra mạng, còn lại GIẢ ĐỊNH, ghi nhãn); kho 80 lô DEMO1709-* × 20 (giả định). PHU_BS_KHAM chưa ánh xạ.
- Sinh hiệu ĐD (`vital_measurement`) nay hiện vào bệnh án (GET /api/clinical-record ghép số đo mới nhất vào objective.vitals) và phiếu chuyên khoa (điền ô trống, cả tiền tố `kls_`) — `lib/sinh-hieu-dong-bo.ts`. Bệnh án tự lưu 1s (không nạp lại form, nhận revision mới), phiếu chuyên khoa tự lưu 1,2s + đọc lại 4s khi không có chữ chưa lưu. Chưa bấm thử giao diện thật; hai người cùng gõ một bệnh án sẽ ra dải "có bản mới".
- CÒN: bảng giá 1/39 dịch vụ có giá → màn thu tiền chặn "chưa có giá"; số thứ tự chưa đổi theo kéo thả VIP; Đo sinh hiệu chưa có nút "Gọi vào đo"; chưa bấm thử giao diện trên trình duyệt thật.

## -0015. Không giới hạn dung lượng tệp + CSKH xem/tải PDF hồ sơ khám (16/09/2026 đêm) — edd6b3c · c82d77b · aff7bcf, ĐÃ LÊN FINAL CLOUD

**Tải tệp không giới hạn (Tuyền chốt):**
- Trần theo loại = env `MEDIA_MAX_BYTES_<ANH|VIDEO|PDF|TAI_LIEU>`, mặc định 0 = không giới hạn. Hạn mức tổng `MEDIA_CLINIC_QUOTA_BYTES` mặc định 0. Vẫn giữ `MEDIA_MIN_FREE_BYTES` (5GB trống).
- Đường thật: `services/nhan_tep_luong.py` đọc multipart THEO LUỒNG → `<kho>/.tam/*.part` (cùng kho Viettel) → service chỉ đổi tên. Kiểm quyền TRƯỚC khi đọc byte thân; nhận kiểu ở 8KB đầu. Bỏ `UploadFile` ở 2 cửa tải (CSKH/nhân viên + đối tác).
- Dashboard: bỏ chặn 82MB; chuyển tiếp bằng `lib/chuyen-tiep-tai-len.ts` (node:http, không thời hạn — undici chờ header 300s); `cluster.cjs` vá `requestTimeout=0` và **tiến trình con phải exec lại cluster.cjs** (bản đầu chỉ vá tiến trình chính → cắt ở giây ~327). Ô tải có % tiến độ.
- api `TMPDIR=/var/lib/clinicai/media/.tam` (không để tệp lớn rơi vào ổ hệ điều hành chung với database).
- `backup-db.sh`: kho có `MEDIA_MARKER` (Viettel) → KHÔNG đóng tar media về `~/backups` (vài chục GB sẽ làm đầy ổ database mỗi đêm).
- Đo trên final cloud: video 2GB 51s (bản chép hai lần: 287s), khớp từng byte; RAM api ~200MB, dashboard ~250MB suốt lúc tải; PDF 120MB 5s; ảnh 30MB nhận.
- Còn: người KHÔNG có quyền gửi tệp to thì bị cắt kết nối (~6s) thay vì đọc được câu 403 — giao diện chỉ hiện ô tải cho vai có quyền nên chưa gặp thật.

**CSKH xem trước + tải PDF hồ sơ khám:**
- `GET /api/v1/cskh/ho-so-kham/{appointment_id}` (`ho_so_kham_service.py`, cùng nhóm vai đọc tệp kết quả): lịch + khách, lượt, sinh hiệu, phiên khám, phiếu khám (form_data), chỉ định + kết quả + duyệt, tệp, xét nghiệm, đơn thuốc. Mọi câu khoá theo clinic_id.
- Giao diện: `_lam-viec/HoSoKham.tsx` — Khách hàng → Lịch sử các lần khám → "Xem hồ sơ khám · tải PDF" (lượt CHECKED_IN/COMPLETED). Nhãn phiếu từ `lib/form-schemas`. PDF = chụp khung (html-to-image) cắt trang A4 (jspdf). Kết quả chưa duyệt mang nhãn "Chờ bác sĩ duyệt"; tệp chưa cho phép gửi mang nhãn.
- Chưa bấm thử nút Tải PDF trên trình duyệt thật (không đăng nhập hộ được) — cần Tuyền bấm.

## -0014. QA xoay vai theo lịch trên final cloud (16/09/2026 đêm) — 1d04d90 … sau cùng

Tuyền: *"tài khoản là duy nhất còn vai trò có thể thay đổi… thử thay đổi các vai trò cho mỗi tài khoản, riêng bác sĩ thì không cần… thư ký y khoa y hệt bác sĩ, có gọi khách vào khám rồi bấm bắt đầu khám… check cả upload video, ảnh, pdf, docx"*.

Lịch chụp trước QA: `~/qa-16-09/work_roster_truoc_qa_20260916.json` trên VPS (+ scratchpad). Sau QA so lại: 739/739 dòng, mất 0 · thừa 0 · lệch 0.
Bộ thử: scratchpad `qa-xoay-vai.py` (xếp lịch → đợi 32s bộ nhớ danh tính → cookie phiên thật → trang/API/thao tác → khôi phục lịch ở finally), `tep-lon.py`.

**Lỗi tìm ra và đã sửa:**
1. Kiểm vai nằm trong SQL (bảng việc Tiếp đón, đọc thẻ việc, thông báo theo vai) chỉ nhận 1 vai → truyền tập vai hôm nay; tư cách thành viên so `vai_goc`.
2. `_order_for_performer` so `identity.role.value` → tập vai.
3. Chưa có "Gọi vào khám" → `POST /luot-kham/hang-cho/{id}/goi` + nút ở Bàn khám, phòng dịch vụ.
4. Thư ký chưa phân bác sĩ (mở quyền) mở "Khách của tôi" không thấy ai → thấy mọi lượt khám chính.
5. Khách check-in mà lịch hẹn không gắn bác sĩ → không nằm trong hàng chờ của ai → nay hiện ở hàng chờ bác sĩ, ai bấm Bắt đầu thì nhận.
6. Ảnh HEIC/AVIF iPhone bị cất thành VIDEO MP4 → từ chối kèm hướng dẫn. Nhận thêm WEBP, GIF, DOCX, XLSX (loại TAI_LIEU, migration 20260917000002); Word xem ngay trong ô (mammoth, iframe sandbox). ZIP, AVI, BMP, exe đổi đuôi, tệp rỗng bị từ chối.
7. **Proxy Next cắt thân yêu cầu ở 10MB** → mọi video siêu âm thật tải qua giao diện hỏng ("không kết nối được máy chủ"). Proxy matcher bỏ qua `api/cskh/ket-qua`, `api/doi-tac`; route từ chối >82MB bằng 413 câu rõ. Thử: video 50MB/79MB tải 3s, tải về khớp byte, tua cuối 206; RAM dashboard 207MB.
8. `/api/cashier` đổi 403 thành 502 "Không đọc được danh sách chờ thu" → giữ 403 kèm câu "không có quyền".

**Kết quả lần chạy cuối:** 89/90 bước đạt (bước còn lại = lỗi 7, đã sửa và thử riêng đạt 5/5 + so byte + tua).

**Còn để lại (dữ liệu thử):** ~145MB tệp thử trong kho Viettel (`thu-*`, `video-50MB`, `video-79MB`…); 2 khách thử đã đi hết vòng (check-in → khám → SA → XN → duyệt). 9 phiên khám "đang khám" cũ của BS Hằng từ lát 1 vẫn treo.

## -0013. Một đường dữ liệu + màn theo phòng + thanh bên nhóm theo vai (16/09/2026 đêm) — 874ebf9 · ce3cad6 · c9d8e40, ĐÃ LÊN FINAL CLOUD

Tuyền chốt (sau khi đọc Notion "Kế hoạch v1.0.0"): thanh bên nhóm theo vai · cơ sở Kim Ngưu · lấy mẫu XN tuỳ loại (ĐD hoặc đối tác) · lễ tân kiêm thu ngân + kho thuốc · check-in/out phòng = bác sĩ/thư ký bấm Bắt đầu / Đã khám xong · **thủ thuật do BÁC SĨ làm** · ô tải và ô xem tệp là một · ĐD siêu âm cũng bấm Bắt đầu được.

**Đo trước khi sửa:** 3–4 đường chỉ định song song — payload thẻ việc (0 dòng), `service_log` (0 dòng, nhưng /sono /service-queue và THU NGÂN đọc nó), `lab_result`/`ultrasound_record` (hồ sơ /tasks ghi), `service_order` (8 dòng thật, chỉ màn ẩn ghi). Phòng siêu âm đọc thẻ việc nên không thấy 6 chỉ định SA.

**Máy chủ:**
- Migration 20260917000001: 12 phòng `KN-*` + phòng `KN-DOITAC` (la_doi_tac); 26 vị trí lịch nối phòng; tắt bộ phòng mẫu cũ; `DICHVU-THUTHUAT` chỉ DOCTOR; `service_price.doi_tac_lay_mau`; `tep_ket_qua.service_order_id`; `service_order.ket_qua_luc/bac_si_danh_gia/duyet_luc/duyet_boi`.
- Duyệt chỉ định → TỰ xếp phòng (ưu tiên phòng có người trong lịch hôm nay, rồi ít chờ; bỏ qua việc đối tác tự lấy và phòng đối tác).
- `GET /luot-kham/phong-hom-nay`, `GET /luot-kham/hang-cho?phong=`, `POST consultations/{id}/kham-xong` (tự chọn outcome), `GET /luot-kham/ket-qua-cho-duyet`, `POST orders/{id}/duyet-ket-qua`, `POST /doi-tac/viec/{id}/da-lay-mau`.
- Thư ký đi kèm bấm Bắt đầu/Kết thúc cho bác sĩ mình (duyệt vẫn chỉ bác sĩ).
- Thu ngân đọc `service_order` (giá theo mã), hiện khách khi phiên khám chính xong.
- Lễ tân: vào bảng thu ngân, ghi thanh toán (cả 2 loại), kho thuốc, tra giá (không sửa giá).
- Danh sách tệp kết quả mở cho mọi vai tải lên được (trước chỉ vai tiếp nhận → bác sĩ tải xong không thấy).

**Giao diện:** `/ban-kham[/KN-…]` (bố cục Bàn khám bác sĩ Tuyền chọn), `/phong/KN-…` (siêu âm/thủ thuật/lấy mẫu), `/duyet-ket-qua`, bàn đối tác 2 trạng thái, ô `KhungTep` (kéo thả + xem ảnh/video/PDF tại chỗ). Thanh bên: nhóm Bác sĩ · Bác sĩ siêu âm · Thư ký · Điều dưỡng · Lễ tân · Trưởng ca. Gỡ thân màn: /doctor/board, /kham/*, /doctor/orders, /sono, /sieu-am, /service-queue, /lab-queue, /result-review, /luot-kham (chỉ còn chuyển hướng).

**Thử thật trên final cloud (API, tài khoản thật):** BS Hằng thấy Trịnh Bảo Ngọc (STT 7) → Bắt đầu → duyệt SA + CFTR → tự vào Phòng siêu âm tầng 1 + Lấy mẫu → Khám xong (SERVICES) → BS SA Giáp Bắt đầu, gửi ảnh, Xong → ĐD Diễm Thuý lấy mẫu → đối tác thấy "Đã lấy mẫu", gửi kết quả → BS Hằng thấy 2 kết quả, phê duyệt → lễ tân Hải Yến mở thu ngân thấy 3 dòng. 20/20 bước 200/201. **Chưa bấm thử trên giao diện** (Claude không đăng nhập app được).

**Vai theo vị trí hôm nay (072245f, đã lên final cloud):** tài khoản Điều dưỡng Minh Thư đứng Lễ tân + Thu ngân bị 403 ở thu ngân/check-out/đặt lịch/kho thuốc/bảng giá và Tạo bệnh nhân đá về trang chủ. Nay danh tính mang `vai_theo_vi_tri` (Lễ tân/Điều dưỡng/Trưởng ca — KHÔNG BAO GIỜ bác sĩ, BS SA, thư ký, quản lý); cửa gác bị từ chối theo vai tài khoản mà vị trí cho phép thì đi tiếp dưới vai vị trí. Giao diện: `getVaiHomNay`/`vaiLamViec` (lib/clinic-session.ts). Dò lại bằng token Minh Thư: 7/7 cửa 200.

**Hai tầng vai (30b8497 + trang chủ theo vị trí, đã lên final cloud):** giấy phép = vai tài khoản (bác sĩ, BS SA, thư ký, quản lý, CSKH — lịch không vượt qua được); việc hôm nay = vị trí trong lịch (lễ tân, điều dưỡng, trưởng ca). `lib/clinic-session.ts`: `getVaiHomNay` (vị trí trước, tài khoản cuối), `getVaiChinh` (HIỂN THỊ), `vaiLamViec` (QUYỀN, xét mọi vai). 38 trang/route thôi đọc vai tài khoản; bài kiểm `vai-hom-nay-boundary` cấm tái phát. Nhật ký ghi `vai_tai_khoan`. Trang chủ: khối "Việc của bạn hôm nay"; "Điền sinh hiệu" chỉ cho người đứng Đo chỉ số.
Tự kiểm theo lịch 16/09 bằng cookie phiên thật (script scratchpad `tu-kiem-lich.py`, cookie `clinicai-auth`, base64- + chia 3180): 12/12 tài khoản mở đủ trang + API; Minh Thư → Tổng quan tiếp nhận + nhóm Lễ tân.
**co_vai (lỗi check-in Minh Thư):** đổi vai ở cửa gác CHỈ xảy ra khi cửa gác từ chối vai tài khoản; công tắc mở quyền để điều dưỡng qua nên booking_service vẫn so identity.role → "không được phép checkin". Nay mọi kiểm tra nghiệp vụ dùng `identity.co_vai(...)`; bài kiểm cấm `identity.role in/==` trong services/routers. Thử thật: Minh Thư check-in Trần Thu Hà → CHECKED_IN → hoàn tác → CONFIRMED.
**Chưa tắt công tắc MO_QUYEN_TAM_THOI** (cố ý): 4 người hôm nay chỉ có mã lịch cũ (LE_TAN, PHU_BS_SA, MAY_TRONG, TLYK) — tắt thì họ bị siết về vai tài khoản. Xếp lại lịch trước, rồi tắt.

**CÒN LẠI (chưa làm, cố ý):**
1. Bảng giá gần như trống → dòng thu tiền ra `None`.
2. Phiếu siêu âm phụ khoa có ô cấu trúc (`sieu-am/KetQuaPhuKhoa.tsx`) chưa nối vào Phòng siêu âm — hiện ô mô tả tự do + tệp.
3. `/tasks` (Công việc của tôi, 4 màn trong 1), `ClinicalRecordForm` còn nút chỉ định XN đường cũ; `/patient-list` vs `/customers`; `/cskh-tasks` + `/nhac-tai-kham` + `/episodes` — chưa gộp.
4. Thu tiền dịch vụ và Check-out vẫn 2 mục; Cấp thuốc (/pharmacy) và Thu tiền thuốc 2 mục.
5. API đường cũ (`/api/sono`, `/api/service-log`) còn nhưng không màn nào gọi.
6. Danh sách XN nào đối tác tự lấy: chưa có màn cấu hình để quản lý tích (cột đã có).

## -0012. Tệp kết quả lưu trên Viettel Cloud File Storage (16/09/2026 khuya) — commit a6ef82b

Tuyền: *"mình cần lưu vào viettel file storage"*. Trước đó tệp nằm trên ổ VPS, Viettel chỉ nhận bản sao lưu 02:15.

- `.env.prod`: `MEDIA_DIR=/mnt/viettel-cfs/clinicai-media` + `MEDIA_MARKER=.o-viettel-cfs`. api bind `/mnt/viettel-cfs/clinicai-media/production`.
- **Chốt an toàn**: thiếu tệp `.o-viettel-cfs` (ổ rớt / Docker lên trước ổ mạng khi khởi động lại) → từ chối ghi kèm câu báo, KHÔNG ghi nhầm xuống ổ VPS. Có ổ lại thì `docker compose ... restart api`.
- 5 tệp cũ đã chép sang (sha256 khớp); bản cũ vẫn để ở `~/clinicai/.media/production` (tệp thử, dọn được).
- Thử thật sau chuyển: tải PNG/MP4/PDF → 201, đọc Range → 206, tệp mới rơi vào Viettel (ổ VPS đứng yên 5 tệp).
- ⚠️ **Còn hở**: (1) sao lưu đêm `backup-db.sh` giờ nén tệp TỪ Viettel VÀO Viettel — cùng một nơi, chưa phải bản sao thứ hai; (2) hợp đồng Viettel File Storage hết hạn **16/10/2026**.

## -0011. Thanh bên tường minh + ảnh/video siêu âm (16/09/2026 khuya) — commit 02c0e94

Tuyền: *"điều dưỡng đang ngồi vào đo sinh hiệu thì phải có node là đo sinh hiệu… siêu âm phải có chỗ up ảnh, video… đối tác cũng phải gửi file vào hệ thống… cứ tường minh ra ở bên sidebar"*.

- **Màn mới `/do-sinh-hieu`**: khách hôm nay theo giờ check-in, hai nhóm Chờ đo / Đã đo, bấm là điền 10 chỉ số, lưu xong tự nhảy người kế. Vị trí `T1_DOCHISO` mở màn này.
- **Đổi tên mục theo việc**: Tiếp đón khách · Đo sinh hiệu · Lấy mẫu xét nghiệm · Làm thủ thuật & dịch vụ · Điều dưỡng siêu âm · Khám siêu âm · Cấp thuốc · Điều phối ca · Khám bệnh (mọi loại). Tiêu đề trang đổi theo.
- **Thanh bên có ca**: phần **Hôm nay** (việc của vị trí) + **Việc khác** (gập sẵn, tự mở khi đang đứng trong một màn của nó). Không ca / Quản lý: danh sách phẳng như cũ. Thanh dưới điện thoại không đổi.
- **Phòng siêu âm**: khối "Ảnh & video siêu âm" theo đúng lượt khám (record trả thêm `appointment_id`), ô xem nhanh + khung xem lớn phát video. Đối tác chọn được video.
- 5 mục `/kham/*` GIỮ (chưa gộp theo phòng — chờ ma trận phòng → phiếu).

**ĐÃ LÊN FINAL CLOUD** (Tuyền cho quyền): dựng lại api + dashboard, bật `KET_QUA_VIDEO_UPLOAD_ENABLED=true` trong `.env.prod`.

**LỖI NGỦ ĐÔNG bắt được khi thử thật**: thư mục `.media/production` do Docker tự tạo với chủ `root`, api chạy uid 1000 → MỌI lần tải tệp đều 503 "Permission denied" từ ngày dựng máy (0 tệp từng được tải). Sửa bền ở 69889e3: service một-lần `media-quyen` trong compose chown thư mục trước khi api chạy. Thử lại: BS SA Giáp tải PNG/MP4/PDF → 201, đọc lại có Range → 206; `doi-tac-pk` gửi video → 201. Còn 4 tệp thử nằm trên máy (tên `thu-*`).

## -0010. Bảng lịch Y HỆT Excel + lịch 4 tuần tháng 9 (16/09/2026 khuya)

Tuyền gửi ảnh hai tuần Excel: "bảng nó phải dạng y hệt như này".

**Khung bảng** (`RosterGrid.tsx`): ba hàng tiêu đề Thứ·ngày·ca · nền theo phòng
(token `--color-lich-*`, mã màu đọc bằng openpyxl) · vạch tầng `073763` · ô ĐEN
= vị trí không làm ca ấy · khối NGHỈ · gộp dọc khi hai vị trí liền nhau cùng
người. Hàng "Lịch khám / Số bác sĩ" ra khỏi bảng Excel, xuống bảng nhỏ riêng
chỉ ở màn xếp ca của quản lý (đặt lịch vẫn đọc nó).

**Bảng mới `vi_tri_dong_ca`** (migration 000011) — RIÊNG, không nhét vào
work_roster. Đọc qua PostgREST (màn lịch) và gói trang chủ (backend, câu SQL
thứ 7).

**Bộ đọc Excel trải ô gộp** — bản đầu chỉ đọc ô trên cùng nên Thu ngân, Tạo đơn
trống trơn và Thủy Tiên (ô gộp Hỏi bệnh + Thư ký) bị gán mỗi Hỏi bệnh.

**Hỏi bệnh ban đầu → nhóm CHUNG** (migration 000012): Excel có điều dưỡng đứng.

**Lịch đã nạp**: 07/09 ← Excel tuần 2 · 14/09 ← tuần 1 · 21/09 ← tuần 2 · 28/09 ←
tuần 1. 588 ô người · 296 ô đen/NGHỈ · 104 ô trống (13 tên). 0 ô bị từ chối.

⚠️ Chưa có: nút tô đen / bỏ tô đen một ô trong màn xếp ca (ô đen hôm nay chỉ nạp
được từ Excel). Chữ đỏ/xanh của tên bác sĩ trong Excel chưa làm — chưa rõ nghĩa.

⚠️ Deploy commit 43ace54 đi lên khi 3 bài kiểm backend đỏ (`pytest | tail -1`
nuốt mã lỗi). Đã sửa ở ed38e77; mã chạy không sai. Xem memory ong-tail-nuot-ma-loi.

---

## -0009. Màn khám riêng từng loại + một tài khoản thu ngân (16/09/2026 khuya)

**Gỡ "6 giai đoạn"** của mục -0008 (điểm 6): nó chỉ sửa `ServiceFormEngine`, mà
thành phần ấy nằm TRONG tab 3 của `ClinicalRecordForm` — hai cách chia chồng lên
nhau. Tuyền phát hiện qua ảnh.

**Màn khám riêng** (Tuyền chốt): `/kham/noi-tiet · phu-khoa · san · hiem-muon ·
nam-khoa` + "Khám siêu âm" (`/sieu-am` đổi tên). Mỗi màn = Bàn khám bác sĩ lọc
theo `service_type.form_code`. Danh mục ở `lib/loai-kham.ts`. Bàn khám chung giữ
lại (tên "Bàn khám (tất cả)") cho dịch vụ không có phiếu.

**Gốc ô vàng "chưa gắn biểu mẫu"**: CẢ 14 loại khám trên final cloud mất
`form_code` — migration 07/08 gắn đúng rồi dữ liệu bị nạp đè, sổ migration vẫn
ghi "đã áp". Migration `20260916000010` gắn lại (chạy lại được). Đo sau khi vá:
19 lượt hôm nay đều có phiếu — PK 13 · SK 2 · NT 2 · HMVS 1 · NK 1.

⚠️ **Dữ liệu `service_type` trên final cloud KHÁC quyết định 07/08 của Quang**:
14 dịch vụ đang bật (Quang chốt chỉ 5), tên vẫn "Sản 1", "Nội tiết - Tình dục".
CHƯA sửa — bật tắt dịch vụ đổi thứ khách thấy lúc đặt lịch. Cần hỏi.

**Thanh bên theo vị trí** trỏ vào màn khám riêng. **Sàn chậu chưa có phiếu** →
tạm Khám phụ khoa (chờ Tuyền). Thủ thuật → bàn khám chung. Hiếm muộn, Nam khoa
KHÔNG có vị trí nào trong lịch Kim Ngưu trỏ tới.

**Menu dự phòng** (ngày không ca) dùng `canSeeNavGoc` — luật gốc, KHÔNG theo công
tắc mở quyền. Quyền vào vẫn mở.

**Thu ngân**: `thu-ngan@dr4women.vn` (CASHIER) có `/thu-ngan/dich-vu` +
`/thu-ngan/thuoc`. `thu-ngan-thuoc`, `thu-ngan-dich-vu` đã NGHỈ (không xoá) qua
`scripts/gop-tai-khoan-thu-ngan.py` — đã kiểm: /me trả 403.

---

## -0008. Form lịch = Excel · thanh bên theo vị trí · phiếu bác sĩ theo giai đoạn (16/09/2026 đêm)

Tuyền chốt sáu điều, cả sáu đã lên final cloud:

1. **Form lịch = đúng hình Excel.** Ba bảng lịch lật chiều: hàng Tầng→Phòng→Vị
   trí, cột ngày×ca (T2→T6 một ca Tối; T7, CN ba ca = 11 cột). `LICH_KHAM` tách
   thành hàng riêng trên lưới + hàng "Số bác sĩ trực". `OfficialRosterTable` thôi
   có thân riêng, dùng lại bảng trang chủ.
2. **13 tên để trống** — khoá cứng trong `DE_TRONG` (scripts/nhan-su-kim-nguu.py).
3. Tài khoản theo vị trí giữ nguyên.
4. **Thanh bên theo vị trí hôm nay**: `GET /me/vi-tri-hom-nay` (dữ kiện) +
   `MAN_THEO_VI_TRI` trong nav-items.ts (trình bày). Không ca → menu theo vai.
   Quản lý không áp dụng.
5. Mở quyền: xem mục -0007.
6. **Phiếu bác sĩ theo 6 giai đoạn lâm sàng** (lib/form-schemas/giai-doan.ts),
   thay xếp gạch 2 cột. Chưa động thẩm mỹ.

**Migration 20260916000009** — ma trận `vai_duoc_vao_tram` nạp lại theo vị trí
mới. Không có nó MỌI lần lưu ca đều bị từ chối. Đã thử trong ROLLBACK trên final
cloud trước khi áp — và nhờ thế bắt được bản nháp tắt nhầm quyền `LICH_KHAM`.

**Lịch thật đã nạp** tuần 14/09 + 21/09 qua `POST /roster/shifts`: 259/260 ô, 41
ô trống. Ô bị từ chối: `Nguyễn Thuỷ Tiên` (điều dưỡng) đứng *Hỏi bệnh ban đầu*
20/08 — vị trí ấy đang xếp nhóm bác sĩ. **Chờ Tuyền: hỏi bệnh ban đầu có phải
việc riêng của bác sĩ không?**

⚠️ Lịch trực mã CŨ (`LE_TAN`, `LAY_MAU`…) vẫn nằm trong `work_roster` — vô hại
(không mã nào khớp bảng mới, không ảnh hưởng đặt lịch) nhưng chưa dọn.

**Bộ ghép tên đã gộp nhầm hai CSKH thành điều dưỡng** (Phương Thúy Nguyễn → Đỗ
Thuý Phương Anh; Nguyễn Thị Ngọc Giàu → …Giầu). Đã trả tên, gỡ 5 dòng vị trí,
và vá: nhóm nghề là một phần danh tính — tên trong lịch không bao giờ trỏ vào
hồ sơ CSKH/quản lý.

---

## -0007. MỞ QUYỀN TẠM THỜI + hai lỗi ngủ đông (16/09/2026 tối)

Tuyền: *"mở quyền giúp tôi, tất cả các tài khoản đều có thể thao tác đã, đừng
bị phụ thuộc lịch khám nữa, trừ bác sĩ ra thui, tại giờ đang rối"*.

**Công tắc `MO_QUYEN_TAM_THOI` — mặc định BẬT**

- Tắt backend: `MO_QUYEN_TAM_THOI=0` trong `.env.prod`, khởi động lại container.
- Tắt frontend: `NEXT_PUBLIC_MO_QUYEN_TAM_THOI=0` — **phải DỰNG LẠI ảnh**, vì
  Next nhét biến `NEXT_PUBLIC_*` vào mã trình duyệt lúc build. Tắt một nửa là
  quyền lệch nhau giữa hai tầng.
- Bộ kiểm chạy ở chế độ SIẾT (conftest + mọi lệnh `test:*`), nên 1932 bài
  backend + 288 bài frontend vẫn canh nguyên luật gốc.

**KHÔNG nới, có chủ ý:** cửa của bác sĩ (`DOCTOR_ROLES`, `NOTE_ROLES`,
`DRAFT_ROLES`), quyền đọc bệnh án (`CLINICAL_READ_ROLES`), vai DISPLAY, vai
PARTNER, và các màn quản trị trên thanh bên (`/portal` `/settings` `/reports`
`/ops`).

**BÀI HỌC: cửa ở router KHÔNG phải cửa thật.** Nới `_BANG_GUARD` xong mà CSKH
và thu ngân vẫn 403 — vì `LuotKhamService.bang()` gọi `_require(...)` lần nữa.
Luật nghiệp vụ nằm trong hàm dịch vụ (CLAUDE.md), nên đó mới là cửa. Nhìn cửa
ở router thì thấy hoàn toàn đúng.

**Hai lỗi ngủ đông mà việc mở quyền lôi ra**

1. `/cskh/man-khach-hang` trả **500 cho MỌI vai**. Kiểu trả về khai
   `dict[str, list[dict]]`, nhưng khối `tuan_cong_bo` là danh sách CHUỖI.
   Rỗng thì hợp lệ với mọi kiểu — nên lỗi ngủ cho tới đúng hôm có tuần lịch
   trực được công bố. Trên màn chỉ hiện "Không đọc được dữ liệu chăm sóc".
2. `_DANH_SACH_GUARD` thiếu `TRUONG_CA`, trong khi có đủ mười vai còn lại và
   trưởng ca vẫn tạo/sửa được hồ sơ qua hai cửa ngay trên nó. Sót, không phải luật.

**Đã đo lại trên final cloud sau khi vá:** 7/7 vai thấy đủ 19 lượt · điều dưỡng
bất kỳ ghi được sinh hiệu (200) · 4 vai đọc được màn Quản lý khách hàng, kèm
đúng khối `tuan_cong_bo` từng làm nổ 500.

⚠️ Công tắc này là TẠM. Máy chủ kêu `mo_quyen_tam_thoi_dang_bat` mức WARNING
mỗi lần khởi động — đừng hạ mức, đó là thứ duy nhất giữ nó khỏi thành vĩnh viễn.

---

## -0006. Lịch Kim Ngưu: dữ liệu thật đã vào, FORM thì CHƯA (16/09/2026 chiều)

Tuyền gửi `[Dr4women] PK Kim Ngưu - Lịch làm việc nhân sự theo tuần.xlsx` + trang
Notion *Kế hoạch v1.0.0*. Đối chiếu đầy đủ: **`docs/DOI-CHIEU-LICH-KIM-NGUU-16-09-2026.md`**.

**Ba phát hiện đổi cách nghĩ**

1. **Không ai làm một vai.** Hải Yến hai tuần đứng 8 vị trí ở 3 tầng. Chỉ Thanh
   Phương gần như chuyên một chỗ (7/7 ca Thư ký y khoa). Hệ thống đang gán MỘT
   vai cố định cho một người và mở/đóng màn theo vai ấy.
2. **"Thư ký y khoa" là chỗ ngồi, không phải nghề.** Danh sách nhân sự chỉ có 4
   nhóm bác sĩ + 21 điều dưỡng. Tính năng điền song song GIỮ NGUYÊN (Tuyền:
   "không được xoá nhé"); cái sai là giả định có một lớp nhân viên riêng.
3. **T2–T6 chỉ chạy ca Tối**; T7/CN có Sáng·Chiều·Tối. Khớp luật Notion: mọi mốc
   sức chứa đều 18h00/18h15/18h30/18h45.

**Đã làm**

- Migration `20260916000008`: `vi_tri_lam_viec` (27 vị trí Tầng→Phòng) +
  `staff_vi_tri`. **CHƯA nối vào quyền** — Tuyền chốt "từ đã để tính tiếp".
- `scripts/nhan-su-kim-nguu.py`: đọc Excel → nạp. Đã chạy trên final cloud:
  **90 dòng vị trí · 15 hồ sơ sang tên đầy đủ · 5 người mới · tất cả về cơ sở
  Kim Ngưu**. So tên theo TẬP CHỮ (≥2 chữ), có ba chốt chống gán nhầm.
- Ba màn theo góp ý Tuyền: đối tác gom theo KHÁCH · thu ngân bỏ đối soát · trưởng
  ca có lối sang Quản lý khách hàng.

**CÒN DỞ — việc lớn nhất**

`src/dashboard/lib/roster.ts` vẫn giữ `STATIONS` **của file Hào Nam đời cũ**
("Máy trong E10", "Phòng ngoài + Monitoring", "HSS + Thủ thuật"). Không một vị
trí nào trong đó tồn tại ở Kim Ngưu. Ba bảng lịch (trang chủ, lịch chính thức,
bảng xếp ca) đều đọc hằng ấy.

Và form phải **đổi chiều**: Excel là *hàng = vị trí, cột = ngày×ca*; bảng hiện
tại là *hàng = ngày, cột = trạm*. Với 27 vị trí thì chiều cũ thành 27 cột.

⚠️ `LICH_KHAM` KHÔNG phải một vị trí trong Excel — nó là "bác sĩ nào trực ngày
ấy" và `lib/roster.ts:110` dùng nó để dựng lưới đặt lịch. **Giữ lại**, đừng gộp
vào danh mục vị trí.

⚠️ Lịch trực tuần này trên final cloud đang dùng MÃ CŨ (`LE_TAN`, `PHU_BS_SA`…).
Đổi `STATIONS` mà không dựng lại lịch thì các cột hiện ra trống.

**Hai việc chờ Tuyền chốt**

- `BS Hằng` mơ hồ: trùng cả `BS Hằng` lẫn `ĐD Hằng` → khai vào `PHAN_XU`.
- Hai người suýt bị tạo trùng, script đã chặn: `Lê Huyền Trang` (= `ĐD Trang Lê`?)
  và `Vũ Hoàng Vân Anh` (= `TL Vân Anh`? — hay là người thứ hai, vì lịch có cả
  `N. Vân Anh` lẫn `V. Vân Anh`).
- 5 ô trong Sheet3 ghi "1-2 người" bị Excel đổi thành ngày `2026-02-01`.

**CHẶN QUẦY THU NGÂN, không phải lỗi code**

Bảng giá có **1/39 dịch vụ** và **0/80 thuốc** có giá. Quầy hiện đủ người mà
`còn phải trả = 0`. Notion đã ghi đây là việc phía khách ("Cần khách cấp data
chi phí dịch vụ khám…" và "…danh sách thuốc + tiền tương ứng").

---

## -0004. Nhóm đua tranh đã chạy — trên cả hai nơi (16/09/2026 ~14:00)

`scripts/tests/dua-tranh.py` — ba kịch bản mà **không ai bấm tay thử được**:

| | final mac | final cloud |
|---|---|---|
| SC-31  8 lịch bắn cùng lúc vào MỘT khung | ✅ đúng 2 lọt, trần 2 | ✅ đúng 2 lọt, trần 2 |
| SC-32  hai lễ tân cùng check-in một lịch | ✅ 200/409, đúng 1 lượt | ✅ 200/409, đúng 1 lượt |
| SC-33  bác sĩ + thư ký cùng sửa hồ sơ | ✅ 200/409 | ✅ 200/409 |

**Trần sức chứa giữ được dưới cuộc đua thật** — đây là bất biến đắt nhất của hệ:
tám lời gọi đồng thời, database vẫn đếm đúng 2. Ép ở Postgres (trigger), không
ở Python, nên không lối gọi nào vòng qua được.

⚠️ **Trần CHỈ chặn khi tuần đã công bố lịch trực** (luật Tuyền chốt 15/09).
Chưa công bố thì nhận thoải mái — đúng ý, nhưng nghĩa là **phải công bố lịch
trực thì trần mới có tác dụng**. Cả hai nơi hiện đang KHÔNG có tuần nào công bố;
tôi dựng tạm một tuần để thử rồi gỡ đi.

### Bốn lần phép thử sai trước khi đúng — ghi lại vì sẽ lặp
1. Lấy "cơ sở active đầu tiên" → rơi vào nơi bác sĩ không làm. Lấy từ `/me`.
2. Bịa giờ "bây giờ + 20 phút" → rơi vào giờ nghỉ trưa. Đọc `/appointments/policy`.
3. Kết luận "cho chen lọt" khi 8/8 lọt — trong khi tuần chưa công bố lịch trực
   nên KHÔNG có trần. Phép thử nay hỏi `roster_week_published` rồi mới kết luận.
4. Tệp dấu vết bị GHI ĐÈ mỗi lần chạy → lần trước mất đường dọn, và lần sau đếm
   cả dữ liệu cũ rồi báo đỏ nhầm. Nay nối thêm, và mỗi lần chạy mang dấu riêng.

Cả bốn đều là phép thử sai, không phải hệ thống sai.

### SC-34/35/36 đã chạy nốt — và tìm ra một lỗi thật

| | final mac | final cloud |
|---|---|---|
| SC-34 hai người cùng nhận một dịch vụ | ✅ 409/200 | ✅ 409/200 |
| SC-35 bấm thanh toán 2 lần | ✅ 200/200, database 1 khoản | ✅ 200/200, database 1 khoản |
| SC-36 bấm cấp thuốc 2 lần | ✅ 201/409, tồn trừ 1 | ✅ 201/409, tồn trừ 1 |

**SC-36 ban đầu HỎNG THẬT**: hai lời gọi cấp 1 viên bắn cùng lúc, cả hai trả
201, lô nhập 50 còn **48** — trừ tồn hai lần. `pharmacy.py` là cửa ghi DUY NHẤT
trong hệ không có lớp chống gửi trùng, mà lại là cửa duy nhất động vào vật thật.
Đã vá (`230ad82`), và ngay khi vá xong lộ thêm một lỗi thứ hai: lần bấm thứ hai
trả **500** vì kết quả mang `Decimal` mà `json.dumps` của lớp ấy không nuốt
được — người dùng sẽ thấy "lỗi máy chủ" cho một thao tác đã thành công.

Vì sao `/payments` không cần lớp ấy mà vẫn đúng: mỗi lượt khám chỉ có một khoản
thu mỗi loại nên ghi đè là đủ. Cấp thuốc thì **cấp một phần là hợp lệ**, nên hệ
không thể tự phân biệt "bấm nhầm" với "cố ý cấp thêm" — khoá chống-gửi-trùng
chính là chỗ người gọi nói ra điều đó.

### Nhóm ngoại lệ — 6/6 xanh ở cả hai nơi (`scripts/tests/ngoai-le.py`)

SC-08 huỷ trước khi đến · SC-09 đánh không đến · SC-10 check-in rồi về ·
SC-11 đã check-in vẫn đặt được ngày khác · SC-12 quay lại bấm check-in lần hai ·
SC-28 lịch lùi vào khung đã qua.

SC-10 kiểm CẢ HAI phía: bảng làm việc 1 → 0, **và** truy vấn thẳng database thấy
lượt còn nguyên ở `INCOMPLETE`. "Rời bảng" khác "bị xoá" — chỉ nhìn bảng thì
không phân biệt được.

Còn lại chưa chạy: SC-06 (đến lấy kết quả), SC-17/18 (kết quả về sau / có bản
sửa), SC-27 (đến sớm, đổi sang khám luôn), SC-29 (bác sĩ nghỉ đột xuất) — cả
bốn cần tính năng hoặc dữ liệu chưa có sẵn để dựng cảnh.

### Danh mục thuốc: 64 → 80
Thêm 16 dòng theo bảng Tuyền gửi 16/09. **12 dòng trong database không còn
trong bảng mới** — chưa xoá, chờ Tuyền xác nhận từng cái là BỎ hay ĐỔI TÊN
(Aspirin ↔ Aspilete, Folic Mum ↔ 5MTHF/ Folic mum trông như đổi tên). Danh sách
nằm trong `20260916000006_bo_sung_danh_muc_thuoc.sql`.

### Logo tab
`icon.png` từng là nguyên logo KÈM CHỮ → 16px thành vệt mờ. Nay chỉ còn dấu hiệu
hai vòng hạt. ⚠️ `.ico` phải nhúng RGBA, không thì `next build` chết — và `tsc`
KHÔNG bắt được lỗi ấy.

## -0003. Bản 15–16/09 đã LÊN VPS MỚI và chạy thật (16/09/2026 ~13:10)

`https://dr4women.io.vn` nay chạy nhánh `lat-1-luot-kham` (`8e74805`), không còn
là bản 22/08.

**Đường đưa mã lên:** VPS KHÔNG có khoá GitHub (repo private), nên đẩy thẳng qua
SSH — `git remote add vps clinic-vps-moi:clinicai`. Nhánh đang được checkout
trên VPS thì không nhận push; đẩy vào nhánh phụ `dua-len` rồi
`git merge --ff-only` là xong. **Đừng chép tay bằng `scp` nữa** — 7 tệp sửa tay
của phiên trước đã kéo về git (`b4e24e6`), giờ cây trên VPS sạch.

**Đã làm, theo đúng thứ tự an toàn:**
1. Sao lưu trước (130K, mã thoát 0).
2. **25 migration** áp bằng `apply-pending-migrations.sh --apply` → 79→90 bảng,
   119→144 migration, 69→92 policy.
3. `NOTIFY pgrst, 'reload schema'` (cạm bẫy #4 của phiên trước).
4. Dựng lại api + dashboard → cả hai `healthy`.
5. Quét 16 màn chính bằng 8 tài khoản thật: **15 × 200, 1 × 403** — cái 403 là
   thu ngân bị chặn khỏi bảng lượt khám, ĐÚNG luật.

⚠️ Tài khoản thử trên VPS là `letan bs.a bs.sa dd.sa cskh thungan duocsi ql`,
**không có `truongca` và `thuky`** — hai vai ấy chưa thử được trên máy chủ.

### Caddy đỏ 377 lần mà web vẫn chạy — đèn báo nói dối
Healthcheck gõ `http://localhost:80/health`; từ ngày bật HTTPS, Caddy chuyển nó
sang TLS với tên `localhost` (không có chứng chỉ) → `SSL alert number 80`. Đã
thêm khối `http://localhost` riêng trong Caddyfile (`4fefcb3`); nay `healthy`,
hỏng liên tiếp về 0. Một đèn đỏ giả nguy hiểm ngang một đèn xanh giả.

### Hiệu năng: tôi đoán sai chỗ, và số liệu chỉ ra chỗ đúng
Màn Đặt lịch mất **762ms** trên máy chủ. Giả thiết của tôi: truy vấn lịch trực
chạy 126 lần (18 hàng × 7 ngày). Đã gộp nó về 1 lần/tuần (`8e74805`), đối chiếu
**252 ô trên dữ liệu thật, lệch 0** — nhưng **tốc độ không đổi** (742ms).

`pg_stat_statements` trên prod nói thẳng:

| Truy vấn | Số lần | TB | Tổng |
|---|---:|---:|---:|
| **sức chứa** (`WITH hours … clinic_hours_for_date`) | 630 | **22,56ms** | **14,2s** |
| lịch trực (cái tôi vừa gộp) | 378 | 0,70ms | 0,27s |

Tức **98% thời gian database nằm ở truy vấn sức chứa**, và nó chạy đủ 126 lần
mỗi lần mở màn (không ô nào thoát sớm vì các tuần này chưa công bố lịch trực).
Bản gộp vẫn giữ — nó bỏ được 750 lời gọi vô ích và đã chứng minh không đổi kết
quả — nhưng **việc đáng làm tiếp là gộp chính truy vấn sức chứa** theo
(danh sách bác sĩ × khoảng ngày). Bộ đối chiếu ô-với-ô đã có sẵn, dùng lại được.

**Bài học ghi lại:** tôi đã suýt báo "đã tối ưu" chỉ vì mã gọn hơn. Số đo
trước/sau là thứ duy nhất phân biệt tối ưu thật với tối ưu tưởng tượng.

## -0002. Ba câu hỏi lớn — đã kiểm bằng số, 16/09/2026 14:20

### A. Database prod nằm ở đâu → CÙNG VPS. Tôi đã cảnh báo sai.

Tôi từng nói "coi chừng app ở Vietnix mà database ở Viettel thì mỗi truy vấn trả
tiền đường giữa hai nhà cung cấp". Kiểm lại: `docker-compose.supabase.yml` dựng
`db`, `auth`, `rest`, `realtime`, `gateway` NGAY TRÊN VPS; `docker-compose.yml`
dựng caddy/dashboard/api/worker/rabbitmq cùng chỗ. Viettel chỉ là kho sao lưu.
Tuyền nói đúng, tôi cảnh báo theo giả định chứ không theo mã. Cảnh báo ấy CHỈ
còn giá trị như một luật giữ chỗ: **đừng bao giờ tách database sang nhà cung cấp
khác với API**.
⚠️ `.env.prod.example` dòng 27 vẫn ghi `...pooler.supabase.com` — tàn dư của đời
Supabase cloud, dễ dẫn người sau đi sai. Nên sửa.

### B. Bỏ luồng chỉ định cũ → KHÔNG ĐỔI BÂY GIỜ. Quyết định của tôi.

Bức tranh thật khác hẳn mô tả trong chốt 16/09 (và khác cả điều tôi nói sáng nay):

| | Đường ĐANG CHẠY THẬT | Đường "mới" |
|---|---|---|
| Ghi vào | `work_item` (qua hàm SQL `order_services()`) + `service_order_draft` | `service_order` + `queue_entry` |
| Ai ghi | `ServiceOrderService` | CHỈ `luot_kham_service` |
| Màn | `/doctor/orders` (bác sĩ), `/service-queue`, `/sieu-am`, `/lab-queue`, bảng trưởng ca | `/luot-kham` — **chỉ Quản lý vào được** |
| Dữ liệu | nuôi 4 màn thực hiện | 37 dòng, toàn dữ liệu thử |

Nghĩa là `service_order` mới phủ phần **RA CHỈ ĐỊNH**, còn phần **THỰC HIỆN**
(hàng đợi phòng, siêu âm, xét nghiệm, điều phối) vẫn chạy trọn trên `work_item`.
"Bỏ luồng cũ" vì thế không phải đổi một nút — là viết lại phần thực hiện của cả
hệ, kéo theo 4 màn và bảng điều phối.

**Quyết: giữ `work_item` làm đường thực hiện** (nó là cái đang chở bệnh nhân
thật, và nó có kernel workflow). Thứ luồng mới có mà cũ thiếu — vòng
*nháp → bác sĩ duyệt* — thì ĐÃ có sẵn trên đường cũ dưới tên `service_order_draft`.
Nên việc đúng là **gộp**, không phải thay: đóng băng `/luot-kham` (không đầu tư
thêm), và nếu sau này muốn vòng đời draft→authorized→assigned đầy đủ thì thêm
cột trạng thái vào đường cũ chứ không dựng đường thứ hai.
Việc này cần một phiên riêng, KHÔNG làm chen giữa ngày khám.

### C. "Chậm vô lý" → đo rồi, KHÔNG có chỗ nào chậm vô lý.

Một lần mở `/reception/queue` = 4 lời gọi backend:
`/me` 0.6ms · `/appointments/policy` 4.5ms · `/thong-bao` 3.9ms · `/work-items` 34ms.
Tổng ~43ms; cả trang 20–40ms. p50 toàn hệ 11.8ms, p95 123ms, p99 151ms, 0 lời
gọi vượt 1s.

Nên nói thẳng: **cache lúc này không chữa bệnh gì cả** — nó là chuẩn bị cho tải
gấp 10. Thứ tự đáng làm khi cần:
1. `appointments/policy` (đổi rất hiếm, gọi MỖI lần render) → cache trong tiến
   trình TTL 60s. Lãi ~4.5ms/trang.
2. `/me` **KHÔNG cache** — cache một quyết định phân quyền là mở cửa cho lỗi phân
   quyền.
3. Tệp **không đi qua FastAPI** khi lên kho Viettel: dùng URL ký sẵn.

## -0001. Buổi khám thật chạy được trọn vòng trên local (16/09/2026, 12:00)

`scripts/tests/buoi-kham-that.py` giờ có KỊCH BẢN GHI, không chỉ đọc màn:

```bash
set -a && . ./.env.thu-local && set +a
PYTHONPATH=src poetry run python scripts/tests/buoi-kham-that.py --ghi 5
PYTHONPATH=src poetry run python scripts/tests/buoi-kham-that.py --rollback
```

Năm khách cùng lúc đi hết vòng: CSKH mở hồ sơ + đặt lịch → lễ tân check-in →
điều dưỡng đo mười ô sinh hiệu → bác sĩ vào khám, ghi chú, chỉ định → trưởng ca
xếp phòng → người thực hiện làm xong. Mỗi bước do ĐÚNG VAI gọi nên nó cũng là
phép thử quyền. `--rollback` huỷ lịch + tắt hồ sơ (không xoá cứng) rồi ĐỌC LẠI
bảng để tự kiểm; dấu vết nằm ở `.dev-logs/buoi-kham-that-dau-vet.json`.

**Hai lỗi thật tìm được, đã vá (d7ee31a):**
1. `VitalsBody` thiếu bốn chỉ số mới → nhịp thở/SpO₂/BMI/thang đau bị Pydantic
   cắt trước khi tới service, ghi NULL trong im lặng.
2. Huỷ lịch / hoàn tác check-in chỉ huỷ `work_item`, để lượt ở IN_PROGRESS →
   lượt ma nằm trên bảng bác sĩ cả ngày. Nay đóng thành INCOMPLETE kèm lý do.

**Hai cái bẫy ĐO, không phải lỗi sản phẩm** — ghi lại để đừng mất công lần nữa:
- Quét route bằng `fetch` trong trình duyệt: mặc định lấy từ **bộ nhớ đệm HTTP**.
  Đo lại phiên vai khác mà quên `cache:"no-store"` là đọc lại HTML của vai trước.
- HTML trả về CÓ tiêu đề trang bị chặn (vd "Quản lý nhân sự" khi đang là lễ tân)
  — tiêu đề ấy do `GlobalHeader.tsx` dựng theo đường dẫn và được đẩy đi TRƯỚC khi
  `requireNavAccess` kịp chặn. Gác cửa **vẫn đúng**: điều hướng thật bị đá về
  /home. Muốn kiểm thì tìm nội dung riêng của trang, đừng tìm tiêu đề.
- Trang chủ đo được 3–16 GIÂY vài lần — hoá ra do TÔI dùng chung một cookie phiên
  ở hai nơi (curl + trình duyệt), làm khoá làm mới xoay vòng đá nhau. Một phiên
  một máy thì 45–119ms sau 45s nghỉ. ⚠️ Nhưng nó gợi ra một câu hỏi thật: **một
  tài khoản mở trên hai máy** sẽ gặp đúng cảnh ấy.

**Số đo (local, 46 hồ sơ · 14 phòng):** 8 vai đăng nhập song song 108ms · 10 màn
chính gọi đồng thời trung vị 12–23ms · 5 khách đi trọn vòng 79 lời gọi, hỏng 0 ·
40 route của Quản lý qua lớp Next trung vị 21ms, không route nào 5xx.
Số đo đầu tiên sau khi khởi động lại máy chủ (trung vị 117ms) là số của bộ nhớ
đệm lạnh — đừng lấy nó làm chuẩn.

## 0000. Phiên 16/09/2026 (chiều) — Lễ tân · Trưởng ca · chốt lâm sàng

Nối tiếp mục 000. **13 commit**, từ `6dedcc3` tới `f81cc9b`. Chưa push.

### Đã xong
· **CSKH (nốt)**: cột danh sách hẹp chỉ còn tên + mới/cũ; màn Đặt lịch bỏ hàng
  lọc thừa, bỏ ô "Khung giờ khả dụng" (trùng popup), popup báo chỗ người khác
  đang giữ (VÀNG, vẫn bấm được — giữ chỗ là tư vấn); lọc bác sĩ chuyển vào
  chính cột "Bác sĩ" của bảng tuần và SỐNG QUA việc đổi khách.
· **Lễ tân**: bỏ hẳn luồng "vãng lai" — nay chỉ là KÊNH ĐẶT "Trực tiếp"; mở
  `/appointments` cho quầy (trước đó hai nút "Đặt lịch mới" đá về /home);
  hàng đợi gộp một hàng chung kéo-thả tại chỗ, bỏ bảng "Thứ tự khám" riêng;
  hai nút quy trình gộp thành "Vào khám"; bỏ 2 mục thanh bên thừa.
· **Trưởng ca**: bốn ô số · "Điều phối nhanh" (dùng lại dữ liệu cảnh báo vốn
  tải rồi vứt đi) · "Sơ đồ phòng đang dùng" theo tầng; BỎ "tuyến điều phối"
  cứng, thay bằng **"Bác sĩ chỉ định gì"** kèm số người đang chờ ở từng bước;
  thanh bên bỏ 5 mục (trưởng ca không làm thay người khác).
· **Lâm sàng** (5 quyết định Tuyền chốt sau khi đối chiếu tài liệu bàn giao 618
  dòng + phiếu chỉ định giấy + 14 ảnh thiết kế):
  1. Điều dưỡng **chỉ ghi sinh hiệu** (đảo quyết định 29/6), khoá cả hai phía.
  2. **Bật phiếu Nam khoa** qua đúng cổng duyệt `activate_clinical_form`.
  3. **Nhịp thở · SpO₂ · BMI · thang đau** vào `vital_measurement` thật.
  4. **Tệp kết quả**: bác sĩ / thư ký / điều dưỡng tải lên được, ngay trong hồ
     sơ khám; tệp do bác sĩ tải thì được gửi ngay, người khác tải vẫn chờ duyệt.
  5. **Kết quả siêu âm phụ khoa có ô cấu trúc** (tử cung, nội mạc, buồng trứng
     ± AFC, phần phụ, dịch) — ô trống KHÁC số 0.
· **Fixture**: `so_do_tang_demo.sql` (3 tầng, 14 phòng, khai `clinic_room_node`
  còn thiếu bước "Khám") và `ngay_dieu_phoi_demo.sql` (đóng rác ngày cũ, dựng
  18 lượt hôm nay, xếp phòng, 6 chỉ định đủ trạng thái). Chạy lại được.

### Còn nợ — việc LỚN nhất trước mắt
· **Bỏ luồng chỉ định cũ, giữ `service_order`** (Tuyền đã chốt, CHƯA làm). Ba
  bước: mở luồng mới cho bác sĩ + thư ký → chạy đối chiếu một lượt khám thật →
  gỡ luồng cũ (`order_services()` + OrderComposer). Câu phải hỏi khi tới bước
  ba: chỉ định cũ trong database có cần chuyển sang bảng mới không.
· Điều dưỡng gọi bệnh nhân ở hàng chờ dịch vụ (Tuyền chốt) — chưa dựng màn.
· **Không** chặn "thanh toán trước khi thực hiện" (Tuyền: xong xuôi mới thu).
· Kết quả xét nghiệm dạng bảng chỉ số + khoảng tham chiếu — CHƯA chốt; hiện đi
  đường ô chữ + đính kèm tệp.
· ~25 mã dịch vụ trong ảnh chưa có trong danh mục 39 mã; chưa có mã ICD-10.
· Chưa kiểm 3 cỡ màn 375/768/1280 cho các màn mới.

### Bẫy gặp trong phiên
· `demo_clinic_day.sql` KHÔNG chạy lại được: mở đầu bằng `DELETE FROM visit` mà
  `visit` là bảng chỉ-ghi-thêm.
· Năm ràng buộc database bắt fixture viết đúng luật: `finished_at` khi việc về
  trạng thái cuối · lượt INCOMPLETE phải có lý do · `consultation` cần
  `round_no` + `kind` khớp nhau · huỷ lịch mã KHAC phải viết rõ lý do · trần
  vãng lai 1 chỗ/khung.
· Bài kiểm "gương hai chiều" bắt đúng chỗ bỏ sót: gỡ màn khỏi thanh bên mà quên
  gỡ ở guard API.
· `node --test` không nạp `.tsx` — hàm thuần phải nằm ở file `.ts` riêng.

## 000. Phiên 16/09/2026 — Làm lại VAI CSKH trên local (đã commit, chưa push)

Tuyền chốt thứ tự: xong nghiệp vụ/giao diện/lỗi trên LOCAL theo từng vai, online
(VPS/Viettel/file storage) bàn sau. Tuyền gửi 4 ảnh ChatGPT (trang chủ, đặt lịch,
khách mới, danh sách BN) + chốt hành trình khách → memory
`cskh-hanh-trinh-khach-1609`, `lo-trinh-hoan-thien-local-theo-vai-1609`.
Nhánh `lat-1-luot-kham`: `00c23ad` (luật 15/09) rồi 6 commit CSKH:

1. `733d98c` Dòng trạng thái khách: bỏ "Làm bước này", vòng tròn = nút (bấm ghi,
   bấm lại hoàn tác — sổ giữ dòng); ô KHOÁ đồng bộ từ lễ tân/bác sĩ/đối tác; bỏ
   Vượt sức chứa/Nhắc hẹn mai/Sau sinh/Sau thủ thuật 1 ngày; màn CSKH KHÔNG còn
   đóng lượt (CHECK_OUT) — checkout là lễ tân. Migration 20260916000001
   `visit.theo_doi_thu_thuat` + GET/PUT /visits/{id}/theo-doi-thu-thuat, ô chọn ở
   mục X hồ sơ khám. CSKH mở được Chờ xếp bác sĩ; cơ sở mặc định form khách mới.
2. `bc13bcf` Khung báo dưới tên khách (khung-bao.ts thuần + test) + thanh chọn
   lượt theo đợt ở đầu vùng làm việc.
3. `57af6e8` Một nguồn "còn chỗ": quote thêm `con_lai`/`dat_tu_do`; GET
   /appointments/cho-trong-tuan (Bác sĩ × 7 ngày, tóm từ chính quote; ít chỗ ngày
   = ≤2 chỗ hoặc ≤20%, `clinic.settings.it_cho_toi_da`). Màn Đặt lịch: bảng tuần
   + popup + "Khung giờ khả dụng"; dọn ~400 dòng lưới tự đếm chỗ.
4. `4334722` Form khách mới dùng chung bảng tuần; tab Có sẵn/Mới; ô Kênh đặt
   (Trực tiếp·Điện thoại·Hotline·Zalo·Facebook·Website·Giới thiệu).
5. `4336fb1` Trang chủ: ô số bấm được (Lịch cần xử lý thay Lịch chờ xác nhận),
   gập ngày, menu "…", "Đặt lịch vào đây" → /appointments?ngay=&gio=&bac_si=.
   **Lỗi**: "bác sĩ đã đổi lịch" bật cho tuần CHƯA công bố lịch trực → nay chỉ
   tính tuần đã công bố (trang chủ + Quản lý khách hàng).
6. `f9ce522` Danh sách BN về backend GET /patients/danh-sach — qua nửa đêm không
   mất lượt đang mở (local 21, bản cũ 0); lịch sử lượt trong hồ sơ.

Kiểm mỗi bước: pytest phủ ≥80% (1896, 80.27%) · mypy src · máy kiểm phạm vi 0 ·
tsc · eslint 0 · test node CI · xem/bấm trên stack local (dev-up.sh). Chưa kiểm
đủ 3 cỡ 375/768/1280 (mới 1440). **Còn lại CSKH:** lưới vãng lai của lễ tân vẫn
dùng CinemaSlotPicker (làm ở vai lễ tân); `nutLoiRa`/HanhDongTrangThai còn các
case VUOT_SUC_CHUA/NHAC_HEN_MAI chỉ vào qua khung báo. Vai tiếp: **Lễ tân**.

## 00. Phiên 15/09/2026 — Sửa luật hệ đang chạy theo CONTEXT v1.0 (CHƯA COMMIT)

**Quyết định của Tuyền (15/09 chiều):** code thẳng trên Dr4Women, không chờ
ClinicAI-final; sửa từng luật trái CONTEXT v1.0. Bản đối chiếu hai hệ (danh
sách luật sai + nguồn) nằm ở scratchpad phiên, file
`DOI-CHIEU-DR4WOMEN-CLINICAI-FINAL-20260915.md` + PL1–PL4 — xin Tuyền chỗ lưu.
VPS Vietnix vẫn hết hạn → không deploy gì; mọi thứ nằm trên cây làm việc của
nhánh `lat-1-luot-kham` (lẫn với lát 1 chưa commit — tách PR theo file khi commit).

**Đã xong, đã kiểm:**
1. **Gỡ ca trực không huỷ lịch** (`config_service.RosterService.remove`): lịch
   rơi ra ngoài ca còn lại chỉ bị gỡ bác sĩ → hàng "Lịch chờ xếp bác sĩ";
   thêm event `roster.shift_removed`; tin Telegram + hộp xác nhận đổi câu.
   Đảo #117 — lý do ghi trong docstring và `test_khoi_phuc_lich_khi_xep_lai_ca.py`.
2. **Trần sức chứa chỉ chặn sau khi công bố tuần** (migration
   `20260915000001`): trigger + `booking_service._slot_full` hỏi cùng hàm
   `tuan_lich_truc_da_cong_bo`; lưới BookingHub không khoá ô đủ trần khi tuần
   chưa công bố. `apply_week` đối soát bằng `khung_vuot_tran_trong_tuan` →
   thông báo KHAN cho TRUONG_CA, trả `khung_vuot_tran`, không huỷ lịch nào.

3. **Hàng chờ bỏ hai làn tự vượt** (`queue_order.py`): vé ƯT chỉ còn nhãn
   `uu_tien`; người quay lại đọc kết quả được CHÈN sau mọi người đã chờ lúc
   kết quả cuối cùng về (`lab_result.result_received_at` → `b3_ready_at`).
   **Tuyền CHỐT 15/09: không phân biệt có hẹn/đến thẳng — ai check-in trước
   khám trước** (thay [CHƯA RÕ] ở CONTEXT §6). Giờ hẹn + độ dài khung chỉ còn
   quyết lý do hiển thị; câu TV "được ưu tiên vì đã đặt lịch trước" đã gỡ. TV
   và lưới tuần chưa tính "kết quả đã về" (có từ trước).
4. **Tuần đã công bố chặn cả gán/đổi/dời lịch** (`_guard_slot` gọi
   `_roster_warning`), và tự xếp ca khi gán bác sĩ (quyết định Quang 09/08)
   chỉ còn chạy ở tuần CHƯA công bố. Không bỏ hẳn việc tự xếp ca — không có
   dòng CHỐT nào gỡ quyết định đó.

5. **Đóng lượt giữ việc kết quả** (`checkout_service.close`): huỷ việc còn
   treo TRỪ node `flow_group = 'ket_qua'` (nhập/duyệt kết quả XN, tinh dịch đồ);
   trả + ghi event `viec_ket_qua_giu_lai`. Hạn của việc giữ lại CHƯA đặt (câu 8).
6. **Đơn thuốc đã cấp không bị xoá khi lưu lại bệnh án**
   (`clinical_record_service._replace_prescriptions`): dòng đã cấp/đã chốt bị
   khoá (đổi số lượng/xoá → 409, liều dùng sửa tại chỗ); dòng mới ghi
   `quantity_num`/`unit` — trước đó chốt "không cấp quá số kê" chưa từng chạy
   với đơn mới.

7. **Thư ký nhập — bác sĩ duyệt** (Tuyền chốt 15/09: bác sĩ đọc, thư ký nhập,
   màn bác sĩ hiện song song, bác sĩ duyệt; chưa duyệt CHỈ bác sĩ + thư ký thấy):
   - Đơn thuốc: một phiên khác làm 14:58–15:44 trên cùng cây (Tuyền cho Claude
     tiếp quản) — `clinical_record.revision` + `prescription_draft` (cột ẩn
     khỏi điều dưỡng, 20260915000005/007), `clinical_prescription_service.py`,
     form bác sĩ đồng bộ không đè chữ đang gõ (`lib/clinical-sync.ts`), nút
     "Kết thúc khám" riêng thay cho tự-khám-xong. Claude sửa 004/005 cho chạy
     lại được (CI bắt buộc).
   - Chỉ định dịch vụ (đường thật, không phải lát 1): bảng
     `service_order_draft` (20260915000008) — thư ký POST/PUT nháp, bác sĩ
     phụ trách duyệt đúng `expected_version` → `order_services` với danh tính
     bác sĩ trong cùng giao dịch; `create()` chặn TKYK. UI trong
     `OrderComposer` (panel "Chỉ định chờ bác sĩ duyệt", realtime qua
     `service_order_draft` trong LIVE_TABLES). Smoke Postgres 8 bước OK.
   - CHƯA: bảng bác sĩ chưa báo có nháp khi bác sĩ chưa mở màn chỉ định; chưa
     bấm thử trên trình duyệt (Claude không đăng nhập được app).

8. **Check-in lưu bằng chứng xác minh** (Tuyền chốt 3 cách: đối chiếu thông
   tin cá nhân / kiểm giấy tờ có ảnh / người nhà xác nhận): migration
   20260915000009 (visit.xac_minh_* + CHECK đủ bộ), `cach_xac_minh_bat_buoc`
   ở booking_service cho check-in quầy, vãng lai tự check-in và mốc CHECK_IN
   của CSKH; nút dùng chung `components/ui/NutCheckIn.tsx` — không có mặc định.
   Lớp bảo vệ: service bắt buộc; DB chỉ ép đủ bộ (lượt cũ/lượt điều dưỡng mở
   trước quầy không có bằng chứng).
9. **Nhắc lịch trước 7 ngày và 1 ngày** (Tuyền: đặt 2/9 lịch 15/9 → nhắc 8/9
   và 14/9): migration 20260915000010 đổi 2 nhánh `v_viec_cskh` — hạn = ngày
   khám − so_ngay, quá mốc là đỏ, việc nhắc 1 ngày không biến mất ngày khám;
   lịch đặt trong vòng 7 ngày không sinh việc 7 ngày (giả định của Claude —
   cuộc gọi đặt lịch vừa xảy ra). Test SQL `nhac_lich_truoc_7_ngay_va_1_ngay.sql`.

10. **AI đứng sau cờ + bác sĩ quyết báo kết quả:** không có ANTHROPIC_API_KEY
    thì API vẫn khởi động (endpoint AI trả 503 AI_DISABLED, orchestrator
    rule-based). Bỏ ba cổng AI chặn kết quả xét nghiệm: (a) `finalize_review`
    từ chối nhóm PENDING — chỉ định tay luôn PENDING nên không AI thì không
    duyệt được; (b) `lab_release_decision` chỉ cho GROUP_A — nay "bác sĩ đã chốt
    là được báo"; (c) `v_viec_cskh` KQ_CHUA_GUI sinh khi AI không gắn cờ — CSKH bị
    giục gửi kết quả chưa duyệt (sửa trong 20260915000010). Trang duyệt kết quả:
    nút "Ký duyệt" từng là nút giả → nối endpoint thật; hàng chờ lọc "có kết
    quả + chưa chốt" thay cho cờ AI; gỡ nút "Trả lại chỉnh sửa" (không có đường).
    Smoke Postgres: chỉ định → nhập → chưa duyệt không báo → duyệt → được báo.

11. **Tệp kết quả: bác sĩ cho phép gửi từng tệp** (Tuyền chốt 15/09, thay
    14/08): migration 20260915000011 (cột cho_phep_gui_* + trigger chặn
    gui_luc khi chưa cho phép + v_viec_cskh: CHO_BAC_SI → KQ_CHUA_GUI). API
    `GET /cskh/ket-qua/cho-phep-gui`, `POST /cskh/ket-qua/tep/{id}/cho-phep-gui`
    (chỉ bác sĩ); bác sĩ được mở nội dung tệp. UI: hàng chờ ở trang Duyệt kết
    quả (`TepChoPhepGui.tsx`); màn khách hàng hiện "Chờ bác sĩ cho phép gửi" và
    ẩn nút xác nhận đã gửi. Smoke Postgres 7 bước OK.

12. **Sinh hiệu: 100% huyết áp, có thai thêm cao/nặng, mỗi lần đo một dòng**
    (CONTEXT v1.0 [PM], thay D26 "3 trường cho MỌI khách" chỉ ép ở giao diện).
    KHÔNG dựng bảng mới: lát 1 đã có `vital_measurement` (huyết áp NOT NULL);
    `clinical_record_service._ghi_sinh_hieu` cho hồ sơ khám cũ ghi vào CÙNG bảng,
    qua CÙNG `luot_kham_rules.parse_vitals` + `thieu_sinh_hieu_khi_co_thai` (luồng
    khám mới cũng được thêm luật có thai). Đường điều dưỡng kiểm bộ gửi lên; bác
    sĩ lưu hồ sơ kiểm bộ sau gộp, và chỉ ghi dòng khi số đổi. JSON hồ sơ vẫn giữ
    bản mới nhất. Migration 20260915000012: trigger cấm sửa/xoá dòng đã đo
    (`xoa-du-lieu-test.sh` mở/đóng khoá như 7 bảng kia). UI `ClinicalRecordForm`:
    dấu * theo có thai. "Báo sốt → nhiệt độ" CHƯA ép (chưa có dữ kiện có cấu
    trúc). Hở còn lại: ghi từ màn cũ KHÔNG đổi `encounter_flow.vitals_status` —
    đổi mà không `_decide_route` thì lượt kẹt; hai màn nhập sinh hiệu cho cùng
    lượt là việc gộp màn của lát 1. Smoke Postgres 9 bước OK; 22 test DB lát 1 OK.

13. **Trưởng ca chỉ điều phối chỉ định bác sĩ đã duyệt** (CONTEXT v1.0).
    Migration 20260915000013 viết lại `move_visit_to_station`: tới bước dịch vụ
    (flow_group `dich_vu`/`ket_qua`) chỉ khi lượt đã có việc mở từ chỉ định —
    trước đây hàm tự INSERT việc (một "chỉ định" không bác sĩ nào ra); điều phối
    chỉ gắn phòng, KHÔNG tự bắt đầu; rời bước dịch vụ KHÔNG đánh COMPLETED (trước
    đây đổi thứ tự là siêu âm hiện "đã xong"). Nhà thuốc THUOC-* cần đơn thuốc.
    Bước ga (tiếp nhận/khám/thu ngân) giữ hành vi cũ. `apply_route` bỏ bước dịch
    vụ chưa chỉ định khỏi mẫu tuyến, trả `bo_qua_chua_chi_dinh` (toast trưởng ca
    nói bỏ mấy bước). Màn trưởng ca vốn không gọi `/dispatch/move` — lỗ hổng là
    ở API và tuyến. Luồng lát 1 (`/luot-kham/orders/{id}/dispatch`) không đụng.
    Smoke Postgres 9 bước OK; test SQL `dieu_phoi_chi_chi_dinh_da_duyet.sql`.
    **Câu hỏi mở phát sinh:** khách đặt lịch thẳng với BS siêu âm không có chỉ
    định nào sinh việc DICHVU-SIEUAM — trước đây chỉ `move` tạo được. Cần chốt:
    check-in lịch siêu âm có tự sinh việc siêu âm theo dịch vụ đã đặt không.

14. **Sức chứa = số khách online + số khách trực tiếp, quản lý đặt** (Tuyền chốt
    15/09 tối). Khung 3 tầng có sẵn (regular_cap = online, walkin_cap = trực
    tiếp). Migration 20260915000014: bỏ ghế VANG_LAI_TRE (khách hẹn đến muộn
    chiếm ghế trực tiếp — đếm 1 khách 2 lần); hàm `lich_vuot_suc_chua()` + việc
    CSKH `VUOT_SUC_CHUA` cho TỪNG lịch đặt sau cùng vượt trần ở tuần đã công bố
    (tự hết khi dời/huỷ/nâng trần/CSKH ghi chạm). `apply_week` báo cả CSKH và
    Trưởng ca. Chỉ Quản lý sửa luật đặt lịch (Trưởng ca còn đọc + cài TV). UI
    nhãn "online/trực tiếp", màn CSKH có việc mới. Test SQL
    `lich_vuot_suc_chua.sql`; `ghe_vang_lai_khach_den_muon.sql` +
    `dem_ghe_ca_ngay_mot_lan.sql` đảo khối người đến muộn kèm lý do.

15. **Lễ tân / quyền / ưu tiên** (Tuyền chốt 15/09 tối):
    - CSKH không check-in (CHECKIN_ROLES bỏ CSKH; CSKH đặt WALK_IN hôm nay bị
      chặn; màn CSKH bước "Đã check-in" chỉ còn chữ "Lễ tân check-in tại quầy").
    - Bác sĩ không nhận/từ chối lịch: bỏ action confirm/decline (DOCTOR_DECLINED
      cũ vẫn `reassign` được); xoá AppointmentActions.tsx (không ai import).
    - CCCD trùng: trả `cccd_trung` + hồ sơ trùng, gửi lại kèm lý do mới tạo
      (lý do vào event_log). Migration 20260915000015 bỏ UNIQUE. MPI CHƯA chấm
      CCCD (đo: 49 điểm) — chưa tự vào hàng gộp.
    - Bỏ vé/ghế ưu tiên → cờ `patient.uu_tien` + lý do (PUT
      /patients/{id}/uu-tien, lễ tân/CSKH/TC/QL); thứ tự khám kéo tay
      `visit.thu_tu_tay_ms` = trung điểm mốc hai người kế bên (POST /queue/keo,
      lễ tân/TC/QL). Migration 20260915000016. UI: bảng "Thứ tự khám hôm nay"
      kéo thả + ↑/↓ ở /reception/queue; nút "Đánh dấu khách ưu tiên" ở màn
      khách hàng; chip ưu tiên đọc cờ hồ sơ (bỏ is_priority_slot, bỏ hạng vé ƯT).
    - TV trưởng ca hiện số + tên (bảng gọi số chính vốn mặc định tên đầy đủ).
    Smoke Postgres 10 bước OK.

16. **Lâm sàng** (Tuyền chốt 15/09 tối):
    - Lịch hẹn thẳng với BS siêu âm → check-in tự sinh việc DICHVU-SIEUAM
      (`_open_visit`, payload nguon=lich_hen_sieu_am; check-in lại không nhân đôi).
    - Bác sĩ chính nghỉ giữa chừng: `DoiBacSiService` (POST /dispatch/doi-bac-si,
      TC/QL, bắt buộc lý do) đổi visit.attending_doctor_id + appointment.doctor_id
      + consultation/queue_entry luồng mới; migration 20260915000017 miễn trần
      sức chứa cho lịch đã CHECKED_IN/COMPLETED. UI ở panel bệnh nhân /truong-ca.
    - Miễn/huỷ bước phải có lý do; bước dịch vụ chỉ DOCTOR/ULTRASOUND_DOCTOR quyết
      (bác sĩ chính miễn được cả siêu âm/lấy máu).
    - Kết quả XN muộn: `CHO_KQ_XN` mặc định 3 ngày (20260915000018).
    - BMI: gợi ý từ cân/cao, bấm để điền, sửa được.
    Smoke Postgres 9 bước OK. Kiểm lượt 14–16: 1831 pytest · 331 node · tsc/eslint
    · ruff/format/mypy · tenant audit 0 · SQL suite 0 hỏng.
    **Chưa làm (cần thiết kế/hỏi):** thư ký theo bác sĩ (bảng ghép + màn nào dùng);
    "1 phòng 1 dịch vụ" (phòng khám đang phục vụ 5 chuyên khoa — dịch vụ là nhóm hay
    chuyên khoa?); làm lại dịch vụ (order_services gộp vào việc cũ kể cả đã xong —
    lần siêu âm thứ hai không hiện hàng chờ); MPI chưa chấm CCCD; giao diện trưởng
    ca (Tuyền sẽ chỉ); kế hoạch khám trước (O4); huỷ phiếu thu & hoàn tiền thuốc.

17. **Lượt Tuyền trả lời thêm (15/09 tối)**:
    - Check-in KHÔNG bắt chọn cách xác minh nữa (đảo luật 8): gửi thì ghi, không
      gửi thì thôi; NutCheckIn bấm là check-in; bỏ ô xác minh ở form vãng lai.
    - Huỷ phiếu thu: chỉ thu ngân ĐÃ THU phiếu đó (hoặc Quản lý); thu ngân khác
      bị chặn — trước đây ai cũng gạch được.
    - Lịch vượt sức chứa có CHỖ LƯU để xử lý: gộp vào trang "Lịch chờ xếp bác
      sĩ" (ly_do VUOT_SUC_CHUA, đổi bác sĩ/giờ qua reschedule), không huỷ lịch.
    - Thư ký theo bác sĩ: bảng `thu_ky_bac_si` (20260915000020) + mục "Thư ký
      đi cùng bác sĩ" ở /settings/clinic-config; thư ký đã phân chỉ thấy/ghi
      khách của bác sĩ mình (bảng việc, bảng lịch bác sĩ, nháp chỉ định, bệnh
      án); chưa phân = thấy cả phòng khám như cũ. Màn /result-review và
      /patients/[id] đọc thẳng Supabase — CHƯA lọc.
    - Chỉ định = danh sách tích: màn chỉ định hiện "Đã chỉ định", bác sĩ bỏ tích
      dịch vụ phòng chưa bắt đầu (POST /visits/{id}/service-orders/remove; hết
      dịch vụ thì huỷ việc phòng đó). Làm lại dịch vụ: Tuyền nói không cần.
    - Kết quả về (nhập kết quả XN lần đầu / tải tệp kết quả): chuông báo CSKH +
      ĐÍCH DANH bác sĩ của khách (chưa có bác sĩ thì báo vai bác sĩ);
      `ThongBaoService.goi_nguoi` + chỉ mục 20260915000019. Sửa lỗi thật: "về
      lần đầu" không đo được bằng result_received_at (NOT NULL DEFAULT now()).
    - Bảng bác sĩ: dấu "Chỉ định chờ duyệt" khi thư ký đã nhập nháp.
    - Phòng khám dịch vụ: Tuyền — do quản lý cấu hình (phòng ↔ bước, người ↔
      bước đã có) → không đổi code. Hoàn tiền thuốc: bỏ qua (chưa có tin).
    Smoke Postgres 7 bước OK. Kiểm: 1832 pytest · 331 node · tsc/eslint ·
    ruff/mypy · tenant audit 0 · SQL suite 0 hỏng.

18. **Thư ký theo bác sĩ — LUẬT CỨNG, qua backend** (Tuyền 15/09 khuya: "thư ký
    nào thì theo bác sĩ ấy, không được làm việc của bác sĩ khác"):
    - Thư ký CHƯA được phân bác sĩ → không thấy/không làm được khách nào (đảo
      mặc định "thấy cả phòng khám" của số 17); layout hiện dải cảnh báo.
    - Lọc ở FastAPI cho: bảng việc bác sĩ, lịch bác sĩ (/tasks), bảng lượt khám,
      hàng siêu âm, duyệt kết quả (GET /lab/results/cho-duyet — trang thôi đọc
      thẳng Supabase), nhập kết quả XN, tóm tắt trước khám, nháp chỉ định, bệnh
      án (ghi). Router mới `/thu-ky/pham-vi`, `/thu-ky/khach-duoc-xem`,
      `/thu-ky/khach/{id}` cho trang hồ sơ bệnh nhân, danh sách bệnh nhân và GET
      /api/clinical-record (đọc bệnh án).
    - "Khách của bác sĩ" = có lịch hẹn với bác sĩ đó hoặc lượt khám bác sĩ đó
      phụ trách. Smoke Postgres 7 bước OK; 1832 pytest · 331 node · audit 0.

19. **Bác sĩ thực hiện siêu âm** (Tuyền đồng ý 15/09 khuya): `work_item.assigned_to`
    của việc DICHVU-SIEUAM = bác sĩ siêu âm làm ca. Ghi khi: check-in lịch đặt
    thẳng BS siêu âm; BS siêu âm bấm "Nhận ca" (POST /ultrasound/queue/{id}/nhan)
    hoặc trưởng ca/quản lý giao; BS siêu âm đo/nhập kết quả ca chưa ai nhận. Thư
    ký của BS siêu âm thấy ca mình + hàng chung chưa ai nhận; ca đã giao bác sĩ
    khác thì không. Hàng siêu âm hiện "BS thực hiện"/"Chưa bác sĩ nhận". Phiếu
    siêu âm (tab soạn/đã ký) và nhập nháp kết quả cũng lọc theo thư ký. Smoke 5 bước OK.

20. **Rà backend còn thiếu (bản rà 15/09 khuya) — đã làm:**
    - P0 RLS: migration 20260915000021 — chính sách RESTRICTIVE `*_thu_ky_theo_bac_si`
      trên clinical_record, clinical_form_response, ultrasound_record, lab_result,
      prescription, patient_medical_profile, pregnancy, visit, tep_ket_qua,
      visit_amendment, vital_measurement: thư ký đọc thẳng PostgREST cũng chỉ
      thấy khách bác sĩ mình. Hàm `thu_ky_duoc_xem_khach` khớp Python. Test SQL
      `thu_ky_rls_theo_bac_si.sql`.
    - P0 siêu âm: nháp do thư ký/trưởng ca lưu không ghi họ làm người thực hiện
      (lấy bác sĩ đã nhận ca); bác sĩ đã nhận ca ký được, ký xong ghi đúng người.
    - P0 tài khoản nhân sự: mọi tạo/đổi mật khẩu/đổi tên đăng nhập/thu hồi ghi
      event_log qua POST /staff/{id}/nhat-ky-tai-khoan (thao tác GoTrue vẫn ở
      route Next vì backend chưa có khoá quản trị — chuyển hẳn cần thêm env).
    - P1: ký bệnh án gửi `expected_revision` (bản đang hiện trên form) — thư ký
      sửa sau khi mở thì từ chối; bỏ tích chỉ định bắt buộc lý do + chỉ bác sĩ
      phụ trách lượt; sửa hồ sơ khách ghi `patient.updated` (tên trường); cấu
      hình phòng/bước/người/thư ký ghi `clinic_config.*`.
    - P2: số khám khách trực tiếp do database cấp, bỏ số client gửi.
    Smoke P0/P1 7 bước OK; 1832 pytest · 331 node · audit 0 · SQL suite 0 hỏng.
    **CÒN LẠI (cần quyết/việc lớn):** Idempotency-Key bắt buộc +
    biên nhận trong cùng giao dịch (phải làm cùng giao diện gửi khoá); backend
    kết nối DB bằng quyền chủ (vai DB riêng — Quang); đơn thuốc chưa cấp xoá-ghi
    lại mỗi lần lưu; lab result ghi đè không giữ giá trị cũ; gỡ ca trực xoá cứng
    (có log); ngưỡng cảnh báo trưởng ca 20'/8 (chờ giao diện trưởng ca); JWT chưa
    kiểm `iss`; luồng /luot-kham lát 1 chạy song song (bỏ hay làm tiếp?); MPI
    chấm CCCD; tiền: số tiền do client gửi, sửa giá không log, thu lại sau huỷ
    đè dòng (để khi làm thanh toán).

21. **Dịch vụ làm lại trong cùng lượt = LẦN MỚI** (Tuyền: "siêu âm lại thì vẫn
    tính là lần siêu âm thứ 2 của lần khám"). Migration 20260915000022:
    `work_item.lan` + `ultrasound_record.lan`; chỉ mục duy nhất thêm cột lần;
    order_services chỉ gộp vào việc CÒN MỞ, bước đã xong/miễn → việc mới lần kế;
    viết lại instantiate_visit_workflow / move_visit_to_station / check-in lịch
    siêu âm theo chỉ mục mới. Phiếu siêu âm lần 1 đã ký + có lần mới → phiếu mới.
    Màn chỉ định hiện "(lần 2)". Smoke 7 bước OK (lần 2 vào hàng chờ, điều phối
    đúng lần, 2 phiếu, tính tiền 2 dòng, check-in lại không trùng bước ga); chạy
    lại smoke điều phối / đợt 3 / siêu âm / lượt 4 đều OK.
22. **Đóng gói để commit** (Tuyền: "làm thật hết, commit nếu ok hết"):
    - Ngưỡng cảnh báo điều phối **riêng từng phòng** do quản lý (và trưởng ca)
      chỉnh ở `/truong-ca/canh-bao` → `PUT /dispatch/threshold` (room_id rỗng =
      mặc định cả phòng khám). Đã có sẵn, nay có test HTTP khoá quyền + chỉ mục.
    - Ẩn màn "Luồng khám mới" (`/luot-kham`) khỏi menu, chỉ MANAGEMENT vào được —
      không chạy hai màn khám song song.
    - Migration cũ 20260803000006: khối dedupe phiếu siêu âm bỏ qua khi đã có cột
      `lan` (CI chạy lại migration sẽ xoá mất phiếu lần 2 nếu không chặn).
    - CI đòi phủ ≥80%: thêm test đơn vị theo luật (nháp chỉ định/duyệt/bỏ, ký
      theo revision/cho gửi/đính chính/ký siêu âm, điều phối qua HTTP, hàng chờ
      kéo tay, phạm vi thư ký, phiếu siêu âm lần 2) — `tests/services/fake_sql.py`
      trả lời theo nội dung câu SQL. Dọn 118 lỗi `mypy src/` trong file test.
    - Kiểm trước commit: 1875 pytest (phủ 80.04%) · ruff/format/mypy src/ sạch ·
      máy kiểm phạm vi 0 · tsc · eslint 0 cảnh báo · 327 test node CI · `npm run
      build` · infra safety · SQL suite kiểu CI + chạy lại migration.
23. **Chạy thật trên local** (`scripts/dev-up.sh`, Tuyền: "chạy được trên local đã"):
    áp 20 migration mới vào DB thử; script thử HTTP (scratchpad
    `smoke_http_local.py`, 32 bước: phân thư ký, check-in, ưu tiên + kéo thứ tự,
    nháp chỉ định → duyệt, ngưỡng từng phòng, chuyển bác sĩ, nhận ca siêu âm,
    lịch chờ xếp bác sĩ) chạy 3 lần liền đều 32/32. Bắt được và sửa:
    - **401 ngẫu nhiên ngay sau đăng nhập**: GoTrue trong máy ảo Docker nhanh
      hơn máy thật vài phần giây → `iat` ở tương lai, PyJWT lệch 0 giây từ chối.
      `identity.py` cho lệch 5 giây (`JWT_CLOCK_LEEWAY_SECONDS`) + 2 test.
    - **Bảng điều phối trưởng ca rỗng trên local**: `luot_kham_demo.sql` gán
      thư ký + trưởng ca vào cơ sở Kim Ngưu (0 phòng) trong khi 8 tài khoản kia ở
      MAIN → chọn cơ sở giống `staff_logins.sql` và cập nhật khi nạp lại.
    - Hướng dẫn in cuối `dev-up.sh` còn trỏ màn /luot-kham đã ẩn; 4 chú thích còn
      ghi check-in "bắt buộc xác minh" — đã sửa.
    Chưa bấm giao diện thật: Claude không được gõ mật khẩu vào trình duyệt —
    Tuyền đăng nhập tay theo danh sách tài khoản in cuối `dev-up.sh`.

**Tuyền chốt 15/09 tối (trả lời mục 7 bản đối chiếu)** — chi tiết ở memory
`tuyen-chot-luat-van-hanh-1509`. Tinh thần: luật khắt khe quá là vận hành rắc rối;
số liệu từng phòng khám để quản lý tự cấu hình.
- Sức chứa: mỗi bác sĩ × khung, quản lý đặt số khách ONLINE + số khách TRỰC TIẾP
  (lễ tân đặt xong check-in luôn). Bỏ 2+1 cứng. Chưa có lịch trực → đặt không giới
  hạn; có lịch trực → khách vượt trần (đặt sau cùng) báo về màn CSKH (+ trưởng ca).
- Bỏ ghế ưu tiên. Thay bằng cờ ưu tiên/VIP + lý do trên hồ sơ; lễ tân kéo thả thứ
  tự khám. Khám theo thứ tự check-in.
- CSKH không check-in. Bác sĩ không nhận/từ chối lịch. Chỉ Quản lý công bố/gỡ
  lịch trực. CCCD trùng: cảnh báo + lý do. TV hiện tên đầy đủ.
- Sinh hiệu: sốt/nhịp thở không bắt buộc; BMI tự tính là gợi ý, sửa được; sửa
  lúc nào cũng được, có log.
- Bác sĩ nghỉ giữa chừng: trưởng ca chuyển bác sĩ khác + lý do. Thư ký theo bác sĩ.
  Bệnh án: bác sĩ bấm xác nhận là chốt; sửa sau có log. Chỉ định trùng: cảnh báo;
  huỷ: bắt lý do. Dịch vụ không làm được: bác sĩ quyết. Kết quả muộn: CSKH theo dõi,
  hạn 3 ngày, cảnh báo tới khi xử lý. 1 phòng 1 dịch vụ. Gia hạn Vietnix.
- Tiền: quản lý thu được; khám xong mới thu; trừ kho tự động; kê thuốc tự đồng bộ
  kho → hoá đơn. Chưa trả lời: kế hoạch khám trước (O4), số khung chiều, form
  chuyên khoa, hoàn tiền thuốc đã giao.

**Quyết định 15/09:** khách ĐƯỢC đặt lịch thẳng với bác sĩ siêu âm → giữ nguyên
`BOOKABLE_DOCTOR_ROLES`; không làm luật "bác sĩ chính chỉ DOCTOR" cho lịch hẹn.

**(Cũ, đã đóng) Hoãn có lý do — bác sĩ chính chỉ DOCTOR:** đặt lịch với bác sĩ siêu âm là
thiết kế có chủ ý (`BOOKABLE_DOCTOR_ROLES`, 5 BS SA trong lịch trực thật,
ultrasound_service tự mở lượt với BS SA); CONTEXT chỉ bắt qua bác sĩ chính cho
lượt "chưa có kế hoạch trước hợp lệ" mà hệ cũ chưa có khái niệm kế hoạch trước
(O4). Ép cứng có thể chặn lịch siêu âm theo kế hoạch đang dùng thật → cần chốt.

Kiểm lượt 3 (luật 3 chốt + 5 + 6): 1702 pytest · 327 node · tsc · toàn bộ SQL
suite (0 hỏng) · smoke Postgres thật cho đóng lượt và đơn thuốc.

Kiểm lượt 2 (luật 3–4): 1700 pytest · 327 test node · smoke Postgres thật
(hàng B→A→C→D, gán BS không trực bị chặn ở tuần công bố, tuần nháp vẫn tự xếp).

Kiểm lượt 1: 1692 pytest unit · 270 test node · toàn bộ migration + 24 file SQL
assertion trên Postgres tạm (script `chay-test-sql.sh` trong scratchpad, không
dừng ở lỗi đầu) · smoke chạy thật cả hai luật trên Postgres tạm · ruff/format/
mypy/tsc/eslint.

**Luật sai còn lại, thứ tự định làm:** "+1" là ghế ưu tiên chứ không phải
ghế vãng lai (chờ câu 11, 13) → huy hiệu nháp chỉ định chờ duyệt trên bảng
bác sĩ → việc siêu âm cho khách đặt thẳng BS siêu âm (chờ chốt, xem 13).
Đã xong khỏi danh sách: điều phối (13), sinh hiệu (12), check-in xác minh (8),
TKYK không tự tạo chỉ định (7). Câu hỏi còn mở: mục 7 của bản đối chiếu.

Kiểm lượt 12–13: 1819 pytest · 331 node · tsc/eslint · ruff/format/mypy · máy
kiểm phạm vi 0 · SQL suite 0 hỏng · smoke Postgres sinh hiệu + điều phối.

## 0. Phiên 21→22/08/2026 — Chịu tải: Lát 1+2+3 xong, OOM tìm ra, đường ghi đã kiểm

**BỔ SUNG TRƯA 22/08 — Lát 3 + kiểm đường ghi (staging-0822e = `026669b7`):**
- **PR #162 (Lát 3)**: trang chủ gộp 6 vòng PostgREST + 3 endpoint rời về MỘT
  `GET /api/v1/home/bang-dieu-khien`; thêm SUSPENSE — lời chào + khung hiện
  tức thì, dữ liệu rót sau (hết cảnh bấm sidebar màn trắng). Đo: 54→35 câu
  SQL, 9→3 vòng, /home p50 dưới 100 người 3,6–3,7s → 2,9s. Khối theo vai do
  backend quyết từ identity. Suýt ship lỗi rò dữ liệu giữa người dùng (Map
  module-scope khử trùng lặp) — đã đổi sang `cache()` của React, có test canh.
- **Bộ kiểm ĐƯỜNG GHI dưới tranh chấp** (scratchpad `kiem-duong-ghi.py`,
  CHỈ CHẠY TRÊN STAGING — nó tạo lịch thật rồi huỷ mềm): 6/6 PASS giữa bão
  100 người đọc — đua ghế 15 người trần 2 → đúng 2 thắng 0×500; trùng khách
  5 lần → 1 lịch; giữ chỗ hiện chéo; huỷ đồng thời an toàn; sổ tương tác
  ghi/thấy/hoàn tác; khách inactive bị chặn 422. Sổ sự kiện cân từng cặp
  (created×8=cancelled×8). TUYỆT ĐỐI không chạy bộ này trên prod.
- Chip đã tạo: endpoint GET timeline tương tác mồ côi (không màn nào dùng,
  hiện cả dòng đã hoàn tác như thật) — chờ quyết gỡ hay sửa.

**CHECKLIST DEPLOY PROD batch #150–162 (Tuyền bấm, khung 1h–4h; đã soát
ngầm chỉ-đọc 22/08: prod đủ MỌI cột/bảng/view code mới đọc, chỉ thiếu đúng
hàm của bước 1):**
1. Áp migration TRƯỚC (bỏ qua bước này là lưới đặt lịch prod 500):
   `git fetch origin main && git show FETCH_HEAD:supabase/migrations/20260821000002_dem_ghe_ca_ngay_mot_lan.sql | ssh clinic-vps 'docker exec -i clinicai_db psql -U postgres'`
2. Bấm CD như mọi khi (prod tự nhận RAM 1g từ compose — không có override).
3. Ghi sổ migration prod (9 dòng 20260812000001→20260821000002, câu INSERT
   y như đã chạy trên staging — xem lịch sử phiên 22/08).
4. Trần pool supabase-stack prod (#158), lúc vắng khách:
   `docker compose -f docker-compose.supabase.yml --env-file .env.prod -p clinicai_db up -d auth rest`
5. Báo "xong" — phiên AI sẽ kiểm hậu-deploy CHỈ-ĐỌC: container có ký hiệu
   mới, /health, log sạch, RAM 1g, KHÔNG tạo dữ liệu nào trên prod.

**Nhiệm vụ Tuyền giao trước khi ngủ:** "đo lại staging → làm Lát 2 → làm hết
các nghi vấn, không làm hỏng hoặc kém đi, xong báo cáo."

**Đã lên staging (`staging-0822d` = `bc2de348`, xác minh bằng cách hỏi container):**
- **PR #157–159 (Lát 1)**: bộ nhớ tạm danh mục theo phòng khám, phân trang
  /customers 50 khách/trang, trần pool gotrue+PostgREST=10 (đăng nhập hết 500).
- **PR #160 (Lát 2)**: mười vòng PostgREST làm giàu màn khách hàng gộp về
  `GET /api/v1/cskh/man-khach-hang` — mười câu SQL chạy tuần tự trên MỘT kết
  nối asyncpg. Hình trả về bắt chước PostgREST từng trường nên page.tsx giữ
  nguyên phần dựng map. Guard 7 vai có test gương hai chiều với roles.ts.
- **Đo trước→sau** (cùng đêm, cùng máy, bảng đầy đủ trong PR #160):
  - Giải phẫu 1 lần mở /customers: 73→50 câu SQL, 14→4 vòng PostgREST,
    44→20 câu nghi lễ.
  - 100 người ảo ×3 vòng: /customers p50 5734→2705ms (−53%), p95 8144→4190ms;
    tổng 25,6→30,2 lượt/giây, 1300/1300 ok.

**Phát hiện lớn nhất đêm nay — OOM-kill worker im lặng:** `.env.staging` trên
VPS (cả hai bản) ghim `DASHBOARD_MEMORY_LIMIT=512m`, đè mặc định 1g mà #152
đưa vào compose. 4 worker ×~125MB vượt trần → kernel giết worker giữa response:
63/1300 lượt đứt kết nối (RemoteDisconnected/IncompleteRead), app-log sạch
bong. Chẩn đoán bằng `docker inspect --format '{{.State.OOMKilled}}
{{.HostConfig.Memory}}'`. Đã sửa env + `docker update --memory 1g` → 1300/1300
ok. **Prod không có override nên lần deploy tới tự nhận 1g — không cần sửa.**

**Đã ghi sổ migration staging**: 9 dòng `20260812000001`…`20260821000002` vào
`supabase_migrations.schema_migrations` (từng cái xác minh object trước khi ghi).

**Việc chờ Tuyền (prod — nút bấm của Tuyền, khung 1h–4h):**
1. Deploy batch #150–160 lên prod. **TRƯỚC đó** áp migration
   `20260821000002_dem_ghe_ca_ngay_mot_lan.sql` vào prod bằng psql
   (`git show FETCH_HEAD:supabase/migrations/20260821000002_dem_ghe_ca_ngay_mot_lan.sql | ssh clinic-vps 'docker exec -i clinicai_db psql -U postgres'`)
   — prod đã soát: đủ mọi migration khác, chỉ thiếu đúng cái này.
2. Ghi sổ prod (9 dòng, cùng câu INSERT như staging — xem PR #160 / phiên này).
3. Áp trần pool supabase-stack prod (#158): `docker compose -f
   docker-compose.supabase.yml --env-file .env.prod -p clinicai_db up -d auth rest`
   lúc vắng khách.
4. PR #144 (lễ tân) vẫn chờ quản lý duyệt trên staging.

**Nghi vấn đã đóng / còn mở:**
- ✅ RemoteDisconnected khi tải = OOM 512m (ở trên). ✅ Danh sách khách 5 giây
  = phân trang + Lát 2. ✅ Đăng nhập 500 khi đông = pool không trần (#158).
- ⏳ Suspense/streaming (P2 của cố vấn): hai trang nặng nhất (customers 1184
  dòng, home 489) đều là một server component nguyên khối, không Suspense.
  Đánh giá đêm nay: dưới tải, nút thắt là CPU render chứ không phải chuỗi
  chờ, nên streaming cải thiện cảm nhận (TTFB) chứ không tăng thông lượng —
  đáng làm thành LÁT 3 riêng, không sửa vội lúc cuối phiên.
- ⏳ /home p50 ~3,6s dưới 100 người: ứng viên Lát 3 (cùng cách gói như Lát 2).

**Cạm bẫy mới trả giá phiên này:**
- Sửa `mem_limit` trong git mà máy đích có `.env.*` ghim giá trị cũ thì
  override thắng IM LẶNG — đổi tài nguyên xong phải `docker inspect` máy đích.
- Container restart là `/tmp/tai.py` (harness đo tải) bay — chép lại trước
  mỗi lần đo, và đừng chạy đo song song với đo giải phẫu (bẩn cửa sổ log).
- 4 test biên đỏ khi Lát 2 dọn truy vấn về backend — ĐỎ ĐÚNG THIẾT KẾ; viết
  lại theo Luật 12.5: tiền đề dọn nhà thì test đi theo (giờ chúng đọc cả file
  Python). Đừng xoá assertion, đổi địa chỉ cho nó.

---

## 0.1 Phiên 21/08/2026 (Tuyền) — Ba ca làm việc, đã LÊN PROD trọn gói

**Một ngày nay chia BA ca thay vì hai, giờ do quản lý tự đặt.** PR #145–#148
đã gộp; prod deploy giữa giờ khám theo yêu cầu của Tuyền (vượt khung 1h–4h có
ghi lý do, run 32457538585, gián đoạn ~50 giây); staging = `staging-0821f`.

- **Kernel**: `core/shifts.py` viết lại — `shift_window()` (một khoảng) thành
  `shift_windows()` (danh sách), vì "cả ngày" nay là HAI khoảng rời nhau do
  nghỉ trưa. Giờ ca đọc từ `clinic.settings->'ca_lam_viec'`, mặc định Dr4Women:
  sáng 08:00–13:00 · chiều 14:00–17:30 · tối 17:30–21:30.
- **Migration `20260821000001`** đã áp CẢ HAI database (prod áp 21/08 chiều,
  đo trước khi áp: 1 lịch sống duy nhất nằm trong khung, 0 lịch từng đặt sau
  21:30 nên thu giờ đóng 23:00→22:00 không đụng ai).
- **Luật mới — chỉ đặt lịch TRONG ca** (`_chan_dat_ngoai_khung_ca`): gắn ở
  đúng 2 đường chọn giờ (đặt mới, đổi lịch); cố ý KHÔNG gắn ở đường gán bác sĩ
  để lịch cũ ngoài ca vẫn gán được. Lưới + 5 màn chọn giờ thôi mời giờ ngoài
  ca (mời-rồi-mắng làm người trực mất niềm tin vào lưới).
- **Quản lý tự sửa giờ ca**: Cài đặt → Luật đặt lịch → thẻ "Giờ ca làm việc"
  (Trưởng ca + Quản lý). Bốn luật chặn khi lưu, quan trọng nhất là "ca phải
  nằm trong giờ mở cửa" — sai kiểu này KHÔNG tự lộ, cấu hình lưu được nhưng bị
  cắt lúc đọc. Sai thì báo đủ mọi lỗi một lần, một lỗi một dòng.
- Xác minh trên CẢ prod lẫn staging bằng dữ liệu thật: 12/12 mốc giờ
  chặn/cho-qua đúng; lưới 50 khung 08:00→21:15; đổi giờ giả thì kết quả đổi
  theo (phân biệt "đọc từ DB" với "trùng mặc định").

**Kịch bản bấm thử cho quản lý (staging trước, prod đã giống hệt):**
1. Cài đặt → Luật đặt lịch → Giờ ca làm việc: sửa ca tối thành `17:30→23:00`,
   bấm Lưu → phải bị chặn, MỘT dòng "Mọi ngày mở cửa 07:00–22:00…".
2. Sửa ca chiều `12:00→17:30` → báo chồng ca sáng, có câu "KPI đếm đôi".
3. Sửa ca sáng `09:00→12:00`, Lưu → lưới đặt lịch bỏ các khung 08:00–08:45
   ngay (không cần F5). Thử xong TRẢ LẠI `08:00→13:00`.
4. Màn đặt lịch: không còn cột 13:00 (nghỉ trưa) và sau 21:15.
5. Lịch làm việc: xếp được ca **Tối** cho nhân viên.

**Việc sót lại của phiên (làm đầu phiên sau):**
- **Ghi sổ migration** — cả hai database áp `20260821000001` bằng psql tay,
  CHƯA ghi `supabase_migrations.schema_migrations` (staging còn thiếu cả
  `20260820000001` của #144). Lệnh:
  `INSERT INTO supabase_migrations.schema_migrations(version) VALUES ('20260821000001') ON CONFLICT DO NOTHING;`
- **PR #144 (lễ tân)** vẫn mở, chỉ ở staging (`staging-0820a`+), chờ quản lý
  duyệt; migration `20260820000001` của nó CHƯA áp prod — đúng, vì code chưa lên.
- Chip "siết cổng độ phủ": ngưỡng ghi 80 nhưng so sánh số ĐÃ LÀM TRÒN nên
  thực tế là 79,5. Đừng hạ số; viết thêm test vượt 80.00 rồi mới siết.
- HTTPS vẫn chưa có — toàn bộ chạy HTTP trần.

**Cạm bẫy mới trả giá phiên này:**
- `git fetch origin main && git tag X origin/main` gắn tag vào giá trị CŨ
  (chỉ `FETCH_HEAD` chắc chắn được cập nhật) → tag trỏ code cũ, CD deploy lại
  bản đang chạy, mọi thứ *trông như* đã lên. **Luôn tag vào SHA viết rõ**, và
  xác minh bằng cách hỏi CONTAINER có ký hiệu mới chưa, đừng tin nhãn CI xanh.
- `gh run list --workflow=cd.yml` hiện `headBranch=main` cho MỌI lần chạy, kể
  cả deploy tag staging → nhìn danh sách tưởng CD chưa từng chạy. Phải mở từng
  run xem JOB.
- Lệnh đưa cho người khác chạy phải trơ với ngữ cảnh: `git pull` trong
  worktree không upstream gãy im lặng giữa chuỗi `&&` (bước 2 của quy trình
  prod đã trượt kiểu này). Dùng `git show FETCH_HEAD:<file>` thay vì pull.
- Dòng giả trong test là `dict` thì có đủ khoá mình tự cho vào;
  `asyncpg.Record` thì KeyError. `capacity_service` đọc cột không SELECT, cả
  bộ test xanh, staging vỡ. Đã có `test_doc_dung_cot_da_chon.py` đối chiếu
  mọi khoá đọc với mọi cột SELECT.
- Phép đo phải PHÂN BIỆT được: giờ prod trùng giá trị mặc định nên "đọc từ
  DB" và "lùi về mặc định" cho cùng kết quả — phải thử bằng giờ giả khác hẳn.

---

## 0.2 Phiên 15/08/2026 (Tuyền) — 16 PR #112–#127 (nền gần)

**Đại tu giao diện xong cả 5 bước (0→4).** DESIGN.md là hiến pháp; nguyên tử
Button/Chip/NutInPhieu ở `components/ui/`; ratchet `[..px]` trần 102 (từ 474)
sống trong `px-tu-che-ratchet-boundary.test.mts` — vượt là CI đỏ, dọn được
thì phải hạ trần. Thanh cuộn ẩn tới khi rê vào vùng cuộn.

**Chuỗi lịch-bác-sĩ có kết thúc thật.** Xoá ca → lịch tương lai của ca ấy
HUỶ HẲN (mã `BAC_SI_DOI_LICH`, giữ vết `bac_si_da_go_id` cho câu "đổi từ
ai"); gán được bác sĩ là vết xoá, cảnh báo tắt; khung giờ trống thật để đặt
lại cùng khách + bác sĩ khác. Cơ chế "thêm lại ca thì lịch tự quay về" (#115)
đã GỠ theo quyết định của Tuyền — bia mộ kèm lý do trong
`test_khoi_phuc_lich_khi_xep_lai_ca.py`.

**Một bệnh nhân nhiều SĐT.** Bảng `patient_sdt_them` + cột gộp
`patient.sdt_tim_kiem` (trigger nuôi) — mọi đường tìm tra số nào cũng ra.
Nút "＋ Thêm số cho khách này" trong ô cảnh báo trùng (trùng SỐ lẫn trùng
TÊN — tên 3 ký tự là hỏi, không cần năm sinh); xoá số trong khối sửa hồ sơ.

**Telegram trọn bộ.** Bot `@chat_Tuyen_bot` ("Theo dõi Clinic"), token trong
`.env.prod` trên VPS; kênh: chat riêng Tuyền `8457103265` + nhóm
`-1003672911684` (MVP2: Clinic AI). Relay realtime (nghe pg_notify
`clinicai_changes`, trigger event_log CHỈ INSERT — nghe UPDATE là tự đánh
thức vô tận); 4 tin: lịch mới/huỷ/đổi/xoá ca; bot lệnh /trangthai /homnay
(chỉ trả lời kênh đã đăng ký, trả lời đúng nơi hỏi); Kuma cũng bắn cùng
kênh (4 monitor + Sao lưu đêm). KHÔNG SĐT khách nào qua Telegram — có test.
Đổi kênh: sửa `TELEGRAM_CHAT_ID` (danh sách phẩy) trong `.env.prod` rồi
`docker compose --env-file .env.prod -p clinicai_prod --profile notifications up -d notification-relay`.

**Cạm bẫy mới trả giá hôm nay:**
- PostgREST cache lược đồ — thêm bảng/FK mới thì `docker restart clinicai_rest`
  (đã ghi vào lệnh migration mẫu), không thì màn đỏ "Could not find a relationship".
- Migration prod là việc của người (classifier chặn agent ghi DB prod); thứ tự
  BẮT BUỘC: DB trước, code sau — CHECK chưa nới mà code ghi mã mới là 500.
- CI mypy chạy `src/` (không chỉ src/clinicai); tenant-scope audit đòi mọi câu
  ghi tự khoá clinic_id; drift-test audit_labels đòi nhãn Việt cho event mới.
- `gh pr merge` khi CI chưa xong sẽ trượt lặng lẽ — đợi `gh run watch` xong
  hẳn rồi mới merge + tag, không thì tag chỉa vào main cũ.

**Chờ quyết / việc treo:** dọn prod trước bàn giao
(`scripts/don-prod-truoc-ban-giao.sql` — Tuyền chạy tay); đổi mật khẩu chung
12345678 sau bàn giao; token bot đã đi qua khung chat — muốn kín thì /revoke
rồi thay trong .env.prod; nếu nhóm MVP2 thêm người ngoài thì tách kênh (tin
nghiệp vụ có tên khách + mã BN).

---

## 1. Hệ thống đang ở đâu

| | |
|---|---|
| Máy chủ | Vietnix VPS, `ssh clinic-vps` (222.255.215.219) |
| Prod | nhánh `main`, cổng 80, project `clinicai_prod` + database `clinicai_db` |
| Staging | cổng 8080, project `clinicai_staging` + database `clinicai_stg_db` |
| Migration mới nhất | `20260821000001_ba_ca_lam_viec` — đã áp cả hai (chưa ghi sổ, xem mục 0) |
| Cơ sở | **2**: Kim Ngưu (đang mở, 12 phòng, 40 nhân sự) và Hào Nam (`is_active=false`) |
| Dịch vụ khám | 5: PK · SK · NT · NK · HMVS |
| Danh mục chỉ định | 39 mục đang bật, 5 mục chưa gán phòng |
| Lịch làm việc | 2340 ô, đến **31/01/2027** (mẫu tuần 01–07/06 trải ra 26 tuần) |
| Tài khoản | 40, mật khẩu tất cả `12345678` |

**Prod KHÔNG còn rỗng.** Quang đã tự tạo 2 hồ sơ (`Lalaa`, `Nguyễn Thị Lan`) và
5 lịch hẹn ngày 07/08. Đừng coi prod là môi trường vứt đi được nữa.

Staging có 3 hồ sơ `ZZ…` (0 lượt / 1 lượt / 3 lượt) để thử màn danh sách.

## 2. Tài khoản

Dạng `<chức vụ><tên>@dr4women.vn`: `bacsithanh`, `bacsisieuamdat`,
`dieuduonghavu`, `letanthu`, `thukyvananh`, `manhinhphongcho`…

**Bốn tài khoản dùng chung còn lại** (`.local`) — vì bốn bộ phận này chưa có một
người thật nào trong danh sách nhân sự:

| tài khoản | bộ phận |
|---|---|
| `ql@dr4women.local` | Quản lý |
| `thungan@dr4women.local` | Thu ngân |
| `cskh@dr4women.local` | CSKH |
| `duocsi@dr4women.local` | Dược sĩ |

Có tên bốn người này thì tạo tài khoản riêng rồi chạy lại
`supabase/fixtures/xoa_tai_khoan_dung_chung.sql` — nó tự kiểm và tự xoá nốt.

**Đừng xoá `ql@` khi chưa có quản lý thật**: đó là vai DUY NHẤT tạo lại được tài
khoản cho người khác. Xoá xong thì không ai sửa được nữa.

Quản lý tự làm được ở `/settings/tai-khoan`: thêm tài khoản, **đổi tên đăng
nhập**, đặt lại mật khẩu, gỡ tài khoản.

## 3. Chờ Quang quyết

1. **Hào Nam** đang `is_active = false`. Cơ sở này đang mở hay chưa?
2. **Tên đầy đủ của BS Đào** — bác sĩ duy nhất còn tên tắt, nick vẫn là `bacsidao@`.
3. **Tên bốn người**: quản lý, thu ngân, CSKH, dược sĩ (xem mục 2).
4. **Hai tên trong bảng lịch làm việc chưa ghép được ai**: `Tiên` (trạm Máy
   ngoài) và `Trang A` (Lễ tân). Đang để `staff_id` NULL, giữ nguyên chữ trong
   bảng. Không đoán bừa — tên sai trong lịch trực thì không ai biết mà sửa.
5. **Mật khẩu `12345678`** hợp lý lúc chưa có bệnh nhân thật. Trước ngày nhận
   khách thì nên đổi: `./scripts/dat-lai-mat-khau.sh .env.prod 80 <mật khẩu>`.
6. **Lịch làm việc hết hạn 31/01/2027** — chạy lại
   `supabase/fixtures/lich_lam_viec_tuan_mau.sql` với `tu_ngay` mới.

## 4. Năm PR đang mở — KHÔNG phải đồ thừa

Đã đóng 5 PR có nội dung thật sự đã vào `main` theo đường khác (#7, #9, #12,
#13, #29). Năm cái còn lại đo lại rồi: **nội dung chưa có trong `main`**.

| PR | vì sao còn sống |
|---|---|
| **#43 Sentry** | `src/clinicai/core/sentry.py` CÓ trong `main` nhưng `sentry-sdk` **không có trong `pyproject.toml`**. Đã kiểm trong container prod: `ModuleNotFoundError: No module named 'sentry_sdk'`. Nghĩa là **hiện không có lỗi nào được báo về**, và log khởi động chỉ nói "SENTRY_DSN not set" nên nhìn qua tưởng cố ý tắt. Nên làm sớm nhất. |
| **#44 công cụ migration** | `scripts/apply-pending-migrations.sh` chưa có trong `main`. Hiện phải áp migration bằng tay qua `docker cp` + `psql`. |
| **#8 event_log actor** | `event_log` chưa có cột actor; "ai làm" đang chìm trong JSON, không truy vấn hay ràng buộc được. |
| **#10, #11 chọn phòng khám** | Màn cho bác sĩ làm hai nơi. Chưa cần (mới một phòng khám) nhưng không bị thay thế bởi gì cả. |

## 5. Chưa xây

- Sinh tài liệu / lưu trữ tệp: "Hồ sơ trả bệnh nhân", tệp đính kèm nhân sự.
- **208 dòng `event_log` chưa ai xử lý** — relay không chạy.
- `visit_gate_rule` chưa được thi hành ở đâu.
- ~~CD tắt~~ **CD ĐÃ CHẠY (21/08)**: runner `vps-clinicai` online. Tag `staging-*` → staging tự động; prod bấm `gh workflow run cd.yml`, chỉ khung 1h–4h (ngoài khung phải điền `ly_do_vuot_khung_gio`).

## 6. Cạm bẫy đã trả giá để biết

**Đo trên máy chủ, không đoán từ code.** Ba lỗi lớn nhất phiên này đều chỉ lộ ra
khi so prod với staging, hoặc khi mở màn hình ra nhìn:

- **`auth.uid()` bản rút gọn trong `bootstrap_plain_postgres.sql`** chỉ đọc
  `request.jwt.claim.sub`; PostgREST v12 chỉ đặt `request.jwt.claims`. Staging
  thừa hưởng bản rút gọn → mọi lượt đọc trả `[]` cho MỌI tài khoản, không lỗi,
  không cảnh báo. Đã sửa cho giống hệt bản thật.
- **`proxy.ts` gọi Supabase bằng địa chỉ trình duyệt.** Từ trong container, IP
  công cộng cổng 80 đi vòng được, cổng 8080 thì không → staging đá mọi request
  về `/login`, gõ đúng mật khẩu vẫn quay lại. **Prod đang đúng nhờ may**: một
  luật tường lửa là cả phòng khám mất đường vào. Đã sửa; nếu thấy chỗ nào khác
  còn dùng `NEXT_PUBLIC_SUPABASE_URL` phía máy chủ thì sửa nốt.
- **PostgREST giữ lược đồ trong bộ nhớ.** Migration mới không tự vào. Triệu
  chứng: `Could not find a relationship between 'appointment' and 'patient'` —
  số đếm vẫn ra nên trông như lỗi dữ liệu. `NOTIFY pgrst, 'reload schema'`.
  Đã thêm vào `dung-staging.sh`; **prod thì phải nhớ chạy tay sau mỗi migration
  có đổi bảng/khoá ngoại.**

**Khoá an toàn của script dọn từng vô dụng.** `don-du-lieu-thu.sh` có mẫu
`BN-2026-%` trong danh sách "dữ liệu thử", trong khi `_generate_patient_code()`
sinh đúng dạng `BN-<năm>-<6 số>` cho MỌI bệnh nhân thật. Khoá nhìn hồ sơ thật và
bảo "đây là đồ thử". Đã gỡ mẫu đó. **Không bao giờ thêm vào danh sách ấy một mẫu
mà chính ứng dụng sinh ra.**

**Test biên là bạn, không phải chướng ngại.** Phiên này chúng bắt tôi hai lần và
đúng cả hai: một lần chặn file mới với ra khoá service-role (ADR-0012), một lần
là chính nó siết quá chặt theo nguyên văn câu điều kiện. Đọc ý định của test rồi
mới quyết sửa test hay sửa code.

**Deploy chạy bằng docker của MÁY GÕ LỆNH.** Muốn lên VPS thì `ssh clinic-vps`
rồi chạy ở đó. `all healthy ✓` KHÔNG có nghĩa là tính năng chạy — `/health`
không chạm bảng của tính năng. Luôn gọi thẳng endpoint của nó, và mở màn hình ra
nhìn.

**Nhánh mọc từ nhánh cũ sẽ xung đột giả** sau khi PR gộp kiểu rebase (SHA đổi
hết). Chữa bằng `git rebase --onto origin/main <tip-cũ>`.

## 7. Bộ lệnh kiểm đầy đủ

```bash
poetry run ruff check src/ && poetry run ruff format --check src/
poetry run mypy src/
python3 scripts/tests/tenant-scope-audit.py --check
ANTHROPIC_API_KEY="" poetry run pytest src/tests/ -q -m "not db and not integration" \
  --cov=clinicai --cov-report=term --cov-fail-under=80
cd src/dashboard && npx tsc --noEmit && npx eslint . --max-warnings=0 \
  && npm run test:audit && npm run test:ops && npm run test:boundary && npx next build
```

Độ phủ đang **~79,8%** và cổng thực tế là 79,5 vì coverage so số đã làm tròn
(xem chip "siết cổng độ phủ"). Thêm code mới thì phải thêm test, đừng hạ ngưỡng.

## 8. Việc thường dùng

```bash
ssh clinic-vps 'cd ~/clinicai && git pull --ff-only origin main && \
  DEPLOY_EXPECTED_SHA=$(git rev-parse HEAD) ./scripts/deploy-backend.sh prod'
```

```bash
ssh clinic-vps 'cd ~/clinicai && CLINIC_ENV_FILE=.env.staging \
  docker compose --env-file .env.staging -p clinicai_staging up -d --build dashboard'
```

Áp migration (chưa có công cụ — xem PR #44):
```bash
scp supabase/migrations/<file>.sql clinic-vps:/tmp/m.sql && \
ssh clinic-vps 'docker cp /tmp/m.sql clinicai_db:/tmp/m.sql && \
  docker exec clinicai_db psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres -f /tmp/m.sql'
```
Nhớ ghi vào sổ `supabase_migrations.schema_migrations`, và `NOTIFY pgrst,
'reload schema'` nếu có đổi bảng hoặc khoá ngoại.

## 9. Bản thiết kế thống nhất + quy trình kiểm chứng một khẳng định

Bản đọc và vault Obsidian: `docs/thiet-ke-he-thong/`. **Nguồn sinh nằm ở
`docs/thiet-ke-he-thong/_nguon/`** — sửa nội dung ở đó rồi `python3 build.py`,
đừng bao giờ sửa tay `.md` hay `.html` đã sinh (mỗi lần dựng lại là mất).

Vòng phản biện 06/09/2026 (Codex đọc worktree `charming-mcclintock-d227f5` tại
`9376db8`) tìm ra **sáu** kết luận rút quá tay trong bản 05/09. Tất cả cùng một
lỗi: dừng ở `grep` hoặc ở một con số rồi suy ra ý định của hệ thống. Quy trình
dưới đây là thứ lẽ ra phải làm, ghi lại để phiên sau dùng.

**Trước khi viết một câu dạng "code không làm X":**

1. Truy đủ chuỗi **caller → service → SQL/event**, không dừng ở tên hàm.
   `grep "checked_in"` không thấy ở `tuong_tac_cskh_service.py` — nhưng nó gọi
   `_doi_trang_thai_lich` → `BookingService.apply_action` → `_log(...)`.
2. Đếm **mọi** nhánh phát cùng một event trước khi nói "một cửa ghi duy nhất".
   `appointment.checked_in` có hai nhánh: `apply_action` và `auto_checkin` cho
   khách vãng lai trong ngày (`booking_service.py:464`, `:623`).
3. Kiểm **mẫu số** trước khi biến tỷ lệ thành kết luận. "1 check-in / 66 lịch"
   vô nghĩa vì 66 là lịch *đã tạo*, không phải khách *đã đến*.
4. Hỏi **cờ này còn ai đặt được nữa không**. `event_published = TRUE` không
   chứng minh đã gửi: `scripts/danh-dau-event-cu-truoc-khi-bat-telegram.sql`
   đặt hàng loạt mà không gửi gì.
5. Trước khi nói "dữ liệu này vô dụng", tìm **ai đang đọc nó**.
   `AuditLogService.events()` đọc `event_log` làm nhật ký thao tác mỗi ngày.
6. Số dòng trong trích dẫn phải là **dòng thật của tệp**. `grep -n` trên đầu ra
   của `awk`/`sed` cho số dòng của đoạn cắt, không phải của tệp (đã cắn một lần:
   ghi `:106` trong khi dòng thật là `:227`).
7. Tách bốn thứ hay bị gộp: **ai thao tác** · **code phủ tới đâu** · **mức dùng
   đo được** · **quyết định sản phẩm**. Số đo trả lời ba cái đầu, không cái cuối.
8. Một hàm đặt cờ có thể có **nhiều nhánh gọi**. `_mark_published` chạy ở cả
   nhánh *không có template* (`notification_relay.py:205-214`, không gửi gì) lẫn
   nhánh gửi ok (`:238`), và `processed` cộng cả hai (`:256`). Đọc hết thân vòng
   lặp trước khi mô tả ngữ nghĩa một cờ.
9. **Hai cột bằng nhau không phải một phép đo**, nếu cả hai cùng `DEFAULT now()`
   và đường ghi truyền `now()` (`baseline_schema.sql:539-540`). Nó nói về cách
   ghi, không nói về thế giới thật.
10. Trước khi viết một câu truy vấn, kiểm **giá trị nằm ở cột nào**. `origin`
   không phải cột: `_log` đổ nó vào `source` và `metadata->>'origin'`
   (`booking_service.py:2019-2036`).
11. Đề xuất của chính mình cũng phải soi bằng đúng thước ấy. `seq bigserial`
   cấp số lúc INSERT chứ không lúc commit, và sequence có khoảng trống — nên
   `seq > last_seq` bỏ sót event, `max(seq) − last_seq` không phải số việc tồn.
   Tài liệu: `functions-sequence` và Wiki FAQ của PostgreSQL. Giao thức tiêu thụ
   trong bản thiết kế đang bị **chặn** cho tới khi có xác nhận theo từng event,
   consumer idempotent, và test commit đảo thứ tự + crash-retry.

**Nhãn bắt buộc trong tài liệu:** số đo cũ không chạy lại trong phiên phải ghi
*"chưa xác minh lại"*; suy luận phải nói rõ là suy luận và kèm phép đo còn thiếu.

**Sáu phép đo còn nợ.** Ghi thành *yêu cầu*, cố ý KHÔNG ghi sẵn câu SQL: câu
viết vội đo nhầm thứ khác rồi vẫn cho ra một con số trông có vẻ chắc chắn. Đã
cắn đúng lỗi này hai lần trong một phiên, nên đây là luật.

1. **Check-in có mất event không.** Không so hai tổng `count(*)`. Phải đối soát
   từng cặp `(clinic_id, appointment_id)`: lịch từng đạt `CHECKED_IN` có dòng
   `appointment.checked_in` tương ứng không, và ngược lại. Phải xét hoàn tác
   (`appointment.checkin_undone`, hành động `undo_checkin`) và thứ tự thời gian
   — một lịch có thể check-in, hoàn tác, rồi check-in lại, nên số event lớn hơn
   số lịch vẫn là đúng. Mẫu số "số lịch đã tạo" không bao giờ dùng được.
2. **CSKH đang chạm chặng nào.** `tuong_tac_cskh` tách theo `loai`, để biết tỷ
   trọng giữa trước buổi khám (`XAC_NHAN_LICH`, `NHAC_HEN`), trong buổi khám
   (`CHECK_IN`, `CHECK_OUT`, `THANH_TOAN`, `MUA_THUOC`) và sau khám (`TRA_KQ`).
3. **`slot_hold` có lấn cửa sổ nhật ký không.** Phải chạy lại **đúng câu truy
   vấn của màn hình** trong `audit_log_service.py` — nó UNION `v_audit_log` với
   `work_item_event` TRƯỚC khi sắp xếp và cắt. `LIMIT 200` trên một mình
   `v_audit_log` cho ra một tập khác, không kết luận được gì về màn hình.
4. **Nhánh `auto_checkin` đã từng chạy chưa.** Đếm trên `event_log` những dòng
   có `source = 'api:appointment-walkin-autocheckin'` hoặc `metadata->>'origin'`
   bằng chuỗi ấy (không có cột tên `origin`), lọc theo `clinic_id` và một khoảng
   thời gian rõ ràng. KHÔNG suy từ "hôm nay bảng lịch hẹn có 0 khách vãng lai":
   ảnh chụp một thời điểm của bảng trạng thái không nói gì về lịch sử thực thi.
5. **Relay thật sự gửi được bao nhiêu.** `processed` trong `relay_poll_complete`
   cộng cả nhánh không-có-template. Muốn biết số tin thật sự ra khỏi hệ thì đếm
   log `relay_no_template` và trừ ra, hoặc đọc lịch sử nhóm Telegram.
6. **Độ trễ ghi nhận thật.** Chưa đo được và sẽ chưa đo được cho tới khi có
   đường ghi truyền `occurred_at` thật của sự việc thay vì `now()`.
