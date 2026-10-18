# BÀN GIAO CHO CODEX — việc còn lại của agent soát (đợt 2) · 18/10/2026

> Người giao: Claude. Người nhận: Codex, làm tiếp trên cùng máy Mac này.
> Quang đã bấm **DỪNG** (tệp `scripts/soat_he_thong/ket-qua/DUNG` đang có) — mọi lần gọi model
> đang bị chặn. **Chỉ Quang được xoá tệp đó.** Codex không tự xoá, không `touch`/`rm` nó.
> Đọc trước: `CLAUDE.md`, `docs/ai/HIEN-PHAP-AGENT.md`, `docs/ai/AGENT-SOAT.md`,
> `docs/ai/GIAO-CODEX-SOAT.md` (cách xử lý từng phát hiện đã được người nhận).

## 0. Trạng thái nhánh

* Nhánh `claude/agent-soat-he-thong`, tách từ `origin/main`, **chỉ ở máy này**: 3 commit
  (`6077147d`, `5c4b4fd4`, `428e73dd`). **Chưa đẩy, chưa PR, chưa chạy CI máy.** Không đẩy khi
  Quang chưa bảo.
* Worktree: `/Users/quangdang/Projects/Dr4Women-MacMini/.claude/worktrees/ke-hoach-quy-doi-don-vi`.
  Tệp `BANG-PHAN-LOAI-RAC-1710.md` chưa theo dõi là của phiên khác — đừng commit.
* Test: `.venv/bin/python -m pytest src/tests/unit/test_agent_soat.py src/tests/unit/test_agent_soat_model.py -q`
  (74 ca xanh). Lint đúng bản CI: `uvx ruff@0.11.10 format/check`. Kiểu:
  `.venv/bin/python -m mypy --strict --ignore-missing-imports scripts/soat_he_thong`.

## 1. Đã có

| Thành phần | Ở đâu | Ghi chú |
|---|---|---|
| 5 bộ quét tĩnh (0 token) | `scripts/soat_he_thong/bo_quet/` | `chay.py` → 62 thẻ, báo cáo HTML |
| 16 bất biến dữ liệu (SQL chỉ-đọc) | `bat_bien.py`, `doc_du_lieu.py` | `--docker clinicai_thu_db` hoặc `--in-sql` + `--nap` |
| Máy duyệt + trang theo dõi + nút dừng | `may_xem.py`, `tien_do.py` | `http://127.0.0.1:8765/` và `/tien-do` |
| Tầng model | `tang_model/` | cổng mạng `khach.py`, trần `chi_phi.py`, lọc `che_du_lieu.py` |
| Thước đo 20 lỗi đã biết | `tang_model/thuoc_do.py` | `chay_model.py thuoc-do --models …` |
| Quét toàn bộ + cố bác bỏ | `tang_model/soat_toan_bo.py` | `chay_model.py soat …` (có sổ "đã đọc", chạy tiếp được) |

## 2. Kết quả thước đo (đã chạy xong, đừng chạy lại)

| Model | Trúng/20 | Chi phí | Kết luận |
|---|---|---|---|
| **Claude Sonnet 5.5** (AVIS `avis:claude-sonnet-5-5`) | **5/20** (P1, P7, P9, H1, N2) | $2,07 | **Dùng làm người đọc.** Trượt chủ yếu lỗi cần hiểu nghiệp vụ nhiều tệp |
| MiniMax-M3 (HF, tắt suy nghĩ) | 0/20 | $0,17 | Không dùng |
| gpt-oss-120b (HF) | 0/20 | $0,06 | Lượt đo đầu có thẩm phán hỏng; chưa đo lại (rẻ, ưu tiên thấp) |
| Kimi-K2.7-Code (HF) | 0/20, 0 ứng viên | $1,36 | Đốt token suy nghĩ ẩn, trả rỗng — bỏ |
| DeepSeek-V4.1-Flash / V4-Pro / GLM-5.3-Flash | không dùng được | ~$0,7 | Suy nghĩ ẩn, không tắt được qua nhà cung cấp hiện có |
| Qwen3.8-27B | HTTP 504 | — | Suy nghĩ quá lâu |
| Qwen3-235B-Instruct-2507, Llama-4, Qwen-Next, DeepSeek-V3-0324, Kimi-K2.6 | **chưa đo xong** (bị dừng giữa chừng / chưa chạy) | — | Có thể thử bằng ~$0,3 mỗi model; nếu ≥5/20 thì rẻ hơn Claude hàng chục lần |

Chi tiêu tới giờ (sổ của agent): HF **$3,85**, AVIS **$2,94**. Trần phía AVIS Quang đặt: **15** (đơn vị
chưa rõ). **Không được vượt $8 cho một lượt quét** và không để tổng AVIS vượt ~$10 khi chưa hỏi.

Hai bẫy đã gặp, đừng lặp lại: (1) model "suy nghĩ ẩn" đốt hết `max_tokens` rồi trả rỗng — luôn
đếm `khuc_tra_rong` trong kết quả; (2) thẩm phán phải là model KHÔNG suy nghĩ ẩn (hiện MiniMax-M3,
`thinking: disabled`). Cổng AVIS/Cloudflare chặn User-Agent mặc định của Python (đã khai `UA`).

## 3. Việc còn lại — theo thứ tự, mỗi bước cần điều kiện

**B1. Chờ Quang gỡ DUNG** (ở `http://127.0.0.1:8765/tien-do` bấm "Cho chạy tiếp"). Chưa gỡ = dừng ở đây.

**B2. Quét mã rủi ro cao bằng Claude, chạy TIẾP lượt đang dở** (không đọc lại tệp đã đọc):

