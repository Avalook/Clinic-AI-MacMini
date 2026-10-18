# GIAO CHO CODEX — xử lý phát hiện của agent soát hệ thống

> Soạn 18/10/2026 theo khuôn `docs/MAU-GIAO-VIEC.md`. Dán nguyên khối dưới đây cho Codex.
> **Codex KHÔNG tự chọn việc.** Chỉ làm phát hiện mà NGƯỜI đã bấm "Nhận" trên máy duyệt
> (`so-duyet.jsonl`). Agent soát chỉ nêu ứng viên; "đúng hay sai" là việc của người.

```text
Đọc CLAUDE.md, docs/ai/HIEN-PHAP-AGENT.md (§2 thứ tự ưu tiên, §23–24 tự kiểm),
docs/ai/AGENT-SOAT.md, rồi docs/BAN-DO-SUA.md.

VIỆC:
  Xử lý các phát hiện agent soát đã được người NHẬN, mỗi phát hiện MỘT nhánh · MỘT PR.

DANH SÁCH VIỆC (nguồn duy nhất — không tự thêm):
  Tệp: <thư mục repo>/scripts/soat_he_thong/ket-qua/so-duyet.jsonl
  Lấy dòng có "quyet_dinh":"chap_nhan"; ghép với phat-hien.jsonl cùng thư mục theo "id"
  (chạy `.venv/bin/python scripts/soat_he_thong/chay.py` nếu chưa có). Phát hiện không có
  dòng "chap_nhan" = KHÔNG làm. Dòng "bo_qua"/"can_them" = không làm.

VỚI MỖI PHÁT HIỆN:
  1. Mở đúng trich_dan (tệp:dòng), TỰ chạy kịch bản trong phát hiện. Không tái hiện được
     → dừng, ghi "không tái hiện" vào thân PR nháp, KHÔNG sửa.
  2. Viết test tái hiện TRƯỚC, thấy đỏ trên main; rồi sửa tối thiểu; thấy xanh.
     (Bộ quét tĩnh: thêm một ca vào test_agent_soat.py chứng minh lỗi biến mất.)
  3. Mức việc ghi trên thẻ (muc_viec):
       2 → làm thẳng theo QUY TRÌNH CHUẨN trong CLAUDE.md.
       3 (tiền, kho, quyền, migration) → CHỈ nộp KẾ HOẠCH NGẮN (≤ 1 trang: sửa gì, vì sao,
           migration có không, cách diễn tập, cách hoàn tác) vào thân PR NHÁP rồi DỪNG chờ
           Tuyền duyệt. Không code migration khi chưa có chữ "duyệt".
  4. Một đợt tối đa 3 PR; PR > ~400 dòng (không tính test/migration/tệp sinh) thì tách.

KHÔNG ĐƯỢC ĐỤNG:
  · Staging, prod, VPS, `.env*`, khoá, bất kỳ lệnh ghi lên máy chủ. Không deploy. Không đẩy `main`.
  · scripts/soat_he_thong/** (agent soát) và docs/ai/** — đó là của người duyệt. Muốn đổi
    bộ quét vì phát hiện sai → ghi đề xuất vào PR, đừng sửa bộ quét cho "hết đỏ".
  · Không sửa phát hiện bằng cách THÊM tên vào danh sách bỏ qua của bộ quét.
  · Không xoá/đổi luật nghiệp vụ đã chốt trong memory ClinicAI; thấy mâu thuẫn → hỏi, đừng chọn.
  · Mọi thao tác nhân viên bấm phải HOÀN TÁC được và cập nhật ngay ở mọi màn liên quan.

ĐẦU RA mỗi PR:
  ./scripts/ci-may.sh --bao-github xanh (08:00–20:00) · python3 scripts/ban-do-code.py nếu đổi
  route/router/màn · báo cáo 4 mục SO-LUAT 12.4 (đã đổi gì · kịch bản bấm thử · KHÔNG đổi gì ·
  rủi ro còn lại) + bảng "nút/link đã đụng" · dòng đầu: id phát hiện + "Mức N".
  Sau khi xong: chạy lại bộ quét liên quan và dán kết quả (phát hiện đã biến mất, các phát
  hiện khác không đổi).
```

## Việc đầu tiên đề xuất (vẫn phải qua người bấm "Nhận")

Phát hiện `ghi_khong_dau_vet` cho `POST/PATCH /api/v1/service-prices` — **sửa giá không để lại
dấu vết** (đã kiểm tay: `PriceListService.add/update` trong `config_service.py`, bảng
`service_price` không có trigger hay bảng lịch sử). Mức 3 → Codex chỉ nộp KẾ HOẠCH: ghi sự
kiện đã khai ở `events/catalogue.py` kèm giá cũ → mới + người đổi, hay bảng lịch sử; cách hoàn
tác; ảnh hưởng báo cáo. Quang/Tuyền chọn phương án trước khi ai viết code.

## Vì sao Codex chưa được "nhận nguyên cả hệ thống"

* Danh sách hiện có là **ứng viên**, chưa phải lỗi đã xác nhận (62 thẻ: nhiều thẻ mức bằng chứng
  "suy luận"). Giao thẳng = Codex tự đoán đúng/sai thay người — vi phạm hiến pháp §14 (RECOMMEND).
* Tầng model chưa qua thước đo recall (xem `AGENT-SOAT.md`); chưa đủ tin để lấy thẻ của nó làm
  việc sửa mà không có người duyệt.
* Việc tiền/kho/quyền đã có luật "kế hoạch cho Tuyền duyệt trước" (CLAUDE.md, mức 3).
