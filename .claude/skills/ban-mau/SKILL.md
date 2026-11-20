---
name: ban-mau
description: Làm bản mẫu (prototype) bấm được cho một tính năng ClinicAI để Tuyền xem, góp ý từng chỗ bằng bình luận, rồi mang đi bàn với quản lý trước khi code thật. Một màn duy nhất giống app thật, hướng dẫn nằm ngay dưới, sửa theo từng bình luận trên artifact. Dùng khi Tuyền nói "gen prototype", "làm bản mẫu", "dựng màn thử", "mô tả tính năng cho phòng khám xem", "cho quản lý xem luồng", "chưa code vội, làm mẫu trước", hoặc gửi bình luận trên một artifact bản mẫu.
---

# Bản mẫu bấm được cho ClinicAI

Mẫu đã làm đúng cách này: Việc của đối tác (xét nghiệm đối tác), 02/11/2026,
https://claude.ai/artifact/FQF9Awp8drByCVfZ7ycC8M. Mở nó ra trước khi làm cái mới.

Bản mẫu là để **hiểu nhau và bàn nghiệp vụ**, không phải code. Không đụng repo, không
PR, không migration. Dòng đầu câu trả lời: "Mức 1 · ước ~X phút".

## Tuyền muốn gì ở một bản mẫu

1. **Một màn duy nhất.** Giao diện trên, hướng dẫn ngay dưới. Không tách tab kiểu
   Hiểu luồng / Bấm thử / Cần chốt.
2. **Giống app thật.** Sidebar đủ nhóm và nhãn thật, màu, chữ, chip, bảng theo
   `DESIGN.md` và `globals.css`. Màn đã có (Bàn khám, Quản lý khách hàng, Thu tiền
   dịch vụ…) dựng lại đúng bố cục thật, chỉ thêm phần mới.
3. **Hướng dẫn trả lời đúng ba câu của đầu việc:** tính năng làm gì, xuất hiện ở đâu,
   vai trò nào làm gì. Thêm **kịch bản bấm thử dạng bảng** với cột Bước · Màn · Ai thao
   tác · Làm gì · Tiến độ; bấm một dòng là nhảy tới đúng màn.
4. **Không đưa mục "cần chốt" lên màn.** Đó là ý của Tuyền, chưa phải tài liệu chốt.
   Câu hỏi để trong chat hoặc trả lời bình luận.
5. **Tối giản.** Chỉ dựng đúng những gì Tuyền mô tả. Đừng thêm bước theo "thông lệ
   ngành" (đã bị xoá: phiếu bàn giao mẫu, mẫu không đạt, báo nguy hiểm, đối soát,
   chiết khấu). Muốn đề xuất thì hỏi trước, đừng dựng sẵn.
6. **Bấm được thật:** trạng thái đổi, số tiền tự cộng, timeline cập nhật, hoàn tác
   được, xem được tệp mẫu (PDF thật có dấu "BẢN MẪU MINH HOẠ").
7. **Chữ người thường hiểu.** Nút ghi việc cần làm, xong thì đổi thành trạng thái
   ("Thu tiền" → "Đã thu tiền"). Bỏ chữ thừa, số đếm thừa, ngày lặp lại khi đã có thanh
   ngày ở trên.

## Các bước

1. **Đọc thật trước khi vẽ.** Giao một agent Explore chỉ đọc, trả về: bảng/khái niệm
   đã có, luồng hiện tại, nhãn sidebar theo nhóm (`D/nav-items.ts`), vai trò
   (`lib/roles.ts`), bố cục màn thật sẽ đụng (cột, nhãn, thứ tự khối), token màu.
   Nói rõ trong bản mẫu cái gì hệ thống đã có, cái gì mới.
2. **Tạo artifact.** `Artifact` action `quickstart` intent `design`, rồi publish với
   `type_url` của Design, `title` theo tên tính năng, `auto_open: "after_first_write"`.
   Một artboard `Main.dc.html`, `expand: "fill"`, `is_interactive: true`,
   `launch: {"view":"focused","file":"Main.dc.html"}`. Làm thư mục trong scratchpad
   (`<root>/project/…`), publish bằng `root` + `file_path`.
3. **Dựng một artboard** theo khung dưới. Dữ liệu giả: khách `DEMO-*`, số tiền ghi
   rõ là giả. Không gắn tên đối tác/công ty thật lên tài liệu giả.
