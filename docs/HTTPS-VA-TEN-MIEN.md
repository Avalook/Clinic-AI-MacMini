# HTTPS và tên miền — chọn đường nào, làm thế nào

Viết 21/08/2026 sau khi Tuyền hỏi làm Cloudflare Tunnel và phát hiện phòng khám
**chưa có tên miền cho phần mềm**.

---

## 1. Đang ở đâu

| | |
|---|---|
| Địa chỉ đang dùng | `http://222.255.215.219` (prod) · `:8080` (staging) |
| Giao thức | **HTTP trần** — không mã hoá |
| `SITE_ADDRESS` trong `.env` | `:80` — nghĩa là "TLS do tunnel lo", đang chờ sẵn |
| `cloudflared` trong `docker-compose.yml` | **đã viết sẵn**, ẩn sau `--profile cloudflare` |
| `dr4women.vn` | không có bản ghi DNS nào — chỉ dùng làm đuôi tên đăng nhập |
| `dr4women.com` | web giới thiệu, chạy Squarespace, **đừng đụng vào** |

Nói cách khác: **code đã sẵn sàng từ lâu**, thứ duy nhất thiếu là một cái tên.

### Vì sao HTTP trần là vấn đề thật, không phải chuyện làm màu

- **Mật khẩu và dữ liệu bệnh nhân đi qua mạng ở dạng đọc được.** Ai đứng cùng
  wifi phòng khám, hoặc ngồi ở bất kỳ nút mạng nào giữa phòng khám và VPS, đều
  đọc được. Đây là dữ liệu y tế.
- **Trình duyệt sẽ ngày càng cản đường.** Chrome đã hiện "Không bảo mật" cạnh
  địa chỉ; các tính năng mới (thông báo đẩy, máy ảnh, lưu ngoại tuyến) chỉ chạy
  trên HTTPS.
- **IP trần bị dò tự động.** Trong 14 giờ log ngày 21/08 có 15 lượt bot dò cổng.
  Chưa gây hại, nhưng đó là tiếng gõ cửa liên tục.
- **Đổi máy chủ là đổi địa chỉ.** Mọi người đang nhớ dãy số; chuyển VPS lần sau
  là cả phòng khám phải học lại. Tên miền thì trỏ đi đâu cũng được.

---

## 2. Hai đường đi

### Đường A — Tailscale Funnel: **miễn phí, không cần mua tên miền, làm được hôm nay**

Tailscale cho không một tên dạng `clinicai.<tên-nhóm>.ts.net` kèm HTTPS tự động.

**Được gì**
- HTTPS thật, chứng chỉ tự gia hạn, không tốn đồng nào
- Có ngay trong ngày, không chờ DNS lan truyền
- Giấu IP máy chủ

**Mất gì**
- Tên xấu, khó đọc cho khách (`clinicai.abc-xyz.ts.net`)
- Đi qua mạng Tailscale — thêm một nhà cung cấp nữa vào đường đi
- Không phải "thương hiệu" — dùng nội bộ thì ổn, đưa cho bệnh nhân thì kỳ

**Hợp khi**: muốn hết HTTP trần ngay, chấp nhận tên xấu, để tính chuyện tên
miền sau.

### Đường B — Cloudflare Tunnel: **cần một tên miền, khoảng 250.000đ/năm**

**Được gì**
- Tên đẹp, đọc được cho cả nhân viên lẫn bệnh nhân
- HTTPS + chống DDoS + bộ nhớ đệm của Cloudflare
- Đổi máy chủ không ai phải học lại địa chỉ
- Chặn được truy cập theo quốc gia / theo tài khoản (Cloudflare Access) nếu sau
  này muốn siết

**Mất gì**
- Tốn tiền tên miền, và phải chờ 15 phút–2 ngày cho DNS lan truyền

**Hợp khi**: đây là hệ thống dùng lâu dài cho phòng khám thật — tức là trường
hợp của mình.

### Nên chọn gì

**Mua tên miền mới, đi đường B.** Lý do: một hệ đang phục vụ bệnh nhân thật thì
250.000đ/năm là rẻ hơn mọi phương án chắp vá, và tên miền còn dùng cho email,
cho trang đặt lịch của khách sau này.

**Mua tên riêng cho phần mềm, ĐỪNG đụng `dr4women.com`.** Cloudflare gói miễn
phí đòi chuyển **toàn bộ** nameserver của tên miền về nó — nghĩa là web giới
thiệu trên Squarespace cũng phải chuyển theo. Cấu hình sót một bản ghi là trang
bán hàng sập. Không đáng đánh đổi.

Gợi ý tên: `dr4women.app`, `dr4women.io`, `dr4womenclinic.com`. Mua thẳng trên
Cloudflare thì khỏi bước đổi nameserver.

> **Tên miền `.vn`**: nếu phòng khám đã sở hữu `dr4women.vn` thì dùng được và
> không tốn thêm — nhưng phải biết đang mua ở nhà cung cấp nào và có quyền vào
> đó để đổi nameserver. Kiểm bằng `whois dr4women.vn` tại một nhà cung cấp Việt
> Nam, hoặc hỏi người đã lập các địa chỉ email `@dr4women.vn`.

---

## 3. Các bước — đường B (Cloudflare Tunnel)

Phần **chị làm** cần tài khoản và thẻ, tôi không làm hộ được. Phần **tôi làm**
đã chuẩn bị sẵn trong repo, chỉ chờ token.

### Chị làm

