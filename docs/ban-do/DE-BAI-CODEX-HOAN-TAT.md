# Đề bài cho Codex — làm nốt để bản đồ "hiểu hệ thống" đủ nhất có thể (22/10/2026)

Tuyền giao. Claude soạn. Làm lần lượt theo thứ tự; mỗi việc xong thì báo một dòng.
Khuôn: việc · ở đâu · kết quả cần đạt · cách kiểm · không đụng (`docs/MAU-GIAO-VIEC.md`).

## Luật chung — áp cho MỌI việc dưới

- Repo: `/Users/quangdang/Projects/Dr4Women-MacMini`. Gọi git bằng `/usr/bin/git` (hook RTK
  đổi `git` thành `rtk git` và bị chặn trong worktree).
- KHÔNG ghi lên VPS / prod / staging, KHÔNG merge, KHÔNG deploy, KHÔNG đẩy thẳng `main`.
  Câu SQL / lệnh nào cần chạy trên VPS: chỉ SOẠN (chỉ đọc, chỉ trả số đếm), Tuyền chạy.
- KHÔNG in, chép hay commit khoá API (`~/.clinicai-claude.env`, `.env.claude.local`,
  `~/.clinicai-avis.env`, `.env.prod`).
- KHÔNG sửa luật nghiệp vụ trong code. Tìm ra lỗi thật → ghi vào
  `docs/ban-do/hieu/phat-hien.json` (trạng thái `can_soat`), KHÔNG tự sửa — sửa code là việc
  Tuyền duyệt riêng.
- Test: `scripts/test-nhanh.sh <tệp test…>`. CI: `./scripts/ci-may.sh --bao-github`, chạy trong
  khung **08:00–23:00** (ngoài giờ có test đỏ giả theo giờ máy).
- Mỗi việc ghi rõ đã kiểm ở lớp nào; chưa chạy thật thì nói "chưa chạy thật".

## Việc 1 — Codex TỰ soát nốt ~760 ghi chú tệp (KHÔNG gọi API, không trần tiền)

Bản trên PR #521 (`54612bbb`): đã soát 1.329/2.089. KHÔNG chạy `--claude` hay AVIS nữa —
Codex tự đọc tệp và tự soát; script chỉ để in đề và nạp kết quả qua máy kiểm.

