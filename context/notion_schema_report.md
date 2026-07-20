# Notion schema report — NOTION-SCHEMA-01
> Generated: 2026-05-29 04:00 UTC · Root page: `36eccb0eac8880d5919ff96376be1fca` · Read-only inspection.

## TL;DR
- Databases discovered: **31**
- Data sources (Notion API 2025-09 model): **31**
- Properties from schema: **265** · back-side props only on pages: **59**
- Relation properties: **11** schema-side + **54** back-side (hidden from schema; recovered from page samples)
- ⚠️ `data_sources.retrieve` omits the back-side of dual-property relations defined in another DB. The import pipeline must read those columns from page properties (not schema).

## Database index
| # | Title | DB ID | Parent path | Data sources | Rows fetched |
| --- | --- | --- | --- | --- | --- |
| 1 | 🔑 File bệnh nhân (lâm sàng) | `ac6ccb0e` | (root) | 1 | 3 |
| 2 | 🔑 File khách hàng (hành chính) | `43dccb0e` | (root) | 1 | 3 |
| 3 | CSKH - Action | `d65ccb0e` | (root) | 1 | 3 |
| 4 | LỊCH HẸN | `55bccb0e` | (root) | 1 | 3 |
| 5 | Nhật kí chính | `250ccb0e` | (root) | 1 | 1 |
| 6 | Kê thuốc | `764ccb0e` | (root) | 1 | 3 |
| 7 | Chấm công | `14bccb0e` | (root) | 1 | 3 |
| 8 | Dịch vụ | `f7fccb0e` | (root) | 1 | 3 |
| 9 | Xét nghiệm | `ff5ccb0e` | (root) | 1 | 3 |
| 10 | lib 8 - thư viện báo cáo hằng ngày | `9aeccb0e` | (root) | 1 | 0 |
| 11 | lib 7 - thư viện mã điều khiển thống kê | `336ccb0e` | (root) | 1 | 3 |
| 12 | lib 6 - danh mục thuốc | `03accb0e` | (root) | 1 | 3 |
| 13 | lib 5 - kênh tiếp nhận | `49eccb0e` | (root) | 1 | 3 |
| 14 | lib 4 - Xét nghiệm & Cận lâm sàng | `638ccb0e` | (root) | 1 | 3 |
| 15 | lib 3 - danh sách nhân viên | `ad7ccb0e` | (root) | 1 | 3 |
| 16 | lib 2 - danh mục dịch vụ | `ad4ccb0e` | (root) | 1 | 3 |
| 17 | brigde 4.1 - lễ tân | `c37ccb0e` | bridge 4 - log and lock | 1 | 0 |
| 18 | bridge 4.2 - trực chat | `9e6ccb0e` | bridge 4 - log and lock | 1 | 0 |
| 19 | bridge 4.3 - cskh | `745ccb0e` | bridge 4 - log and lock | 1 | 0 |
| 20 | bridge 4.4 - file lâm sàng | `319ccb0e` | bridge 4 - log and lock | 1 | 3 |
| 21 | bridge 3 - Panel điều khiển thống kê | `07eccb0e` | (root) | 1 | 3 |
| 22 | bridge 2 - Master record ghi dữ liệu ngày khám | `26eccb0e` | (root) | 1 | 3 |
| 23 | bridge 1 - tự điền nhân viên buổi khám | `8acccb0e` | (root) | 1 | 3 |
| 24 | Phiếu đăng kí khám không theo hẹn | `ac5ccb0e` | (root) | 1 | 3 |
| 25 | output - tờ in đơn thuốc | `857ccb0e` | (root) | 1 | 3 |
| 26 | Video checkmark | `e63ccb0e` | (root) | 1 | 3 |
| 27 | Pathowiki | `c08ccb0e` | (root) | 1 | 0 |
| 28 | Microwiki | `1ccccb0e` | (root) | 1 | 1 |
| 29 | Sidewiki | `f00ccb0e` | (root) | 1 | 0 |
| 30 | Phiếu khám | `ce5ccb0e` | (root) | 1 | 3 |
| 31 | lib 1 - kịch bản cskh | `042ccb0e` | (root) | 1 | 3 |

## Cross-source relations
| Source DB | Data source | Property | Origin | → | Target | Sync type |
| --- | --- | --- | --- | --- | --- | --- |
| 🔑 File bệnh nhân (lâm sàng) | 🔑 File bệnh nhân (lâm sàng) | `//file phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| 🔑 File bệnh nhân (lâm sàng) | 🔑 File bệnh nhân (lâm sàng) | `File hành chính` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| 🔑 File khách hàng (hành chính) | 🔑 File khách hàng (hành chính) | `//file action` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| 🔑 File khách hàng (hành chính) | 🔑 File khách hàng (hành chính) | `//file lịch hẹn` | `page-only` | → | LỊCH HẸN | `back-side (name-match guess)` |
| 🔑 File khách hàng (hành chính) | 🔑 File khách hàng (hành chính) | `Nguồn khách` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| 🔑 File khách hàng (hành chính) | 🔑 File khách hàng (hành chính) | `Người nhà` | `schema` | → | 🔑 File khách hàng (hành chính) | `single_property` |
| 🔑 File khách hàng (hành chính) | 🔑 File khách hàng (hành chính) | `🔑 File lâm sàng` | `page-only` | → | bridge 4.4 - file lâm sàng | `back-side (name-match guess)` |
| CSKH - Action | CSKH - Action | `//file lịch hẹn` | `page-only` | → | LỊCH HẸN | `back-side (name-match guess)` |
| CSKH - Action | CSKH - Action | `//file phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| CSKH - Action | CSKH - Action | `//file xét nghiệm` | `page-only` | → | Xét nghiệm | `back-side (name-match guess)` |
| CSKH - Action | CSKH - Action | `//parent item` | `schema` | → | CSKH - Action | `dual_property` |
| CSKH - Action | CSKH - Action | `//sub-item` | `schema` | → | CSKH - Action | `dual_property` |
| CSKH - Action | CSKH - Action | `Kết quả thực hiện` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| CSKH - Action | CSKH - Action | `🔑 File khách hàng (hành chính)` | `page-only` | → | 🔑 File khách hàng (hành chính) | `back-side (name-match guess)` |
| LỊCH HẸN | LỊCH HẸN | `//bridge 3 - Panel điều khiển thống kê` | `page-only` | → | bridge 3 - Panel điều khiển thống kê | `back-side (name-match guess)` |
| LỊCH HẸN | LỊCH HẸN | `//file action` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| LỊCH HẸN | LỊCH HẸN | `//file phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| LỊCH HẸN | LỊCH HẸN | `🔑File hành chính` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Nhật kí chính | Nhật kí chính | `Nhân viên liên quan` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Kê thuốc | Kê thuốc | `//Masterpage - Thuốc` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Kê thuốc | Kê thuốc | `//bridge 3 - Panel điều khiển thống kê` | `page-only` | → | bridge 3 - Panel điều khiển thống kê | `back-side (name-match guess)` |
| Kê thuốc | Kê thuốc | `Phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| Kê thuốc | Kê thuốc | `Tên thuốc` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Chấm công | Chấm công | `//file Master record` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Chấm công | Chấm công | `//file common Master record` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Chấm công | Chấm công | `Nhân viên` | `page-only` | → | lib 3 - danh sách nhân viên | `back-side (name-match guess)` |
| Chấm công | Chấm công | `bridge 3 - Panel điều khiển thống kê` | `page-only` | → | bridge 3 - Panel điều khiển thống kê | `back-side (name-match guess)` |
| Dịch vụ | Dịch vụ | `//Người làm` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Dịch vụ | Dịch vụ | `//bridge 1 ` | `page-only` | → | bridge 1 - tự điền nhân viên buổi khám | `back-side (name-match guess)` |
| Dịch vụ | Dịch vụ | `//bridge 3 - trung tâm thống kê` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Dịch vụ | Dịch vụ | `CSDL bệnh nhân (lâm sàng)` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Dịch vụ | Dịch vụ | `Phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| Dịch vụ | Dịch vụ | `Tên dịch vụ` | `page-only` | → | Dịch vụ | `back-side (name-match guess)` |
| Dịch vụ | Dịch vụ | `📝 Tờ in kết quả` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Xét nghiệm | Xét nghiệm | `//bridge 3 - Panel điều khiển thống kê` | `page-only` | → | bridge 3 - Panel điều khiển thống kê | `back-side (name-match guess)` |
| Xét nghiệm | Xét nghiệm | `//file action` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Xét nghiệm | Xét nghiệm | `Phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| Xét nghiệm | Xét nghiệm | `Tên xét nghiệm` | `page-only` | → | Xét nghiệm | `back-side (name-match guess)` |
| Xét nghiệm | Xét nghiệm | `🔑 File bệnh nhân` | `page-only` | → | 🔑 File bệnh nhân (lâm sàng) | `back-side (name-match guess)` |
| lib 6 - danh mục thuốc | lib 6 - danh mục thuốc | `Parent item` | `schema` | → | lib 6 - danh mục thuốc | `dual_property` |
| lib 6 - danh mục thuốc | lib 6 - danh mục thuốc | `Sub-item` | `schema` | → | lib 6 - danh mục thuốc | `dual_property` |
| lib 3 - danh sách nhân viên | lib 3 - danh sách nhân viên | `Parent item` | `schema` | → | lib 3 - danh sách nhân viên | `dual_property` |
| lib 3 - danh sách nhân viên | lib 3 - danh sách nhân viên | `Sub-item` | `schema` | → | lib 3 - danh sách nhân viên | `dual_property` |
| bridge 3 - Panel điều khiển thống kê | bridge 3 - Panel điều khiển thống kê | `Nội dung Thống kê 1` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| bridge 3 - Panel điều khiển thống kê | bridge 3 - Panel điều khiển thống kê | `Nội dung thống kê 2` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| bridge 2 - Master record ghi dữ liệu ngày khám | bridge 2 - Master record ghi dữ liệu ngày khám | `Chấm công` | `page-only` | → | Chấm công | `back-side (name-match guess)` |
| bridge 2 - Master record ghi dữ liệu ngày khám | bridge 2 - Master record ghi dữ liệu ngày khám | `Parent item` | `schema` | → | bridge 2 - Master record ghi dữ liệu ngày khám | `dual_property` |
| bridge 2 - Master record ghi dữ liệu ngày khám | bridge 2 - Master record ghi dữ liệu ngày khám | `Phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| bridge 2 - Master record ghi dữ liệu ngày khám | bridge 2 - Master record ghi dữ liệu ngày khám | `Sub-item` | `schema` | → | bridge 2 - Master record ghi dữ liệu ngày khám | `dual_property` |
| bridge 1 - tự điền nhân viên buổi khám | bridge 1 - tự điền nhân viên buổi khám | `Nhân viên` | `page-only` | → | lib 3 - danh sách nhân viên | `back-side (name-match guess)` |
| bridge 1 - tự điền nhân viên buổi khám | bridge 1 - tự điền nhân viên buổi khám | `Parent item` | `schema` | → | bridge 1 - tự điền nhân viên buổi khám | `dual_property` |
| bridge 1 - tự điền nhân viên buổi khám | bridge 1 - tự điền nhân viên buổi khám | `Sub-item` | `schema` | → | bridge 1 - tự điền nhân viên buổi khám | `dual_property` |
| Phiếu đăng kí khám không theo hẹn | Phiếu đăng kí khám không theo hẹn | `🔑 File hành chính` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| output - tờ in đơn thuốc | output - tờ in đơn thuốc | `Phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| Video checkmark | Video checkmark | `Bệnh nhân` | `page-only` | → | 🔑 File bệnh nhân (lâm sàng) | `back-side (name-match guess)` |
| Video checkmark | Video checkmark | `Phiếu khám` | `page-only` | → | Phiếu khám | `back-side (name-match guess)` |
| Phiếu khám | Phiếu khám | `// file tờ đơn thuốc` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Phiếu khám | Phiếu khám | `//bridge 2 - Master record` | `page-only` | → | bridge 2 - Master record ghi dữ liệu ngày khám | `back-side (name-match guess)` |
| Phiếu khám | Phiếu khám | `//bridge 3 - Panel điều khiển thống kê` | `page-only` | → | bridge 3 - Panel điều khiển thống kê | `back-side (name-match guess)` |
| Phiếu khám | Phiếu khám | `//file action` | `page-only` | → | (unknown) | `back-side (forward dual_property)` |
| Phiếu khám | Phiếu khám | `//file dịch vụ ` | `page-only` | → | Dịch vụ | `back-side (name-match guess)` |
| Phiếu khám | Phiếu khám | `//file kê thuốc` | `page-only` | → | Kê thuốc | `back-side (name-match guess)` |
| Phiếu khám | Phiếu khám | `//file lịch hẹn` | `page-only` | → | LỊCH HẸN | `back-side (name-match guess)` |
| Phiếu khám | Phiếu khám | `//file xét nghiệm` | `page-only` | → | Xét nghiệm | `back-side (name-match guess)` |
| Phiếu khám | Phiếu khám | `🔑 file lâm sàng` | `page-only` | → | bridge 4.4 - file lâm sàng | `back-side (name-match guess)` |

