# Round 11 — Vòng đời hồ sơ khám, điều trị và kết quả

**Snapshot:** exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7` (`/tmp/clinicai-audit-main-956ba4f2`). Phạm vi này đọc các service hồ sơ khám/điều trị/sinh hiệu/xét nghiệm/tệp kết quả đang ở trạng thái `scanned` trong `MAIN-PHAM-VI.json` hoặc `clinical.coverage.json`, cùng các test đối ứng; riêng `cskh.py` trước đó chỉ được trace một phần. Hash từng file nằm trong [coverage JSON](round11_clinical_records.coverage.json).

## Phát hiện mới

### CAND-CLIN-REC-001 — Quyền tải tệp kết quả mở được toàn bộ hồ sơ khám (**HIGH, confirmed static**)

`GET /cskh/ho-so-kham/{appointment_id}` dùng `_KET_QUA_DOC_GUARD`, alias của `_TEP_TAI_LEN_GUARD`. Guard chấp nhận **bất kỳ một** quyền trong danh sách, bao gồm `reception.checkin.perform` và `crm.manage`; `moi_phong=True` còn cho qua khi capability được cấp ở một phòng bất kỳ. Sau đó `HoSoKhamService.doc` chỉ lọc theo `clinic_id` và trả cả dữ liệu nhận diện/liên hệ, biểu mẫu lâm sàng (`form_data`), kết quả chỉ định, đơn thuốc và giá trị xét nghiệm. Không có guard đọc bệnh án riêng, location check hoặc patient-assignment check trên đường gọi này.

Trigger cụ thể là nhân viên có một capability trên gọi trực tiếp bằng mã lịch hợp lệ. Đây cũng là luồng đang được giao diện CSKH dùng: từ lịch sử khám mở hồ sơ hoặc lấy `visit_id` để in. Nội bộ `luot_kham_chung.py` lại mô tả lễ tân/trưởng ca chỉ cần làm việc với trạng thái và không cần đọc chữ bác sĩ viết; `CLINICAL_READ_ROLES` không gồm các vai đó. Đây là đối chiếu policy trong code, cần chủ sản phẩm xác nhận ma trận trường CSKH được phép xem.

**Tác động:** nội dung lâm sàng và PII của lượt trong cùng clinic có thể được đọc bởi capability dành cho tiếp đón/CRM; do query chỉ lọc clinic, cùng clinic khác cơ sở cũng có thể nằm trong phạm vi nếu có appointment UUID. Không có chứng cứ tĩnh về vượt clinic, đọc byte của file đính kèm, grants đang cấp trên production hay việc đã xảy ra.

**Hướng sửa:** tách quyền đọc chart khỏi quyền tải/đọc tệp; kiểm tra clinic, cơ sở và assignment theo policy. Nếu CSKH cần in hồ sơ cho bệnh nhân, cung cấp projection riêng với trường đã được duyệt, không dùng quyền xem tệp để nhận toàn bộ `form_data`, ghi chú/kết quả nội bộ và đơn thuốc.

**Kiểm thử chấp nhận:** gọi route FastAPI trực tiếp bằng actor chỉ có `reception.checkin.perform` (kể cả quyền phòng) hoặc `crm.manage`; không được trả nội dung lâm sàng. Actor có quyền đọc chart, assignment và scope hợp lệ đọc được. Test khác cơ sở/cùng clinic theo policy; nếu còn PDF cho CSKH, test projection tối thiểu. Test hiện có gọi service trực tiếp nên không chứng minh route guard.

## Bằng chứng và đối chiếu

- `cskh.py:673-679, 774-798`: danh sách quyền của upload guard, alias `_KET_QUA_DOC_GUARD`, route chart và lời gọi service.
- `cua_quyen.py:27-49`: semantics OR và `moi_phong=True`.
- `ho_so_kham_service.py:40-72, 105-171, 193-223`: truy vấn theo clinic và trường lâm sàng được serialize.
- `luot_kham_chung.py:145-153, 177-178`: policy nội bộ cho nội dung khám; dùng làm đối chiếu, không phải enforcement của route này.
- Caller CSKH: `ThanhLuotKham.tsx:68-92`, `HoSoKham.tsx:547-573`; BFF chỉ proxy tại `route.ts:1-16`.
- `test_ho_so_kham.py:62-85` kiểm clinic scope/shape nhưng không kiểm HTTP authorization; `test_doc_luot_v5_sinh_hieu_buoi_db.py:76-87` gọi service trực tiếp bằng identity lễ tân. Test guard tệp từ chối PARTNER (`test_full_chi_dinh_slice_ab_db.py:1174-1181`) không kiểm chart route cho reception/CRM.

Đã dedup với `SEC-011` (các đường đọc y khoa/assignment) và `SEC-019` (PostgREST trực tiếp hai bảng lịch sử/ghi chú): khác đường gọi và khác nhóm capability. Không trùng `LAB-001`, `CLIN-034`, `API-001..003`, `INF-018`. Route lab cũ `POST /lab/orders` và `PATCH /lab/results/{id}` trả 410 (`lab.py:105-132`), nên không coi `lab_order_service` là luồng HTTP đang hoạt động.

Chỉ đọc static exact-main; không chạy test/runtime, không truy cập DB/VPS/secrets/PHI và không sửa source/migration. Findings JSON đầy đủ, line ranges, SHA-256 và giới hạn bằng chứng nằm trong cùng thư mục.
