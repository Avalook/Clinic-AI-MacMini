# Video hướng dẫn — viết kịch bản một lần, máy tự làm video

Giao việc gốc: `docs/GIAO-VIEC-VIDEO-HUONG-DAN.md`. Code: `scripts/video-huong-dan/`.
Áp dụng đầu tiên: bàn **Việc của đối tác** (`/ban-xet-nghiem`).

## Chạy

Cần: stack local đang chạy (`scripts/dev-up.sh`, hoặc API + web của nhánh ở cổng riêng),
**worker sự kiện** đang chạy (phiên bác sĩ chỉ mở sau check-in nhờ nó), Google Chrome,
`ffmpeg` (`brew install ffmpeg`), `edge-tts` cho bản nháp (`brew install pipx && pipx install edge-tts`).

```bash
cd src/dashboard
npm run video:du-lieu                          # dựng dữ liệu demo mọi chương (chạy lại = về trạng thái đầu)
npm run video:huong-dan -- --chuong 2 --nhap   # một chương, bản nháp (edge-tts, preset veryfast)
npm run video:huong-dan -- --tat-ca --nhap     # mọi chương đợt 1 (0–4) bản nháp + video gộp
npm run video:huong-dan -- --tat-ca            # bản chính (Google TTS, preset slow) + video gộp
```

Chạy API/web ở cổng khác 8100/3100: thêm `VIDEO_API_URL=http://127.0.0.1:8291 VIDEO_WEB_URL=http://127.0.0.1:3291`.
Script **chỉ chịu** địa chỉ loopback — không bao giờ quay staging/prod.

Ra `~/ClinicAI-video/<YYYYMMDD>/` (ngoài repo, không commit): `<so>-<ten>.mp4` · `.srt` ·
`.png` (bìa) · `.moc.json` (mốc từng cảnh) · `.khung/` (một khung giữa mỗi cảnh để soi) · `bao-cao.md`.
`--tat-ca` thêm `00-tron-bo.mp4` (nối các chương, có **chương** trong tệp — QuickTime/VLC hiện danh
sách để nhảy tới) và `00-muc-luc.txt` (mốc phút:giây từng chương, dán được vào mô tả video).

| Chương | Kịch bản | Vai | Khách mẫu lúc bắt đầu |
|---|---|---|---|
| 0 | `00-ban-viec-doi-tac.yaml` | Quản lý `ql` | Lê Thị Ngọc Lan: HPV đã thu, ThinPrep chưa thu |
| 1 | `01-cai-dat-doi-tac.yaml` | Quản lý `ql` | thêm "Phòng xét nghiệm Mẫu" (PXN) trên hình — bản lần quay trước được đổi mã + ngưng |
| 2 | `02-ghi-nhan-thu-ho.yaml` | Nhân viên `dd.sa` | Nguyễn Thị Minh Anh: cả hai chưa thu |
| 3 | `03-tien-thu-ho-huy-hoan.yaml` | Quản lý `ql` | khách đầu tiên chưa bị hoàn trong danh sách (Trần Thị Thu Hà…): cả hai đã thu |
| 4 | `04-lay-mau-hoan-tac.yaml` | Nhân viên `dd.sa` | Lê Thị Ngọc Lan (như chương 0). **Công tắc "Hiện mã ống" phải tắt** |

Chương 3 bấm **Hoàn tiền** (tiền thật — không bù được, và đã hoàn thì không huỷ được ghi nhận)
⇒ mỗi lần quay trong ngày dùng khách kế tiếp (`KHACH.hoan` trong `dung-du-lieu.mjs`, 5 tên);
kịch bản gọi khách đó là `{khach_hoan}`.

| Biến | Khi nào | Ý nghĩa |
|---|---|---|
| `GOOGLE_TTS_API_KEY` | bản chính | khoá Google Cloud Text-to-Speech (dự án Google Cloud của phòng khám). Không commit, không dán vào chat. |
| `GOOGLE_TTS_VOICE` | tuỳ chọn | ép tên giọng; bỏ trống ⇒ script tự tra danh sách giọng vi-VN và chọn giọng nữ tốt nhất (Chirp3-HD → Neural2 → Wavenet → Standard) |
| `TEST_PW`, `BACKEND_API_KEY` | tuỳ chọn | ghi đè mặc định của tài khoản thử local (giống `scripts/dev-up.sh`) |

## Cách máy làm (để sửa đúng chỗ)

1. **Dữ liệu** (`dung-du-lieu.mjs`) — bằng CHÍNH API của app: đối tác Medlatec (MED, hẹn 3 ngày,
   HPV 350.000 / ThinPrep 550.000), khách giả "Nguyễn Thị Minh Anh" 0900000101 → lịch → check-in →
   bác sĩ chỉ định. Đã có việc hôm nay ⇒ đưa về đầu bằng lệnh bù của bàn (huỷ mẫu, huỷ ghi nhận thu).
