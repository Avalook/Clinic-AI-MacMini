# Soát hệ thống 22/10/2026 · Khối 3 — Lịch + Hành trình

> Soát **CHỈ ĐỌC** trên nhánh `main` @00bde52 (gần bản prod). Không sửa code, test hay migration.
> Bản đồ `claude/ban-do-hieu` dùng để định hướng. Mọi kết luận dựa trên code thật: "đã lần theo code" nghĩa là đã mở đúng dòng
> và đi hết đường gọi; "nghi" nghĩa là chưa đi hết, hoặc cần dữ liệu prod / Tuyền quyết nghiệp vụ. Chưa chạy test nào.
> Đọc ba nhánh song song bằng 3 agent; các phát hiện mức cao đã được người viết mở lại đúng dòng kiểm tận mắt.

## Tóm tắt 10 dòng

1. Khối lịch + hành trình **chắc ở chỗ khó nhất**: hai người đặt cùng khung, hai lễ tân check-in cùng lúc, hai phòng cùng "Nhận" đều đã khoá đúng ở Postgres.
2. Lỗi tập trung ở **hoàn tác**. Nhiều thao tác khoá cứng, hoặc hoàn tác được nhưng không trả lại đủ trạng thái.
3. **Cao 3.1:** hoàn tác "bỏ chỉ định" không dựng lại yêu cầu "cần kết quả". Kết quả xét nghiệm có thể không bao giờ về bác sĩ đọc.
4. **Cao 2.1:** hoàn tác check-in xong, màn Tiếp đón ghi "Về giữa chừng" và mất nút Check-in. Khách kẹt, phải đi đường vòng.
5. **Cao 1.1:** "Không đến" và "Huỷ lịch" không có đường khôi phục. Bấm nhầm là phải đặt lịch mới.
6. Hoàn tác check-in còn để lại rác ở màn Check-out (2.2) và chỉ định đã xếp phòng bị kẹt không vào hàng (2.3).
7. Ba thao tác ở bàn khám / phòng chưa có hoàn tác: Bắt đầu khám (3.2), Không làm được (3.3), Miễn yêu cầu kết quả (3.4).
8. Mâu thuẫn giữa màn: tick lại dịch vụ sau khi lượt "khám xong" (3.5); lưới đặt lịch nói "còn chỗ" mà bấm bị chặn (1.2, 1.4).
9. Giờ VN gần như sạch: chỉ còn `queue.py:104` (đã biết, PR #522 chưa vào `main`) và vài `current_date` phụ thuộc cấu hình DB (0.3, cần một lệnh kiểm trên VPS).
10. Lọc cơ sở ở mọi danh sách đều đúng. Lệnh ghi không kiểm cơ sở là theo thiết kế; Tuyền chốt lại khi có phòng khám thứ hai (2.10).

## Bảng phát hiện

| # | Mức | Chỗ | Một dòng | Độ chắc |
|---|---|---|---|---|
| 3.1 | **cao** | `hoan_tac_service.py:824` · `so_sua_chi_dinh_service.py:754` | Hoàn tác bỏ chỉ định không dựng lại yêu cầu kết quả, nên kết quả không về bác sĩ | chắc chắn |
| 2.1 | **cao** | `tiep_don_service.py:151,163` · `booking_service.py:2813` | Hoàn tác check-in → chip "Về giữa chừng", mất nút Check-in | chắc chắn |
| 1.1 | **cao** | `booking_service.py:324–425` | Không đến / Huỷ lịch khoá cứng, không khôi phục được | chắc chắn |
| 2.2 | vừa | `checkout_service.py:85,410` | Lượt hoàn tác check-in nằm mãi ở Check-out; check-out khách chưa đến | chắc chắn |
| 2.3 | vừa | `service_routing_service.py:1402` · `booking_service.py:2839` | Chỉ định đã xếp phòng kẹt sau hoàn tác + check-in lại | chắc chắn (agent) |
| 2.4 | vừa | `booking_service.py:376,1040` | Huỷ lịch đã check-in khi khách đang làm dịch vụ | chắc ở backend |
| 2.5 | vừa | `hoan_tac_service.py:1205` | Mở lại lượt nhận cả lượt INCOMPLETE do hoàn tác / huỷ | chắc chắn |
| 3.2 | vừa | `luot_kham_service.py:1874` | Bắt đầu khám không hoàn tác được | chắc chắn (agent) |
| 3.3 | vừa | `service_execution_service.py:648` · `dieu_tri_ban_kham.py:507` | "Không làm được" không hoàn tác; kê lại trả chỉ định chết | chắc chắn (agent) |
| 3.4 | vừa | `luot_kham_service.py:2984` | Miễn / Chuyển theo dõi yêu cầu kết quả không hoàn tác | chắc chắn (agent) |
| 3.5 | vừa | `service_selection_service.py:504` | Tick lại dịch vụ sau "khám xong" không mở lại mốc → màn mâu thuẫn | chắc chắn (agent) |
| 3.6 | vừa | `luot_kham_service.py:1133` | Lượt Điều trị không tự "khám xong" khi bác sĩ không nhận | cần Tuyền quyết |
| 1.2 | vừa | `booking_service.py:2449` | Lịch chưa phân bác sĩ: Python chặn, trigger + lưới cho | chắc chắn |
| 1.3 | vừa | `booking_service.py:1785` · `doi_lich_nhanh.py:1209` | Dời / đổi lịch bỏ qua luật "khách mới → BS X" | chắc chắn (agent) |
| 1.4 | vừa | `capacity_service.py:119,265` | Lưới hiểu "đã xếp ca" theo ngày, luật theo tuần | chắc chắn |
| 1.5 | vừa | `routers/booking.py:304` | Chờ xếp bác sĩ sót lịch khi ca chưa duyệt | chắc về code |
| 1.6 | vừa | `booking_service.py:345` | Check-in được lịch ngày khác | nghi (màn) |
| 1.7 | vừa | `booking_service.py:419` | Dời được lịch đã CHECKED_IN sang ngày khác | cần Tuyền quyết |
| 0.4 | vừa | `routers/booking.py:482,539` | `quote` / `cho-trong-tuan` 500 với UUID rác | chắc chắn |
| 0.1 | thấp | `routers/queue.py:104` | Hàng chờ dùng `date.today()` | **đã biết** (#522) |
| 0.2 | thấp | `booking_override_service.py:369` | Luật số chỗ dùng `date.today()` | **đã biết** (bản đồ) |
| 0.3 | thấp | `booking_override_service.py:287,298,754` | `current_date` phụ thuộc múi của cụm DB | nghi, cần `SHOW timezone` |
| 0.5 | thấp | `scheduling_service.py:244` | Nơi ghi lịch thứ hai là code chết, bỏ qua mọi luật, bài canh vẫn duyệt | chắc chắn |
| 1.8 | thấp | `booking_service.py:612` | Dời lịch không chặn trùng giờ cùng khách | chắc chắn (agent) |
| 1.9 | thấp | `v_viec_cskh` (20261015110000) | Đã xác nhận một lần → việc đóng vĩnh viễn kể cả khi dời | cần Tuyền quyết |
| 1.10 | thấp | `clinic_policy.py:197` | `except: pass` trong giao dịch che lỗi gốc | chắc chắn (agent) |
| 1.11 | thấp | `capacity_service.py:367` | Lưới và trigger cắt khung khác nhau khi giờ mở lệch | nghi |
| 2.6 | thấp | `booking_service.py:2648` | Check-in lại giữ mốc kéo tay cũ → vượt hàng | chắc chắn (agent) |
| 2.7 | thấp | `sinh_hieu_service.py:146` | Bắt đầu đo trên lượt đã hoàn tác check-in | chắc chắn (agent) |
| 2.8 | thấp | `20261008700000_co_so_hien_hanh.sql:94` | Check-in lại không đặt lại trạm đầu | nghi |
| 2.9 | thấp | `bang_hanh_trinh_service.py:36` · `lich_phong_service.py:67` | Ngày `9999-12-31` → 500 | chắc chắn |
| 2.10 | thấp | lệnh ghi lượt | Lệnh ghi không kiểm cơ sở người bấm | theo thiết kế, Tuyền chốt |
| 3.7 | thấp | `BanKham.tsx:952` | Luật chọn chế độ Hoàn tất nằm trong TSX, lệch backend | chắc chắn (agent) |
| 3.8 | thấp | `luot_kham_service.py:1133` | Phiên tư vấn được tính là "đã khám" | nghi |
| 3.9 | thấp | `hoan_tac_service.py:1023` | Phát `visit.exam_completed` hai lần, đè giờ | chắc chắn (agent) |

"chắc chắn (agent)" = agent đã lần theo code tới đúng dòng; người viết đã kiểm lại các dòng chính của 1.1, 1.2, 2.1, 2.2, 3.1, 0.4, 0.5.

## Việc cần Tuyền

- **Quyết nghiệp vụ:** 1.7 (dời lịch đã check-in?), 1.9 (dời lịch thì gọi xác nhận lại?), 3.6 (lượt Điều trị tự "khám xong"?), 2.10 (lệnh ghi có chặn theo cơ sở?).
- **Kiểm VPS (chỉ đọc), cho 0.3:** `docker exec clinicai_db psql -U postgres -c 'SHOW timezone'` (và container DB staging). Kỳ vọng `Asia/Ho_Chi_Minh`.
- **Thứ tự sửa đề xuất** (mỗi việc một PR Mức 2): 3.1 → 2.1 + 2.5 → 1.1 + 2.4 → 2.2 → 2.3 → các lệnh hoàn tác 3.2/3.3/3.4 → 3.5 → nhóm sức chứa 1.2/1.4/1.5 → 0.4.

## Phạm vi

Đặt lịch (3 nơi ghi lịch, sức chứa, gọi xác nhận, Không đến), tiếp đón / check-in, xếp phòng theo lịch trực, nhận khách tại phòng,
Bàn khám / Bàn tư vấn, chỉ định, Hoàn tất khám, check-out, mở lại lượt, liệu trình, đa cơ sở. **Không** gồm kho thuốc, quầy thuốc, kho vật tư.

## Nhóm 0 — Giờ Việt Nam và ngày rác (quét chéo)

Quét toàn bộ `src/clinicai` tìm `date.today()` / `datetime.now()` trần, các dòng `CURRENT_DATE` trong migration, và kiểu `toISOString().slice(0,10)` ở giao diện.
Kết quả **khá sạch**: SQL hầu hết đã viết `AT TIME ZONE 'Asia/Ho_Chi_Minh'`. Python dùng
`core/clock.py` (`hom_nay_vn`, `now_vn`). Giao diện cộng +7 giờ hoặc neo theo UTC. Tham số `?week=` rác đã trả rỗng
(`lib/roster.ts` `weekStartOf`).

> **Thuật ngữ.** *Giờ máy chủ*: container chạy múi UTC, chậm 7 tiếng so với giờ VN. Vì vậy `date.today()` gọi lúc 0h–7h sáng VN
> vẫn trả **ngày hôm qua**.

**0.1 · thấp · `queue.py:104` hàng chờ dùng `date_cls.today()`** — **đã biết** (phat-hien.json, PR #522).
Ghi lại vì trên `main` @00bde52 dòng này **vẫn còn**: PR #522 chưa vào `main`.

**0.2 · thấp · `services/booking_override_service.py:369` `eff_from = date.today()`** — **đã biết**
(bản đồ khối booking ghi). Hệ quả: tạo luật số chỗ thường trực lúc 0h–7h thì luật mới tính hiệu lực từ hôm qua. Luật cũ
cũng bị cắt từ hôm qua. Hôm qua đã qua nên tác động thực tế gần như bằng 0. Sửa: `hom_nay_vn()`.

**0.3 · thấp · nghi · `booking_override_service.py:287, 298, 754` dùng `current_date` trong SQL.**
Giá trị `current_date` theo múi giờ của **phiên Postgres**. `core/database.py:42` chỉ đặt `{"jit": "off"}`, không đặt `timezone`.
Vậy nó phụ thuộc cấu hình máy chủ DB. `docker-compose.supabase.yml:60` có đặt `TZ: Asia/Ho_Chi_Minh`. Nếu cụm DB
được `initdb` với biến này thì `postgresql.conf` mang giờ VN và **không lỗi**. Nếu cụm được khởi tạo trước đó / nạp từ nơi khác
thì 0h–7h màn "Luật số chỗ" coi luật hết hạn hôm qua là còn hiệu lực (chỉ ảnh hưởng hiển thị).
*Cách kiểm (Tuyền, chỉ đọc):* `docker exec clinicai_db psql -U postgres -c 'SHOW timezone'` trên prod và staging.
*Hướng sửa phòng xa:* đặt `"timezone": "Asia/Ho_Chi_Minh"` vào `SERVER_SETTINGS`, để mọi `current_date`/`now()::date`
không còn phụ thuộc cấu hình cụm.

**0.4 · vừa · `api/v1/routers/booking.py:482–507` (`/appointments/quote`) và `:539–562` (`/appointments/cho-trong-tuan`) — UUID rác ra 500.**
`doctor_id` và `location_id` khai kiểu `str`, đi thẳng vào `$n::uuid` trong `capacity_service.py`. asyncpg ném
`DataError`, không handler nào bắt nên thành 500.
*Tái hiện:* `GET /api/v1/appointments/quote?date=2026-10-22&doctor_id=abc` → 500. Tương tự với `location_id=abc`, và
`/cho-trong-tuan?week_start=2026-10-20&location_id=abc`. Còn `?date=abc` thì ném `ValidationError` (4xx, không 500)
thay vì trả rỗng. *Đối chiếu:* `/appointments/policy` (booking.py:652–659) và `luoi-ngay` (`_uuid_hop_le`) đã làm đúng.
*Độ chắc:* đã lần theo code. *Test:* gọi hai route với `abc`, kỳ vọng ≠ 500. *Sửa:* khai `UUID | None`, hoặc qua
`_uuid_hop_le` (rác → None).

**0.5 · thấp · `services/scheduling_service.py:244` — "nơi ghi lịch thứ hai" là code chết, bỏ qua mọi luật.**
Bài canh `test_dat_lich_chi_ba_noi_ghi.py` duyệt ba nơi `INSERT INTO appointment`: `booking_service`, `scheduling_service`, `chuyen_luot_that`.
`SchedulingService.create_appointment` chỉ được gọi từ công cụ AI `tools/scheduling/create_appointment.py`. Công cụ này
đăng ký vào `REGISTRY` nhưng **không nơi nào gọi `REGISTRY.get`/`.fn`**, và orchestrator tắt ở prod
(`ENABLE_AI_ORCHESTRATOR`). Đường này ghi `SCHEDULED`, không phát sự kiện, không chặn khung đã qua, không chặn trùng khách, không áp luật bác sĩ bắt buộc.
Hôm nay vô hại. Nhưng bài canh đang **duyệt** nó như một nơi ghi hợp lệ, nên ai nối lại công cụ AI thì lọt hết luật
mà không bài nào đỏ. *Sửa:* xoá `create/cancel/confirm_appointment` ở `scheduling_service` + `tools/scheduling`, bỏ khỏi
`NOI_DUOC_GHI`. Còn `chuyen_luot_that.py` là script nhập Notion, ghi thẳng `COMPLETED`, cố ý không qua luật (không phải lỗi).

## Nhóm 1 — Đặt lịch, sức chứa, gọi xác nhận

> **Thuật ngữ.** *Lịch hẹn* = dòng `appointment`. *Sức chứa* = số chỗ mỗi bác sĩ mỗi khung 15 phút (Dr4Women: 2 chỗ
> đặt trước + 1 vãng lai). *Trigger* = đoạn SQL Postgres tự chạy khi ghi một dòng; ở đây `enforce_slot_capacity` là chốt cuối
> cùng chặn đặt quá chỗ.

**Đã soát, ổn:** hai người đặt cùng khung. Trigger `enforce_slot_capacity` (bản 20260915000017) lấy
`pg_advisory_xact_lock` theo phòng khám | bác sĩ | khung rồi mới đếm, nên không lọt. `ClinicPolicy.bucket` cắt khung cùng phép
với trigger. `_update` đổi trạng thái có điều kiện `status IN (...)`. `check_in_appointment` có `FOR UPDATE`.
`v_viec_cskh` dùng giờ VN và tự đóng việc khi lịch huỷ / check-in / đã qua.

**1.1 · CAO · `services/booking_service.py:324–425` (`TRANSITIONS`) — "Không đến" và "Huỷ lịch" là thao tác KHOÁ CỨNG.**
`no_show` đưa lịch sang `NO_SHOW`, `cancel` đưa sang `CANCELLED`. Trong bảng `TRANSITIONS` **không chuyển tiếp nào
đi ra** từ hai trạng thái này. Grep toàn `src/clinicai` không thấy đường khôi phục khác: `hoan_tac_service` chỉ mở lại lượt đã check-out.
*Vì sao sai:* trái luật CLAUDE.md mục 7, "mọi thao tác nhân viên bấm phải hoàn tác được".
*Tái hiện:* lễ tân bấm nhầm "Không đến" cho lịch 9:00, khách tới lúc 9:10. Không nút/API nào đưa lịch về `CONFIRMED`.
Lễ tân phải đặt lịch mới, kéo theo nhiều hệ quả:
- mất liên kết `lich_truoc_id` / `hen_tu_visit_id` / đợt điều trị;
- khung có thể đã bị người khác lấy;
- sinh lại việc "Gọi xác nhận lịch";
- việc "Hỏi lý do huỷ" của CSKH còn treo.

*Độ chắc:* đã lần theo code, chắc chắn.
*Test:* `no_show` rồi gọi hành động khôi phục, kỳ vọng `CONFIRMED`; `cancel` rồi khôi phục, kỳ vọng `cancelled_at`, `ly_do_huy_ma` = NULL.
Khôi phục vào khung đã đầy phải trả 409, không 500.
*Hướng sửa:* thêm chuyển tiếp `khoi_phuc` (NO_SHOW/CANCELLED → CONFIRMED, quyền `booking.manage`, qua `_guard_slot`).
Trigger sẽ tự kiểm lại ghế vì `OLD` là trạng thái chết. Xoá các cột `cancelled_*`, ghi nhật ký, phát sự kiện.

**1.2 · vừa · `booking_service.py:2449–2510` (`_slot_full`) — Python chặn lịch "chưa phân bác sĩ", trong khi trigger và lưới cho qua.**
Trigger (20260915000017 dòng 33): `IF NEW.doctor_id IS NULL AND NOT v_walkin THEN RETURN NEW` — lịch chưa có bác sĩ
không chiếm ghế. `_slot_full` không có nhánh này, nên vẫn đếm bằng `slot_seats_used(..., doctor_id=NULL)`. Hàm đếm SQL coi
NULL là một "bác sĩ" `'~none~'` (20260915000014 dòng 50–51), nên các lịch chưa phân bác sĩ chiếm chỗ lẫn nhau.
`capacity_service.tran_co_chan` (:516) lại trả `regular_chan=False` cho hàng "Chưa phân bác sĩ".
*Tái hiện:* tuần đã công bố lịch trực, khung 09:00 đã có 2 lịch chưa phân bác sĩ. CSKH đặt lịch thứ 3 không chọn bác sĩ:
lưới hiện ô trống, bấm thì nhận 409 "Khung 09:00–09:15 đã đủ 2 chỗ đặt hẹn".
*Độ chắc:* đã lần theo code. *Test:* `BookingService.create` 3 lần với `doctor_id=None`, tuần có `roster_week`, kỳ vọng cả 3 thành công.
*Sửa:* đầu `_slot_full` thêm `if doctor_id is None and not is_walkin(channel): return None`.

**1.3 · vừa · `booking_service.py:1785–1890` (`reschedule`, `reassign` trong `_build_patch`) và `doi_lich_nhanh.py:1209` — bỏ qua luật "khách mới phải khám bác sĩ X".**
`_luat_bac_si_bat_buoc` chỉ được gọi ở `create` (:640), `doi_dich_vu_kham` (:1401) và `assign_doctor` (:1813).
*Tái hiện:* dịch vụ S có luật chặn cứng "khách mới → BS A". Đặt với BS A (qua). Sau đó dời lịch, hoặc bấm "Đổi lịch tại chỗ",
chọn BS B: lưu thành công, luật bị lách.
*Độ chắc:* đã lần theo code (bản báo của agent, tôi chưa mở từng nhánh). *Test:* test DB như trên, kỳ vọng 409.
*Sửa:* gọi luật trong `_guard_slot` khi `doctor_id` hoặc `service_type_id` đổi. Một chỗ phủ cả bốn đường.

**1.4 · vừa · `services/capacity_service.py:119–131, 265–279` và `doi_lich_nhanh.py:208/218` — lưới hiểu "đã xếp ca" theo NGÀY, luật đặt lịch hiểu theo TUẦN đã công bố.**
`roster_known` của lưới = "hôm đó có dòng ca APPROVED". `_roster_warning` (booking_service.py:2349) lại dùng
"tuần đã công bố" (docstring ghi chính nghĩa theo ngày là lỗi đã sửa 24/09, nhưng mới sửa một phía).
*Tái hiện:* tuần đã công bố, Chủ nhật phòng khám mở nhưng không xếp ai. Lưới và popover Đổi lịch mời đặt mọi bác sĩ.
Bấm thì nhận 409 "BS X không có lịch làm việc ngày …". *Độ chắc:* chắc chắn (theo agent; tôi đã thấy điều kiện
`roster_week` ở capacity_service:265–270 tính theo ngày có ca). *Sửa:* `roster_known := tuan_lich_truc_da_cong_bo(ngày)`.

**1.5 · vừa · `api/v1/routers/booking.py:304–325` — màn "Lịch chờ xếp bác sĩ" sót lịch "mất bác sĩ" khi bác sĩ chỉ có ca CHƯA DUYỆT.**
Câu `NOT EXISTS (SELECT 1 FROM work_roster w …)` không lọc `w.status = 'APPROVED'`. Ca đăng ký của người không phải admin
được ghi `PENDING` (config_service.py:251), và còn có ca `REJECTED`. Trong khi đó quote / `_roster_warning` chỉ tính ca APPROVED.
*Tái hiện:* BS A chỉ có ca PENDING ngày 25/10, tuần đã công bố. Lịch của BS A ngày ấy **không** hiện "Mất bác sĩ",
trong khi lưới hiện BS A nghỉ và dời lịch vào BS A bị chặn. Không ai được nhắc xếp lại bác sĩ.
*Độ chắc:* đã lần theo code; tác động thật tuỳ prod có dòng PENDING/REJECTED không. *Sửa:* thêm `AND w.status = 'APPROVED'`.

**1.6 · vừa · nghi · `booking_service.py:345` (`checkin`) — check-in được lịch của ngày KHÁC.**
Chuyển tiếp `checkin` không kiểm ngày của `slot_start`. Chỉ `doi_lich_nhanh` có chốt "chỉ check-in luôn được khi đổi sang hôm nay" (:1241–1246).
*Tái hiện:* gửi `PATCH action=checkin` cho lịch ngày mai. Lượt khám mở hôm nay, nhưng số khám cấp theo dãy của ngày
mai (`check_in_appointment` lấy ngày của slot). *Độ chắc:* chắc ở backend; chưa kiểm màn có che nút với lịch khác ngày.
*Sửa:* chặn khi ngày slot ≠ `hom_nay_vn()`, hướng sang "Đổi & Check-in".

**1.7 · vừa · nghi (cần Tuyền quyết) · `booking_service.py:419` — dời được lịch đã CHECKED_IN sang ngày khác.**
`reschedule` nhận `_ALIVE`, trong đó có `CHECKED_IN`, và trigger miễn kiểm ghế cho CHECKED_IN. *Tái hiện:* khách đã check-in,
CSKH dời lịch sang tuần sau. Kết quả: lượt hôm nay vẫn mở, lịch nằm ở tuần sau với trạng thái CHECKED_IN.
Màn Lịch hẹn tuần sau hiện "đã tới", còn việc gọi xác nhận / nhắc hẹn không sinh. Hai màn mâu thuẫn nhau.
*Sửa:* từ CHECKED_IN chỉ cho dời trong cùng ngày, hoặc bắt hoàn tác check-in trước.

**1.8 · thấp · dời lịch không chặn trùng giờ cùng khách.** `_patient_double_booked` chỉ chạy ở `create` (:612). Dời lịch A
về đúng giờ lịch B của cùng khách thì có hai lịch sống cùng giờ. (Chống trùng chỉ ở Python, không ở DB, là **đã biết**;
mới ở đây là đường dời lịch không có cả chốt Python.)

**1.9 · thấp · cần Tuyền quyết · `v_viec_cskh` nhánh `CHO_XAC_NHAN` (migration 20261015110000) — đã xác nhận một lần là đóng vĩnh viễn.**
Lịch đã gọi xác nhận, sau đó bị dời sang tuần khác: việc "Gọi xác nhận" không mở lại cho ngày mới. Nên so thời điểm
lần chạm với lần dời gần nhất (`appointment_doi_lich`).

**1.10 · thấp · `services/clinic_policy.py:197` `except Exception: pass` trong `load_effective_policy`.** Cùng họ với
`:163` (**đã biết**). Riêng ở đây: nếu câu SQL lỗi giữa giao dịch của `create()`, giao dịch đã hỏng, câu kế tiếp nổ
`InFailedSQLTransaction` thành 500, và lỗi gốc bị che. Sửa: bọc bằng `SAVEPOINT` hoặc để lỗi nổi lên.

**1.11 · thấp · nghi · `capacity_service.py:367–380` — lưới sinh khung từ giờ mở cửa, trigger cắt khung theo epoch.**
Hai cách cắt chỉ lệch khi giờ mở cửa không chia hết độ dài khung (vd luật bác sĩ khung 60′, mở 07:30). Không chỗ nào ép
hai thứ khớp nhau. Dr4Women khung 15′ hiện không dính.

## Nhóm 2 — Tiếp đón, check-in, xếp phòng, check-out, mở lại lượt

> **Thuật ngữ.** *Lượt khám* (`visit`) = một lần khách tới phòng khám. *Hàng chờ* (`queue_entry`) = chỗ của khách ở một phòng,
> trạng thái `waiting / called / serving / left / cancelled`. *Hoàn tác check-in* đưa lịch về `CONFIRMED` và lượt về
> `INCOMPLETE` (lượt không bị xoá).

**Đã soát, ổn:**
- Hai lễ tân check-in cùng lúc: `check_in_appointment` có `FOR UPDATE` + khoá advisory, người sau nhận 409.
- Cấp số tiếp đón / số khám: khoá advisory, ngày theo giờ VN.
- Hai phòng cùng "Nhận" một khách: `khoa_luot` nối tiếp hai lệnh, người sau nhận `KHACH_O_PHONG_KHAC`.
- Hoàn tác Nhận: có.
- Lịch trực chỉ dùng để xếp hạng phòng, không phải điều kiện. Không phòng nào nhận được thì chuông "chờ xếp phòng" kêu ở quầy, không có khách bị bỏ rơi im lặng.
- Check-out khoá lượt rồi mới tính vướng.
- Lọc cơ sở ở mọi danh sách: Tiếp đón, `/queue`, Check-out, lượt treo, hành trình.
- Trigger `chan_phong_khac_co_so` chặn xếp khách sang phòng cơ sở khác.

**2.1 · CAO · Hoàn tác check-in xong, dòng Tiếp đón ghi "Về giữa chừng hh:mm", mất nút Check-in, hiện nút "Mở lại lượt".**
- `services/booking_service.py:2813–2832`: hoàn tác đặt lượt `INCOMPLETE` + `incomplete_at = now()`, **giữ nguyên `checked_in_at`**.
- `services/tiep_don_service.py:228–246`: câu đọc lấy lượt theo `appointment_id`, kèm `checked_in_at` và `ve_luc = coalesce(closed_at, incomplete_at)`.
- `tiep_don_service.py:151`: chỉ coi "Chưa đến" khi `check_in` **không** phải datetime. Ở đây nó là datetime, nên rơi xuống `:163–166`
  (`visit_status in VISIT_DA_RA_VE`) → chip `loai="ve"`, chữ **"Về giữa chừng 09:12"**, nhóm "Đã đến".
- `:345` `check_in_duoc` = False (nhóm không phải `chua_den`); `:351` `mo_lai_duoc` = True.

*Vì sao sai:* lịch đã về `CONFIRMED`, nhưng chip đọc giờ check-in và trạng thái của lượt cũ. Chú thích ở `QueueBoard.tsx:181`
hứa "check-in nhầm → về Chưa đến"; thực tế màn không về Chưa đến. Khách **kẹt**: không check-in lại được từ màn Tiếp đón.
*Tái hiện:* check-in khách DEMO → bấm "Hoàn tác" → màn tự nạp lại → chip "Về giữa chừng 09:12", không có nút Check-in,
có nút "Mở lại lượt". Bấm "Mở lại lượt" (`hoan_tac_service.py:1205`, nhận mọi lượt INCOMPLETE) thì lượt thành IN_PROGRESS,
nhưng lịch vẫn CONFIRMED (`:254–266` chỉ sửa lịch COMPLETED → CHECKED_IN). Hàng chờ đã `cancelled` không được dựng lại.
Kết quả: khách "đang trong lượt" mà không ở hàng nào, và Hoàn tác check-in cũng hết làm được vì lịch không còn CHECKED_IN.
*Độ chắc:* đã lần theo code, chắc chắn. `test_tiep_don_service.py` không có ca "lịch CONFIRMED + lượt INCOMPLETE".
*Test:* (a) unit `dung_dong` với `status=CONFIRMED, visit_status=INCOMPLETE, checked_in_at, ve_luc` có giá trị → kỳ vọng
`nhom="chua_den"`, `check_in_duoc=True`, `mo_lai_duoc=False`. (b) test DB: check-in → `undo_checkin` → `TiepDonService.hom_nay`.
*Sửa:* trong `trang_thai`/`dung_dong`, khi lịch thuộc `CHO_CHECK_IN` thì bỏ qua lượt (coi `check_in=None`). Thêm
`mo_lai_luot` từ chối lượt INCOMPLETE có `closed_at IS NULL` (xem 2.5).

**2.2 · vừa · `services/checkout_service.py:85–87, 410–419` — lượt bị hoàn tác check-in nằm mãi ở danh sách Check-out, và "check-out" được khách chưa từng đến.**
`already_closed` chỉ đúng khi bước `LUOTKHAM-15` ở COMPLETED, mà bước này đã bị huỷ lúc hoàn tác. `pending_list` chỉ loại
`FINALIZED`, nên vẫn lấy lượt INCOMPLETE. `close` (`:792–813, 1012`) đặt `closed_at` và phát `visit.checked_out`. Sự kiện này kéo theo
H6 báo chuông CSKH "khách về còn việc dở", và dòng vẫn ở mục chưa đóng vì `already_closed` vẫn false.
Bảng `/hanh-trinh` thì ghi lượt này "Bỏ về giữa chừng" (`bang_hanh_trinh_service.py:59`). Ba màn nói ba điều khác nhau.
*Tái hiện:* check-in → hoàn tác → mở `/reception/checkout` → khách hiện ở "chưa đóng". Bấm Check-out → báo thành công,
tải lại vẫn còn. *Độ chắc:* đã lần theo code. *Test:* undo → `pending_list` không chứa lượt.
*Sửa:* `pending_list` thêm điều kiện `(v.status IN ('OPEN','IN_PROGRESS') OR v.closed_at IS NOT NULL)`. `close` coi lượt INCOMPLETE
chưa có `closed_at` là `already_closed`.

**2.3 · vừa · chỉ định đã có phòng bị KẸT sau hoàn tác check-in rồi check-in lại.**
Diễn biến theo code:
1. Lúc check-in, H2 mang chỉ định đã trả từ lượt trước sang, `tu_xep_da_thu` gán phòng (`events/consumers/hanh_trinh.py:107–117`,
   `service_routing_service.py:1683`).
2. Hoàn tác vẫn được, vì `hoan_tac_check_in.py:65–69, 86` bỏ qua chỉ định mang sang.
3. Hoàn tác huỷ `queue_entry` (booking_service.py:2839–2848), nhưng `service_order` giữ `routing_status=ASSIGNED`, `room_id`.
4. Check-in lại: `mang_sang_luot_moi` không động tới (chỉ định đã ở lượt này), `tu_xep_da_thu` chỉ lấy UNASSIGNED.
5. Xếp tay đúng phòng ấy: `_gan` rơi vào nhánh "cùng phòng" (`service_routing_service.py:1402–1427`) và trả về luôn, không tạo chỗ chờ.

*Tái hiện (dây H4 tự xếp phòng bật):* khách có siêu âm đã trả từ hôm trước → check-in (tự xếp SA1) → Hoàn tác → Check-in lại →
`/hanh-trinh` ghi "Chờ làm Siêu âm ở SA1", nhưng hàng chờ SA1 trống. Xếp lại vào SA1 cũng không đổi gì.
*Độ chắc:* đã lần theo code (agent); tôi chưa mở `_gan`. *Test:* test DB chỉ định mang sang + H4 → undo → check-in → có queue_entry sống.
*Sửa:* khi hoàn tác check-in, đưa chỉ định có chỗ chờ vừa huỷ về UNASSIGNED. Hoặc trong `_gan`, nhánh cùng phòng mà không có chỗ chờ sống thì vẫn tạo chỗ.

**2.4 · vừa · `booking_service.py:376–382, 1040, 2839–2847` — huỷ lịch đã CHECKED_IN không chặn khi khách đang làm dịch vụ, và không hoàn tác được.**
`cancel` nhận cả CHECKED_IN. Chỉ `undo_checkin` mới hỏi `chan_hoan_tac_neu_da_lam`. Đoạn dọn hàng chờ bỏ qua `serving`.
*Tái hiện:* khách đang làm siêu âm (serving) → quản lý Huỷ lịch → lượt INCOMPLETE, phòng SA1 vẫn thấy khách "đang làm".
Lịch CANCELLED không có đường khôi phục (cùng gốc với 1.1). *Độ chắc:* chắc ở backend; chưa kiểm màn nào mở nút Huỷ cho lịch đã check-in.
*Sửa:* áp `chan_hoan_tac_neu_da_lam` cho `cancel` khi lịch đang CHECKED_IN, hoặc chỉ cho huỷ trước khi khách đến.

**2.5 · vừa · `services/hoan_tac_service.py:1205` — "Mở lại lượt" nhận cả lượt INCOMPLETE sinh từ hoàn tác check-in / huỷ lịch.**
Điều kiện `closed_at IS NULL AND status <> 'INCOMPLETE'` → mọi INCOMPLETE đều qua. Hệ quả: lượt IN_PROGRESS trong khi lịch
CONFIRMED hoặc CANCELLED, hàng chờ không dựng lại. Màn chỉ tới được qua lỗi 2.1; gọi API tay thì tới được cả với lịch đã huỷ.
*Sửa:* đòi `closed_at IS NOT NULL`, hoặc `incomplete_reason` phải đến từ check-out "về giữa chừng".

**2.6 · thấp · `booking_service.py:2648–2655` — check-in lại sau hoàn tác giữ `thu_tu_tay_ms` cũ, khách vượt hàng.**
`DO UPDATE` đặt lại `checked_in_at` nhưng không xoá mốc kéo tay. Mốc này được ưu tiên khi xếp (`thu_tu_kham_service.py:66`).
*Tái hiện:* kéo khách lên đầu → hoàn tác → 1 giờ sau check-in lại → khách đứng trước những người đến trong 1 giờ ấy.
*Sửa:* xoá `thu_tu_tay_*` trong `DO UPDATE`.

**2.7 · thấp · `sinh_hieu_service.py:146` — điều dưỡng "Bắt đầu đo" được trên lượt vừa bị hoàn tác check-in.**
`khoa_luot(..., cho_phep_ve_giua_chung=True)`. Khoá cùng thứ tự nên không đè nhau, nhưng hoàn tác vào trước thì điều dưỡng vẫn
được báo OK trên lượt INCOMPLETE. *Sửa:* lệnh Bắt đầu (khác sửa số đo) từ chối lượt INCOMPLETE chưa có `closed_at`.

**2.8 · thấp · nghi · check-in lại sau hoàn tác không đặt lại trạm đầu.** `current_node_code` cũ còn (vì `cap_nhat_vi_tri` bỏ qua
lượt INCOMPLETE), `place_visit_at_first_station` (`20261008700000_co_so_hien_hanh.sql:94–99`) thấy đã có vị trí nên bỏ qua.
Bảng Trưởng ca có thể chỉ sai phòng.

**2.9 · thấp · ngày cực biên gây 500.** `GET /hanh-trinh/hom-nay?ngay=9999-12-31`: `bang_hanh_trinh_service.py:36,147`
cộng một ngày → `OverflowError`. `lich_phong_service.doc_tuan("9999-12-31")` (`:67–68`) cũng vậy. Ngày đúng cú pháp nên qua
bộ đọc, nhưng nổ khi cộng. *Sửa:* bắt `OverflowError`, hoặc chặn năm > 2100 ở `doc_ngay_xem`. *Test:* hai hàm với `9999-12-31` không ném.

**2.10 · thấp · cần Tuyền quyết · lệnh GHI không kiểm cơ sở của người bấm.** `CheckoutService.close`, `mo_lai_luot`, hoàn tác
check-in, hoàn tác Nhận nhận `visit_id` của bất kỳ cơ sở nào trong cùng phòng khám. Danh sách đã lọc cơ sở, nên chỉ lộ khi
gọi API thẳng hoặc mở liên kết. Theo thiết kế hiện tại (`identity.py:345`: cơ sở là *bộ chọn*, không phải *thẩm quyền*) thì đây không
phải lỗ quyền. Ghi lại để Tuyền chốt khi có phòng khám thứ hai dùng chung hệ thống.

## Nhóm 3 — Bàn khám, Bàn tư vấn, chỉ định, Hoàn tất khám, liệu trình

> **Thuật ngữ.** *Phiên khám* (`consultation`) = một lần bác sĩ hoặc tư vấn ngồi với khách, trạng thái `queued → in_progress → completed`.
> *Vòng đọc* (`review_round`) = lượt chờ kết quả cận lâm sàng về để bác sĩ đọc. Mỗi kết quả cần chờ là một *yêu cầu* (`round_requirement`).
> *Khám xong hẳn* = mốc `exam_completed_at`, do `_ket_thuc_neu_xong` ghi khi không còn gì giữ lượt. Lúc đó lịch hẹn thành COMPLETED.

**Đã soát, ổn:**
- Liệu trình (trigger bản 20261009145151 / 20261009900000): không đếm buổi hai lần nhờ khoá duy nhất. Huỷ / không làm / không chọn thì tự gỡ buổi, sống lại thì tự gắn lại. `lieu_trinh` khoá `FOR UPDATE` khi hai phòng cùng ghi. Tiền trả trước có trigger gác.
- `mang_sang_luot_moi` không nhân đôi: `FOR UPDATE` và kiểm lại sau khi chờ khoá.
- Bác sĩ sửa chỉ định cùng lúc thu ngân thu: mọi lệnh khoá `visit` trước rồi mới khoá chỉ định.
- Hoàn tất khám **có** hoàn tác (`mo_lai_kham`).
- Bỏ chỉ định đang làm / đã xong bị chặn đúng.
- Không có `date.today()` / `CURRENT_DATE` trong các tệp thuộc phạm vi.
- Bàn khám lọc cơ sở đúng.

**3.1 · CAO · Hoàn tác "bỏ chỉ định" KHÔNG trả lại yêu cầu "cần kết quả" → kết quả xét nghiệm có thể không bao giờ về bác sĩ đọc.**
- `services/hoan_tac_service.py:824–833`: `huy_chi_dinh` **DELETE** `round_requirement` của chỉ định ở mọi vòng đọc chưa đóng.
- `:834–841`: huỷ `follow_up_case` OPEN.
- `:847–849`: `_evaluate_rounds` đóng vòng rỗng, rồi `_ket_thuc_neu_xong` khép lượt.
- `services/so_sua_chi_dinh_service.py:754–850` (`_dat_lai_chi_dinh`, đường Hoàn tác ở sổ sửa chỉ định) chỉ đưa
  `service_order` về `authorized`. Grep cả tệp **không có** `round_requirement` hay `follow_up_case`. `mo_lai_moc_kham_xong` + `_evaluate_rounds` (:720)
  chỉ xét vòng `collecting/ready`, không mở lại vòng đã đóng.

*Tái hiện:*
1. Bác sĩ "Đã khám xong" khi còn xét nghiệm X gửi ngoài cần kết quả → mở vòng 2, yêu cầu X.
2. Trưởng ca bỏ nhầm X → vòng 2 rỗng, đóng; lượt "khám xong hẳn".
3. Bấm Hoàn tác ở sổ sửa chỉ định → X sống lại, mốc khám xong mở lại, nhưng vòng 2 vẫn đóng và không còn yêu cầu X.
4. X làm xong, kết quả về → lượt tự khép. Bác sĩ **không bao giờ** thấy "Kết quả cần đọc", quầy check-out không cảnh báo.

Đây đúng là dạng "hoàn tác không trả lại đủ trạng thái", và ảnh hưởng an toàn người bệnh.
*Độ chắc:* đã lần theo code, chắc chắn (tôi đã mở hai đoạn trên).
*Test:* khám xong (X cần kết quả) → `huy_chi_dinh(X)` → `SoSuaChiDinhService.hoan_tac` → còn một vòng chưa đóng có yêu cầu X `open`.
X xong mà chưa có kết quả thì `exam_completed_at` vẫn NULL.
*Sửa:* lúc bỏ, lưu yêu cầu bị xoá (round_id, need, status) và id việc theo dõi vào `so_sua_chi_dinh.chi_tiet`. Lúc hoàn tác: dựng lại
yêu cầu, mở lại vòng nếu nó đóng vì rỗng (về `collecting`), mở lại việc theo dõi đã huỷ.

**3.2 · vừa · `services/luot_kham_service.py:1874, 1913` — "Bắt đầu khám" (nhận khách vào khám / tư vấn) không có hoàn tác.**
Phiên chuyển `in_progress`, `_block_others` chặn chỗ chờ ở phòng khác. Không lệnh nào đưa phiên về `queued`; `mo_lai_kham` chỉ nhận phiên `completed`.
*Tái hiện:* bác sĩ bấm Bắt đầu nhầm khách A (trùng tên) → A "đang khám", các chỗ chờ khác của A bị chặn. Hoàn tác check-in, đổi
dịch vụ khám, bỏ qua tư vấn đều bị từ chối vì có phiên khám. Lối duy nhất là Hoàn tất khám, tức đóng sai phần khám.
*Độ chắc:* chắc chắn (agent). *Sửa:* lệnh `huy_nhan_kham` khi phiên chưa có ghi chú / chỉ định, giống `huy_bat_dau` của dịch vụ.

**3.3 · vừa · `services/service_execution_service.py:648–760` — phòng bấm "Không làm được" không có hoàn tác trực tiếp.**
Chỉ định sang `NOT_PERFORMED`, hàng chờ đóng, buổi liệu trình bị gỡ. "Gián đoạn" có Làm lại, "Không làm" thì không.
Thêm nữa, `dieu_tri_ban_kham.py:507–513` (`chi_dinh_dieu_tri_dang_co`) coi chỉ định `not_performed` là "đã có", nên bác sĩ kê lại thì
nhận lại đúng chỉ định chết (`da_co_san`), không tạo dòng mới.
*Đường vòng hiện có:* bỏ chỉ định (đã thu thì thành tiền thừa) rồi Hoàn tác bỏ. Vòng vèo, và dính 3.1.
*Sửa:* lệnh `hoan_tac_khong_lam` khi chưa có lần làm; lọc `not_performed` khỏi `chi_dinh_dieu_tri_dang_co`.

**3.4 · vừa · `luot_kham_service.py:2984–3030` — "Miễn" / "Chuyển theo dõi" một yêu cầu vòng đọc không hoàn tác được.**
Ghi `waived`/`follow_up`, rồi `_evaluate_rounds` có thể đóng vòng, `_ket_thuc_neu_xong` khép lượt (:3043). Không lệnh nào trả yêu cầu về `open`.
*Tái hiện:* bác sĩ bấm Miễn nhầm kết quả X → khách "khám xong". Muốn quay lại phải Hoàn tác cả phiên khám chính: việc này xoá mọi vòng sau.
*Sửa:* lệnh `bo_quyet_yeu_cau` (yêu cầu về `open`, huỷ `follow_up_case` vừa mở, mở lại vòng, `mo_lai_moc_kham_xong`).

**3.5 · vừa · `services/service_selection_service.py:504–517` (`ap_lua_chon`) — quầy tick lại dịch vụ đã bỏ sau khi lượt "khám xong hẳn" thì mốc không mở lại.**
Đổi NOT_SELECTED → SELECTED mà không gọi `mo_lai_moc_kham_xong`. Consumer vòng đọc (`events/consumers/vong_doc.py:97`) chỉ khép, không mở.
Cùng kiểu ở `lam_them_tai_quay_service.py:722`.
*Tái hiện:* bác sĩ Hoàn tất khi X còn chờ → quầy bỏ X → lượt khép (lịch COMPLETED) → khách đổi ý, quầy tick lại X, thu tiền → X vào
hàng phòng. Nhưng Trang chủ, Hành trình, lịch hẹn vẫn "Khám xong": **mâu thuẫn giữa các màn**.
*Test:* khép lượt → NOT_SELECTED rồi SELECTED → `exam_completed_at IS NULL`, lịch về CHECKED_IN.
*Sửa:* trong `ap_lua_chon`, có id chuyển sang SELECTED thì gọi `mo_lai_moc_kham_xong`.

**3.6 · vừa · cần Tuyền quyết · `luot_kham_service.py:1133–1140` — lượt Điều trị không bao giờ "khám xong hẳn" nếu bác sĩ không nhận.**
`_ket_thuc_neu_xong` đòi có phiên `completed` và không còn phiên `queued`. Lượt Điều trị luôn có phiên PRIMARY `queued` (hàng bác sĩ tuỳ chọn).
`checkout_service.py:115–120` đã miễn trường hợp này, còn `_ket_thuc_neu_xong` thì không.
*Tái hiện:* khách Điều trị làm xong buổi ở phòng → khách vẫn nằm ở hàng bác sĩ "chờ khám", lịch "đang khám" tới khi check-out.
*Sửa (nếu Tuyền đồng ý):* áp cùng ngoại lệ DIEU_TRI vào `_ket_thuc_neu_xong`, đóng chỗ chờ PRIMARY `queued` khi khép.

**3.7 · thấp · `src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:952–958` — giao diện tự suy chế độ Hoàn tất bằng luật khác backend.**
TSX đếm mọi chỉ định `authorized/assigned/in_progress`. Backend `kham_xong` (`luot_kham_service.py:1620–1635`) dùng `CHI_DINH_CON_VIEC_SQL`,
loại NOT_SELECTED, đã miễn, làm thêm tại quầy. *Tái hiện:* trợ lý, chỉ còn dịch vụ khách đã bỏ → màn ghi "Khách còn chỉ định sẽ sang
hàng chờ phòng", backend trả 403. Không hỏng dữ liệu, chỉ sai câu. Đây cũng là **luật nghiệp vụ trong TSX** (trái CLAUDE.md).
*Sửa:* backend trả `che_do_hoan_tat`, TSX chỉ vẽ.

**3.8 · thấp · nghi · `luot_kham_service.py:1133–1136` — `_ket_thuc_neu_xong` tính cả phiên TƯ VẤN là "đã khám".**
Phiên PRIMARY chỉ được tạo bất đồng bộ khi consumer H3 nhận `consultation.handed_over` (`hanh_trinh.py:200`). Trong khoảng hở ấy
(hoặc H3 lỗi và thử lại), một lệnh gọi khép có thể đánh lượt "khám xong hẳn" khi bác sĩ chính chưa khám. Cửa sổ hẹp.
*Sửa:* điều kiện EXISTS thêm `c.kind <> 'TU_VAN'`.

**3.9 · thấp · `hoan_tac_service.py:1023–1027`, `service_execution_service.py:1698–1700` — hoàn tác rồi khép lại thì phát `visit.exam_completed` lần hai và đè giờ.**
`mo_lai_moc_kham_xong` đặt NULL, rồi `_ket_thuc_neu_xong` ghi `now()` mới. Hiện chỉ dòng thời gian nghe sự kiện này, nên chỉ lệch giờ và trùng mốc.
