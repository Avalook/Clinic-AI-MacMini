# BM-01 — Form Template Engine (một cỗ máy, mọi biểu mẫu)

| | |
|---|---|
| **Mã** | BM-01 |
| **Module chủ** | `result` + `catalogue` |
| **Trạng thái** | ĐÃ CODE 23/09 — backend + 10 test + **màn điền** (`_lam-viec/PhieuKetQua.tsx`); **khung để trống, chờ phòng khám đưa ruột**; chưa bấm thật trên trình duyệt |
| **Nguồn** | chat #174–#178 · phiếu chỉ định giấy Dr4Women 17/08/2026 |

## 0. Vì sao một cỗ máy

18 mẫu kết quả, 7 biểu mẫu khám, các phiếu thủ thuật — **na ná nhau**: vài mục,
mỗi mục vài ô, có câu mẫu điền sẵn, sửa thoải mái, xong thì xác nhận.

Viết 19 cái form bằng 19 đoạn code là 19 chỗ phải sửa mỗi lần bác sĩ đổi một câu.
Nên: **một engine**, mỗi biểu mẫu là **dữ liệu** (`form_definition.khung`).

Ruột từng mẫu chưa có — phòng khám đưa sau. Lúc ấy chỉ thêm ô vào khung, **không
sửa dòng code nào**. Hiện mỗi mẫu có sẵn ba mục mà mẫu nào cũng có: Mô tả · Kết
luận · Đề nghị.

## 1. Trigger
Phòng dịch vụ / bàn khám, sau khi làm xong dịch vụ · vai: ai có `result.form.fill`
(mặc định bác sĩ, BS siêu âm, điều dưỡng SA, thư ký y khoa).

## 2. Command
```text
OpenForm      POST /api/v1/phieu/mo              {service_order_id, form_id}
SaveDraft     POST /api/v1/phieu/{id}/luu        {du_lieu, expected_revision}
CompleteForm  POST /api/v1/phieu/{id}/hoan-tat   {expected_revision, thuc_hien_boi}
PublishForm   POST /api/v1/bieu-mau/{form_id}/xuat-ban  {khung}
```

## 3. Events

| Sự kiện | Khi nào | Công khai |
|---|---|---|
| `result_form.completed` | bấm [Hoàn tất] | có |

