# OC-01 — Ổ cắm module (chuẩn chân cắm của LEGO)

| | |
|---|---|
| **Mã** | OC-01 |
| **Trạng thái** | ĐÃ CODE 23/09 — bản khai + 5 bài kiểm CI |

## 0. Vì sao

"Mọi thứ là LEGO" chỉ là khẩu hiệu nếu không ai kiểm được. Một viên LEGO cắm được
vì nó có **chuẩn chân cắm**. Ở đây chuẩn ấy là: mỗi module khai đúng những gì nó
nhận vào và nhả ra, và **CI so bản khai với code thật**.

Không có bài kiểm ấy thì sau ba tháng bản khai thành tờ giấy đẹp treo tường, còn
code đi đường khác — chuyện đã xảy ra với bảng nhãn sự kiện cũ.

## 1. Mỗi module khai gì

```
NHẬN VÀO   lệnh · sự kiện nó nghe
NHẢ RA     sự kiện nó phát · việc không được rơi · màn/bảng đọc nó dựng
GIỮ RIÊNG  bảng state của chính nó
QUYỀN      capability mà lệnh của nó đòi
```

## 2. Năm bài kiểm CI

| Kiểm | Bắt được chuyện gì |
|---|---|
| Mỗi sự kiện có **đúng một** module nhận là của mình | sự kiện mồ côi — sau này ai sửa nó? |
| `source_module` trong sự kiện khớp bản khai | bản khai và code nói hai chuyện khác nhau |
| Mỗi bên nghe thuộc một module, và module khai nghe đúng sự kiện | ai đó cắm thêm bên nghe mà không khai |
| Mỗi quyền thuộc một module | quyền mồ côi = quyền không ai gác |
| **Không hai module cùng giữ một bảng** | hai LEGO dính keo vào nhau |

## 3. Luật cắm (chat #128)

- Module A **không** UPDATE bảng state của module B.
- Muốn B đổi thì gửi **lệnh** của B, hoặc phát **sự kiện** để B tự nghe.
- Thêm bên nghe mới = thêm một dòng bản khai, **không sửa module phát**.
- Thêm tính năng mà phải sửa xuyên nhiều module không liên quan
  = **thiết kế LEGO đang thủng**, dừng lại xem lại đường cắm.

## 4. Hiện có 12 module

`service_order` · `service_selection` · `service_routing` · `execution` ·
`result` · `catalogue` · `permission` · `journey` (chỉ nghe) ·
`trach_nhiem` (chỉ nghe) · `reception` · `vitals` · `payment`

Hai module **chỉ nghe** là bằng chứng ổ cắm chạy thật: cả hai được thêm vào mà
không sửa một dòng nào của module phát sự kiện.

## 5. Còn thiếu

Bản khai mới phủ các module đã chuyển sang mô hình mới. Các service cũ
(booking, pharmacy, config…) chưa khai — chúng chưa phát sự kiện nào trong danh
mục nên CI chưa bắt được, và đó là **nợ có chủ ý**, gỡ dần theo từng lát.

## Phụ lục

| Thứ | Ở đâu |
|---|---|
| Bản khai | `src/clinicai/modules.py` |
| Bài kiểm | `src/tests/unit/test_o_cam_module.py` |
