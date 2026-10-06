# ADR-0016 — Phòng khám mới: tạo từ bộ mẫu trong git, đối tác tự nhập bằng Excel có xem trước và hoàn tác

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-05 |
| **Deciders** | Tuyền ("sau này còn có đối tác phòng khám mới dùng bên mình thì phải có sẵn cho họ nhập") |
| **Liên quan** | ADR-0009 (tenant thật), ADR-0015 (cơ sở), `docs/kien-truc-nhieu-phong-kham.md` (luật là dữ liệu), `docs/design/da-co-so-va-phong-kham-doi-tac.md` mục 8 |

## Context

ADR-0009 đã làm phần **cô lập**: khoảng 130 bảng có `clinic_id`, RLS, audit trần 0, kiểm lúc chạy. Nhưng chưa có đường **tạo** một phòng khám:

- Dòng `clinic` duy nhất được seed trong migration.
- Phòng khám mới cần khoảng 25 bảng cấu hình mới chạy được: bước, tuyến, phiếu khám, bộ quyền, kỹ năng, mẫu kết quả, ngưỡng điều phối, ca, giờ mở cửa…
- Danh mục, nhân sự, giá của Dr4Women đều đã nạp bằng script viết riêng (`nhan-su-kim-nguu.py`, `kim-nguu-3-tang-2709.py`).

Một đối tác không thể nhờ lập trình viên viết script cho mình.

## Decision

1. **Bộ mẫu sản phẩm là tệp dữ liệu có phiên bản trong git:** `supabase/mau-phong-kham/`. Hàm `tao_phong_kham()` làm các bước sau trong **một transaction**:
   - tạo tenant;
   - chép bộ mẫu vào tenant mới;
   - tạo cơ sở đầu tiên;
   - tạo tài khoản quản lý đầu tiên.

   Khi bộ mẫu có bản mới thì áp theo kiểu chỉ-thêm, không ghi đè thứ đối tác đã sửa.
2. **Chỉ người vận hành nền tảng tạo tenant.** Giai đoạn 1 làm bằng lệnh `scripts/tao-phong-kham.py`.
3. **Đối tác tự nhập** qua màn "Thiết lập phòng khám". Mọi bước dùng một khuôn nhập Excel chung:
   - tải lên;
   - **xem trước từng dòng, có lỗi đánh dấu**;
   - xác nhận;
   - ghi trong một transaction, **idempotent theo mã**;
   - **hoàn tác được cả lô**.
4. Dr4Women dùng chính khuôn này cho danh mục và nhân sự Hào Nam. Không viết thêm script nạp lẻ.

## Considered Options

| Phương án | Ưu | Nhược |
|---|---|---|
| **A. Bộ mẫu trong git (chọn)** | Có phiên bản và review. Giống hệt nhau ở dev, staging, prod. Test được ("tạo tenant mới → chạy được một ngày khám"). | Muốn sửa mẫu phải qua PR |
| B. Một "tenant mẫu" ẩn trong DB, chép từ đó | Người không code sửa được trên màn | Trôi lệch giữa các môi trường. Không có lịch sử. Sửa nhầm thì mọi đối tác về sau đều nhận lỗi. |
| C. Chép từ Dr4Women | Không phải soạn mẫu | Rò giá, tên bác sĩ, luật riêng của Dr4Women sang pháp nhân khác. Loại. |
| D. Mỗi đối tác một database / VPS | Cô lập tuyệt đối | Đã loại ở ADR-0009C: chi phí và migration nhân N. Ở 10–20 lượt gọi/giây cho 10 đối tác thì không cần. |

## Consequences

**Tích cực:**
- Mở một đối tác = một lệnh, cộng với việc quản lý của họ tự đi qua wizard.
- Khuôn nhập Excel giúp chính Dr4Women: sửa danh mục, nhập Excel 01.10.26 không cần script.
- Bài kiểm cô lập tenant chạy trên tenant được tạo bằng đường thật, thay vì một dòng INSERT tay.

**Tiêu cực / đánh đổi:**
- Phải tách được phần "hằng số sản phẩm" khỏi phần "dữ liệu riêng của Dr4Women" trong 25 bảng cấu hình. Việc này cần soát từng bảng.
- Màn quản trị nền tảng (tạo tenant bằng giao diện) và thương hiệu / tên miền riêng cho từng đối tác chưa làm. Chờ Quang chốt tên miền sản phẩm.
- Xuất trả dữ liệu khi đối tác rời đi (Nghị định 13/2023) chưa có. Làm khi có đối tác thật.
