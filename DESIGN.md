# DESIGN.md — Hiến pháp giao diện ClinicAI

Chốt **15/08/2026** (Tuyền chọn từ hai phương án render thật: **khí chất Linear
+ nền dịu của Stripe**). File này trả lời "UI TRÔNG thế nào"; `CLAUDE.md` trả
lời "code CÁCH nào" — hai file riêng, không gộp.

**Luật gốc:** mọi thay đổi giao diện lấy giá trị từ các thang trong file này.
"To ra / bé đi" nghĩa là **nhích một bậc thang**, không bao giờ là cộng trừ px
tự do. Số đo ngày chốt: repo có **463 giá trị kích thước tuỳ ý** (`[..px]`) —
con số ấy chỉ được giảm (xem §Kỷ luật thi hành).

---

## 1. Khí chất & không khí

Phần mềm vận hành cho người nhìn nó **cả ca làm việc**: phẳng, gọn, dày dữ liệu
mà không ngộp. Chiều sâu tạo bằng **viền mảnh + bậc nền**, không bằng bóng đổ.
Trang không có trang trí; thứ duy nhất được phép nổi bật là **trạng thái cần
hành động** (đỏ/vàng). Một màn nhiều màu đỏ hơn hai chỗ là màn sai — màu cảnh
báo lạm phát thì người trực học cách bỏ qua nó.

## 2. Màu — vai trò, không phải bảng màu

Giữ nguyên hệ token trong `globals.css`. KHÔNG thêm màu mới ngoài một token:

| vai trò | token | hex | ghi chú |
|---|---|---|---|
| Nền trang (canvas) | `--color-surface-muted` | `#f5f8fb` | "nền dịu của B" — token có sẵn, không thêm màu |
| Thẻ / bảng | `--color-surface` | `#ffffff` | mọi nội dung ngồi trên thẻ trắng |
| Viền mảnh (MỚI) | `--color-hairline` | `#e5e9f0` | viền thẻ + kẻ ngang trong bảng |
| Viền đậm | `--color-line-strong` | `#bcccdc` | chỉ cho ô nhập và nút outline |
| Chữ chính | `--color-ink` | `#102a43` | |
| Chữ phụ | `--color-ink-muted` | `#627d98` | meta, nhãn cột |
| Chữ mờ | `--color-ink-faint` | `#829ab1` | placeholder, "—" |
| Thương hiệu | `--color-brand-600` | `#0c7476` | nút chính, liên kết, tab đang chọn |
| OK / cảnh báo / lỗi | token `status-*` sẵn có | | màu ngữ nghĩa ≠ màu thương hiệu |

Quy tắc: **màu ngữ nghĩa không bao giờ dùng để trang trí**, và teal thương hiệu
không bao giờ dùng để báo trạng thái.

## 3. Chữ — đúng 5 cỡ, hết

Font: system stack hiện tại (SF trên macOS/iOS, Segoe/Roboto nơi khác). Số luôn
`font-variant-numeric: tabular-nums` ở mọi cột số.

| bậc | cỡ | đậm | dùng cho |
|---|---|---|---|
| `label` | 11px, +0.05em, UPPERCASE | 600 | nhãn cột bảng, eyebrow |
| `meta` | 12px | 400 | mã BN, giờ, chú thích |
| `body` | **13px** | 400/600 | thân bảng, nội dung mặc định |
| `emph` | 14px | 500/600 | tên trong danh sách, nút cỡ lớn |
| `title` | 16px, −0.01em | 600 | tiêu đề màn; con số KPI dùng 22px cùng bậc này |

Cấm: mọi `text-[..px]` ngoài 5 bậc trên. 8 cỡ hiện hành (9→15, 28) gom về đây.

## 4. Khoảng cách & bo góc — lưới 4px

Khoảng cách chỉ dùng: **4 / 8 / 12 / 16 / 24 / 32**. Bo góc chỉ dùng:

| token | giá trị | dùng cho |
|---|---|---|
| `r-chip` | 6px | chip, badge |
| `r-control` | 8px | nút, ô nhập, select |
| `r-card` | 12px | thẻ, khung bảng |
| `r-modal` | 16px | hộp thoại, panel trượt |

KHÔNG pill (trừ avatar), không 4px lẻ, không mix.

## 5. Nút — giải phẫu cố định (hết lỗi "góc bo mỏng hơn cạnh")

Nguồn lỗi cũ: viền 1px chạy theo cung tròn bị khử răng cưa nên góc nhạt hơn
cạnh. Cách chữa nằm trong cấu trúc, không phải chỉnh từng nút:

