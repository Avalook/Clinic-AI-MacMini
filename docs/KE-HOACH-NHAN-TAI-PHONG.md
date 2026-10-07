# Kế hoạch: Nhận khách tại phòng dịch vụ (Tuyền chốt 07/10/2026)

Yêu cầu quản lý mục 7: phòng dịch vụ hiện số đang chờ / đang làm; check-in ở mỗi
phòng để ghi nhận người xếp giấy chờ khám. Nhánh `claude/service-room-assignment-flow-d71f40`,
migration dải `20261007500000`, cổng API/web 8251/3251.

## Luật đã chốt

1. **Một công tắc** `nhan_tai_phong` (/settings/day-noi, code mặc định TẮT — tắt là y
   như cũ). BẬT: worker không tự xếp phòng; quầy thu/bàn khám chọn phòng chỉ là
   **hướng dẫn**; danh sách "Sắp đến" hiện khách ngay sau khi BS chỉ định.
2. **Sắp đến → [Nhận vào phòng này] → Đang chờ → [Bắt đầu làm] → Đang làm → [Xong]**,
   lặp qua từng phòng, về BS chính bấm "Bắt đầu khám" lần 2. ~~Nhận theo KHÁCH~~ →
   **Nhận theo từng CHỈ ĐỊNH** (sửa 07/10, mục cuối). Phòng nhiều BS: ô chọn BS cạnh nút Nhận.
3. Khách **chưa chốt ở quầy** vẫn hiện ở Sắp đến và Nhận được; **Bắt đầu làm** vẫn theo
   luật thu trước – làm sau / tick "Làm trước – thu sau". Quầy bỏ dịch vụ → tự rời hàng.
4. **Không khoá cứng — nhận chéo:** B luôn nhận được, chỉ một nút xác nhận, không bắt
   chọn lý do. Áp theo CHỈ ĐỊNH ĐƯỢC TICK (07/10).
   - Chỉ định được tick đang CHỜ ở A → rời hàng A. Chỉ định không tick ở A: không đụng.
   - Khách đang LÀM ở A (A quên Xong) → đóng hàng chờ A, **lượt làm của A giữ mở**,
     thẻ ở A gắn nhãn đỏ "Khách đã sang phòng B lúc …"; A tự bấm Xong / Gián đoạn.
     Hệ thống không đoán thay A. (Bỏ hành vi cũ ở `service_execution_service.py`
     ~1200 kéo dịch vụ A về PENDING.)
   - Sổ ghi: phòng cũ, trạng thái cũ, ai bấm Nhận/Bắt đầu ở A + lúc nào, ai nhận ở B
     + lúc nào; A bấm Xong muộn → giờ bấm và mốc "khách rời" nằm riêng.
5. **Hướng dẫn phòng = nháp** (`phong_du_kien_id`, lệnh `dat_phong_du_kien` có sẵn):
   không bắt buộc, không bao giờ xếp thật khi công tắc bật. Phiếu hướng dẫn in phòng đã
   chọn, chưa chọn in "các phòng làm được". Phòng được hướng dẫn: khách lên đầu Sắp đến,
   nhãn "được hướng dẫn đến đây". Thứ tự hướng dẫn = thứ tự dòng trên phiếu. Khi nhận,
   sổ ghi đối chiếu hướng dẫn ↔ thực tế (phòng và thứ tự).
6. Khách đang ở phòng A: list Sắp đến các phòng khác + list BS chính ở bàn khám hiện
   "đang chờ / đang làm ở phòng A".
7. Ô mỗi phòng ở `/phong`: **sắp đến · đang chờ · đang làm**, tự cập nhật.
7b. **Bỏ nút Nhả (Tuyền chốt với quản lý 07/10) — chỉ ghi sự kiện THẬT người bấm.**
    Nhân viên quên thì kệ, hệ thống không suy diễn / tự "đưa sẵn giải pháp". Không có
    nút Nhả, không hoàn tác Nhả, Xong KHÔNG tự nhả chỉ định khác. Khách rời hàng một
    phòng (`service.room_released`) chỉ khi: `NHAN_CHEO` (phòng khác bấm Nhận) hoặc
    `BO_DICH_VU` (quầy bỏ dịch vụ). Ô "đổi phòng" của trưởng ca khi dây bật = CHỈ ghi
    hướng dẫn; khách sang phòng mới thì phòng ấy nhận chéo. Nhãn đỏ "Khách đã sang
    phòng B lúc …" trên thẻ đang làm ở A giữ nguyên (không thêm chuông).
    Thời gian: chờ = Nhận→Bắt đầu; khám = Bắt đầu→Xong; đi lại = Xong/rời→Nhận phòng sau.