4. **Kiểm trước khi đăng** (Tuyền chốt "verifier trước"):
   - `node scripts/kiem-ban-mau.js <Main.dc.html> [kich-ban.js]`: báo hole `{{…}}`
     không có trong `renderVals()`, chạy kịch bản logic.
   - `scripts/xem-thu.sh <Main.dc.html> <dc-runtime.js>` (chạy nền) rồi mở
     `http://127.0.0.1:3291/Main.dc.html` trong trình duyệt app, bấm thật ở 1280 và
     375, đo tràn ngang, đọc console.
5. **Đăng và báo.** Nói rõ đã kiểm ở lớp nào; chưa xem được trang đăng thật thì nói.

## Khung một artboard

```
top: tên tính năng · "Bản mẫu bấm được · khách và số tiền đều là giả"
#dauApp
  guide: các bước của luồng (chip bấm được) + một dòng "Bước n/N · Ai. Làm gì" + Hoàn tác / Làm lại
  app: sidebar thật (nhóm + nhãn, mục chưa liên quan để mờ) | main: các màn, mỗi màn một sc-if
wrap (hướng dẫn): Tính năng này là gì · Xuất hiện ở đâu (bảng) · Vai trò nào làm gì (bảng)
                  · Kịch bản bấm thử (bảng bấm được) · Thử thêm tình huống · phần nghiệp vụ riêng (tiền…)
popup: bảng nổi xem nhanh khách, tờ kết quả (ảnh PDF + nút Mở file PDF)
```

Mẫu thao tác đã dùng và Tuyền ưng: ô tìm không dấu theo tên/mã; bấm tên khách mở bảng
nổi, có câu "vì sao" và bấm để nhảy tới đúng mục; timeline ngang 5 mốc, mốc đang chờ
xanh dương có vòng toả, bấm mốc là làm việc đó; timeline dọc cho "Xem quá trình", cùng
ngày chỉ hiện giờ; xoá chỉ gạch đi + "Hoàn tác xoá"; chọn đối tác bằng một nút toggle
góc phải; Cài đặt sửa được thật (thêm đối tác, gán, quyền, thông báo).

## Bẫy của định dạng `.dc.html` (đã cắn)

- `{{hole}}` chỉ là đường dẫn, không biểu thức. Tính hết trong `renderVals()`.
- Chữ + hole trong nút `inline-flex` bị nuốt dấu cách ("Đi tới mànBàn khám"): ghép
  chuỗi sẵn trong JS.
- Không `<table>` với `<sc-for>` bên trong (trình duyệt đẩy ra ngoài): dùng grid div.
- Ô nhập: `value="{{x}}" onChange="{{fn}}"`, đọc `e.target.value`.
- Cuộn tới mục: đặt `cuon` trong state, `componentDidUpdate` gọi `scrollIntoView` rồi xoá.
- Thêm `<meta name="viewport">`, không thì 375 thành 980.
- Ảnh/PDF: upload asset (`Artifact` publish `asset: true`), dùng đúng `/_blob/<id>`.
  Không iframe/embed: hiện ảnh trang PDF + link mở PDF. Tạo bằng `scripts/tao-pdf-mau.sh`.
- Trình duyệt thử: nút lọc và nút thao tác có thể trùng chữ, bấm theo `.btn.pri`
  trong `.main` khi chạy kịch bản.

## Khi Tuyền góp ý bằng bình luận trên artifact

Mỗi bình luận là một vòng nhỏ:
1. `Artifact` read `project/Main.dc.html` và so với bản local (`cmp`). Khác thì gộp
   trước.
2. Sửa đúng chỗ được nói, bằng thay chuỗi chính xác (báo lỗi nếu không khớp đúng một
   lần). Đổi chữ thì đổi đồng bộ mọi chỗ cùng nghĩa, nói rõ chỗ nào cố ý giữ.
3. Kiểm logic; đổi giao diện thì bấm thử local.
4. Publish, rồi trả lời trong đúng luồng bình luận (ArtifactComments reply): làm gì,
   kiểm ở lớp nào, còn điểm nào cần Tuyền quyết. Trong phiên chỉ viết một dòng.
5. Bình luận là câu hỏi ("cái này để làm gì?") thì trả lời, đề xuất, chưa sửa.
6. Bỏ một thứ đang gánh một luật (ví dụ hoàn tác bắt buộc), hoặc xoá làm một con số
   hiểu sai: vẫn làm, nhưng nói hệ quả một câu.

## Khi bản mẫu xong

- Ghi memory `project` một tệp: concept đã chốt, link artifact, các thứ đã bỏ và vì sao.
- Code thật là việc riêng, theo `docs/SO-LUAT.md` và mức việc; đụng tiền, quyền,
  migration là Mức 3, có kế hoạch duyệt trước.
