# TN-01 — Trách nhiệm không được rơi

| | |
|---|---|
| **Mã** | TN-01 |
| **Module chủ** | `trach_nhiem` (module CHỈ NGHE) |
| **Trạng thái** | ĐÃ CODE 23/09 — backend + 5 test; màn "việc của tôi" chưa nối |

## 0. Khách là trên hết — chỗ câu ấy thành code

Khách trả tiền siêu âm, máy hỏng, dịch vụ không làm. Lúc đó **tiền của khách
đang nằm ở phòng khám**. Hôm nay hệ thống ghi một dòng sự kiện rồi thôi:
`payment.reconciliation_needed` và ba mã tương tự nằm trong `event_log` — không
chủ, không hạn, không màn nào hiện. Người nhớ ra là khách.

Từ nay mỗi chuyện như vậy **mở một việc có người chịu trách nhiệm**.

## 1. Đây là bài chứng minh LEGO

Module Thực hiện dịch vụ **không biết module này tồn tại**. Nó chỉ phát sự kiện.

```
execution ──service.not_performed────▶ trach_nhiem ─▶ OPS-FINANCIAL-RESOLUTION
          ──service.interrupted─────▶             ─▶ OPS-SERVICE-INTERRUPTED
routing   ──service.routing_invalidated▶             ─▶ OPS-ROUTING-REASSIGN
```

Xoá module này đi thì Thực hiện chạy y nguyên. Mai kia thêm "quá 20 phút chưa ai
xử lý thì nhắc trưởng ca", hay "CSKH gọi xin lỗi khách" — thêm một bên nghe nữa,
**vẫn không đụng** Thực hiện. Thêm một dòng trong `VIEC_THEO_SU_KIEN` là thêm
một trách nhiệm được canh.

## 2. Hai loại việc

| Việc | Mở khi | Ai nhận (dự phòng) |
|---|---|---|
| `OPS-ROUTING-REASSIGN` | xếp phòng bị huỷ, cần xếp lại | Trưởng ca · Quản lý |
| `OPS-FINANCIAL-RESOLUTION` | không làm dịch vụ **mà đã thu tiền** | Quản lý · Thu ngân — **không** trưởng ca |
| `OPS-SERVICE-INTERRUPTED` | dịch vụ bị dừng giữa chừng | Trưởng ca · Bác sĩ · Quản lý |

`actor_roles` ở đây là **người dự phòng**, không phải hàng rào quyền. Quyền vẫn là
capability.

## 3. Bốn luật đã code

1. **Không mở việc khi không cần.** Không thu tiền mà không làm thì không có gì để
   đối soát. Mở việc cho mọi trường hợp là cách nhanh nhất để người trực học cách
   lờ đi những việc hệ thống đẩy ra.
2. **Một chuyện chỉ một việc.** Sự kiện có thể tới hai lần (giao tin "ít nhất một
   lần"). Chỉ mục duy nhất trên `(clinic, service_order, node_code)` khi việc còn
   mở lo chuyện ấy — Postgres, không phải trí nhớ người viết code.
3. **Chạy lại lịch sử không dựng lại việc cũ.** Sự kiện có dấu phát lại thì bỏ qua:
   người ta đã xử lý xong từ lâu.
4. **Không tự quyết thay người.** Việc mở ra chỉ nói "có chuyện cần xử lý". Hoàn
   tiền là quyết định của người, đi đường tài chính riêng.

## 4. Hỏng thì phải thấy

Loại việc chưa được khai ở phòng khám → bên nhận **dừng có tiếng**, dòng giao vào
hộp chết, hiện ở `GET /api/v1/ops/su-kien`. Im lặng bỏ qua mới là mất trách nhiệm.

## 5. Hotspot

1. **Ai là chủ mặc định của việc đối soát?** Hiện để trống, ai trong nhóm dự phòng
   cũng nhận được. Có nên gán đích danh thu ngân của ca?
2. **Hạn xử lý** (`due_at`) chưa đặt — cần phòng khám chốt: 24 giờ? cuối ca?
3. Màn "việc của tôi" chưa hiện hai loại việc này.

## 6. Given / When / Then (5 test)

```text
G1  Không làm + ĐÃ thu tiền  → mở việc Đối soát tiền
G2  Không làm + CHƯA thu tiền → KHÔNG mở việc nào
G3  Dừng giữa chừng → mở việc Quyết định làm lại
G4  Sự kiện giao lại lần hai → vẫn chỉ MỘT việc
G5  Phát lại lịch sử → KHÔNG mở lại việc đã xử lý xong
```

## Phụ lục

| Thứ | Ở đâu |
|---|---|
| Bên nghe | `src/clinicai/events/consumers/trach_nhiem.py` |
| Cột `work_item.service_order_id` + 2 loại việc | `supabase/migrations/20260923000007_trach_nhiem_khong_roi.sql` |
| Bản khai module | `src/clinicai/modules.py` (`trach_nhiem`) |
| Test | `src/tests/services/test_trach_nhiem_db.py` |

## Tên node lấy từ thiết kế, không tự đặt (sửa 23/09 chiều)

Bản đầu dùng `OPS-DOI-SOAT-TIEN` và `OPS-QUYET-LAM-LAI` — hai cái tên Claude tự
nghĩ ra. Thiết kế đã chốt (ChatGPT tin 112) gọi chúng là `OPS-FINANCIAL-RESOLUTION`
và `OPS-SERVICE-INTERRUPTED`, và có thêm node đầu `OPS-ROUTING-REASSIGN`.

Đặt tên khác thiết kế không phải chuyện thẩm mỹ: hai bên bàn về cùng một thứ
bằng hai từ, và tới lúc nối thì không khớp.

Cùng lần sửa này, **trưởng ca rời khỏi việc tiền**. Tin 112 nói rõ việc tài
chính không tự giao điều dưỡng hay trưởng ca: họ điều phối phòng và người, không
đối soát sổ tiền của khách. Giao mặc định cho họ là đẩy trách nhiệm sang người
không có công cụ để làm.
