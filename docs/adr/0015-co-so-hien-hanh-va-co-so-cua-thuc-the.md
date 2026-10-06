# ADR-0015 — Cơ sở: phiên chọn, thực thể quyết định; cơ sở không phải ranh giới bảo mật

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-05 |
| **Deciders** | Tuyền (chốt nghiệp vụ 05/10: kho riêng, giá chung, khách chung, báo cáo tách + tổng) |
| **Liên quan** | ADR-0009 (tenant), `docs/design/da-co-so-va-phong-kham-doi-tac.md`, memory "cơ sở lạc từ tài khoản local" (24/09) |

## Context

Dr4Women mở cơ sở thứ hai, Hào Nam. Nhân sự dùng chung: cùng một người có thể làm ở Kim Ngưu hôm nay và ở Hào Nam ngày mai.

Hiện tại cơ sở của mọi request lấy từ `staff.primary_location_id`. Cột này cố định, mỗi người chỉ một giá trị. Ngày 24/09 đã có sự cố từ đúng chỗ này: tài khoản mang cơ sở lạc, lịch lễ tân đặt rơi vào cơ sở không có phòng, khách trả tiền xong mà không vào được phòng nào. Khi có hai cơ sở dùng chung người, chuyện đó sẽ xảy ra hằng ngày.

Ngoài ra, một số chỗ trong code lấy "phần tử đầu tiên của cả phòng khám" (ví dụ quầy `LUOTKHAM-01` trong `hang_cho.py`). Worker nền thì không có phiên người dùng nào để hỏi cơ sở.

## Decision

1. **Cơ sở của thực thể luôn thắng.** Thao tác lên lượt, lịch hẹn, lô thuốc hay phiếu kho thì dùng `location_id` của chính thực thể đó để chọn phòng, quầy, kho. Không dùng cơ sở của người bấm.
2. **Cơ sở hiện hành của phiên** do người dùng chọn lúc đăng nhập (gợi ý theo lịch trực hôm nay) và đổi được trên thanh trên. Nó chỉ dùng cho hai việc:
   - giá trị mặc định khi **tạo mới**;
   - **bộ lọc mặc định** của danh sách.
3. Phiên mang cơ sở qua header `X-Location-ID`. Header là **bộ chọn, không phải thẩm quyền**:
   - API chỉ nhận cơ sở nằm trong `staff_location` đang hoạt động của người đó; cơ sở ngoài danh sách → 403;
   - người được từ 2 cơ sở mà không gửi header → 428. **Không đoán.**
4. **Cơ sở là phân vùng vận hành, không phải ranh giới bảo mật.** Không viết RLS theo cơ sở. Ép cứng chỉ ở chỗ ghi sai gây hại vật lý:
   - khoá ngoại ghép `(location_id, clinic_id)`;
   - trigger "lô cấp phải cùng cơ sở với lượt";
   - tồn kho không âm, theo từng cơ sở.
5. **Bảng con của lượt không chép `location_id`.** Chúng suy cơ sở qua `visit.location_id`. Chỉ thứ có chỗ đứng vật lý mà không gắn lượt (kho, phiếu kho, bán lẻ không lượt) mới mang cột này.

## Considered Options

| Phương án | Ưu | Nhược |
|---|---|---|
| **A. Phiên chọn + thực thể quyết định (chọn)** | Đúng cả khi người làm hai nơi. Worker nền tự đúng. Gợi ý theo lịch trực nên gần như không phải nghĩ. | Thêm một màn chọn và một header. Phải rà các chỗ "lấy phần tử đầu". |
| B. Suy hoàn toàn từ lịch trực, không cho chọn | Không một cú bấm nào | Hỏng khi lịch chưa xếp (từ tuần thứ 3 trở đi lịch trống là chủ ý), khi đổi người phút chót, và với quản lý không có ca |
| C. Giữ `primary_location_id`, quản lý sửa khi người đổi nơi làm | Không sửa code | Chính là cơ chế gây sự cố 24/09. Sửa dữ liệu mỗi ngày, quên là ghi nhầm cơ sở mà không ai thấy. |
| D. Coi cơ sở như tenant: RLS theo cơ sở | Cô lập chặt | Sai nghiệp vụ: khách, lịch sử, giá, quyền đều chung. Mọi thao tác cần chéo cơ sở phải xuyên qua cơ chế bảo mật. |

## Consequences

**Tích cực:**
- Sự cố loại 24/09 bị chặn ở hai lớp: 428 thay vì đoán, và dải cảnh báo khi cơ sở đang chọn lệch lịch trực.
- Phòng khám đối tác có một hay mười cơ sở đều đi cùng một đường code.
- Thêm cơ sở thứ ba là việc **dữ liệu**, không phải code.

**Tiêu cực / đánh đổi:**
- Mọi màn vận hành phải nhận bộ lọc cơ sở. Phải rà hết các chỗ `LIMIT 1` / `locations[0]`.
- Người dùng một cơ sở không thấy gì khác, nhưng test phải phủ đủ 4 nhánh của bộ chọn.
- Không có RLS theo cơ sở, nên lớp kiểm bổ sung là **mô phỏng một ngày khám chạy song song hai cơ sở**, không phải audit tĩnh.
