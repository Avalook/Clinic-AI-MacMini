---
name: lam-mot-pr
description: Quy trình làm MỘT PR Mức 2/3 của ClinicAI từ lúc nhận việc tới lúc chờ Tuyền merge — test ca biên trước, thử ngược phải thấy đỏ, kiểm nhanh trước CI, CI đúng SHA, agent soát, thân PR đủ khuôn. Dùng mỗi khi bắt đầu một PR có code/test/migration (mọi chặng của kế hoạch xét nghiệm đối tác và việc Mức 2/3 khác), hoặc khi Tuyền nói "làm PR", "làm chặng", "sửa lỗi này".
---

# Làm một PR — từ nhận việc tới chờ merge

Rút từ chặng 0 xét nghiệm đối tác (05/11/2026). Mỗi bước có lý do đã cắn thật.
Luật thiết kế: `.claude/rules/thiet-ke-code.md`. Khuôn báo cáo: SO-LUAT 12.4.

## 1. Trước khi viết code
1. Dòng đầu: "Mức N · ước ~X phút". Mức 3 thì kế hoạch phải đã duyệt — dẫn mục.
2. Nhánh mới từ `origin/main` mới nhất (`git fetch` trước). Một PR một nhánh.
3. Việc chạm nhiều tầng → agent `tim-cho-sua`. Tìm hàm đang trả lời câu hỏi
   này trước khi viết hàm mới (luật 1).
4. Viết ra (vào nháp thân PR) **danh sách ca biên và kịch bản bấm thử TRƯỚC** khi code —
   lấy từ kế hoạch nếu có. Không viết kịch bản sau khi code xong.

## 2. Test trước, và test phải đo được
- Mỗi ca biên một test. **Sửa lỗi:** viết test tái hiện, cho thấy ĐỎ, rồi mới sửa.
- **Thử ngược bắt buộc:** làm hỏng đúng chỗ code mà test canh (bỏ một dòng khoá, đổi
  một điều kiện) → test phải ĐỎ → trả code lại. Không đỏ = test không đo gì, viết lại.
- **Test tranh chấp:** ép hai bên chen nhau bằng điều kiện trong DB (hai kết nối, giao
  dịch 1 INSERT chưa commit, giao dịch 2 ghi, rồi commit 1) — **không** dùng `sleep`.
  Kiểm KẾT QUẢ (một dòng thắng; người thua nhận 409 câu tiếng Việt, không 500), không
  kiểm cơ chế khoá. Bất biến đã ép ở DB thì ghi trong comment test (SO-LUAT Phần 6).
- Không `sleep` nào trong `src/clinicai` để phục vụ test.
- **Fixture:** chỉ `import` đúng fixture cần; không nạp module test có fixture
  `autouse` qua `pytest_plugins` (nó áp lên MỌI test trong phiên).
- Chạy test bằng `scripts/test-nhanh.sh <tệp…>`. Không sửa kỳ vọng của test cũ cho xanh.

## 3. Trước CI
- Hook `kiem-truoc-ci.sh` tự chạy ruff, mypy `src/` (đúng phạm vi CI, gồm cả test),
  tenant-scope, `ban-do-code.py --kiem` khi gọi `ci-may.sh`. Đỏ thì sửa — đừng lách
  bằng `BO_KIEM_TRUOC_CI=1` khi Tuyền chưa cho.
- Thêm tệp test hay đổi router/route đều có thể làm lệch bản đồ → `python3 scripts/ban-do-code.py`, commit.
- Mọi thứ đã commit. CI chạy trên một SHA, không trên cây bẩn.

## 4. CI, soát, mở PR
1. `./scripts/ci-may.sh --bao-github` — một lần, ở cuối. Chạy nền, trong lúc chờ gọi
   agent `soat-thiet-ke` (song song được).
2. Soát ra CHẶN → sửa → commit mới → **CI lại trên HEAD mới**. NÊN SỬA không chặn →
   ghi vào kế hoạch (mục "Việc mang sang") hoặc `docs/DANG-LAM.md`, không chỉ memory.
3. Thân PR có:
   - bảng SHA: `soát | CI xanh | HEAD` — chỉ mở để merge khi HEAD = SHA CI xanh, hoặc
     chỉ khác tệp sinh đã `--kiem` đạt;
   - dòng KẾT LUẬN của `soat-thiet-ke`;
   - "Đường cũ: … → xử lý: …" (luật 2);
   - khuôn 12.4: đã đổi gì · kịch bản bấm thử · KHÔNG đổi · rủi ro còn lại · bảng nút/link đã đụng.
4. **Dừng ở đây.** Gửi Tuyền link PR + dòng KẾT LUẬN + SHA. Tuyền bấm merge (chế độ
   tự động chặn AI tự merge PR của mình — đúng ý, không tìm đường vòng).

## 5. Sau merge
- `git fetch`, kiểm `origin/main` chứa đúng SHA đã CI. Xoá nhánh, worktree thừa.
- Rút **bài học**: điều gì Tuyền phải nhắc tay trong PR này? Đề xuất MỘT dòng luật và
  chỗ đặt (hook > test CI > `.claude/rules` > skill này). Không lưu vào memory máy làm
  chỗ chính — memory không theo repo.

## 6. Bẫy trên máy Mac
- Phiên đang mở KHÔNG nạp hook/agent mới thêm vào `.claude/` — kiểm hook bằng JSON qua stdin (`{"tool_input":{"command":"…"}}`) hoặc mở phiên mới.
- zsh KHÔNG tách biến chứa danh sách tệp (`$F` thành một chuỗi) — dùng `… | xargs <lệnh>`.
- `.venv` (symlink tới virtualenv của poetry) có thể bị xoá khi dọn cache — `ci-may` báo "Thiếu .venv" thì chạy `poetry install --no-root --with dev` ở checkout chính.
- Phiên Claude KHÔNG được ghi sang worktree khác (hook chặn) — việc song song thì mở hai phiên, mỗi phiên một worktree.
