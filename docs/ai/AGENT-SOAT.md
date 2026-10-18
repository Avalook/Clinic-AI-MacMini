# AGENT SOÁT HỆ THỐNG — hợp đồng vận hành

> Dựng 18/10/2026 theo yêu cầu của Quang: "xem toàn bộ hệ thống, biết lego nào thiếu
> liên kết, dữ liệu nào sai, chỗ nào mất dữ liệu chưa lưu, logic có vấn đề, đề xuất
> cải tiến — human in loop, quét thôi không làm hỏng prod."
> Hiến pháp: [`HIEN-PHAP-AGENT.md`](HIEN-PHAP-AGENT.md) (thắng khi mâu thuẫn).
> Khác với [`HOP-DONG-AGENT.md`](HOP-DONG-AGENT.md): bản đó là agent **vận hành** chạy
> trong worker `su-kien` lúc phòng khám làm việc; đây là agent **soát** chạy ngoài giờ
> trên máy dev, đọc code + dữ liệu, không sống trên VPS.

## Nó là gì, một câu

Một bộ quét **chỉ đọc** cho ra danh sách *ứng viên vấn đề*, mỗi ứng viên có đủ 10 mục
hiến pháp §13, mức bằng chứng (sự thật / suy luận / chưa biết) và trích dẫn `tệp:dòng`
script đã mở lại kiểm. **Người duyệt** từng cái. Agent không sửa gì, không quyết gì.

```
Nguon (đọc repo) ─► 5 bộ quét tĩnh ─┐
bat_bien (SQL chỉ-đọc, 16 câu) ─────┼─► cửa trích dẫn ─► phat-hien.jsonl ─► may_xem ─► người
   (DB local, hoặc kết quả do         │      (loại bịa dòng)   do-phu.json     (ghi so-duyet.jsonl)
    Tuyền chạy trên máy chủ rồi nạp)  ┘                        bao-cao.html
```

## Chạy

```bash
.venv/bin/python scripts/soat_he_thong/chay.py                      # 5 bộ quét tĩnh (~5 giây, 0 token)
.venv/bin/python scripts/soat_he_thong/chay.py --docker clinicai_thu_db   # + 16 bất biến trên DB LOCAL
.venv/bin/python scripts/soat_he_thong/may_xem.py                   # mở http://127.0.0.1:8765 để duyệt
```

Kết quả nằm ở `scripts/soat_he_thong/ket-qua/` (gitignore). Quyết định của người nằm ở
`ket-qua/so-duyet.jsonl`, gắn vào `id` ổn định nên lần quét sau không hỏi lại điều đã bỏ qua.

### Quét dữ liệu THẬT trên prod/staging (chỉ Tuyền làm, agent không có đường vào)

```bash
.venv/bin/python scripts/soat_he_thong/chay.py --in-sql > /tmp/bat-bien.sql   # 1. sinh tệp SQL chỉ-đọc, xem trước
# 2. Tuyền chạy trên máy chủ (mỗi bất biến một giao dịch READ ONLY, hết giờ 20 giây):
#    ssh clinic-vps 'docker exec -i <container-db> psql -U postgres -d postgres -X -q -t -A' < /tmp/bat-bien.sql > bat-bien-ket-qua.jsonl
.venv/bin/python scripts/soat_he_thong/chay.py --nap bat-bien-ket-qua.jsonl     # 3. nạp kết quả về, duyệt
```

Kết quả chỉ chứa **mã/số**, không tên, SĐT, ghi chú khách. Đừng chạy giờ cao điểm
(08:00–20:00) nếu máy chủ đang tải cao — 16 câu nhẹ, nhưng prod đã từng sập vì ít hơn thế.

## Lời hứa an toàn (và cái canh lời hứa)

| Lời hứa | Canh bằng |
|---|---|
| Không mạng, không import thư viện gọi ra ngoài | `test_agent_soat.py` quét AST từng tệp của agent |
| Không `ssh`/`scp`/`rsync`; không nghe `0.0.0.0` | cùng bài test (chuỗi hằng bị cấm) |
| Chỉ `chay.py`/`may_xem.py` được ghi tệp, chỉ vào `ket-qua/` | cùng bài test |
| SQL chỉ SELECT, không `FOR UPDATE`, `nextval`, `pg_sleep`… | `kiem_chi_select` + 9 ca bị từ chối + giao dịch `READ ONLY` |
| DB chỉ chạy được ở container local (`clinicai_thu*`, `chung_test*`, `ci_may*`) | `kiem_container` |
| Trang duyệt không bị trang web lạ lợi dụng ghi quyết định | chỉ `127.0.0.1`, kiểm Host/Origin/Content-Type, test CSRF |
| Không bịa số dòng | `kiem_trich_dan` mở lại tệp kiểm từng trích dẫn; sai thì loại, không đến tay người |
| Bộ quét thật sự bắt được lỗi | test **đột biến**: repo giả có lỗi cài sẵn, bộ quét phải ra đúng tập khoá |

## Năm bộ quét tĩnh — thấy gì, mù ở đâu

Mỗi bộ quét tự khai "đã nhìn gì / không nhìn được gì" trong `do-phu.json` — **0 phát hiện
chỉ có nghĩa SẠCH ở phần đã nhìn** (hiến pháp §3.2).

