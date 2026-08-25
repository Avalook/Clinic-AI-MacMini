# TẦM NHÌN — thang 5 cấp và ClinicAI đang đứng ở đâu

> Nguồn: Quang chốt trong chat nhóm **24/08/2026**. File này tồn tại vì chính
> luận điểm hôm đó: *"nếu không có bản đồ và tầm nhìn thì feedback không có giá
> trị"* — bản đồ phải nằm trong git, nơi mọi PR đối chiếu được, không nằm trong
> trí nhớ hay lịch sử chat.

## Thang 5 cấp của hệ điều hành phòng khám

| Cấp | Vận hành bằng gì | Điểm gãy |
|---|---|---|
| **lv1** | Con người + quan hệ + kinh nghiệm | Người giỏi nghỉ là hệ thống toang |
| **lv2** | Quy trình, chuẩn hoá, phân cấp — vẫn chạy bằng người | Quy trình nằm trong đầu người; thay người là hệ đổi |
| **lv3** | SaaS: logic cố định, database chuẩn, scale bằng máy | Chỉ *record* không *hiểu*; luật đóng cứng, khó nhận feedback |
| **lv4** | AI đọc **state-status** của hệ → dự đoán, khuyến nghị, điều phối | Khuyến nghị sai còn nguy hơn không khuyến nghị |
| **lv5** | Tự cải thiện qua feedback, học từ **case ngoại lệ**, tự nâng cấp hệ vận hành | Trần an toàn: y tế không cho phép máy tự sửa luật không ai duyệt |

**Đích là lv5. Đường đi bắt buộc: lv3 → lv4 → lv5.** Không nhảy cấp được, vì
lv4 chỉ đọc được state mà lv3 đã bắt **đầy đủ và đáng tin**; dữ liệu thiếu thì
mô hình giỏi đến đâu cũng cho khuyến nghị rác.

## Định vị 24/08/2026

- **Phòng khám Dr4Women: lv1–2** (đánh giá của Quang: quy trình phần lớn trong
  đầu nhân viên, mệnh lệnh truyền miệng — chưa đạt trọn lv2).
- **ClinicAI: đang xây nền lv3.** Nợ lv3 lớn nhất có số đo sẵn: **42/63 route
  dashboard còn chạm thẳng database** — luật còn nằm ngoài nơi kiểm soát được.
  Con số này chỉ được phép giảm (CLAUDE.md).
- **Mầm lv4 đã có thật trong code:** `event_log` + relay Telegram (điều phối sơ
  khai); `GET /api/v1/home/bang-dieu-khien` (đúng nghĩa API "state của phòng
  khám hôm nay"); mô hình sức chứa 3 tầng lưu **luật dưới dạng dữ liệu**.
- **Tài sản cho lv4/lv5 mà SaaS thường không có:** 31.179 dòng `cskh_action`
  lịch sử + 12 tính năng CSKH đã đặc tả trên Notion — ground truth để dạy máy
  "case này người giỏi đã xử lý thế nào".

## Luật rút ra từ tầm nhìn (áp NGAY, vì rẻ)

1. **Tính năng lv4 phải chỉ được tên bảng lv3 nó đọc, và bảng đó phải đã đáng
   tin.** Không nêu được thì là demo, không phải sản phẩm. Đây là chốt chặn
   "nhảy cấp" — dashboard "AI khuyến nghị" làm một tuần là có, và vô giá trị
   nếu dữ liệu dưới nó ghi sót.
2. **Mọi override/ngoại lệ phải có chỗ ghi lý do có cấu trúc.** Mẫu đã có:
   `ly_do_vuot_khung_gio` (CD), `ly_do_lam_lai` (migration 20260817000001).
   Case ngoại lệ là thức ăn của lv5; ngoại lệ không ghi lại là bài học vứt đi.
3. **Luật nghiệp vụ mới ưu tiên dạng đọc được** (bảng rule, như sức chứa 3
   tầng) thay vì hard-code, khi chi phí ngang nhau — hệ thống chỉ đề xuất sửa
   được luật mà nó đọc được.
4. **"Ai làm" là chiều dữ liệu bắt buộc của state** — PR #8 (cột actor cho
   `event_log`) vì thế tăng hạng ưu tiên, không còn là dọn dẹp tuỳ hứng.
5. **lv5 = AI đề xuất diff (kể cả diff của luật) kèm bằng chứng, người duyệt.**
   Khuôn mẫu là chính vòng PR-review đang chạy hằng ngày. Khuyến nghị của lv4
   cần verifier như code cần test — bộ eval vàng hôm nay đo flow đặt lịch, mai
   sau đo cả chất lượng khuyến nghị.

## Điều tầm nhìn KHÔNG đổi

Ưu tiên hiện tại giữ nguyên — và đó là dấu hiệu bản đồ vẽ đúng: đưa luật ra
khỏi `src/dashboard` là trả nợ lv3; CSKH là bãi thử lv4 tự nhiên. Chỉ đạo kèm
theo của Quang: **"Trước mắt cứ làm việc mình nghĩ là có ích đã"** — không lập
kế hoạch ngược từ lv5; tầm nhìn rõ dần từ bằng chứng, không từ suy luận.

## Cách dùng file này

Khi viết đặc tả hay review PR có mùi "thông minh" (dự đoán, khuyến nghị, tự
động quyết), mở file này và hỏi ba câu: *nó đọc bảng lv3 nào — bảng đó đáng
tin chưa — người nào duyệt đầu ra của nó?* Không trả lời được câu nào thì
tính năng đang đứng nhầm cấp.