**Tự lưu KHÔNG phát sự kiện** — nháp chưa phải sự thật (#150).
Payload chỉ mang mã phiếu, người gõ, người thực hiện và **số ô còn trống** —
không một chữ lâm sàng nào (sổ sự kiện không xoá được, nên không chứa chữ bệnh án).

## 4. Views
Dòng thời gian lượt khám đã nghe sự kiện này. Sau này CSKH và màn "kết quả chờ
duyệt" nghe thêm mà không phải sửa module biểu mẫu.

## 5. Constraint — ép ở đâu

| Luật | Ép ở đâu |
|---|---|
| Mỗi biểu mẫu chỉ có MỘT bản đang dùng | **Postgres** (chỉ mục duy nhất một phần) |
| Mỗi chỉ định một phiếu | **Postgres** (chỉ mục duy nhất) |
| Phiếu ghim đúng phiên bản mẫu của nó | **Postgres** (khoá ngoại 3 cột) |
| READY thì phải biết ai hoàn tất, lúc nào | **Postgres** (CHECK) |
| Hai người cùng gõ không ghi đè nhau | **Lệnh** (`expected_revision`) |
| Nguồn giá trị lạ | **Lệnh** (chặn ngay lúc lưu) |
| Điền thiếu **KHÔNG** chặn | cố ý: chỉ đếm "còn N mục chưa điền" |

## 6. Bốn luật đã chốt, đã code

1. **Hoàn tất = xác nhận TOÀN BỘ** nội dung hiện tại, kể cả câu mẫu không ai sửa
   (#177). Code đổi nguồn mọi ô từ `TEMPLATE_DEFAULT` sang `USER` đúng lúc bấm.
2. **Sửa mẫu v1 → v2 không đổi hồ sơ cũ.** Có test.
3. **Người gõ ≠ người thực hiện** (`nhap_boi` ≠ `thuc_hien_boi`). Điều dưỡng nhập
   thay bác sĩ vẫn ghi đúng ai làm.
4. **Mỗi giá trị nhớ nó từ đâu ra**: câu mẫu · người gõ · hồ sơ khách · dịch vụ ·
   máy tính ra · lấy từ lần trước · AI gợi ý. Không có cái này thì sau không phân
   biệt được "bác sĩ viết thế" với "máy điền sẵn mà không ai đọc".

## 7. Hotspot — chưa chốt

1. **Ruột từng mẫu** — phòng khám đưa sau (Tuyền: "nào có đưa bạn rồi bạn làm sau").
2. **Ai được xuất bản bản mẫu mới?** Hiện quản lý. Trưởng khoa? Bác sĩ trưởng?
3. ~~Hoàn tất phiếu có tự đóng dịch vụ không?~~ **ĐÃ NỐI 23/09.** Phiếu xong mà
   dịch vụ còn đang làm dở thì đóng hộ, nhưng bằng **lệnh** `CompleteService`
   của module Thực hiện (khai ở `modules.py` mục `goi_dong_bo`) — không thò tay
   vào bảng của nó, nên vẫn kiểm quyền, vẫn khoá lượt, vẫn phát sự kiện.
   Không đóng được (không đủ quyền / dịch vụ không đang làm) thì phiếu **vẫn
   hoàn tất**, và kết quả trả về nói rõ vì sao để màn hình báo lại.
4. `[Lấy từ lần trước]` và `[Chèn vào kết quả]`: đã có chỗ trong mô hình nguồn,
   chưa có nút.

## 8. Given / When / Then

```text
G1  18 mẫu đều có khung đang dùng
G2  Khung rỗng có đủ ba mục chung, mọi ô đánh dấu "chờ phòng khám đưa"
G3  Mở phiếu hai lần không tạo hai phiếu
G4  Tự lưu KHÔNG phát sự kiện nào
G5  Hai người cùng gõ → người sau bị chặn, không ghi đè im lặng
G6  Hoàn tất: câu mẫu thành "đã xác nhận", ghi đúng người gõ và người thực hiện,
    phát result_form.completed, payload KHÔNG có chữ lâm sàng
G7  Còn ô trống vẫn hoàn tất được, chỉ nhắc "còn 1 mục"
G8  Lễ tân không điền được
G9  Xuất bản v2 không đổi phiếu đã điền ở v1; phiếu mới lấy v2
G10 Bác sĩ không xuất bản được mẫu
G11 Nguồn giá trị lạ bị chặn ngay lúc lưu
```

## Phụ lục

| Thứ | Ở đâu |
|---|---|
| Hai bảng + khung rỗng 18 mẫu + 3 quyền mới | `supabase/migrations/20260923000005_form_engine.sql` |
| Engine | `src/clinicai/services/form_engine_service.py` |
| Endpoint | `src/clinicai/api/v1/routers/phieu.py` |
| Sự kiện | `src/clinicai/events/catalogue.py` (`result_form.completed`) |
| Test | `src/tests/services/test_form_engine_db.py` |

**Chưa làm:** màn hình (Quản lý biểu mẫu + màn điền phiếu), đường proxy dashboard,
in phiếu. Biểu mẫu khám cũ (`ServiceFormEngine`, PK/SK/NT/NK/HMVS) **vẫn chạy như
cũ** — chuyển sang engine này là một lát riêng, không đập đi làm lại.

## Màn hình (23/09)

`_lam-viec/PhieuKetQua.tsx` — MỘT màn cho mọi biểu mẫu. Máy chủ trả `khung`
(mục → ô, mỗi ô có `kieu`), màn vẽ đúng khung ấy. Phòng khám đưa ruột 18 mẫu
thì chỉ thêm ô vào dữ liệu; tệp TSX không phải sửa một dòng.

Ba điều màn phải nói ra, vì chúng là luật:

- **"Đã lưu 10:32 · nháp, chưa phải kết quả"** — tự lưu sau 1,5 giây im, và
  nháp không phát sự kiện nào.
- **[Hoàn tất phiếu]** — "xác nhận toàn bộ nội dung đang thấy, kể cả câu điền
  sẵn". Câu này in ngay cạnh nút.
- **"Còn N mục chưa điền — vẫn hoàn tất được"** — nhắc, không chặn.

Bấm Hoàn tất thì màn **lưu lần cuối trước khi chốt**: gõ xong bấm ngay trong
khoảng lặng tự lưu, nếu không lưu trước thì phiếu chốt thiếu đúng câu vừa viết.

Hoàn tất lúc dịch vụ còn đang làm dở: máy chủ đóng hộ dịch vụ và trả về đã đóng
hay chưa. Màn in ra nguyên câu ấy — không để người làm tưởng xong mà hàng chờ
vẫn còn tên khách.

Ô "Người thực hiện" tách riêng: điều dưỡng nhập thay bác sĩ là chuyện thường
ngày, nên người gõ không được ngầm thành người chịu trách nhiệm.

Dịch vụ chưa gắn mẫu thì màn nói thẳng "chưa gắn mẫu kết quả nào", không im
lặng biến mất.

## Một nút, ba việc (23/09 chiều)

Bấm `[Hoàn tất]` một lần, hệ thống ghi:

1. phiếu chuyển `READY` — người bấm xác nhận **toàn bộ** nội dung đang thấy;
2. `service.completed` — dịch vụ đóng, khách rời hàng chờ;
3. `result.ready` — **chỉ khi** dịch vụ có kết quả ngay tại phòng.

Điểm 3 là chỗ dễ làm sai nhất. `service.completed` ≠ `result.ready`: lấy mẫu
xét nghiệm gửi ra ngoài thì dịch vụ xong hôm nay, kết quả hai ngày sau mới về.
Báo "đã có kết quả" sớm một ngày là một lần bác sĩ mở ra và thấy trống.

Cấu hình ở `dich_vu_mau_ket_qua.result_mode`:

| | Nghĩa | Phát `result.ready`? |
|---|---|---|
| `INLINE` | kết quả có ngay tại phòng (siêu âm, thủ thuật) | có |
| `LATER` | làm xong nhưng kết quả về sau (mẫu gửi đi) | không |
| `NONE` | dịch vụ không sinh kết quả để đọc | không |

Chưa cấu hình gì thì coi như `NONE`. Im lặng nghĩa là "không có kết quả", chứ
không phải "cứ báo có cho chắc".

## Sửa lại sau khi đã hoàn tất

Tuyền 23/09: *"vẫn cho sửa được vì audit log được mà"*. Cùng luật đã áp cho sinh
hiệu (`VitalsCorrected`, ChatGPT tin 144): hệ thống không khoá người dùng, nó
**ghi lại**.

    [Sửa lại]  →  gõ (tự lưu)  →  [Xác nhận sửa]  →  result.corrected

`dang_sua` là một cờ riêng, **không** đưa phiếu về nháp: kết quả cũ vẫn là kết
quả chính thức suốt lúc sửa. Không có khoảnh khắc nào bác sĩ mở ra mà thấy
trống. Phiếu READY chưa bấm [Sửa lại] thì vẫn chặn gõ đè — chặn tới khi người
dùng nói rõ "tôi muốn sửa", không chặn vĩnh viễn.

Lần sửa **không** sinh thêm một `result_form.completed` thứ hai: nó là bản mới
của cùng một kết quả, không phải một kết quả khác.