| Bộ quét | Tìm | Mức bằng chứng | Mù ở |
|---|---|---|---|
| `quyen_lego` | khối quyền không lego nào chứa · lego trỏ màn không có trang · ánh xạ vai↔lego chết | sự thật | quyền cấp mà route không ép (xem `cua_route`) |
| `cua_route` | route GHI không thấy cửa quyền (theo 4 tầng lời gọi) | suy luận | cửa ở proxy Next/middleware, RLS thuần |
| `ghi_khong_dau_vet` | route GHI không để lại sự kiện/nhật ký/dòng sổ cái | suy luận | trigger Postgres tự ghi lịch sử |
| `su_kien` | phát mà không khai · khai mà không phát · phát mà không ai nghe | sự thật / chưa biết | sự kiện phát bởi SQL; bên nghe có chạy thật không |
| `day_fe_be` | giao diện gọi `/api/v1/…` không có route · route ghi không ai gọi | suy luận / chưa biết | đường ghép động phức tạp, bảng ánh xạ ở route.ts |

**Đã thử rồi BỎ vì ồn:** kiểm RLS bằng đọc migration — 22 cảnh báo giả, vì RLS bật bằng vòng
lặp động trong SQL mà parse tĩnh không thấy. Thay bằng bất biến **D16** hỏi thẳng
`pg_class.relrowsecurity` trong DB thật (chính xác). Bài học: câu hỏi mà *trạng thái thật*
trả lời được thì hỏi trạng thái thật, đừng suy từ mã.

## Mười sáu bất biến dữ liệu (`bat_bien.py`)

D01 tồn lô thuốc âm · D02 tồn lô lệch tổng sổ kho · D03 vật tư tồn âm (chỉ thông tin — Quang
chốt không chặn) · D04 giao nhiều hơn số gán lô · D05 lịch kết thúc trước khi bắt đầu · D06 phiếu
thu huỷ thiếu lý do/mốc · D07 lượt chốt thiếu mốc · D08 hoàn tiền mở quá 3 ngày · D09 thuốc khách
trả chờ kiểm quá 2 ngày · D10 sự kiện kẹt quá 15 phút · D11 thuốc giao chưa gán lô quá 1 ngày ·
D12 lô hết hạn còn tồn · D13 lô lệch đơn vị bán · D14 lượt khám mở quá 2 ngày · D15 lịch đã
xác nhận quá hạn 1 ngày · D16 bảng có `clinic_id` đọc được mà chưa bật RLS.

D02 và D10 mang nhãn **suy luận** — dấu của sổ kho và ngưỡng 15 phút là suy từ cách đọc
code, chưa ai xác nhận. Thêm bất biến mới = thêm một `BatBien(...)` có `vi_sao`, `rui_ro`,
`de_xuat`; bài test tự kiểm nó là SELECT.

## Việc người duyệt làm

Mở `may_xem.py`, mỗi thẻ có 3 nút: **Nhận** (đưa vào hàng sửa, mỗi việc một PR nhỏ theo
`docs/MAU-GIAO-VIEC.md`) · **Bỏ qua** (bắt buộc lý do — lần quét sau không hỏi lại) · **Cần
thêm thông tin**. Thẻ ghi sẵn *mức việc* theo `CLAUDE.md`: mức 3 (tiền, kho, quyền, migration)
phải có kế hoạch cho Tuyền duyệt trước khi sửa.

Mỗi thẻ tự trả lời hộ bạn câu 4 trong checklist §24: *đây là sự thật, suy luận, dự báo hay đề
xuất?* — đọc nhãn màu ở đầu thẻ trước khi đọc nội dung.

## Chưa làm — và vì sao

| Cần | Tình trạng | Chặn bởi |
|---|---|---|
| **Tầng model** (đọc ngữ nghĩa: "logic này sai ở đâu", "chỗ nào nhập xong chưa lưu") | CHƯA. Khung đã chừa: mọi ứng viên của model sẽ đi qua cùng `kiem_trich_dan` và cùng `PhatHien` | HF: Quang đặt trần chi tiêu; AVIS: chưa rõ đơn vị 18,43 credits và địa chỉ gọi; chỉ gửi **code + dữ liệu đã che** ra ngoài |
| **Thước đo recall/precision** (20 lỗi đã biết, chạy trên commit TRƯỚC khi sửa) | CHƯA. Cần chạy trước khi tin tầng model | tầng model |
| **"Mất dữ liệu chưa lưu" phía giao diện** (form gõ dở bị mất khi chuyển trang) | CHƯA có bộ quét tĩnh đủ chính xác; sẽ là việc của tầng model, ứng viên do script chọn (component có ô nhập + không có lưu nháp) | tầng model |
| **Quét từng PR / hằng đêm** | CHƯA. Chạy 1 lần trước, xem số phát hiện thật, rồi mới quyết có gắn vào `ci-may.sh` không | quyết định của Tuyền (đổi quy trình CI) |
| **Luật thành test** ("route ghi thiếu cửa → CI đỏ") | `cua_route` hiện 0 phát hiện nên biến thành cổng được; CHƯA bật — thêm cổng CI là đổi luật nhóm | Tuyền |