- Ở đâu: worktree `.claude/worktrees/ban-do-hieu`, nhánh `claude/ban-do-hieu` (PR #521).
- B1 — danh sách việc: `python3 scripts/ban-do-doc-lai.py --soat --xuat-lo 1 --ra /tmp/codex-soat`
  → `/tmp/codex-soat/lo-01.txt`, mỗi dòng một tệp chưa soát (tiền / kho / quyền đã xong trước).
- B2 — với TỪNG tệp P trong danh sách:
  1. `python3 scripts/ban-do-doc-lai.py --soat --in-de P` → in LỜI DẶN, tệp có số dòng, GHI CHÚ ĐÃ CÓ.
  2. Làm đúng lời dặn: đối chiếu luật / bẫy / hàm chính / test với CODE (số dòng trỏ đúng
     dòng thực thi, câu đúng điều code làm, không bỏ sót nhánh / ngoại lệ). Tiếng Việt lời
     thường, mỗi chuỗi ≤ 300 ký tự, không bịa.
  3. Ghi MỘT dòng vào `/tmp/codex-soat/kq.jsonl`:
     `{"tep": "P", "doi": {<chỉ khoá cần đổi, giá trị mới ĐẦY ĐỦ>, "da_sua": ["..."]}}`
     (ghi chú đã đúng → `{"tep": "P", "doi": {"da_sua": []}}`). Ghi dần, đừng gom cuối.
  4. Cứ ~100 tệp: `python3 scripts/ban-do-doc-lai.py --soat --nap /tmp/codex-soat/kq.jsonl`
     (nạp lại cả tệp an toàn — đã nạp thì ghi đè cùng nội dung). Dòng bị loại (`✗`) thì sửa
     lại đúng số dòng rồi nạp lại. Chạy lại B1 thì danh sách tự bớt tệp đã nạp.
- Tuyệt đối KHÔNG sửa tay `docs/ban-do/hieu/tep|test/*.json` — chỉ qua `--nap`.
- Kết quả: `soat-tep.json` ≈ 2.089 mục; `python3 scripts/ban-do-code.py --html` chạy được;
  `--kiem` khớp; commit `docs/ban-do/hieu`, push. Báo số tệp đã soát, số bị loại.

## Việc 2 — xác minh các "bẫy" agent mới tìm ra (chỉ đọc code + chạy test)

Mỗi điểm: đọc code, nếu được thì viết test nhỏ tái hiện (KHÔNG sửa code), rồi ghi vào
`phat-hien.json` với `trang_thai` = `dung` (có thật) / `can_soat` / `bao_oan`, kèm tệp:dòng
và bằng chứng một câu.

1. `scripts/vps-chuan-bi.sh`: `sshd -t && reload ssh || reload sshd` vẫn reload khi cấu hình hỏng;
   chép `authorized_keys` của root đè khoá của `clinicai`.
2. `src/clinicai/services/transcribe.py`: `_ensure_model` nạp đồng bộ trên vòng sự kiện → đứng API.
3. `scripts/supabase-local-nap.sh`: `docker cp` vào `/migrations` đã có → chép lồng, nạp bản cũ.
4. `src/clinicai/services/checkout_service.py`: thiếu cờ `chan_no` thì `chan` gộp tiền thừa, báo
   nhầm là nợ; danh sách chờ check-out không loại lượt đã đóng.
5. `scripts/provision-staff-logins.sh` dòng 93–124: nhánh gửi lời mời có thể không bao giờ chạy.
6. `ClinicalRecordForm.tsx`: lưu bệnh án là đơn thuốc tới nhà thuốc ngay, không bước duyệt
   (ghi là câu hỏi nghiệp vụ cho Tuyền, không phải lỗi).
7. Cảnh báo trùng SĐT: route `check-phone` đã tắt (410) mà test vẫn canh — cảnh báo nay đi
   đường nào, hay đã mất?
8. `DayNoiBoard.tsx` 123–125 / 417, `LichSuNotion.tsx` 281, `FeedbackBox.tsx` 69: lỗi hiển thị.

## Việc 3 — luật tiền / kho chưa có test canh

- Ở đâu: nhánh MỚI từ `main` (`codex/test-canh-luat-tien-kho`), PR riêng.
- Lấy luật có số dòng trong ghi chú các tệp thuộc khối `payment`, `pharmacy`, `kho_vat_tu`,
  `ke_toan`, `cong_no` (`docs/ban-do/hieu/tep/*.json`, trường `luat`), đối chiếu với mục
  `canh` của ghi chú test (`docs/ban-do/hieu/test/*.json`). Liệt kê luật CHƯA có test canh.
- Viết test DB cho tối đa 15 luật quan trọng nhất (tiền trước), không đổi code chạy thật.
  Test đỏ = lỗi thật → KHÔNG sửa code, đánh `xfail(strict=True)` kèm lý do + ghi `phat-hien.json`.
- Giờ / ngày trong test đặt thẳng vào dữ liệu, KHÔNG "now() ± N phút" (đỏ giả quanh nửa đêm).
- Kết quả: danh sách luật chưa canh (`docs/ban-do/hieu/luat-chua-canh.md`) + PR test, CI xanh.

## Việc 4 — chạy thật từng luồng chính, so với bản đồ

- Ở đâu: stack dev local (`scripts/dev-up.sh`, khách `DEMO-*`, tài khoản `@dr4women.local`);
  mô phỏng `scripts/mo-phong/` (`ngay_kham.py`).
- Chạy: tiếp đón → khám → chỉ định → thu tiền → phòng dịch vụ → đọc kết quả → Hoàn tất →
  check-out; bán thuốc; hoàn tiền; đóng ca. Mỗi bước so với "Tổng quan" và thẻ khối của bản đồ.
- Kết quả: `docs/ban-do/hieu/doi-chieu-chay-that.md` — chỗ bản đồ nói khác với chạy thật
  (tệp:dòng). Lệch là lỗi ghi chú thì sửa ghi chú (nhánh #521); lệch là lỗi code thì ghi
  `phat-hien.json`.
- Không đụng: không dùng DB staging local nạp từ bản sao prod (dữ liệu khách thật).

## Việc 5 — soạn câu kiểm dữ liệu prod lượt 4 (Tuyền chạy)

- Ở đâu: `docs/ban-do/hieu/kiem-du-lieu-prod-4.sql`, cùng khuôn lượt 1–3 (BEGIN READ ONLY,
  statement_timeout, chỉ `jsonb_build_object` số đếm, không in tên / SĐT khách).
- Nội dung: tiền theo NGÀY — báo cáo cuối ngày (luật `bao_cao_cuoi_ngay_service`) vs sổ gốc
  `payment_cycle` / `payment_refund` (30 ngày gần nhất, số ngày lệch + tổng lệch); tồn kho từng
  lô = tổng `inventory_txn` (số lô lệch); phiếu VOIDED có ngày thu ≠ ngày huỷ (đếm).
- Thử câu trên DB tạm nhân bản từ khuôn test trước (chạy không lỗi).

## Việc 6 — đối chiếu cấu hình VPS với repo (Tuyền chạy)

- Ở đâu: `scripts/so-cau-hinh-vps.sh` (chỉ đọc): in TÊN tệp + sha256 của các tệp repo quản lý
  trên VPS (`/etc/systemd/system/clinicai-*`, `Caddyfile`, `docker-compose*.yml` trong
  `/home/clinicai/clinicai`) để so với repo. KHÔNG in nội dung, KHÔNG đọc `.env*`.
- Kết quả: lệnh cho Tuyền chạy + bảng tệp lệch sau khi Tuyền dán kết quả.

## Việc 7 — gom câu hỏi nghiệp vụ cho Tuyền

- `docs/ban-do/hieu/cau-hoi-tuyen.md`: mỗi câu kèm ví dụ số và lựa chọn — giá tái khám; bỏ tick
  dịch vụ đã thu thành tiền thừa; khoá cứng thai kỳ / thuốc trả; 4 tệp test integration CI bỏ
  qua; `/traffic`; đơn thuốc không bước duyệt (việc 2.6); cảnh báo trùng SĐT (việc 2.7).

## Báo cáo cuối

Một bảng: việc · kết quả · tệp / PR / SHA · đã kiểm ở lớp nào · còn gì chờ Tuyền.