| loại | nền | viền | chữ |
|---|---|---|---|
| **primary** | `brand-600` phủ đặc, hover `brand-700` | **không viền** | trắng, 600 |
| **secondary** | trắng | `inset ring 1px line-strong` (không dùng `border`) | ink, 500 |
| **ghost** | trong suốt, hover `surface-sunken` | không | ink-muted |
| **danger** | trắng | ring 1px đỏ nhạt | đỏ |

Cỡ: **sm 28px** (trong bảng) · **md 32px** (mặc định) · **lg 40px** (điện
thoại, hành động chính). Đệm ngang 12/14/16. Bo `r-control`. Mỗi màn tối đa
**một** nút primary trong một vùng nhìn.

Chip: cao 20px, đệm ngang 7px, bo `r-chip`, chữ `label` không uppercase, nền
nhạt + chữ đậm cùng họ màu — **không viền**.

## 6. Bảng — nơi sửa cảm giác "Google Sheets"

1. **Chỉ kẻ ngang**, bằng `hairline`. Kẻ dọc bị cấm — căn cột và khoảng trắng
   làm việc của nó. (Ngoại lệ duy nhất: lưới đặt chỗ kiểu rạp phim, vốn là ma
   trận ghế thật.)
2. Header: nền `#fcfcfd`, chữ `label`, dính (`sticky`) khi bảng cuộn.
3. Hàng cao ~40px (đệm dọc 9px); hover `#f7f9fa`; hàng chọn `surface-selected`.
4. Cột số/ngày **căn phải**, tabular-nums. Cột chữ căn trái. Không căn giữa.
5. Ô trống ghi `—` màu ink-faint — không bỏ trắng.
6. Cảnh báo nằm **trong hàng** nó nói về, nền vàng nhạt bo `r-chip`.
7. Cột hành động ghim phải, nút cỡ `sm`.

## 7. Responsive — hai chiến lược, chọn theo loại bảng

Breakpoint: **375 / 768 / 1280**. Mọi thay đổi giao diện nghiệm thu ở đủ ba cỡ
(ảnh chụp cả ba là một phần của bàn giao — Luật 12.4).

- **Bảng danh sách** (Quản lý khách hàng, Danh sách BN…): dưới 768px **xuống
  dạng thẻ** — hàng 1: tên + chip trạng thái; hàng 2: bước tiếp theo + hạn.
  Không bao giờ bóp 7 cột vào 375px.
- **Bảng vận hành rộng** (lịch tuần, lịch làm việc, lưới đặt chỗ): giữ dạng
  bảng, **cuộn ngang bên trong thẻ** (`overflow-x:auto`), cột định danh đầu
  tiên dính trái. Thân trang không bao giờ cuộn ngang.
- Ô bấm trên điện thoại tối thiểu **40px** chiều cao.

## 8. Chuyển động

Chỉ ba thứ được chuyển động: hover/press của nút và hàng (120ms), mở panel
(200ms ease-out), nhấp nháy cảnh báo (chỉ khi cần hành động ngay, tôn trọng
`prefers-reduced-motion`). Không animation trang trí.

## 9. Hướng dẫn ra lệnh (cho người + cho AI)

- *"chữ to lên"* → nhích **một bậc** trong 5 bậc (§3), áp qua token, kiểm 3 cỡ màn.
- *"cột này rộng ra"* → đổi tỉ lệ `fr`/minmax trong lưới chung của bảng đó —
  header và hàng dùng **cùng một lưới** (test đang canh).
- *"thêm nút"* → chọn 1 trong 4 loại §5, cỡ theo ngữ cảnh; không tự chế class.
- *"bảng xấu"* → soi theo 7 điều §6 trước khi bàn thêm.
- Thứ tự ưu tiên khi mâu thuẫn: **lời người dùng > file này > thói quen cũ
  trong code**.

## Kỷ luật thi hành

1. Component dùng chung ở `components/ui/` (Button, Chip, DataTable, Field —
   Bước 1 của kế hoạch đại tu). Màn nào cần nút là import, không tự vẽ.
2. **Ratchet:** số giá trị `[..px]` tuỳ ý hiện tại **463** — bài kiểm CI chỉ cho
   giảm, không cho tăng (Bước 3).
3. Đổi bất kỳ thang nào trong file này = một PR riêng chỉ đổi file này + lý do,
   không đổi ngầm trong một PR tính năng.
