# GIAO VIỆC — Bộ máy làm video hướng dẫn "Việc của đối tác"

> Soạn 09/11/2026 cho Claude Code trên Mac. Đặt file này vào `docs/GIAO-VIEC-VIDEO-HUONG-DAN.md`
> rồi bảo Claude Code: "Đọc CLAUDE.md, rồi làm theo docs/GIAO-VIEC-VIDEO-HUONG-DAN.md, đợt 1."
> **Thứ tự:** `docs/GIAO-VIEC-AN-MA-ONG.md` (ẩn mã ống) xong trước; nhánh quay dựng trên nhánh đó
> (hoặc main sau khi PR ẩn mã đã gộp). Chương 0–3 không phụ thuộc, làm song song được.

```text
Đọc CLAUDE.md của repo, rồi docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md mục 5d và 8,
.claude/rules/xet-nghiem-doi-tac.md, src/dashboard/e2e/README.md.

VIỆC (một câu):
  Dựng một bộ máy làm video hướng dẫn: viết kịch bản một lần → máy tự đọc lời,
  tự bấm màn, tự quay, tự ghép tiếng + phụ đề → ra video chỉn chu, giao diện đổi
  thì chạy lại một lệnh là có video mới. Áp dụng đầu tiên cho màn "Việc của đối tác".

Ở ĐÂU:
  Màn quay: /ban-xet-nghiem (tab Việc theo ngày · Còn tồn · Kết quả · Tiền thu hộ · Cài đặt)
            + lối vào ở thanh bên "Việc của đối tác".
  Code mới: scripts/video-huong-dan/ (Node, dùng playwright có sẵn trong src/dashboard).
  Kịch bản: docs/huong-dan-video/kich-ban/<so>-<ten>.yaml + docs/huong-dan-video/doc-chu.yaml.
  Video ra: NGOÀI repo — ~/ClinicAI-video/<YYYYMMDD>/ (không commit mp4/wav).
  Tham khảo cách đăng nhập + bấm: src/dashboard/e2e/danh-sach-hoa-don.mjs.
```

---

## 1. Đã quyết (không hỏi lại, làm theo)

| Việc | Quyết | Vì sao |
|---|---|---|
| Quay ở đâu | **Local trên Mac** (`scripts/dev-up.sh` / `scripts/dev-giao-dien.sh`), DB demo, tài khoản `*@dr4women.local` | Staging là bản sao prod đã che, tên khách bị che trông lạ, và bị nạp lại 03:30 mỗi đêm. Local không có dữ liệu thật nào. |
| Dữ liệu trên hình | Script `dung-du-lieu.mjs` dựng bằng **chính API/màn của app** (không INSERT tay). Tên khách giả rõ ràng, ví dụ "Nguyễn Thị Minh Anh", SĐT `0900 000 1xx`. Đối tác mẫu "Medlatec" (mã `MED`, hẹn 3 ngày, gán HPV + ThinPrep, giá gợi ý 350.000 / 550.000) | Trạng thái đúng như dùng thật; quay lại lần nào cũng như nhau |
| Thứ tự làm | **Tiếng trước, hình theo tiếng**: đọc lời từng cảnh → đo độ dài → khi quay, mỗi cảnh làm xong thao tác thì chờ cho đủ độ dài tiếng (+0,4 giây nghỉ) | Không bao giờ lệch tiếng – hình |
| Quay | Playwright, Chrome thật (`channel: 'chrome'`), khung **1920×1080**, quay **một mạch mỗi chương**, ghi mốc thời gian bắt đầu từng cảnh vào `moc.json` | Ghép tiếng theo mốc bằng ffmpeg `adelay` |
| Độ nét | Thử `recordVideo` trước. Cắt 3 khung hình, **tự mở xem**: chữ cỡ 13px còn nét không. Nhòe ⇒ chuyển sang CDP `Page.startScreencast` (png) rồi ghép bằng ffmpeg. Ghi lựa chọn vào README | Chữ tiếng Việt có dấu nhòe là hỏng cả video |
| Giọng đọc | Bản nháp: `edge-tts` giọng nữ `vi-VN-HoaiMyNeural` (miễn phí). Bản chính: **Google Cloud Text-to-Speech** tiếng Việt, giọng nữ chất lượng cao nhất đang có (tự tra tên giọng hiện hành), khoá trong biến môi trường | Phòng khám đã có dự án Google Cloud (Drive) |
| Con trỏ | Chrome tự động không hiện chuột ⇒ **chèn con trỏ giả** bằng `addInitScript`: lướt cong 500–700 ms tới giữa nút rồi mới bấm, vòng gợn khi bấm | Người xem thấy tay đi đâu |
| Gõ chữ | `pressSequentially` 50–70 ms/ký tự | Nhìn như người gõ |
| Nhấn mạnh | Khung viền đỏ bo góc + làm tối phần còn lại 30%, hiện 1,2 giây trước khi bấm | Chỉ đúng chỗ cần nhìn |
| Phóng to | Làm **trong trang** bằng CSS `transform: scale(1.6)` hướng vào phần tử, mượt 600 ms, rồi thu về | Nét hơn phóng to ở hậu kỳ |
| Phụ đề | Sinh `.srt` từ chính lời + mốc; **in cứng** lên bản chính, kèm file `.srt` riêng. Chữ trắng viền đen, đáy màn, tối đa 2 dòng × 42 ký tự | Nhân viên hay xem không bật tiếng |
| Âm thanh | `loudnorm` I=-16 LUFS, TP=-1.5. Không nhạc nền ở đợt 1 | Đơn giản, rõ lời |
| Mở / kết | Thẻ mở 3 giây: tên chương + vai ("Dành cho: Quản lý"). Thẻ kết 2 giây: "Xong. Bước tiếp theo: …" | Xem lẻ từng chương vẫn hiểu |
| Xuất | MP4 H.264 1920×1080 30fps, CRF 18 (nháp: preset veryfast; bản chính: preset slow), AAC 192k. Kèm `.srt` + ảnh bìa PNG | Xem được trên mọi máy, Zalo gửi được |