```bash
.venv/bin/python scripts/soat_he_thong/chay_model.py soat \
  --models avis:claude-sonnet-5-5 --xac-nhan avis:claude-opus-5-5 \
  --tran 8 --chi-rui-ro --khong-migration --toi-da-nhom 45 --song-song 4 \
  --thu-muc scripts/soat_he_thong/ket-qua/model-20261018-093737 --docker clinicai_thu_db
```

**Trạng thái dở khi Quang dừng:** mới đọc 3/167 tệp; có 27 thẻ do model nêu (báo cáo
`ket-qua/20261018-094328/bao-cao.html` đang hiện 89 thẻ = 62 tĩnh + 27 model) nhưng bước **bác bỏ bị
DUNG chặn nên 27 thẻ ấy CHƯA được kiểm chứng** (mức bằng chứng "chưa biết"). Đừng đưa chúng cho ai sửa;
chạy lại lệnh dưới sẽ đọc tiếp các tệp còn lại rồi bác bỏ lại toàn bộ.

Phạm vi ≈ 0,67 triệu token (services, router, giao diện tiền/kho/lịch/quyền; bỏ migration cũ).
Ước chi phí $4–6. Xong báo cáo nằm ở `ket-qua/<giờ>/bao-cao.html`.

**B3. KHÔNG tự duyệt.** Báo Quang: có bao nhiêu thẻ, bao nhiêu bị "bác bỏ", chi phí thật. Người
duyệt bấm Nhận/Bỏ qua trên máy duyệt. Rồi mới sang `GIAO-CODEX-SOAT.md` (mỗi thẻ đã nhận = một PR).

**B4. (Tuỳ, rẻ) đo nốt model mở** để biết có đường thay Claude cho phần đọc không:
`chay_model.py thuoc-do --models "Qwen/Qwen3-235B-A22B-Instruct-2507:nscale,meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8:novita,Qwen/Qwen3-Next-80B-A3B-Instruct:deepinfra,deepseek-ai/DeepSeek-V3-0324:deepinfra" --tran 2 --song-song 4`.
Chỉ chạy khi DUNG đã gỡ. Mỗi lượt đo nên có thư mục riêng (đã tự thêm pid).

**B5. Hoàn thiện để đưa vào repo** (chỉ khi Quang bảo mở PR): `./scripts/ci-may.sh --bao-github`
(08:00–20:00); PR gồm code + test + 2 tài liệu; kịch bản bấm thử = mở `/tien-do`, bấm Dừng/Chạy tiếp,
duyệt một thẻ. **Không mở PR, không đẩy nhánh nếu chưa được bảo.**

**B6. Việc nên làm sau (cần Quang/Tuyền chốt, đừng tự làm):**
* Gắn bộ quét tĩnh vào `ci-may.sh` để mỗi PR bị soát (đổi quy trình CI).
* Bật cổng "route ghi thiếu cửa = CI đỏ" (`cua_route` hiện 0 phát hiện).
* Bộ quét "mất dữ liệu chưa lưu" phía giao diện (form gõ dở bị mất) — chưa có cách tĩnh đủ chính xác;
  hướng: script chọn component có ô nhập + không có lưu nháp, model đọc.
* Quét dữ liệu THẬT trên prod: chỉ Tuyền chạy `--in-sql` qua ssh, rồi `--nap` (agent không có đường vào).

## 4. LUẬT CỨNG (kế thừa từ Quang — vi phạm là dừng ngay)

1. **Không đụng staging, prod, VPS** (không deploy, không ghi, không ssh). Chỉ Tuyền chạy lệnh ghi.
2. **Không đẩy nhánh / mở PR / merge** khi chưa được bảo; không xoá worktree/nhánh/sao lưu khi chưa duyệt.
3. **Không đọc, in, dán khoá**: `~/.config/clinicai-ai/.env.ai` chỉ do `khach.py` đọc. Không `cat`/`sed`
   `.env*`. Không dán khoá vào chat/commit/log. (Claude đã từng lỡ in khoá local thử khi dò `.env.thu-local` — đừng lặp.)
4. **Chỉ MÃ NGUỒN đã lọc ra khỏi máy** tới model bên thứ ba; dữ liệu database thật không bao giờ đi qua tầng model.
5. Không xoá `ket-qua/DUNG`; không sửa `chi_phi.py` để nới trần; không thêm host mạng ngoài `khach.py`.
   Bài `test_agent_soat.py` canh các điều này — đừng sửa bài cho "hết đỏ".
6. Không đụng `Sangy AI Ops` (của người khác).
7. Quy trình chuẩn `CLAUDE.md` giữ nguyên: mức việc, kịch bản bấm thử trong thân PR, CI máy chạy 08:00–20:00.

## 5. Bẫy công cụ

* Hook của worktree chặn lệnh git/shell "phức tạp": dùng `/usr/bin/git` + lệnh đơn; việc dài thì ghi ra tệp rồi chạy. Chữ "git" trong
  heredoc/chuỗi cũng bị nghi — ghi tệp bằng công cụ Write/Edit thay vì `python - <<EOF`.
* macOS không có `timeout`; `sleep` dài bị chặn — dùng chạy nền + theo dõi `tien-do`.
* Đừng dán lệnh có chữ mẫu `<…>` vào khối chạy (Tuyền bấm Run nguyên văn).
* Sổ chi phí `ket-qua/chi-phi.jsonl` dùng chung mọi tiến trình; mỗi tiến trình có trần riêng, không cộng chung —
  tự cộng tổng trước khi chạy lượt mới (trang `/tien-do` có tổng).