## Per-database schemas

### 🔑 File bệnh nhân (lâm sàng)
- DB ID: `ac6ccb0e-ac88-83a2-bd04-0136bd0e1936`
- Parent path: (root)

#### Data source · 🔑 File bệnh nhân (lâm sàng)
- Data source ID: `ad3ccb0e-ac88-83f8-ac49-0746cf7c7e7c`
- Property count: **11** (schema: 8, page-only: 3)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `*ID` | `unique_id` | `schema` |  |
| `//file phiếu khám` | `relation` | `page-only` | → unknown target |
| `//log` | `rich_text` | `schema` |  |
| `Created time` | `created_time` | `schema` |  |
| `Dự kiến sinh` | `date` | `schema` |  |
| `File hành chính` | `relation` | `page-only` | → unknown target |
| `Họ tên` | `title` | `schema` |  |
| `Link drive` | `url` | `schema` |  |
| `Loại dịch vụ khám` | `rollup` | `page-only` | (back-side; see sample rows) |
| `Tuổi thai` | `formula` | `schema` | formula: `let(GAw,
  floor((280 - dateBetween({{notion:block_property:…` |
| `Tóm tắt thông tin` | `formula` | `schema` | formula: `/*📌Thông tin chung*/
	/*Loại dịch vụ khám - tuổi thai và EDD…` |

**Sample rows (PII-redacted)**

