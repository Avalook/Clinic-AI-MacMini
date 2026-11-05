---
paths:
  - "src/clinicai/**"
  - "src/dashboard/**"
  - "src/tests/**"
  - "supabase/migrations/**"
---

# Thiết kế code — tám luật chống "logic sau chồng logic trước" (05/11/2026)

Rút từ kiểm toán 04–05/11: lỗi lặp lại ở repo này hiếm khi do một dòng sai. Nó đến từ
**đường mới mọc cạnh đường cũ mà đường cũ không chết**, file phình mãi, và cùng một câu
hỏi được trả lời ở nhiều nơi. Các luật dưới đây bổ sung `backend.md`, `giao-dien.md`,
`migration.md` — không thay chữ nào của chúng.

## 1. Một câu hỏi — một hàm
"Còn nợ bao nhiêu?", "việc này đang ở trạng thái gì?", "ai được bấm?" — mỗi câu chỉ có
**một** hàm trả lời. Trước khi viết hàm tính, tìm hàm đang trả lời câu đó (Serena
`find_symbol`, `docs/BAN-DO-CODE.md`, agent `tim-cho-sua`). Có rồi ⇒ gọi nó. Nó sai ⇒ sửa
nó. **Không viết bản thứ hai "cho màn này".**

## 2. Thêm đường mới thì phải giết đường cũ
Đổi cách làm một việc ⇒ trong **cùng PR** (hoặc PR kế tiếp, ghi rõ) phải: đường cũ gọi
sang đường mới, hoặc bị xoá, hoặc bị khoá bằng một test đếm "con số chỉ được giảm"
(mẫu: số route Next chạm DB 42 → 1). Thân PR có dòng **"Đường cũ: … → xử lý: …"**.
Không được để hai đường cùng sống mà không có test đếm.

## 3. Trạng thái tính ra, không lưu
Trạng thái suy được từ sự việc (đã thu? đã lấy mẫu? có tệp? đã gửi?) thì **tính bằng một
hàm thuần**, không lưu thành cột số/chữ. Lưu **sự việc** (ai, lúc nào, bao nhiêu, vì sao),
không lưu kết luận. Chỉ lưu kết luận khi có lý do đo được (tốc độ) và có test so với hàm.

## 4. Không sửa quá khứ — ghi bù
Tiền, mẫu, tệp, thao tác của người: không `UPDATE` đè, không `DELETE`. Sai ⇒ đóng bản cũ
(`*_luc`, `*_boi`, `ly_do_*`) rồi ghi bản mới; trả lại ⇒ dòng đảo. Hoàn tác = **lệnh bù
của đúng bước đó**, có lý do, có sự kiện — không chụp rồi khôi phục bản ghi.

## 5. Kích thước có trần
- File mới ≤ **400 dòng**, hàm ≤ **60 dòng**. Vượt ⇒ tách theo nghiệp vụ trước khi thêm.
- File đã quá trần (vd `luot_kham_service.py`, `doi_tac_service.py`, `quay_thu_service.py`):
  **không thêm hàm mới vào đó**. Viết ở module mới, file cũ chỉ thêm một dòng gọi.
  Số dòng của chúng **chỉ được giảm** (`scripts/tran-kich-thuoc.json` khi có).
- PR > ~400 dòng (không tính test, migration, tệp sinh) ⇒ tách.

## 6. SQL có nhà
SQL nằm trong hàm dịch vụ hoặc module truy vấn của đúng nghiệp vụ, **không** trong router,
**không** trong route Next (`src/dashboard/app/api/**` chỉ chuyển tiếp). Bảng nào thuộc
module nào khai ở `src/clinicai/modules.py`; ghi vào bảng của module khác ⇒ gọi hàm của
module đó.

## 7. Hợp đồng API rõ
Cửa mới có `response_model` (Pydantic) và trả **cờ đã tính sẵn** cho màn (`co_the_lay_mau`,
`ly_do_khong`), để TSX chỉ hiển thị — không tự suy luật, không `if` theo vai. Lỗi nghiệp
vụ trả 409/422 kèm câu tiếng Việt người đọc hiểu, không 500.

## 8. Dữ liệu sạch để AI đọc được
- Lưu **id**, không lưu tên làm khoá (tên đổi được; chụp tên chỉ để in).
- Mọi bảng có `clinic_id`; mọi đọc lọc theo nó.
- Tiền là `numeric(12,0)` VND; thời điểm là `timestamptz`, đổi sang giờ Việt Nam **chỉ** ở
  chỗ nhóm theo ngày (`AT TIME ZONE 'Asia/Ho_Chi_Minh'`).
- Mã trạng thái là chuỗi cố định có CHECK, có một bảng/enum mô tả nghĩa; không số ma thuật.
- Sự kiện đặt tên theo việc đã xảy ra, theo kiểu tên đang có trong catalogue (`lab.sample_collected`), payload có id, không có dữ liệu sức khoẻ dư.

## Khi một luật ở đây cản việc
Dừng, ghi một dòng "luật N cản vì …, đề xuất …" trong báo cáo cho Tuyền. **Không lách im.**
Không sửa test/ratchet để nó xanh.