2. **Tiếng trước** (`loi.mjs`) — đọc lời từng cảnh (đã áp `doc-chu.yaml`), đo độ dài, lưu đệm theo băm.
3. **Hình theo tiếng** (`quay.mjs` + `lop-trang.js`) — Chrome thật, 1920×1080, quay một mạch:
   mỗi cảnh hiện phụ đề → làm các bước → chờ đủ độ dài tiếng + 0,4 s. Thẻ mở/kết có lời.
   Ghi hình bằng CDP `Page.startScreencast` (PNG, không mờ chữ). Không dùng `recordVideo`
   của Playwright: cần tải thêm ffmpeg riêng và nén VP8 làm nhoè chữ 13 px.
   Chrome ẩn mặc định chỉ ghi được 993 px chiều cao ⇒ script tự chỉnh cửa sổ tới đúng 1080.
4. **Ghép** (`ghep.mjs`) — tiếng đặt đúng mốc (`adelay`), `loudnorm` −16 LUFS / −1,5 dBTP,
   H.264 CRF 18 30 fps, AAC 192k, `.srt` sinh từ chính lời + mốc.
   Phụ đề **vẽ trong trang lúc quay** (ffmpeg Homebrew không có `subtitles`/`drawtext`) —
   cùng lúc biết nút đang bấm ở đâu để đẩy phụ đề lên khi đè.
5. **Soi** — khung giữa từng cảnh, âm lượng, khoảng lặng > 1,5 s, phụ đề > 42 ký tự, lệch tiếng–hình.
   Người làm video **tự mở xem từng khung** và ghi vào `bao-cao.md` (cột "Soi bằng mắt").

## Thêm một chương

1. Tạo `docs/huong-dan-video/kich-ban/<so>-<ten>.yaml` (xem `02-ghi-nhan-thu-ho.yaml`):
   `chuong`, `ten`, `vai` (hiện trên thẻ mở), `tai_khoan` (vd `ql`, `dd.sa`), `mo_tu` (trang mở đầu),
   `mo_dau`, `ket_thuc`, tuỳ chọn `cam_tren_man` (danh sách regex chữ không được hiện — vd
   `"M\\d{6}"` cho chương 4 khi tắt mã ống), và `canh`.
2. Mỗi cảnh: `id`, `loi` (≤ 25 từ, **đúng chữ trên màn**), `lam` (các bước):

| Bước | Làm gì |
|---|---|
| `re: {…}` | rê chuột vào (thanh bên chỉ có biểu tượng ⇒ mở chữ ra) |
| `nhan_manh: {…}` | khung đỏ + làm tối phần còn lại 1,2 s |
| `bam: {…}` | con trỏ lướt tới, gợn tròn, bấm |
| `go: {…, chu: "…"}` | bấm vào ô, xoá, gõ 60 ms/ký tự |
| `phong_to: {…, he: 1.6}` | phóng to tại chỗ rồi thu về |
| `chon: {label: "…", chu: "…"}` | chọn mục trong ô thả xuống theo chữ (tên trùng ⇒ mục đầu) |
| `cho: {…}` | chờ phần tử hiện (và màn hết "Đang tải…") |
| `dung: 1.5` | dừng thêm (giây) |

   Tìm phần tử CHỈ bằng `role` + `name`, `text` (chữ trên màn) hoặc `label` (nhãn ô); thêm
   `exact: true` khi cần khớp nguyên chữ; `trong: "<chữ>"` = trong khung NHỎ NHẤT chứa cả chữ
   đó lẫn phần tử (thẻ việc, thẻ đối tác, form…) — vd hai nút "Lưu": `trong: "Thêm đối tác"`.
   `name: "/…/"` = mẫu regex (vd `"/{khach_hoan}.*hoàn tiền/"` — đúng dòng của khách này).
   `{khach_<khoá>}` = tên khách mẫu `dung-du-lieu.mjs` vừa dựng cho chương (khoá trong `KHACH`).
   **Không dùng class CSS** — giao diện đổi kiểu không làm vỡ kịch bản.
3. Giọng đọc sai chữ nào ⇒ thêm vào `doc-chu.yaml`, không sửa lời.
4. Giao diện đổi nhãn/vị trí ⇒ lệnh dừng với câu "Cảnh «id», bước N: không tìm thấy …" và
   **không ra video** — sửa kịch bản theo màn mới rồi chạy lại.
5. Thêm số chương vào `DOT_1` trong `chay.mjs` nếu muốn `--tat-ca` làm nó, và dòng `CAN` trong
   `dung-du-lieu.mjs` (chương cần khách / đối tác nào).

## Bẫy đã gặp

- edge-tts hay báo "No audio was received" **ngẫu nhiên** (cùng câu lúc được lúc không) ⇒ script
  tự thử lại tới 12 lần, chờ lâu dần. Hỏng hẳn thì chạy lại lệnh: đoạn đã đọc nằm ở bộ đệm
  `~/ClinicAI-video/dem-tieng`, chỉ đọc lại đoạn thiếu.