8. **Mọi nút hoàn tác được:** Nhận → về Sắp đến, theo từng chỉ định vừa nhận (không
   đẻ việc trưởng ca như `invalidate`); Bắt đầu → về Đang chờ (có sẵn); Xong (có sẵn).
9. **Không cái gì sau đè cái trước:** cột giờ trên bảng = giá trị hiện tại; lịch sử đủ ở
   `domain_event` (chỉ thêm). Mọi lệnh đổi cột giờ trong phạm vi này phải phát sự kiện.
   Vá: `serving_at` khi khám lần 2 (`luot_kham_service.py` nhánh quay lại →
   `consultation.resumed`), `phong_du_kien_id` (mỗi lần đặt/đổi/bỏ một sự kiện), soát
   `eligible_at` khi rời phòng.
10. View `v_moc_hanh_trinh`: mỗi mốc một dòng (lượt, chỉ định, phòng, loại mốc, giờ,
    người, mốc bị hoàn tác, hướng dẫn ↔ thực tế) cho AI phân tích.

## Chỗ sửa

**PR 1 — backend + migration**

| File | Sửa |
|---|---|
| `services/day_noi.py` | dây `nhan_tai_phong` |
| `events/consumers/hanh_trinh.py` (98-157) | dây bật → bỏ `tu_xep_da_thu`, giữ việc khác |
| `services/service_routing_service.py` | `cho_nhan_vao_phong` → sắp đến (gồm chưa chốt, theo khách, `dang_o_phong`, hướng dẫn lên đầu); `_gan` nới SELECTED cho nguồn `TAI_PHONG`; mới `nhan_vao_phong` (nhận chéo), `hoan_tac_nhan`; `dat_phong_du_kien` chỉ ghi hướng dẫn + phát sự kiện |
| `services/service_execution_service.py` (~1200) | nhận chéo khi đang làm: đóng hàng A, giữ lượt làm A |
| bỏ chọn dịch vụ ở quầy (`bill_service`) | chỉ định đã nhận bị bỏ → đóng hàng chờ |
| `services/luot_kham_service.py` (1742) | `consultation.resumed`, không mất mốc lần 1 |
| `services/luot_kham_doc.py` | `phong_hom_nay` 3 số; `hang_cho` kèm `dang_o_phong` |
| `events/catalogue.py`, `modules.py`, `audit_labels.py`, `consumers/dong_thoi_gian.py` | sự kiện: nhận, hoàn tác nhận, nhận chéo, khám lại, hướng dẫn phòng |
| `api/v1/routers/luot_kham.py` | route mỏng `nhan-vao-phong`, `hoan-tac-nhan` |
| `supabase/migrations/20261007500000_moc_hanh_trinh.sql` | view `v_moc_hanh_trinh` (+ index nếu thiếu) |

**PR 2 — giao diện (dựng trên PR 1, merge cùng đợt)**

| File | Sửa |
|---|---|
| `phong/page.tsx` | 3 số + `LiveBoardSync` |
| `phong/[ma]/ChuaXepPhong.tsx` → khối Sắp đến | theo khách, nhãn "đang ở phòng X"/"được hướng dẫn", Nhận/Hoàn tác, chọn BS, xác nhận nhận chéo |
| `phong/[ma]/PhongDichVu.tsx` | đếm khớp 3 số; nhãn đỏ "khách đã sang phòng B" |
| `ban-kham/BanKham.tsx` (~1056) | "đang chờ/làm ở phòng X" thay câu cứng |
| `_lam-viec/DoiPhong.tsx`, khối phòng quầy thu | dây bật → nhãn "Hướng dẫn phòng (không bắt buộc)" |
| `app/api/luot-kham/route.ts`, `_lam-viec/hoan-tac.ts` | 2 mã lệnh |

**Còn sống khi dây tắt (có test):** quầy đổi phòng, trưởng ca điều phối, TV
`/display?phong=`, Hành trình, phiếu hướng dẫn, chuông chờ xếp phòng.

## Kiểm

1. Đang làm: hook ruff + LSP; test liên quan trên `chung_test_db`.
2. `test_nhan_tai_phong_db.py`: sắp đến sau chỉ định; Nhận→Bắt đầu→Xong→Nhận phòng 2;
   nhận chéo khi chờ / khi làm (lượt A giữ mở, sổ ghi người A); hoàn tác Nhận về Sắp đến,
   không đẻ việc; khám lần 2 giữ mốc 1; hướng dẫn đổi 2 lần → 2 sự kiện; đối chiếu
   hướng dẫn ↔ thực tế; quầy bỏ dịch vụ → rời hàng; dây tắt = y cũ; hai người Nhận cùng
   lúc → một; view đủ mốc kể cả hoàn tác.