**Sample 1** (page `e54ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 6505
  - `//file phiếu khám`: <rel→0 page(s)>
  - `//log`: @A…(10 chars)
  - `Created time`: 2026-**-**
  - `Dự kiến sinh`: ∅
  - `File hành chính`: <rel→0 page(s)>
  - `Họ tên`: L…(12 chars)
  - `Link drive`: ∅
  - `Loại dịch vụ khám`: <rollup:array>
  - `Tuổi thai`: ∅
  - `Tóm tắt thông tin`: ∅

**Sample 2** (page `72cccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 6504
  - `//file phiếu khám`: <rel→0 page(s)>
  - `//log`: @A…(10 chars)
  - `Created time`: 2026-**-**
  - `Dự kiến sinh`: ∅
  - `File hành chính`: <rel→0 page(s)>
  - `Họ tên`: ''
  - `Link drive`: ∅
  - `Loại dịch vụ khám`: <rollup:array>
  - `Tuổi thai`: ∅
  - `Tóm tắt thông tin`: ∅

**Sample 3** (page `b78ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 6503
  - `//file phiếu khám`: <rel→0 page(s)>
  - `//log`: @A…(10 chars)
  - `Created time`: 2026-**-**
  - `Dự kiến sinh`: ∅
  - `File hành chính`: <rel→0 page(s)>
  - `Họ tên`: Đ…(22 chars)
  - `Link drive`: ∅
  - `Loại dịch vụ khám`: <rollup:array>
  - `Tuổi thai`: ∅
  - `Tóm tắt thông tin`: ∅

### 🔑 File khách hàng (hành chính)
- DB ID: `43dccb0e-ac88-8209-97ae-012408d8efce`
- Parent path: (root)

#### Data source · 🔑 File khách hàng (hành chính)
- Data source ID: `f6bccb0e-ac88-8333-8d20-07cc963a6889`
- Property count: **27** (schema: 23, page-only: 4)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `*ID` | `unique_id` | `schema` |  |
| `//assigned` | `formula` | `schema` | formula: `{{notion:block_property:dLGG:f6bccb0e-ac88-8333-8d20-07cc963…` |
| `//file action` | `relation` | `page-only` | → unknown target |
| `//file lịch hẹn` | `relation` | `page-only` | → unknown target |
| `//họ tên (neat)` | `formula` | `schema` | formula: `replaceAll({{notion:block_property:title:f6bccb0e-ac88-8333-…` |
| `//sdt (neat)` | `formula` | `schema` | formula: `if(replaceAll({{notion:block_property:title:f6bccb0e-ac88-83…` |
| `//stat manipulate` | `formula` | `schema` | formula: `2026-year({{notion:block_property:VKwD:f6bccb0e-ac88-8333-8d…` |
| `//stat manipulate 2` | `formula` | `schema` | formula: `{{notion:block_property:LRg%7B:f6bccb0e-ac88-8333-8d20-07cc9…` |
| `Created by` | `created_by` | `schema` |  |
| `Created time` | `created_time` | `schema` |  |
| `Công việc` | `formula` | `schema` | formula: `{{notion:block_property:V%7DDY:f6bccb0e-ac88-8333-8d20-07cc9…` |
| `Email` | `email` | `schema` |  |
| `Giới tính` | `select` | `schema` | options: `Nam`, `Nữ` |
| `Last edited by` | `last_edited_by` | `schema` |  |
| `Last edited time` | `last_edited_time` | `schema` |  |
| `Lịch nhắc việc` | `formula` | `schema` | formula: `{{notion:block_property:V%7DDY:f6bccb0e-ac88-8333-8d20-07cc9…` |
| `Name` | `title` | `schema` |  |
| `Nguồn khách` | `relation` | `page-only` | → unknown target |
| `Ngày sinh` | `date` | `schema` |  |
| `Người nhà` | `relation` | `schema` | → `f6bccb0e` (single_property) |
| `Phân loại khách` | `multi_select` | `schema` | options: `😊 ✚✚`, `💲 ✚✚`, `📖 ✚✚`, `😡 ––`, `💲 ––`, `🕮 ––` |
| `Tóm tắt thông tin` | `formula` | `schema` | formula: `{{notion:block_property:LRg%7B:f6bccb0e-ac88-8333-8d20-07cc9…` |
| `Đang nhận action` | `formula` | `schema` | formula: `

/*Lọc request chưa hoàn thành => người khởi tạo các action…` |
| `Địa chỉ` | `place` | `schema` |  |
| `Ưu tiên` | `select` | `schema` | options: `0 - Thường`, `1 - Lượt khám ♦️`, `2 - Giảm giá ♦️`, `3 - Miễn phí ♦️♦️` |
| `📌GHI CHÚ VĨNH VIỄN` | `rich_text` | `schema` |  |
| `🔑 File lâm sàng` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `ba9ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 6403
  - `//assigned`: <string>
  - `//file action`: <rel→0 page(s)>
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//họ tên (neat)`: <string>
  - `//sdt (neat)`: <string>
  - `//stat manipulate`: 47
  - `//stat manipulate 2`: 0
  - `Created by`: <user>
  - `Created time`: 2026-**-**
  - `Công việc`: <string>
  - `Email`: ∅
  - `Giới tính`: Nữ
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Lịch nhắc việc`: ∅
  - `Name`: P…(23 chars)
  - `Nguồn khách`: <rel→0 page(s)>
  - `Ngày sinh`: 1979-**-**
  - `Người nhà`: <rel→1 page(s)>
  - `Phân loại khách`: []
  - `Tóm tắt thông tin`: ∅
  - `Đang nhận action`: ∅
  - `Địa chỉ`: <place>
  - `Ưu tiên`: 0 - Thường
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 File lâm sàng`: <rel→0 page(s)>

**Sample 2** (page `a33ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 6402
  - `//assigned`: <string>
  - `//file action`: <rel→0 page(s)>
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//họ tên (neat)`: <string>
  - `//sdt (neat)`: <string>
  - `//stat manipulate`: 26
  - `//stat manipulate 2`: 0
  - `Created by`: <user>
  - `Created time`: 2026-**-**
  - `Công việc`: <string>
  - `Email`: ∅
  - `Giới tính`: Nữ
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Lịch nhắc việc`: ∅
  - `Name`: H…(25 chars)
  - `Nguồn khách`: <rel→0 page(s)>
  - `Ngày sinh`: 2000-**-**
  - `Người nhà`: <rel→0 page(s)>
  - `Phân loại khách`: []
  - `Tóm tắt thông tin`: ∅
  - `Đang nhận action`: ∅
  - `Địa chỉ`: <place>
  - `Ưu tiên`: 0 - Thường
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 File lâm sàng`: <rel→0 page(s)>

**Sample 3** (page `fd9ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 6401
  - `//assigned`: <string>
  - `//file action`: <rel→0 page(s)>
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//họ tên (neat)`: <string>
  - `//sdt (neat)`: <string>
  - `//stat manipulate`: 43
  - `//stat manipulate 2`: 0
  - `Created by`: <user>
  - `Created time`: 2026-**-**
  - `Công việc`: <string>
  - `Email`: ∅
  - `Giới tính`: Nữ
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Lịch nhắc việc`: ∅
  - `Name`: H…(25 chars)
  - `Nguồn khách`: <rel→0 page(s)>
  - `Ngày sinh`: 1983-**-**
  - `Người nhà`: <rel→2 page(s)>
  - `Phân loại khách`: []
  - `Tóm tắt thông tin`: ∅
  - `Đang nhận action`: ∅
  - `Địa chỉ`: <place>
  - `Ưu tiên`: 0 - Thường
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 File lâm sàng`: <rel→0 page(s)>

### CSKH - Action
- DB ID: `d65ccb0e-ac88-8389-86bc-817785a43a03`
- Parent path: (root)

#### Data source · CSKH - Action
- Data source ID: `db7ccb0e-ac88-83d7-a642-876bcd70eab0`
- Property count: **25** (schema: 19, page-only: 6)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `//ID` | `unique_id` | `schema` |  |
| `//file lịch hẹn` | `relation` | `page-only` | → unknown target |
| `//file phiếu khám` | `relation` | `page-only` | → unknown target |
| `//file xét nghiệm` | `relation` | `page-only` | → unknown target |
| `//parent item` | `relation` | `schema` | → `db7ccb0e` (dual_property) |
| `//self deadline` | `formula` | `schema` | formula: `if({{notion:block_property:K%5DZr:db7ccb0e-ac88-83d7-a642-87…` |
| `//sub-item` | `relation` | `schema` | → `db7ccb0e` (dual_property) |
| `>>Check 1` | `formula` | `schema` | formula: `let(theday,{{notion:block_property:mZUW:db7ccb0e-ac88-83d7-a…` |
| `>>Check 2` | `formula` | `schema` | formula: `/*lich hen*/
if({{notion:block_property:mZUW:db7ccb0e-ac88-8…` |
| `Created by` | `created_by` | `schema` |  |
| `Deadline` | `formula` | `schema` | formula: `
	[{{notion:block_property:mZUW:db7ccb0e-ac88-83d7-a642-876b…` |
| `Dữ liệu thao tác` | `formula` | `schema` | formula: `if({{notion:block_property:mZUW:db7ccb0e-ac88-83d7-a642-876b…` |
| `Giờ khởi tạo` | `created_time` | `schema` |  |
| `Kết quả thực hiện` | `relation` | `page-only` | → unknown target |
| `Last edited by` | `last_edited_by` | `schema` |  |
| `Last edited time` | `last_edited_time` | `schema` |  |
| `Mô tả chi tiết` | `rich_text` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Phân loại` | `formula` | `schema` | formula: `let(q,{{notion:block_property:JhS%60:db7ccb0e-ac88-83d7-a642…` |
| `Step` | `rollup` | `page-only` | (back-side; see sample rows) |
| `Tag tính tiền` | `formula` | `schema` | formula: `{{notion:block_property:JhS%60:db7ccb0e-ac88-83d7-a642-876bc…` |
| `Tình trạng` | `formula` | `schema` | formula: `/* KIỂM SOÁT LỖI */
/*---Lỗi thiếu file lịch hẹn*/
if(and({{…` |
| `Tự tạo deadline` | `date` | `schema` |  |
| `Điểm đánh giá` | `select` | `schema` | options: `+2`, `+1`, `0`, `-1`, `-2` |
| `🔑 File khách hàng (hành chính)` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `213ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//ID`: 34866
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//file phiếu khám`: <rel→0 page(s)>
  - `//file xét nghiệm`: <rel→0 page(s)>
  - `//parent item`: <rel→1 page(s)>
  - `//self deadline`: ∅
  - `//sub-item`: <rel→0 page(s)>
  - `>>Check 1`: <string>
  - `>>Check 2`: ∅
  - `Created by`: <user>
  - `Deadline`: ∅
  - `Dữ liệu thao tác`: <string>
  - `Giờ khởi tạo`: 2026-**-**
  - `Kết quả thực hiện`: <rel→0 page(s)>
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Mô tả chi tiết`: ''
  - `Name`: ©…(7 chars)
  - `Phân loại`: <string>
  - `Step`: <rollup:array>
  - `Tag tính tiền`: <string>
  - `Tình trạng`: <string>
  - `Tự tạo deadline`: ∅
  - `Điểm đánh giá`: ∅
  - `🔑 File khách hàng (hành chính)`: <rel→0 page(s)>

**Sample 2** (page `136ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//ID`: 34865
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//file phiếu khám`: <rel→0 page(s)>
  - `//file xét nghiệm`: <rel→0 page(s)>
  - `//parent item`: <rel→0 page(s)>
  - `//self deadline`: ∅
  - `//sub-item`: <rel→0 page(s)>
  - `>>Check 1`: <string>
  - `>>Check 2`: ∅
  - `Created by`: <user>
  - `Deadline`: ∅
  - `Dữ liệu thao tác`: <string>
  - `Giờ khởi tạo`: 2026-**-**
  - `Kết quả thực hiện`: <rel→0 page(s)>
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Mô tả chi tiết`: ''
  - `Name`: #…(9 chars)
  - `Phân loại`: <string>
  - `Step`: <rollup:array>
  - `Tag tính tiền`: <string>
  - `Tình trạng`: <string>
  - `Tự tạo deadline`: ∅
  - `Điểm đánh giá`: ∅
  - `🔑 File khách hàng (hành chính)`: <rel→0 page(s)>

**Sample 3** (page `534ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//ID`: 34864
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//file phiếu khám`: <rel→0 page(s)>
  - `//file xét nghiệm`: <rel→0 page(s)>
  - `//parent item`: <rel→1 page(s)>
  - `//self deadline`: ∅
  - `//sub-item`: <rel→0 page(s)>
  - `>>Check 1`: <string>
  - `>>Check 2`: ∅
  - `Created by`: <user>
  - `Deadline`: ∅
  - `Dữ liệu thao tác`: <string>
  - `Giờ khởi tạo`: 2026-**-**
  - `Kết quả thực hiện`: <rel→0 page(s)>
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Mô tả chi tiết`: ''
  - `Name`: ©…(7 chars)
  - `Phân loại`: <string>
  - `Step`: <rollup:array>
  - `Tag tính tiền`: <string>
  - `Tình trạng`: <string>
  - `Tự tạo deadline`: ∅
  - `Điểm đánh giá`: ∅
  - `🔑 File khách hàng (hành chính)`: <rel→0 page(s)>

### LỊCH HẸN
- DB ID: `55bccb0e-ac88-8217-8365-8198151b2374`
- Parent path: (root)

#### Data source · LỊCH HẸN
- Data source ID: `d1eccb0e-ac88-820e-bae1-87f9270ea036`
- Description: Tình trạng CSKH total
[Reg + Số]  + cột STT không trống + Tình trạng: Đã xác nhận lịch hẹn ⇒ BN đã đặt lịch
[Reg + Số] + Tình trạng: Hủy lịch ⇒ BN đã đặt nhưng hủy
[Reg ] + Cột STT trống + Tình trạng: chờ xác nhận lịch hẹn ⇒ BN có dự kiến tái khám nhưng chưa được liên hệ hẹn
[Reg ] + Cột STT trống + Tình trạng: Hủy lịch ⇒ BN có dự kiến tái khám, CSKH đã gọi nhưng chưa được liên hệ hẹn
- Property count: **23** (schema: 19, page-only: 4)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `//bridge 3 - Panel điều khiển thống kê` | `relation` | `page-only` | → unknown target |
| `//file action` | `relation` | `page-only` | → unknown target |
| `//file phiếu khám` | `relation` | `page-only` | → unknown target |
| `>>Thống kê 1` | `formula` | `schema` | formula: `` |
| `>>Thống kê 2` | `formula` | `schema` | formula: `` |
| `Bác sĩ` | `select` | `schema` | options: `BS Thành`, `BS Vân`, `BS Hằng`, `BS Thủy`, `BS Linh nam khoa`, `BS Đào`, `BS Hùng`, `BS Nam`, `BS Thiệp`, `BS Quyết` |
| `Check in` | `button` | `schema` |  |
| `Created by ` | `created_by` | `schema` |  |
| `Created time` | `created_time` | `schema` |  |
| `Ghi chú` | `formula` | `schema` | formula: `{{notion:block_property:LZgy:d1eccb0e-ac88-820e-bae1-87f9270…` |
| `ID` | `unique_id` | `schema` |  |
| `Last edited by` | `last_edited_by` | `schema` |  |
| `Last edited time` | `last_edited_time` | `schema` |  |
| `Loại dịch vụ khám` | `select` | `schema` | options: `Sản 1`, `Sản 2`, `Sản 3`, `NPĐH`, `Hồ sơ sinh`, `Tiền hôn nhân`, `Hiếm muộn`, `Nội tiết - Tình dục`, `Phụ khoa`, `Nam khoa`, `Tư vấn chuyên sâu`, `***#Thủ thuật` (+2 more) |
| `Name` | `title` | `schema` |  |
| `Ngày giờ hẹn` | `date` | `schema` |  |
| `Phòng khám` | `select` | `schema` | options: `Kim Ngưu`, `Hào Nam`, `Bệnh viện` |
| `Số thứ tự` | `rich_text` | `schema` |  |
| `Tag giờ hẹn` | `formula` | `schema` | formula: `(if({{notion:block_property:pf~k:d1eccb0e-ac88-820e-bae1-87f…` |
| `Tình trạng CSKH` | `formula` | `schema` | formula: `/*
Danh sách tình trạng phiếu hẹn
//Check điều kiện
//Ngày …` |
| `Tình trạng khách đến` | `formula` | `schema` | formula: `/*
Danh sách tình trạng phiếu hẹn
//Check điều kiện
//Ngày …` |
| `Tóm tắt bệnh nhân` | `formula` | `schema` | formula: `/*Địa chỉ*/
{{notion:block_property:atvQ:d1eccb0e-ac88-820e-…` |
| `🔑File hành chính` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `d57ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//file phiếu khám`: <rel→0 page(s)>
  - `>>Thống kê 1`: ∅
  - `>>Thống kê 2`: ∅
  - `Bác sĩ`: BS Hùng
  - `Check in`: <button>
  - `Created by `: <user>
  - `Created time`: 2026-**-**
  - `Ghi chú`: <string>
  - `ID`: 11014
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Loại dịch vụ khám`: ***#Thủ thuật
  - `Name`: […(40 chars)
  - `Ngày giờ hẹn`: 2026-**-**
  - `Phòng khám`: Kim Ngưu
  - `Số thứ tự`: Bơ…(7 chars)
  - `Tag giờ hẹn`: <string>
  - `Tình trạng CSKH`: <string>
  - `Tình trạng khách đến`: <string>
  - `Tóm tắt bệnh nhân`: <string>
  - `🔑File hành chính`: <rel→0 page(s)>

**Sample 2** (page `39eccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//file phiếu khám`: <rel→0 page(s)>
  - `>>Thống kê 1`: ∅
  - `>>Thống kê 2`: ∅
  - `Bác sĩ`: BS Hằng
  - `Check in`: <button>
  - `Created by `: <user>
  - `Created time`: 2026-**-**
  - `Ghi chú`: <string>
  - `ID`: 11013
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Loại dịch vụ khám`: Phụ khoa
  - `Name`: […(32 chars)
  - `Ngày giờ hẹn`: 2026-**-**
  - `Phòng khám`: Kim Ngưu
  - `Số thứ tự`: 14…(2 chars)
  - `Tag giờ hẹn`: <string>
  - `Tình trạng CSKH`: <string>
  - `Tình trạng khách đến`: <string>
  - `Tóm tắt bệnh nhân`: <string>
  - `🔑File hành chính`: <rel→0 page(s)>

**Sample 3** (page `f26ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//file phiếu khám`: <rel→0 page(s)>
  - `>>Thống kê 1`: ∅
  - `>>Thống kê 2`: ∅
  - `Bác sĩ`: BS Hằng
  - `Check in`: <button>
  - `Created by `: <user>
  - `Created time`: 2026-**-**
  - `Ghi chú`: <string>
  - `ID`: 11012
  - `Last edited by`: <user>
  - `Last edited time`: 2026-**-**
  - `Loại dịch vụ khám`: Phụ khoa
  - `Name`: […(38 chars)
  - `Ngày giờ hẹn`: 2026-**-**
  - `Phòng khám`: Kim Ngưu
  - `Số thứ tự`: 13…(2 chars)
  - `Tag giờ hẹn`: <string>
  - `Tình trạng CSKH`: <string>
  - `Tình trạng khách đến`: <string>
  - `Tóm tắt bệnh nhân`: <string>
  - `🔑File hành chính`: <rel→0 page(s)>

### Nhật kí chính
- DB ID: `250ccb0e-ac88-82e7-b01b-814002483bcc`
- Parent path: (root)

#### Data source · Nhật kí chính
- Data source ID: `9c2ccb0e-ac88-830e-9708-87f13c3c054a`
- Property count: **6** (schema: 5, page-only: 1)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `ID` | `unique_id` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Ngày ghi nhận` | `created_time` | `schema` |  |
| `Nhân viên liên quan` | `relation` | `page-only` | → unknown target |
| `Nội dung ` | `rich_text` | `schema` |  |
| `Phân loại` | `select` | `schema` | options: `Lỗi nhân viên`, `Vấn đề với khách`, `Lỗi vận hành - kĩ thuật`, `Báo cáo buổi khám` |

**Sample rows (PII-redacted)**

**Sample 1** (page `4a6ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `ID`: 1
  - `Name`: D…(7 chars)
  - `Ngày ghi nhận`: 2026-**-**
  - `Nhân viên liên quan`: <rel→0 page(s)>
  - `Nội dung `: ''
  - `Phân loại`: ∅

### Kê thuốc
- DB ID: `764ccb0e-ac88-83cc-ae33-0150c1edae51`
- Parent path: (root)

#### Data source · Kê thuốc
- Data source ID: `75accb0e-ac88-82b0-abed-879adedf8e78`
- Property count: **14** (schema: 10, page-only: 4)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `*ID` | `unique_id` | `schema` |  |
| `//Masterpage - Thuốc` | `relation` | `page-only` | → unknown target |
| `//bridge 3 - Panel điều khiển thống kê` | `relation` | `page-only` | → unknown target |
| `//chuẩn form` | `formula` | `schema` | formula: `{{notion:block_property:PUHT:75accb0e-ac88-82b0-abed-879aded…` |
| `>> Thống kê 1` | `formula` | `schema` | formula: `` |
| `>> Thống kê 2` | `formula` | `schema` | formula: `` |
| `Button` | `button` | `schema` |  |
| `Ghi chú số lượng` | `rich_text` | `schema` |  |
| `Hướng dẫn dùng` | `rich_text` | `schema` |  |
| `Lưu ý` | `rich_text` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Phiếu khám` | `relation` | `page-only` | → unknown target |
| `Số lượng` | `rich_text` | `schema` |  |
| `Tên thuốc` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `42fccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 17452
  - `//Masterpage - Thuốc`: <rel→0 page(s)>
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//chuẩn form`: <string>
  - `>> Thống kê 1`: ∅
  - `>> Thống kê 2`: ∅
  - `Button`: <button>
  - `Ghi chú số lượng`: ''
  - `Hướng dẫn dùng`: Tu…(32 chars)
  - `Lưu ý`: ''
  - `Name`: R…(8 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Số lượng`: ''
  - `Tên thuốc`: <rel→0 page(s)>

**Sample 2** (page `03dccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 17451
  - `//Masterpage - Thuốc`: <rel→0 page(s)>
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//chuẩn form`: <string>
  - `>> Thống kê 1`: ∅
  - `>> Thống kê 2`: ∅
  - `Button`: <button>
  - `Ghi chú số lượng`: ''
  - `Hướng dẫn dùng`: Đặ…(54 chars)
  - `Lưu ý`: ''
  - `Name`: R…(8 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Số lượng`: ''
  - `Tên thuốc`: <rel→0 page(s)>

**Sample 3** (page `e6eccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 17450
  - `//Masterpage - Thuốc`: <rel→0 page(s)>
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//chuẩn form`: <string>
  - `>> Thống kê 1`: ∅
  - `>> Thống kê 2`: ∅
  - `Button`: <button>
  - `Ghi chú số lượng`: ''
  - `Hướng dẫn dùng`: Ng…(132 chars)
  - `Lưu ý`: ''
  - `Name`: R…(8 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Số lượng`: ''
  - `Tên thuốc`: <rel→0 page(s)>

### Chấm công
- DB ID: `14bccb0e-ac88-82f6-bdc6-01fa14c50216`
- Parent path: (root)

#### Data source · Chấm công
- Data source ID: `6b7ccb0e-ac88-82f9-bba1-0732c418c0ab`
- Property count: **21** (schema: 17, page-only: 4)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `//file Master record` | `relation` | `page-only` | → unknown target |
| `//file common Master record` | `relation` | `page-only` | → unknown target |
| `>> Thống kê 1` | `formula` | `schema` | formula: `` |
| `>> Thống kê 2` | `formula` | `schema` | formula: `` |
| `Ghi chú` | `rich_text` | `schema` |  |
| `Giờ kết thúc dịch vụ` | `formula` | `schema` | formula: `if({{notion:block_property:v%3DyM:6b7ccb0e-ac88-82f9-bba1-07…` |
| `Giờ ra` | `date` | `schema` |  |
| `Giờ vào` | `date` | `schema` |  |
| `ID` | `unique_id` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Ngày làm` | `date` | `schema` |  |
| `Nhân viên` | `relation` | `page-only` | → unknown target |
| `Phòng khám` | `select` | `schema` | options: `Hào Nam`, `Kim Ngưu` |
| `Ra về` | `button` | `schema` |  |
| `Số block công (15p/block)` | `formula` | `schema` | formula: `((dateBetween({{notion:block_property:ADj%40:6b7ccb0e-ac88-8…` |
| `Số bệnh nhân phục vụ` | `formula` | `schema` | formula: `if({{notion:block_property:v%3DyM:6b7ccb0e-ac88-82f9-bba1-07…` |
| `Số chỉ định` | `formula` | `schema` | formula: `	{{notion:block_property:eRXP:6b7ccb0e-ac88-82f9-bba1-0732c4…` |
| `Tình trạng` | `formula` | `schema` | formula: `let(inout, ("in " + if({{notion:block_property:q%3Ek%40:6b7c…` |
| `Vào làm` | `button` | `schema` |  |
| `Vị trí làm việc` | `multi_select` | `schema` | options: `*Lễ tân`, `*Thu ngân`, `Siêu âm`, `Khám - Phụ khám`, `Monitor`, `Thuốc*`, `Tư vấn - Trợ lý`, `Kiểm soát chất lượng` |
| `bridge 3 - Panel điều khiển thống kê` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `a57ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//file Master record`: <rel→0 page(s)>
  - `//file common Master record`: <rel→0 page(s)>
  - `>> Thống kê 1`: ∅
  - `>> Thống kê 2`: ∅
  - `Ghi chú`: ''
  - `Giờ kết thúc dịch vụ`: ∅
  - `Giờ ra`: ∅
  - `Giờ vào`: ∅
  - `ID`: 549
  - `Name`: Đ…(18 chars)
  - `Ngày làm`: 2026-**-**
  - `Nhân viên`: <rel→0 page(s)>
  - `Phòng khám`: Kim Ngưu
  - `Ra về`: <button>
  - `Số block công (15p/block)`: ∅
  - `Số bệnh nhân phục vụ`: 0
  - `Số chỉ định`: 0
  - `Tình trạng`: <string>
  - `Vào làm`: <button>
  - `Vị trí làm việc`: [Thuốc*]
  - `bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>

**Sample 2** (page `807ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//file Master record`: <rel→0 page(s)>
  - `//file common Master record`: <rel→0 page(s)>
  - `>> Thống kê 1`: ∅
  - `>> Thống kê 2`: ∅
  - `Ghi chú`: ch…(5 chars)
  - `Giờ kết thúc dịch vụ`: ∅
  - `Giờ ra`: ∅
  - `Giờ vào`: ∅
  - `ID`: 548
  - `Name`: Đ…(24 chars)
  - `Ngày làm`: 2026-**-**
  - `Nhân viên`: <rel→0 page(s)>
  - `Phòng khám`: Kim Ngưu
  - `Ra về`: <button>
  - `Số block công (15p/block)`: ∅
  - `Số bệnh nhân phục vụ`: 0
  - `Số chỉ định`: 0
  - `Tình trạng`: <string>
  - `Vào làm`: <button>
  - `Vị trí làm việc`: [Siêu âm]
  - `bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>

**Sample 3** (page `ce2ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//file Master record`: <rel→0 page(s)>
  - `//file common Master record`: <rel→0 page(s)>
  - `>> Thống kê 1`: ∅
  - `>> Thống kê 2`: ∅
  - `Ghi chú`: ''
  - `Giờ kết thúc dịch vụ`: ∅
  - `Giờ ra`: ∅
  - `Giờ vào`: ∅
  - `ID`: 547
  - `Name`: Đ…(17 chars)
  - `Ngày làm`: 2026-**-**
  - `Nhân viên`: <rel→0 page(s)>
  - `Phòng khám`: Kim Ngưu
  - `Ra về`: <button>
  - `Số block công (15p/block)`: ∅
  - `Số bệnh nhân phục vụ`: 0
  - `Số chỉ định`: 0
  - `Tình trạng`: <string>
  - `Vào làm`: <button>
  - `Vị trí làm việc`: [Siêu âm]
  - `bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>

### Dịch vụ
- DB ID: `f7fccb0e-ac88-83d9-b379-013890a0089a`
- Parent path: (root)

#### Data source · Dịch vụ
- Data source ID: `bc9ccb0e-ac88-8216-a963-0724267d3f51`
- Property count: **21** (schema: 14, page-only: 7)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `//Giờ bắt đầu` | `date` | `schema` |  |
| `//Giờ kết thúc` | `date` | `schema` |  |
| `//Người làm` | `relation` | `page-only` | → unknown target |
| `//bridge 1 ` | `relation` | `page-only` | → unknown target |
| `//bridge 3 - trung tâm thống kê` | `relation` | `page-only` | → unknown target |
| `//created by` | `created_by` | `schema` |  |
| `//status light` | `formula` | `schema` | formula: `ifs(
	{{notion:block_property:fs%3Cn:bc9ccb0e-ac88-8216-a963…` |
| `>> Thống kê 1` | `formula` | `schema` | formula: `let(code, {{notion:block_property:eLrV:bc9ccb0e-ac88-8216-a9…` |
| `>>Thống kê 2` | `formula` | `schema` | formula: `` |
| `Bắt đầu` | `button` | `schema` |  |
| `CSDL bệnh nhân (lâm sàng)` | `relation` | `page-only` | → unknown target |
| `Giờ chỉ định` | `created_time` | `schema` |  |
| `ID` | `unique_id` | `schema` |  |
| `Kết quả` | `formula` | `schema` | formula: ` if({{notion:block_property:x%60%3D%3E:bc9ccb0e-ac88-8216-a9…` |
| `Kết thúc` | `button` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Phiếu khám` | `relation` | `page-only` | → unknown target |
| `Tên dịch vụ` | `relation` | `page-only` | → unknown target |
| `Tình trạng` | `formula` | `schema` | formula: `if(dateBetween(today(),{{notion:block_property:OQxV:bc9ccb0e…` |
| `Tạo tờ in` | `button` | `schema` |  |
| `📝 Tờ in kết quả` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `e7accb0e`, created 2026-**-**, edited 2026-**-**)
  - `//Giờ bắt đầu`: 2026-**-**
  - `//Giờ kết thúc`: 2026-**-**
  - `//Người làm`: <rel→0 page(s)>
  - `//bridge 1 `: <rel→0 page(s)>
  - `//bridge 3 - trung tâm thống kê`: <rel→0 page(s)>
  - `//created by`: <user>
  - `//status light`: <string>
  - `>> Thống kê 1`: <string>
  - `>>Thống kê 2`: ∅
  - `Bắt đầu`: <button>
  - `CSDL bệnh nhân (lâm sàng)`: <rel→0 page(s)>
  - `Giờ chỉ định`: 2026-**-**
  - `ID`: 16786
  - `Kết quả`: <string>
  - `Kết thúc`: <button>
  - `Name`: S…(13 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Tên dịch vụ`: <rel→0 page(s)>
  - `Tình trạng`: <string>
  - `Tạo tờ in`: <button>
  - `📝 Tờ in kết quả`: <rel→0 page(s)>

**Sample 2** (page `542ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//Giờ bắt đầu`: 2026-**-**
  - `//Giờ kết thúc`: 2026-**-**
  - `//Người làm`: <rel→0 page(s)>
  - `//bridge 1 `: <rel→0 page(s)>
  - `//bridge 3 - trung tâm thống kê`: <rel→0 page(s)>
  - `//created by`: <user>
  - `//status light`: <string>
  - `>> Thống kê 1`: <string>
  - `>>Thống kê 2`: ∅
  - `Bắt đầu`: <button>
  - `CSDL bệnh nhân (lâm sàng)`: <rel→0 page(s)>
  - `Giờ chỉ định`: 2026-**-**
  - `ID`: 16785
  - `Kết quả`: <string>
  - `Kết thúc`: <button>
  - `Name`: S…(13 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Tên dịch vụ`: <rel→0 page(s)>
  - `Tình trạng`: <string>
  - `Tạo tờ in`: <button>
  - `📝 Tờ in kết quả`: <rel→0 page(s)>

**Sample 3** (page `65dccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//Giờ bắt đầu`: 2026-**-**
  - `//Giờ kết thúc`: 2026-**-**
  - `//Người làm`: <rel→0 page(s)>
  - `//bridge 1 `: <rel→0 page(s)>
  - `//bridge 3 - trung tâm thống kê`: <rel→0 page(s)>
  - `//created by`: <user>
  - `//status light`: <string>
  - `>> Thống kê 1`: <string>
  - `>>Thống kê 2`: ∅
  - `Bắt đầu`: <button>
  - `CSDL bệnh nhân (lâm sàng)`: <rel→0 page(s)>
  - `Giờ chỉ định`: 2026-**-**
  - `ID`: 16796
  - `Kết quả`: <string>
  - `Kết thúc`: <button>
  - `Name`: S…(13 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Tên dịch vụ`: <rel→0 page(s)>
  - `Tình trạng`: <string>
  - `Tạo tờ in`: <button>
  - `📝 Tờ in kết quả`: <rel→0 page(s)>

### Xét nghiệm
- DB ID: `ff5ccb0e-ac88-8208-9af2-01c59d622b10`
- Parent path: (root)

#### Data source · Xét nghiệm
- Data source ID: `fe7ccb0e-ac88-83eb-8e9e-073c802bcd03`
- Property count: **20** (schema: 15, page-only: 5)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `*ID` | `unique_id` | `schema` |  |
| `//bridge 3 - Panel điều khiển thống kê` | `relation` | `page-only` | → unknown target |
| `//file action` | `relation` | `page-only` | → unknown target |
| `//mã xét nghiệm` | `formula` | `schema` | formula: `("["+({{notion:block_property:p%5DZI:fe7ccb0e-ac88-83eb-8e9e…` |
| `//ngày up notion` | `date` | `schema` |  |
| `Created by` | `created_by` | `schema` |  |
| `Created time` | `created_time` | `schema` |  |
| `Files kết quả` | `files` | `schema` |  |
| `Kết quả` | `rich_text` | `schema` |  |
| `Kết quả AI` | `rich_text` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Ngày có kết quả (dự kiến)` | `formula` | `schema` | formula: `(dateAdd({{notion:block_property:created_time}},{{notion:blo…` |
| `Người làm` | `formula` | `schema` | formula: `{{notion:block_property:WjzM:fe7ccb0e-ac88-83eb-8e9e-073c802…` |
| `Phiếu khám` | `relation` | `page-only` | → unknown target |
| `Phân loại xét nghiệm` | `formula` | `schema` | formula: `{{notion:block_property:p%5DZI:fe7ccb0e-ac88-83eb-8e9e-073c8…` |
| `Trợ lý ghi chú` | `rich_text` | `schema` |  |
| `Tên xét nghiệm` | `relation` | `page-only` | → unknown target |
| `Tình trạng` | `formula` | `schema` | formula: `/*Phát hiện lỗi*/
(if({{notion:block_property:Hx%3F_:fe7ccb0…` |
| `📌GHI CHÚ VĨNH VIỄN` | `rich_text` | `schema` |  |
| `🔑 File bệnh nhân` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `ee3ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 5719
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//mã xét nghiệm`: <string>
  - `//ngày up notion`: ∅
  - `Created by`: <user>
  - `Created time`: 2026-**-**
  - `Files kết quả`: <0 file(s)>
  - `Kết quả`: ''
  - `Kết quả AI`: ''
  - `Name`: […(20 chars)
  - `Ngày có kết quả (dự kiến)`: ∅
  - `Người làm`: ∅
  - `Phiếu khám`: <rel→0 page(s)>
  - `Phân loại xét nghiệm`: ∅
  - `Trợ lý ghi chú`: xn…(4 chars)
  - `Tên xét nghiệm`: <rel→0 page(s)>
  - `Tình trạng`: ∅
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 File bệnh nhân`: <rel→0 page(s)>

**Sample 2** (page `265ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 5718
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//mã xét nghiệm`: <string>
  - `//ngày up notion`: 2026-**-**
  - `Created by`: <user>
  - `Created time`: 2026-**-**
  - `Files kết quả`: <1 file(s)>
  - `Kết quả`: HP…(7 chars)
  - `Kết quả AI`: ''
  - `Name`: […(19 chars)
  - `Ngày có kết quả (dự kiến)`: ∅
  - `Người làm`: ∅
  - `Phiếu khám`: <rel→0 page(s)>
  - `Phân loại xét nghiệm`: ∅
  - `Trợ lý ghi chú`: ''
  - `Tên xét nghiệm`: <rel→0 page(s)>
  - `Tình trạng`: ∅
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 File bệnh nhân`: <rel→0 page(s)>

**Sample 3** (page `498ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 5717
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//mã xét nghiệm`: <string>
  - `//ngày up notion`: 2026-**-**
  - `Created by`: <user>
  - `Created time`: 2026-**-**
  - `Files kết quả`: <1 file(s)>
  - `Kết quả`: Hb…(90 chars)
  - `Kết quả AI`: Hb…(61 chars)
  - `Name`: […(20 chars)
  - `Ngày có kết quả (dự kiến)`: ∅
  - `Người làm`: ∅
  - `Phiếu khám`: <rel→0 page(s)>
  - `Phân loại xét nghiệm`: ∅
  - `Trợ lý ghi chú`: nt…(2 chars)
  - `Tên xét nghiệm`: <rel→0 page(s)>
  - `Tình trạng`: ∅
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 File bệnh nhân`: <rel→0 page(s)>

### lib 8 - thư viện báo cáo hằng ngày
- DB ID: `9aeccb0e-ac88-8256-b6fb-8185c9482e38`
- Parent path: (root)

#### Data source · lib 8 - thư viện báo cáo hằng ngày
- Data source ID: `359ccb0e-ac88-823e-b7bd-87f78b864e2c`
- Property count: **2** (schema: 2, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `ID` | `unique_id` | `schema` |  |
| `Name` | `title` | `schema` |  |

**Sample rows (PII-redacted)**

_No rows or query failed._

### lib 7 - thư viện mã điều khiển thống kê
- DB ID: `336ccb0e-ac88-82e0-9f80-01dec1d5d61a`
- Parent path: (root)

#### Data source · lib 7 - thư viện mã điều khiển thống kê
- Data source ID: `1a4ccb0e-ac88-8341-bb6d-078b49fcf383`
- Property count: **3** (schema: 3, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Diễn giải ý nghĩa` | `rich_text` | `schema` |  |
| `Mã điều khiển` | `rich_text` | `schema` |  |
| `Name` | `title` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `e4eccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Diễn giải ý nghĩa`: Ma…(32 chars)
  - `Mã điều khiển`: 03…(4 chars)
  - `Name`: D…(25 chars)

**Sample 2** (page `4e6ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Diễn giải ý nghĩa`: ''
  - `Mã điều khiển`: ''
  - `Name`: B…(6 chars)

**Sample 3** (page `a77ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Diễn giải ý nghĩa`: ''
  - `Mã điều khiển`: ''
  - `Name`: B…(28 chars)

### lib 6 - danh mục thuốc
- DB ID: `03accb0e-ac88-8226-8397-8177ea3e8c47`
- Parent path: (root)

#### Data source · lib 6 - danh mục thuốc
- Data source ID: `721ccb0e-ac88-821b-bf1a-87ea373c4622`
- Property count: **10** (schema: 10, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Giá` | `number` | `schema` | format: `dollar` |
| `ID` | `unique_id` | `schema` |  |
| `Liều tham khảo` | `rich_text` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Nhóm` | `select` | `schema` | options: `Nội tiết` |
| `Parent item` | `relation` | `schema` | → `721ccb0e` (dual_property) |
| `Sub-item` | `relation` | `schema` | → `721ccb0e` (dual_property) |
| `Tên biệt dược` | `rich_text` | `schema` |  |
| `Tình trạng` | `select` | `schema` | options: `Lưu hành`, `Sắp hết`, `Đẩy mạnh`, `Tạm dừng`, `Bỏ hẳn` |
| `Đơn vị tính` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `2e4ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Giá`: ∅
  - `ID`: 111
  - `Liều tham khảo`: ''
  - `Name`: M…(18 chars)
  - `Nhóm`: ∅
  - `Parent item`: <rel→0 page(s)>
  - `Sub-item`: <rel→25 page(s)>
  - `Tên biệt dược`: ''
  - `Tình trạng`: ∅
  - `Đơn vị tính`: ''

**Sample 2** (page `eb1ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Giá`: ∅
  - `ID`: 110
  - `Liều tham khảo`: Ng…(62 chars)
  - `Name`: […(12 chars)
  - `Nhóm`: ∅
  - `Parent item`: <rel→1 page(s)>
  - `Sub-item`: <rel→0 page(s)>
  - `Tên biệt dược`: Cl…(6 chars)
  - `Tình trạng`: Lưu hành
  - `Đơn vị tính`: hộ…(3 chars)

**Sample 3** (page `882ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Giá`: 150000
  - `ID`: 109
  - `Liều tham khảo`: Ng…(68 chars)
  - `Name`: […(34 chars)
  - `Nhóm`: ∅
  - `Parent item`: <rel→1 page(s)>
  - `Sub-item`: <rel→0 page(s)>
  - `Tên biệt dược`: Ce…(14 chars)
  - `Tình trạng`: Lưu hành
  - `Đơn vị tính`: hộ…(3 chars)

### lib 5 - kênh tiếp nhận
- DB ID: `49eccb0e-ac88-83c9-a82e-816d2247688e`
- Parent path: (root)

#### Data source · lib 5 - kênh tiếp nhận
- Data source ID: `703ccb0e-ac88-83b3-bb65-07d325ea2584`
- Property count: **1** (schema: 1, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Name` | `title` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `4f1ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Name`: Z…(6 chars)

**Sample 2** (page `b9cccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Name`: H…(7 chars)

**Sample 3** (page `2eeccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Name`: F…(4 chars)

### lib 4 - Xét nghiệm & Cận lâm sàng
- DB ID: `638ccb0e-ac88-82ec-ac80-01cc1d69178b`
- Parent path: (root)

#### Data source · lib 4 - Xét nghiệm & Cận lâm sàng
- Data source ID: `d6bccb0e-ac88-83c9-beee-07102721efca`
- Property count: **3** (schema: 3, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Name` | `title` | `schema` |  |
| `Thời gian chờ KQ` | `number` | `schema` | format: `number` |
| `Tên viết tắt` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `829ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Name`: N…(16 chars)
  - `Thời gian chờ KQ`: 48
  - `Tên viết tắt`: NI…(16 chars)

**Sample 2** (page `e51ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Name`: N…(11 chars)
  - `Thời gian chờ KQ`: 48
  - `Tên viết tắt`: NI…(11 chars)

**Sample 3** (page `035ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Name`: N…(13 chars)
  - `Thời gian chờ KQ`: 48
  - `Tên viết tắt`: NI…(13 chars)

### lib 3 - danh sách nhân viên
- DB ID: `ad7ccb0e-ac88-83e2-aab3-81279177e7b8`
- Parent path: (root)

#### Data source · lib 3 - danh sách nhân viên
- Data source ID: `b15ccb0e-ac88-82a3-96fa-072e912b16e0`
- Property count: **9** (schema: 9, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Created time` | `created_time` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Ngày bắt đầu vào làm` | `date` | `schema` |  |
| `Parent item` | `relation` | `schema` | → `b15ccb0e` (dual_property) |
| `Sub-item` | `relation` | `schema` | → `b15ccb0e` (dual_property) |
| `Tài khoản` | `people` | `schema` |  |
| `Tên đầy đủ` | `rich_text` | `schema` |  |
| `Vị trí nhân sự` | `multi_select` | `schema` | options: `Lễ tân - Thu ngân`, `Điều dưỡng sản`, `Điều dưỡng siêu âm`, `Phụ + Thuốc bs Thành`, `Trợ lý BS Thành` |
| `Vị trí ưa thích` | `select` | `schema` | options: `*Lễ tân`, `*Thu ngân`, `Khám - Phụ khám`, `Monitor`, `Thuốc`, `Tư vấn - trợ lý`, `Kiểm soát chất lượng`, `Siêu âm` |

**Sample rows (PII-redacted)**

**Sample 1** (page `233ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Created time`: 2026-**-**
  - `Name`: […(28 chars)
  - `Ngày bắt đầu vào làm`: ∅
  - `Parent item`: <rel→0 page(s)>
  - `Sub-item`: <rel→5 page(s)>
  - `Tài khoản`: <0 people>
  - `Tên đầy đủ`: ''
  - `Vị trí nhân sự`: []
  - `Vị trí ưa thích`: ∅

**Sample 2** (page `66cccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Created time`: 2026-**-**
  - `Name`: […(33 chars)
  - `Ngày bắt đầu vào làm`: ∅
  - `Parent item`: <rel→0 page(s)>
  - `Sub-item`: <rel→18 page(s)>
  - `Tài khoản`: <0 people>
  - `Tên đầy đủ`: ''
  - `Vị trí nhân sự`: []
  - `Vị trí ưa thích`: ∅

**Sample 3** (page `36dccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Created time`: 2026-**-**
  - `Name`: B…(7 chars)
  - `Ngày bắt đầu vào làm`: ∅
  - `Parent item`: <rel→1 page(s)>
  - `Sub-item`: <rel→0 page(s)>
  - `Tài khoản`: <0 people>
  - `Tên đầy đủ`: BS…(17 chars)
  - `Vị trí nhân sự`: []
  - `Vị trí ưa thích`: ∅

### lib 2 - danh mục dịch vụ
- DB ID: `ad4ccb0e-ac88-8388-addd-01a225085e49`
- Parent path: (root)

#### Data source · lib 2 - danh mục dịch vụ
- Data source ID: `0e0ccb0e-ac88-83cd-abb8-874bd9122296`
- Property count: **6** (schema: 6, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Giá` | `number` | `schema` | format: `number` |
| `ID` | `unique_id` | `schema` |  |
| `Phân loại` | `select` | `schema` | options: `SA`, `Khám - Tư vấn`, `Thủ thuật` |
| `Tên công khai` | `rich_text` | `schema` |  |
| `Tên dịch vụ` | `title` | `schema` |  |
| `Tên viết tắt` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `0eeccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Giá`: 180000
  - `ID`: 68
  - `Phân loại`: Thủ thuật
  - `Tên công khai`: ''
  - `Tên dịch vụ`: […(55 chars)
  - `Tên viết tắt`: Th…(9 chars)

**Sample 2** (page `430ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Giá`: 255000
  - `ID`: 67
  - `Phân loại`: Thủ thuật
  - `Tên công khai`: ''
  - `Tên dịch vụ`: […(37 chars)
  - `Tên viết tắt`: Th…(9 chars)

**Sample 3** (page `e42ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Giá`: 800000
  - `ID`: 66
  - `Phân loại`: Thủ thuật
  - `Tên công khai`: ''
  - `Tên dịch vụ`: […(24 chars)
  - `Tên viết tắt`: Th…(9 chars)

### brigde 4.1 - lễ tân
- DB ID: `c37ccb0e-ac88-822a-9666-01fe24739a07`
- Parent path: bridge 4 - log and lock

#### Data source · brigde 4.1 - lễ tân
- Data source ID: `a7bccb0e-ac88-83e6-b49f-07e904cc8854`
- Description: Kiểm soát khả năng nhấn nút Check-in trong trang lịch hẹn
- Property count: **7** (schema: 7, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Created time` | `created_time` | `schema` |  |
| `ID` | `unique_id` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Person` | `people` | `schema` |  |
| `Thông tin step 1` | `rich_text` | `schema` |  |
| `Thông tin step 2` | `rich_text` | `schema` |  |
| `Thông tin step 3` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

_No rows or query failed._

### bridge 4.2 - trực chat
- DB ID: `9e6ccb0e-ac88-8239-9997-81404333192d`
- Parent path: bridge 4 - log and lock

#### Data source · bridge 4.2 - trực chat
- Data source ID: `476ccb0e-ac88-83cf-95c6-07ef6ad617fe`
- Description: Kiểm soát các button tạo action tự động trong file hành chính
- Property count: **7** (schema: 7, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Created time` | `created_time` | `schema` |  |
| `ID` | `unique_id` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Person` | `people` | `schema` |  |
| `Thông tin step 1` | `rich_text` | `schema` |  |
| `Thông tin step 2` | `rich_text` | `schema` |  |
| `Thông tin step 3` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

_No rows or query failed._

### bridge 4.3 - cskh
- DB ID: `745ccb0e-ac88-83b7-bfe5-01c14f71c8bc`
- Parent path: bridge 4 - log and lock

#### Data source · bridge 4.3 - cskh
- Data source ID: `5b6ccb0e-ac88-839c-a5cc-87dcd702da0e`
- Description: Kiểm soát các button tạo action tự động trong file hành chính
- Property count: **7** (schema: 7, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Created time` | `created_time` | `schema` |  |
| `ID` | `unique_id` | `schema` |  |
| `Input` | `rich_text` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Person` | `people` | `schema` |  |
| `Thông tin step 2` | `rich_text` | `schema` |  |
| `Thông tin step 3` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

_No rows or query failed._

### bridge 4.4 - file lâm sàng
- DB ID: `319ccb0e-ac88-8247-9db2-01d8a3748bae`
- Parent path: bridge 4 - log and lock

#### Data source · bridge 4.4 - file lâm sàng
- Data source ID: `3b3ccb0e-ac88-83fb-a1e5-07a114975562`
- Property count: **6** (schema: 6, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `ID` | `unique_id` | `schema` |  |
| `Input` | `rich_text` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Output` | `rich_text` | `schema` |  |
| `Person` | `people` | `schema` |  |
| `Trigger time` | `created_time` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `c1cccb0e`, created 2026-**-**, edited 2026-**-**)
  - `ID`: 3
  - `Input`: Un…(20 chars)
  - `Name`: ''
  - `Output`: Un…(8 chars)
  - `Person`: <1 people>
  - `Trigger time`: 2026-**-**

**Sample 2** (page `cd8ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `ID`: 2
  - `Input`: Un…(20 chars)
  - `Name`: ''
  - `Output`: Un…(8 chars)
  - `Person`: <1 people>
  - `Trigger time`: 2026-**-**

**Sample 3** (page `fffccb0e`, created 2026-**-**, edited 2026-**-**)
  - `ID`: 1
  - `Input`: Un…(21 chars)
  - `Name`: ''
  - `Output`: Un…(8 chars)
  - `Person`: <1 people>
  - `Trigger time`: 2026-**-**

### bridge 3 - Panel điều khiển thống kê
- DB ID: `07eccb0e-ac88-82ec-a558-01b08294e432`
- Parent path: (root)

#### Data source · bridge 3 - Panel điều khiển thống kê
- Data source ID: `b65ccb0e-ac88-8344-ad6b-874ebe842767`
- Property count: **9** (schema: 7, page-only: 2)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Control code 1` | `formula` | `schema` | formula: `{{notion:block_property:qD%5Ch:b65ccb0e-ac88-8344-ad6b-874eb…` |
| `Control code 2` | `formula` | `schema` | formula: `{{notion:block_property:%7D%5Bb%3B:b65ccb0e-ac88-8344-ad6b-8…` |
| `Diễn giải của thống kê 1` | `formula` | `schema` | formula: `{{notion:block_property:qD%5Ch:b65ccb0e-ac88-8344-ad6b-874eb…` |
| `Diễn giải của thống kê 2` | `formula` | `schema` | formula: `{{notion:block_property:%7D%5Bb%3B:b65ccb0e-ac88-8344-ad6b-8…` |
| `Name` | `title` | `schema` |  |
| `Nội dung Thống kê 1` | `relation` | `page-only` | → unknown target |
| `Nội dung thống kê 2` | `relation` | `page-only` | → unknown target |
| `Tham số điều khiển 1` | `rich_text` | `schema` |  |
| `Tham số điều khiển 2` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `a6dccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Control code 1`: <string>
  - `Control code 2`: <string>
  - `Diễn giải của thống kê 1`: <string>
  - `Diễn giải của thống kê 2`: <string>
  - `Name`: /…(15 chars)
  - `Nội dung Thống kê 1`: <rel→0 page(s)>
  - `Nội dung thống kê 2`: <rel→0 page(s)>
  - `Tham số điều khiển 1`: ''
  - `Tham số điều khiển 2`: ''

**Sample 2** (page `22dccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Control code 1`: <string>
  - `Control code 2`: <string>
  - `Diễn giải của thống kê 1`: <string>
  - `Diễn giải của thống kê 2`: <string>
  - `Name`: /…(15 chars)
  - `Nội dung Thống kê 1`: <rel→0 page(s)>
  - `Nội dung thống kê 2`: <rel→0 page(s)>
  - `Tham số điều khiển 1`: ''
  - `Tham số điều khiển 2`: ''

**Sample 3** (page `066ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Control code 1`: <string>
  - `Control code 2`: <string>
  - `Diễn giải của thống kê 1`: <string>
  - `Diễn giải của thống kê 2`: <string>
  - `Name`: /…(13 chars)
  - `Nội dung Thống kê 1`: <rel→0 page(s)>
  - `Nội dung thống kê 2`: <rel→0 page(s)>
  - `Tham số điều khiển 1`: ''
  - `Tham số điều khiển 2`: ''

### bridge 2 - Master record ghi dữ liệu ngày khám
- DB ID: `26eccb0e-ac88-83d6-9f55-0178db4aa83e`
- Parent path: (root)

#### Data source · bridge 2 - Master record ghi dữ liệu ngày khám
- Data source ID: `3f7ccb0e-ac88-8220-afa3-075b3b192ac3`
- Property count: **8** (schema: 4, page-only: 4)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Chấm công` | `relation` | `page-only` | → unknown target |
| `Dịch vụ` | `rollup` | `page-only` | (back-side; see sample rows) |
| `Name` | `title` | `schema` |  |
| `Ngày khám` | `date` | `schema` |  |
| `Parent item` | `relation` | `schema` | → `3f7ccb0e` (dual_property) |
| `Phiếu khám` | `relation` | `page-only` | → unknown target |
| `Sub-item` | `relation` | `schema` | → `3f7ccb0e` (dual_property) |
| `Xét nghiệm` | `rollup` | `page-only` | (back-side; see sample rows) |

**Sample rows (PII-redacted)**

**Sample 1** (page `f1eccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Chấm công`: <rel→0 page(s)>
  - `Dịch vụ`: <rollup:array>
  - `Name`: M…(24 chars)
  - `Ngày khám`: 2025-**-**
  - `Parent item`: <rel→1 page(s)>
  - `Phiếu khám`: <rel→0 page(s)>
  - `Sub-item`: <rel→0 page(s)>
  - `Xét nghiệm`: <rollup:array>

**Sample 2** (page `5eaccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Chấm công`: <rel→0 page(s)>
  - `Dịch vụ`: <rollup:array>
  - `Name`: M…(24 chars)
  - `Ngày khám`: 2025-**-**
  - `Parent item`: <rel→1 page(s)>
  - `Phiếu khám`: <rel→0 page(s)>
  - `Sub-item`: <rel→0 page(s)>
  - `Xét nghiệm`: <rollup:array>

**Sample 3** (page `123ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Chấm công`: <rel→0 page(s)>
  - `Dịch vụ`: <rollup:array>
  - `Name`: M…(24 chars)
  - `Ngày khám`: 2025-**-**
  - `Parent item`: <rel→1 page(s)>
  - `Phiếu khám`: <rel→0 page(s)>
  - `Sub-item`: <rel→0 page(s)>
  - `Xét nghiệm`: <rollup:array>

### bridge 1 - tự điền nhân viên buổi khám
- DB ID: `8acccb0e-ac88-82fc-8a6c-018213105fc4`
- Parent path: (root)

#### Data source · bridge 1 - tự điền nhân viên buổi khám
- Data source ID: `421ccb0e-ac88-8349-9268-07aeae75b364`
- Property count: **7** (schema: 6, page-only: 1)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Last edited by` | `last_edited_by` | `schema` |  |
| `Nhân viên` | `relation` | `page-only` | → unknown target |
| `Parent item` | `relation` | `schema` | → `421ccb0e` (dual_property) |
| `Phòng khám` | `select` | `schema` | options: `Hào Nam`, `Kim ngưu` |
| `Status` | `formula` | `schema` | formula: `if({{notion:block_property:cteU:421ccb0e-ac88-8349-9268-07ae…` |
| `Sub-item` | `relation` | `schema` | → `421ccb0e` (dual_property) |
| `Tài khoản` | `title` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `227ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Last edited by`: <user>
  - `Nhân viên`: <rel→0 page(s)>
  - `Parent item`: <rel→1 page(s)>
  - `Phòng khám`: Kim ngưu
  - `Status`: <string>
  - `Sub-item`: <rel→0 page(s)>
  - `Tài khoản`: S…(3 chars)

**Sample 2** (page `1d2ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Last edited by`: <user>
  - `Nhân viên`: <rel→0 page(s)>
  - `Parent item`: <rel→1 page(s)>
  - `Phòng khám`: Kim ngưu
  - `Status`: <string>
  - `Sub-item`: <rel→0 page(s)>
  - `Tài khoản`: S…(3 chars)

**Sample 3** (page `fe8ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Last edited by`: <user>
  - `Nhân viên`: <rel→0 page(s)>
  - `Parent item`: <rel→1 page(s)>
  - `Phòng khám`: Kim ngưu
  - `Status`: <string>
  - `Sub-item`: <rel→0 page(s)>
  - `Tài khoản`: S…(3 chars)

### Phiếu đăng kí khám không theo hẹn
- DB ID: `ac5ccb0e-ac88-820f-ba34-019ed223bd0b`
- Parent path: (root)

#### Data source · Phiếu đăng kí khám không theo hẹn
- Data source ID: `3faccb0e-ac88-8214-b519-87668c493287`
- Property count: **8** (schema: 7, page-only: 1)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Bác sĩ` | `select` | `schema` | options: `BS Thành` |
| `Loại dịch vụ khám` | `select` | `schema` | (no options) |
| `Name` | `title` | `schema` |  |
| `Phòng khám` | `select` | `schema` | options: `Kim Ngưu`, `Hào Nam` |
| `Số thứ tự` | `number` | `schema` | format: `number` |
| `Thông tin` | `formula` | `schema` | formula: `/*Địa chỉ*/
{{notion:block_property:xwqq:3faccb0e-ac88-8214-…` |
| `Thời điểm đến khám` | `created_time` | `schema` |  |
| `🔑 File hành chính` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `db4ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Bác sĩ`: ∅
  - `Loại dịch vụ khám`: ∅
  - `Name`: Đ…(48 chars)
  - `Phòng khám`: Kim Ngưu
  - `Số thứ tự`: ∅
  - `Thông tin`: ∅
  - `Thời điểm đến khám`: 2026-**-**
  - `🔑 File hành chính`: <rel→0 page(s)>

**Sample 2** (page `091ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Bác sĩ`: BS Thành
  - `Loại dịch vụ khám`: ∅
  - `Name`: Đ…(54 chars)
  - `Phòng khám`: ∅
  - `Số thứ tự`: ∅
  - `Thông tin`: ∅
  - `Thời điểm đến khám`: 2026-**-**
  - `🔑 File hành chính`: <rel→0 page(s)>

**Sample 3** (page `3caccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Bác sĩ`: ∅
  - `Loại dịch vụ khám`: ∅
  - `Name`: Đ…(30 chars)
  - `Phòng khám`: Kim Ngưu
  - `Số thứ tự`: ∅
  - `Thông tin`: ∅
  - `Thời điểm đến khám`: 2026-**-**
  - `🔑 File hành chính`: <rel→0 page(s)>

### output - tờ in đơn thuốc
- DB ID: `857ccb0e-ac88-820d-afd8-01f2d2b2a0d2`
- Parent path: (root)

#### Data source · output - tờ in đơn thuốc
- Data source ID: `a2fccb0e-ac88-8208-bac4-870913523b5c`
- Property count: **6** (schema: 4, page-only: 2)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `//lượt kê thuốc` | `rollup` | `page-only` | (back-side; see sample rows) |
| `Danh sách thuốc` | `formula` | `schema` | formula: `{{notion:block_property:KAW%3E:a2fccb0e-ac88-8208-bac4-87091…` |
| `ID` | `unique_id` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Phiếu khám` | `relation` | `page-only` | → unknown target |
| `Thông tin bệnh nhân` | `formula` | `schema` | formula: `let(BN,{{notion:block_property:fy%60d:a2fccb0e-ac88-8208-bac…` |

**Sample rows (PII-redacted)**

**Sample 1** (page `151ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//lượt kê thuốc`: <rollup:array>
  - `Danh sách thuốc`: ∅
  - `ID`: 5818
  - `Name`: H…(20 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Thông tin bệnh nhân`: ∅

**Sample 2** (page `19eccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//lượt kê thuốc`: <rollup:array>
  - `Danh sách thuốc`: ∅
  - `ID`: 5798
  - `Name`: H…(20 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Thông tin bệnh nhân`: ∅

**Sample 3** (page `177ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//lượt kê thuốc`: <rollup:array>
  - `Danh sách thuốc`: ∅
  - `ID`: 5817
  - `Name`: H…(20 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Thông tin bệnh nhân`: ∅

### Video checkmark
- DB ID: `e63ccb0e-ac88-8247-ab3b-814e7fba25c1`
- Parent path: (root)

#### Data source · Video checkmark
- Data source ID: `c6bccb0e-ac88-83e2-9755-07547a3767ea`
- Property count: **13** (schema: 11, page-only: 2)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Bệnh nhân` | `relation` | `page-only` | → unknown target |
| `Created by` | `created_by` | `schema` |  |
| `Date` | `date` | `schema` |  |
| `Feedback BS ` | `rich_text` | `schema` |  |
| `ID` | `unique_id` | `schema` |  |
| `Link video ` | `url` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Note PR` | `rich_text` | `schema` |  |
| `Note trợ lý` | `rich_text` | `schema` |  |
| `Phiếu khám` | `relation` | `page-only` | → unknown target |
| `Time` | `created_time` | `schema` |  |
| `Tình trạng hoàn thành` | `status` | `schema` | options: `Bỏ`, `Dự kiến`, `Đang hoàn thành`, `Hoàn thành` |
| `Tóm tắt` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `07dccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Bệnh nhân`: <rel→0 page(s)>
  - `Created by`: <user>
  - `Date`: ∅
  - `Feedback BS `: ''
  - `ID`: 241
  - `Link video `: ∅
  - `Name`: C…(5 chars)
  - `Note PR`: ''
  - `Note trợ lý`: Mộ…(42 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Time`: 2026-**-**
  - `Tình trạng hoàn thành`: ∅
  - `Tóm tắt`: @N…(76 chars)

**Sample 2** (page `d12ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Bệnh nhân`: <rel→0 page(s)>
  - `Created by`: <user>
  - `Date`: ∅
  - `Feedback BS `: ''
  - `ID`: 240
  - `Link video `: ∅
  - `Name`: C…(5 chars)
  - `Note PR`: ''
  - `Note trợ lý`: tử…(45 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Time`: 2026-**-**
  - `Tình trạng hoàn thành`: ∅
  - `Tóm tắt`: @S…(221 chars)

**Sample 3** (page `fa8ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Bệnh nhân`: <rel→0 page(s)>
  - `Created by`: <user>
  - `Date`: ∅
  - `Feedback BS `: ''
  - `ID`: 239
  - `Link video `: ∅
  - `Name`: C…(5 chars)
  - `Note PR`: ''
  - `Note trợ lý`: Mẹ…(30 chars)
  - `Phiếu khám`: <rel→0 page(s)>
  - `Time`: 2026-**-**
  - `Tình trạng hoàn thành`: ∅
  - `Tóm tắt`: @S…(16 chars)

### Pathowiki
- DB ID: `c08ccb0e-ac88-836a-9968-81829a02c254`
- Parent path: (root)

#### Data source · Pathowiki
- Data source ID: `de7ccb0e-ac88-82c7-8786-07f67178d0ab`
- Property count: **1** (schema: 1, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Name` | `title` | `schema` |  |

**Sample rows (PII-redacted)**

_No rows or query failed._

### Microwiki
- DB ID: `1ccccb0e-ac88-838f-bb91-81c753f1ea1a`
- Parent path: (root)

#### Data source · Microwiki
- Data source ID: `154ccb0e-ac88-83b5-92ca-87e7fd4b4fa0`
- Property count: **7** (schema: 7, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Brief` | `rich_text` | `schema` |  |
| `Classification 1` | `multi_select` | `schema` | options: `CT` |
| `Classification 2` | `multi_select` | `schema` | options: `Measuring` |
| `Last update` | `date` | `schema` |  |
| `Name` | `title` | `schema` |  |
| `Profession` | `multi_select` | `schema` | options: `Cardiac` |
| `Tags` | `rich_text` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `d74ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `Brief`: ''
  - `Classification 1`: [CT]
  - `Classification 2`: [Measuring]
  - `Last update`: 2026-**-**
  - `Name`: C…(26 chars)
  - `Profession`: [Cardiac]
  - `Tags`: th…(58 chars)

### Sidewiki
- DB ID: `f00ccb0e-ac88-82f7-8742-8116303feaf3`
- Parent path: (root)

#### Data source · Sidewiki
- Data source ID: `290ccb0e-ac88-82b3-901b-078cfc881080`
- Property count: **1** (schema: 1, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `Name` | `title` | `schema` |  |

**Sample rows (PII-redacted)**

_No rows or query failed._

### Phiếu khám
- DB ID: `ce5ccb0e-ac88-824b-9b08-01a9c15162e8`
- Parent path: (root)

#### Data source · Phiếu khám
- Data source ID: `850ccb0e-ac88-8269-bc04-87c76245e500`
- Property count: **28** (schema: 19, page-only: 9)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `*ID` | `unique_id` | `schema` |  |
| `// file tờ đơn thuốc` | `relation` | `page-only` | → unknown target |
| `//bridge 2 - Master record` | `relation` | `page-only` | → unknown target |
| `//bridge 3 - Panel điều khiển thống kê` | `relation` | `page-only` | → unknown target |
| `//file action` | `relation` | `page-only` | → unknown target |
| `//file dịch vụ ` | `relation` | `page-only` | → unknown target |
| `//file kê thuốc` | `relation` | `page-only` | → unknown target |
| `//file lịch hẹn` | `relation` | `page-only` | → unknown target |
| `//file xét nghiệm` | `relation` | `page-only` | → unknown target |
| `>> Thống kê 1` | `formula` | `schema` | formula: `let(previousindex,({{notion:block_property:xaki:850ccb0e-ac8…` |
| `>> Thống kê 2` | `formula` | `schema` | formula: `if({{notion:block_property:f%7DP%7B:850ccb0e-ac88-8269-bc04-…` |
| `Bác sĩ khám chính` | `select` | `schema` | options: `BS Thành`, `BS Vân`, `BS Hằng`, `BS Thủy`, `BS Linh nam khoa`, `BS Đào`, `BS Hùng`, `BS Nam`, `BS Thiệp`, `BS Quyết` |
| `Chuẩn đoán công khai` | `rich_text` | `schema` |  |
| `Created by` | `created_by` | `schema` |  |
| `Cận lâm sàng` | `formula` | `schema` | formula: `let(DV,{{notion:block_property:G%3AG%5C:850ccb0e-ac88-8269-b…` |
| `Formula` | `formula` | `schema` | formula: `let(
  minutes,
  dateBetween({{notion:block_property:p%7Cj…` |
| `Giờ kết thúc` | `formula` | `schema` | formula: `{{notion:block_property:G%3AG%5C:850ccb0e-ac88-8269-bc04-87c…` |
| `Giờ vào khám` | `formula` | `schema` | formula: `{{notion:block_property:G%3AG%5C:850ccb0e-ac88-8269-bc04-87c…` |
| `Khám - Tư vấn` | `rich_text` | `schema` |  |
| `Loại dịch vụ khám` | `select` | `schema` | options: `Sản 1`, `Sản 2`, `Sản 3`, `NPĐH`, `Hồ sơ sinh`, `Tiền hôn nhân`, `Hiếm muộn`, `Nội tiết - Tình dục`, `Phụ khoa`, `Nam khoa`, `Tư vấn chuyên sâu`, `Khám tiền sản` (+5 more) |
| `Name` | `title` | `schema` |  |
| `Ngày khám` | `formula` | `schema` | formula: `if({{notion:block_property:%3CGBx:850ccb0e-ac88-8269-bc04-87…` |
| `Phòng khám` | `select` | `schema` | options: `Kim Ngưu`, `Hào Nam` |
| `Thuốc` | `formula` | `schema` | formula: `if({{notion:block_property:UJcj:850ccb0e-ac88-8269-bc04-87c7…` |
| `Tình trạng` | `formula` | `schema` | formula: `/*Hiển thị nếu loại khám là thủ thuật / mổ ngoài*/
if({{noti…` |
| `Tùy chọn ngày khám` | `date` | `schema` |  |
| `📌GHI CHÚ VĨNH VIỄN` | `rich_text` | `schema` |  |
| `🔑 file lâm sàng` | `relation` | `page-only` | → unknown target |

**Sample rows (PII-redacted)**

**Sample 1** (page `357ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 9683
  - `// file tờ đơn thuốc`: <rel→0 page(s)>
  - `//bridge 2 - Master record`: <rel→0 page(s)>
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//file dịch vụ `: <rel→0 page(s)>
  - `//file kê thuốc`: <rel→0 page(s)>
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//file xét nghiệm`: <rel→0 page(s)>
  - `>> Thống kê 1`: <string>
  - `>> Thống kê 2`: <string>
  - `Bác sĩ khám chính`: BS Thành
  - `Chuẩn đoán công khai`: kh…(36 chars)
  - `Created by`: <user>
  - `Cận lâm sàng`: <string>
  - `Formula`: <string>
  - `Giờ kết thúc`: ∅
  - `Giờ vào khám`: ∅
  - `Khám - Tư vấn`: HB…(66 chars)
  - `Loại dịch vụ khám`: Tiền hôn nhân
  - `Name`: P…(41 chars)
  - `Ngày khám`: 2026-**-**
  - `Phòng khám`: Kim Ngưu
  - `Thuốc`: <string>
  - `Tình trạng`: <string>
  - `Tùy chọn ngày khám`: ∅
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 file lâm sàng`: <rel→0 page(s)>

**Sample 2** (page `0ffccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 9682
  - `// file tờ đơn thuốc`: <rel→0 page(s)>
  - `//bridge 2 - Master record`: <rel→0 page(s)>
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//file dịch vụ `: <rel→0 page(s)>
  - `//file kê thuốc`: <rel→0 page(s)>
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//file xét nghiệm`: <rel→0 page(s)>
  - `>> Thống kê 1`: <string>
  - `>> Thống kê 2`: <string>
  - `Bác sĩ khám chính`: BS Thành
  - `Chuẩn đoán công khai`: Th…(30 chars)
  - `Created by`: <user>
  - `Cận lâm sàng`: <string>
  - `Formula`: <string>
  - `Giờ kết thúc`: ∅
  - `Giờ vào khám`: ∅
  - `Khám - Tư vấn`: HA…(46 chars)
  - `Loại dịch vụ khám`: Sản 1
  - `Name`: P…(36 chars)
  - `Ngày khám`: 2026-**-**
  - `Phòng khám`: Kim Ngưu
  - `Thuốc`: <string>
  - `Tình trạng`: <string>
  - `Tùy chọn ngày khám`: ∅
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 file lâm sàng`: <rel→0 page(s)>

**Sample 3** (page `efcccb0e`, created 2026-**-**, edited 2026-**-**)
  - `*ID`: 9681
  - `// file tờ đơn thuốc`: <rel→0 page(s)>
  - `//bridge 2 - Master record`: <rel→0 page(s)>
  - `//bridge 3 - Panel điều khiển thống kê`: <rel→0 page(s)>
  - `//file action`: <rel→0 page(s)>
  - `//file dịch vụ `: <rel→0 page(s)>
  - `//file kê thuốc`: <rel→0 page(s)>
  - `//file lịch hẹn`: <rel→0 page(s)>
  - `//file xét nghiệm`: <rel→0 page(s)>
  - `>> Thống kê 1`: <string>
  - `>> Thống kê 2`: <string>
  - `Bác sĩ khám chính`: BS Thành
  - `Chuẩn đoán công khai`: TM…(75 chars)
  - `Created by`: <user>
  - `Cận lâm sàng`: <string>
  - `Formula`: <string>
  - `Giờ kết thúc`: ∅
  - `Giờ vào khám`: ∅
  - `Khám - Tư vấn`: HB…(134 chars)
  - `Loại dịch vụ khám`: Nội tiết - Tình dục
  - `Name`: P…(34 chars)
  - `Ngày khám`: 2026-**-**
  - `Phòng khám`: Kim Ngưu
  - `Thuốc`: <string>
  - `Tình trạng`: <string>
  - `Tùy chọn ngày khám`: ∅
  - `📌GHI CHÚ VĨNH VIỄN`: ''
  - `🔑 file lâm sàng`: <rel→0 page(s)>

### lib 1 - kịch bản cskh
- DB ID: `042ccb0e-ac88-829f-86b8-8180dd291996`
- Parent path: (root)

#### Data source · lib 1 - kịch bản cskh
- Data source ID: `91bccb0e-ac88-83b5-beb8-87f4d42c8b6b`
- Property count: **7** (schema: 7, page-only: 0)

**Properties**

| Property | Type | Origin | Notes |
| --- | --- | --- | --- |
| `//step` | `select` | `schema` | options: `#request`, `#key`, `#forward`, `#foward*` |
| `//text code` | `rich_text` | `schema` |  |
| `ID` | `unique_id` | `schema` |  |
| `Phân loại` | `select` | `schema` | options: `Đặt hẹn`, `Mổ và thủ thuật`, `Trả xét nghiệm`, `Tư vấn`, `CSKH sau khám`, `Xử lí sự cố`, `Ghi chú` |
| `Phân loại tính tiền` | `select` | `schema` | options: `Tạo hẹn khám`, `Nhắc hẹn khám`, `Chăm sóc sau khám`, `Tư vấn`, `Trả xét nghiệm` |
| `Số giờ đến deadline` | `number` | `schema` | format: `number` |
| `result` | `title` | `schema` |  |

**Sample rows (PII-redacted)**

**Sample 1** (page `2b6ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//step`: #foward*
  - `//text code`: BI…(34 chars)
  - `ID`: 48
  - `Phân loại`: Xử lí sự cố
  - `Phân loại tính tiền`: ∅
  - `Số giờ đến deadline`: ∅
  - `result`: 6…(31 chars)

**Sample 2** (page `08cccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//step`: #key
  - `//text code`: ꪜ …(16 chars)
  - `ID`: 47
  - `Phân loại`: Xử lí sự cố
  - `Phân loại tính tiền`: ∅
  - `Số giờ đến deadline`: ∅
  - `result`: 6…(37 chars)

**Sample 3** (page `1a8ccb0e`, created 2026-**-**, edited 2026-**-**)
  - `//step`: #key
  - `//text code`: ✘ …(21 chars)
  - `ID`: 46
  - `Phân loại`: Xử lí sự cố
  - `Phân loại tính tiền`: ∅
  - `Số giờ đến deadline`: ∅
  - `result`: 6…(38 chars)