---

## 2. Kịch bản — một file YAML mỗi chương

```yaml
chuong: 2
ten: "Ghi nhận thu hộ"
vai: "Nhân viên bàn xét nghiệm"        # tài khoản: dd.sa@dr4women.local
mo_dau: "Khách trả tiền xét nghiệm cho đối tác — ghi nhận thế nào"
canh:
  - id: mo-ban
    loi: "Vào mục Việc của đối tác ở thanh bên trái."
    lam:
      - nhan_manh: { role: link, name: "Việc của đối tác" }
      - bam: { role: link, name: "Việc của đối tác" }
      - cho: { text: "Hành trình xét nghiệm" }
  - id: chon-khach
    loi: "Chọn khách cần thu. Hai xét nghiệm đang ở trạng thái Chưa thu tiền."
    lam:
      - bam: { text: "Nguyễn Thị Minh Anh" }
      - phong_to: { text: "Chưa thu tiền" }
  - id: go-tien
    loi: "Ô số tiền đã điền sẵn giá gợi ý. Khách trả khác thì sửa lại cho đúng số thật."
    lam:
      - go: { label: "Tiền mặt", chu: "300000" }
```

- Bước `lam` chỉ được tìm phần tử theo **vai + tên** hoặc **chữ trên màn** (như người dùng thấy), không dùng class CSS — giao diện đổi kiểu không làm vỡ kịch bản.
- Một cảnh = một ý = một câu nói ≤ 25 từ. Một chương 60–120 giây.
- `doc-chu.yaml`: bảng đọc cho máy đọc, áp trước khi gửi sang giọng đọc: `XN → xét nghiệm`, `CK → chuyển khoản`, `TM → tiền mặt`, `CSKH → chăm sóc khách hàng`, `HPV → hát pê vê`, `ThinPrep → thin prép`, `300000 → ba trăm nghìn đồng`. Nghe thử, sai chữ nào thì thêm vào bảng, **không** sửa lời trong kịch bản.
- Lời nói theo chữ trên màn: màn ghi "Chưa thu tiền" thì nói "Chưa thu tiền". Nhãn lấy từ màn thật, không lấy từ kế hoạch (mục 8 kế hoạch còn chữ cũ "Chờ thu", "giá gợi ý chữ mờ").

---

## 3. Chương

**Đợt 1 — làm ngay (phần đã ổn định):**

| # | Chương | Vai / tài khoản | Nội dung |
|---|---|---|---|
| 0 | Bàn "Việc của đối tác" là gì | Quản lý `ql@` | Thanh bên → 5 tab → hành trình 5 mốc (Chưa thu → Đã thu → Đã lấy mẫu → Có kết quả → Đã gửi). Hai mốc cuối chỉ nói một câu "sẽ có hướng dẫn riêng". Tối đa 60 giây |
| 1 | Cài đặt đối tác | Quản lý `ql@` | Thêm đối tác, mã ngắn, hẹn trả, tài khoản nhận CK, gán xét nghiệm + giá gợi ý, xem bảng Quyền |
| 2 | Ghi nhận thu hộ | Nhân viên `dd.sa@` | Chọn khách → Thu tiền: tiền mặt (Khách đưa / Trả lại khách), chuyển khoản + mã giao dịch + ảnh CK, trả cả hai |
| 3 | Tiền thu hộ, huỷ và hoàn | Quản lý `ql@` | Tab Tiền thu hộ theo ngày ghi nhận; **Huỷ = ghi sai**, **Hoàn = trả tiền thật cho khách** — hai nút khác nhau, đều bắt lý do |
| 4 | Lấy mẫu và hoàn tác bước trước | Nhân viên `dd.sa@` | Nút Lấy mẫu mờ khi chưa thu ⇒ thu xong mới sáng; lấy mẫu chung một ống cho nhiều xét nghiệm cùng đối tác; hẹn trả; Hoàn tác bước trước (bắt lý do) |