3. Chạy lại ~15 tệp test xếp phòng / thực hiện / hoàn tác + boundary giao diện, tsc, lint.
4. Diễn tập migration trong giao dịch → ROLLBACK trên `chung_test_db`.
5. CI một lần: `./scripts/ci-may.sh --bao-github` → PR có kịch bản bấm thử + bảng nút/link.
6. Bấm thật: Tuyền trên staging (memory 06/10 tiết kiệm token).

Ước: ~3,5–4h AI, ~7–9M token (phần lớn đọc lại cache).

## Phòng chuyên + nhận theo chỉ định, 07/10 (sau bấm thử staging)

**Lỗi thật:** khách 3 chỉ định — Soi cổ tử cung + Siêu âm 2D (quầy hướng dẫn Phòng siêu
âm 2 máy), Monitor sản khoa (→ Phòng thủ thuật). Phòng thủ thuật làm được cả ba node,
bấm Nhận (theo khách) gom cả ba; phòng siêu âm mất khách; thủ thuật hiện 3 dòng cho 1
khách ("1 đang chờ" mà "ĐANG CHỜ (3)"). Ô siêu âm hiện tiêu đề kiểu cũ thiếu "sắp đến"
vì phòng trống thì `hang_cho.dem` trả None (đã sửa: luôn có ba số).

**Tuyền chốt:**
1. **Phòng chuyên ★** = cột `clinic_room_node.chuyen` (migration
   `20261007510000_phong_chuyen.sql`, không seed). Hàm Postgres `phong_chuyen(...)` =
   `phong_lam_duoc` VÀ phòng ★ node ấy. Chỉ ở mức node — ngoại lệ dịch vụ đã có
   `clinic_room_service` thu hẹp phòng làm được, giao với ★ là đủ. Quản lý đánh ★ ở
   `/settings/clinic-config` (lệnh `PUT /clinic-config/room-node-chuyen`, nhật ký
   `clinic_config.room_node_chuyen` trước → sau). Sửa việc của phòng không xoá ★
   (`set_room_nodes` chỉ xoá bước bị bỏ). Cảnh báo nhẹ "chức năng chưa có phòng chuyên"
   (`overview.chua_co_phong_chuyen`), không chặn.
2. **Sắp đến ở MỌI phòng làm được vẫn hiện tất cả khách** (không ẩn theo ★). Khách có
   chỉ định tick sẵn lên đầu, nhãn ★ / "hướng dẫn: P. X". Khách đã chờ / làm ở phòng
   này không ở Sắp đến của phòng (nhận tiếp bằng "Nhận thêm" trên ô khách). Chỉ định
   đang CHỜ / đang LÀM ở phòng khác VẪN HIỆN ở Sắp đến mọi phòng làm được, nhãn "đang
   chờ / đang làm ở P. X" (đang chờ thì nhận chéo được), nhưng KHÔNG vào số "sắp đến"
   (`tinh_so` — đã đếm ở "đang chờ / đang làm" phòng kia).
3. **Mỗi khách MỘT ô** ở mọi danh sách (sắp đến · đang chờ · đang làm · đã xong): trong
   ô các chỉ định phòng làm được + trạng thái (sắp đến [hướng dẫn: P. X] · chờ ở đây ·
   đang làm · xong · đang ở P. Y) — `hang_cho.chi_dinh_khach`, `sap_den_phong[].chi_dinh`.
   Mọi con số đếm KHÁCH; mỗi khách đúng một nhóm (đang làm > đang chờ). Bắt đầu / Xong /
   hoàn tác vẫn theo từng chỉ định.
4. **Nhận theo từng chỉ định** (`nhan-vao-phong` thân `chi_dinh_ids`): tick sẵn chỉ định
   hướng dẫn tới phòng; hoặc chưa hướng dẫn mà phòng là phòng chuyên ★. Còn lại để trống,
   tick được. Phải tick ≥1 (`CHUA_CHON_CHI_DINH`). "Nhận thêm" = cùng lệnh. Hoàn tác
   Nhận theo đúng chỉ định vừa nhận (`hoan-tac-nhan` thân `chi_dinh_ids`).
5. Chỉ định không nhận vẫn ở Sắp đến của phòng khác, kèm "khách đang ở P. …".
6. ~~Xong chỉ định cuối → tự nhả~~ — BỎ (7b): Xong chỉ đổi trạng thái chỉ định ấy.
7. Quầy thu / bàn khám: ô hướng dẫn gợi ý sẵn phòng chuyên khi đúng MỘT phòng ★
   (`phong_chon_duoc[].goi_y`, `goi-y-phong.goi_y_chuyen`) — gợi ý, không tự lưu. Phiếu
   hướng dẫn chưa chọn phòng: in phòng chuyên (một phòng), không thì "các phòng làm được".