1. **Tạo tài khoản Cloudflare** tại `dash.cloudflare.com` (miễn phí).
2. **Mua tên miền** ngay trong đó: *Domain Registration → Register Domain*.
   Mua tại Cloudflare thì tên miền tự nằm sẵn trong tài khoản, bỏ được bước đổi
   nameserver.
3. **Tạo tunnel**: *Zero Trust → Networks → Tunnels → Create a tunnel* → chọn
   **Cloudflared** → đặt tên `clinicai-vps`.
4. **Chép token.** Màn hình sẽ hiện một lệnh cài dài; token là chuỗi rất dài
   sau chữ `--token`. **Chỉ cần chuỗi đó**, không cần chạy lệnh Cloudflare đưa
   — mình chạy bằng Docker.
5. **Khai hai tên** trong tab *Public Hostname* của tunnel:

   | Subdomain | Domain | Service |
   |---|---|---|
   | `app` | tên miền vừa mua | `http://caddy:80` |
   | `staging` | tên miền vừa mua | `http://caddy:80` |

   > Staging chạy compose riêng nên cần tunnel riêng hoặc trỏ tới container
   > Caddy của staging — lúc làm tôi sẽ chốt lại, đừng tự xoay ở bước này.

6. **Gửi token cho tôi** — hoặc tự dán vào `.env.prod` trên VPS:
   `TUNNEL_TOKEN=<chuỗi vừa chép>`

> ⚠️ Token này **là chìa khoá vào hệ thống**. Đừng dán vào chat công khai,
> đừng commit vào git. Dán thẳng vào `.env.prod` trên VPS là an toàn nhất.

### Tôi làm sau khi có token

1. Bật `cloudflared` (`--profile cloudflare`) và xác nhận tunnel báo *Healthy*
2. **Vá chỗ IP bị nướng cứng vào bản build** — xem mục 4, đây là bẫy chính
3. Bật lại HSTS cho đúng, đóng cổng 80/443 khỏi Internet, chỉ để tunnel vào
4. Đổi Uptime Kuma sang theo dõi tên miền mới
5. Đo lại: HTTPS thật, chứng chỉ hợp lệ, đăng nhập chạy, lịch hẹn nguyên vẹn
6. Làm trên staging trước, chị bấm thử, rồi mới tới prod

---

## 4. Bẫy đã biết trước: IP nướng cứng trong bản build

`NEXT_PUBLIC_SUPABASE_URL` là biến **nướng thẳng vào JavaScript lúc build**,
không phải đọc lúc chạy. Đã đo trong container prod ngày 21/08 — chuỗi
`http://222.255.215.219` nằm nguyên trong tệp gửi xuống trình duyệt.

Nghĩa là: đổi `.env` rồi khởi động lại thôi thì **chưa đủ** — trình duyệt vẫn
gọi về IP cũ. Phải **build lại** dashboard sau khi đổi biến.

Triệu chứng nếu quên: trang lên bình thường, nhưng đăng nhập xoay mãi hoặc
đá về `/login`; console báo lỗi nội dung hỗn hợp (trang HTTPS gọi tài nguyên
HTTP). Đúng họ với lỗi `proxy.ts` gọi Supabase bằng địa chỉ trình duyệt đã ghi
trong `DANG-LAM.md` mục 6.

Các chỗ phải đổi cùng lúc, cả hai môi trường:

```
NEXT_PUBLIC_SUPABASE_URL   → https://app.<tên-miền>
SUPABASE_PUBLIC_URL        → https://app.<tên-miền>
PUBLIC_SUPABASE_URL        → https://app.<tên-miền>
SITE_ADDRESS               → giữ nguyên :80  (TLS do tunnel lo)
```

---

## 5. Nếu chọn đường A (Tailscale Funnel) — làm hôm nay

```bash
ssh clinic-vps
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                 # mở link hiện ra để đăng nhập
sudo tailscale funnel --bg 80     # công khai cổng 80 kèm HTTPS
sudo tailscale funnel status      # xem tên .ts.net vừa được cấp
```

Rồi đổi ba biến ở mục 4 sang tên `.ts.net` ấy và **build lại** dashboard.

Bỏ khi không cần: `sudo tailscale funnel --https=443 off`.

---

## 6. Việc này KHÔNG chữa được cơn mạng chập chờn

Nói rõ để khỏi kỳ vọng nhầm. Ngày 21/08 đo được: máy chủ khoẻ (10/10 lượt gọi
dữ liệu dưới 340ms, Uptime Kuma cả ngày chậm nhất 138ms, không lần nào trượt),
nhưng trình duyệt ở phòng khám tự bỏ cuộc giữa chừng và luồng sự kiện rớt-nối
lại 4 lần trong 15 phút. Cộng với vụ trước — wifi phòng khám báo
`ERR_CONNECTION_TIMED_OUT` mà 4G vào được ngay — thì nghi phạm là **đường mạng
phòng khám**.

Tunnel *có thể* đỡ hơn vì đi qua mạng Cloudflare thay vì tuyến thẳng tới
Vietnix, nhưng đó là tác dụng phụ, không phải cách chữa. Muốn chữa thật thì
phải nhắm vào wifi/router phòng khám.

**Lần sau trang treo, làm ngay:** bật 4G điện thoại mở cùng trang. Vào được =
mạng phòng khám, khởi động lại router hoặc gọi nhà mạng. Không vào được = báo
tôi, lúc đó là chuyện của máy chủ.

Việc đang chạy song song: bật access log cho Caddy. Xong thì lần treo sau chỉ
cần mở log là phân xử dứt điểm — request có tới máy chủ hay không.