**Chương 4 quay KHÔNG có mã ống** (Tuyền 09/11: mã ống chưa bàn với phòng khám). Điều kiện:
PR `claude/an-ma-ong` (`docs/GIAO-VIEC-AN-MA-ONG.md`) đã vào nhánh đang quay và công tắc
"Hiện mã ống" đang **tắt**. Lời và hình không được nhắc tới mã ống, in tem, ghi mã lên ống.
Trước khi quay chương 4, trích khung hình kiểm: không có chuỗi dạng `M` + 6 chữ số nào trên màn.

**Bản 2 (v2) — CHƯA làm, chờ đối tác báo cách tự động lấy kết quả:**

| # | Chương | Chờ |
|---|---|---|
| 5 | Kết quả về: tự về / tải tay, ghép tay, từ chối tệp | Cách lấy kết quả từ đối tác (đang hỏi IT bên đối tác) |
| 6 | CSKH "Đúng người, gửi" và thu hồi | Đi cùng chương 5 |
| 7 | Còn tồn, cảnh báo trễ, Xem quá trình | Đi cùng chương 5 |

Bản 2 cũng là lúc xem lại chương 4 nếu phòng khám chốt dùng mã ống.

---

## 4. Lệnh

```bash
cd src/dashboard
npm run video:du-lieu                          # dựng dữ liệu demo cho mọi chương
npm run video:huong-dan -- --chuong 2 --nhap   # một chương, bản nháp (edge-tts, preset veryfast)
npm run video:huong-dan -- --tat-ca            # bản chính mọi chương đợt 1 + 1 video gộp có mục lục
```

Mỗi lần chạy ra `~/ClinicAI-video/<YYYYMMDD>/`: `02-ghi-nhan-thu-ho.mp4`, `.srt`, `.png` (bìa),
`moc.json`, `bao-cao.md`.

---

## 5. KẾT QUẢ CẦN ĐẠT

- Tuyền chạy **một lệnh** là ra video một chương, không phải chỉnh tay khâu nào.
- Nghe: giọng đọc tiếng Việt tự nhiên, không đọc sai chữ viết tắt, không có khoảng lặng > 1,5 giây.
- Nhìn: luôn thấy con trỏ đi tới trước khi bấm; chỗ cần nhìn có khung đỏ hoặc được phóng to; không có cảnh "Đang tải…", vòng xoay, thông báo lỗi, chữ bị cắt "Kh…", thanh cuộn nhảy.
- Tiếng và hình lệch nhau không quá 0,3 giây ở mọi cảnh.
- Không có bất kỳ dữ liệu thật, email thật, khoá, thanh địa chỉ có token nào trên hình.
- Giao diện đổi nhãn/vị trí ⇒ kịch bản báo **đúng cảnh nào hỏng, tìm không thấy gì**, rồi dừng; không quay video lỗi.

## 6. CÁCH KIỂM (Claude Code tự làm trước khi báo)

1. Với mỗi cảnh, trích 1 khung hình giữa cảnh (`ffmpeg -ss`), **tự mở xem từng ảnh** và ghi vào `bao-cao.md`: đúng màn chưa, có lỗi nào ở mục 5 không.
2. Đo âm lượng (`ffmpeg -af ebur128`) ghi vào báo cáo; đo độ lệch tiếng – hình từ `moc.json`.
3. Xem lại phụ đề: không dòng nào quá 42 ký tự, không che nút đang bấm (che ⇒ đẩy phụ đề lên trên cho cảnh đó).
4. Chạy lại cùng lệnh lần hai ⇒ video giống lần một (cùng độ dài ± 1 giây).
5. **Cổng duyệt:** làm xong **chương 2 bản nháp** thì dừng, gửi Tuyền xem (đây là "bản dựng đầu tiên" Tuyền chờ xem). Tuyền duyệt giọng, nhịp, kiểu nhấn mạnh rồi mới làm các chương còn lại.

## 7. KHÔNG ĐƯỢC ĐỤNG

- Không sửa giao diện hay luật của app để quay cho đẹp. Thấy lỗi giao diện ⇒ ghi vào `bao-cao.md` mục "Lỗi thấy khi quay", làm việc riêng sau.
- Không quay trên staging hay prod; không dùng tài khoản thật; không dữ liệu khách thật.
- Không commit video, tiếng, khoá Google. Video ra ngoài repo; nếu cần thư mục tạm trong repo thì thêm nó vào `.gitignore`.
- Không cài phần mềm trả phí. Thiếu `ffmpeg` / `edge-tts` ⇒ cài bằng `brew` / `pipx`, ghi vào README.

## 8. ĐẦU RA

- Nhánh `claude/video-huong-dan` từ `origin/main` → PR: `scripts/video-huong-dan/`, `docs/huong-dan-video/` (kịch bản + README cách chạy + cách thêm chương mới), script npm.
- Báo cáo 4 mục SO-LUAT 12.4 + đường dẫn video nháp chương 2 + ảnh khung hình đã soi.
