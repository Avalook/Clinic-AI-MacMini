# Soát hệ thống 22/10/2026 · Khối 3 — Lịch + Hành trình

> Soát CHỈ ĐỌC trên nhánh `main` (@00bde52). Đang viết dần — các nhóm phát hiện
> sẽ được thêm theo từng lượt commit.

## Phạm vi

Đặt lịch (3 nơi ghi lịch, sức chứa, gọi xác nhận, Không đến), tiếp đón / check-in,
xếp phòng theo lịch trực, nhận khách tại phòng, Bàn khám / Bàn tư vấn, chỉ định,
Hoàn tất khám, check-out, mở lại lượt, liệu trình, đa cơ sở.

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
